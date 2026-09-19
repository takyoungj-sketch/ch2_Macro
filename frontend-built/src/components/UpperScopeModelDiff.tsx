import clsx from "clsx";
import type { AssetType, RegressionCoeff, RegressionLevelResult } from "../types";
import { ADMIN_LABELS, levelCardTitle } from "../utils/regressionFormat";

/** 연속변수 — 기준 범주가 없어 초점·상위 사이 부호를 바로 견줄 수 있다. */
const CONTINUOUS_ORDER = ["gross_area", "land_area", "building_age", "road_code"] as const;

const CONTINUOUS_LABELS: Record<string, string> = {
  gross_area: "연면적",
  land_area: "대지면적",
  building_age: "연식",
  road_code: "도로",
};

const DUMMY_GROUPS: Array<{ prefix: string; label: string; detachedLabel?: string }> = [
  { prefix: "zone_", label: "용도지역 더미" },
  { prefix: "use_", label: "건축물용도 더미", detachedLabel: "주택유형 더미" },
  { prefix: "struct_", label: "구조 더미" },
  { prefix: "road_", label: "도로조건 더미" },
  { prefix: "atype_", label: "유형 더미" },
  { prefix: "loc_", label: "지역 더미" },
];

type Row = {
  key: string;
  label: string;
  focus: number;
  upper: number;
  /** 상위 단계에서 구조적으로 빠지는 열 */
  scopeBound?: boolean;
};

function countPrefix(coefs: RegressionCoeff[], prefix: string): number {
  return coefs.filter((c) => c.name.startsWith(prefix)).length;
}

function hasName(coefs: RegressionCoeff[], name: string): number {
  return coefs.some((c) => c.name === name) ? 1 : 0;
}

function buildRows(
  focus: RegressionCoeff[],
  upper: RegressionCoeff[],
  assetType: AssetType,
  upperLevel: string,
): Row[] {
  const rows: Row[] = [];
  for (const name of CONTINUOUS_ORDER) {
    const f = hasName(focus, name);
    const u = hasName(upper, name);
    if (!f && !u) continue;
    rows.push({ key: name, label: CONTINUOUS_LABELS[name] ?? name, focus: f, upper: u });
  }
  for (const group of DUMMY_GROUPS) {
    const f = countPrefix(focus, group.prefix);
    const u = countPrefix(upper, group.prefix);
    if (!f && !u) continue;
    const label =
      assetType === "detached" && group.detachedLabel ? group.detachedLabel : group.label;
    rows.push({
      key: group.prefix,
      label,
      focus: f,
      upper: u,
      scopeBound:
        group.prefix === "loc_" && f > 0 && u === 0 && (upperLevel === "sigungu" || upperLevel === "gu"),
    });
  }
  return rows;
}

function cellText(count: number, isDummy: boolean): string {
  if (count === 0) return "—";
  return isDummy ? `${count}열` : "포함";
}

type SignRow = {
  key: string;
  label: string;
  focusSign: "+" | "−";
  upperSign: "+" | "−";
  holds: boolean;
  bothSignificant: boolean;
};

function buildSignRows(focus: RegressionCoeff[], upper: RegressionCoeff[]): SignRow[] {
  const out: SignRow[] = [];
  for (const name of CONTINUOUS_ORDER) {
    const f = focus.find((c) => c.name === name);
    const u = upper.find((c) => c.name === name);
    if (!f || !u || !Number.isFinite(f.estimate) || !Number.isFinite(u.estimate)) continue;
    const focusSign = f.estimate >= 0 ? "+" : "−";
    const upperSign = u.estimate >= 0 ? "+" : "−";
    out.push({
      key: name,
      label: CONTINUOUS_LABELS[name] ?? name,
      focusSign,
      upperSign,
      holds: focusSign === upperSign,
      bothSignificant:
        f.p_value != null && f.p_value < 0.05 && u.p_value != null && u.p_value < 0.05,
    });
  }
  return out;
}

type Props = {
  focus: RegressionLevelResult;
  upper: RegressionLevelResult;
  assetType: AssetType;
  focusTitle: string;
};

/**
 * 초점과 상위지역 재적합이 같은 모형이 아님을 드러내는 패널.
 * 변수 구성 차이 → 공통 변수 부호 → 표본 중첩·지표 주의 순서로 읽힌다.
 */
export default function UpperScopeModelDiff({ focus, upper, assetType, focusTitle }: Props) {
  const rows = buildRows(focus.coefficients, upper.coefficients, assetType, upper.admin_level);
  const signRows = buildSignRows(focus.coefficients, upper.coefficients);
  const upperTitle = levelCardTitle(upper.scope_label, upper.admin_level);
  const upperLevelLabel = ADMIN_LABELS[upper.admin_level] ?? upper.admin_level;
  const scopeBoundRow = rows.find((r) => r.scopeBound);
  const heldCount = signRows.filter((r) => r.holds).length;

  if (!rows.length) return null;

  return (
    <div className="rounded-md border border-amber-200 dark:border-amber-800 bg-amber-50/40 dark:bg-amber-950/20 p-3 space-y-3 text-xs">
      <div>
        <h4 className="font-semibold text-sm text-amber-900 dark:text-amber-100">모형 차이</h4>
        <p className="text-slate-600 dark:text-slate-300 mt-0.5 leading-relaxed">
          {upperTitle} 재적합은 <strong>{focusTitle}</strong>과 같은 표본도, 같은 식도 아닙니다.
          아래 차이를 먼저 확인한 뒤 계수를 읽으세요.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="text-slate-500 border-b border-amber-200 dark:border-amber-800">
              <th className="py-1 pr-2 font-medium">변수</th>
              <th className="py-1 pr-2 font-medium">초점</th>
              <th className="py-1 pr-2 font-medium">{upperLevelLabel}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const isDummy = row.key.endsWith("_");
              const differs = (row.focus > 0) !== (row.upper > 0);
              return (
                <tr
                  key={row.key}
                  className={clsx(
                    "border-b border-amber-100/70 dark:border-amber-900/40 last:border-0",
                    differs && "bg-amber-100/50 dark:bg-amber-900/30",
                  )}
                >
                  <td className="py-1 pr-2">{row.label}</td>
                  <td className="py-1 pr-2 tabular-nums">{cellText(row.focus, isDummy)}</td>
                  <td className="py-1 pr-2 tabular-nums">
                    {cellText(row.upper, isDummy)}
                    {row.scopeBound && (
                      <span className="ml-1 text-amber-800 dark:text-amber-200">← 제외</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {scopeBoundRow && (
        <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
          <strong>지역 더미를 넣지 않는 이유</strong> — {upperLevelLabel}는 그 단위 자체가 표본
          경계입니다. 표본 안에 비교할 다른 {upperLevelLabel}가 없어 지역 간 차이를 담을 열이
          만들어지지 않습니다. 정책으로 유지하는 선택이며 누락이 아닙니다.
        </p>
      )}

      {signRows.length > 0 && (
        <div className="space-y-1">
          <p className="font-medium text-slate-700 dark:text-slate-200">공통 변수 계수 방향</p>
          <ul className="space-y-0.5">
            {signRows.map((row) => (
              <li key={row.key} className="flex items-center gap-1.5">
                <span className="text-slate-600 dark:text-slate-300">{row.label}</span>
                <span className="tabular-nums font-medium">
                  {row.focusSign} → {row.upperSign}
                </span>
                <span
                  className={clsx(
                    "font-medium",
                    row.holds
                      ? "text-emerald-700 dark:text-emerald-300"
                      : "text-rose-700 dark:text-rose-300",
                  )}
                >
                  {row.holds ? "유지" : "뒤바뀜"}
                </span>
                {!row.bothSignificant && (
                  <span className="text-slate-400">· 한쪽 이상 유의하지 않음</span>
                )}
              </li>
            ))}
          </ul>
          <p className="text-slate-500">
            {signRows.length}개 중 {heldCount}개 방향 유지. 더미는 기준 범주가 단계마다 달라질 수
            있어 부호를 견주지 않습니다.
          </p>
        </div>
      )}

      <p className="text-slate-600 dark:text-slate-300 leading-relaxed border-t border-amber-200 dark:border-amber-800 pt-2">
        <strong>표본</strong> — {upperLevelLabel} {upper.n.toLocaleString("ko-KR")}건은 초점{" "}
        {focus.n.toLocaleString("ko-KR")}건을 포함합니다(중첩). 독립된 두 표본의 비교가 아니므로
        Adj R²·MAPE를 우열로 읽지 마세요. 표본 크기와 변수 구성이 동시에 다르면 두 지표는 비교
        가능한 값이 아닙니다. 공통 변수의 방향이 유지되는지만 참고하세요.
      </p>
    </div>
  );
}
