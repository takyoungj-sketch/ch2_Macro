// @ts-nocheck — 공유 JSX는 각 앱의 React 런타임 경로로 번들링합니다.
import type { ReactNode } from "react";
import type { AnalysisExplain } from "./types";

export type ReadableHelpIntro = { title?: string; summary: string; points: string[]; notes?: string[] };

export function createReadableHelpContent(getIntro: (explain: AnalysisExplain) => ReadableHelpIntro | undefined, helpText: (text: string) => string = text => text) {

function List({ items }: { items: string[] }) {
  return <ul className="list-disc pl-5 space-y-2 leading-relaxed">{items.filter(item => item?.trim()).map((item, i) => <li key={i}>{helpText(item)}</li>)}</ul>;
}
function Fold({ title, children }: { title: string; children: ReactNode }) {
  return <details className="rounded-lg border border-slate-200 p-3 dark:border-slate-600"><summary className="cursor-pointer font-medium">{title}</summary><div className="mt-3 space-y-3 leading-relaxed">{children}</div></details>;
}

return function ReadableHelpContent({ explain, learnUrl }: { explain: AnalysisExplain; learnUrl?: string }) {
  const intro = getIntro(explain);
  const interpretation = explain.interpretation?.filter(item => item?.trim()) ?? [];
  const points = intro?.points ?? interpretation.slice(0, 3);
  const more = intro ? interpretation : interpretation.slice(3);
  const notes = intro?.notes ?? explain.limitations?.filter(item => item?.trim()).slice(0, 2) ?? [];
  const extraNotes = intro ? explain.limitations ?? [] : explain.limitations?.slice(2) ?? [];
  const controls = explain.controls?.filter(item => item?.trim()) ?? [];
  const hints = explain.interpretation_hints?.filter(item => item?.trim()) ?? [];
  const presets = explain.presets?.filter(item => item.question?.trim() && item.answer?.trim()) ?? [];
  const hasMethod = Boolean(explain.formula || explain.index_rule || explain.reference || explain.floor_groups?.length);
  return <div className="space-y-5 text-slate-600 dark:text-slate-300">
    {(intro?.summary || explain.summary)?.trim() && <p className="leading-relaxed">{helpText(intro?.summary ?? explain.summary)}</p>}
    {points.length > 0 && <section className="space-y-3"><h4 className="font-semibold text-slate-800 dark:text-slate-100">확인할 내용</h4><List items={points} /></section>}
    {notes.length > 0 && <section className="space-y-3"><h4 className="font-semibold text-slate-800 dark:text-slate-100">알아두세요</h4><List items={notes} /></section>}
    {hints.length > 0 && <section className="space-y-3"><h4 className="font-semibold text-slate-800 dark:text-slate-100">현재 결과에서 확인할 점</h4><List items={hints} /></section>}
    {controls.length > 0 && <Fold title={explain.spec_id.includes(".glossary.") ? "참고 기준" : "포함·제외 기준"}><List items={controls} /></Fold>}
    {hasMethod && <Fold title="계산 기준 자세히 보기">
      {explain.formula && <p className="whitespace-pre-wrap break-words rounded bg-slate-50 p-2 dark:bg-slate-900/60">{helpText(explain.formula)}</p>}
      {explain.index_rule && <p>{helpText(explain.index_rule)}</p>}{explain.reference && <p>{helpText(explain.reference)}</p>}
      {explain.floor_groups?.length ? <List items={explain.floor_groups} /> : null}
    </Fold>}
    {(more.length > 0 || extraNotes.length > 0) && <Fold title={explain.spec_id.includes("cv") ? "검증 범위와 추가 설명" : "상세 설명 더 보기"}><List items={more} /><List items={extraNotes} /></Fold>}
    {presets.length > 0 && <section className="space-y-3"><h4 className="font-semibold text-slate-800 dark:text-slate-100">자주 묻는 질문</h4>{presets.map(preset => <Fold key={preset.id} title={helpText(preset.question)}><p>{helpText(preset.answer)}</p></Fold>)}</section>}
    {learnUrl && <p className="border-t border-slate-200 pt-3 dark:border-slate-600"><a href={learnUrl} target="_blank" rel="noopener noreferrer" className="text-indigo-700 underline dark:text-indigo-300">통계 설명에서 더 알아보기</a></p>}
  </div>;
}

}
