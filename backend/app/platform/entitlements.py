"""Entitlement 조회·갱신."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

PRODUCTS = frozenset({"fieldnote", "macro"})
BUNDLE_PRODUCTS = ("fieldnote", "macro")


def list_entitlements(db: Session, user_id: int) -> dict[str, bool]:
    rows = db.execute(
        text(
            """
            SELECT product, active, expires_at
            FROM entitlements
            WHERE user_id = :uid
            """
        ),
        {"uid": user_id},
    ).mappings().all()
    now = datetime.now(timezone.utc)
    out = {p: False for p in PRODUCTS}
    for r in rows:
        product = str(r["product"])
        if product not in out:
            continue
        if not r["active"]:
            continue
        exp = r["expires_at"]
        if exp is not None and exp.replace(tzinfo=timezone.utc) if exp.tzinfo is None else exp < now:
            continue
        out[product] = True
    return out


def upsert_entitlement(
    db: Session,
    *,
    user_id: int,
    product: str,
    expires_at: datetime | None,
    source_sub_id: int | None = None,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO entitlements (user_id, product, active, expires_at, source_sub)
            VALUES (:uid, :product, TRUE, :exp, :sub)
            ON CONFLICT (user_id, product) DO UPDATE SET
                active = EXCLUDED.active,
                expires_at = EXCLUDED.expires_at,
                source_sub = EXCLUDED.source_sub,
                updated_at = now()
            """
        ),
        {"uid": user_id, "product": product, "exp": expires_at, "sub": source_sub_id},
    )


def grant_bundle(
    db: Session,
    *,
    user_id: int,
    expires_at: datetime | None,
    source_sub_id: int | None,
) -> None:
    for product in BUNDLE_PRODUCTS:
        upsert_entitlement(
            db, user_id=user_id, product=product, expires_at=expires_at, source_sub_id=source_sub_id
        )


def create_subscription(
    db: Session,
    *,
    user_id: int,
    product: str,
    source: str,
    external_id: str | None,
    period_end: datetime | None,
) -> int:
    row = db.execute(
        text(
            """
            INSERT INTO subscriptions (user_id, product, source, external_id, status, current_period_end)
            VALUES (:uid, :product, :source, :ext, 'active', :end)
            RETURNING id
            """
        ),
        {
            "uid": user_id,
            "product": product,
            "source": source,
            "ext": external_id,
            "end": period_end,
        },
    ).mappings().first()
    sub_id = int(row["id"])
    if product == "bundle":
        grant_bundle(db, user_id=user_id, expires_at=period_end, source_sub_id=sub_id)
    elif product in PRODUCTS:
        upsert_entitlement(
            db, user_id=user_id, product=product, expires_at=period_end, source_sub_id=sub_id
        )
    db.commit()
    return sub_id
