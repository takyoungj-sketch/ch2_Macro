// @ts-nocheck — shared: 각 frontend node_modules 기준 경로가 달라짐
import { useState, type ReactNode } from "react";

export type ModelRecommendDepth = "standard" | "standard_plus" | "extended";

export type ModelRecommendRow = {
  key: string;
  primary: string;
  metrics: string;
};

export type ModelRecommendPurposeTab = {
  id: string;
  label: string;
  /** 화면 한 문장: 이 탭이 무엇을 최적화했는지 */
  optimizeSentence: string;
  rows: ModelRecommendRow[];
  emptyText?: string;
};

const DEPTH_META: Record<
  ModelRecommendDepth,
  { badge: string; title: string }
> = {
  standard: {
    badge: "깊이: 표준",
    title: "AIC/MAPE 후보 (Twin Validation 없음)",
  },
  standard_plus: {
    badge: "깊이: 표준+",
    title: "Adj R²·CV-MAPE 후보 (Twin Validation 없음)",
  },
  extended: {
    badge: "깊이: 확장",
    title: "Stage1 + Twin Validation",
  },
};

export type ModelRecommendSectionProps = {
  depth: ModelRecommendDepth;
  selectionN?: number | null;
  limitations: string;
  tabs: ModelRecommendPurposeTab[];
  defaultTabId?: string;
  headerExtra?: ReactNode;
  className?: string;
};

/**
 * 토지·집합·복합이 공유하는 「모형 추천」 골격.
 * 목적 탭 · 최적화 한 문장 · 후보 · 한계 — 깊이만 도메인별로 다름.
 */
export default function ModelRecommendSection({
  depth,
  selectionN,
  limitations,
  tabs,
  defaultTabId,
  headerExtra,
  className = "",
}: ModelRecommendSectionProps) {
  const initial =
    defaultTabId && tabs.some((t) => t.id === defaultTabId)
      ? defaultTabId
      : tabs[0]?.id ?? "";
  const [tabId, setTabId] = useState(initial);
  const active = tabs.find((t) => t.id === tabId) ?? tabs[0];
  const meta = DEPTH_META[depth];

  if (!tabs.length) return null;

  return (
    <div
      className={`rounded-lg border border-indigo-200 bg-indigo-50/40 p-3 space-y-2 text-xs dark:border-indigo-800 dark:bg-indigo-950/20 ${className}`}
    >
      <div className="flex flex-wrap items-center gap-2 font-semibold text-indigo-900 dark:text-indigo-100">
        <span>모형 추천</span>
        <span
          className="rounded border border-slate-300 bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-600 dark:border-slate-600 dark:bg-slate-900/60 dark:text-slate-300"
          title={meta.title}
        >
          {meta.badge}
        </span>
        {selectionN != null && (
          <span className="font-normal text-indigo-800/80 dark:text-indigo-200/80">
            · 공통 표본 n={selectionN.toLocaleString("ko-KR")}
          </span>
        )}
        {headerExtra}
      </div>

      <div className="flex flex-wrap gap-1">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={
              t.id === active?.id
                ? "rounded border border-indigo-500 bg-indigo-600 px-2 py-0.5 text-[11px] font-medium text-white"
                : "rounded border border-indigo-200 bg-white px-2 py-0.5 text-[11px] text-indigo-800 dark:border-indigo-700 dark:bg-slate-900/50 dark:text-indigo-200"
            }
            onClick={() => setTabId(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {active && (
        <>
          <p className="text-[11px] text-slate-600 dark:text-slate-400">
            {active.optimizeSentence}
          </p>
          <div className="space-y-1">
            {active.rows.length === 0 ? (
              <p className="text-[11px] text-slate-500">
                {active.emptyText ?? "후보 없음"}
              </p>
            ) : (
              active.rows.map((row) => (
                <div
                  key={row.key}
                  className="rounded border border-indigo-100 bg-white px-2 py-1 dark:border-indigo-900/60 dark:bg-slate-900/60"
                >
                  <div className="text-slate-800 dark:text-slate-100">{row.primary}</div>
                  <div className="text-[11px] text-slate-500 tabular-nums">{row.metrics}</div>
                </div>
              ))
            )}
          </div>
        </>
      )}

      <p className="text-[10px] leading-relaxed text-slate-500 dark:text-slate-400 border-t border-indigo-100/80 dark:border-indigo-900/50 pt-1.5">
        한계: {limitations}
      </p>
    </div>
  );
}
