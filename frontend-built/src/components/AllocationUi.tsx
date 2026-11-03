import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import type { BuiltTransactionRow } from "../types";
import { structureGroupLabel } from "../utils/builtTxDisplay";
import { ALLOCATION_DEFAULTS } from "../utils/allocationDefaults";
import { TRANSACTION_ALLOCATION_HELP, TRANSACTION_ALLOCATION_TABLE_HELP } from "../utils/builtTransactionHelp";
import {
  allocateRow,
  allocationTitle,
  bandKey,
  allocationAge,
  defaultBand,
  defaultBands,
  defaultRemainingYears,
  formatLandRange,
  formatMan,
  formatYearInput,
  referenceBand,
  residualRatio,
  type BandMap,
  type RowOverride,
} from "../utils/allocationCost";
import DraggableModalShell from "./DraggableModalShell";

const STRUCTURES = ["RC", "SRC", "철골", "벽돌", "목", "블록", "기타"] as const;

function usesInOrder(): string[] {
  const out: string[] = [];
  for (const row of ALLOCATION_DEFAULTS) {
    if (!out.includes(row.use)) out.push(row.use);
  }
  return out;
}

export function AllocationCells({
  row,
  bands,
  override,
  onOpen,
}: {
  row: BuiltTransactionRow;
  bands: BandMap;
  override?: RowOverride;
  onOpen: (id: number) => void;
}) {
  const outcome = allocateRow(row, bands, override);
  const tone = outcome.customized
    ? "text-amber-800 dark:text-amber-300 font-medium"
    : "text-slate-700 dark:text-slate-200";
  const open = () => onOpen(row.id);
  if (!outcome.ok) {
    return (
      <td colSpan={3} className="border px-2 py-1 whitespace-nowrap">
        <button type="button" onClick={open} className="text-slate-400 underline-offset-2 hover:underline" title="가정 입력">
          {outcome.reason}
        </button>
      </td>
    );
  }
  const { band, view } = outcome;
  const wide = !row.structure_group?.trim() && !outcome.customized;
  return (
    <>
      <td className={clsx("border px-2 py-1 text-right tabular-nums whitespace-nowrap", tone)}>
        <button
          type="button"
          onClick={open}
          title={wide ? "구조 없음. 이 용도의 구조별 하한·상한을 모은 범위. 만원/㎡" : "만원/㎡"}
        >
          {band.low}~{band.high}
        </button>
      </td>
      <td className={clsx("border px-2 py-1 text-right tabular-nums whitespace-nowrap", tone)}>
        <button type="button" onClick={open} title={wide ? "이 용도 구조들의 내용연수 중앙값" : undefined}>
          {band.life}년
        </button>
      </td>
      <td className={clsx("border px-2 py-1 text-right tabular-nums whitespace-nowrap", tone)}>
        <button type="button" onClick={open} title={allocationTitle(outcome)}>
          {formatLandRange(view)}
        </button>
      </td>
    </>
  );
}

function NumberField({
  label,
  value,
  onChange,
  onBlur,
  suffix,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onBlur?: (value: string) => void;
  suffix?: string;
  placeholder?: string;
}) {
  return (
    <label className="block text-[11px] text-slate-600 dark:text-slate-300">
      {label}
      <span className="mt-0.5 flex items-center gap-1">
        <input
          type="number"
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
          onBlur={(e) => onBlur?.(e.target.value)}
          className="w-full px-2 py-1 rounded border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 tabular-nums"
        />
        {suffix && <span className="shrink-0 text-slate-400">{suffix}</span>}
      </span>
    </label>
  );
}

export function AllocationDetailDialog({
  row,
  bands,
  override,
  onOverride,
  onClear,
  onClose,
}: {
  row: BuiltTransactionRow | null;
  bands: BandMap;
  override?: RowOverride;
  onOverride: (id: number, patch: RowOverride) => void;
  onClear: (id: number) => void;
  onClose: () => void;
}) {
  const outcome = row ? allocateRow(row, bands, override) : null;
  const overrideEmpty = !override || Object.keys(override).length === 0;
  const [draft, setDraft] = useState({ low: "", high: "", life: "", remain: "", min: "" });

  useEffect(() => {
    if (!row) return;
    const next = allocateRow(row, bands, overrideEmpty ? undefined : override);
    const partial = override ?? {};
    const band = next.ok ? next.band : null;
    setDraft({
      low: band ? String(band.low) : partial.low != null ? String(partial.low) : "",
      high: band ? String(band.high) : partial.high != null ? String(partial.high) : "",
      life: band ? String(band.life) : partial.life != null ? String(partial.life) : "",
      remain:
        partial.remainingYears != null
          ? formatYearInput(partial.remainingYears)
          : next.ok && next.view.remaining != null
            ? formatYearInput(next.view.remaining)
            : "",
      min: band
        ? String(Math.round(band.minResidual * 100))
        : partial.minResidual != null
          ? String(Math.round(partial.minResidual * 100))
          : "",
    });
    // 행을 바꾸거나 초기화할 때만 입력칸을 다시 채운다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [row?.id, overrideEmpty, bands]);

  const commit = (field: "low" | "high" | "life" | "minResidual", raw: string, asPercent = false) => {
    if (!row) return;
    const use = row.building_use?.trim() || "";
    const structure = row.structure_group?.trim() || "";
    const base = referenceBand(use, structure, bands) ?? undefined;
    if (raw.trim() === "") {
      onOverride(row.id, { [field]: undefined });
      return;
    }
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) return;
    const stored = asPercent ? parsed / 100 : parsed;
    const baseValue = base?.[field];
    if (baseValue != null && stored === baseValue) onOverride(row.id, { [field]: undefined });
    else onOverride(row.id, { [field]: stored });
  };

  const commitRemaining = (raw: string, lifeRaw = draft.life, minRaw = draft.min) => {
    if (!row) return;
    if (raw.trim() === "") {
      onOverride(row.id, { remainingYears: undefined });
      return;
    }
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) return;
    const life = Number(lifeRaw);
    const stored = life > 0 ? Math.min(life, Math.max(0, parsed)) : Math.max(0, parsed);
    const min = Number(minRaw);
    const age = allocationAge(row);
    const base =
      age && life > 0 && Number.isFinite(min) ? defaultRemainingYears(age.years, life, min / 100) : null;
    if (base != null && Math.abs(stored - base) < 0.05) onOverride(row.id, { remainingYears: undefined });
    else onOverride(row.id, { remainingYears: stored });
  };

  const syncRemainingDraft = (lifeRaw: string, minRaw: string) => {
    if (!row || override?.remainingYears != null) return null;
    const life = Number(lifeRaw);
    const min = Number(minRaw);
    const age = allocationAge(row);
    if (!age || !(life > 0) || !Number.isFinite(min)) return null;
    const ratio = residualRatio(age.years, life, min / 100);
    return ratio == null ? null : formatYearInput(ratio * life);
  };

  const useLabel = row?.building_use?.trim() || "용도 없음";
  const structureLabel = structureGroupLabel(row?.structure_group) || "구조 없음";

  return (
    <DraggableModalShell
      open={row != null}
      onClose={onClose}
      titleId="built-alloc-detail-title"
      title="배분 가정"
      subtitle={row ? `${useLabel} · ${structureLabel}` : undefined}
      zClassName="z-[130]"
      defaultWidth={420}
      defaultHeight={520}
      minWidth={320}
      minHeight={360}
      resizable
    >
      {row && outcome && (
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-2">
            <NumberField
              label="신축원가 하한"
              suffix="만원/㎡"
              value={draft.low}
              onChange={(value) => {
                setDraft((prev) => ({ ...prev, low: value }));
                commit("low", value);
              }}
            />
            <NumberField
              label="신축원가 상한"
              suffix="만원/㎡"
              value={draft.high}
              onChange={(value) => {
                setDraft((prev) => ({ ...prev, high: value }));
                commit("high", value);
              }}
            />
            <NumberField
              label="내용연수"
              suffix="년"
              value={draft.life}
              onChange={(value) => {
                const remain = syncRemainingDraft(value, draft.min);
                setDraft((prev) => ({ ...prev, life: value, ...(remain != null ? { remain } : {}) }));
                commit("life", value);
              }}
              onBlur={(value) => {
                const lifeNum = Number(value);
                const explicit = override?.remainingYears;
                if (explicit == null || !(lifeNum > 0) || explicit <= lifeNum) return;
                const capped = formatYearInput(lifeNum);
                setDraft((prev) => ({ ...prev, remain: capped }));
                commitRemaining(capped, value, draft.min);
              }}
            />
            <NumberField
              label="잔존연수"
              suffix="년"
              placeholder="입력"
              value={draft.remain}
              onChange={(value) => {
                const parsed = Number(value);
                const lifeNum = Number(draft.life);
                if (value.trim() !== "" && Number.isFinite(parsed) && lifeNum > 0 && parsed > lifeNum) {
                  const capped = formatYearInput(lifeNum);
                  setDraft((prev) => ({ ...prev, remain: capped }));
                  commitRemaining(capped);
                  return;
                }
                if (value.trim() !== "" && Number.isFinite(parsed) && parsed < 0) {
                  setDraft((prev) => ({ ...prev, remain: "0" }));
                  commitRemaining("0");
                  return;
                }
                setDraft((prev) => ({ ...prev, remain: value }));
                commitRemaining(value);
              }}
            />
            <NumberField
              label="최소잔가(%)"
              value={draft.min}
              onChange={(value) => {
                const remain = syncRemainingDraft(draft.life, value);
                setDraft((prev) => ({ ...prev, min: value, ...(remain != null ? { remain } : {}) }));
                commit("minResidual", value, true);
              }}
            />
          </div>
          {outcome.ok ? (
            <div className="text-[12px] leading-5 text-slate-600 dark:text-slate-300 space-y-1">
              <p>
                {outcome.view.remaining == null ? (
                  <>실거래 건축연도와 사용승인연도가 없어 최종잔가율 {Math.round(outcome.view.residual * 100)}%를 적용했습니다. 잔존연수를 넣으면 그 값으로 계산합니다.</>
                ) : (
                  <>
                    {outcome.view.elapsed != null && (
                      <>
                        경과 {Number.isInteger(outcome.view.elapsed) ? outcome.view.elapsed : outcome.view.elapsed.toFixed(1)}년
                        {outcome.view.ageSource ? ` (${outcome.view.ageSource})` : ""} ·{" "}
                      </>
                    )}
                    잔존 {formatYearInput(outcome.view.remaining)}년 · 잔가 {Math.round(outcome.view.residual * 100)}%
                  </>
                )}
              </p>
              {override?.remainingYears != null && (
                <p>잔존연수를 직접 넣었으므로 최소잔가율은 적용하지 않습니다. 잔존연수는 내용연수를 넘기지 않습니다.</p>
              )}
              <p>
                토지 배분단가 {formatLandRange(outcome.view)}
                {outcome.view.landMid != null && ` · 기준 ${formatMan(outcome.view.landMid)}`}
                <span className="text-slate-400"> 만원/㎡</span>
              </p>
              {!row.structure_group?.trim() && !outcome.customized && (
                <p>구조가 없어 이 용도의 구조별 하한·상한을 모은 범위입니다. 내용연수는 그 구조들의 중앙값입니다.</p>
              )}
              {outcome.view.unfitAll && (
                <p>낮은 신축원가에서도 토지단가가 0 이하입니다. 음수는 추정 건물가가 거래금액보다 큰 만큼입니다.</p>
              )}
              {!outcome.view.unfitAll && outcome.view.landLow != null && outcome.view.landLow <= 0 && (
                <p>높은 신축원가에서는 토지단가가 0 이하입니다.</p>
              )}
            </div>
          ) : (
            <p className="text-[12px] text-slate-500">{outcome.reason}</p>
          )}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => onClear(row.id)}
              className="px-2.5 py-1 rounded border border-slate-200 dark:border-slate-600 text-[12px] text-slate-700 dark:text-slate-200"
            >
              이 행 초기화
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-2.5 py-1 rounded bg-blue-600 text-white text-[12px]"
            >
              닫기
            </button>
          </div>
        </div>
      )}
    </DraggableModalShell>
  );
}

function bandInputClass(changed: boolean, width: string) {
  return clsx(
    width,
    "px-1 py-0.5 text-right rounded border tabular-nums",
    changed
      ? "border-amber-500 bg-amber-50 text-amber-950 dark:border-amber-400 dark:bg-amber-950/40 dark:text-amber-100"
      : "border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100",
  );
}

export function AllocationReferenceDialog({
  open,
  bands,
  items,
  onConfirm,
  onClose,
}: {
  open: boolean;
  bands: BandMap;
  items: BuiltTransactionRow[];
  onConfirm: (bands: BandMap, showAllocation: boolean) => void;
  onClose: () => void;
}) {
  const uses = useMemo(usesInOrder, []);
  const presentUses = useMemo(() => {
    const known = new Set(uses);
    const found = new Set<string>();
    for (const row of items) {
      const use = row.building_use?.trim();
      if (use && known.has(use)) found.add(use);
    }
    return found;
  }, [items, uses]);
  const presentKey = useMemo(() => [...presentUses].sort().join("\n"), [presentUses]);
  const [draftBands, setDraftBands] = useState<BandMap>(bands);
  const [showAllocation, setShowAllocation] = useState(true);
  const [useScope, setUseScope] = useState<"current" | "all">("current");

  useEffect(() => {
    if (!open) return;
    setDraftBands(bands);
    setShowAllocation(true);
    setUseScope(presentUses.size > 0 ? "current" : "all");
  }, [open, bands, presentKey, presentUses.size]);

  const visibleUses = useMemo(() => {
    const ordered = [...uses].sort((a, b) => {
      const rank = (use: string) => (presentUses.has(use) ? 0 : 1);
      const byPresence = rank(a) - rank(b);
      if (byPresence !== 0) return byPresence;
      return uses.indexOf(a) - uses.indexOf(b);
    });
    if (useScope === "current") return ordered.filter((use) => presentUses.has(use));
    return ordered;
  }, [presentUses, useScope, uses]);

  const onPatch = (key: string, patch: Partial<BandMap[string]>) => {
    setDraftBands((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }));
  };

  const onReset = (use: string, structure: string) => {
    const fresh = defaultBand(use, structure);
    if (fresh) onPatch(bandKey(use, structure), fresh);
  };

  return (
    <DraggableModalShell
      open={open}
      onClose={onClose}
      titleId="built-alloc-ref-title"
      title="간이 토지 배분단가"
      zClassName="z-[120]"
      maxWidthClass="max-w-5xl"
      defaultWidth={960}
      defaultHeight={860}
      minWidth={680}
      minHeight={520}
      resizable
      bodyClassName="flex-1 min-h-0 overflow-hidden px-4 py-3 flex flex-col"
    >
      <div className="h-full min-h-0 flex flex-col gap-3">
        <div className="shrink-0 space-y-2 text-[12px] leading-5 text-slate-700 dark:text-slate-200">
          <p>{TRANSACTION_ALLOCATION_HELP.summary}</p>
          <div className="rounded bg-slate-50 dark:bg-slate-800 px-3 py-2 space-y-0.5">
            <p>토지 배분단가 = (거래가격 − 추정 건물가액) ÷ 대지면적</p>
            <p>추정 건물가액 = 연면적 × 재조달원가 × 잔가율</p>
          </div>
          <section className="space-y-1">
            <h3 className="font-semibold text-slate-800 dark:text-slate-100">사용방법</h3>
            <p>{TRANSACTION_ALLOCATION_HELP.interpretation?.[0]}</p>
          </section>
          <details className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100">
            <summary className="cursor-pointer font-semibold">계산 시 유의사항</summary>
            <div className="mt-1 space-y-1">
              {TRANSACTION_ALLOCATION_HELP.limitations?.map((text) => <p key={text}>{text}</p>)}
            </div>
          </details>
        </div>
        <section className="flex-1 min-h-0 flex flex-col gap-2">
          <div className="shrink-0 flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="text-[13px] font-semibold text-slate-800 dark:text-slate-100">간이 신축원가표</h3>
              <p className="text-[12px] leading-5 text-slate-600 dark:text-slate-300">{TRANSACTION_ALLOCATION_TABLE_HELP.summary}</p>
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              <div className="inline-flex rounded-md border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-800 p-0.5" role="tablist" aria-label="원가표 용도 범위">
                <button
                  type="button"
                  role="tab"
                  aria-selected={useScope === "current"}
                  disabled={presentUses.size === 0}
                  onClick={() => setUseScope("current")}
                  className={clsx(
                    "px-2 py-0.5 text-[11px] rounded",
                    useScope === "current"
                      ? "bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 shadow-sm font-medium"
                      : "text-slate-500 dark:text-slate-400",
                    presentUses.size === 0 && "opacity-40 cursor-not-allowed",
                  )}
                >
                  이번 조회 용도
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={useScope === "all"}
                  onClick={() => setUseScope("all")}
                  className={clsx(
                    "px-2 py-0.5 text-[11px] rounded",
                    useScope === "all"
                      ? "bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 shadow-sm font-medium"
                      : "text-slate-500 dark:text-slate-400",
                  )}
                >
                  전체 용도
                </button>
              </div>
              <button
                type="button"
                onClick={() => setDraftBands(defaultBands())}
                className="px-2.5 py-1 rounded border border-slate-200 dark:border-slate-600 text-[11px] text-slate-700 dark:text-slate-200"
              >
                기본값 복원
              </button>
            </div>
          </div>
          <div className="flex-1 min-h-[280px] overflow-auto rounded border border-slate-100 dark:border-slate-700">
            <table className="w-full text-[11px] border-collapse">
              <thead className="sticky top-0 z-10 bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                <tr>
                  <th className="border px-2 py-1 text-left font-medium">용도</th>
                  <th className="border px-2 py-1 text-left font-medium">구조</th>
                  <th className="border px-2 py-1 text-right font-medium">원가 하한(만원/㎡)</th>
                  <th className="border px-2 py-1 text-right font-medium">원가 상한(만원/㎡)</th>
                  <th className="border px-2 py-1 text-right font-medium">내용연수(년)</th>
                  <th className="border px-2 py-1 text-right font-medium">최소잔가(%)</th>
                  <th className="border px-2 py-1 font-medium" />
                </tr>
              </thead>
              <tbody>
                {visibleUses.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-2 py-6 text-center text-slate-400">
                      이번 조회에 해당하는 용도가 없습니다.
                    </td>
                  </tr>
                ) : visibleUses.flatMap((use) =>
                  STRUCTURES.map((structure) => {
                    const key = bandKey(use, structure);
                    const band = draftBands[key];
                    const fresh = defaultBand(use, structure);
                    const differs = (field: "low" | "high" | "life" | "minResidual") =>
                      band != null && fresh != null && band[field] !== fresh[field];
                    return (
                      <tr key={key}>
                        <td className="border px-2 py-1 whitespace-nowrap">{use}</td>
                        <td className="border px-2 py-1 whitespace-nowrap">{structureGroupLabel(structure)}</td>
                        {band ? (
                          <>
                            <td className="border px-1 py-1">
                              <input
                                type="number"
                                value={band.low}
                                title={differs("low") ? "기본값과 다릅니다" : undefined}
                                onChange={(e) => {
                                  const n = Number(e.target.value);
                                  if (Number.isFinite(n)) onPatch(key, { low: n });
                                }}
                                className={bandInputClass(differs("low"), "w-16")}
                              />
                            </td>
                            <td className="border px-1 py-1">
                              <input
                                type="number"
                                value={band.high}
                                title={differs("high") ? "기본값과 다릅니다" : undefined}
                                onChange={(e) => {
                                  const n = Number(e.target.value);
                                  if (Number.isFinite(n)) onPatch(key, { high: n });
                                }}
                                className={bandInputClass(differs("high"), "w-16")}
                              />
                            </td>
                            <td className="border px-1 py-1">
                              <input
                                type="number"
                                value={band.life}
                                title={differs("life") ? "기본값과 다릅니다" : undefined}
                                onChange={(e) => {
                                  const n = Number(e.target.value);
                                  if (Number.isFinite(n)) onPatch(key, { life: n });
                                }}
                                className={bandInputClass(differs("life"), "w-14")}
                              />
                            </td>
                            <td className="border px-1 py-1 text-right">
                              <input
                                type="number"
                                value={Math.round(band.minResidual * 1000) / 10}
                                title={differs("minResidual") ? "기본값과 다릅니다" : undefined}
                                onChange={(e) => {
                                  const n = Number(e.target.value);
                                  if (Number.isFinite(n)) onPatch(key, { minResidual: n / 100 });
                                }}
                                className={bandInputClass(differs("minResidual"), "w-14")}
                              />
                            </td>
                          </>
                        ) : (
                          <td colSpan={4} className="border px-2 py-1 text-slate-400">
                            기준 없음
                          </td>
                        )}
                        <td className="border px-1 py-1 text-center">
                          <button
                            type="button"
                            onClick={() => onReset(use, structure)}
                            className="text-[10px] text-slate-500 hover:text-slate-800"
                          >
                            초기화
                          </button>
                        </td>
                      </tr>
                    );
                  }),
                )}
              </tbody>
            </table>
          </div>
        </section>
        <div className="shrink-0 flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 pt-3">
          <label className="inline-flex items-center gap-2 text-[12px] text-slate-600 dark:text-slate-300">
            <input type="checkbox" checked={showAllocation} onChange={(e) => setShowAllocation(e.target.checked)} />
            토지 배분단가 표시
          </label>
          <p className="text-[11px] text-amber-800 dark:text-amber-300">노란 칸은 수정한 값입니다.</p>
          <button
            type="button"
            onClick={() => onConfirm(draftBands, showAllocation)}
            className="ml-auto rounded bg-blue-600 px-4 py-1.5 text-[12px] font-medium text-white hover:bg-blue-700"
          >
            적용
          </button>
        </div>
      </div>
    </DraggableModalShell>
  );
}
