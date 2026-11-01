import type { AssetType, FloorIndexResponse } from "../types";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import { floorIndexGuideText } from "./FloorIndexMethodGuide";
import { UTILITY_CONTROL_LABELS, utilityNumber } from "../utils/residentialUtilityPresentation";
import { collectiveHelpText } from "../utils/collectiveHelpPresentation";

export type UtilityHelpData = Partial<Omit<FloorIndexResponse, "building_key" | "display_name">>;

export default function ResidentialUtilityIndexHelp({ data, assetType }: { data?: UtilityHelpData; assetType: AssetType }) {
  const title = assetType === "presale" ? "층·권리·면적 효용지수" : "층·동·면적 효용지수";
  const explain = { spec_id: "residential_utility_index_ui_v1", spec_version: "1", title,
    summary: "거래자료를 이용해 층, 동, 면적형에 따른 가격 차이를 분석합니다.", interpretation: [], limitations: [], interpretation_hints: [], presets: [] };
  const guide = data ? floorIndexGuideText({ dimension: data.dimension ?? "floor", floorMode: data.floor_mode ?? undefined, isRegression: data.method === "regression_semilog", referenceLabel: data.reference_floor }) : null;
  const guideBody = guide?.body
    .replace("전용면적·연식·거래시점(반기)을 맞춘 뒤", "실제 분석에 포함된 조건의 차이를 고려한 뒤")
    .replace("전용면적·연식·시점·상대 층을 맞춘 뒤", "실제 분석에 포함된 조건의 차이를 고려한 뒤")
    .replace("면적·연식·시점·층을 맞춘 뒤", "실제 분석에 포함된 조건의 차이를 고려한 뒤")
    .replace("층·연식·시점은 통제합니다.", "실제 통제변수는 아래 목록에서 확인할 수 있습니다.");
  const note = data?.explain;
  return <AnalysisHelpPanel explain={explain} title={`${title} 설명`} content={
    <div className="space-y-5 leading-relaxed text-slate-600 dark:text-slate-300">
      <p>{assetType === "apartment" ? "아파트" : assetType === "rowhouse" ? "연립·다세대" : assetType === "presale" ? "분양권·입주권" : "주거용 집합"} 거래자료를 이용해 층, {assetType === "presale" ? "권리" : "동"}, 면적형에 따른 가격 차이를 분석합니다.</p>
      <section className="space-y-3"><h4 className="font-semibold text-slate-800 dark:text-slate-100">효용지수란?</h4>
        <p>면적·연식·거래시점 등 다른 조건의 차이를 고려한 후, 기준 구간과 비교한 가격 수준을 지수로 표시합니다.</p>
        <p>기준 구간의 지수는 100입니다. 지수가 110이라면 다른 조건이 같을 때 기준 구간보다 추정 단가가 약 10% 높은 것으로 해석할 수 있습니다.</p>
      </section>
      <section className="space-y-3"><h4 className="font-semibold text-slate-800 dark:text-slate-100">분석 방법</h4><ul className="list-disc pl-5 space-y-2">
        <li>상대층: 1층·저층·중층·고층·관측 최상층으로 구분합니다. 지하는 별도 구간입니다. 관측 최상층은 선택 기간에 거래된 최고층입니다.</li>
        {assetType === "rowhouse" && <li>연립·다세대의 기본 구분은 1층·중간층·관측 최상층입니다.</li>}
        <li>층별: 개별 층의 가격 차이를 비교합니다.</li>
        <li>층 구간: 1~5층, 6~15층, 16층 이상으로 구분합니다. 지하는 별도 구간입니다.</li>
        <li>동별·면적형별: 동일 단지에서 동이나 면적형에 따른 가격 차이를 분석합니다. 주거 면적형은 전용면적을 30㎡ 단위로 반올림합니다. 예를 들어 84㎡는 90㎡ 면적형입니다.</li>
        {assetType === "presale" && <li>권리별: 분양권·입주권 등 권리에 따른 가격 차이를 비교합니다.</li>}
      </ul><p>거래자료의 ㎡당 단가를 로그로 변환해 회귀분석하며, 분석에 포함된 다른 조건을 통제합니다. 면적형별 분석에서는 면적을 구간으로 반영하며 연속 면적 변수는 함께 넣지 않습니다.</p></section>
      <section className="space-y-3"><h4 className="font-semibold text-slate-800 dark:text-slate-100">결과를 읽는 방법</h4><ul className="list-disc pl-5 space-y-2">
        <li>전체 거래: 선택한 기간과 조건에서 조회된 거래 수입니다.</li><li>분석 거래: 실제 회귀분석에 사용된 거래 수입니다.</li>
        <li>평균 단가: 해당 구간의 원자료 평균으로, 다른 조건을 통제하지 않은 값입니다. 단위는 만원/㎡입니다.</li>
        <li>효용지수: 다른 조건의 차이를 고려한 기준 구간 대비 가격 수준입니다.</li><li>95% 신뢰구간: 추정된 지수의 불확실성을 나타냅니다.</li>
        <li>p값: 기준 구간과의 차이가 통계적으로 유의한지 판단할 때 참고하는 값입니다. 기준 구간의 p값은 표시하지 않습니다.</li>
      </ul></section>
      <section className="space-y-3"><h4 className="font-semibold text-slate-800 dark:text-slate-100">알아두세요</h4><ul className="list-disc pl-5 space-y-2">
        <li>거래 수가 적거나 변수의 효과를 구분하기 어려운 경우 지수가 산출되지 않을 수 있습니다.</li><li>기준 구간은 지수 100으로 표시하며, 다른 구간은 이를 기준으로 비교합니다. 모형을 적합하지 못한 경우 기준의 100도 참고용 표시입니다.</li>
        <li>원자료 평균 단가와 회귀분석에 따른 효용지수는 서로 다를 수 있습니다.</li><li>효용지수는 거래자료에서 관찰된 통계적 관계로, 개별 아파트의 적정가격이나 인과적 효과를 의미하지 않습니다.</li>
      </ul></section>
      {data && <details className="rounded-lg border border-slate-200 p-3 dark:border-slate-600"><summary className="cursor-pointer font-semibold">현재 분석·계산 기준 자세히 보기</summary><div className="mt-3 space-y-3">
        {data.baseline_median != null && <p>전체 거래의 단가 중앙값: {utilityNumber(data.baseline_median)}만원/㎡</p>}
        {guideBody && <p>{guideBody}</p>}
        {data.controls?.length ? <p>실제 통제변수: {data.controls.map(c => UTILITY_CONTROL_LABELS[c] ?? collectiveHelpText(c)).join(" · ")}</p> : null}
        {data.diagnostics?.max_vif != null && <p>최대 VIF: {utilityNumber(data.diagnostics.max_vif)}{data.diagnostics.max_vif_term && ` · ${UTILITY_CONTROL_LABELS[data.diagnostics.max_vif_term] ?? collectiveHelpText(data.diagnostics.max_vif_term)}`}</p>}
        {data.diagnostics?.condition_number != null && <p>조건수: {utilityNumber(data.diagnostics.condition_number)}</p>}
        {data.diagnostics?.vifs && <ul className="list-disc pl-5 space-y-2">{Object.entries(data.diagnostics.vifs).map(([term,v]) => <li key={term}>{UTILITY_CONTROL_LABELS[term] ?? collectiveHelpText(term)} · VIF {utilityNumber(v)}</li>)}</ul>}
        {data.warnings?.length ? <div><p className="font-semibold">변수 제외 사유와 결과 안내</p><ul className="mt-2 list-disc pl-5 space-y-2">{[...new Set(data.warnings)].map(text => <li key={text}>{collectiveHelpText(text)}</li>)}</ul></div> : null}
        {[note?.formula, note?.index_rule, note?.reference].filter(Boolean).map((text,i) => <p key={i} className="whitespace-pre-wrap break-words">{collectiveHelpText(text!)}</p>)}
        {note?.floor_groups?.length ? <ul className="list-disc pl-5 space-y-2">{note.floor_groups.map(text => <li key={text}>{collectiveHelpText(text)}</li>)}</ul> : null}
        {note && [...(note.interpretation ?? []), ...(note.limitations ?? []), ...(note.interpretation_hints ?? [])].length > 0 && <details className="rounded border border-slate-200 p-3 dark:border-slate-600"><summary className="cursor-pointer font-medium">추가 계산 설명</summary><ul className="mt-3 list-disc pl-5 space-y-2">{[...new Set([...(note.interpretation ?? []), ...(note.limitations ?? []), ...(note.interpretation_hints ?? [])])].map(text => <li key={text}>{collectiveHelpText(text)}</li>)}</ul></details>}
      </div></details>}
    </div>
  } />;
}
