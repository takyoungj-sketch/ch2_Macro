/**
 * 화면 식별 헤더 `X-CH2-Screen` (집합 1단계 C-05 경고·집계 모드).
 *
 * 값은 `앱/화면` 수준만 담는다(예: `collective/commercial-detail`). 사용자·지역·값 정보는 넣지 않는다.
 * 서버는 받지 않는 파라미터 **이름**을 이 화면 식별자와 함께 집계한다.
 */

type HeaderBag = { set?: (name: string, value: string) => unknown; [key: string]: unknown };
// axios 타입에 의존하지 않도록 구조 타입만 쓴다(shared 폴더에는 node_modules 가 없다).
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type InterceptableClient = { interceptors: { request: { use: (fn: (config: any) => any) => unknown } } };

export const SCREEN_HEADER = "X-CH2-Screen";

let currentScreen: string | null = null;

/** 모달·상세 화면이 열릴 때 화면 이름을 지정한다. 닫힐 때 null 로 되돌린다. */
export function setApiScreen(screen: string | null): void {
  currentScreen = screen && screen.trim() ? screen.trim() : null;
}

export function apiScreenValue(app: string, base: string): string {
  return `${app}/${currentScreen ?? base}`;
}

/** axios 인스턴스에 화면 식별 헤더를 붙인다. base 는 화면 지정이 없을 때 쓰는 기본 화면 이름. */
export function attachApiScreenHeader<T extends InterceptableClient>(client: T, app: string, base = "main"): T {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  client.interceptors.request.use((config: any) => {
    const value = apiScreenValue(app, base);
    const headers = (config.headers ?? {}) as HeaderBag;
    if (typeof headers.set === "function") headers.set(SCREEN_HEADER, value);
    else headers[SCREEN_HEADER] = value;
    config.headers = headers;
    return config;
  });
  return client;
}
