import { useMemo } from "react";
import { Link } from "react-router-dom";
import MatrixStatsTable, { MatrixStatsLegend } from "../components/MatrixStatsTable";
import StatsTable from "../components/StatsTable";
import HelpPopover from "../components/HelpPopover";
import { COMPARE_SESSION_KEY } from "../constants/compareStorage";
import { CompareHelpContent } from "../help/helpCopy";
import type { ComparePayloadV1 } from "../types/comparePayload";
import { downloadComparePack } from "../utils/exportCsv";
import { safeFileStem } from "../utils/safeFilename";

function loadPayload(): ComparePayloadV1 | null {
  try {
    const raw = sessionStorage.getItem(COMPARE_SESSION_KEY);
    if (!raw) return null;
    const o = JSON.parse(raw) as ComparePayloadV1;
    if (o.v !== 1 || !o.matrix || !o.by_region) return null;
    return o;
  } catch {
    return null;
  }
}

export default function ComparePage() {
  const payload = useMemo(() => loadPayload(), []);
  const stem = useMemo(
    () => safeFileStem(payload?.title ?? "compare"),
    [payload?.title]
  );

  if (!payload) {
    return (
      <div className="min-h-screen bg-slate-50 p-8 text-center text-slate-600 text-sm">
        <p className="font-medium text-slate-800">비교할 데이터가 없습니다.</p>
        <p className="mt-2 text-xs text-slate-500">
          유료 화면에서 필터 분석을 실행한 뒤「비교 새 창」을 눌러 주세요.
        </p>
        <Link to="/" className="mt-4 inline-block text-blue-600 underline text-sm">
          대시보드로
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 compare-print-root">
      <header className="no-print sticky top-0 z-50 border-b border-slate-200 bg-white/95 px-4 py-3 flex flex-wrap items-center justify-between gap-2 shadow-sm">
        <div>
          <h1 className="text-sm font-bold text-slate-800">지역 비교</h1>
          <p className="text-[11px] text-slate-500">{payload.title}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="text-xs font-medium px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50"
            onClick={() => downloadComparePack(payload, stem)}
          >
            CSV 묶음
          </button>
          <button
            type="button"
            className="text-xs font-medium px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-800 text-white hover:bg-slate-900"
            onClick={() => window.print()}
          >
            인쇄 / PDF
          </button>
          <Link
            to="/"
            className="text-xs font-medium px-3 py-1.5 rounded-lg border border-blue-200 text-blue-700 hover:bg-blue-50"
          >
            대시보드
          </Link>
        </div>
      </header>

      <main className="max-w-[1200px] mx-auto p-4 space-y-8">
        <section className="no-print rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-[11px] text-amber-950 leading-relaxed">
          <strong className="font-semibold">안내:</strong> 위에서부터 각 법정단위별{" "}
          <strong>전체 표본 단가 통계</strong>입니다. 맨 아래 <strong>통합 매트릭스</strong>는 선택
          지역을 하나의 표본으로 합친 용도지역×지목 표입니다.
        </section>

        {payload.regionOrder.map((code, idx) => {
          const st = payload.by_region[code];
          if (!st) return null;
          const label = payload.regionLabels[code]?.trim() || code;
          return (
            <section
              key={code}
              className={`bg-white rounded-xl shadow-sm p-5 space-y-3 print:shadow-none ${idx > 0 ? "print:break-before-page" : ""}`}
            >
              <h2 className="text-base font-bold text-slate-800 border-b border-slate-100 pb-2 flex flex-wrap items-center gap-2">
                <span>
                  ({idx + 1}) {label}
                </span>
                <span className="text-xs font-normal text-slate-400 tabular-nums">{code}</span>
              </h2>
              <StatsTable
                title=""
                rows={[{ label: `${label} · 해당 지역 표본 통계`, stats: st }]}
              />
            </section>
          );
        })}

        <section className="bg-white rounded-xl shadow-sm p-5 space-y-4 print:shadow-none print:break-before-page">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-3">
            <div>
              <h2 className="text-base font-bold text-slate-800">통합 매트릭스</h2>
              <p className="text-[11px] text-slate-500 mt-1 max-w-xl leading-relaxed">
                선택 법정동·리 필터 안에서 모든 거래를 합친 표본입니다. 원본 분석 탭과 동일한 매트릭스입니다.
              </p>
            </div>
            <div className="flex items-start gap-2 no-print shrink-0">
              <MatrixStatsLegend />
              <HelpPopover ariaLabel="비교 창에서 통합 매트릭스와 지역 블록의 차이" align="left">
                <CompareHelpContent />
              </HelpPopover>
            </div>
          </div>
          <MatrixStatsTable
            title=""
            matrix={payload.matrix}
            byZone={payload.by_zone}
            byLandCategory={payload.by_land_category}
            showEmbeddedLegend={false}
          />
        </section>
      </main>
    </div>
  );
}
