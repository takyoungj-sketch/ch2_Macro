-- 048b: 게시판 지원 창구 — 상태 확장 · 공지 고정 (ch2_platform 전용)
-- 기존 048 설치분: resolved → answered, is_pinned 추가.
-- 신규 설치: 048이 이미 새 제약을 넣으므로 이 파일은 멱등.

ALTER TABLE posts DROP CONSTRAINT IF EXISTS posts_status_chk;

UPDATE posts SET status = 'answered' WHERE status = 'resolved';

ALTER TABLE posts
    ADD CONSTRAINT posts_status_chk
    CHECK (status IN ('open', 'checking', 'answered', 'planned', 'done'));

ALTER TABLE posts
    ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_posts_pinned_created ON posts (is_pinned DESC, created_at DESC);

UPDATE posts SET is_pinned = TRUE
 WHERE is_pinned = FALSE
   AND title IN ('ch2 project 게시판입니다.', 'CH2 프로젝트 통합 게시판 안내');
