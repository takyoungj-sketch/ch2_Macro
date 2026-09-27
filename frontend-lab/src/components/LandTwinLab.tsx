import { useEffect, useMemo, useState } from "react";
import {
  fetchLandTwinRegions,
  runLandTwin,
  type LandTwinRegion,
  type LandTwinRun,
} from "../api/landTwinClient";

function fmt(n: number | null, digits: number): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toFixed(digits);
}

function topFive(
  rows: LandTwinRun["rows"],
  key: "price_rank" | "rank_b" | "rank_c" | "rank_d",
): LandTwinRun["rows"] {
  return rows
    .filter((row) => row[key] != null && (row[key] as number) <= 5)
    .sort((a, b) => (a[key] as number) - (b[key] as number));
}

export default function LandTwinLab() {
  const [regions, setRegions] = useState<LandTwinRegion[]>([]);
  const [meta, setMeta] = useState("");
  const [query, setQuery] = useState("흥덕");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<LandTwinRun | null>(null);

  useEffect(() => {
    let live = true;
    fetchLandTwinRegions()
      .then((data) => {
        if (!live) return;
        setRegions(data.regions);
        const end = (data.period_end ?? data.as_of_month).slice(0, 7);
        setMeta(`${data.window_years}년 · 기준월 ${end} · 시군구 ${data.regions.length}곳`);
        const hit = data.regions.find((row) => row.label.includes("청주시 흥덕구"));
        if (hit) setCode(hit.region_code);
      })
      .catch((err: unknown) => {
        if (!live) return;
        setError(err instanceof Error ? err.message : "시군구 목록을 불러오지 못했습니다.");
      });
    return () => {
      live = false;
    };
  }, []);

  const shown = useMemo(() => {
    const q = query.trim();
    if (!q) return regions;
    return regions.filter((row) => row.label.includes(q) || row.region_code.includes(q));
  }, [regions, query]);

  async function onRun() {
    if (!code) return;
    setBusy(true);
    setError("");
    try {
      setResult(await runLandTwin(code));
    } catch (err: unknown) {
      setResult(null);
      setError(err instanceof Error ? err.message : "계산에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  const listA = result ? topFive(result.rows, "price_rank") : [];
  const listB = result ? topFive(result.rows, "rank_b") : [];
  const listC = result ? topFive(result.rows, "rank_c") : [];
  const listD = result ? topFive(result.rows, "rank_d") : [];
  const listE = (result?.basket_rows ?? []).filter((row) => row.rank <= 5);

  return (
    <div className="space-y-4 text-sm">
      <p className="text-slate-600 dark:text-slate-300">
        지목 전체 거래비중으로 가까운 시군구 20곳을 후보로 둔 뒤, 그 후보에서 네 순위를 같이
        봅니다. A는 지목 가격형태만, B는 지목 비중과 가격형태, C는 용도지역 비중을 더합니다.
        D는 C와 같되 가격을 용도×지목 칸의 중위로 바꿉니다. 양쪽 15건 미만인 칸은 빠지고, 남은
        칸이 5개 미만이면 D 순위에서 제외합니다. 거래 건수와 칸 수는 점수에 넣지 않습니다.
        합산은 후보 안에서 거리를 0~1로 맞춘 같은 비중이며, 아직 확정한 식이 아닙니다.
        E는 그와 별개로, 고정한 10개 용도×지목의 대표액 구성비만으로 전국 시군구를 줄 세웁니다.
        대표액은 건수×중위단가이고 돈이 아닙니다. 가격과 규모는 E 순위에 넣지 않습니다.
      </p>
      <p className="text-xs text-slate-500">{meta}</p>
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-slate-500">찾기</span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-40 rounded border border-slate-300 bg-white px-2 py-1 dark:border-slate-600 dark:bg-slate-900"
          />
        </label>
        <label className="flex min-w-[16rem] flex-1 flex-col gap-1">
          <span className="text-xs text-slate-500">기준 시군구</span>
          <select
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="rounded border border-slate-300 bg-white px-2 py-1 dark:border-slate-600 dark:bg-slate-900"
          >
            <option value="">선택</option>
            {shown.map((row) => (
              <option key={row.region_code} value={row.region_code}>
                {row.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={!code || busy}
          onClick={() => void onRun()}
          className="rounded bg-slate-800 px-3 py-1.5 text-white disabled:opacity-40 dark:bg-slate-200 dark:text-slate-900"
        >
          {busy ? "계산 중" : "20곳 계산"}
        </button>
      </div>
      {error ? <p className="text-red-600">{error}</p> : null}
      {result ? (
        <>
          <p>
            기준 {result.anchor.label} · 거래 {result.anchor.n_tx.toLocaleString()}건 · 지목{" "}
            {result.anchor.n_jimok}개 · 용도 {result.anchor.n_zone}개
          </p>
          <div className="grid gap-3 md:grid-cols-4">
            {(
              [
                ["A 지목 가격", listA, "price_rank"],
                ["B 지목+가격", listB, "rank_b"],
                ["C 지목+용도+가격", listC, "rank_c"],
                ["D 지목+용도+칸가격", listD, "rank_d"],
              ] as const
            ).map(([title, list, key]) => (
              <div key={title} className="rounded border border-slate-200 p-2 dark:border-slate-700">
                <p className="mb-1 text-xs font-medium">{title}</p>
                <ol className="space-y-0.5">
                  {list.map((row) => (
                    <li key={row.region_code}>
                      {row[key]} {row.label}
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
          <div className="rounded border border-slate-200 p-2 dark:border-slate-700">
            <p className="mb-1 text-xs font-medium">E 대표 10칸 구성</p>
            {result.basket_note ? <p>{result.basket_note}</p> : null}
            <p className="mb-2 text-xs text-slate-500">
              {result.anchor.basket_shares
                .map((item) => `${item.cell} ${(item.share * 100).toFixed(0)}%`)
                .join(" · ")}
            </p>
            <ol className="mb-2 space-y-0.5">
              {listE.map((row) => (
                <li key={row.region_code}>
                  {row.rank} {row.label} · 구조 {fmt(row.structure_similarity, 1)} · 가격{" "}
                  {fmt(row.price_distance, 3)} · {row.scale_phrase ?? "—"}
                </li>
              ))}
            </ol>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="border-b border-slate-300 text-xs dark:border-slate-600">
                    <th className="py-1 pr-2">E</th>
                    <th className="py-1 pr-2">시군구</th>
                    <th className="py-1 pr-2">구조</th>
                    <th className="py-1 pr-2">가격</th>
                    <th className="py-1 pr-2">가격 칸</th>
                    <th className="py-1">대표액</th>
                  </tr>
                </thead>
                <tbody>
                  {result.basket_rows.map((row) => (
                    <tr key={row.region_code} className="border-b border-slate-100 dark:border-slate-800">
                      <td className="py-1 pr-2">{row.rank}</td>
                      <td className="py-1 pr-2">{row.label}</td>
                      <td className="py-1 pr-2">{fmt(row.structure_similarity, 1)}</td>
                      <td className="py-1 pr-2">{fmt(row.price_distance, 3)}</td>
                      <td className="py-1 pr-2">{row.price_cells || "—"}</td>
                      <td className="py-1">{row.scale_phrase ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-slate-300 text-xs dark:border-slate-600">
                  <th className="py-1 pr-2">구조</th>
                  <th className="py-1 pr-2">A</th>
                  <th className="py-1 pr-2">B</th>
                  <th className="py-1 pr-2">C</th>
                  <th className="py-1 pr-2">D</th>
                  <th className="py-1 pr-2">시군구</th>
                  <th className="py-1 pr-2">지목구조</th>
                  <th className="py-1 pr-2">용도구조</th>
                  <th className="py-1 pr-2">지목가격</th>
                  <th className="py-1 pr-2">칸가격</th>
                  <th className="py-1 pr-2">비교 지목</th>
                  <th className="py-1 pr-2">비교 칸</th>
                  <th className="py-1 pr-2">용도 수</th>
                  <th className="py-1 pr-2">수준 차</th>
                  <th className="py-1">거래</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row) => (
                  <tr key={row.region_code} className="border-b border-slate-100 dark:border-slate-800">
                    <td className="py-1 pr-2">{row.structure_rank}</td>
                    <td className="py-1 pr-2">{row.price_rank ?? "—"}</td>
                    <td className="py-1 pr-2">{row.rank_b ?? "—"}</td>
                    <td className="py-1 pr-2">{row.rank_c ?? "—"}</td>
                    <td className="py-1 pr-2">{row.rank_d ?? "—"}</td>
                    <td className="py-1 pr-2">{row.label}</td>
                    <td className="py-1 pr-2">{fmt(row.structure_similarity, 1)}</td>
                    <td className="py-1 pr-2">{fmt(row.zone_similarity, 1)}</td>
                    <td className="py-1 pr-2">{fmt(row.price_distance, 3)}</td>
                    <td className="py-1 pr-2" title={row.cell_level_phrase ?? ""}>
                      {fmt(row.cell_distance, 3)}
                    </td>
                    <td className="py-1 pr-2" title={row.shared_jimok.join(" ")}>
                      {row.shared_count || "—"}
                    </td>
                    <td className="py-1 pr-2" title={row.shared_cells.join(" ")}>
                      {row.shared_cell_count || "—"}
                    </td>
                    <td className="py-1 pr-2">{row.zone_count || "—"}</td>
                    <td className="py-1 pr-2">{row.level_phrase ?? "—"}</td>
                    <td className="py-1">{row.n_tx.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  );
}
