import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { fetchProfileTwinSigungu, fetchTwinNeighborsForEupmyeondong } from "../api/client";
import type { TwinCitySearchTarget } from "../types";
import { parseApiError } from "../utils/apiError";

interface Props {
  open: boolean;
  onClose: () => void;
  /** null 이면 닫힘과 동일 — open 과 함께 씀 */
  target: TwinCitySearchTarget | null;
}

/** 유료 필터 표 — 읍면동(인접 시도) 또는 시군구(전국) 쌍둥이 후보 */
export default function TwinCityModal({ open, onClose, target }: Props) {
  const eupEnabled = Boolean(open && target?.kind === "eupmyeondong");
  const eupCode = target?.kind === "eupmyeondong" ? target.anchor.eupmyeondong_code : "";

  const sgEnabled = Boolean(open && target?.kind === "sigungu");
  const sgCode = target?.kind === "sigungu" ? target.anchor.sigungu_code : "";

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
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[82vh] flex flex-col border border-slate-200">
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

        <div className="px-4 py-3 overflow-y-auto text-[12px] text-slate-700 space-y-3">
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

function twinRetryPolicy(failureCount: number, err: unknown): boolean {
  if (axios.isAxiosError(err)) {
    const s = err.response?.status;
    if (s === 404 || s === 422) return false;
  }
  return failureCount < 2;
}
