import { getGlossaryEntry, getStatsLearnUrl, type StatsGlossaryHelpProps } from "@ch2/stats-glossary";
import { AnalysisHelpPanel, createReadableHelpContent, type AnalysisExplain } from "@ch2/analysis-help";
import { PROFILE_HELP_COPY } from "../utils/profileHelpPresentation";

const ProfileHelpContent = createReadableHelpContent(() => undefined);

export default function ProfileStatsGlossaryHelp({ termId, className, size = "sm" }: StatsGlossaryHelpProps) {
  const original = getGlossaryEntry(termId);
  if (!original) return null;
  const entry = { ...original, ...PROFILE_HELP_COPY[termId] };
  const explain: AnalysisExplain = {
    spec_id: `profile.glossary.${termId}`,
    spec_version: "1",
    title: entry.title,
    summary: entry.definition,
    formula: entry.formula,
    interpretation: entry.interpretation,
    limitations: entry.limitations,
    controls: entry.thresholds,
  };
  return <AnalysisHelpPanel
    explain={explain}
    title={`${entry.label} 용어 설명`}
    hideMetadata
    className={`${size === "xs" ? "h-5 w-5" : ""} ${className ?? ""}`}
    content={<ProfileHelpContent explain={explain} learnUrl={getStatsLearnUrl(termId)} />}
  />;
}
