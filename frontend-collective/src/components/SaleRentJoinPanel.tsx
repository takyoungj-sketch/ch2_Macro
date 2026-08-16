import { useQuery } from "@tanstack/react-query";
import { fetchSaleRentJoin } from "../api/rentJoinClient";
import type { AssetType } from "../types";
import type { StatsWindowYears } from "./StatsWindowToggle";

function fmt(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString("ko-KR", { maximumFractionDigits: 1 });
}

const REASON: Record<string, string> = {
  no_join: "이 건물 키로 맞는 임대 거래가 없습니다.",
  map_missing: "매매×임대 매핑이 없습니다. 빌더를 실행하세요.",
  no_rent_stats: "키는 맞지만 이 창의 임대 마트가 없습니다.",
  asset_not_in_scope: "분양권·비주거는 이 조인 대상이 아닙니다.",
};

export default function SaleRentJoinPanel({
  buildingKey,
  assetType,
  windowYears,
}: {
  buildingKey: string;
  assetType: AssetType;
  windowYears: StatsWindowYears;
}) {
  const q = useQuery({
    queryKey: ["sale-rent-join", buildingKey, assetType, windowYears],
    queryFn: () =>
      fetchSaleRentJoin({
        saleBuildingKey: buildingKey,
        assetType,
        windowYears,
      }),
    enabled: assetType !== "presale",
  });

  if (assetType === "presale") {
    return <p className="text-xs text-slate-500 text-center py-6">분양권은 임대 조인 대상이 아닙니다.</p>;
  }
  if (q.isLoading) {
    return <p className="text-xs text-slate-400 text-center py-6">임대 조인 불러오는 중…</p>;
  }
  if (q.isError) {
    return <p className="text-xs text-red-500 text-center py-6">임대 조인을 불러오지 못했습니다.</p>;
  }
  const data = q.data;
  if (!data?.joined) {
    return (
      <div className="px-3 py-6 text-center space-y-1">
        <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">조인 없음</p>
        <p className="text-xs text-slate-500">{REASON[data?.reason || ""] || "이 건물과 맞는 임대 통계가 없습니다."}</p>
      </div>
    );
  }
  const b = data.building;
  if (!b) {
    return <p className="text-xs text-slate-500 text-center py-6">조인 없음</p>;
  }
  const r = data.conversion?.r_selected;
  return (
    <div className="space-y-3 px-1">
      <p className="text-[11px] text-slate-500">
        같은 건물 키의 전월세입니다. 매매 원장과 합치지 않았습니다. 창 {data.window_years}년
        {data.conversion_fallback ? " · 전환율은 시군구 fallback" : ""}
        {data.conversion_applied && r != null ? ` · 적용 전환율 ${r.toFixed(1)}%` : " · 적용 전환율 없음"}
      </p>
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-[11px] text-slate-500 border-b border-slate-200 dark:border-slate-700">
            <th className="text-left py-1.5 font-medium">구분</th>
            <th className="text-right py-1.5 font-medium">P50</th>
            <th className="text-right py-1.5 font-medium">n</th>
          </tr>
        </thead>
        <tbody>
          <Row label="전세 보증금/㎡" m={b.jeonse} />
          <Row label="반전세 보증금/㎡" m={b.mixed.deposit} n={b.mixed.n} />
          <Row label="반전세 월세/㎡" m={b.mixed.monthly} n={b.mixed.n} />
          <Row label="월세/㎡" m={b.monthly} />
          <Row label="전세환산/㎡" m={b.jeonse_equiv} />
          <Row label="월세환산/㎡" m={b.monthly_equiv} />
        </tbody>
      </table>
      <p className="text-[10px] text-slate-400">
        환산은 비교용입니다. 그 건물 시세·수익률이 아닙니다.
      </p>
    </div>
  );
}

function Row({
  label,
  m,
  n,
}: {
  label: string;
  m: { n: number; median?: number | null };
  n?: number;
}) {
  return (
    <tr className="border-b border-slate-100 dark:border-slate-800">
      <td className="py-1.5 text-slate-600 dark:text-slate-300">{label}</td>
      <td className="py-1.5 text-right tabular-nums">{fmt(m.median)}</td>
      <td className="py-1.5 text-right tabular-nums text-slate-500">{(n ?? m.n).toLocaleString("ko-KR")}</td>
    </tr>
  );
}
