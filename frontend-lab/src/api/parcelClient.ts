import axios from "axios";
import { readQaToken } from "./qaClient";

function parcelApi() {
  const token = readQaToken();
  return axios.create({
    baseURL: "/api/admin/parcel",
    timeout: 60_000,
    headers: token ? { "X-Qa-Audit-Token": token } : undefined,
  });
}

export type ParcelKindCount = { kind: string; n: number };
export type ParcelSnapCount = { snapshot: string; n: number };
export type ParcelSidoCount = {
  sido_code: string;
  label: string;
  n_parcel: number;
  n_building: number;
};

export type ParcelStatus = {
  available: boolean;
  detail?: string;
  n_building?: number;
  n_parcel?: number;
  n_zone?: number;
  n_zone_pnu?: number;
  n_zone_fine?: number;
  kinds?: ParcelKindCount[];
  snapshots?: ParcelSnapCount[];
  sidos?: ParcelSidoCount[];
  note?: string | null;
};

export type ParcelListRow = {
  pnu: string;
  sido_code?: string | null;
  sido_label?: string;
  beopjungri_code?: string | null;
  lot?: string;
  n_buildings?: number | null;
  land_area?: number | null;
  jimok_code?: string | null;
  land_area_source?: string | null;
  first_seen?: string | null;
  last_seen?: string | null;
  building_name?: string | null;
};

export type ParcelSearchResponse = {
  items: ParcelListRow[];
  n: number;
  truncated: boolean;
  kind: string;
  note?: string | null;
};

export type ParcelBuildingRow = {
  mgmt_pk: string;
  snapshot: string;
  ledger_kind: string;
  building_name?: string | null;
  dong_name?: string | null;
  structure_name?: string | null;
  structure_group?: string | null;
  main_purpose?: string | null;
  purpose_detail?: string | null;
  households?: number | null;
  ho_cnt?: number | null;
  parking_total?: number | null;
  floors_above?: number | null;
  floors_below?: number | null;
  gross_area?: number | null;
  approve_date?: string | null;
};

export type ParcelZoneRow = {
  zone_label: string;
  zone_family?: string | null;
  is_coarse: boolean;
  source?: string | null;
  snapshot?: string | null;
};

export type ParcelDetail = {
  parcel: ParcelListRow & { sigungu_code?: string | null };
  buildings: ParcelBuildingRow[];
  zones: ParcelZoneRow[];
  buildings_capped: boolean;
};

export async function fetchParcelStatus(): Promise<ParcelStatus> {
  const { data } = await parcelApi().get<ParcelStatus>("/status");
  return data;
}

export async function searchParcels(params: {
  q?: string;
  sido?: string;
  offset?: number;
  limit?: number;
}): Promise<ParcelSearchResponse> {
  const { data } = await parcelApi().get<ParcelSearchResponse>("/search", { params });
  return data;
}

export async function fetchParcelDetail(pnu: string): Promise<ParcelDetail> {
  const { data } = await parcelApi().get<ParcelDetail>(`/parcels/${encodeURIComponent(pnu)}`);
  return data;
}
