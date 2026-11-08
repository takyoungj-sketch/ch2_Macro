import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import MobileStatsShell, { MobileRollingDialog } from "@ch2/macro-shell/mobile/MobileStatsShell";
import MobileRegionSearch, { type MobileRegion } from "@ch2/macro-shell/mobile/MobileRegionSearch";
import { fetchFreeStats, fetchPaidMatrixYearly, fetchUpperStats } from "./api/client";
import { rollingMatrixModalPayload } from "./utils/freeStatsV2";
import { upperToFreeStatsShape } from "./utils/upperTierStats";
import MatrixYearlyTrendChart from "./components/MatrixYearlyTrendChart";
import MatrixStatsTable from "./components/MatrixStatsTable";
import "./mobileLandMatrix.css";
import type { FreeStatsV2Response, MatrixYearlyRequest } from "./types";

const price = (value: number | null | undefined) => value == null ? "—" : value.toLocaleString("ko-KR", { maximumFractionDigits: 1 });

export default function MobileLandApp() {
  const [region, setRegion] = useState<MobileRegion | null>(null);
  const [cell, setCell] = useState<{ zone: string; category: string } | null>(null);
  const stats = useQuery<FreeStatsV2Response>({
    queryKey: ["mobile-land-basic", region?.level, region?.code],
    enabled: region != null,
    queryFn: async () => region!.level === "beopjungri"
      ? fetchFreeStats(region!.code, { window_years: 5, matrix_mode: "category" })
      : upperToFreeStatsShape(await fetchUpperStats(region!.level, region!.code, { window_years: 5, matrix_mode: "category" })),
  });
  const request: MatrixYearlyRequest | null = region && cell && stats.data ? {
    region_selections: [{ scope_type: region.level, code: region.code }],
    region_codes: null, ...rollingMatrixModalPayload(stats.data),
    zone_type: cell.zone, land_category: cell.category, matrix_mode: "category",
    road_conditions: null, area_categories: null, area_sqm_min: null, area_sqm_max: null,
    land_categories: null, zone_types: null, exclude_partial: false, exclude_outlier: false,
    outlier_iqr_multiplier: 3,
  } : null;
  const rolling = useQuery({
    queryKey: ["mobile-land-rolling", request], enabled: request != null,
    queryFn: () => fetchPaidMatrixYearly(request!),
  });
  return <MobileStatsShell product="land" search={<MobileRegionSearch token={import.meta.env.VITE_API_TOKEN} selected={region} onSelect={next => { setCell(null); setRegion(next); }} />}>
    {!region && <p className="ch2-field-note">지역을 선택하면 용도×지목 기본통계가 표시됩니다.</p>}
    {region && stats.isPending && <p role="status">기본통계 불러오는 중…</p>}
    {stats.isError && <p role="alert">통계를 불러오지 못했습니다. <button onClick={() => stats.refetch()}>다시 시도</button></p>}
    {stats.data && <section className="ch2-mobile-land-matrix" aria-label="토지 용도×지목 기본통계">
      <p className="ch2-field-note">{stats.data.period_start} ~ {stats.data.period_end} · {stats.data.total.count.toLocaleString()}건 · 만원/㎡</p>
      <p className="ch2-field-note">좌우로 밀어 지목을 확인하고, 수치를 누르면 5년 롤링창이 열립니다.</p>
      <MatrixStatsTable basicOnly matrix={stats.data.matrix} byZone={stats.data.by_zone} byLandCategory={stats.data.by_land_category}
        onPaidMatrixCellClick={(zone, category) => setCell({ zone, category })} />
      {stats.data.total.count === 0 && <p>선택한 지역에 해당 기간의 거래가 없습니다.</p>}
    </section>}
    {cell && <MobileRollingDialog title={`${cell.zone} · ${cell.category}`} subtitle="5년 롤링 · 평균 만원/㎡ · 거래 건수" onClose={() => setCell(null)}>
      {rolling.isPending && <p role="status">롤링 추이 불러오는 중…</p>}
      {rolling.isError && <p role="alert">롤링 추이를 불러오지 못했습니다. <button onClick={() => rolling.refetch()}>다시 시도</button></p>}
      {rolling.data && <><MatrixYearlyTrendChart rows={rolling.data.rows} />
        <table className="ch2-field-table" aria-label="토지 롤링 구간 수치"><thead><tr><th>기간</th><th>거래수</th><th>평균</th></tr></thead><tbody>{rolling.data.rows.map((r, i) => <tr key={i}><th>{r.chart_label || `${r.period_start} ~ ${r.period_end}`}</th><td>{r.count}</td><td>{price(r.mean_unit_price_per_sqm)}</td></tr>)}</tbody></table>
      </>}
    </MobileRollingDialog>}
  </MobileStatsShell>;
}
