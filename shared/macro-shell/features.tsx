// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
/**
 * D-085 관리자 전용 기능 스위치 — 5앱 공통.
 *
 * - `GET /api/features` 를 한 번 읽어 켜진 기능 이름을 보관한다(앱 전체 공유 저장소).
 * - 꺼진 기능의 탭·칸은 그리지 않는다. 관리자에게만 켜진 기능에는 「비공개」 배지를 단다.
 * - 같은 탭에서 권한이 바뀌면(로그인·로그아웃·staff 세션 만료) 화면 데이터를 비운다:
 *   창이 다시 보일 때 다시 읽고, 기능 목록이 달라졌으면 페이지를 새로 불러온다.
 *   react-query 캐시·모달 상태·불러온 거래목록이 모두 메모리에서 사라진다.
 */
import { useSyncExternalStore } from "react";

export type FeatureName = "rent_regression" | "land_regression" | "land_ledger_link";

type FeatureState = {
  loaded: boolean;
  features: ReadonlySet<string>;
  privateFeatures: ReadonlySet<string>;
};

const EMPTY: FeatureState = { loaded: false, features: new Set(), privateFeatures: new Set() };

let state: FeatureState = EMPTY;
let signature: string | null = null;
let inflight: Promise<void> | null = null;
let watching = false;
const listeners = new Set<() => void>();

function sig(features: string[], privateFeatures: string[]): string {
  return `${[...features].sort().join(",")}|${[...privateFeatures].sort().join(",")}`;
}

async function load(): Promise<void> {
  let features: string[] = [];
  let privateFeatures: string[] = [];
  try {
    const res = await fetch("/api/features", { credentials: "include", cache: "no-store" });
    if (res.ok) {
      const body = (await res.json()) as { features?: string[]; private?: string[] };
      features = Array.isArray(body.features) ? body.features : [];
      privateFeatures = Array.isArray(body.private) ? body.private : [];
    }
  } catch {
    // 읽지 못하면 모두 꺼진 것으로 본다(사용자 화면이 기본).
  }
  const next = sig(features, privateFeatures);
  if (signature !== null && next !== signature) {
    // 권한이 바뀌었다 — 관리자 때 받은 값이 화면에 남지 않게 새로 시작한다.
    window.location.reload();
    return;
  }
  signature = next;
  state = { loaded: true, features: new Set(features), privateFeatures: new Set(privateFeatures) };
  listeners.forEach((fn) => fn());
}

export function refreshFeatures(): Promise<void> {
  if (!inflight) {
    inflight = load().finally(() => {
      inflight = null;
    });
  }
  return inflight;
}

function startWatching() {
  if (watching || typeof window === "undefined") return;
  watching = true;
  void refreshFeatures();
  const onVisible = () => {
    if (document.visibilityState === "visible") void refreshFeatures();
  };
  document.addEventListener("visibilitychange", onVisible);
  window.addEventListener("focus", onVisible);
}

function subscribe(fn: () => void) {
  listeners.add(fn);
  startWatching();
  return () => {
    listeners.delete(fn);
  };
}

function snapshot() {
  return state;
}

/** 켜진 기능. 읽기 전(`loaded=false`)에는 모두 꺼진 것으로 다룬다. */
export function useFeatures() {
  const s = useSyncExternalStore(subscribe, snapshot, () => EMPTY);
  return {
    loaded: s.loaded,
    has: (name: FeatureName) => s.features.has(name),
    isPrivate: (name: FeatureName) => s.privateFeatures.has(name),
  };
}

export function useFeature(name: FeatureName): boolean {
  return useFeatures().has(name);
}

/** 관리자에게만 켜진 기능 옆에 붙이는 「비공개」 배지. 공개됐거나 꺼졌으면 그리지 않는다. */
export function PrivateFeatureBadge({ feature, className = "" }: { feature: FeatureName; className?: string }) {
  const { isPrivate } = useFeatures();
  if (!isPrivate(feature)) return null;
  return (
    <span
      className={`ml-1 inline-flex items-center rounded border border-amber-300 bg-amber-50 px-1 py-px text-[10px] font-semibold leading-none text-amber-800 dark:border-amber-700 dark:bg-amber-950/50 dark:text-amber-300 ${className}`}
      title="관리자에게만 보이는 기능입니다(D-085)."
    >
      비공개
    </span>
  );
}

/** 권한 변화 감시만 켠다(대상 기능이 없는 앱도 같은 동작을 갖게 — 형식 패리티). */
export function useFeatureWatch(): void {
  useSyncExternalStore(subscribe, snapshot, () => EMPTY);
}
