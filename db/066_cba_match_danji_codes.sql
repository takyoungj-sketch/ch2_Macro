-- D·F 복수 K-apt 후보 코드 저장. 세대수는 합산, 시공사는 첫 단지 + 외.
-- danji_code VARCHAR(20)에는 코드를 여러 개 넣을 수 없어 별도 컬럼을 둔다.

ALTER TABLE collective_building_attributes
    ADD COLUMN IF NOT EXISTS match_danji_codes TEXT;

ALTER TABLE collective_building_attributes
    ALTER COLUMN builder_raw TYPE VARCHAR(500);

ALTER TABLE collective_building_attributes
    ALTER COLUMN developer_raw TYPE VARCHAR(500);

COMMENT ON COLUMN collective_building_attributes.match_danji_codes IS
    'D·F 복수 K-apt 단지코드(쉼표 구분). danji_code는 정렬 후 첫 코드. 세대수는 합산, 시공사는 첫 단지 기준에 외';
