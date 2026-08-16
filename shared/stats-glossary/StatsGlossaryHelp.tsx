// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { getGlossaryEntry, type StatsGlossaryEntry } from "./statsGlossary";
import "./glossaryHelp.css";

const FONT_PX_MIN = 11;
const FONT_PX_MAX = 18;
const FONT_PX_DEFAULT = 13;
const FONT_STORAGE_KEY = "ch2-glossary-font-px";

function readStoredFontPx(): number {
  try {
    const n = Number(localStorage.getItem(FONT_STORAGE_KEY));
    if (Number.isFinite(n) && n >= FONT_PX_MIN && n <= FONT_PX_MAX) return n;
  } catch {
    /* ignore */
  }
  return FONT_PX_DEFAULT;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-0.5">
      <h4 className="font-semibold text-slate-800 dark:text-white" style={{ fontSize: "1.05em" }}>
        {title}
      </h4>
      <div className="text-slate-600 dark:text-slate-200 leading-snug">{children}</div>
    </section>
  );
}

function BulletList({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <ul className="list-disc list-outside ml-3.5 space-y-0.5">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function GlossaryBody({ entry }: { entry: StatsGlossaryEntry }) {
  const hasThresholds = (entry.thresholds?.length ?? 0) > 0;
  return (
    <div className={`gap-3 ${hasThresholds ? "grid sm:grid-cols-2" : "space-y-2.5"}`}>
      <div className="space-y-2.5">
        <Section title="정의">
          <p>{entry.definition}</p>
        </Section>
        {entry.formula && (
          <Section title="공식">
            <p className="font-mono bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-indigo-400/50 rounded px-2 py-1 whitespace-normal break-words dark:text-indigo-100" style={{ fontSize: "0.92em" }}>
              {entry.formula}
            </p>
          </Section>
        )}
        <Section title="해석">
          <BulletList items={entry.interpretation} />
        </Section>
      </div>
      {(hasThresholds || entry.limitations.length > 0) && (
        <div className="space-y-2.5">
          {hasThresholds && (
            <Section title="참고 기준">
              <BulletList items={entry.thresholds!} />
            </Section>
          )}
          <Section title="한계·주의">
            <BulletList items={entry.limitations} />
          </Section>
        </div>
      )}
    </div>
  );
}

function usePopoverPosition(open: boolean, anchorRef: React.RefObject<HTMLElement | null>) {
  const [style, setStyle] = useState<{ top: number; left: number } | null>(null);

  const update = useCallback(() => {
    const el = anchorRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const popW = Math.min(360, window.innerWidth - 16);
    const popH = 320;
    let left = rect.left + rect.width / 2 - popW / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - popW - 8));
    let top = rect.bottom + 6;
    if (top + popH > window.innerHeight - 8) {
      top = Math.max(8, rect.top - popH - 6);
    }
    setStyle({ top, left });
  }, [anchorRef]);

  useEffect(() => {
    if (!open) {
      setStyle(null);
      return;
    }
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [open, update]);

  return style;
}

export default function StatsGlossaryHelp({
  termId,
  className,
  size = "sm",
}: {
  termId: string;
  className?: string;
  size?: "sm" | "xs";
}) {
  const entry = getGlossaryEntry(termId);
  const [open, setOpen] = useState(false);
  const [fontPx, setFontPx] = useState(FONT_PX_DEFAULT);
  const anchorRef = useRef<HTMLButtonElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const pos = usePopoverPosition(open, anchorRef);

  useEffect(() => {
    setFontPx(readStoredFontPx());
  }, []);

  const bumpFont = (delta: number) => {
    setFontPx((prev) => {
      const next = Math.min(FONT_PX_MAX, Math.max(FONT_PX_MIN, prev + delta));
      try {
        localStorage.setItem(FONT_STORAGE_KEY, String(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onClick = (e: MouseEvent) => {
      const t = e.target as Node;
      if (anchorRef.current?.contains(t) || popupRef.current?.contains(t)) return;
      setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    const t = window.setTimeout(() => {
      document.addEventListener("mousedown", onClick);
    }, 0);
    return () => {
      window.clearTimeout(t);
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  if (!entry) return null;

  const popup =
    open && pos
      ? createPortal(
          <div
            ref={popupRef}
            role="dialog"
            aria-label={`${entry.label} 설명`}
            className="ch2-glossary-popup fixed rounded-lg border border-indigo-200 dark:border-indigo-300 bg-white dark:bg-slate-800 shadow-xl dark:shadow-black/70 ring-1 ring-black/5 dark:ring-indigo-300/60 p-3 text-left font-normal"
            style={{ position: "fixed", top: pos.top, left: pos.left, zIndex: 10000 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="ch2-glossary-popup-chrome flex items-start justify-between gap-2 mb-2">
              <div className="min-w-0">
                <p className="font-semibold text-slate-800 dark:text-white" style={{ fontSize: 14 }}>
                  {entry.title}
                </p>
                <p className="text-slate-500 dark:text-slate-300 mt-0.5" style={{ fontSize: 11 }}>
                  {entry.label}
                </p>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  className="ch2-glossary-font-btn"
                  aria-label="글자 작게"
                  disabled={fontPx <= FONT_PX_MIN}
                  onClick={() => bumpFont(-1)}
                >
                  −
                </button>
                <span className="tabular-nums text-slate-500 dark:text-slate-300 w-5 text-center" style={{ fontSize: 11 }}>
                  {fontPx}
                </span>
                <button
                  type="button"
                  className="ch2-glossary-font-btn"
                  aria-label="글자 크게"
                  disabled={fontPx >= FONT_PX_MAX}
                  onClick={() => bumpFont(1)}
                >
                  +
                </button>
                <button
                  type="button"
                  className="text-slate-400 hover:text-slate-600 dark:text-slate-300 dark:hover:text-white ml-0.5"
                  style={{ fontSize: 11 }}
                  onClick={() => setOpen(false)}
                >
                  닫기
                </button>
              </div>
            </div>
            <div className="ch2-glossary-popup-body" style={{ fontSize: fontPx }}>
              <GlossaryBody entry={entry} />
              <p className="text-slate-400 dark:text-slate-300 pt-2 mt-2 border-t border-slate-100 dark:border-slate-500" style={{ fontSize: "0.8em" }}>
                이번 결과 해석은 AI 어시스턴트에 질문하세요.
              </p>
            </div>
          </div>,
          document.body,
        )
      : null;

  return (
    <>
      <span className={`ch2-glossary-help ch2-glossary-help--${size}${className ? ` ${className}` : ""}`}>
        <button
          ref={anchorRef}
          type="button"
          title={`${entry.label} 설명`}
          aria-expanded={open}
          aria-label={`${entry.label} 용어 설명`}
          className={
            open
              ? "ch2-glossary-help-btn border-indigo-400 bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-200 dark:border-indigo-500"
              : "ch2-glossary-help-btn border-slate-400 bg-white text-slate-600 hover:border-indigo-300 hover:text-indigo-600 dark:border-slate-300 dark:bg-slate-700 dark:text-slate-100 dark:hover:border-indigo-300 dark:hover:text-white"
          }
          onClick={(e) => {
            e.stopPropagation();
            setOpen((v) => !v);
          }}
        >
          ?
        </button>
      </span>
      {popup}
    </>
  );
}

export function MetricWithHelp({
  label,
  termId,
  value,
  title,
}: {
  label: string;
  termId: string;
  value: ReactNode;
  title?: string;
}) {
  return (
    <div className="flex items-center gap-1 min-w-0" title={title}>
      <span className="truncate">
        {label} {value}
      </span>
      <StatsGlossaryHelp termId={termId} size="xs" />
    </div>
  );
}
