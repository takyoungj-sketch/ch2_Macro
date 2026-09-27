import { useState } from "react";
import { runAptTwin, type AptTwinResult } from "../api/aptTwinClient";

function pct(v: number | null | undefined): string {
  return v == null ? "—" : `${v.toFixed(2)}%`;
}

function gain(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

export default function AptTwinRegressionLab() {
  const [addr1, setAddr1] = useState("충청남도");
  const [addr2, setAddr2] = useState("아산시");
  const [addr4, setAddr4] = useState("모종동");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AptTwinResult | null>(null);

  async function onRun() {
    setBusy(true);
    setError("");
    try {
      setResult(await runAptTwin(addr1.trim(), addr2.trim(), addr4.trim()));
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setError(detail || "계산에 실패했습니다");
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  const first = result?.twins[0];

  return (
    <div className="space-y-6 text-sm">
      <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
        같은 권역의 아파트 재고 구성으로 쌍둥이를 고른 뒤, 연식·최고층·세대수·주차·공시지가의 표준화 계수를 비교합니다.
        예측력은 기준 지역 단지의 CV-MAPE만 봅니다. 제품 지역회귀 식은 바꾸지 않습니다.
      </p>
      <div className="flex flex-wrap gap-2 items-end">
        <label className="grid gap-1">
          <span className="text-xs text-slate-500">시도</span>
          <input className="rounded border px-2 py-1.5" value={addr1} onChange={(e) => setAddr1(e.target.value)} />
        </label>
        <label className="grid gap-1">
          <span className="text-xs text-slate-500">시군구</span>
          <input className="rounded border px-2 py-1.5" value={addr2} onChange={(e) => setAddr2(e.target.value)} />
        </label>
        <label className="grid gap-1">
          <span className="text-xs text-slate-500">읍면동</span>
          <input className="rounded border px-2 py-1.5" value={addr4} onChange={(e) => setAddr4(e.target.value)} />
        </label>
        <button type="button" className="rounded bg-slate-900 px-3 py-1.5 text-white disabled:opacity-50" disabled={busy} onClick={onRun}>
          {busy ? "계산 중" : "이 지역 계산"}
        </button>
      </div>
      {error && <p className="text-red-600">{error}</p>}
      {result && (
        <>
          <p className="text-slate-500">
            {result.as_of_label} · 권역 {result.region_name || "—"} · 기준 {result.anchor.label} · 적격 단지 {result.anchor.n}곳
            {result.anchor.in_pilot_band ? "" : " · 파일럿 구간(20~40곳) 밖"}
          </p>
          <section className="space-y-2">
            <h3 className="font-semibold">가까운 아파트 재고</h3>
            <table className="w-full text-left">
              <thead>
                <tr className="text-slate-500">
                  <th className="py-1 pr-3">지역</th>
                  <th className="py-1 pr-3">거리</th>
                  <th className="py-1 pr-3">단지 수</th>
                  <th className="py-1">유사도 규칙</th>
                </tr>
              </thead>
              <tbody>
                {result.twins.map((row) => (
                  <tr key={row.region_id} className="border-t border-slate-100">
                    <td className="py-1 pr-3">{row.label}</td>
                    <td className="py-1 pr-3">{row.distance.toFixed(3)}</td>
                    <td className="py-1 pr-3">{row.n}</td>
                    <td className="py-1">{row.gate.pass ? `통과 ${row.gate.cosine}` : row.gate.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          {first?.gate.rows && (
            <section className="space-y-2">
              <h3 className="font-semibold">1위와 표준화 계수 · 코사인 {first.gate.cosine ?? "—"} · 부호 {first.gate.sign_match}/5</h3>
              <table className="w-full text-left">
                <thead>
                  <tr className="text-slate-500">
                    <th className="py-1 pr-3">변수</th>
                    <th className="py-1 pr-3">기준</th>
                    <th className="py-1 pr-3">쌍둥이</th>
                    <th className="py-1">부호</th>
                  </tr>
                </thead>
                <tbody>
                  {first.gate.rows.map((row) => (
                    <tr key={row.variable} className="border-t border-slate-100">
                      <td className="py-1 pr-3">{row.variable}</td>
                      <td className="py-1 pr-3">{row.anchor.toFixed(3)}</td>
                      <td className="py-1 pr-3">{row.twin.toFixed(3)}</td>
                      <td className="py-1">{row.same_sign ? "같음" : "다름"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
          {result.steps && (
            <section className="space-y-2">
              <h3 className="font-semibold">기준 지역 CV-MAPE · {result.steps.role}</h3>
              <table className="w-full text-left">
                <thead>
                  <tr className="text-slate-500">
                    <th className="py-1 pr-3">추가</th>
                    <th className="py-1 pr-3">단순 통합</th>
                    <th className="py-1 pr-3">지역 더미</th>
                    <th className="py-1">더미 상대 감소</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t border-slate-100">
                    <td className="py-1 pr-3">단독</td>
                    <td className="py-1 pr-3">{pct(result.steps.local)}</td>
                    <td className="py-1 pr-3">{pct(result.steps.local)}</td>
                    <td className="py-1">—</td>
                  </tr>
                  {result.steps.steps.map((step) => (
                    <tr key={step.k} className="border-t border-slate-100">
                      <td className="py-1 pr-3">{step.k}곳{step.stop ? " · 중단" : ""}</td>
                      <td className="py-1 pr-3">{pct(step.pool)}</td>
                      <td className="py-1 pr-3">{pct(step.dummy)}</td>
                      <td className="py-1">{gain(step.dummy_gain)}{step.dummy_gain != null && step.dummy_gain < 0.1 ? " · 개선 작음" : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-slate-500">
                {result.steps.folds}-fold. 평가 단지는 기준 지역만입니다. 지역 더미 CV-MAPE가 직전보다 줄지 않으면 다음 쌍둥이를 더하지 않습니다.
              </p>
            </section>
          )}
          {result.pilot.length > 0 && (
            <section className="space-y-2">
              <h3 className="font-semibold">이 권역의 파일럿 후보 · 단지 20~40곳</h3>
              <div className="flex flex-wrap gap-2">
                {result.pilot.map((place) => (
                  <button
                    key={`${place.addr1}-${place.addr2}-${place.addr4}`}
                    type="button"
                    className="rounded-full border border-slate-300 px-3 py-1 text-xs"
                    onClick={() => {
                      setAddr1(place.addr1);
                      setAddr2(place.addr2);
                      setAddr4(place.addr4);
                    }}
                  >
                    {place.label} ({place.n})
                  </button>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
