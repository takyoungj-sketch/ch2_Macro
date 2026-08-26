-- P3.1: 월간 해시 유지 UPSERT. 창에서 사라진 hash의 보강은 고아로 남긴다.
-- ON DELETE CASCADE 금지. FK가 있으면 옛 거래 DELETE가 막힌다.
-- 적용: psql "$BUILT_DATABASE_URL" -f db/069_built_enrichment_orphan.sql

ALTER TABLE built_transaction_enrichment
    DROP CONSTRAINT IF EXISTS built_transaction_enrichment_transaction_hash_fkey;

COMMENT ON TABLE built_transaction_enrichment IS
    '복합 마스킹 복원 확정분만. 원장 무수정. 미상은 행 없음 (D-047). 고아(원장에 없는 hash)는 국토부 정정 시 허용. FK 없음 (069).';
