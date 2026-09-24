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
          <li>
            <a
              href="/insight/?q=2"
              className="block card p-4 hover:border-slate-400 dark:hover:border-slate-500"
            >
              <p className="text-xs text-slate-500 mb-1">2</p>
              <p className="font-semibold text-slate-900 dark:text-slate-50 leading-snug">
                {INSIGHT_02.listTitle}
              </p>
              <p className="text-sm text-slate-500 mt-1">{INSIGHT_02.listSub}</p>
            </a>
          </li>
          <li>
            <a
              href="/insight/?q=3"
              className="block card p-4 hover:border-slate-400 dark:hover:border-slate-500"
            >
              <p className="text-xs text-slate-500 mb-1">3</p>
              <p className="font-semibold text-slate-900 dark:text-slate-50 leading-snug">
                {INSIGHT_03.listTitle}
              </p>
              <p className="text-sm text-slate-500 mt-1">{INSIGHT_03.listSub}</p>
            </a>
          </li>
          <li>
            <a
              href="/insight/?q=4"
              className="block card p-4 hover:border-slate-400 dark:hover:border-slate-500"
            >
              <p className="text-xs text-slate-500 mb-1">4</p>
              <p className="font-semibold text-slate-900 dark:text-slate-50 leading-snug">
                {INSIGHT_04.listTitle}
              </p>
              <p className="text-sm text-slate-500 mt-1">{INSIGHT_04.listSub}</p>
            </a>
          </li>
          <li>
            <a
              href="/insight/?q=5"
              className="block card p-4 hover:border-slate-400 dark:hover:border-slate-500"
            >
              <p className="text-xs text-slate-500 mb-1">5</p>
              <p className="font-semibold text-slate-900 dark:text-slate-50 leading-snug">
                {INSIGHT_05.listTitle}
              </p>
              <p className="text-sm text-slate-500 mt-1">{INSIGHT_05.listSub}</p>
            </a>
          </li>
          <li>
            <a
              href="/insight/?q=6"
              className="block card p-4 hover:border-slate-400 dark:hover:border-slate-500"
            >
              <p className="text-xs text-slate-500 mb-1">6</p>
              <p className="font-semibold text-slate-900 dark:text-slate-50 leading-snug">
                {INSIGHT_06.listTitle}
              </p>
              <p className="text-sm text-slate-500 mt-1">{INSIGHT_06.listSub}</p>
            </a>
          </li>
          <li>
            <a
              href="/insight/?q=7"
              className="block card p-4 hover:border-slate-400 dark:hover:border-slate-500"
            >
              <p className="text-xs text-slate-500 mb-1">7</p>
              <p className="font-semibold text-slate-900 dark:text-slate-50 leading-snug">
                {INSIGHT_07.listTitle}
              </p>
              <p className="text-sm text-slate-500 mt-1">{INSIGHT_07.listSub}</p>
            </a>
          </li>
          <li>
            <a
              href="/insight/?q=8"
              className="block card p-4 hover:border-slate-400 dark:hover:border-slate-500"
            >
              <p className="text-xs text-slate-500 mb-1">8</p>
              <p className="font-semibold text-slate-900 dark:text-slate-50 leading-snug">
                {INSIGHT_08.listTitle}
              </p>
              <p className="text-sm text-slate-500 mt-1">{INSIGHT_08.listSub}</p>
            </a>
          </li>
          <li>
            <a
              href="/insight/?q=10"
              className="block card p-4 hover:border-slate-400 dark:hover:border-slate-500"
            >
              <p className="text-xs text-slate-500 mb-1">10</p>
              <p className="font-semibold text-slate-900 dark:text-slate-50 leading-snug">
                {INSIGHT_10.listTitle}
              </p>
              <p className="text-sm text-slate-500 mt-1">{INSIGHT_10.listSub}</p>
            </a>
          </li>
          <li>
            <a
              href="/insight/?q=11"
              className="block card p-4 hover:border-slate-400 dark:hover:border-slate-500"
            >
              <p className="text-xs text-slate-500 mb-1">11</p>
              <p className="font-semibold text-slate-900 dark:text-slate-50 leading-snug">
                {INSIGHT_11.listTitle}
              </p>
              <p className="text-sm text-slate-500 mt-1">{INSIGHT_11.listSub}</p>
            </a>
          </li>
          <li>
            <a
              href="/insight/?q=12"
              className="block card p-4 hover:border-slate-400 dark:hover:border-slate-500"
            >
              <p className="text-xs text-slate-500 mb-1">12</p>
              <p className="font-semibold text-slate-900 dark:text-slate-50 leading-snug">
                {INSIGHT_12.listTitle}
              </p>
              <p className="text-sm text-slate-500 mt-1">{INSIGHT_12.listSub}</p>
            </a>
          </li>
        </ol>
      </main>
    </>
  );
}
