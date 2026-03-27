"""
Webhook delivery engine
-----------------------
Fires HTTP POST payloads to registered tenant webhook URLs
when alert events occur. Fire-and-forget with basic retry.
"""

import hashlib
import hmac
import json
import logging
import ipaddress
import socket
from urllib.parse import urlparse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Union

from app.config import is_production, webhook_secret, webhook_timeout_seconds
from app.schemas import Alert, WebhookConfig, WebhookEvent

logger = logging.getLogger(__name__)

def _sign_payload(body: bytes) -> str:
    """HMAC-SHA256 signature for webhook verification by consumers."""
    return hmac.new(webhook_secret().encode(), body, hashlib.sha256).hexdigest()


def validate_webhook_target(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError("Webhook URL must use http or https")
    if is_production() and parsed.scheme != "https":
        raise ValueError("Webhook URL must use https in production")
    if not parsed.hostname:
        raise ValueError("Webhook URL must include a hostname")
    if parsed.username or parsed.password:
        raise ValueError("Webhook URL cannot include embedded credentials")

    host = parsed.hostname.strip().lower()
    if host == "localhost":
        raise ValueError("Webhook URL cannot target localhost")

    try:
        direct_ip = ipaddress.ip_address(host)
        _reject_private_ip(direct_ip)
        return
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("Webhook hostname could not be resolved") from exc

    for info in infos:
        address = info[4][0]
        try:
            _reject_private_ip(ipaddress.ip_address(address))
        except ValueError as exc:
            raise ValueError("Webhook URL cannot target private or local network addresses") from exc


def _reject_private_ip(ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> None:
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise ValueError("private address blocked")


def _build_payload(event_type: WebhookEvent, alert: Alert) -> Dict[str, Any]:
    return {
        "event": event_type,
        "fired_at": datetime.now(timezone.utc).isoformat(),
        "data": {
            "id": alert.id,
            "tenant_id": alert.tenant_id,
            "created_at": alert.created_at,
            "trigger": alert.trigger,
            "chain": alert.chain,
            "address": alert.address,
            "score": alert.score,
            "risk_level": alert.risk_level,
            "title": alert.title,
            "body": alert.body,
        },
    }


def fire_webhooks(
    webhooks: List[WebhookConfig],
    event_type: WebhookEvent,
    alert: Alert,
) -> None:
    """
    Attempt to deliver alert payload to all matching webhook URLs.
    Failures are logged but never raised — delivery is best-effort.
    """
    if not webhooks:
        return

    for hook in webhooks:
        if not hook.active:
            continue
        if event_type not in hook.events:
            continue

        try:
            validate_webhook_target(hook.url)
        except ValueError as exc:
            logger.warning("Webhook skipped: url=%s error=%s", hook.url, str(exc))
            continue

        payload = _build_payload(event_type, alert)
        body = json.dumps(payload).encode("utf-8")
        sig = _sign_payload(body)

        req = urllib.request.Request(
            hook.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Compliance-Event": event_type,
                "X-Compliance-Signature": f"sha256={sig}",
                "User-Agent": "ComplianceCopilot/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=webhook_timeout_seconds()) as resp:
                logger.info(
                    "Webhook delivered: url=%s event=%s status=%s",
                    hook.url,
                    event_type,
                    resp.status,
                )
        except Exception as exc:
            logger.warning(
                "Webhook delivery failed: url=%s event=%s error=%s",
                hook.url,
                event_type,
                str(exc),
            )
