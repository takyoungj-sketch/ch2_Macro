import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import {
  fetchProfileTwinSigungu,
  fetchTwinNeighborsForEupmyeondong,
  fetchTwinV8Neighbors,
} from "../api/client";
import type { TwinCitySearchTarget, TwinV8Query } from "../types";
import { parseApiError } from "../utils/apiError";
import { isChungcheongSido } from "../utils/twinRegionAnchor";

interface Props {
  open: boolean;
  onClose: () => void;
  /** null 이면 닫힘과 동일 — open 과 함께 씀 */
  target: TwinCitySearchTarget | null;
  /** Twin v8 조회 앵커 — 기존 MVP/하이브리드와 별도 */
  v8Query: TwinV8Query | null;
}

/** 유료 필터 표 — 읍면동(인접 시도) 또는 시군구(전국) 쌍둥이 후보 + Twin v8(충청권) */
export default function TwinCityModal({ open, onClose, target, v8Query }: Props) {
  const eupEnabled = Boolean(open && target?.kind === "eupmyeondong");
  const eupCode = target?.kind === "eupmyeondong" ? target.anchor.eupmyeondong_code : "";

  const sgEnabled = Boolean(open && target?.kind === "sigungu");
  const sgCode = target?.kind === "sigungu" ? target.anchor.sigungu_code : "";

  const v8Enabled = Boolean(
    open && v8Query != null && isChungcheongSido(v8Query.sido_code),
  );

  const eupQ = useQuery({
    queryKey: ["twinNeighborsEup", eupCode],
    queryFn: () => fetchTwinNeighborsForEupmyeondong(eupCode),
    enabled: eupEnabled,
    staleTime: 5 * 60 * 1000,
    retry: twinRetryPolicy,
  });

  const sgQ = useQuery({
    queryKey: ["twinSigunguHybrid", sgCode],
    queryFn: () => fetchProfileTwinSigungu({ sigungu_code: sgCode, top_k: 10 }),
    enabled: sgEnabled,
    staleTime: 5 * 60 * 1000,
    retry: twinRetryPolicy,
  });

  const v8Q = useQuery({
    queryKey: ["twinV8Neighbors", v8Query?.region_level, v8Query?.region_code],
    queryFn: () =>
      fetchTwinV8Neighbors({
        region_level: v8Query!.region_level,
        region_code: v8Query!.region_code,
        top_k: 10,
      }),
    enabled: v8Enabled,
    staleTime: 5 * 60 * 1000,
    retry: twinRetryPolicy,
  });

  const isLoading =
    target?.kind === "eupmyeondong"
      ? eupQ.isLoading
      : target?.kind === "sigungu"
        ? sgQ.isLoading
        : false;
  const isError =
    target?.kind === "eupmyeondong"
      ? eupQ.isError
      : target?.kind === "sigungu"
        ? sgQ.isError
        : false;
  const error = target?.kind === "eupmyeondong" ? eupQ.error : sgQ.error;
  const refetch =
    target?.kind === "eupmyeondong"
      ? eupQ.refetch
      : target?.kind === "sigungu"
        ? sgQ.refetch
        : async () => ({});

  const eupData = eupQ.data;
  const sgData = sgQ.data;

  if (!open || !target) return null;

  const v8OutOfScope = v8Query != null && !isChungcheongSido(v8Query.sido_code);

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/35"
      role="dialog"
      aria-modal="true"
      aria-labelledby="twin-city-modal-title"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white rounded-xl shadow-xl max-w-xl w-full max-h-[88vh] flex flex-col border border-slate-200">
        <div className="flex justify-between items-start gap-2 px-4 py-3 border-b border-slate-100">
          <div className="min-w-0">
            <h2 id="twin-city-modal-title" className="text-sm font-bold text-slate-800">
              쌍둥이 도시 찾기
            </h2>
            {target.kind === "eupmyeondong" ? (
              <p className="text-[11px] text-slate-500 mt-1 leading-snug">
                기준 읍면동 ·{" "}
                <span className="font-medium text-slate-700">{target.anchor.eupmyeondong_name}</span> (
                {target.anchor.eupmyeondong_code}) — {target.anchor.sigungu_name} / {target.anchor.sido_name}
              </p>
            ) : (
              <p className="text-[11px] text-slate-500 mt-1 leading-snug">
                기준 시군구 ·{" "}
                <span className="font-medium text-slate-700">{target.anchor.sigungu_name}</span> (
                {target.anchor.sigungu_code}) — {target.anchor.sido_name}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 text-slate-400 hover:text-slate-700 text-xl leading-none px-1"
            aria-label="닫기"
          >
            ×
          </button>
        </div>

        <div className="px-4 py-3 overflow-y-auto text-[12px] text-slate-700 space-y-4">
          <section aria-labelledby="twin-legacy-heading" className="space-y-3">
            <h3
              id="twin-legacy-heading"
              className="text-[11px] font-semibold uppercase tracking-wide text-slate-500"
            >
              기존 알고리즘 (MVP / Hybrid)
            </h3>

            {target.kind === "eupmyeondong" ? (
              <p className="text-[11px] text-slate-500 leading-relaxed">
                거래 패턴 기반 MVP입니다. 용도×지목 비중(코사인), ±40% 인구 허들, 단가 보조항을 사용하고,
                후보 읍면동은{" "}
                <span className="font-medium text-slate-700">같은 시도·육상 인접 시도</span> 안에서만 고릅니다.
                {eupData?.batch_key ? (
                  <span className="block text-[10px] text-slate-400 mt-1 truncate" title={eupData.batch_key}>
                    배치 {eupData.batch_key}
                  </span>
                ) : null}
              </p>
            ) : (
              <p className="text-[11px] text-slate-500 leading-relaxed">
                선택 범위가 <span className="font-medium text-slate-700">하나의 시군구</span>
                에만 속할 때는 읍면동 단위 대신{" "}
                <span className="font-medium text-slate-700">전국 시군구</span> 하이브리드 유사도를
                표시합니다(토지+집합거래+프로파일).
                {sgData?.batch_key ? (
                  <span className="block text-[10px] text-slate-400 mt-1 truncate" title={sgData.batch_key}>
                    배치 {sgData.batch_key}
                  </span>
                ) : null}
              </p>
            )}

            {isLoading ? (
              <p className="text-slate-400 text-center py-4">불러오는 중…</p>
            ) : isError ? (
              <div className="space-y-2">
                <p className="text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-2 py-1.5">
                  {parseApiError(error).message}
                </p>
                <button
                  type="button"
                  onClick={() => void refetch()}
                  className="text-[11px] text-blue-600 underline underline-offset-2"
                >
                  다시 시도
                </button>
              </div>
            ) : target.kind === "eupmyeondong" && (eupData?.neighbors.length ?? 0) === 0 ? (
              <p className="text-slate-500">후보가 없습니다.</p>
            ) : target.kind === "sigungu" && (sgData?.neighbors.length ?? 0) === 0 ? (
              <p className="text-slate-500">후보가 없습니다.</p>
            ) : target.kind === "eupmyeondong" ? (
              <ol className="space-y-2 list-decimal list-inside text-[12px]">
                {(eupData?.neighbors ?? []).map((n) => (
                  <li key={n.twin_eupmyeondong_code} className="leading-snug pl-1">
                    <span className="font-medium">
                      [{n.rank}] {n.twin_eupmyeondong_name}
                    </span>
                    <span className="text-slate-500">
                      （{n.twin_sigungu_name}, {n.twin_sido_name} · {n.twin_eupmyeondong_code}）
                    </span>
                    <span className="text-slate-400 tabular-nums ml-1">
                      · 유사도 {n.similarity_score.toFixed(4)}
                    </span>
                  </li>
                ))}
              </ol>
            ) : (
              <ol className="space-y-2 list-decimal list-inside text-[12px]">
                {(sgData?.neighbors ?? []).map((n) => (
                  <li key={n.twin_sigungu_code} className="leading-snug pl-1">
                    <span className="font-medium">
                      [{n.rank}] {n.twin_sigungu_name}
                    </span>
                    <span className="text-slate-500">
                      （{n.twin_sido_name} · {n.twin_sigungu_code}）
                    </span>
                    {typeof n.detail_scores.twin_region === "string" ? (
                      <span className="text-[10px] text-violet-600 ml-1">
                        {n.detail_scores.twin_region as string}
                      </span>
                    ) : null}
                    <span className="text-slate-400 tabular-nums ml-1">
                      · 유사도 {n.similarity_score.toFixed(4)}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <TwinV8Section
            v8Query={v8Query}
            outOfScope={v8OutOfScope}
            isLoading={v8Q.isLoading}
            isError={v8Q.isError}
            error={v8Q.error}
            refetch={v8Q.refetch}
            data={v8Q.data}
          />
        </div>

        <div className="px-4 py-2 border-t border-slate-100 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="text-xs font-medium px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}

function TwinV8Section({
  v8Query,
  outOfScope,
  isLoading,
  isError,
  error,
  refetch,
  data,
}: {
  v8Query: TwinV8Query | null;
  outOfScope: boolean;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => Promise<unknown>;
  data: Awaited<ReturnType<typeof fetchTwinV8Neighbors>> | undefined;
}) {
  const levelLabel =
    v8Query?.region_level === "beopjungri"
      ? "법정리"
      : v8Query?.region_level === "eupmyeondong"
        ? "읍면동"
        : "시군구";

  return (
    <section
      aria-labelledby="twin-v8-heading"
      className="border-t border-slate-200 pt-4 space-y-3"
    >
      <div>
        <h3
          id="twin-v8-heading"
          className="text-[11px] font-semibold uppercase tracking-wide text-teal-700"
        >
          Twin v8 (충청권)
        </h3>
        {v8Query ? (
          <p className="text-[11px] text-slate-500 mt-1 leading-snug">
            기준 {levelLabel} ·{" "}
            <span className="font-medium text-slate-700">{v8Query.region_name}</span> (
            {v8Query.region_code}) — {v8Query.sigungu_name} / {v8Query.sido_name}
          </p>
        ) : (
          <p className="text-[11px] text-slate-500 mt-1">
            단일 시군구·읍면동·리로 범위를 좁히면 v8 결과를 함께 표시합니다.
          </p>
        )}
      </div>

      <p className="text-[11px] text-slate-500 leading-relaxed">
        토지 구조·단가(Top-N Jaccard + 교집합 셀 유사도) 60점, 집합상가·아파트 분포 40점.
        인구는 0.6~1.7× 필터만 적용합니다. 리 단위는 동일 시군구 안에서만 후보를 비교합니다.
        {data?.batch_key ? (
          <span className="block text-[10px] text-slate-400 mt-1 truncate" title={data.batch_key}>
            배치 {data.batch_key}
            {data.scope_label ? ` · ${data.scope_label}` : null}
          </span>
        ) : null}
      </p>

      {outOfScope ? (
        <p className="text-slate-500 bg-slate-50 border border-slate-200 rounded-md px-2 py-1.5">
          Twin v8은 현재 충청권(세종·대전·충북·충남)만 지원합니다. 선택 지역은 {v8Query?.sido_name}
          입니다.
        </p>
      ) : v8Query == null ? null : isLoading ? (
        <p className="text-slate-400 text-center py-3">v8 불러오는 중…</p>
      ) : isError ? (
        <div className="space-y-2">
          <p className="text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-2 py-1.5">
            {parseApiError(error).message}
          </p>
          <button
            type="button"
            onClick={() => void refetch()}
            className="text-[11px] text-blue-600 underline underline-offset-2"
          >
            다시 시도
          </button>
        </div>
      ) : (data?.neighbors.length ?? 0) === 0 ? (
        <p className="text-slate-500">v8 후보가 없습니다.</p>
      ) : (
        <ol className="space-y-3 list-none text-[12px]">
          {(data?.neighbors ?? []).map((n) => (
            <li
              key={n.twin_region_code}
              className="rounded-lg border border-teal-100 bg-teal-50/40 px-2.5 py-2 leading-snug"
            >
              <div className="flex flex-wrap items-baseline gap-x-1 gap-y-0.5">
                <span className="font-semibold text-slate-800">
                  [{n.rank}] {n.twin_region_name}
                </span>
                <span className="text-slate-500">
                  （
                  {n.twin_sigungu_name ? `${n.twin_sigungu_name}, ` : ""}
                  {n.twin_sido_name} · {n.twin_region_code}）
                </span>
              </div>
              <div className="text-[11px] tabular-nums text-slate-600 mt-0.5">
                Twin Score {n.similarity_score.toFixed(1)} · Confidence {n.confidence_score.toFixed(0)}
              </div>
              {n.explanation_ko ? (
                <p className="text-[11px] text-slate-600 mt-1 leading-relaxed">{n.explanation_ko}</p>
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function twinRetryPolicy(failureCount: number, err: unknown): boolean {
  if (axios.isAxiosError(err)) {
    const s = err.response?.status;
    if (s === 404 || s === 422) return false;
  }
  return failureCount < 2;
}
