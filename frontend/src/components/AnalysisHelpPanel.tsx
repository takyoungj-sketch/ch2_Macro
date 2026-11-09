import type { ComponentProps } from "react";
import { AnalysisHelpPanel as SharedAnalysisHelpPanel } from "@ch2/analysis-help";
import LandHelpContent from "./LandHelpContent";
import { landHelpText } from "../utils/landHelpPresentation";

export default function AnalysisHelpPanel(props: ComponentProps<typeof SharedAnalysisHelpPanel>) {
  const explain = props.explain;
  const title = explain ? landHelpText(explain.title) : "도움말";
  return <SharedAnalysisHelpPanel {...props} title={props.title ?? `${title} 설명`}
    explain={explain ? { ...explain, title } : explain} hideMetadata
    content={props.content ?? (explain ? <LandHelpContent explain={explain} /> : undefined)} />;
}
