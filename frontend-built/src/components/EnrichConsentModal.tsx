import { ENRICH_MATCH_RATE, ENRICH_NOTICE } from "../utils/enrichmentConsent";

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
          건축물대장 보강
        </h2>
        <div className="text-sm text-slate-600 dark:text-slate-300 space-y-2 leading-relaxed">
          {ENRICH_NOTICE.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
        <p className="text-[11px] text-slate-500 dark:text-slate-400">{ENRICH_MATCH_RATE}</p>
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
            className="px-2.5 py-1 rounded bg-blue-600 text-white text-xs hover:bg-blue-700"
          >
            확인
          </button>
        </div>
      </div>
    </div>
  );
}
