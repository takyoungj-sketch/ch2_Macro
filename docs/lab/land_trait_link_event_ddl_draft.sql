-- DRAFT ONLY. DO NOT APPLY. Not a numbered migration on purpose.
-- Rejudge event log for land_transaction_trait_link (design: LAND_LINK_GAP_REVIEW_20261110.md §3).
-- Applying it needs T's approval, a numbered db/ migration, and a deploy plan.

CREATE TABLE IF NOT EXISTS public.land_transaction_trait_link_event (
    event_id              bigserial PRIMARY KEY,
    transaction_hash      char(64)    NOT NULL,
    cycle_id              text        NOT NULL,      -- e.g. 202612-ledger or honam_v2-20261110
    target                text        NOT NULL,      -- honam_v2 | new_plate | approved_relink
    previous_status       text        NOT NULL,
    previous_rule_version text        NOT NULL,
    previous_trait_asof   date,
    previous_price_status text,
    new_status            text        NOT NULL,
    new_rule_version      text        NOT NULL,
    new_trait_asof        date,
    ledger_latest_asof    date        NOT NULL,      -- newest plate in the ledger used for judging
    judged_at             timestamptz NOT NULL DEFAULT now(),
    applied_by            text        NOT NULL
);

CREATE INDEX IF NOT EXISTS land_transaction_trait_link_event_hash
    ON public.land_transaction_trait_link_event (transaction_hash, judged_at);

-- Columns on the link table (backfill: judged_at = created_at, ledger_latest_asof = '2026-07-20').
ALTER TABLE public.land_transaction_trait_link
    ADD COLUMN IF NOT EXISTS judged_at timestamptz,
    ADD COLUMN IF NOT EXISTS ledger_latest_asof date;

-- Apply shape (one transaction per batch; abort if rowcount differs from the plan):
--   INSERT INTO land_transaction_trait_link_event (...) SELECT ... FROM plan;
--   UPDATE land_transaction_trait_link l
--      SET link_status = p.new_status, rule_version = p.new_rule_version, price_status = p.price_status,
--          official_price_won = p.official_price_won, price_year = p.price_year, trait_asof = p.trait_asof,
--          ledger_beopjungri_code = p.ledger_beopjungri_code, code_resolution = p.code_resolution,
--          recovered_lot = p.recovered_lot, judged_at = now(), ledger_latest_asof = :ledger_latest_asof
--     FROM plan p
--    WHERE l.transaction_hash = p.transaction_hash
--      AND l.link_status = p.previous_status                -- optimistic guard
--      AND l.link_status NOT IN ('exact', 'label_normalized'); -- linked rows are never overwritten here
