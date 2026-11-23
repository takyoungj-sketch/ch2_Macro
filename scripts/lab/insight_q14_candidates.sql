BEGIN READ ONLY;
SET LOCAL enable_nestloop = off;
WITH
apt AS MATERIALIZED (
  SELECT building_key, contract_year, price, exclusive_area, btrim(beopjungri_code::text) AS bjd,
         regexp_match(btrim(lot_number), '^(산[[:space:]]*)?([0-9]{1,4})(-([0-9]{1,4}))?$') AS lot
  FROM collective_transactions
  WHERE asset_type='apartment' AND is_valid AND price>0 AND exclusive_area>0 AND contract_year BETWEEN 2021 AND 2025
),
shop AS MATERIALIZED (
  SELECT id, contract_year, btrim(beopjungri_code::text) AS bjd,
         regexp_match(btrim(lot_number), '^(산[[:space:]]*)?([0-9]{1,4})(-([0-9]{1,4}))?$') AS lot,
         floor, price, gross_area, building_year, building_use, contract_date
  FROM collective_commercial_transactions
  WHERE asset_type='collective_shop' AND is_valid AND price>0 AND gross_area>0 AND contract_year BETWEEN 2021 AND 2025
),
attr AS MATERIALIZED (
  SELECT DISTINCT ON (building_key) building_key, danji_code, match_tier, match_danji_codes
  FROM collective_building_attributes WHERE asset_type='apartment' ORDER BY building_key,snapshot_ym DESC
),
kapt AS MATERIALIZED (
  SELECT DISTINCT ON (danji_code) danji_code, danji_name, households, btrim(pnu::text) AS pnu
  FROM builder_master ORDER BY danji_code,snapshot_ym DESC
),
eligible AS (
  SELECT a.building_key, k.danji_code, k.pnu
  FROM attr a JOIN kapt k USING(danji_code)
  WHERE k.households>=1000 AND a.match_tier IN ('A','B','C')
    AND (a.match_danji_codes IS NULL OR position(',' in a.match_danji_codes)=0)
),
norm_apt AS (
  SELECT a.building_key,a.contract_year,e.danji_code,a.price,a.exclusive_area,
         bjd||CASE WHEN lot[1] IS NULL THEN '1' ELSE '2' END||lpad(lot[2],4,'0')||lpad(coalesce(lot[4],'0'),4,'0') AS pnu
  FROM apt a JOIN eligible e USING(building_key)
  WHERE a.bjd ~ '^[0-9]{10}$' AND a.lot[2]::integer>0
),
apt_year AS (
  SELECT danji_code,contract_year,count(*) AS n FROM norm_apt GROUP BY 1,2
),
parcel AS (
  SELECT pnu,min(danji_code) AS danji_code FROM norm_apt GROUP BY 1 HAVING count(DISTINCT danji_code)=1
),
norm_shop AS (
  SELECT id,contract_year,price,gross_area,floor,building_year,building_use,contract_date,bjd||CASE WHEN lot[1] IS NULL THEN '1' ELSE '2' END
     ||lpad(lot[2],4,'0')||lpad(coalesce(lot[4],'0'),4,'0') AS pnu
  FROM shop WHERE bjd ~ '^[0-9]{10}$' AND lot[2]::integer>0
),
shop_year AS (
  SELECT p.danji_code,s.contract_year,count(*) AS n
  FROM norm_shop s JOIN parcel p USING(pnu) GROUP BY 1,2
),
comparison AS (
  SELECT a.danji_code,a.contract_year
  FROM apt_year a JOIN shop_year s USING(danji_code,contract_year)
  WHERE a.contract_year IN (2024,2025)
),
matched_shops AS (
  SELECT c.danji_code,s.*
  FROM norm_shop s JOIN parcel p USING(pnu)
  JOIN comparison c ON c.danji_code=p.danji_code AND c.contract_year=s.contract_year
)
SELECT 'apt' AS kind, c.danji_code, c.contract_year AS year, k.danji_name, k.households, k.pnu AS kapt_pnu,
       NULL AS pnu, NULL AS shop_id, NULL AS floor, NULL AS building_year, NULL AS building_use, NULL AS contract_date,
       a.price / a.exclusive_area AS unit_price
FROM comparison c JOIN norm_apt a USING(danji_code,contract_year) JOIN kapt k USING(danji_code)
UNION ALL
SELECT 'shop', s.danji_code,s.contract_year,k.danji_name,k.households,k.pnu,s.pnu,s.id,s.floor,s.building_year,
       s.building_use,s.contract_date,s.price/s.gross_area
FROM matched_shops s JOIN kapt k USING(danji_code)
ORDER BY kind, year, danji_code, shop_id, unit_price;
COMMIT;
