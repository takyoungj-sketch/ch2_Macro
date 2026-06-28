import { useState } from "react";
import clsx from "clsx";
import type { RegressionCoeff, RegressionModelType } from "../types";
import {
  compareCoefficientOrder,
  EQUATION_SIG_P,
  formatCoefValue,
  isEquationSignificant,
  shortDisplayLabel,
  sortCoefficientsByVariableOrder,
} from "../utils/collectiveRegressionFormat";

export default function CollectiveRegressionEquation({
  coefficients,
  modelType,
  equation,
}: {
  coefficients: RegressionCoeff[];
  modelType: RegressionModelType;
  equation?: string;
}) {
  const [showAll, setShowAll] = useState(false);
  const dep = modelType === "log" ? "log(금액)" : "금액(만원)";
  const intercept = coefficients.find((c) => c.name === "const");

  if (!intercept && equation) {
    return <p className="text-sm font-mono leading-relaxed break-words text-slate-800 dark:text-slate-100">{equation}</p>;
  }
  if (!intercept) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">{dep} = —</p>;
  }

  const others = coefficients.filter((c) => c.name !== "const");
  const sig = sortCoefficientsByVariableOrder(
    others.filter((c) => isEquationSignificant(c.p)),
  );
  const nonsig = sortCoefficientsByVariableOrder(
    others.filter((c) => !isEquationSignificant(c.p)),
  );

  const visible = showAll ? [...sig, ...nonsig] : sig;
  const hiddenCount = nonsig.length;

  return (
    <div className="space-y-1">
      <p className="text-sm font-mono leading-relaxed break-words text-slate-800 dark:text-slate-100">
        <span>
          {dep} = {formatCoefValue(intercept.coef)}
        </span>
        {visible.map((c) => {
          const sign = c.coef >= 0 ? "+" : "−";
          const mag = formatCoefValue(Math.abs(c.coef));
          const significant = isEquationSignificant(c.p);
          const faded = showAll && !significant;
          return (
            <span
              key={c.name}
              className={clsx(faded && "opacity-40", significant && !faded && "font-semibold")}
            >
              {" "}
              {sign} {mag}·{shortDisplayLabel(c.label)}
            </span>
          );
        })}
        {!showAll && hiddenCount > 0 && (
          <span className="text-slate-400 dark:text-slate-500 text-xs font-sans not-italic">
            {" "}
            · 외 {hiddenCount}개
          </span>
        )}
      </p>

      {hiddenCount > 0 && (
        <button
          type="button"
          className="text-[11px] text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 underline underline-offset-2"
          onClick={() => setShowAll((v) => !v)}
        >
          {showAll ? "유의변수만 보기" : "전체보기"}
        </button>
      )}

      <p className="text-[10px] text-slate-400 dark:text-slate-500">
        회귀식 유의 기준 p&lt;{EQUATION_SIG_P}
        {!showAll && hiddenCount > 0 ? " · 기본은 유의 변수만" : showAll ? " · 비유의는 흐림" : ""}
      </p>
    </div>
  );
}
