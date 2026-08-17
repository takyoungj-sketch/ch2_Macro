import clsx from "clsx";
import type { UseMutationResult } from "@tanstack/react-query";
import type {
  RegressionRecommendResponse,
  RegressionSelectionRequest,
  RegressionVariableSpec,
  ResponseScale,
} from "../types";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import RecommendStagePanel, { type AdoptPoolPayload } from "./RecommendStagePanel";
import { BUILT_RECOMMEND_HELP } from "../utils/builtAnalysisHelp";

type MacroMode = "predictive" | "explanatory";

type Props = {
  mode: MacroMode;
  sectionId: string;
  recommendM: UseMutationResult<
    RegressionRecommendResponse,
    Error,
    RegressionSelectionRequest
  >;
  onRunRecommend: () => void;
  onAdopt: (vars: RegressionVariableSpec, scale: ResponseScale) => void;
  onAdoptPool?: (payload: AdoptPoolPayload) => void;
  adopting?: boolean;
  onPredict?: (vars: RegressionVariableSpec, scale: ResponseScale, label: string) => void;
  predictActiveLabel?: string | null;
  regionNameByCode?: Record<string, string>;
  onRunTwin?: () => void;
  twinRunning?: boolean;
  showHelp?: boolean;
  /** 사용자가 이 모드 탐색을 실행했을 때만 결과 표시 */
  explored?: boolean;
  /** 이 카드에서 탐색 요청 중 */
  exploring?: boolean;
};

const META: Record<
  MacroMode,
  { title: string; subtitle: string }
> = {
  predictive: {
    title: "Macro 예측형",
    subtitle: "CV-MAPE 1위 — SSOT 변수 풀. 한 번 탐색하면 설명형도 함께 채워집니다.",
  },
  explanatory: {
    title: "Macro 설명형",
    subtitle: "AIC 1위 — 계수 해석용. Adj R²는 참고 숫자입니다.",
  },
};

/** @deprecated RecommendationModal 탭 창으로 대체. 인라인 이중 카드는 쓰지 않음. */
export default function MacroModelExploreCard({
  mode,
  sectionId,
  recommendM,
  onRunRecommend,
  onAdopt,
  onAdoptPool,
  adopting,
  onPredict,
  predictActiveLabel,
  regionNameByCode,
  onRunTwin,
  twinRunning,
  showHelp = true,
  explored = false,
  exploring = false,
}: Props) {
  const meta = META[mode];
  const loading = exploring && recommendM.isPending && !recommendM.data;
  const showResults = explored && Boolean(recommendM.data);

  return (
    <section id={sectionId} className="card scroll-mt-16 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-semibold text-sm">{meta.title}</h2>
          <p className="text-xs text-slate-500 mt-1">{meta.subtitle}</p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {showHelp && <AnalysisHelpPanel explain={BUILT_RECOMMEND_HELP} />}
          <button
            type="button"
            className={clsx(
              "btn text-xs shrink-0",
              showResults ? "btn-ghost" : "btn-primary",
            )}
            disabled={recommendM.isPending}
            onClick={onRunRecommend}
          >
            {exploring && recommendM.isPending
              ? "탐색 중…"
              : showResults
                ? "다시 탐색"
                : "Macro 탐색"}
          </button>
        </div>
      </div>

      {loading && (
        <p className="text-xs text-slate-400 text-center py-6">Macro 탐색 계산 중…</p>
      )}

      {recommendM.isError && exploring && (
        <p className="text-sm text-red-600">
          {(recommendM.error as Error).message ?? "Macro 탐색 실패"}
        </p>
      )}

      {!loading && !showResults && !(recommendM.isError && exploring) && (
        <p className="text-xs text-slate-400 py-4">
          「Macro 탐색」을 누르면 SSOT 변수 풀에서 예측형(CV-MAPE)과 설명형(AIC) 후보를 함께
          찾습니다.
        </p>
      )}

      {showResults && recommendM.data && (
        <RecommendStagePanel
          data={recommendM.data}
          mode={mode}
          onAdopt={onAdopt}
          onAdoptPool={onAdoptPool}
          adopting={adopting}
          onPredict={onPredict}
          predictActiveLabel={predictActiveLabel}
          regionNameByCode={regionNameByCode}
          onRunTwin={mode === "predictive" ? onRunTwin : undefined}
          twinRunning={twinRunning}
        />
      )}
    </section>
  );
}
