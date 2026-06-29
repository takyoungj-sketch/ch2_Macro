-- =============================================================================
-- land_transactions_resolved VIEW
-- Master(land_transactions)를 수정하지 않고 Correction Rule을 적용한 분석 뷰.
--
-- 사용 경로:
--   build_stats_v2.py / build_upper_stats_v2.py → 이 VIEW FROM
--   API paid.py / free_v2.py → (선택) 이 VIEW 참조
--
-- 보존 컬럼:
--   zone_type              ← Master 원본 (절대 불변)
--   land_category          ← Master 원본 (절대 불변)
--   zone_type_resolved     ← Rule 적용 후 분석용
--   land_category_resolved ← Rule 적용 후 분석용
--   has_correction         ← Rule이 1개 이상 적용됐으면 TRUE
-- =============================================================================

CREATE OR REPLACE VIEW land_transactions_resolved AS
SELECT
    lt.*,

    -- zone_type 보정 (Rule 없으면 원본 그대로)
    COALESCE(
        r_zone.action_value,
        lt.zone_type
    ) AS zone_type_resolved,

    -- land_category 보정 (Rule 없으면 원본 그대로)
    COALESCE(
        r_land.action_value,
        lt.land_category
    ) AS land_category_resolved,

    -- 보정 적용 여부
    (r_zone.rule_id IS NOT NULL OR r_land.rule_id IS NOT NULL) AS has_correction,

    -- 적용된 Rule ID (디버깅용)
    r_zone.rule_id  AS zone_correction_rule_id,
    r_land.rule_id  AS land_correction_rule_id

FROM land_transactions lt

-- zone_type 보정 Rule 탐색 (활성·최신 우선)
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

-- land_category 보정 Rule 탐색
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
) r_land ON TRUE;

COMMENT ON VIEW land_transactions_resolved IS
    'Master(land_transactions) + Correction Rule 적용 분석 뷰. '
    'zone_type_resolved / land_category_resolved 을 통계·API에서 사용. '
    'Master 원본(zone_type, land_category)은 항상 보존.';
