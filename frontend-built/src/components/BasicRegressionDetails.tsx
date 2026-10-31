import { StatsGlossaryHelp } from "./StatsGlossaryHelp";
import { formatProbability } from "../../../shared/regression-ui/format";
import type { AssetType, PredictOptions, RegressionCoeff, ResponseScale } from "../types";
import { dummyReferenceRows, formatCoefName, formatCoefValue, interpretCoefficient, isEquationSignificant, shortCoefName } from "../utils/regressionFormat";

// 기본회귀의 왼쪽 변수 선택 순서. 공유 회귀식·Macro의 정렬은 변경하지 않는다.
function variableOrder(name: string): number {
  if (name === "const") return -1;
  if (name === "gross_area") return 0;
  if (name === "land_area") return 1;
  if (name === "building_age") return 2;
  if (name === "road_code" || name.startsWith("road_")) return 3;
  if (name.startsWith("zone_")) return 4;
  if (name.startsWith("use_")) return 5;
  if (name.startsWith("struct_")) return 6;
  if (name === "assessed_land_price") return 7;
  if (name.startsWith("atype_")) return 8;
  if (name.startsWith("loc_")) return 9;
  return 10;
}

function ordered(coefficients: RegressionCoeff[]) {
  return [...coefficients].sort((a, b) => variableOrder(a.name) - variableOrder(b.name));
}

// 회귀식에만 적용하는 표시 순서. 연식·지역 항도 유의하면 뒤에 유지한다.
function equationOrder(name: string): number {
  if (name === "gross_area") return 0;
  if (name === "land_area") return 1;
  if (name.startsWith("zone_")) return 2;
  if (name === "road_code" || name.startsWith("road_")) return 3;
  if (name.startsWith("atype_")) return 4;
  if (name.startsWith("struct_")) return 5;
  if (name.startsWith("use_")) return 6;
  if (name === "assessed_land_price") return 7;
  if (name === "building_age") return 8;
  return 9;
}

function statistic(value?: number | null, digits = 4) {
  if (value == null || !Number.isFinite(value)) return "—";
  if (value !== 0 && Math.abs(value) < 0.5 * 10 ** -digits) return value.toExponential(2);
  return value.toLocaleString("ko-KR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

type Props = {
  coefficients: RegressionCoeff[];
  assetType: AssetType;
  responseScale: ResponseScale;
  predictOptions?: PredictOptions | null;
};

export function BasicRegressionEquation({ coefficients, assetType, responseScale, predictOptions, equation }: Props & { equation?: string }) {
  const intercept = coefficients.find(c => c.name === "const");
  const terms = coefficients.filter(c => c.name !== "const" && isEquationSignificant(c.p_value))
    .sort((a, b) => equationOrder(a.name) - equationOrder(b.name));
  const references = dummyReferenceRows(predictOptions, assetType);
  const dependent = responseScale === "linear" ? "금액(만원)" : "log(금액)";
  return <div className="space-y-3">
    <div className="rounded-lg border border-indigo-200 bg-indigo-50/50 p-3 dark:border-indigo-500/30 dark:bg-indigo-950/20">
      <p className="flex items-center gap-1 text-sm font-semibold text-slate-800 dark:text-slate-100">
        회귀식 · 유의변수 <StatsGlossaryHelp termId="coefficient" size="xs" />
      </p>
      <p className="mt-2 flex flex-wrap gap-x-2 gap-y-2 text-base font-bold leading-relaxed text-yellow-700 dark:text-yellow-300" aria-label="유의변수 회귀식">
        {!coefficients.length ? <span className="break-words">{equation || "회귀식을 제공하지 않습니다."}</span> : <>
          <span>{dependent} = {intercept ? formatCoefValue(intercept.estimate) : ""}</span>
          {terms.map((c, index) => <span key={c.name} className="max-w-full break-words">
            {c.estimate < 0 ? "−" : intercept || index > 0 ? "+" : ""} {formatCoefValue(Math.abs(c.estimate))} × ({shortCoefName(c.name, assetType, responseScale)})
          </span>)}
        </>}
      </p>
    </div>
    {references.length > 0 && <div className="text-sm leading-relaxed text-slate-700 dark:text-slate-200" aria-label="회귀식 기준 범주">
      <span className="font-semibold">기준 범주</span>
      <ul className="mt-1 flex flex-wrap gap-x-5 gap-y-1">
        {references.map(reference => <li key={reference.key}>{reference.kind}: <span className="font-medium">{reference.display}</span></li>)}
      </ul>
    </div>}
  </div>;
}

export function BasicRegressionCoefficients({ coefficients, assetType, responseScale, predictOptions }: Props) {
  const intercept = coefficients.find(c => c.name === "const");
  return <div className="space-y-2">
    <div tabIndex={0} role="region" aria-label="기본회귀 계수 표" className="max-h-96 overflow-auto rounded-lg border border-slate-200 dark:border-slate-700">
      <table className="w-full min-w-[640px] border-collapse text-xs">
        <thead className="sticky top-0 bg-slate-100 text-slate-700 dark:bg-slate-900 dark:text-slate-200">
          <tr>
            <th className="px-3 py-2 text-left font-medium">변수</th>
            <th className="px-2 py-2 text-center font-medium">β</th>
            <th className="px-3 py-2 text-left font-medium">효과 해석</th>
            <th className="px-2 py-2 text-center font-medium">SE <StatsGlossaryHelp termId="se" size="xs" /></th>
            <th className="px-2 py-2 text-center font-medium">t</th>
            <th className="px-2 py-2 text-center font-medium">p <StatsGlossaryHelp termId="p_value" size="xs" /></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
          {ordered(coefficients.filter(c => c.name !== "const")).map(c => <tr key={c.name} className={isEquationSignificant(c.p_value) ? "bg-emerald-50/50 dark:bg-emerald-950/20" : ""}>
            <td className="px-3 py-2 text-left font-medium">{formatCoefName(c.name, assetType, responseScale)}</td>
            <td className="px-2 py-2 text-center tabular-nums whitespace-nowrap">{statistic(c.estimate)}</td>
            <td className="px-3 py-2 text-left leading-relaxed">{interpretCoefficient(c, responseScale, assetType, predictOptions)}</td>
            <td className="px-2 py-2 text-center tabular-nums whitespace-nowrap">{statistic(c.std_err)}</td>
            <td className="px-2 py-2 text-center tabular-nums whitespace-nowrap">{statistic(c.t_value, 2)}</td>
            <td className="px-2 py-2 text-center tabular-nums whitespace-nowrap">{formatProbability(c.p_value)}</td>
          </tr>)}
        </tbody>
      </table>
    </div>
    {intercept && <details className="text-xs text-slate-600 dark:text-slate-300">
      <summary className="cursor-pointer py-1">절편 통계 보기</summary>
      <p className="py-2 tabular-nums">β {statistic(intercept.estimate)} · SE {statistic(intercept.std_err)} · t {statistic(intercept.t_value, 2)} · p {formatProbability(intercept.p_value)}</p>
    </details>}
  </div>;
}
