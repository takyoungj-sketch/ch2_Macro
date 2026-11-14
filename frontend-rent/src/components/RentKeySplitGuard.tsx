import { useEffect, useState, type ReactNode } from "react";
import { fetchRentKeyStatus } from "../api/client";
import KeySplitC2Notice, { hasC2Siblings, type KeySplitC2Candidate, type KeySplitC2Note } from "./KeySplitC2Notice";

/**
 * 집합 2단계 C-2 — 임대 단지 상세를 열 때 키 상태를 확인해, 같은 동 동명 다른 건물이 나뉜 키면(가장 큰 그룹으로 열림)
 * 상세 위에 분리 안내를 띄운다. 키 확인 실패·C-01 분할(409)은 지금처럼 상세를 그대로 연다(임대 C-01 화면은 바꾸지 않음).
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
  const [note, setNote] = useState<KeySplitC2Note | null>(null);
  useEffect(() => {
    let alive = true;
    setNote(null);
    void fetchRentKeyStatus(buildingKey).then((s) => {
      if (alive) setNote(s?.key_split_c2 ?? null);
    });
    return () => {
      alive = false;
    };
  }, [buildingKey]);
  return (
    <>
      {hasC2Siblings(note) ? <KeySplitC2Notice note={note} displayName={displayName} onOpenKey={onOpenKey} /> : null}
      {children}
    </>
  );
}
