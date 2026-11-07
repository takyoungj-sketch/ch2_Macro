// @ts-nocheck — React resolves through each frontend's runtime, as in the shared header.
import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import "./analysisGuide.css";

const shownThisVisit = new Set<string>();

interface Props {
  id: string;
  storageKey: string;
  title: string;
  triggerLabel: string;
  actionLabel: string;
  oncePerVisit?: boolean;
  children: ReactNode;
}

export default function GuideDialog({
  id,
  storageKey,
  title,
  triggerLabel,
  actionLabel,
  oncePerVisit = false,
  children,
}: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const preferenceRef = useRef<HTMLInputElement>(null);
  const backdropPress = useRef(false);
  const suppressed = useRef(false);

  function openGuide() {
    const dialog = dialogRef.current;
    if (!dialog || dialog.open || typeof dialog.showModal !== "function") return;
    try {
      suppressed.current = window.localStorage.getItem(storageKey) === "1";
    } catch {
      // Keep the in-memory choice when browser storage is unavailable.
    }
    if (preferenceRef.current) preferenceRef.current.checked = suppressed.current;
    backdropPress.current = false;
    dialog.showModal();
    shownThisVisit.add(storageKey);
    if (bodyRef.current) bodyRef.current.scrollTop = 0;
  }

  useEffect(() => {
    try {
      suppressed.current = window.localStorage.getItem(storageKey) === "1";
    } catch {
      // The guide also works without browser storage.
    }
    if (!suppressed.current && (!oncePerVisit || !shownThisVisit.has(storageKey))) openGuide();
  }, [storageKey, oncePerVisit]);

  function closeGuide() {
    suppressed.current = preferenceRef.current?.checked ?? false;
    try {
      if (suppressed.current) window.localStorage.setItem(storageKey, "1");
      else window.localStorage.removeItem(storageKey);
    } catch {
      // Dismissal remains available for this visit.
    }
    dialogRef.current?.close();
    triggerRef.current?.focus({ preventScroll: true });
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="dialog"
        aria-controls={id}
        onClick={openGuide}
        className="analysis-guide-trigger"
      >
        {triggerLabel}
      </button>
      {createPortal(
        <dialog
          ref={dialogRef}
          id={id}
          role="dialog"
          aria-labelledby={`${id}-title`}
          aria-describedby={`${id}-summary`}
          onCancel={(event) => {
            event.preventDefault();
            closeGuide();
          }}
          onPointerDown={(event) => {
            backdropPress.current = event.target === event.currentTarget;
          }}
          onClick={(event) => {
            if (backdropPress.current && event.target === event.currentTarget) closeGuide();
            backdropPress.current = false;
          }}
          className="analysis-guide"
        >
          <header className="analysis-guide__header">
            <p className="analysis-guide__eyebrow">CH2 Macro · {triggerLabel}</p>
            <h2 id={`${id}-title`}>{title}</h2>
            <button
              type="button"
              autoFocus
              aria-label={`${triggerLabel} 닫기`}
              onClick={closeGuide}
              className="analysis-guide__close"
            >
              ×
            </button>
          </header>
          <div
            ref={bodyRef}
            role="region"
            aria-label={`${triggerLabel} 본문`}
            tabIndex={0}
            className="analysis-guide__body"
          >
            {children}
          </div>
          <footer className="analysis-guide__footer">
            <label className="analysis-guide__preference">
              <input ref={preferenceRef} type="checkbox" />
              다음부터 보지 않기
            </label>
            <button type="button" onClick={closeGuide} className="analysis-guide__primary">
              {actionLabel}
            </button>
          </footer>
        </dialog>,
        document.body,
      )}
    </>
  );
}
