-- land_transactions_resolved + 지목 7대분류 파생 컬럼
-- 선행: db/037_land_jimok_group_map.sql

CREATE OR REPLACE VIEW land_transactions_resolved AS
SELECT
    lt.*,

    COALESCE(r_zone.action_value, lt.zone_type) AS zone_type_resolved,
    COALESCE(r_land.action_value, lt.land_category) AS land_category_resolved,

    (r_zone.rule_id IS NOT NULL OR r_land.rule_id IS NOT NULL) AS has_correction,
    r_zone.rule_id  AS zone_correction_rule_id,
    r_land.rule_id  AS land_correction_rule_id,

    COALESCE(jg.group_code, 'other') AS jimok_group_code,
    COALESCE(jg.group_label, '기타') AS jimok_group_label

FROM land_transactions lt

LEFT JOIN LATERAL (
    SELECT rule_id, action_value
    FROM land_correction_rules
    WHERE is_active = TRUE
      AND conflict_type = 'zone_type'
      AND action       = 'set_zone_type'
      AND (beopjungri_code IS NULL OR beopjungri_code = lt.beopjungri_code)
      AND (contract_year   IS NULL OR contract_year   = lt.contract_year)
      AND (contract_month  IS NULL OR contract_month  = lt.contract_month)
      AND (contract_day    IS NULL OR contract_day    = EXTRACT(DAY FROM lt.contract_date)::INT)
      AND (area_sqm        IS NULL OR area_sqm        = lt.area_sqm)
      AND (total_price_10k IS NULL OR total_price_10k = lt.total_price_10k)
      AND (lot_display     IS NULL OR lot_display     = lt.lot_display)
    ORDER BY created_at DESC
    LIMIT 1
) r_zone ON TRUE

LEFT JOIN LATERAL (
    SELECT rule_id, action_value
    FROM land_correction_rules
    WHERE is_active = TRUE
      AND conflict_type = 'land_category'
      AND action       = 'set_land_category'
      AND (beopjungri_code IS NULL OR beopjungri_code = lt.beopjungri_code)
      AND (contract_year   IS NULL OR contract_year   = lt.contract_year)
      AND (contract_month  IS NULL OR contract_month  = lt.contract_month)
      AND (contract_day    IS NULL OR contract_day    = EXTRACT(DAY FROM lt.contract_date)::INT)
      AND (area_sqm        IS NULL OR area_sqm        = lt.area_sqm)
      AND (total_price_10k IS NULL OR total_price_10k = lt.total_price_10k)
      AND (lot_display     IS NULL OR lot_display     = lt.lot_display)
    ORDER BY created_at DESC
    LIMIT 1
) r_land ON TRUE

LEFT JOIN land_jimok_group_map jg
    ON jg.jimok_key = btrim(COALESCE(r_land.action_value, lt.land_category)::text);

COMMENT ON VIEW land_transactions_resolved IS
    'Master + Correction Rule + jimok_group(7대분류). '
    'zone_type_resolved / land_category_resolved / jimok_group_* 를 통계·API에서 사용.';
