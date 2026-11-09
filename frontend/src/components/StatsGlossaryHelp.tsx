import { getGlossaryEntry, getStatsLearnUrl, type StatsGlossaryHelpProps } from "@ch2/stats-glossary";
import type { AnalysisExplain } from "@ch2/analysis-help";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import LandHelpContent from "./LandHelpContent";
import { landGlossaryCopy } from "../utils/landHelpPresentation";

export default function StatsGlossaryHelp({ termId, className, size = "sm" }: StatsGlossaryHelpProps) {
  const entry = getGlossaryEntry(termId);
  if (!entry) return null;
  const copy = landGlossaryCopy[termId];
  const explain: AnalysisExplain = {
    spec_id: `land.glossary.${termId}`, spec_version: "1", title: copy?.title ?? entry.title,
    summary: copy?.summary ?? entry.definition, formula: copy?.formula ?? entry.formula,
    interpretation: copy?.points ?? entry.interpretation, limitations: copy?.notes ?? entry.limitations,
    controls: copy?.thresholds ?? entry.thresholds, interpretation_hints: [], presets: [],
  };
  return <AnalysisHelpPanel explain={explain} title={`${entry.label} 용어 설명`}
    className={`${size === "xs" ? "h-5 w-5" : ""} ${className ?? ""}`}
    content={<LandHelpContent explain={explain} learnUrl={getStatsLearnUrl(termId)} />} />;
}
