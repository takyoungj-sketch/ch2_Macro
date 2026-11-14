import { useEffect, useState, type ReactNode } from "react";
import { fetchRentKeyStatus, type RentKeyStatus } from "../api/client";
import KeySplitC2Notice, { KeyStatusUnknownNotice, hasC2Siblings, type KeySplitC2Candidate } from "./KeySplitC2Notice";

/** 어떤 안내를 띄울지(테스트용으로 분리): C-2 → 분리 안내 / 조회 실패 → 확인 불가 / 그 밖(C-01 409 포함) → 안내 없음 */
export function rentGuardMode(s: RentKeyStatus | null): "c2" | "unknown" | "none" {
  if (s?.key_status === "ok" && hasC2Siblings(s.key_split_c2)) return "c2";
  if (s?.key_status === "unknown") return "unknown";
  return "none";
}

/**
 * 집합 2단계 C-2 — 임대 단지 상세를 열 때 키 상태를 확인해, 같은 동 동명 다른 건물이 나뉜 키면(가장 큰 그룹으로 열림)
 * 상세 위에 분리 안내를 띄운다. 조회 실패는 「확인 불가」 안내. C-01 분할(409)은 지금처럼 상세를 그대로 연다.
 */
export default function RentKeySplitGuard({
  buildingKey,
  displayName,
  onOpenKey,
  children,
}: {
  buildingKey: string;
  displayName?: string;
  onOpenKey?: (key: string, candidate: KeySplitC2Candidate) => void;
  children: ReactNode;
}) {
  const [status, setStatus] = useState<RentKeyStatus | null>(null);
  useEffect(() => {
    let alive = true;
    setStatus(null);
    void fetchRentKeyStatus(buildingKey).then((s) => {
      if (alive) setStatus(s);
    });
    return () => {
      alive = false;
    };
  }, [buildingKey]);
  const mode = rentGuardMode(status);
  return (
    <>
      {mode === "c2" && status?.key_status === "ok" && status.key_split_c2 ? (
        <KeySplitC2Notice note={status.key_split_c2} displayName={displayName} onOpenKey={onOpenKey} />
      ) : null}
      {mode === "unknown" && status?.key_status === "unknown" ? <KeyStatusUnknownNotice reason={status.reason} /> : null}
      {children}
    </>
  );
}
