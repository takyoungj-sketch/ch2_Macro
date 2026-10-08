import LabResume from "./LabResume";
import { useState } from "react";
import CheongjuLedgerRegressionLab from "./CheongjuLedgerRegressionLab";
import CheongjuHistoricalLedgerLab from "./CheongjuHistoricalLedgerLab";
import CheongjuLedgerFollowupLab from "./CheongjuLedgerFollowupLab";

function Table({
  caption,
  headers,
  rows,
}: {
  caption: string;
  headers: string[];
  rows: string[][];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm tabular-nums">
        <caption className="text-left text-xs text-slate-500 mb-2">{caption}</caption>
        <thead>
          <tr className="border-b border-slate-200 dark:border-slate-700 text-left text-xs text-slate-500">
            {headers.map((h) => (
              <th key={h} className="py-1.5 pr-3 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.join("|")} className="border-b border-slate-100 dark:border-slate-800">
              {row.map((cell, i) => (
                <td key={`${row[0]}-${i}`} className="py-1.5 pr-3">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function LandLotUnmaskLab() {
  const [tab, setTab] = useState("followup");
  return (
    <>
      <nav aria-label="청주 대장 실험" className="max-w-5xl mx-auto px-4 pt-4 flex gap-2">
        {[{ id: "followup", label: "평균 편향·갱신 시험" }, { id: "historical", label: "2019년 확대 실험" }, { id: "annual", label: "연도별 대장·회귀 비교" }, { id: "original", label: "단일 대장 마스킹 기록" }].map(t => (
          <button key={t.id} type="button" aria-pressed={tab === t.id} onClick={() => setTab(t.id)} className={`rounded border px-3 py-2 text-sm ${tab === t.id ? "bg-indigo-700 text-white" : "bg-white dark:bg-slate-900"}`}>{t.label}</button>
        ))}
      </nav>
      {tab === "followup" ? <CheongjuLedgerFollowupLab /> : tab === "historical" ? <CheongjuHistoricalLedgerLab /> : tab === "annual" ? <CheongjuLedgerRegressionLab /> : <OriginalLandLotUnmaskLab />}
    </>
  );
}

function OriginalLandLotUnmaskLab() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6 text-sm leading-relaxed">
      <LabResume
        resume={{
          next_id: "land-unmask-cheongju",
          title: "청주 1차 기록. 제품 식에는 없다",
          say: "비교 대상 중 필지가 하나로 좁혀진 비율은 전체 기간 50.8%, 2024년 이후 74.2%입니다. 대장은 2026년 8월 한 장입니다.",
          do_not: "지분 거래를 대장 면적과 맞추기. 부번이 공개된 것처럼 읽기. 소유자로 좁히기. 토지 제품 식에 넣기. Insight로 올리기.",
          how: "docs/lab/LAND_LOT_UNMASK_LAB.md · 관리자 ?tool=land-unmask",
        }}
      />

      <section className="space-y-2">
        <h2 className="font-semibold">질문</h2>
        <p>
          국토부 토지 실거래의 마스킹 지번을, 토지대장과 토지이용계획을 붙인 필지 목록으로 되돌릴 수 있는지
          청주시에서 봤습니다. 확정은 후보가 하나일 때입니다.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="font-semibold">자료</h2>
        <p>
          토지대장 <code>AL_D003_43_20260807</code>와 토지이용계획 <code>AL_D155_43_20260809</code>를
          법정동코드, 대장구분(토지/임야), 지번으로 연결했습니다. 청주(43111–43114) 대장 필지는 481,476개이고,
          그중 479,775개(99.6%)에 세부 용도지역이 있습니다. 세부 용도가 둘 이상인 필지는 104,174개(21.6%)입니다.
          구별 필지는 상당 144,791, 서원 81,631, 흥덕 125,160, 청원 129,894입니다.
        </p>
        <p>
          실거래는 로컬 <code>land_transactions</code>의 청주 행입니다. 지목·용도는 원장의 축약(
          <code>임</code>, <code>자녹</code>)이고, 대장은 긴 이름(<code>임야</code>, <code>자연녹지지역</code>
          )입니다. 맞출 때 <code>pipeline/constants.py</code>의 축약표를 썼습니다. 소유구분은 실거래에 없어서
          키에서 뺐습니다.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="font-semibold">무엇이면 마스킹이 걷힌 것으로 세나</h2>
        <p>
          지분, 해제, 용도 「기타」는 비교에서 뺍니다. 남는 거래에 대해 같은 법정동에서 지목·용도·계약면적
          (소수점 한 자리)이 같은 필지를 찾고, 본번 마스킹에 맞는 것만 남깁니다. <code>산</code>으로 시작하면
          임야대장만 봅니다. 그 후보가 하나이면 필지가 정해진 것으로 셉니다.
        </p>
        <p>
          공개 번지에는 부번이 없습니다. 청주 실거래 중 하이픈이 있는 번지는 0건입니다. 가장 많은 형태는{" "}
          <code>2**</code>처럼 세 자리 본번의 앞자리만 보이는 경우입니다. 대장은 <code>919-1</code>처럼 부번이
          있는 필지가 가장 많습니다(187,000필지). 마스킹은 본번 자리수만 좁히고, 같은 본번의 부번은 면적이
          갈라 줍니다.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-semibold">전체 기간 (2010–2026)</h2>
        <p>청주 거래 137,186건. 번지가 있는 133,790건은 전부 마스킹입니다. 빈 번지는 3,396건입니다.</p>
        <Table
          caption="비교 대상 99,818건. 지분 29,286건, 용도 기타 3,760건, 해제는 비교 전에 제외."
          headers={["결과", "건수", "비율"]}
          rows={[
            ["필지 1개", "50,708", "50.8%"],
            ["후보 2개 이상", "6,315", "6.3%"],
            ["같은 면적 없음", "42,795", "42.9%"],
          ]}
        />
        <p className="text-slate-600 dark:text-slate-300">
          면적만으로 이미 48,086건(48.2%)이 하나였습니다. 본번 마스킹을 더하면 50,708건입니다.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="font-semibold">2024년 이후</h2>
        <p>
          계약연도 2024–2026 거래는 16,515건이고, 같은 조건의 비교 대상은 9,473건입니다. 2026년은 적재된
          월까지만 있습니다.
        </p>
        <Table
          caption="필지가 하나로 좁혀진 비율. 분모는 그 해의 비교 대상입니다."
          headers={["계약연도", "비교 대상", "필지 1개", "비율"]}
          rows={[
            ["2024", "3,654", "2,545", "69.7%"],
            ["2025", "3,666", "2,672", "72.9%"],
            ["2026", "2,153", "1,814", "84.3%"],
            ["합계", "9,473", "7,031", "74.2%"],
          ]}
        />
        <p>
          합계의 나머지는 같은 면적이 없는 1,689건(17.8%)과 후보가 둘 이상인 753건(8.0%)입니다. 거래 시점이
          2026년 8월 대장에 가까울수록 면적·지목·용도가 그대로인 경우가 많아 비율이 올라갑니다. 대장 파일은
          그 한 시점뿐입니다.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="font-semibold">이번 기록에 없는 것</h2>
        <ul className="list-disc pl-5 space-y-1">
          <li>저촉여부(포함·접함·저촉)로 용도를 갈라 후보를 더 줄인 측정.</li>
          <li>후보가 없는 42.9%를 분할·합병, 지목 변경, 일부 면적 거래로 나눈 측정.</li>
          <li>청주 밖 지역. 제품 토지 식과 공개 Insight.</li>
        </ul>
      </section>
    </div>
  );
}
