export const PENDING_NOTICE = "확인되지 않은 거래 포함";

export default function RentPendingNotice({ pendingN }: { pendingN?: number | null }) {
  if (!pendingN || pendingN <= 0) return null;
  return <span className="ml-1 text-amber-700 dark:text-amber-300">{PENDING_NOTICE}</span>;
}
