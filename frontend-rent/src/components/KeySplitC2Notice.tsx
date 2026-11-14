/**
 * 집합 2단계 C-2 — 같은 이름·같은 동 안의 다른 건물이 따로 나뉜 단지 키.
 * 서버(key_remap)는 옛 키를 가장 큰 그룹으로 열고 응답에 key_split_c2 를 붙인다(임대 /api/rent/buildings/{key}/key-status).
 * 집합 frontend-collective/src/components/KeySplitC2Notice.tsx 와 같은 파일(5앱 형식 패리티). 임대 C-01 409 처리는 바꾸지 않음.
 */
export type KeySplitC2Candidate = {
  building_key: string;
  split_part: number;
  n_tx: number;
  display_name?: string;
  addr3?: string | null;
  addr4?: string | null;
  addr5?: string | null;
};

export type KeySplitC2Note = {
  status: "has_split_siblings";
  message: string;
  building_key: string;
  new_keys: string[];
  candidates: KeySplitC2Candidate[];
};

export const C2_NOTICE_TEXT = "같은 이름의 단지 중 가장 큰 단지를 보고 있습니다.";

export function c2CandidateLabel(c: KeySplitC2Candidate, fallbackName?: string): string {
  const where = [c.addr3, c.addr4, c.addr5].filter(Boolean).join(" ");
  const name = c.display_name || fallbackName || "단지";
  return `${name}${where ? ` · ${where}` : ""} · ${c.n_tx.toLocaleString()}건`;
}

export function hasC2Siblings(note: KeySplitC2Note | null | undefined): note is KeySplitC2Note {
  return !!note && note.status === "has_split_siblings" && note.candidates.length > 0;
}

export const KEY_STATUS_UNKNOWN_TEXT = "단지 분리 여부를 확인할 수 없습니다.";

/** key-status 조회 실패(401·403·5xx·연결) — 정상으로 보지 않고 「확인 불가」로 알린다. */
export function KeyStatusUnknownNotice({ reason }: { reason?: string }) {
  return (
    <div
      className="fixed left-1/2 top-3 z-[60] w-[min(92vw,30rem)] -translate-x-1/2 rounded-lg border border-slate-300 bg-slate-50 p-2 text-xs text-slate-700 shadow dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200"
      role="status"
      data-testid="key-status-unknown"
    >
      {KEY_STATUS_UNKNOWN_TEXT} 같은 이름의 다른 단지가 섞여 있을 수 있습니다.{reason ? ` (${reason})` : ""}
    </div>
  );
}

export default function KeySplitC2Notice({
  note,
  displayName,
  onOpenKey,
}: {
  note: KeySplitC2Note;
  displayName?: string;
  onOpenKey?: (key: string, candidate: KeySplitC2Candidate) => void;
}) {
  return (
    <div
      className="fixed left-1/2 top-3 z-[60] w-[min(92vw,36rem)] -translate-x-1/2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 shadow-lg dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100"
      role="status"
      data-testid="key-split-c2-notice"
    >
      <p className="font-medium">{C2_NOTICE_TEXT}</p>
      <p className="mt-1">분리된 단지:</p>
      <ul className="mt-1 space-y-0.5">
        {note.candidates.map((c) => (
          <li key={c.building_key}>
            {onOpenKey ? (
              <button
                type="button"
                className="text-left text-blue-700 hover:underline dark:text-blue-300"
                onClick={() => onOpenKey(c.building_key, c)}
              >
                {c2CandidateLabel(c, displayName)}
              </button>
            ) : (
              <span>{c2CandidateLabel(c, displayName)}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
