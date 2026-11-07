// @ts-nocheck — React resolves through each frontend's runtime, as in the shared header.
import GuideDialog from "./GuideDialog";

export interface AnalysisGuideContent {
  id: string;
  storageKey: string;
  title: string;
  triggerLabel: string;
  actionLabel: string;
  tagline: string;
  summary: string;
  features: { title: string; description: string }[];
  steps: string[];
  notes: string[];
}

const icons = [
  "M4 4h16v16H4zM4 10h16M10 4v16",
  "M4 6h16M4 12h16M4 18h16M9 4v4m6 2v4m-5 2v4",
  "m4 13 5-5 4 3 7-7M6 20v-4m4 4v-7m4 7v-5m4 5v-9",
];

export default function AnalysisGuide({ content }: { content: AnalysisGuideContent }) {
  return (
    <GuideDialog
      key={content.id}
      id={content.id}
      storageKey={content.storageKey}
      title={content.title}
      triggerLabel={content.triggerLabel}
      actionLabel={content.actionLabel}
    >
      <p className="analysis-guide__tagline">{content.tagline}</p>
      <p id={`${content.id}-summary`}>{content.summary}</p>
      <section className="analysis-guide__section">
        <h3>주요 기능</h3>
        <ul className="analysis-guide__features">
          {content.features.map(({ title, description }, index) => (
            <li key={title}>
              <svg
                aria-hidden="true"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d={icons[index % icons.length]} />
              </svg>
              <div>
                <h4>{title}</h4>
                <p>{description}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>
      <section className="analysis-guide__section">
        <h3>사용방법</h3>
        <ol className="analysis-guide__steps">
          {content.steps.map(step => <li key={step}>{step}</li>)}
        </ol>
      </section>
      <section className="analysis-guide__note">
        <h3>분석할 때 유의하세요</h3>
        <ul>
          {content.notes.map(note => <li key={note}>{note}</li>)}
        </ul>
      </section>
    </GuideDialog>
  );
}
