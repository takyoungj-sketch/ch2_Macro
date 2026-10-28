import { getGlossaryEntry, getStatsLearnUrl, type StatsGlossaryHelpProps } from "@ch2/stats-glossary";
import type { AnalysisExplain } from "@ch2/analysis-help";
import AnalysisHelpPanel from "./AnalysisHelpPanel";
import CollectiveHelpContent from "./CollectiveHelpContent";
import { collectiveHelpIntro } from "../utils/collectiveHelpPresentation";

export default function StatsGlossaryHelp({ termId, className, size = "sm" }: StatsGlossaryHelpProps) {
  const entry = getGlossaryEntry(termId);
  if (!entry) return null;
  const explain: AnalysisExplain = {
    spec_id: `collective.glossary.${termId}`, spec_version: "1", title: entry.title,
    summary: entry.definition, formula: entry.formula, interpretation: entry.interpretation,
    limitations: entry.limitations, controls: entry.thresholds, interpretation_hints: [], presets: [],
  };
  const title = collectiveHelpIntro(explain)?.title ?? entry.title;
  return <AnalysisHelpPanel explain={{ ...explain, title }} title={`${entry.label} 용어 설명`}
    className={`${size === "xs" ? "h-5 w-5" : ""} ${className ?? ""}`}
    content={<CollectiveHelpContent explain={explain} learnUrl={getStatsLearnUrl(termId)} />} />;
}
