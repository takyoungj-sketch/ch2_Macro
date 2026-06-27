import { useState } from "react";
import clsx from "clsx";
import type { AssetType, RegressionCoeff, ResponseScale } from "../types";
import {
  EQUATION_SIG_P,
  formatCoefName,
  formatCoefValue,
  isEquationSignificant,
} from "../utils/regressionFormat";

type Props = {
  coefficients: RegressionCoeff[];
  responseScale: ResponseScale;
  assetType: AssetType;
  /** API equation fallback when coefficients empty */
  equation?: string;
  /** 전체보기 토글 표시 (기본 true) */
  showToggle?: boolean;
};

export default function RegressionEquation({
  coefficients,
  responseScale,
  assetType,
  equation,
  showToggle = true,
}: Props) {
  const [showAll, setShowAll] = useState(false);
  const dep = responseScale === "log" ? "log(금액)" : "금액";
  const intercept = coefficients.find((c) => c.name === "const");

  if (!intercept && equation) {
    return <p className="text-sm font-mono leading-relaxed break-words">{equation}</p>;
  }
  if (!intercept) {
    return <p className="text-sm text-slate-500">{dep} = —</p>;
  }

  const others = coefficients.filter((c) => c.name !== "const");
  const sig = others
    .filter((c) => isEquationSignificant(c.p_value))
    .sort((a, b) => (a.p_value ?? 1) - (b.p_value ?? 1));
  const nonsig = others
    .filter((c) => !isEquationSignificant(c.p_value))
    .sort((a, b) => (a.p_value ?? 1) - (b.p_value ?? 1));

  const visible = showAll ? [...sig, ...nonsig] : sig;
  const hiddenCount = nonsig.length;

  return (
    <div className="space-y-1">
      <p className="text-sm font-mono leading-relaxed break-words">
        <span>
          {dep} = {formatCoefValue(intercept.estimate)}
        </span>
        {visible.map((c) => {
          const sign = c.estimate >= 0 ? "+" : "−";
          const mag = formatCoefValue(Math.abs(c.estimate));
          const label = formatCoefName(c.name, assetType);
          const faded = showAll && !isEquationSignificant(c.p_value);
          return (
            <span key={c.name} className={clsx(faded && "opacity-40")}>
              {" "}
              {sign} {mag}·{label}
            </span>
          );
        })}
        {!showAll && hiddenCount > 0 && (
          <span className="text-slate-400 text-xs font-sans not-italic">
            {" "}
            · 외 {hiddenCount}개
          </span>
        )}
      </p>

      {showToggle && hiddenCount > 0 && (
        <button
          type="button"
          className="text-[11px] text-slate-500 hover:text-slate-700 underline underline-offset-2"
          onClick={() => setShowAll((v) => !v)}
        >
          {showAll ? "유의변수만 보기" : "전체보기"}
        </button>
      )}

      <p className="text-[10px] text-slate-400">
        회귀식 유의 기준 p&lt;{EQUATION_SIG_P}
        {!showAll && hiddenCount > 0 ? " · 기본은 유의 변수만" : showAll ? " · 비유의는 흐림" : ""}
      </p>
    </div>
  );
}
