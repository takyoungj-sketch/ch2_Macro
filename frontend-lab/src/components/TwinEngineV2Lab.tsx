import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  fetchTwinsV2,
  searchRegions,
  type TwinV2Level,
  type TwinV2Neighbor,
  type TwinV2Response,
  type TwinV2Role,
} from "../api/twinV2Client";

const LEVELS: { id: TwinV2Level; label: string }[] = [
  { id: "sigungu", label: "시군구" },
  { id: "eupmyeondong", label: "읍면동" },
  { id: "beopjungri", label: "리" },
];

function pct100(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return String(Math.round(v * 100));
}

function neighborLabel(n: TwinV2Neighbor): string {
  const name = n.region_name || n.region_code;
  const where = [n.sido_name, n.sigungu_name].filter(Boolean).join(" ");
  return where ? `${name} · ${where}` : name;
}

function ResultTable({
  title,
  data,
  error,
  loading,
}: {
  title: string;
  data?: TwinV2Response;
  error?: string | null;
  loading: boolean;
}) {
  return (
    <section className="card overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-700">
        <h2 className="text-sm font-semibold">{title}</h2>
        {data && (
          <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
            구조 {Math.round(data.weights.structure * 100)} / 시장{" "}
            {Math.round(data.weights.market * 100)}
            {data.universe.scope_label ? ` · ${data.universe.scope_label}` : ""}
            {` · 후보 ${data.universe.size}곳`}
            {` · 인구문 통과 ${data.universe.after_population_gate}`}
            {data.universe.fallback ? ` · 폴백 ${data.universe.fallback}` : ""}
            {data.universe.n_hop != null ? ` · n-hop ${data.universe.n_hop}` : ""}
          </p>
        )}
      </div>
      {loading && <p className="px-4 py-6 text-sm text-slate-500">계산 중…</p>}
      {error && <p className="px-4 py-6 text-sm text-red-600">{error}</p>}
      {!loading && !error && data && data.neighbors.length === 0 && (
        <p className="px-4 py-6 text-sm text-slate-500">통과한 Twin이 없습니다.</p>
      )}
      {!loading && data && data.neighbors.length > 0 && (
        <div className="overflow-x-auto">
          <table className="data w-full text-xs">
            <thead>
              <tr>
                <th>#</th>
                <th>지역</th>
                <th>점수</th>
                <th>신뢰도</th>
                <th>구조</th>
                <th>시장</th>
                <th>V1</th>
                <th>빠진 항</th>
              </tr>
            </thead>
            <tbody>
              {data.neighbors.map((n) => (
                <tr key={n.region_code}>
                  <td>{n.rank}</td>
                  <td>
                    <div>{neighborLabel(n)}</div>
                    <div className="text-[10px] text-slate-400">{n.region_code}</div>
                  </td>
                  <td className="num font-semibold">{pct100(n.twin_score)}</td>
                  <td className="num">{pct100(n.confidence)}</td>
                  <td className="num">{pct100(n.structure_score)}</td>
                  <td className="num">{pct100(n.market_score)}</td>
                  <td className="num text-slate-400">{pct100(n.v1_similarity ?? null)}</td>
                  <td className="text-[10px] text-slate-500">
                    {n.dropped_blocks.length ? n.dropped_blocks.join(", ") : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default function TwinEngineV2Lab() {
  const [level, setLevel] = useState<TwinV2Level>("eupmyeondong");
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<{
    level: TwinV2Level;
    code: string;
    label: string;
  } | null>(null);
  const [open, setOpen] = useState(false);

  const searchQ = useQuery({
    queryKey: ["twin-v2-search", query],
    queryFn: () => searchRegions(query),
    enabled: query.trim().length >= 2,
  });

  const compareQ = useQuery({
    queryKey: ["twin-v2", "compare", picked?.level, picked?.code],
    queryFn: () =>
      fetchTwinsV2({
        regionLevel: picked!.level,
        regionCode: picked!.code,
        role: "compare" satisfies TwinV2Role,
      }),
    enabled: Boolean(picked),
    retry: false,
  });
  const poolQ = useQuery({
    queryKey: ["twin-v2", "pool", picked?.level, picked?.code],
    queryFn: () =>
      fetchTwinsV2({
        regionLevel: picked!.level,
        regionCode: picked!.code,
        role: "pool",
      }),
    enabled: Boolean(picked),
    retry: false,
  });

  const hits = useMemo(() => {
    const rows = searchQ.data ?? [];
    const seen = new Set<string>();
    const out: { code: string; label: string }[] = [];
    for (const r of rows) {
      let code = "";
      let label = "";
      if (level === "beopjungri") {
        code = (r.beopjungri_code || "").trim();
        label = [r.sido_name, r.sigungu_name, r.eupmyeondong_name, r.beopjungri_name]
          .filter(Boolean)
          .join(" ");
      } else if (level === "eupmyeondong") {
        code = (r.eupmyeondong_code || "").trim().slice(0, 8);
        label = [r.sido_name, r.sigungu_name, r.eupmyeondong_name].filter(Boolean).join(" ");
      } else {
        code = (r.sigungu_code || "").trim().slice(0, 5);
        label = [r.sido_name, r.sigungu_name].filter(Boolean).join(" ");
      }
      if (!code || seen.has(code)) continue;
      seen.add(code);
      out.push({ code, label: label || code });
      if (out.length >= 12) break;
    }
    return out;
  }, [level, searchQ.data]);

  const compareErr =
    (compareQ.error as { response?: { data?: { detail?: string } }; message?: string } | null)
      ?.response?.data?.detail ||
    (compareQ.error as { message?: string } | null)?.message ||
    null;
  const poolErr =
    (poolQ.error as { response?: { data?: { detail?: string } }; message?: string } | null)
      ?.response?.data?.detail ||
    (poolQ.error as { message?: string } | null)?.message ||
    null;

  return (
    <div className="max-w-6xl mx-auto px-4 py-4 space-y-4">
      <div className="card p-4 space-y-3">
        <p className="text-xs text-slate-500 leading-relaxed">
          V2는 프로필 카드를 바꾸지 않습니다. 아는 지역을 고르고, 비교 Twin(설명용)과 풀
          Twin(가격 검토용)이 눈에 맞는지 보면 됩니다. 점수와 신뢰도는 따로입니다.
        </p>
        <div className="flex flex-wrap gap-2">
          {LEVELS.map((lv) => (
            <button
              key={lv.id}
              type="button"
              className={clsx(
                "btn text-xs",
                level === lv.id ? "btn-primary" : "btn-ghost",
              )}
              onClick={() => {
                setLevel(lv.id);
                setPicked(null);
              }}
            >
              {lv.label}
            </button>
          ))}
        </div>
        <div className="relative">
          <input
            className="w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm"
            placeholder="이름 검색 (예: 나성동)"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
          />
          {open && query.trim().length >= 2 && (
            <ul className="absolute z-10 mt-1 w-full max-h-64 overflow-auto rounded-md border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 shadow">
              {searchQ.isFetching && (
                <li className="px-3 py-2 text-xs text-slate-400">검색 중…</li>
              )}
              {!searchQ.isFetching && hits.length === 0 && (
                <li className="px-3 py-2 text-xs text-slate-400">결과 없음</li>
              )}
              {hits.map((h) => (
                <li key={h.code}>
                  <button
                    type="button"
                    className="w-full text-left px-3 py-2 text-sm hover:bg-slate-100 dark:hover:bg-slate-700"
                    onClick={() => {
                      setPicked({ level, code: h.code, label: h.label });
                      setQuery(h.label);
                      setOpen(false);
                    }}
                  >
                    {h.label}
                    <span className="ml-2 text-[10px] text-slate-400">{h.code}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        {picked && (
          <p className="text-xs text-slate-600 dark:text-slate-300">
            선택: <span className="font-semibold">{picked.label}</span>{" "}
            <span className="text-slate-400">{picked.code}</span>
          </p>
        )}
      </div>

      {picked && (
        <div className="grid gap-4 lg:grid-cols-2">
          <ResultTable
            title="비교 Twin — 이 지역을 설명할 때"
            data={compareQ.data}
            error={compareErr}
            loading={compareQ.isFetching}
          />
          <ResultTable
            title="풀 Twin — 가격을 볼 때"
            data={poolQ.data}
            error={poolErr}
            loading={poolQ.isFetching}
          />
        </div>
      )}
    </div>
  );
}
