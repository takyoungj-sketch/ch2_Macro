import type { ComponentProps } from "react";
import { AnalysisHelpPanel as SharedAnalysisHelpPanel } from "@ch2/analysis-help";
import { BUILT_SETTINGS_COPY, type SettingsHelpSection } from "../utils/builtRegressionSettingsCopy";
import BuiltHelpContent from "./BuiltHelpContent";
import { builtHelpIntro } from "../utils/builtHelpPresentation";

function SectionBody({ section }: { section: SettingsHelpSection }) {
  if (section.bullets) return <ul className="list-disc pl-5 space-y-2 leading-relaxed">
    {section.entries.map(entry => <li key={entry.text}>{entry.text}</li>)}
  </ul>;
  return <div className="space-y-4 leading-relaxed">{section.entries.map(entry => <div key={entry.text}>
    {entry.label && <p className="mb-1.5 font-semibold text-slate-700 dark:text-slate-200">{entry.label}</p>}
    <p>{entry.text}</p>
  </div>)}</div>;
}

export default function AnalysisHelpPanel(props: ComponentProps<typeof SharedAnalysisHelpPanel>) {
  const copy = props.explain && BUILT_SETTINGS_COPY[props.explain.spec_id];
  if (!copy) {
    const explain = props.explain;
    const title = explain ? builtHelpIntro(explain)?.title ?? explain.title : "도움말";
    return <SharedAnalysisHelpPanel {...props} title={props.title ?? `${title} 설명`} explain={explain ? { ...explain, title } : explain} hideMetadata content={props.content ?? (explain ? <BuiltHelpContent explain={explain} /> : undefined)} />;
  }
  return <SharedAnalysisHelpPanel {...props} hideMetadata content={
    <div className="space-y-6 text-slate-600 dark:text-slate-300">
      <p className="leading-relaxed">{copy.explain.summary}</p>
      {copy.sections.map(section => section.collapsed
        ? <details key={section.title} className="rounded-lg border border-slate-200 p-3 dark:border-slate-600">
            <summary className="cursor-pointer font-medium">{section.title}</summary>
            <div className="mt-3"><SectionBody section={section} /></div>
          </details>
        : <section key={section.title} className="space-y-3">
            <h4 className="font-semibold text-slate-800 dark:text-slate-100" style={{ fontSize: "1.05em" }}>{section.title}</h4>
            <SectionBody section={section} />
          </section>)}
    </div>
  } />;
}
