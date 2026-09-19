import { useEffect, useMemo, useState } from "react";
import type { UseMutationResult } from "@tanstack/react-query";
import type {
  AssetType,
  RegressionRecommendResponse,
  RegressionRunRequest,
  RegressionRunResponse,
  RegressionSelectionRequest,
  RegressionVariableSpec,
  ResponseScale,
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
  onCancelRecommend?: () => void;
  /** 확인 후 왼쪽 변수·척도만 옮긴다. 통계분석은 돌리지 않는다. */
  onAdopt?: (vars: RegressionVariableSpec, scale: ResponseScale) => void;
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
  onCancelRecommend,
  onAdopt,
}: Props) {
  const [upperOpened, setUpperOpened] = useState(false);
  const [macroOpen, setMacroOpen] = useState(false);
  const scopeKey = useMemo(() => builtAnalysisScopeKey(regBody), [regBody]);

  useEffect(() => {
    setUpperOpened(false);
    setMacroOpen(false);
    onCancelRecommend?.();
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
          기본 회귀·예측과 별도 — Macro 모형 탐색·상위지역 재적합
        </p>
      </div>

      <section id="built-step-macro" className="card scroll-mt-16 space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="font-semibold text-sm">Macro 모형 탐색</h2>
            <p className="text-xs text-slate-500 mt-1">
              변수 조합과 척도를 CV-MAPE로 탐색합니다. 추천식을 쓰려면 창 안에서 「기본 통계에 이
              식 적용」을 누른 뒤, 왼쪽 「통계분석」을 다시 실행하세요.
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
        onClose={() => {
          onCancelRecommend?.();
          setMacroOpen(false);
        }}
        regBody={regBody}
        regData={regData}
        recommendM={recommendM}
        assetType={assetType}
        regionLabel={regionLabel}
        profileTarget={profileTarget}
        onAdopt={
          onAdopt
            ? (vars, scale) => {
                onAdopt(vars, scale);
                setMacroOpen(false);
              }
            : undefined
        }
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
