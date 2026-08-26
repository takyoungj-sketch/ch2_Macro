import { ENRICH_NOTICE } from "../utils/enrichmentConsent";

export default function EnrichConsentModal({
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
        aria-labelledby="enrich-consent-title"
        className="max-w-md w-full rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 p-4 space-y-3 shadow-lg"
      >
        <h2 id="enrich-consent-title" className="text-sm font-semibold text-slate-800 dark:text-slate-100">
          건축물대장 보강을 켭니다
        </h2>
        <ul className="text-xs text-slate-600 dark:text-slate-300 space-y-1.5 list-disc pl-4 leading-snug">
          {ENRICH_NOTICE.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        <p className="text-[11px] text-slate-500">
          기본통계는 국토부 원장만 씁니다. 목록·회귀의 용도지역 필터는 화면에 보이는 값과 같아집니다.
        </p>
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
            className="px-2.5 py-1 rounded bg-slate-800 text-white text-xs dark:bg-slate-200 dark:text-slate-900"
          >
            이해했습니다
          </button>
        </div>
      </div>
    </div>
  );
}
