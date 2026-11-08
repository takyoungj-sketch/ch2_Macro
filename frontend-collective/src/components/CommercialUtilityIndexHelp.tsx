import { createReadableHelpContent } from "@ch2/analysis-help";
import type { AnalysisExplain, CommercialFloorIndexResponse } from "../types";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import { CLUSTER_FLOOR_INDEX_HELP } from "../utils/residentialAnalysisHelp";
import { collectiveHelpText } from "../utils/collectiveHelpPresentation";
import { UTILITY_CONTROL_LABELS, utilityNumber } from "../utils/residentialUtilityPresentation";

const HelpContent = createReadableHelpContent(() => undefined, collectiveHelpText);
export default function CommercialUtilityIndexHelp({ data, isFactory }: { data?: Partial<CommercialFloorIndexResponse>; isFactory: boolean }) {
  const note = data?.explain ?? CLUSTER_FLOOR_INDEX_HELP;
  const labels = { ...UTILITY_CONTROL_LABELS, ln_exclusive_area: "연면적(로그)", building_use: "건축물용도" };
  const controlName = (name: string) => labels[name as keyof typeof labels] ?? collectiveHelpText(name);
  const explain: AnalysisExplain = {
    spec_id: "commercial_utility_index_ui_v1", spec_version: "1",
    title: isFactory ? "공장창고 층·면적 효용지수" : "상가 층·면적 효용지수",
    summary: "같은 도로명 묶음의 거래자료로 층과 면적 구간에 따른 가격 수준을 비교합니다. 개별 건물 한 곳의 결과와는 다릅니다.",
    interpretation: [
      "분석에 포함된 다른 조건의 차이를 고려한 기준 구간의 효용지수는 100입니다. 지수가 110이면 기준보다 추정 단가가 약 10% 높은 수준입니다.",
      "전체 거래는 조회된 거래 수, 분석 거래는 실제 회귀분석에 사용된 거래 수입니다. 평균 단가는 다른 조건을 통제하지 않은 원자료의 평균이며 단위는 만원/㎡입니다.",
      "95% 신뢰구간은 지수 추정의 불확실성을 나타냅니다. p값은 기준 구간과의 차이를 판단할 때 참고하며, 기준 구간의 p값은 표시하지 않습니다.",
    ],
    limitations: ["표본이 적거나 변수의 효과를 구분하기 어려우면 지수가 산출되지 않을 수 있습니다. 표의 미산출·참고용 표시를 확인해 주세요.", "효용지수는 관찰된 통계적 관계이며 개별 호실의 적정가격이나 인과적 효과를 뜻하지 않습니다."],
    floor_groups: isFactory ? ["층: 지하·1층·2층·3층 이상입니다. 층 정보가 부족한 경우 면적대별 결과를 먼저 확인해 주세요.", "면적대: 연면적 100㎡ 미만·100~300㎡·300~1000㎡·1000㎡ 이상입니다."] : ["층: 지하심층(B2 이하)·지하1층·1층·2층·저층(3~4층)·중층(5~9층)·고층(10~19층)·초고층(20층 이상)입니다.", "면적형: 연면적 35㎡ 미만·35~50㎡·50~100㎡·100~300㎡·300㎡ 이상입니다. 주거의 30㎡ 반올림 구간과 다릅니다."],
    formula: note.formula,
    index_rule: note.index_rule,
    reference: data?.reference_floor ? `현재 기준 구간: ${data.reference_floor} = 100` : note.reference,
    controls: ["㎡당 단가에 로그를 적용해 분석합니다. 면적형·면적대 분석에서는 면적을 구간으로 반영하며 연속 면적 변수는 함께 넣지 않습니다.", "면적 구간의 기준은 최종 분석 표본의 면적 중앙값에 가장 가까운 칸입니다. 거리가 같으면 작은 칸을 사용합니다.",
      ...(data?.controls?.length ? [`실제 통제변수: ${data.controls.map(controlName).join(" · ")}`] : []),
      ...(data?.baseline_median != null ? [`전체 거래의 단가 중앙값: ${utilityNumber(data.baseline_median)}만원/㎡`] : []),
      ...(data?.diagnostics?.max_vif != null ? [`최대 VIF: ${utilityNumber(data.diagnostics.max_vif)}${data.diagnostics.max_vif_term ? ` · ${controlName(data.diagnostics.max_vif_term)}` : ""}`] : []),
      ...(data?.diagnostics?.condition_number != null ? [`조건수: ${utilityNumber(data.diagnostics.condition_number)}`] : []),
      ...Object.entries(data?.diagnostics?.vifs ?? {}).map(([term,value]) => `${controlName(term)} · VIF ${utilityNumber(value)}`),
      ...[...new Set(data?.warnings ?? [])],
    ],
    interpretation_hints: [], presets: [],
  };
  return <AnalysisHelpPanel explain={explain} title={`${explain.title} 설명`} content={<HelpContent explain={explain} />} />;
}
