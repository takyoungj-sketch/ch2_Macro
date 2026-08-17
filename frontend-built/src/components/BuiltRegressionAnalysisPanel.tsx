import { useEffect, useMemo, useState } from "react";
import type { UseMutationResult } from "@tanstack/react-query";
import type {
  AssetType,
  RegressionRecommendResponse,
  RegressionRunRequest,
  RegressionRunResponse,
  RegressionSelectionRequest,
  RegressionVariableSpec,
} from "../types";
import { builtAnalysisScopeKey } from "../utils/builtAnalysisScopeKey";
import type { ProfileLinkTarget } from "../utils/profileLink";
import RecommendationModal from "./RecommendationModal";
import UpperScopeAnalysisCard from "./UpperScopeAnalysisCard";

type Props = {
  regBody: RegressionRunRequest;
  regData: RegressionRunResponse;
  resultRegBody: RegressionRunRequest;
  vars: RegressionVariableSpec;
  recommendM: UseMutationResult<
    RegressionRecommendResponse,
    Error,
    RegressionSelectionRequest
  >;
  assetType: AssetType;
  regionLabel: string;
  profileTarget?: ProfileLinkTarget | null;
};

export default function BuiltRegressionAnalysisPanel({
  regBody,
  regData,
  resultRegBody,
  vars,
  recommendM,
  assetType,
  regionLabel,
  profileTarget,
}: Props) {
  const [upperOpened, setUpperOpened] = useState(false);
  const [macroOpen, setMacroOpen] = useState(false);
  const scopeKey = useMemo(() => builtAnalysisScopeKey(regBody), [regBody]);

  useEffect(() => {
    setUpperOpened(false);
    setMacroOpen(false);
    recommendM.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 지역·기간·필터가 바뀔 때만 Macro 리셋
  }, [scopeKey]);

  const focusLabel = regData.focus_scope_label ?? regData.primary.scope_label;
  const explored = Boolean(recommendM.data);

  return (
    <div className="space-y-4">
      <div
        className="border-t-2 border-slate-200 dark:border-slate-700 pt-4 -mt-1"
        aria-labelledby="built-additional-analysis-heading"
      >
        <h2
          id="built-additional-analysis-heading"
          className="text-sm font-semibold text-slate-800 dark:text-slate-100"
        >
          추가분석
        </h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          기본 회귀·예측과 별도 — Macro 모형 탐색·상위지역 비교
        </p>
      </div>

      <section id="built-step-macro" className="card scroll-mt-16 space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="font-semibold text-sm">Macro 모형 탐색</h2>
            <p className="text-xs text-slate-500 mt-1">
              예측형(CV-MAPE)과 설명형(AIC)을 한 번에 찾습니다. 결과는 창 안에서만 보며 기본 통계
              식은 바꾸지 않습니다.
            </p>
          </div>
          <button
            type="button"
            className="btn btn-primary text-xs shrink-0"
            onClick={() => setMacroOpen(true)}
          >
            {explored ? "결과 보기" : "창 열기"}
          </button>
        </div>
      </section>

      <RecommendationModal
        open={macroOpen}
        onClose={() => setMacroOpen(false)}
        regBody={regBody}
        regData={regData}
        recommendM={recommendM}
        assetType={assetType}
        regionLabel={regionLabel}
        profileTarget={profileTarget}
      />

      <UpperScopeAnalysisCard
        regData={regData}
        regBody={resultRegBody}
        vars={vars}
        assetType={assetType}
        responseScale={resultRegBody.response_scale ?? "linear"}
        regionLabel={regionLabel}
        focusLabel={focusLabel}
        opened={upperOpened}
        onOpen={() => setUpperOpened(true)}
      />
    </div>
  );
}
