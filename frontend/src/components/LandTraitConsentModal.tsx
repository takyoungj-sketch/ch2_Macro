import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { LAND_TRAIT_MATCH_NOTE, LAND_TRAIT_MISSING_REASONS, LAND_TRAIT_NOTICE } from "../utils/landTraitConsent";
import "../../../shared/macro-shell/analysisGuide.css";
import { useModalFocus } from "../../../shared/ui-window/modalFocus";

export default function LandTraitConsentModal({ open, onCancel, onConfirm }: {
  open: boolean; onCancel: () => void; onConfirm: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const cancelRef = useRef(onCancel);
  cancelRef.current = onCancel;
  const backdropPress = useRef(false);
  useEffect(() => {
    if (!open) return;
    const dialog = dialogRef.current;
    const previousFocus = document.activeElement;
    dialog?.showModal();
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      cancelRef.current();
    };
    window.addEventListener("keydown", onKey, true);
    return () => {
      window.removeEventListener("keydown", onKey, true);
      dialog?.close();
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus({ preventScroll: true });
    };
  }, [open]);
  useModalFocus(open, dialogRef);
  if (!open) return null;
  return createPortal(
    <dialog ref={dialogRef} role="dialog" aria-labelledby="land-trait-consent-title" aria-describedby="land-trait-consent-summary"
      className="analysis-guide"
      onCancel={(event) => { event.preventDefault(); onCancel(); }}
      onPointerDown={(event) => { backdropPress.current = event.target === event.currentTarget; }}
      onClick={(event) => {
        if (backdropPress.current && event.target === event.currentTarget) onCancel();
        backdropPress.current = false;
      }}>
      <header className="analysis-guide__header">
        <p className="analysis-guide__eyebrow">CH2 Macro · 거래목록</p>
        <h2 id="land-trait-consent-title">공시지가 표시 안내</h2>
        <button type="button" autoFocus aria-label="공시지가 표시 안내 닫기" onClick={onCancel} className="analysis-guide__close">×</button>
      </header>
      <div className="analysis-guide__body" tabIndex={0}>
        <p id="land-trait-consent-summary">{LAND_TRAIT_NOTICE[0]}</p>
        <section className="analysis-guide__section">
          <h3>공시지가가 표시되지 않는 경우</h3>
          <ul className="analysis-guide__steps" style={{ listStyleType: "disc" }}>
            {LAND_TRAIT_MISSING_REASONS.map((line) => <li key={line}>{line}</li>)}
          </ul>
        </section>
        <section className="analysis-guide__section"><p>{LAND_TRAIT_NOTICE[1]}</p></section>
        <div className="analysis-guide__note"><p>{LAND_TRAIT_MATCH_NOTE}</p></div>
      </div>
      <footer className="analysis-guide__footer">
        <button type="button" onClick={onConfirm} className="analysis-guide__primary">확인</button>
      </footer>
    </dialog>, document.body,
  );
}
