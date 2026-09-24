import { useEffect, useState } from "react";
import AiAssistantPanel from "@ch2/ai-assistant/AiAssistantPanel";
import { ActiveAiViewProvider, emptyAiContext } from "@ch2/ai-assistant/ActiveAiView";
import InsightHome from "./pages/InsightHome";
import Insight01 from "./pages/Insight01";
import Insight02 from "./pages/Insight02";
import Insight03 from "./pages/Insight03";
import Insight04 from "./pages/Insight04";
import Insight05 from "./pages/Insight05";
import Insight06 from "./pages/Insight06";
import Insight07 from "./pages/Insight07";
import Insight08 from "./pages/Insight08";
import Insight10 from "./pages/Insight10";
import Insight11 from "./pages/Insight11";

function readQ(): string | null {
  return new URLSearchParams(window.location.search).get("q");
}

export default function App() {
  const [q, setQ] = useState<string | null>(() => readQ());

  useEffect(() => {
    const onPop = () => setQ(readQ());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const panel =
    q === "1"
      ? "Insight01"
      : q === "2"
        ? "Insight02"
        : q === "3"
          ? "Insight03"
          : q === "4"
            ? "Insight04"
            : q === "5"
              ? "Insight05"
              : q === "6"
                ? "Insight06"
                : q === "7"
                  ? "Insight07"
                  : q === "8"
                    ? "Insight08"
                    : q === "10"
                      ? "Insight10"
                      : q === "11"
                        ? "Insight11"
                        : "InsightHome";

  return (
    <ActiveAiViewProvider fallback={emptyAiContext("insight", panel, { regionLabel: "전국" })}>
      <div className="min-h-screen">
        <header className="border-b border-slate-200 bg-white/90 dark:border-slate-700 dark:bg-slate-800/90">
          <div className="max-w-4xl mx-auto px-4 py-4 flex items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                <a href="/" className="hover:text-slate-800 dark:hover:text-slate-200">
                  CH2 Macro
                </a>
                <span className="mx-1.5 text-slate-300">·</span>
                베타
              </p>
              <h1 className="text-xl font-bold mt-0.5">
                <a href="/insight/" className="hover:text-slate-700 dark:hover:text-slate-200">
                  Macro Insight
                </a>
              </h1>
            </div>
            <AiAssistantPanel />
          </div>
        </header>
        {q === "1" ? (
          <Insight01 />
        ) : q === "2" ? (
          <Insight02 />
        ) : q === "3" ? (
          <Insight03 />
        ) : q === "4" ? (
          <Insight04 />
        ) : q === "5" ? (
          <Insight05 />
        ) : q === "6" ? (
          <Insight06 />
        ) : q === "7" ? (
          <Insight07 />
        ) : q === "8" ? (
          <Insight08 />
        ) : q === "10" ? (
          <Insight10 />
        ) : q === "11" ? (
          <Insight11 />
        ) : (
          <InsightHome />
        )}
      </div>
    </ActiveAiViewProvider>
  );
}
