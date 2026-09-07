import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

export type HelpSection = {
  paras: string[];
  bullets?: string[];
};

export type ExpHelpDoc = {
  title: string;
  blurb?: string;
  method: HelpSection;
  limits: HelpSection;
  meaning: HelpSection;
};

function HelpBody({ title, section }: { title: string; section: HelpSection }) {
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">{title}</h3>
      {section.paras.map((p, i) => (
        <p key={i} className="text-[13px] leading-relaxed text-slate-600 dark:text-slate-300">
          {p}
        </p>
      ))}
      {section.bullets && section.bullets.length > 0 && (
        <ul className="list-disc list-outside ml-4 space-y-1.5 text-[13px] leading-relaxed text-slate-600 dark:text-slate-300">
          {section.bullets.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function ExpHelp({ doc, size = "sm" }: { doc: ExpHelpDoc; size?: "sm" | "xs" }) {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const dim = size === "xs" ? "h-5 w-5 text-[11px]" : "h-6 w-6 text-[13px]";

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panelRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        className={`ml-1 inline-flex ${dim} shrink-0 items-center justify-center rounded-full border border-slate-400 bg-white font-bold leading-none text-slate-600 hover:border-amber-500 hover:text-amber-800 dark:border-slate-500 dark:bg-slate-800 dark:text-slate-200 dark:hover:border-amber-400 dark:hover:text-amber-200`}
        aria-expanded={open}
        aria-label={`${doc.title} 설명`}
        title={`${doc.title} 설명`}
        onClick={(e) => {
          e.stopPropagation();
          setOpen(true);
        }}
      >
        ?
      </button>
      {open &&
        createPortal(
          <div className="fixed inset-0 z-[10000] flex items-start justify-center px-3 py-8 sm:py-12">
            <button
              type="button"
              className="absolute inset-0 bg-slate-900/40"
              aria-label="설명 닫기"
              onClick={() => setOpen(false)}
            />
            <div
              ref={panelRef}
              role="dialog"
              aria-modal="true"
              aria-labelledby={titleId}
              tabIndex={-1}
              className="relative z-10 flex max-h-[min(40rem,calc(100vh-4rem))] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl outline-none dark:border-slate-600 dark:bg-slate-900"
            >
              <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-3 dark:border-slate-700">
                <div className="min-w-0">
                  <p id={titleId} className="text-base font-semibold text-slate-900 dark:text-slate-50">
                    {doc.title}
                  </p>
                  {doc.blurb && (
                    <p className="mt-1 text-[12px] leading-relaxed text-slate-500 dark:text-slate-400">{doc.blurb}</p>
                  )}
                </div>
                <button
                  type="button"
                  className="shrink-0 rounded-md px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
                  onClick={() => setOpen(false)}
                >
                  닫기
                </button>
              </div>
              <div className="space-y-5 overflow-y-auto px-5 py-4">
                <HelpBody title="실험 방법" section={doc.method} />
                <HelpBody title="한계" section={doc.limits} />
                <HelpBody title="의미" section={doc.meaning} />
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
