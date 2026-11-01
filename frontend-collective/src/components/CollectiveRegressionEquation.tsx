import { useState } from "react";
import clsx from "clsx";
import type { RegressionCoeff, RegressionModelType } from "../types";
import {
  EQUATION_SIG_P,
  formatCoefValue,
  isEquationSignificant,
  shortDisplayLabel,
  sortCoefficientsByVariableOrder,
} from "../utils/collectiveRegressionFormat";

function isTimeCoef(c: RegressionCoeff) {
  return c.name.startsWith("time_");
}

function timeCode(c: RegressionCoeff) {
  if (c.name.startsWith("time_")) return c.name.slice("time_".length);
  return shortDisplayLabel(c.label);
}

export default function CollectiveRegressionEquation({
  coefficients,
  modelType,
  equation,
  timeReference,
  targetLabel = "금액",
  targetUnit = "만원",
  prominent = false,
  coefficientOrder,
  showTechnicalNote = true,
}: {
  coefficients: RegressionCoeff[];
  modelType: RegressionModelType;
  equation?: string;
  timeReference?: string | null;
  targetLabel?: string;
  targetUnit?: string;
  prominent?: boolean;
  coefficientOrder?: readonly string[];
  showTechnicalNote?: boolean;
}) {
  const equationClass = prominent ? "text-base font-bold leading-relaxed break-words text-amber-700 dark:text-yellow-300" : "text-sm font-mono leading-relaxed break-words text-slate-800 dark:text-slate-100";
  const [showAll, setShowAll] = useState(false);
  const dep = modelType === "log" ? `log(${targetLabel})` : `${targetLabel}(${targetUnit})`;
  const intercept = coefficients.find((c) => c.name === "const");

  if (!intercept && equation) {
    return <p className={equationClass}>{equation}</p>;
  }
  if (!intercept) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">{dep} = —</p>;
  }

  const others = coefficients.filter((c) => c.name !== "const" && !isTimeCoef(c));
  const time = coefficients.filter(isTimeCoef).sort((a, b) => a.name.localeCompare(b.name));
  const sig = sortCoefficientsByVariableOrder(others.filter((c) => isEquationSignificant(c.p)), coefficientOrder);
  const nonsig = sortCoefficientsByVariableOrder(others.filter((c) => !isEquationSignificant(c.p)), coefficientOrder);
  const sigTime = time.filter((c) => isEquationSignificant(c.p));
  const nonsigTime = time.filter((c) => !isEquationSignificant(c.p));
  const visible = showAll ? (coefficientOrder ? sortCoefficientsByVariableOrder([...sig, ...nonsig], coefficientOrder) : [...sig, ...nonsig]) : sig;
  const visibleTime = showAll ? [...sigTime, ...nonsigTime] : sigTime;
  const hiddenCount = nonsig.length + nonsigTime.length;

  return (
    <div className="space-y-1">
      <p className={equationClass}>
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
              className={clsx(faded && "text-slate-600 dark:text-slate-300", significant && !faded && "font-semibold")}
            >
              {" "}
              {sign} {mag}·{prominent ? `(${shortDisplayLabel(c.label)})` : shortDisplayLabel(c.label)}
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

      {visibleTime.length > 0 && (
        <div className="space-y-0.5">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            거래시점
            {timeReference ? ` · 기준 ${timeReference} (최다 반기)` : " · 기준은 거래 최다 반기"}
          </p>
          <p className={equationClass}>
            {visibleTime.map((c, i) => {
              const sign = c.coef >= 0 ? "+" : "−";
              const mag = formatCoefValue(Math.abs(c.coef));
              const significant = isEquationSignificant(c.p);
              const faded = showAll && !significant;
              return (
                <span
                  key={c.name}
                  className={clsx(faded && "text-slate-600 dark:text-slate-300", significant && !faded && "font-semibold")}
                >
                  {i > 0 ? " · " : ""}
                  {timeCode(c)} {sign}
                  {mag}
                </span>
              );
            })}
          </p>
        </div>
      )}

      {hiddenCount > 0 && (
        <button
          type="button"
          className="text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 underline underline-offset-2"
          onClick={() => setShowAll((v) => !v)}
        >
          {showAll ? "유의변수만 보기" : "전체보기"}
        </button>
      )}

      {showTechnicalNote && <p className="text-xs text-slate-500 dark:text-slate-400">
        회귀식 유의 기준 p&lt;{EQUATION_SIG_P}
        {!showAll && hiddenCount > 0 ? " · 기본은 유의 계수만" : showAll ? " · 비유의 계수는 보통 굵기" : ""}
      </p>}
    </div>
  );
}
