-- 048c: 게시판 비밀글 (ch2_platform 전용)
-- 본문은 작성자·관리자만. 제목은 목록에 공개.

ALTER TABLE posts
    ADD COLUMN IF NOT EXISTS is_secret BOOLEAN NOT NULL DEFAULT FALSE;
