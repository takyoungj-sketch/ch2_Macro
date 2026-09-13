-- 고객의 소리: 유형 확장, 새 글은 기본 비밀
ALTER TABLE posts DROP CONSTRAINT IF EXISTS posts_category_chk;
ALTER TABLE posts
    ADD CONSTRAINT posts_category_chk
    CHECK (category IN ('question', 'bug', 'feature', 'data', 'other'));

ALTER TABLE posts ALTER COLUMN is_secret SET DEFAULT TRUE;
