import { useState, type ReactNode } from "react";
import clsx from "clsx";
import type { AnalysisExplain } from "../types";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-1">
      <h4 className="text-[11px] font-semibold text-slate-700">{title}</h4>
      <div className="text-[11px] text-slate-600 leading-relaxed">{children}</div>
    </section>
  );
}

function BulletList({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <ul className="list-disc list-inside space-y-0.5">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

export default function AnalysisHelpPanel({
  explain,
  className,
}: {
  explain: AnalysisExplain | null | undefined;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [activePreset, setActivePreset] = useState<string | null>(null);

  if (!explain) return null;

  return (
    <div className={clsx("relative", className)}>
      <button
        type="button"
        title="분석 방법·해석·한계 설명"
        aria-expanded={open}
        aria-label="분석 설명 열기"
        className={clsx(
          "inline-flex h-6 w-6 items-center justify-center rounded-full border text-[11px] font-bold transition-colors",
          open
            ? "border-indigo-300 bg-indigo-50 text-indigo-700"
            : "border-slate-200 bg-white text-slate-500 hover:border-indigo-200 hover:text-indigo-600",
        )}
        onClick={() => setOpen((v) => !v)}
      >
        ?
      </button>

      {open && (
        <div className="absolute right-0 top-full z-20 mt-1 w-[min(420px,calc(100vw-3rem))] rounded-lg border border-indigo-100 bg-indigo-50/95 shadow-lg p-3 space-y-3 max-h-[min(420px,55vh)] overflow-y-auto">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-xs font-semibold text-slate-800">{explain.title}</p>
              <p className="text-[10px] text-slate-500 mt-0.5">
                spec: {explain.spec_id} · v{explain.spec_version}
              </p>
            </div>
            <button
              type="button"
              className="text-[10px] text-slate-400 hover:text-slate-600 shrink-0"
              onClick={() => setOpen(false)}
            >
              닫기
            </button>
          </div>

          <Section title="요약">
            <p>{explain.summary}</p>
          </Section>

          {explain.formula && (
            <Section title="공식">
              <p className="font-mono text-[10px] bg-white/80 border border-slate-100 rounded px-2 py-1.5 whitespace-pre-wrap">
                {explain.formula}
              </p>
              {explain.index_rule && (
                <p className="mt-1 text-[10px] text-slate-500">지수: {explain.index_rule}</p>
              )}
              {explain.reference && (
                <p className="mt-0.5 text-[10px] text-slate-500">기준: {explain.reference}</p>
              )}
            </Section>
          )}

          {explain.floor_groups && explain.floor_groups.length > 0 && (
            <Section title="집계 단위">
              <BulletList items={explain.floor_groups} />
            </Section>
          )}

          {explain.controls && explain.controls.length > 0 && (
            <Section title="포함·제외 조건">
              <BulletList items={explain.controls} />
            </Section>
          )}

          <Section title="해석 방법">
            <BulletList items={explain.interpretation} />
          </Section>

          {explain.interpretation_hints && explain.interpretation_hints.length > 0 && (
            <Section title="이번 결과 기준">
              <ul className="space-y-1">
                {explain.interpretation_hints.map((hint) => (
                  <li
                    key={hint}
                    className={clsx(
                      "text-[11px] pl-2 border-l-2",
                      hint.startsWith("⚠")
                        ? "border-amber-400 text-amber-900"
                        : "border-indigo-300 text-slate-700",
                    )}
                  >
                    {hint}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          <Section title="한계·주의">
            <BulletList items={explain.limitations} />
          </Section>

          {explain.presets && explain.presets.length > 0 && (
            <Section title="자주 묻는 질문">
              <div className="space-y-1">
                {explain.presets.map((p) => (
                  <div key={p.id} className="rounded border border-slate-100 bg-white/70 overflow-hidden">
                    <button
                      type="button"
                      className="w-full text-left px-2 py-1.5 text-[11px] font-medium text-slate-700 hover:bg-slate-50"
                      onClick={() => setActivePreset(activePreset === p.id ? null : p.id)}
                    >
                      {p.question}
                    </button>
                    {activePreset === p.id && (
                      <p className="px-2 pb-2 text-[11px] text-slate-600 border-t border-slate-50">
                        {p.answer}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </Section>
          )}
        </div>
      )}
    </div>
  );
}
