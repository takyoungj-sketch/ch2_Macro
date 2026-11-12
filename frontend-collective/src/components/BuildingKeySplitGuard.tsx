import { useEffect, useState, type ReactNode } from "react";
import { fetchBuildingKeyStatus, type BuildingKeyStatus } from "../api/client";

/**
 * 집합 2단계 — 분할된 옛 단지 키로 상세를 열면 후보를 보여 준다.
 * 1:1 로 바뀐 키는 서버(key_remap)가 그대로 새 키로 처리하므로 여기서는 분할만 다룬다.
 */
export default function BuildingKeySplitGuard({
  buildingKey,
  displayName,
  onClose,
  children,
}: {
  buildingKey: string;
  displayName?: string;
  onClose: () => void;
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

  if (status?.key_status !== "split") return <>{children}</>;
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
