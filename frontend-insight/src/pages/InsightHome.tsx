import { PublishAiContext } from "@ch2/ai-assistant/ActiveAiView";
import { INSIGHT_01 } from "../copy/insight01";

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
          <li>
            <a
              href="/insight/?q=1"
              className="block card p-4 hover:border-slate-400 dark:hover:border-slate-500"
            >
              <p className="text-xs text-slate-500 mb-1">1</p>
              <p className="font-semibold text-slate-900 dark:text-slate-50 leading-snug">
                {INSIGHT_01.listTitle}
              </p>
              <p className="text-sm text-slate-500 mt-1">{INSIGHT_01.listSub}</p>
            </a>
          </li>
        </ol>
      </main>
    </>
  );
}
