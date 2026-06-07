-- 연립·다세대: 대지권면적(㎡). 아파트·오피스텔은 NULL.

ALTER TABLE collective_transactions
    ADD COLUMN IF NOT EXISTS land_area NUMERIC(14, 4);

COMMENT ON COLUMN collective_transactions.land_area IS
    '대지권면적(㎡) — 연립·다세대(rowhouse) 전용. MOLIT raw col H(iloc 7)';
