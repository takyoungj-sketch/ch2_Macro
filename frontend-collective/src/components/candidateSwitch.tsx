/**
 * 집합 2단계 C-2 — 분리된 단지(후보)로 전환. 기존 행을 복사하지 않고, 후보 키의 실제 목록 행을 다시 조회한 뒤 상세를 연다.
 * 조회하는 동안 로딩, 실패하면 안내(현재 상세는 그대로 둔다). 집합·임대가 같은 파일을 쓴다(5앱 형식 패리티).
 */
import type { KeySplitC2Candidate } from "./KeySplitC2Notice";

export type CandidateSwitchState =
  | { status: "idle" }
  | { status: "loading"; key: string; label: string }
  | { status: "error"; key: string; label: string; message: string };

/** 후보의 동 주소 → 목록 API 필터. 구가 있는 시는 addr3 = 구·addr4 = 동, 그 밖은 addr3 = 읍면동. */
export function candidateFilter(c: KeySplitC2Candidate): { addr3List: string[]; addr4List: string[] } {
  const a3 = (c.addr3 ?? "").trim();
  const a4 = (c.addr4 ?? "").trim();
  return { addr3List: a3 ? [a3] : [], addr4List: a4 ? [a4] : [] };
}

/** 후보 키의 실제 행을 조회. 못 찾거나 실패하면 Error(사용자 안내 문장). */
export async function loadCandidateRow<R extends { building_key: string }>(
  key: string,
  candidate: KeySplitC2Candidate,
  fetchRows: (filter: { addr3List: string[]; addr4List: string[] }) => Promise<R[]>,
): Promise<R> {
  let rows: R[];
  try {
    rows = await fetchRows(candidateFilter(candidate));
  } catch {
    throw new Error("분리된 단지 자료를 불러오지 못했습니다. 잠시 뒤 다시 시도해 주세요.");
  }
  const hit = rows.find((r) => r.building_key === key);
  if (!hit) throw new Error("분리된 단지의 통계 행을 찾지 못했습니다(지금 기간·조건에 거래가 없을 수 있습니다).");
  return hit;
}

/** 후보 클릭 처리: 로딩 → 실제 행 조회 → 상세 전환(성공) / 안내(실패). */
export async function switchToCandidate<R extends { building_key: string }>(
  key: string,
  candidate: KeySplitC2Candidate,
  deps: {
    fetchRows: (filter: { addr3List: string[]; addr4List: string[] }) => Promise<R[]>;
    setSelected: (row: R) => void;
    setState: (s: CandidateSwitchState) => void;
    label: string;
  },
): Promise<void> {
  deps.setState({ status: "loading", key, label: deps.label });
  try {
    const row = await loadCandidateRow(key, candidate, deps.fetchRows);
    deps.setSelected(row);
    deps.setState({ status: "idle" });
  } catch (e) {
    deps.setState({ status: "error", key, label: deps.label, message: (e as Error).message });
  }
}

export function CandidateSwitchStatus({ state, onDismiss }: { state: CandidateSwitchState; onDismiss?: () => void }) {
  if (state.status === "idle") return null;
  return (
    <div
      className="fixed left-1/2 top-24 z-[61] w-[min(92vw,30rem)] -translate-x-1/2 rounded-lg border border-slate-300 bg-white p-3 text-xs text-slate-700 shadow-lg dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200"
      role={state.status === "error" ? "alert" : "status"}
      data-testid="candidate-switch-status"
    >
      {state.status === "loading" ? (
        <p>{state.label} 자료를 불러오는 중…</p>
      ) : (
        <div className="space-y-1">
          <p className="font-medium">{state.label}</p>
          <p>{state.message}</p>
          {onDismiss ? (
            <button type="button" className="text-blue-700 hover:underline dark:text-blue-300" onClick={onDismiss}>
              닫기
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
}
