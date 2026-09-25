import { useState } from "react";
import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { INSIGHT_12, INSIGHT_12_SNAP } from "../copy/insight12";
import yieldSnap from "../../../docs/lab/sangkwon_apt_yield.json";

function Prose({ lines }: { lines: readonly string[] }) {
  return (
    <div className="space-y-2">
      {lines.map((p) => (
        <p key={p}>{p}</p>
      ))}
    </div>
  );
}

const copy = INSIGHT_12;
const snap = INSIGHT_12_SNAP;

const KINDS = [
  { key: "office", label: "오피스" },
  { key: "mid_retail", label: "중대형 상가" },
  { key: "small_retail", label: "소규모 상가" },
  { key: "strata", label: "집합 상가" },
] as const;

type Zone = {
  income: number | null;
  capital: number | null;
  investment: number | null;
  rent: number | null;
  sale_price: number | null;
  n_dongs?: number;
};

type RankRow = {
  asset_kind: string;
  sec_nm: string;
  sido: string;
  income: number | null;
  capital: number | null;
  investment: number | null;
  rent: number | null;
  overlap: Zone | null;
};

function num(v: number | null | undefined, digits = 2): string {
  if (v == null) return "—";
  return v.toLocaleString("ko-KR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function RankTable({ rows, showAll }: { rows: RankRow[]; showAll: boolean }) {
  const visibleRows = showAll ? rows : rows.slice(0, 10);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[12px] whitespace-nowrap">
        <thead className="sticky top-0 z-10 bg-white dark:bg-slate-900">
          <tr className="text-right text-slate-500">
            <th className="py-1 pr-3 text-left font-medium">상권</th>
            <th className="py-1 px-2 font-medium">상권 소득(%)</th>
            <th className="py-1 px-2 font-medium">상권 자본(%)</th>
            <th className="py-1 px-2 font-medium">상권 투자수익률(%)</th>
            <th className="py-1 px-2 font-medium">아파트 소득(%)</th>
            <th className="py-1 px-2 font-medium">아파트 자본(%)</th>
            <th className="py-1 px-2 font-medium">아파트 소득+자본(%)</th>
            <th className="py-1 px-2 font-medium">상권 임대료(만원/㎡·월)</th>
            <th className="py-1 px-2 font-medium">아파트 임대료(만원/㎡·월)</th>
            <th className="py-1 px-2 font-medium">아파트 매매가(만원/㎡)</th>
            <th className="py-1 pl-2 font-medium">읍면동 수(곳)</th>
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((row) => (
            <tr key={`${row.asset_kind}-${row.sec_nm}`} className="border-t border-slate-100 text-right dark:border-slate-800">
              <td className="py-1 pr-3 text-left">
                {row.sec_nm}
                <span className="ml-1 text-slate-400">{row.sido}</span>
              </td>
              <td className="px-2">{num(row.income)}</td>
              <td className="px-2">{num(row.capital)}</td>
              <td className="px-2">{num(row.investment)}</td>
              <td className="px-2">{num(row.overlap?.income)}</td>
              <td className="px-2">{num(row.overlap?.capital)}</td>
              <td className="px-2">{num(row.overlap?.investment)}</td>
              <td className="px-2">{num(row.rent, 3)}</td>
              <td className="px-2">{num(row.overlap?.rent, 3)}</td>
              <td className="px-2">{num(row.overlap?.sale_price, 1)}</td>
              <td className="pl-2">{row.overlap?.n_dongs ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Insight12() {
  const prose = "space-y-3 text-sm leading-relaxed text-slate-700 dark:text-slate-200";
  const [selectedKind, setSelectedKind] = useState<(typeof KINDS)[number]["key"]>("office");
  const [showAll, setShowAll] = useState(false);
  const aiContext = {
    app: "insight" as const,
    panel: "Insight12",
    purpose: "statistics" as const,
    scope: { region_label: "전국" },
    facts: {
      as_of: snap.asOf,
      years: snap.years,
      n_rows: snap.rows,
      n_overlap_investment: snap.overlapInvestment,
    },
    explain: {
      spec_id: "insight_12",
      spec_version: "1",
      title: copy.listTitle,
      summary: copy.lead,
      limitations: [...copy.limits],
    },
  };

  return (
    <>
      <PublishAiContext context={aiContext} />
      <article className="max-w-6xl mx-auto px-4 py-8 space-y-10 pb-16">
        <p>
          <a href="/insight/" className="text-sm text-slate-500 hover:text-slate-800 dark:hover:text-slate-200">
            ← 질문 목록
          </a>
        </p>
        <header className="space-y-3">
          <h2 className="text-xl font-bold leading-snug">{copy.listTitle}</h2>
          <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-300">{copy.listDescription}</p>
          <p className="text-sm text-slate-500">{copy.listPeriod}</p>
        </header>
        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.summaryTitle}</h3>
          <p className="text-sm font-medium text-slate-800 dark:text-slate-100 leading-relaxed">{copy.lead}</p>
          <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.keyFindingTitle}</h4>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/60">
              <p className="text-xs text-slate-500">임대료 상관</p>
              <p className="mt-1 text-lg font-semibold">0.65–0.84</p>
              <p className="text-xs text-slate-500">네 유형</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/60">
              <p className="text-xs text-slate-500">투자수익률 상관</p>
              <p className="mt-1 text-lg font-semibold">0.20–0.35</p>
              <p className="text-xs text-slate-500">네 유형</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/60">
              <p className="text-xs text-slate-500">비교 단위</p>
              <p className="mt-1 text-lg font-semibold">5년 평균</p>
              <p className="text-xs text-slate-500">2021–2025</p>
            </div>
          </div>
        </section>
        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.seeTitle}</h3>
          <p>{copy.methodLead}</p>
          <details className="rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-700">
            <summary className="cursor-pointer font-medium">계산 방법 자세히 보기</summary>
            <ul className="mt-3 list-disc space-y-1.5 pl-5">
              {copy.see.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </details>
        </section>
        <section className="space-y-8">
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.bodyTitle}</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm whitespace-nowrap">
              <thead>
                <tr className="text-left text-slate-500">
                  <th className="py-1 pr-3 font-medium">유형</th>
                  <th className="py-1 pr-3 font-medium">임대료 상관</th>
                  <th className="py-1 pr-3 font-medium">투자수익률 상관</th>
                  <th className="py-1 pr-3 font-medium">소득수익률 상관</th>
                  <th className="py-1 pr-3 font-medium">자본수익률 상관</th>
                </tr>
              </thead>
              <tbody>
                {snap.corr.map((row) => (
                  <tr key={row.kind} className="border-t border-slate-200 dark:border-slate-700">
                    <td className="py-1.5 pr-3">{row.kind}</td>
                    <td className="py-1.5 pr-3">{row.rent.toFixed(2)} ({row.rentN})</td>
                    <td className="py-1.5 pr-3">{row.inv.toFixed(2)} ({row.invN})</td>
                    <td className="py-1.5 pr-3">{row.income.toFixed(2)} ({row.incomeN})</td>
                    <td className="py-1.5 pr-3">{row.capital.toFixed(2)} ({row.capitalN})</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-slate-500">
              괄호 안 숫자는 해당 상관계수 계산에 사용된 상권 수입니다. 각 값은 상권별 2021–2025년 평균끼리의 상관입니다.
            </p>
          </div>
          <section className="space-y-3">
            <div>
              <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">유형별 상권 순위</h4>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{copy.rankNote}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {KINDS.map((kind) => (
                <button
                  key={kind.key}
                  type="button"
                  className={`rounded-full border px-3 py-1.5 text-sm ${
                    selectedKind === kind.key
                      ? "border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900"
                      : "border-slate-300 text-slate-700 dark:border-slate-600 dark:text-slate-200"
                  }`}
                  onClick={() => {
                    setSelectedKind(kind.key);
                    setShowAll(false);
                  }}
                >
                  {kind.label}
                </button>
              ))}
            </div>
            {(() => {
              const kind = KINDS.find((item) => item.key === selectedKind) ?? KINDS[0];
              const part = (yieldSnap.rows as RankRow[]).filter((row) => row.asset_kind === kind.key);
              return (
                <>
                  <h5 className="text-sm font-semibold text-slate-900 dark:text-slate-50">
                    {kind.label} · {part.length}곳
                  </h5>
                  <RankTable rows={part} showAll={showAll} />
                  {part.length > 10 && (
                    <button
                      type="button"
                      className="rounded border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-600"
                      onClick={() => setShowAll((value) => !value)}
                    >
                      {showAll ? "상위 10개만 보기" : `전체 ${part.length}곳 보기`}
                    </button>
                  )}
                </>
              );
            })()}
          </section>
          <section className={prose}>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.s1Title}</h4>
            <Prose lines={copy.s1} />
          </section>
          <section className={prose}>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.s2Title}</h4>
            <Prose lines={copy.s2} />
          </section>
          <section className={prose}>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{copy.s3Title}</h4>
            <Prose lines={copy.s3} />
          </section>
        </section>
        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.scopeTitle}</h3>
          <Prose lines={copy.scope} />
          <div className="overflow-x-auto">
            <table className="w-full text-sm whitespace-nowrap">
              <thead>
                <tr className="text-left text-slate-500">
                  <th className="py-1 pr-3 font-medium">유형</th>
                  <th className="py-1 pr-3 font-medium">읍면동 겹침 투자</th>
                  <th className="py-1 font-medium">1km 투자</th>
                </tr>
              </thead>
              <tbody>
                {snap.corr.map((row) => (
                  <tr key={row.kind} className="border-t border-slate-200 dark:border-slate-700">
                    <td className="py-1.5 pr-3">{row.kind}</td>
                    <td className="py-1.5 pr-3">{row.inv.toFixed(2)} ({row.invN})</td>
                    <td className="py-1.5">{row.nearInv.toFixed(2)} ({row.nearN})</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-slate-500">{copy.scopeNote}</p>
          </div>
        </section>
        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.limitsTitle}</h3>
          <ul className="list-disc ml-5 space-y-1.5">
            {copy.limits.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>
        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.closeTitle}</h3>
          <Prose lines={copy.close} />
        </section>
        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.nextTitle}</h3>
          <ul className="list-disc ml-5 space-y-1.5">
            {copy.next.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>
        <section className={prose}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-50">{copy.relatedTitle}</h3>
          <Prose lines={copy.related} />
        </section>
      </article>
    </>
  );
}
