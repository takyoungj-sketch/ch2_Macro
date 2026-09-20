const NOTICE = [
  "상권통계는 읍·면·동이 아니라 선택한 시군구(구) 경계를 기준으로 합니다.",
  "한국부동산원 상업용부동산 임대동향조사 공표를 인용합니다. 주거 전월세 원장·전환율과 다른 통계입니다.",
  "부동산원이 획정한 대표 상권만 있습니다. 해당 시군구와 겹치는 상권이 없으면 인근에 공표 상권이 없는 것입니다.",
];

export default function SangkwonNoticeModal({
  open,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-labelledby="sangkwon-notice-title"
        className="max-w-md w-full rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 p-4 space-y-3"
      >
        <h2 id="sangkwon-notice-title" className="text-sm font-semibold text-slate-800 dark:text-slate-100">
          상권통계
        </h2>
        <div className="text-sm text-slate-600 dark:text-slate-300 space-y-2 leading-relaxed">
          {NOTICE.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onCancel}
            className="px-2.5 py-1 rounded border border-slate-200 dark:border-slate-600 text-xs text-slate-600 dark:text-slate-300"
          >
            취소
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="px-2.5 py-1 rounded bg-teal-600 text-white text-xs hover:bg-teal-700"
          >
            확인
          </button>
        </div>
      </div>
    </div>
  );
}
