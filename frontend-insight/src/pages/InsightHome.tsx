import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { INSIGHT_01 } from "../copy/insight01";
import { INSIGHT_02 } from "../copy/insight02";
import { INSIGHT_03 } from "../copy/insight03";
import { INSIGHT_04 } from "../copy/insight04";
import { INSIGHT_05 } from "../copy/insight05";
import { INSIGHT_06 } from "../copy/insight06";
import { INSIGHT_07 } from "../copy/insight07";
import { INSIGHT_08 } from "../copy/insight08";
import { INSIGHT_10 } from "../copy/insight10";
import { INSIGHT_11 } from "../copy/insight11";
import { INSIGHT_12 } from "../copy/insight12";

const homeCtx = {
  app: "insight" as const,
  panel: "InsightHome",
  purpose: "statistics" as const,
  scope: { region_label: "전국" },
  facts: {},
  explain: {
    spec_id: "insight_home",
    spec_version: "1",
    title: "Macro Insight",
    summary: "Macro Insight는 질문 목록입니다. 시장에 무엇을 물어봤는지 모아 둔 창입니다.",
    limitations: ["이 창에서 시세나 전망을 구하지 않습니다."],
  },
};

const homeItems = [
  { q: "1", copy: INSIGHT_05 },
  { q: "2", copy: INSIGHT_01 },
  { q: "3", copy: INSIGHT_02 },
  { q: "4", copy: INSIGHT_11 },
  { q: "5", copy: INSIGHT_12 },
  { q: "6", copy: INSIGHT_07 },
  { q: "7", copy: INSIGHT_04 },
  { q: "8", copy: INSIGHT_06 },
  { q: "9", copy: INSIGHT_08 },
  { q: "10", copy: INSIGHT_03 },
  { q: "11", copy: INSIGHT_10 },
];

export default function InsightHome() {
  return (
    <>
      <PublishAiContext context={homeCtx} />
      <main className="max-w-3xl mx-auto px-4 py-8">
        <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed mb-6">
          시장에 무엇을 물어봤는지 모아 둔 창입니다. 지금 올라 있는 글은 데이터를 따라 질문을 살펴본
          기록이며, 같은 질문에 분석을 더하면 내용이 이어질 수 있습니다.
        </p>
        <ol className="space-y-3">
          {homeItems.map((item) => (
            <li key={item.q}>
              <a
                href={`/insight/?q=${item.q}`}
                className="block card p-4 hover:border-slate-400 dark:hover:border-slate-500"
              >
                <p className="text-xs text-slate-500 mb-1">{item.q}</p>
                <p className="font-semibold text-slate-900 dark:text-slate-50 leading-snug">
                  {item.copy.listTitle}
                </p>
                <p className="text-sm text-slate-500 mt-1">{item.copy.listSub}</p>
              </a>
            </li>
          ))}
        </ol>
        <p className="mt-8 text-sm text-center">
          <a
            href="https://ch2data.com/learn/stats/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-indigo-700 dark:text-indigo-300 font-medium hover:underline"
          >
            통계학 &amp; 데이터 분석 — Macro 용어·개념 설명 →
          </a>
        </p>
      </main>
    </>
  );
}
