from typing import List, Optional

from app.schemas import AnalysisEntry, WalletInput, WalletScore
from app.storage.runtime import sqlite_connection


def parse_tags(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def serialize_tags(tags: List[str]) -> str:
    return ",".join(tag.strip() for tag in tags if tag.strip())


def analysis_from_row(row) -> AnalysisEntry:
    return AnalysisEntry(
        id=row["id"],
        created_at=row["created_at"],
        chain=row["chain"],
        address=row["address"],
        score=row["score"],
        risk_level=row["risk_level"],
        explanation=row["explanation"],
        tags=parse_tags(row["tags"]),
    )


def save_analysis(
    tenant_id: str,
    wallet: WalletInput,
    scored: WalletScore,
    explanation: str,
    created_at: str,
    db_path: Optional[str] = None,
) -> AnalysisEntry:
    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO analyses (
                tenant_id,
                created_at, chain, address, txn_24h, volume_24h_usd,
                sanctions_exposure_pct, mixer_exposure_pct, bridge_hops,
                score, risk_level, explanation, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')
            """,
            (
                tenant_id,
                created_at,
                wallet.chain,
                wallet.address,
                wallet.txn_24h,
                wallet.volume_24h_usd,
                wallet.sanctions_exposure_pct,
                wallet.mixer_exposure_pct,
                wallet.bridge_hops,
                scored.score,
                scored.risk_level,
                explanation,
            ),
        )
        conn.commit()
        row_id = cursor.lastrowid if cursor.lastrowid is not None else 0

    return AnalysisEntry(
        id=row_id,
        created_at=created_at,
        chain=wallet.chain,
        address=wallet.address,
        score=scored.score,
        risk_level=scored.risk_level,
        explanation=explanation,
        tags=[],
    )


def list_recent_analyses(
    tenant_id: str, limit: int = 20, db_path: Optional[str] = None
) -> List[AnalysisEntry]:
    with sqlite_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, chain, address, score, risk_level, explanation, tags
            FROM analyses
            WHERE tenant_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (tenant_id, limit),
        ).fetchall()

    return [analysis_from_row(row) for row in rows]


def update_analysis_tags(
    analysis_id: int,
    tenant_id: str,
    tags: List[str],
    db_path: Optional[str] = None,
) -> Optional[AnalysisEntry]:
    tags_str = serialize_tags(tags)
    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE analyses SET tags = ?
            WHERE id = ? AND tenant_id = ?
            """,
            (tags_str, analysis_id, tenant_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None

        row = conn.execute(
            "SELECT id, created_at, chain, address, score, risk_level, explanation, tags FROM analyses WHERE id = ? AND tenant_id = ?",
            (analysis_id, tenant_id),
        ).fetchone()

    if not row:
        return None
    return analysis_from_row(row)
