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
import os
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.schemas import AlertEvent, WebhookConfig, WebhookEvent

logger = logging.getLogger(__name__)

WEBHOOK_SECRET = os.getenv("COMPLIANCE_WEBHOOK_SECRET", "changeme-webhook-secret")
WEBHOOK_TIMEOUT_SECONDS = int(os.getenv("COMPLIANCE_WEBHOOK_TIMEOUT", "5"))


def _sign_payload(body: bytes) -> str:
    """HMAC-SHA256 signature for webhook verification by consumers."""
    return hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def _build_payload(event_type: WebhookEvent, alert: AlertEvent) -> Dict[str, Any]:
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
    alert: AlertEvent,
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
            with urllib.request.urlopen(req, timeout=WEBHOOK_TIMEOUT_SECONDS) as resp:
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
