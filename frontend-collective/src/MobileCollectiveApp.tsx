import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import MobileStatsShell, { MobileRollingDialog } from "@ch2/macro-shell/mobile/MobileStatsShell";
import MobileRegionSearch, { type MobileRegion } from "@ch2/macro-shell/mobile/MobileRegionSearch";
import { fetchAllBuildings, fetchBuildingRollingStats, type BuildingStatsRow } from "./api/client";
import { fetchAllCommercialClusters, fetchCommercialRollingStats } from "./api/commercialClient";
import type { AssetSelectorType, CommercialAssetSelectorType, CommercialClusterRow, RollingStatsResponse, CommercialRollingStatsResponse } from "./types";
import RollingTrendChart from "./components/RollingTrendChart";

const price = (value: number | null | undefined) => value == null ? "—" : value.toLocaleString("ko-KR", { maximumFractionDigits: 1 });
type Row = BuildingStatsRow | CommercialClusterRow;
const name = (row: Row) => "building_key" in row ? row.display_name : row.road_name || row.display_label;
const key = (row: Row) => "building_key" in row ? row.building_key : row.cluster_key;

export default function MobileCollectiveApp({ commercial = false }: { commercial?: boolean }) {
  const [region, setRegion] = useState<MobileRegion | null>(null);
  const [asset, setAsset] = useState("all");
  const [selected, setSelected] = useState<Row | null>(null);
  const params = region ? {
    addr1: region.sido,
    addr2: region.sigungu.split(/\s+/)[0] || region.sido,
    // Canonical code scope avoids the asynchronous PC chip/resolver state entirely.
    ...(region.level === "sigungu" ? {
      addr3_list: region.sigungu.split(/\s+/).slice(1),
    } : {
      region_codes: [region.code], region_code_level: region.level,
      region_addrs: [`${region.sido}|${region.sigungu}|${region.level === "beopjungri" ? region.ri : region.eup}`],
    }), window_years: 5, sort: "count",
  } : null;
  const stats = useQuery({
    queryKey: ["mobile-collective-basic", commercial, region, asset], enabled: params != null,
    queryFn: async () => commercial
      ? fetchAllCommercialClusters({ ...params!, asset_type: asset as CommercialAssetSelectorType })
      : fetchAllBuildings({ ...params!, asset_type: asset as AssetSelectorType, presale_stats_mode: "rolling" }),
  });
  const rolling = useQuery<RollingStatsResponse | CommercialRollingStatsResponse>({
    queryKey: ["mobile-collective-rolling", commercial, selected && key(selected)], enabled: selected != null,
    queryFn: () => commercial ? fetchCommercialRollingStats(key(selected!), 5) : fetchBuildingRollingStats(key(selected!), 5),
  });
  const types = commercial ? [["all", "전체"], ["collective_shop", "집합상가"], ["collective_factory", "집합공장"]] : [["all", "전체"], ["apartment", "아파트"], ["officetel", "오피스텔"], ["rowhouse", "연립다세대"], ["presale", "분양권"]];
  return <MobileStatsShell product={commercial ? "commercial" : "residential"} search={<MobileRegionSearch token={import.meta.env.VITE_API_TOKEN} selected={region} onSelect={next => { setSelected(null); setRegion(next); }} />}>
    <div className="ch2-field-type" aria-label="부동산 유형">{types.map(([value, label]) => <button key={value} aria-pressed={asset === value} onClick={() => { setAsset(value!); setSelected(null); }}>{label}</button>)}</div>
    {!region && <p className="ch2-field-note">지역을 선택하면 {commercial ? "도로명별" : "단지·건물별"} 기본통계가 표시됩니다.</p>}
    {region && stats.isPending && <p role="status">기본통계 불러오는 중…</p>}
    {stats.isError && <p role="alert">통계를 불러오지 못했습니다. <button onClick={() => stats.refetch()}>다시 시도</button></p>}
    {stats.data && <>
      <p className="ch2-field-note">{stats.data.period_start} ~ {stats.data.period_end} · {stats.data.total.toLocaleString()}곳 · 만원/㎡<br />이름을 누르면 5년 롤링 추이를 볼 수 있습니다.</p>
      <table className="ch2-field-table" aria-label={`${commercial ? "도로명별" : "단지별"} 기본통계`}><thead><tr><th>{commercial ? "도로명" : "단지·건물"}</th><th>거래수</th><th>중앙값</th><th>평균</th></tr></thead><tbody>{stats.data.items.map(row => <tr key={`${key(row)}:${row.asset_type}`}>
        <th className="ch2-field-name" scope="row"><button onClick={() => setSelected(row)}>{name(row)}</button></th><td>{row.count.toLocaleString()}</td><td>{price(row.median)}</td><td>{price(row.mean)}</td>
      </tr>)}</tbody></table>
      {stats.data.items.length === 0 && <p>선택한 지역·유형에 해당 기간의 거래가 없습니다.</p>}
    </>}
    {selected && <MobileRollingDialog title={name(selected)} onClose={() => setSelected(null)}>
      {rolling.isPending && <p role="status">롤링 추이 불러오는 중…</p>}
      {rolling.isError && <p role="alert">롤링 추이를 불러오지 못했습니다. <button onClick={() => rolling.refetch()}>다시 시도</button></p>}
      {rolling.data && <><RollingTrendChart points={rolling.data.points} />
        <table className="ch2-field-table" aria-label="집합 롤링 구간 수치"><thead><tr><th>기간</th><th>거래수</th><th>평균</th></tr></thead><tbody>{rolling.data.points.map(p => <tr key={p.bucket_index}><th>{p.label}</th><td>{p.count}</td><td>{price(p.mean)}</td></tr>)}</tbody></table>
      </>}
    </MobileRollingDialog>}
  </MobileStatsShell>;
}
