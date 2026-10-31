import AnalysisHelpPanel from "./AnalysisHelpPanel";
import { BUILT_ENRICHMENT_HELP } from "../utils/builtSettingsHelp";

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
        aria-modal="true"
        aria-labelledby="enrich-consent-title"
        className="max-w-md w-full rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 p-4 space-y-3 shadow-lg"
      >
        <h2 id="enrich-consent-title" className="text-base font-semibold text-slate-800 dark:text-slate-100">
          건축물대장 정보 활용
        </h2>
        <div className="text-sm text-slate-600 dark:text-slate-300 space-y-2 leading-relaxed">
          <p>건축물대장 자료를 활용해 건물 구조 등 추가 정보를 분석에 사용할 수 있습니다. 모든 거래에 해당 정보가 연결되는 것은 아니며, 확인되지 않은 정보는 임의로 보충하지 않습니다.</p>
        </div>
        <div className="rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          <p className="font-semibold text-slate-800 dark:text-slate-100">기준 연결률 75.0%</p>
          <p>연결 498,568건 / 거래 665,030건 · 지분거래 포함</p>
          <p>대상: 2019년 이후 계약 · 고정 집계 기준: 2026-08-25</p>
          <p className="mt-2">실거래-대장 정보 연결률은 지역마다 다를 수 있습니다.</p>
        </div>
        <div className="inline-flex items-center gap-1 text-sm text-slate-600 dark:text-slate-300">활용·집계 기준 <AnalysisHelpPanel explain={BUILT_ENRICHMENT_HELP} title="건축물대장 활용·연결률 설명" /></div>
        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-1.5 rounded border border-slate-200 dark:border-slate-600 text-sm text-slate-600 dark:text-slate-300"
          >
            취소
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="px-3 py-1.5 rounded bg-blue-600 text-white text-sm hover:bg-blue-700"
          >
            확인
          </button>
        </div>
      </div>
    </div>
  );
}
