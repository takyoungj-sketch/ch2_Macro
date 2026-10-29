import { useEffect, useMemo, useRef } from "react";
import { useMutation } from "@tanstack/react-query";
import type { AssetType, RegressionRunRequest } from "../types";
import { recommend2Regression } from "../api/client";
import { builtAnalysisScopeKey } from "../utils/builtAnalysisScopeKey";
import { formatResponseScale } from "../utils/recommendationLabels";
import DraggableModalShell from "./DraggableModalShell";
import FocusRegressionCard from "./FocusRegressionCard";

const CV_TITLE =
  "학습 표본에서 계산한 오차가 아닙니다. 같은 조합에서 척도를 견줄 때 맞춘 양수 가격·면적 행의 교차검증 오차입니다.";

type Props = {
  open: boolean;
  onClose: () => void;
  regBody: RegressionRunRequest;
  assetType: AssetType;
};

function pct(value: number | null | undefined): string {
  return value == null ? "—" : `${value.toFixed(1)}%`;
}

export default function Recommend2Modal({ open, onClose, regBody, assetType }: Props) {
  const abortRef = useRef<AbortController | null>(null);
  const triggerKey = useMemo(
    () =>
      JSON.stringify({
        scope: builtAnalysisScopeKey(regBody),
        enrich: regBody.enrich ?? false,
        structure: Boolean(regBody.variables?.structure_dummy),
        assessed: Boolean(regBody.variables?.assessed_land_price),
      }),
    [regBody],
  );

  const recommend2M = useMutation({
    mutationFn: (body: RegressionRunRequest) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      return recommend2Regression(body, controller.signal);
    },
  });

  useEffect(() => {
    if (!open) {
      abortRef.current?.abort();
      return;
    }
    recommend2M.mutate(regBody);
    // 지역·기간·보강·구조·공시지가가 바뀔 때만 다시 돈다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, triggerKey]);

  if (!open) return null;

  const data = recommend2M.data;
  const loading = recommend2M.isPending && !data;

  return (
    <DraggableModalShell
      open={open}
      onClose={onClose}
      titleId="recommend2-modal-title"
      title="모형추천2"
      subtitle="같은 행 안에서의 예측형입니다. 통계분석 결과와 왼쪽 변수는 바꾸지 않습니다."
      maxWidthClass="max-w-4xl"
      resizable
      allowFullscreen
      defaultWidth={Math.min(880, typeof window !== "undefined" ? window.innerWidth - 48 : 880)}
      defaultHeight={Math.min(760, typeof window !== "undefined" ? window.innerHeight - 48 : 760)}
      minWidth={520}
      minHeight={360}
    >
      <div className="h-full min-h-0 space-y-3">
        <p className="text-xs leading-relaxed text-slate-600 dark:text-slate-300">
          이 창은 왼쪽에서 고른 변수와 회귀모형, 결측 거래 제외를 탐색에 쓰지 않습니다.
          지역·기간·지분·이상치·건축물대장 보강만 표본 조건입니다. 구조와 개별공시지가는
          보강을 켜고 체크한 경우에만 후보에 넣습니다.
        </p>

        {loading && <p className="text-sm text-slate-400 text-center py-8">모형추천2 계산 중…</p>}

        {recommend2M.isError && (
          <p className="text-sm text-red-600">
            {(recommend2M.error as Error).message ?? "모형추천2 실패"}
          </p>
        )}

        {data && (
          <div className="space-y-3">
            <p className="text-xs text-slate-500">
              탐색 풀 {data.pool_summary} · 조합 {data.total_subsets}개 · 조회 {data.n_pool}건
            </p>
            {data.excluded.length > 0 && (
              <ul className="text-xs text-slate-500 list-disc pl-4">
                {data.excluded.map((row) => (
                  <li key={row.detail}>{row.detail}</li>
                ))}
              </ul>
            )}

            <FocusRegressionCard
              result={data.primary}
              assetType={assetType}
              responseScale={data.response_scale}
              includePartial={regBody.include_partial}
            />

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div title={CV_TITLE}>
                <p className="text-slate-500">CV-MAPE</p>
                <p className="font-medium tabular-nums">{pct(data.cv_mape)}</p>
              </div>
              <div title="마지막 계약연도를 떼어 확인한 오차입니다.">
                <p className="text-slate-500">확인 CV</p>
                <p className="font-medium tabular-nums">{pct(data.confirm_cv_mape)}</p>
              </div>
            </div>
            <p className="text-[11px] leading-snug text-slate-500">{CV_TITLE}</p>
            <p className="text-xs text-slate-600 dark:text-slate-300">{data.explanatory_note}</p>

            {data.sides.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">
                  다른 표본 · 개별공시지가
                </p>
                <p className="text-[11px] leading-snug text-slate-500">
                  개별공시지가가 있는 거래만 쓴 식입니다. 행이 달라 위의 예측형 순위가 아닙니다.
                </p>
                {data.sides.map((side) => (
                  <div key={side.block_summary} className="space-y-1">
                    <p className="text-xs text-slate-600 dark:text-slate-300">
                      {side.block_summary} · {formatResponseScale(side.response_scale)} · 적합{" "}
                      {side.n}건
                      {side.coverage_ratio != null
                        ? ` · 조회 대비 ${(side.coverage_ratio * 100).toFixed(1)}%`
                        : ""}{" "}
                      · CV-MAPE {pct(side.cv_mape)}
                    </p>
                    <FocusRegressionCard
                      result={side.result}
                      assetType={assetType}
                      responseScale={side.response_scale}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </DraggableModalShell>
  );
}
