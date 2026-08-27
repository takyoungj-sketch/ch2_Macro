import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  fetchParcelDetail,
  fetchParcelStatus,
  searchParcels,
  type ParcelDetail,
  type ParcelListRow,
} from "../api/parcelClient";
import { readQaToken, writeQaToken } from "../api/qaClient";

function fmt(n: number | null | undefined) {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("ko-KR");
}

function initialQaToken() {
  const t = readQaToken();
  if (/[가-힣]/.test(t)) {
    writeQaToken("");
    return "";
  }
  return t;
}

function statusErrorMessage(err: unknown) {
  const ax = err as { response?: { status?: number; data?: { detail?: string } } };
  if (ax.response?.status === 404) {
    return "대장 조회 API가 아직 서버에 없습니다. 로컬 API(8000)를 한 번 재시작해 주세요.";
  }
  if (ax.response?.status === 401) {
    return "관리 토큰이 틀렸습니다. 로컬에서는 아래 토큰 칸을 비워 두세요. 단지명은 찾기 칸에 넣습니다.";
  }
  return ax.response?.data?.detail ?? "대장DB 현황을 읽지 못했습니다.";
}

export default function ParcelLabPanel() {
  const [token, setToken] = useState(initialQaToken);
  const [sido, setSido] = useState("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 50;
  const [picked, setPicked] = useState<string | null>(null);

  const statusQ = useQuery({
    queryKey: ["parcel-lab-status"],
    queryFn: fetchParcelStatus,
  });

  const searchM = useMutation({
    mutationFn: (args: { off: number; sido?: string; q?: string }) => {
      const s = args.sido !== undefined ? args.sido : sido;
      const query = args.q !== undefined ? args.q : q;
      return searchParcels({
        q: query.trim() || undefined,
        sido: s || undefined,
        offset: args.off,
        limit,
      });
    },
  });

  const detailQ = useQuery({
    queryKey: ["parcel-lab-detail", picked],
    queryFn: () => fetchParcelDetail(picked!),
    enabled: Boolean(picked),
  });

  const status = statusQ.data;
  const search = searchM.data;
  const sidos = status?.sidos ?? [];

  const summaryBits = useMemo(() => {
    if (!status?.available) return [];
    const kind = (status.kinds ?? []).map((k) => `${k.kind} ${fmt(k.n)}`).join(" · ");
    return [
      `동 ${fmt(status.n_building)}`,
      `필지 ${fmt(status.n_parcel)}`,
      `용도지역 라벨 ${fmt(status.n_zone)} (필지 ${fmt(status.n_zone_pnu)})`,
      kind,
    ];
  }, [status]);

  return (
    <div className="max-w-[96rem] mx-auto px-4 py-4 space-y-4">
      <p className="text-xs text-slate-500 leading-relaxed">
        로컬 대장DB만 봅니다. 읽기 전용입니다. 운영 서버에는 이 DB가 없고, 없으면 아래처럼 안내합니다.
        토지만 있는 필지와 표제부 「일반」은 아직 없습니다.
      </p>

      {statusQ.isError && (
        <p className="text-sm text-red-600">{statusErrorMessage(statusQ.error)}</p>
      )}

      {status && !status.available && (
        <div className="card p-4 text-sm text-amber-900 dark:text-amber-100 bg-amber-50 dark:bg-amber-950/40">
          {status.detail}
        </div>
      )}

      {status?.available && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {summaryBits.slice(0, 3).map((b) => (
              <div key={b} className="card p-3">
                <div className="text-sm font-medium">{b}</div>
              </div>
            ))}
            <div className="card p-3">
              <div className="text-[10px] text-slate-500">스냅샷</div>
              <div className="text-sm">
                {(status.snapshots ?? []).map((s) => `${s.snapshot} ${fmt(s.n)}`).join(" · ") || "—"}
              </div>
            </div>
          </div>
          {status.note && <p className="text-[11px] text-slate-500">{status.note}</p>}

          <div className="card overflow-auto max-h-48">
            <table className="data w-full text-[11px]">
              <thead>
                <tr>
                  <th>시도</th>
                  <th>필지</th>
                  <th>동×스냅샷</th>
                </tr>
              </thead>
              <tbody>
                {sidos.map((s) => (
                  <tr
                    key={s.sido_code}
                    className={clsx(sido === s.sido_code && "bg-amber-50 dark:bg-amber-950/30")}
                  >
                    <td>
                      <button
                        type="button"
                        className="underline-offset-2 hover:underline"
                        onClick={() => {
                          setSido(s.sido_code);
                          setOffset(0);
                          setPicked(null);
                          searchM.mutate({ off: 0, sido: s.sido_code });
                        }}
                      >
                        {s.sido_code} {s.label}
                      </button>
                    </td>
                    <td className="num">{fmt(s.n_parcel)}</td>
                    <td className="num">{fmt(s.n_building)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {status?.available && (
        <div className="card p-4 space-y-3">
          <p className="text-xs font-semibold">찾기</p>
          <div className="flex flex-wrap gap-2 items-end">
            <label className="text-xs text-slate-500">
              시도
              <select
                className="mt-1 block rounded border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-900"
                value={sido}
                onChange={(e) => setSido(e.target.value)}
              >
                <option value="">전체</option>
                {sidos.map((s) => (
                  <option key={s.sido_code} value={s.sido_code}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-slate-500 flex-1 min-w-[16rem]">
              PNU · 법정동 10자리 · 건물명
              <input
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-900"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    setOffset(0);
                    setPicked(null);
                    searchM.mutate({ off: 0 });
                  }
                }}
                placeholder="예: 단지명 또는 19자리 PNU"
              />
            </label>
            <button
              type="button"
              className="btn btn-primary"
              disabled={searchM.isPending}
              onClick={() => {
                setOffset(0);
                setPicked(null);
                searchM.mutate({ off: 0 });
              }}
            >
              {searchM.isPending ? "찾는 중…" : "검색"}
            </button>
          </div>
          {searchM.isError && (
            <p className="text-sm text-red-600">
              {(searchM.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
                "검색에 실패했습니다."}
            </p>
          )}
          {search?.note && <p className="text-xs text-slate-500">{search.note}</p>}
        </div>
      )}

      {search && search.items.length > 0 && (
        <ParcelTable
          rows={search.items}
          picked={picked}
          n={search.n}
          offset={offset}
          limit={limit}
          truncated={search.truncated}
          onPick={(pnu) => setPicked(pnu)}
          onPage={(off) => {
            setOffset(off);
            setPicked(null);
            searchM.mutate({ off });
          }}
        />
      )}

      {picked && (
        <DetailBlock
          pnu={picked}
          data={detailQ.data}
          loading={detailQ.isPending}
          error={
            detailQ.isError
              ? ((detailQ.error as { response?: { data?: { detail?: string } } })?.response?.data
                  ?.detail ?? "상세를 읽지 못했습니다.")
              : null
          }
        />
      )}

      <details className="text-xs text-slate-500">
        <summary className="cursor-pointer">관리 토큰 (로컬은 비움)</summary>
        <label className="block mt-2 max-w-sm">
          검증로봇과 같습니다. 단지명·주소는 여기에 넣지 마세요.
          <input
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-900"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            onBlur={() => {
              writeQaToken(token);
              void statusQ.refetch();
            }}
            placeholder="비워 두세요"
            autoComplete="off"
          />
        </label>
      </details>
    </div>
  );
}

function ParcelTable({
  rows,
  picked,
  n,
  offset,
  limit,
  truncated,
  onPick,
  onPage,
}: {
  rows: ParcelListRow[];
  picked: string | null;
  n: number;
  offset: number;
  limit: number;
  truncated: boolean;
  onPick: (pnu: string) => void;
  onPage: (offset: number) => void;
}) {
  return (
    <div className="card overflow-auto">
      <div className="px-3 py-2 text-[11px] text-slate-500 flex justify-between gap-2">
        <span>
          {n.toLocaleString("ko-KR")}필지
          {truncated ? " · 상한 안에서만 표시" : ""}
        </span>
        <span className="flex gap-2">
          <button type="button" className="btn btn-ghost text-[11px]" disabled={offset <= 0} onClick={() => onPage(Math.max(0, offset - limit))}>
            이전
          </button>
          <button
            type="button"
            className="btn btn-ghost text-[11px]"
            disabled={offset + rows.length >= n}
            onClick={() => onPage(offset + limit)}
          >
            다음
          </button>
        </span>
      </div>
      <table className="data w-full text-[11px]">
        <thead>
          <tr>
            <th>PNU</th>
            <th>시도</th>
            <th>지번</th>
            <th>건물명</th>
            <th>동수</th>
            <th>면적㎡</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.pnu}
              className={clsx("cursor-pointer", picked === r.pnu && "bg-indigo-50 dark:bg-indigo-950/40")}
              onClick={() => onPick(r.pnu)}
            >
              <td className="font-mono">{r.pnu}</td>
              <td>{r.sido_label}</td>
              <td>{r.lot}</td>
              <td className="text-left">{r.building_name || "—"}</td>
              <td className="num">{fmt(r.n_buildings)}</td>
              <td className="num">{r.land_area == null ? "—" : fmt(Math.round(r.land_area))}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DetailBlock({
  pnu,
  data,
  loading,
  error,
}: {
  pnu: string;
  data?: ParcelDetail;
  loading: boolean;
  error: string | null;
}) {
  if (loading) return <p className="text-xs text-slate-500">상세 읽는 중… {pnu}</p>;
  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!data) return null;
  const p = data.parcel;
  return (
    <div className="space-y-3">
      <div className="card p-3 text-sm space-y-1">
        <p className="font-semibold">
          {p.sido_label} · 지번 {p.lot} · PNU {p.pnu}
        </p>
        <p className="text-[11px] text-slate-500">
          법정동 {p.beopjungri_code} · 동 키 {fmt(p.n_buildings)} · 면적{" "}
          {p.land_area == null ? "—" : `${fmt(Math.round(p.land_area))}㎡`} ({p.land_area_source || "—"})
          · 지목 {p.jimok_code || "—"} · 스냅샷 {p.first_seen}–{p.last_seen}
        </p>
      </div>

      <div className="card overflow-auto">
        <div className="px-3 py-2 text-xs font-semibold">
          동 {data.buildings.length.toLocaleString("ko-KR")}
          {data.buildings_capped ? " · 상한" : ""}
        </div>
        <table className="data w-full text-[11px]">
          <thead>
            <tr>
              <th>스냅샷</th>
              <th>구분</th>
              <th>건물명</th>
              <th>동</th>
              <th>주용도</th>
              <th>세대</th>
              <th>호수</th>
              <th>주차</th>
              <th>층</th>
              <th>구조</th>
              <th>승인</th>
            </tr>
          </thead>
          <tbody>
            {data.buildings.map((b) => (
              <tr key={`${b.mgmt_pk}|${b.snapshot}`}>
                <td>{b.snapshot}</td>
                <td>{b.ledger_kind}</td>
                <td className="text-left">{b.building_name || "—"}</td>
                <td>{b.dong_name || "—"}</td>
                <td className="text-left">
                  {b.main_purpose || "—"}
                  {b.purpose_detail ? ` · ${b.purpose_detail}` : ""}
                </td>
                <td className="num">{fmt(b.households)}</td>
                <td className="num">{fmt(b.ho_cnt)}</td>
                <td className="num">{fmt(b.parking_total)}</td>
                <td className="num">
                  {b.floors_above != null ? `${b.floors_above}` : "—"}
                  {b.floors_below ? `/${b.floors_below}` : ""}
                </td>
                <td>{b.structure_group || b.structure_name || "—"}</td>
                <td>{b.approve_date || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card overflow-auto">
        <div className="px-3 py-2 text-xs font-semibold">용도지역 {data.zones.length.toLocaleString("ko-KR")}</div>
        {data.zones.length === 0 ? (
          <p className="px-3 pb-3 text-[11px] text-slate-500">이 필지에 붙인 용도지역 라벨이 없습니다.</p>
        ) : (
          <table className="data w-full text-[11px]">
            <thead>
              <tr>
                <th>라벨</th>
                <th>계열</th>
                <th>대분류</th>
                <th>출처</th>
              </tr>
            </thead>
            <tbody>
              {data.zones.map((z) => (
                <tr key={z.zone_label}>
                  <td className="text-left">{z.zone_label}</td>
                  <td>{z.zone_family || "—"}</td>
                  <td>{z.is_coarse ? "대분류" : "세부"}</td>
                  <td>{z.source || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
