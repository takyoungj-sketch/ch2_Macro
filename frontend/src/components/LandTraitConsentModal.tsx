import { useEffect } from "react";
import { createPortal } from "react-dom";
import { LAND_TRAIT_MATCH_NOTE, LAND_TRAIT_NOTICE } from "../utils/landTraitConsent";

export default function LandTraitConsentModal({
  open,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      onCancel();
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open, onCancel]);

  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[140] flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-labelledby="land-trait-consent-title"
        className="max-w-md w-full rounded-lg border border-slate-200 bg-white p-4 space-y-3 shadow-lg"
      >
        <h2 id="land-trait-consent-title" className="text-sm font-semibold text-slate-800">
          토지특성 대장 보강
        </h2>
        <div className="text-sm text-slate-600 space-y-2 leading-relaxed">
          {LAND_TRAIT_NOTICE.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
        <p className="text-[11px] text-slate-500">{LAND_TRAIT_MATCH_NOTE}</p>
        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onCancel}
            className="px-2.5 py-1 rounded border border-slate-200 text-xs text-slate-600"
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
    </div>,
    document.body,
  );
}
