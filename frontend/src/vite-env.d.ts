/// <reference types="vite/client" />

/**
 * Vite env vars used by the app.
 * Backend mirror: STATS_V2_ASSUMED_TODAY (see `docs/V2_STATS_PRODUCTION.md`).
 *
 * `VITE_API_TOKEN` — DECISIONS D-007: 빌드 시 주입된 토큰. 백엔드 `API_TOKEN` 과 동일 값.
 *   `frontend/src/api/client.ts` 가 axios 인터셉터에서 `X-Api-Token` 헤더로 보낸다.
 *   값이 없으면 헤더를 보내지 않는다(개발 모드 호환).
 */
interface ImportMetaEnv {
  readonly VITE_STATS_V2_ASSUMED_TODAY?: string;
  readonly VITE_API_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
