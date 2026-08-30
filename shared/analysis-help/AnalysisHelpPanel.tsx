// @ts-nocheck — shared: 각 frontend node_modules 기준 경로가 달라짐
import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import clsx from "clsx";
import type { AnalysisExplain } from "./types";
import {
  boxesEqual,
  clampBox,
  persistSize,
  readStoredSize,
  ResizeHandles,
  usePanelDrag,
  type PanelBox,
} from "../ui-window/resizableWindow";

const BACKDROP_Z = 149;
const PANEL_Z = 150;
const PANEL_DEFAULT_W = 420;
const PANEL_DEFAULT_H = 520;
const MIN_W = 280;
const MIN_H = 240;
const VIEWPORT_PAD = 12;
const SIZE_STORAGE_KEY = "ch2-analysis-help-win-size";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-1">
      <h4 className="text-[11px] font-semibold text-slate-700 dark:text-slate-200">{title}</h4>
      <div className="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed">{children}</div>
    </section>
  );
}

function BulletList({ items }: { items: string[] }) {
  if (!items?.length) return null;
  return (
    <ul className="list-disc list-inside space-y-0.5">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function computeAnchorPlacement(anchor: HTMLElement, w: number, h: number): PanelBox {
  const rect = anchor.getBoundingClientRect();
  let left = rect.right - w;
  left = Math.max(VIEWPORT_PAD, Math.min(left, window.innerWidth - w - VIEWPORT_PAD));

  let top = rect.bottom + 6;
  if (top + h > window.innerHeight - VIEWPORT_PAD) {
    const above = rect.top - h - 6;
    top = above >= VIEWPORT_PAD ? above : VIEWPORT_PAD;
  }

  return clampBox({ x: left, y: top, w, h }, MIN_W, MIN_H);
}

function defaultHelpSize(): { w: number; h: number } {
  const stored = readStoredSize(SIZE_STORAGE_KEY);
  const vw = typeof window !== "undefined" ? window.innerWidth : 1200;
  const vh = typeof window !== "undefined" ? window.innerHeight : 800;
  return {
    w: stored?.w ?? Math.min(PANEL_DEFAULT_W, vw - VIEWPORT_PAD * 2),
    h: stored?.h ?? Math.min(PANEL_DEFAULT_H, vh * 0.62),
  };
}

export default function AnalysisHelpPanel({
  explain,
  className,
  title = "분석 방법·해석·한계 설명",
  buttonLabel = "?",
}: {
  explain: AnalysisExplain | null | undefined;
  className?: string;
  title?: string;
  buttonLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [box, setBox] = useState<PanelBox | null>(null);
  const userPlacedRef = useRef(false);
  const anchorRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const { beginMove, beginResize } = usePanelDrag(open, MIN_W, MIN_H, (next) => {
    userPlacedRef.current = true;
    setBox(next);
    persistSize(SIZE_STORAGE_KEY, next);
  });

  useLayoutEffect(() => {
    if (!open) {
      setBox(null);
      userPlacedRef.current = false;
      return;
    }
    const onViewport = () => {
      if (userPlacedRef.current) {
        setBox((prev) => {
          if (!prev) return prev;
          const next = clampBox(prev, MIN_W, MIN_H);
          return boxesEqual(prev, next) ? prev : next;
        });
        return;
      }
      if (!anchorRef.current) return;
      const size = defaultHelpSize();
      setBox(computeAnchorPlacement(anchorRef.current, size.w, size.h));
    };
    onViewport();
    window.addEventListener("resize", onViewport);
    window.addEventListener("scroll", onViewport, true);
    return () => {
      window.removeEventListener("resize", onViewport);
      window.removeEventListener("scroll", onViewport, true);
    };
  }, [open]);

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

  const presets = explain.presets ?? [];
  const hints = explain.interpretation_hints ?? [];

  const panel =
    open && box ? (
      <>
        <div className="fixed inset-0 bg-slate-900/40 dark:bg-black/50" style={{ zIndex: BACKDROP_Z }} aria-hidden />
        <div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-label={explain.title}
          className="flex flex-col overflow-hidden rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 shadow-2xl ring-1 ring-black/5 dark:ring-white/10"
          style={{
            position: "fixed",
            zIndex: PANEL_Z,
            top: box.y,
            left: box.x,
            width: box.w,
            height: box.h,
          }}
        >
          <div
            className="flex items-start justify-between gap-2 shrink-0 px-4 pt-4 pb-2 cursor-grab active:cursor-grabbing select-none"
            onPointerDown={(e) => {
              const t = e.target as HTMLElement;
              if (t.closest("button, a, input, textarea, select")) return;
              beginMove(e, box);
            }}
          >
            <div className="min-w-0">
              <p className="text-xs font-semibold text-slate-800 dark:text-slate-100">{explain.title}</p>
              <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">
                spec: {explain.spec_id} · v{explain.spec_version}
                <span className="ml-1.5">· 드래그로 이동 · 모서리로 크기 조절</span>
              </p>
            </div>
            <button
              type="button"
              className="text-[10px] text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 shrink-0"
              onClick={() => setOpen(false)}
            >
              닫기
            </button>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto px-4 pb-4 space-y-3">
            <Section title="요약">
              <p>{explain.summary}</p>
            </Section>

            {explain.formula && (
              <Section title="공식">
                <p className="font-mono text-[10px] bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-600 rounded px-2 py-1.5 whitespace-pre-wrap">
                  {explain.formula}
                </p>
                {explain.index_rule && (
                  <p className="mt-1 text-[10px] text-slate-500 dark:text-slate-400">지수: {explain.index_rule}</p>
                )}
                {explain.reference && (
                  <p className="mt-0.5 text-[10px] text-slate-500 dark:text-slate-400">기준: {explain.reference}</p>
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

            {hints.length > 0 && (
              <Section title="이번 결과 기준">
                <ul className="space-y-1">
                  {hints.map((hint) => (
                    <li
                      key={hint}
                      className={clsx(
                        "text-[11px] pl-2 border-l-2",
                        hint.startsWith("⚠")
                          ? "border-amber-400 text-amber-900 dark:text-amber-200"
                          : "border-indigo-300 text-slate-700 dark:text-slate-200",
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

            {presets.length > 0 && (
              <Section title="자주 묻는 질문">
                <div className="space-y-1">
                  {presets.map((p) => (
                    <div
                      key={p.id}
                      className="rounded border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700/50 overflow-hidden"
                    >
                      <button
                        type="button"
                        className="w-full text-left px-2 py-1.5 text-[11px] font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700"
                        onClick={() => setActivePreset(activePreset === p.id ? null : p.id)}
                      >
                        {p.question}
                      </button>
                      {activePreset === p.id && (
                        <p className="px-2 pb-2 text-[11px] text-slate-600 dark:text-slate-300 border-t border-slate-100 dark:border-slate-600">
                          {p.answer || "화면 Facts·지표를 함께 확인해 주세요."}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </Section>
            )}
          </div>
          <ResizeHandles onPointerDown={(edge, e) => beginResize(edge, e, box)} />
        </div>
      </>
    ) : null;

  return (
    <>
      <button
        ref={anchorRef}
        type="button"
        title={title}
        aria-expanded={open}
        aria-label={title}
        className={clsx(
          "inline-flex items-center justify-center rounded-full border font-bold transition-colors shrink-0",
          buttonLabel === "?"
            ? "h-6 w-6 text-[11px]"
            : "h-6 px-2 w-auto text-[10px] tracking-tight",
          open
            ? "border-indigo-300 bg-indigo-50 text-indigo-700 dark:border-indigo-500 dark:bg-indigo-950/50 dark:text-indigo-200"
            : "border-slate-200 bg-white text-slate-500 hover:border-indigo-200 hover:text-indigo-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-indigo-400 dark:hover:text-indigo-300",
          className,
        )}
        onClick={() => {
          setActivePreset(null);
          setOpen((v) => !v);
        }}
      >
        {buttonLabel}
      </button>
      {panel ? createPortal(panel, document.body) : null}
    </>
  );
}
