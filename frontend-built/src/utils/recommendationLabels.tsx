/** 모형 추천 n 라벨 SSOT — scope_n_tx / selection_n / fit_n (R3). */

export type ScopeNCounts = {
  scope_n_tx: number;
  selection_n?: number;
  fit_n?: number;
};

export function formatScopeNLine(counts: ScopeNCounts): string {
  const parts = [`거래 ${counts.scope_n_tx}`];
  if (counts.selection_n != null) parts.push(`탐색 ${counts.selection_n}`);
  if (counts.fit_n != null) parts.push(`적합 ${counts.fit_n}`);
  return parts.join(" · ");
}

type ScopeNLabelsProps = {
  counts: ScopeNCounts;
  className?: string;
  compact?: boolean;
};

/** scope=필터 통과 원장, selection=후보 complete-case, fit=채택 식 complete-case */
export function ScopeNLabels({ counts, className = "", compact = false }: ScopeNLabelsProps) {
  if (compact) {
    return (
      <p className={className} title="거래=scope_n_tx · 탐색=selection_n · 적합=fit_n">
        {formatScopeNLine(counts)}
      </p>
    );
  }
  return (
    <dl
      className={`grid grid-cols-3 gap-1 text-[11px] tabular-nums ${className}`}
      title="거래=필터 통과 원장 · 탐색=SSOT 후보 complete-case · 적합=채택 식 complete-case"
    >
      <div>
        <dt className="text-slate-400">거래</dt>
        <dd className="font-medium">{counts.scope_n_tx}</dd>
      </div>
      {counts.selection_n != null && (
        <div>
          <dt className="text-slate-400">탐색</dt>
          <dd className="font-medium">{counts.selection_n}</dd>
        </div>
      )}
      {counts.fit_n != null && (
        <div>
          <dt className="text-slate-400">적합</dt>
          <dd className="font-medium">{counts.fit_n}</dd>
        </div>
      )}
    </dl>
  );
}

export type CvFitnessTone = "positive" | "neutral" | "warning" | "negative";

export interface CvFitnessTier {
  tier: string;
  label_ko: string;
  tone: CvFitnessTone;
  max_cv_mape?: number | null;
}

const CV_TONE_CLASS: Record<CvFitnessTone, string> = {
  positive: "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-200 dark:border-emerald-800",
  neutral: "bg-slate-100 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-600",
  warning: "bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-950 dark:text-orange-200 dark:border-orange-800",
  negative: "bg-red-100 text-red-800 border-red-300 dark:bg-red-950 dark:text-red-200 dark:border-red-800",
};

const CV_TIER_BOUNDS: Array<{ max: number; tier: string; label_ko: string; tone: CvFitnessTone }> = [
  { max: 15, tier: "excellent", label_ko: "매우 우수", tone: "positive" },
  { max: 25, tier: "good", label_ko: "우수", tone: "positive" },
  { max: 40, tier: "fair", label_ko: "보통", tone: "neutral" },
  { max: 60, tier: "caution", label_ko: "주의", tone: "warning" },
  { max: 9999, tier: "unsuitable", label_ko: "예측 부적합", tone: "negative" },
];

export function lookupCvFitnessClient(cvMape?: number | null): CvFitnessTier | null {
  if (cvMape == null) return null;
  for (const row of CV_TIER_BOUNDS) {
    if (cvMape < row.max) {
      return { tier: row.tier, label_ko: row.label_ko, tone: row.tone, max_cv_mape: row.max };
    }
  }
  return { tier: "unsuitable", label_ko: "예측 부적합", tone: "negative" };
}

export function CvFitnessBadge({
  cvMape,
  fitness,
  className = "",
}: {
  cvMape?: number | null;
  fitness?: CvFitnessTier | null;
  className?: string;
}) {
  const resolved = fitness ?? lookupCvFitnessClient(cvMape);
  if (cvMape == null && !resolved) return null;
  const tone = resolved?.tone ?? "neutral";
  const label = resolved?.label_ko ?? "—";
  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[11px] font-medium tabular-nums ${CV_TONE_CLASS[tone]} ${className}`}
      title="CV-MAPE 예측 적합 등급"
    >
      {cvMape != null && <span>{cvMape.toFixed(1)}%</span>}
      <span>{label}</span>
    </span>
  );
}
