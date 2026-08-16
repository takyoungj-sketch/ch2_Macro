import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  fetchQaRuns,
  readQaToken,
  runRandom,
  runSpecified,
  writeQaToken,
  type QaRun,
} from "../api/qaClient";

const ASSETS = [
  { id: "apartment", label: "아파트" },
  { id: "rowhouse", label: "연립다세대" },
  { id: "officetel", label: "오피스텔" },
];

function verdictClass(v?: string) {
  if (v === "PASS") return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200";
  if (v === "REVIEW") return "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-100";
  if (v === "ERROR" || v === "BLOCK") return "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200";
  return "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200";
}

function displayVerdict(run: QaRun) {
  return run.verdict_ui || (run.verdict === "BLOCK" ? "ERROR" : run.verdict);
}

export default function QaAuditPanel({ onWhy }: { onWhy?: () => void }) {
  const [mode, setMode] = useState<"specified" | "random">("specified");
  const [year, setYear] = useState(2025);
  const [assetType, setAssetType] = useState("apartment");
  const [region, setRegion] = useState("세종특별자치시 나성동");
  const [regionCode, setRegionCode] = useState("");
  const [n, setN] = useState(1);
  const [saveDb, setSaveDb] = useState(false);
  const [token, setToken] = useState(() => readQaToken());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<QaRun[]>([]);

  const histQ = useQuery({
    queryKey: ["qa-runs"],
    queryFn: () => fetchQaRuns(12),
    retry: false,
  });

  async function onRun() {
    writeQaToken(token);
    setBusy(true);
    setError(null);
    try {
      if (mode === "random") {
        const out = await runRandom({ n, save_db: saveDb });
        setRuns(out.runs);
      } else {
        const out = await runSpecified({
          calendar_year: year,
          asset_type: assetType,
          region_name: regionCode.trim() ? undefined : region.trim() || undefined,
          region_code: regionCode.trim() || undefined,
          save_db: saveDb,
        });
        setRuns([out]);
      }
      void histQ.refetch();
    } catch (exc: unknown) {
      const ax = exc as { response?: { data?: { detail?: string } }; message?: string };
      setError(ax.response?.data?.detail || ax.message || "검증 실패");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-4 space-y-4">
      <div className="card p-4 space-y-3">
        <p className="text-xs text-slate-500 leading-relaxed">
          숫자는 SQL·생산 빌더가 만듭니다. 원장·마트는 변경하지 않습니다.
          <br />
          AI는 검증값을 생성하지 않으며, 검증 결과의 해석과 원인 분석에만 사용합니다.
          {onWhy && (
            <>
              {" "}
              <button type="button" className="underline underline-offset-2 text-amber-800 dark:text-amber-200" onClick={onWhy}>
                왜 이렇게? D-042
              </button>
            </>
          )}
        </p>
        <div className="flex flex-wrap gap-2 text-xs">
          <button
            type="button"
            className={clsx("rounded border px-2 py-1", mode === "specified" ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950" : "border-slate-300")}
            onClick={() => setMode("specified")}
          >
            지정 검증
          </button>
          <button
            type="button"
            className={clsx("rounded border px-2 py-1", mode === "random" ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950" : "border-slate-300")}
            onClick={() => setMode("random")}
          >
            랜덤 표본
          </button>
        </div>
        {mode === "random" && (
          <p className="text-xs text-slate-500">
            지역·유형·연도를 층화 추첨합니다. V1은 집합 주거(아파트·연립·오피스텔). 토지·복합은 후속.
          </p>
        )}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
          {mode === "specified" && (
            <>
              <label className="space-y-1">
                <span className="text-xs text-slate-500">연도</span>
                <input
                  type="number"
                  className="w-full rounded border border-slate-300 px-2 py-1.5 dark:border-slate-600 dark:bg-slate-900"
                  value={year}
                  onChange={(e) => setYear(Number(e.target.value))}
                />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-slate-500">유형</span>
                <select
                  className="w-full rounded border border-slate-300 px-2 py-1.5 dark:border-slate-600 dark:bg-slate-900"
                  value={assetType}
                  onChange={(e) => setAssetType(e.target.value)}
                >
                  {ASSETS.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1 sm:col-span-2">
                <span className="text-xs text-slate-500">지역명</span>
                <input
                  className="w-full rounded border border-slate-300 px-2 py-1.5 dark:border-slate-600 dark:bg-slate-900"
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                  placeholder="세종특별자치시 나성동"
                />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-slate-500">지역코드 (선택)</span>
                <input
                  className="w-full rounded border border-slate-300 px-2 py-1.5 dark:border-slate-600 dark:bg-slate-900"
                  value={regionCode}
                  onChange={(e) => setRegionCode(e.target.value)}
                  placeholder="36110107"
                />
              </label>
            </>
          )}
          {mode === "random" && (
            <label className="space-y-1">
              <span className="text-xs text-slate-500">표본 수 (1–3)</span>
              <input
                type="number"
                min={1}
                max={3}
                className="w-full rounded border border-slate-300 px-2 py-1.5 dark:border-slate-600 dark:bg-slate-900"
                value={n}
                onChange={(e) => setN(Number(e.target.value))}
              />
            </label>
          )}
          <label className="space-y-1 sm:col-span-2">
            <span className="text-xs text-slate-500">QA 토큰 (VPS에서 QA_AUDIT_TOKEN 설정 시)</span>
            <input
              type="password"
              className="w-full rounded border border-slate-300 px-2 py-1.5 dark:border-slate-600 dark:bg-slate-900"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              autoComplete="off"
            />
          </label>
          <label className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300 pt-6">
            <input type="checkbox" checked={saveDb} onChange={(e) => setSaveDb(e.target.checked)} />
            qa_audit_run 에 저장
          </label>
        </div>
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void onRun()}>
          {busy ? "검증 중…" : "검증 실행"}
        </button>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>

      {runs.map((run, i) => (
        <ResultCard key={`${run.region_code}-${run.period_key}-${i}`} run={run} />
      ))}

      {histQ.data?.items?.length ? (
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-2">최근 런</h3>
          <table className="data w-full">
            <thead>
              <tr>
                <th>시각</th>
                <th>대상</th>
                <th>연도</th>
                <th>판정</th>
              </tr>
            </thead>
            <tbody>
              {histQ.data.items.map((row) => (
                <tr key={row.id}>
                  <td className="text-left text-xs">{row.created_at}</td>
                  <td className="text-left">
                    {row.region_name || row.region_code}{" "}
                    <span className="text-slate-400">{row.trigger}</span>
                  </td>
                  <td>{row.period_key}</td>
                  <td>
                    <span className={clsx("rounded px-1.5 py-0.5 text-xs", verdictClass(row.verdict))}>
                      {row.verdict === "BLOCK" ? "ERROR" : row.verdict}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function ResultCard({ run }: { run: QaRun }) {
  const metrics = run.diffs?.metrics || {};
  const n = metrics.n;
  const checks = run.diffs?.checks || [];
  const v = displayVerdict(run);
  const typeLabel = run.asset_label || run.asset_type || "";

  return (
    <div className="card p-4 space-y-4">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">검증 결과</p>
        <p className="text-sm mt-1">
          <span className="text-slate-500">대상</span>{" "}
          {run.region_name || run.region_code} · {typeLabel} · {run.period_key}년
          {run.trigger === "random" ? " · 랜덤 표본" : ""}
        </p>
        <p className="mt-2 flex items-center gap-2">
          <span className="text-slate-500 text-sm">종합판정</span>
          <span className={clsx("rounded px-2 py-0.5 text-sm font-semibold", verdictClass(v))}>{v}</span>
        </p>
      </div>

      {n && (
        <div className="grid gap-2 sm:grid-cols-4 text-sm bg-slate-50 dark:bg-slate-900/40 rounded p-3">
          <EvidenceStat label="원장 유효 거래건수" value={n.l1} suffix="건" />
          <EvidenceStat label="재계산 (L3)" value={n.l3} suffix="건" />
          <EvidenceStat label="기존 Mart" value={n.mart} suffix="건" />
          <EvidenceStat label="차이 (원장−마트)" value={n.delta_l1_mart} suffix="건" />
        </div>
      )}

      {checks.length > 0 && (
        <table className="data w-full">
          <thead>
            <tr>
              <th>검증항목</th>
              <th>결과</th>
              <th>근거</th>
            </tr>
          </thead>
          <tbody>
            {checks.map((c) => (
              <tr key={c.id}>
                <td>{c.label}</td>
                <td>
                  <span className={clsx("rounded px-1.5 py-0.5 text-xs font-semibold", verdictClass(c.grade))}>
                    {c.grade}
                  </span>
                </td>
                <td className="text-left text-xs text-slate-600 dark:text-slate-300">{c.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {run.diffs?.cause_candidates?.length ? (
        <ul className="text-xs text-slate-600 dark:text-slate-300 list-disc pl-5">
          {run.diffs.cause_candidates.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function EvidenceStat({
  label,
  value,
  suffix,
}: {
  label: string;
  value: number | null | undefined;
  suffix: string;
}) {
  return (
    <div>
      <p className="text-[11px] text-slate-500">{label}</p>
      <p className="font-semibold tabular-nums">
        {value == null ? "-" : `${value.toLocaleString("ko-KR")} ${suffix}`}
      </p>
    </div>
  );
}
