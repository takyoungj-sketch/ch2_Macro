import { useEffect, useState, type ReactNode } from "react";
import { fetchBuildingKeyStatus, type BuildingKeyStatus } from "../api/client";
import KeySplitC2Notice, { KeyStatusUnknownNotice, hasC2Siblings, type KeySplitC2Candidate } from "./KeySplitC2Notice";

/**
 * 집합 2단계 — 분할된 옛 단지 키로 상세를 열면 후보를 보여 준다.
 * 1:1 로 바뀐 키는 서버(key_remap)가 그대로 새 키로 처리하므로 여기서는 분할만 다룬다.
 * C-01(동 분할) 옛 키 = 409 → 아래 후보 대화상자(그대로).
 * C-2(같은 동 동명 다른 건물) 옛 키 = 가장 큰 그룹으로 열림 → 상세를 보여 주고 위에 분리 안내(KeySplitC2Notice).
 */
/** 어떤 화면을 그릴지(테스트용으로 분리): C-01 분할 → split 대화상자 / C-2 → 상세 + 분리 안내 / 그 밖 → 상세만 */
export function guardMode(status: BuildingKeyStatus | null): "split" | "c2" | "unknown" | "children" {
  if (status?.key_status === "split") return "split";
  if (status?.key_status === "unknown") return "unknown";
  if (status?.key_status === "ok" && hasC2Siblings(status.key_split_c2)) return "c2";
  return "children";
}

export default function BuildingKeySplitGuard({
  buildingKey,
  displayName,
  onClose,
  onOpenKey,
  children,
}: {
  buildingKey: string;
  displayName?: string;
  onClose: () => void;
  /** C-2 분리된 단지 링크를 눌렀을 때(없으면 링크 대신 글자만) */
  onOpenKey?: (key: string, candidate: KeySplitC2Candidate) => void;
  children: ReactNode;
}) {
  const [status, setStatus] = useState<BuildingKeyStatus | null>(null);
  useEffect(() => {
    let alive = true;
    setStatus(null);
    void fetchBuildingKeyStatus(buildingKey).then((s) => {
      if (alive) setStatus(s);
    });
    return () => {
      alive = false;
    };
  }, [buildingKey]);

  const mode = guardMode(status);
  if (mode === "unknown" && status?.key_status === "unknown") {
    return (
      <>
        <KeyStatusUnknownNotice reason={status.reason} />
        {children}
      </>
    );
  }
  if (mode === "c2" && status?.key_status === "ok" && status.key_split_c2) {
    return (
      <>
        <KeySplitC2Notice note={status.key_split_c2} displayName={displayName} onOpenKey={onOpenKey} />
        {children}
      </>
    );
  }
  if (mode !== "split" || status?.key_status !== "split") return <>{children}</>;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true">
      <div className="card max-w-md w-full space-y-3 text-sm">
        <p className="font-medium text-slate-800 dark:text-slate-100">{displayName || "단지"}</p>
        <p className="text-slate-600 dark:text-slate-300">{status.message}</p>
        <ul className="space-y-1 text-slate-700 dark:text-slate-200">
          {status.candidates.map((c) => {
            const where = [c.addr3, c.addr4, c.addr5].filter(Boolean).join(" ");
            return (
              <li key={c.building_key}>
                {c.display_name || displayName || "단지"}
                {where ? ` · ${where}` : ""} · {c.n_tx.toLocaleString()}건
              </li>
            );
          })}
        </ul>
        <p className="text-xs text-slate-500">목록에서 해당 동의 단지를 다시 선택해 주세요.</p>
        <div className="text-right">
          <button type="button" className="rounded border border-slate-300 px-3 py-1 text-xs text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800" onClick={onClose}>
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}
