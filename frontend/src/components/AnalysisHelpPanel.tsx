import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import clsx from "clsx";
import type { AnalysisExplain } from "../types";

const BACKDROP_Z = 149;
const PANEL_Z = 150;
const PANEL_MAX_W = 420;
const VIEWPORT_PAD = 12;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-1">
      <h4 className="text-[11px] font-semibold text-slate-700">{title}</h4>
      <div className="text-[11px] text-slate-600 leading-relaxed">{children}</div>
    </section>
  );
}

function BulletList({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <ul className="list-disc list-inside space-y-0.5">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

type PanelCoords = {
  top: number;
  left: number;
  width: number;
  maxHeight: number;
};

function computePanelCoords(anchor: HTMLElement): PanelCoords {
  const rect = anchor.getBoundingClientRect();
  const width = Math.min(PANEL_MAX_W, window.innerWidth - VIEWPORT_PAD * 2);
  const maxHeight = Math.min(420, window.innerHeight * 0.55);

  let left = rect.right - width;
  left = Math.max(VIEWPORT_PAD, Math.min(left, window.innerWidth - width - VIEWPORT_PAD));

  let top = rect.bottom + 6;
  if (top + maxHeight > window.innerHeight - VIEWPORT_PAD) {
    const above = rect.top - maxHeight - 6;
    top = above >= VIEWPORT_PAD ? above : VIEWPORT_PAD;
  }

  return { top, left, width, maxHeight };
}

export default function AnalysisHelpPanel({
  explain,
  className,
}: {
  explain: AnalysisExplain | null | undefined;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [coords, setCoords] = useState<PanelCoords | null>(null);
  const anchorRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const updateCoords = useCallback(() => {
    if (!anchorRef.current) return;
    setCoords(computePanelCoords(anchorRef.current));
  }, []);

  useLayoutEffect(() => {
    if (!open) {
      setCoords(null);
      return;
    }
    updateCoords();
    window.addEventListener("resize", updateCoords);
    window.addEventListener("scroll", updateCoords, true);
    return () => {
      window.removeEventListener("resize", updateCoords);
      window.removeEventListener("scroll", updateCoords, true);
    };
  }, [open, updateCoords]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      const t = e.target as Node;
      if (anchorRef.current?.contains(t) || panelRef.current?.contains(t)) return;
      setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown, true);
    return () => document.removeEventListener("pointerdown", onPointerDown, true);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!explain) return null;

  const panel =
    open && coords ? (
      <>
        <div
          className="fixed inset-0 bg-slate-900/40"
          style={{ zIndex: BACKDROP_Z }}
          aria-hidden
        />
        <div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-label={explain.title}
          className="rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 shadow-2xl ring-1 ring-black/5 dark:ring-white/10 p-4 space-y-3 overflow-y-auto"
          style={{
            position: "fixed",
            zIndex: PANEL_Z,
            top: coords.top,
            left: coords.left,
            width: coords.width,
            maxHeight: coords.maxHeight,
          }}
        >
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-xs font-semibold text-slate-800">{explain.title}</p>
            <p className="text-[10px] text-slate-500 mt-0.5">
              spec: {explain.spec_id} · v{explain.spec_version}
            </p>
          </div>
          <button
            type="button"
            className="text-[10px] text-slate-400 hover:text-slate-600 shrink-0"
            onClick={() => setOpen(false)}
          >
            닫기
          </button>
        </div>

        <Section title="요약">
          <p>{explain.summary}</p>
        </Section>

        {explain.formula && (
          <Section title="공식">
            <p className="font-mono text-[10px] bg-slate-50 border border-slate-200 rounded px-2 py-1.5 whitespace-pre-wrap">
              {explain.formula}
            </p>
            {explain.index_rule && (
              <p className="mt-1 text-[10px] text-slate-500">지수: {explain.index_rule}</p>
            )}
            {explain.reference && (
              <p className="mt-0.5 text-[10px] text-slate-500">기준: {explain.reference}</p>
            )}
          </Section>
        )}

        {explain.floor_groups && explain.floor_groups.length > 0 && (
          <Section title="집계 단위">
            <BulletList items={explain.floor_groups} />
          </Section>
        )}

        {explain.controls && explain.controls.length > 0 && (
          <Section title="포함·제외 조건">
            <BulletList items={explain.controls} />
          </Section>
        )}

        <Section title="해석 방법">
          <BulletList items={explain.interpretation} />
        </Section>

        {explain.interpretation_hints && explain.interpretation_hints.length > 0 && (
          <Section title="이번 결과 기준">
            <ul className="space-y-1">
              {explain.interpretation_hints.map((hint) => (
                <li
                  key={hint}
                  className={clsx(
                    "text-[11px] pl-2 border-l-2",
                    hint.startsWith("⚠")
                      ? "border-amber-400 text-amber-900"
                      : "border-indigo-300 text-slate-700",
                  )}
                >
                  {hint}
                </li>
              ))}
            </ul>
          </Section>
        )}

        <Section title="한계·주의">
          <BulletList items={explain.limitations} />
        </Section>

        {explain.presets && explain.presets.length > 0 && (
          <Section title="자주 묻는 질문">
            <div className="space-y-1">
              {explain.presets.map((p) => (
                <div
                  key={p.id}
                  className="rounded border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 overflow-hidden"
                >
                  <button
                    type="button"
                    className="w-full text-left px-2 py-1.5 text-[11px] font-medium text-slate-700 hover:bg-slate-50"
                    onClick={() => setActivePreset(activePreset === p.id ? null : p.id)}
                  >
                    {p.question}
                  </button>
                  {activePreset === p.id && (
                    <p className="px-2 pb-2 text-[11px] text-slate-600 border-t border-slate-50">
                      {p.answer}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </Section>
        )}
        </div>
      </>
    ) : null;

  return (
    <>
      <button
        ref={anchorRef}
        type="button"
        title="분석 방법·해석·한계 설명"
        aria-expanded={open}
        aria-label="분석 설명 열기"
        className={clsx(
          "inline-flex h-6 w-6 items-center justify-center rounded-full border text-[11px] font-bold transition-colors shrink-0",
          open
            ? "border-indigo-300 bg-indigo-50 text-indigo-700"
            : "border-slate-200 bg-white text-slate-500 hover:border-indigo-200 hover:text-indigo-600",
          className,
        )}
        onClick={() => {
          setActivePreset(null);
          setOpen((v) => !v);
        }}
      >
        ?
      </button>
      {panel ? createPortal(panel, document.body) : null}
    </>
  );
}
