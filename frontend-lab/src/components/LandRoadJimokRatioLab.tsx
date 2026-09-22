import { useMemo, useState } from "react";
import runJson from "../../../docs/lab/land_road_jimok_ratio_screen.json";

type Cut = {
  n_cells: number;
  n_candidates: number;
  n_dropped: number;
  n_road_only: number;
  r_p25: number | null;
  r_p50: number | null;
  r_p75: number | null;
  r_mean_p50: number | null;
  n_road_p50: number | null;
  n_base_p50: number | null;
  n_below_third: number;
};

type Band = {
  id: string;
  title: string;
  base_jimok: string;
  cuts: Record<string, Cut>;
};

type Cell = {
  sido_name: string;
  sigungu_name: string;
  eup_name: string;
  eup_code: string;
  zone: string;
  zone_label: string;
  band: string;
  base_jimok: string;
  n_road: number;
  n_base: number;
  r_med: number;
  r_mean: number;
};

type YearBand = { id: string; title: string; cuts: Record<string, Cut> };
type YearRow = { year: number; partial: boolean; bands: YearBand[] };
type RegCut = {
  n_cells: number;
  n_trades: number;
  n_road: number;
  n_base: number;
  beta: number | null;
  se: number | null;
  p: number | null;
  factor: number | null;
  log_area: number | null;
  year_ref: string | null;
  road_ref: string | null;
  r2: number | null;
  error: string | null;
};
type RegBand = { id: string; title: string; base_jimok: string; cuts: Record<string, RegCut> };
type Screen = {
  status: string;
  question: string;
  as_of_month: string;
  period_start: string;
  period_end: string;
  window_years: number;
  price_unit: string;
  primary_min_n: number;
  sensitivity_min_n: number[];
  third_tick: number;
  grain: string;
  controls: string;
  note: string;
  greenbelt: {
    n_groups: number;
    n_road_trades: number;
    n_base_trades: number;
    note: string;
  };
  bands: Band[];
  cells: Cell[];
  yearly?: YearRow[];
  regression?: { formula: string; fixed: string; se: string; note: string; bands: RegBand[] };
};

const screen = runJson as Screen;
const PAGE = 40;

function pct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function ratio(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(2);
}

function n1(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(0);
}

function ptxt(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (v < 0.001) return "<0.001";
  return v.toFixed(3);
}

function DistStrip({ cut, tick }: { cut: Cut; tick: number }) {
  if (cut.r_p25 == null || cut.r_p50 == null || cut.r_p75 == null) {
    return <p className="text-sm text-slate-500">이 기준을 통과한 칸이 없습니다.</p>;
  }
  const domain = Math.max(1, cut.r_p75, tick);
  const at = (v: number) => `${Math.max(0, Math.min(100, (v / domain) * 100))}%`;
  return (
    <div>
      <div className="relative h-10">
        <div className="absolute left-0 right-0 top-4 h-1.5 rounded bg-slate-200 dark:bg-slate-700" />
        <div
          className="absolute top-3 h-3.5 rounded bg-amber-400/80"
          style={{ left: at(cut.r_p25), width: `calc(${at(cut.r_p75)} - ${at(cut.r_p25)})` }}
        />
        <div className="absolute top-1 h-7 w-0.5 bg-slate-900 dark:bg-slate-100" style={{ left: at(cut.r_p50) }} />
        <div className="absolute top-0 h-9 w-px bg-rose-600" style={{ left: at(tick) }} title="1/3 눈금" />
      </div>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600 dark:text-slate-300">
        <span>25% {pct(cut.r_p25)}</span>
        <span className="font-semibold text-slate-900 dark:text-slate-100">중앙 {pct(cut.r_p50)}</span>
        <span>75% {pct(cut.r_p75)}</span>
        <span className="text-rose-700 dark:text-rose-300">1/3 눈금</span>
        <span>눈금 아래 {cut.n_below_third}칸</span>
      </div>
    </div>
  );
}

export default function LandRoadJimokRatioLab() {
  const cuts = screen.sensitivity_min_n?.length ? screen.sensitivity_min_n : [5, 10, 20];
  const [bandId, setBandId] = useState(screen.bands[0]?.id ?? "");
  const [page, setPage] = useState(0);
  const cells = useMemo(
    () => screen.cells.filter((c) => c.band === bandId),
    [bandId],
  );
  const pageCount = Math.max(1, Math.ceil(cells.length / PAGE));
  const shown = cells.slice(page * PAGE, page * PAGE + PAGE);
  const ready = screen.status === "ready" && screen.bands.length > 0;

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-8 text-sm">
      <header className="space-y-2">
        <h2 className="text-lg font-bold">{screen.question}</h2>
        <p className="text-slate-600 dark:text-slate-300">
          같은 읍면동·같은 용도지역에서, 지목 도로의 ㎡당 중앙단가가 비교 지목 중앙단가의 몇 %인지.
          도시와 비도시가 다른지, 비교 지목이 대·전·답 중 무엇인지에 따라 수준이 다른지를 본다.
        </p>
        <p className="text-slate-500">
          {screen.controls} {screen.note}
        </p>
        {screen.period_start ? (
          <p className="text-xs text-slate-500">
            창 {screen.window_years}년 · {screen.period_start} ~ {screen.period_end} · 기준월 {screen.as_of_month} ·{" "}
            {screen.price_unit} · 지분 제외 · 1차 칸은 양쪽 각 {screen.primary_min_n}건 이상
          </p>
        ) : null}
      </header>

      {!ready ? (
        <p className="text-slate-500">스냅샷을 아직 만들지 않았습니다. 러너가 끝나면 이 화면을 다시 엽니다.</p>
      ) : (
        <>
          {screen.bands.map((band) => {
            const cut = band.cuts[String(screen.primary_min_n)];
            if (!cut) return null;
            return (
              <section key={band.id} className="space-y-3">
                <h3 className="font-semibold">{band.title}</h3>
                <DistStrip cut={cut} tick={screen.third_tick} />
                <p className="text-xs text-slate-500">
                  통과 {cut.n_cells}칸 · 후보 {cut.n_candidates} · 건수 미달 {cut.n_dropped} · 비교 지목 없음{" "}
                  {cut.n_road_only} · 도로 건수 중앙 {n1(cut.n_road_p50)} · 비교 건수 중앙 {n1(cut.n_base_p50)} · 보조
                  평균단가 비 중앙 {pct(cut.r_mean_p50)}
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs border-collapse">
                    <thead>
                      <tr className="text-left text-slate-500 border-b border-slate-200 dark:border-slate-700">
                        <th className="py-1 pr-3 font-medium">양쪽 최소 건수</th>
                        <th className="py-1 pr-3 font-medium">통과 칸</th>
                        <th className="py-1 pr-3 font-medium">탈락 칸</th>
                        <th className="py-1 pr-3 font-medium">25%</th>
                        <th className="py-1 pr-3 font-medium">중앙</th>
                        <th className="py-1 pr-3 font-medium">75%</th>
                        <th className="py-1 font-medium">평균단가 비 중앙</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cuts.map((n) => {
                        const row = band.cuts[String(n)];
                        if (!row) return null;
                        return (
                          <tr key={n} className="border-b border-slate-100 dark:border-slate-800">
                            <td className="py-1 pr-3">{n}{n === screen.primary_min_n ? " · 1차" : ""}</td>
                            <td className="py-1 pr-3">{row.n_cells}</td>
                            <td className="py-1 pr-3">{row.n_dropped}</td>
                            <td className="py-1 pr-3">{pct(row.r_p25)}</td>
                            <td className="py-1 pr-3">{pct(row.r_p50)}</td>
                            <td className="py-1 pr-3">{pct(row.r_p75)}</td>
                            <td className="py-1">{pct(row.r_mean_p50)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
            );
          })}

          <p className="text-xs text-slate-500">
            {screen.greenbelt.note} 읍면동×용도 {screen.greenbelt.n_groups}칸 · 도로 거래 {screen.greenbelt.n_road_trades}
            건 · 대·전·답 거래 {screen.greenbelt.n_base_trades}건.
          </p>

          {screen.regression ? (
            <section className="space-y-3">
              <h3 className="font-semibold">2차 · 칸 안 회귀</h3>
              <p className="text-slate-600 dark:text-slate-300">
                {screen.regression.formula}. 고정은 {screen.regression.fixed}. {screen.regression.note}
              </p>
              <p className="text-xs text-slate-500">표준오차는 {screen.regression.se}.</p>
              <div className="overflow-x-auto">
                <table className="w-max min-w-full text-xs border-collapse whitespace-nowrap">
                  <thead>
                    <tr className="text-left text-slate-500 border-b border-slate-200 dark:border-slate-700">
                      <th className="py-1 pr-3 font-medium">분포</th>
                      <th className="py-1 pr-3 font-medium">양쪽 최소</th>
                      <th className="py-1 pr-3 font-medium">칸</th>
                      <th className="py-1 pr-3 font-medium">거래</th>
                      <th className="py-1 pr-3 font-medium">통제 후 배수</th>
                      <th className="py-1 pr-3 font-medium">log 계수 (표준오차)</th>
                      <th className="py-1 pr-3 font-medium">p</th>
                      <th className="py-1 font-medium">1차 중앙 비</th>
                    </tr>
                  </thead>
                  <tbody>
                    {screen.regression.bands.map((band) =>
                      cuts.map((n) => {
                        const row = band.cuts[String(n)];
                        const phase = screen.bands.find((b) => b.id === band.id)?.cuts[String(n)];
                        if (!row) return null;
                        return (
                          <tr key={`${band.id}-${n}`} className="border-b border-slate-100 dark:border-slate-800">
                            <td className="py-1 pr-3">{band.title}</td>
                            <td className="py-1 pr-3">{n}{n === screen.primary_min_n ? " · 1차와 같은 컷" : ""}</td>
                            <td className="py-1 pr-3">{row.n_cells}</td>
                            <td className="py-1 pr-3">{row.n_trades.toLocaleString("ko-KR")}</td>
                            <td className="py-1 pr-3">{row.factor == null ? "—" : pct(row.factor)}</td>
                            <td className="py-1 pr-3">
                              {row.beta == null ? "—" : `${row.beta.toFixed(3)} (${row.se?.toFixed(3) ?? "—"})`}
                            </td>
                            <td className="py-1 pr-3">{ptxt(row.p)}</td>
                            <td className="py-1">{pct(phase?.r_p50)}</td>
                          </tr>
                        );
                      }),
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}

          {screen.yearly && screen.yearly.length > 0 ? (
            <section className="space-y-3">
              <h3 className="font-semibold">2차 · 연도별 중앙값 비</h3>
              <p className="text-slate-600 dark:text-slate-300">
                각 해의 거래만으로 1차와 같은 비를 다시 만든다. 양쪽 10건은 그 해의 건수다. 면적·접면은 여기서도 맞추지 않는다.
                창의 끝 해는 12달이 아니다.
              </p>
              {screen.bands.map((band) => (
                <div key={`y-${band.id}`} className="overflow-x-auto">
                  <p className="text-xs font-medium mb-1">{band.title}</p>
                  <table className="w-max min-w-full text-xs border-collapse whitespace-nowrap">
                    <thead>
                      <tr className="text-left text-slate-500 border-b border-slate-200 dark:border-slate-700">
                        <th className="py-1 pr-3 font-medium">연도</th>
                        <th className="py-1 pr-3 font-medium">통과 칸</th>
                        <th className="py-1 pr-3 font-medium">25%</th>
                        <th className="py-1 pr-3 font-medium">중앙</th>
                        <th className="py-1 font-medium">75%</th>
                      </tr>
                    </thead>
                    <tbody>
                      {screen.yearly!.map((year) => {
                        const row = year.bands.find((b) => b.id === band.id)?.cuts[String(screen.primary_min_n)];
                        if (!row) return null;
                        return (
                          <tr key={`${band.id}-${year.year}`} className="border-b border-slate-100 dark:border-slate-800">
                            <td className="py-1 pr-3">
                              {year.year}
                              {year.partial ? " · 창의 일부" : ""}
                            </td>
                            <td className="py-1 pr-3">{row.n_cells}</td>
                            <td className="py-1 pr-3">{pct(row.r_p25)}</td>
                            <td className="py-1 pr-3">{pct(row.r_p50)}</td>
                            <td className="py-1">{pct(row.r_p75)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ))}
            </section>
          ) : null}

          <section className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <h3 className="font-semibold">칸</h3>
              <label className="text-xs text-slate-500">
                분포
                <select
                  className="ml-2 border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 rounded px-2 py-1"
                  value={bandId}
                  onChange={(e) => {
                    setBandId(e.target.value);
                    setPage(0);
                  }}
                >
                  {screen.bands.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.title}
                    </option>
                  ))}
                </select>
              </label>
              <span className="text-xs text-slate-500">
                {cells.length}칸 · {page + 1}/{pageCount}
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="text-left text-slate-500 border-b border-slate-200 dark:border-slate-700">
                    <th className="py-1 pr-3 font-medium">지역</th>
                    <th className="py-1 pr-3 font-medium">용도</th>
                    <th className="py-1 pr-3 font-medium">비교</th>
                    <th className="py-1 pr-3 font-medium">도로 건수</th>
                    <th className="py-1 pr-3 font-medium">비교 건수</th>
                    <th className="py-1 pr-3 font-medium">중앙 비</th>
                    <th className="py-1 font-medium">평균 비</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((c) => (
                    <tr key={`${c.eup_code}-${c.zone}-${c.base_jimok}`} className="border-b border-slate-100 dark:border-slate-800">
                      <td className="py-1 pr-3">
                        {c.sido_name} {c.sigungu_name} {c.eup_name}
                      </td>
                      <td className="py-1 pr-3">{c.zone_label}</td>
                      <td className="py-1 pr-3">{c.base_jimok}</td>
                      <td className="py-1 pr-3">{c.n_road}</td>
                      <td className="py-1 pr-3">{c.n_base}</td>
                      <td className="py-1 pr-3">
                        {pct(c.r_med)} <span className="text-slate-400">{ratio(c.r_med)}</span>
                      </td>
                      <td className="py-1">{pct(c.r_mean)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {pageCount > 1 ? (
              <div className="flex gap-2">
                <button
                  type="button"
                  className="px-2 py-1 border rounded border-slate-300 dark:border-slate-600 disabled:opacity-40"
                  disabled={page <= 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                >
                  이전
                </button>
                <button
                  type="button"
                  className="px-2 py-1 border rounded border-slate-300 dark:border-slate-600 disabled:opacity-40"
                  disabled={page + 1 >= pageCount}
                  onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                >
                  다음
                </button>
              </div>
            ) : null}
          </section>
        </>
      )}
    </div>
  );
}
