// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import clsx from "clsx";
import { getGlossaryEntry, type StatsGlossaryEntry } from "./statsGlossary";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-0.5">
      <h4 className="text-[11px] font-semibold text-slate-800 dark:text-white">{title}</h4>
      <div className="text-[11px] text-slate-600 dark:text-slate-200 leading-snug">{children}</div>
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
    <div className={clsx("gap-3", hasThresholds ? "grid sm:grid-cols-2" : "space-y-2.5")}>
      <div className="space-y-2.5">
        <Section title="정의">
          <p>{entry.definition}</p>
        </Section>
        {entry.formula && (
          <Section title="공식">
            <p className="font-mono text-[10px] bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-indigo-400/50 rounded px-2 py-1 whitespace-normal break-words dark:text-indigo-100">
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
  const anchorRef = useRef<HTMLButtonElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const pos = usePopoverPosition(open, anchorRef);

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
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  if (!entry) return null;

  const btnClass =
    size === "xs"
      ? "inline-flex h-4 w-4 items-center justify-center rounded-full border text-[9px] font-bold"
      : "inline-flex h-5 w-5 items-center justify-center rounded-full border text-[10px] font-bold";

  const popup =
    open && pos
      ? createPortal(
          <div
            ref={popupRef}
            role="dialog"
            aria-label={`${entry.label} 설명`}
            className="fixed w-[min(22.5rem,calc(100vw-1rem))] min-w-[17rem] rounded-lg border border-indigo-200 dark:border-indigo-300 bg-white dark:bg-slate-800 shadow-xl dark:shadow-black/70 ring-1 ring-black/5 dark:ring-indigo-300/60 p-3 max-h-[min(340px,70vh)] overflow-y-auto text-left font-normal"
            style={{ top: pos.top, left: pos.left, zIndex: 10000 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <div className="min-w-0">
                <p className="text-xs font-semibold text-slate-800 dark:text-white">{entry.title}</p>
                <p className="text-[10px] text-slate-500 dark:text-slate-300 mt-0.5">{entry.label}</p>
              </div>
              <button
                type="button"
                className="text-[10px] text-slate-400 hover:text-slate-600 dark:text-slate-300 dark:hover:text-white shrink-0"
                onClick={() => setOpen(false)}
              >
                닫기
              </button>
            </div>
            <GlossaryBody entry={entry} />
            <p className="text-[9px] text-slate-400 dark:text-slate-300 pt-2 mt-2 border-t border-slate-100 dark:border-slate-500">
              이번 결과 해석은 AI 어시스턴트에 질문하세요.
            </p>
          </div>,
          document.body,
        )
      : null;

  return (
    <>
      <span className={clsx("inline-flex align-middle", className)}>
        <button
          ref={anchorRef}
          type="button"
          title={`${entry.label} 설명`}
          aria-expanded={open}
          aria-label={`${entry.label} 용어 설명`}
          className={clsx(
            btnClass,
            "transition-colors shrink-0",
            open
              ? "border-indigo-400 bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-200 dark:border-indigo-600"
              : "border-slate-200 bg-white text-slate-400 hover:border-indigo-200 hover:text-indigo-600 dark:border-slate-400 dark:bg-slate-700 dark:text-slate-200 dark:hover:border-indigo-300 dark:hover:text-white",
          )}
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
