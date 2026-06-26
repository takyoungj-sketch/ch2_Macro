import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import type { AiChatResponse, AiContextPayload, AiPurpose } from "./aiClient";
import { fetchSuggestedQuestions, sendAiChat } from "./aiClient";

const PANEL_DISCLAIMER = "본 답변은 시장통계 해석이며 감정평가를 대체하지 않습니다.";

function parseSections(text: string): { title: string; body: string }[] | null {
  if (!text.includes("### ")) return null;
  const parts = text.split(/^### /m).filter(Boolean);
  return parts.map((block) => {
    const nl = block.indexOf("\n");
    if (nl === -1) return { title: block.trim(), body: "" };
    return { title: block.slice(0, nl).trim(), body: block.slice(nl + 1).trim() };
  });
}

function renderInline(text: string) {
  const chunks = text.split(/(\*\*[^*]+\*\*)/g);
  return chunks.map((chunk, i) => {
    if (chunk.startsWith("**") && chunk.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-slate-800">
          {chunk.slice(2, -2)}
        </strong>
      );
    }
    return <span key={i}>{chunk}</span>;
  });
}

function AnswerBody({ text }: { text: string }) {
  const sections = useMemo(() => parseSections(text), [text]);
  if (!sections) {
    return <span className="whitespace-pre-wrap">{renderInline(text)}</span>;
  }
  return (
    <div className="space-y-2.5 mt-1">
      {sections.map((s) => {
        const isInsight = s.title.includes("AI Insight");
        const isTable = s.title === "주요 변수" && s.body.includes("|");
        return (
          <div key={s.title}>
            {!isInsight && (
              <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-0.5">
                {s.title}
              </div>
            )}
            {isInsight ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50/80 px-3 py-2">
                <div className="text-[10px] font-semibold text-amber-800 mb-1">💡 AI Insight</div>
                <div className="text-slate-700 leading-relaxed whitespace-pre-wrap text-[11px]">
                  {s.body.split("\n").map((line, i) => (
                    <p key={i}>{renderInline(line)}</p>
                  ))}
                </div>
              </div>
            ) : isTable ? (
              <div
                className="prose prose-xs max-w-none text-slate-700 [&_table]:text-[11px] [&_td]:px-2 [&_th]:px-2"
                dangerouslySetInnerHTML={{
                  __html: s.body
                    .split("\n\n")
                    .map((part) =>
                      part.startsWith("|")
                        ? `<table class="border-collapse border border-slate-200 w-full">${part
                            .split("\n")
                            .filter((row) => !row.match(/^\|[-| ]+\|$/))
                            .map((row, ri) => {
                              const cells = row.split("|").filter(Boolean);
                              const tag = ri === 0 ? "th" : "td";
                              return `<tr>${cells.map((c) => `<${tag} class="border border-slate-200">${c.trim()}</${tag}>`).join("")}</tr>`;
                            })
                            .join("")}</table>`
                        : `<p class="mt-2 text-[11px]">${part.replace(/^- /, "• ")}</p>`,
                    )
                    .join(""),
                }}
              />
            ) : (
              <div className="whitespace-pre-wrap text-slate-700 leading-relaxed">
                {s.body.split("\n").map((line, i) => (
                  <p key={i} className={line.startsWith("- ") ? "pl-0" : ""}>
                    {renderInline(line.replace(/^- /, "• "))}
                  </p>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function trustLabel(level: "high" | "medium" | "low") {
  if (level === "high") return "높음";
  if (level === "medium") return "보통";
  return "낮음";
}

function trustDot(level: "high" | "medium" | "low") {
  if (level === "high") return "🟢";
  if (level === "medium") return "🟡";
  return "🔴";
}

function TrustBadge({
  level,
  sources,
  aiInterpretation,
  llmUsed,
  scopeHint,
  webEvidence,
}: {
  level: "high" | "medium" | "low";
  sources: string[];
  aiInterpretation?: string | null;
  llmUsed?: boolean;
  scopeHint: string;
  webEvidence?: { label: string; url?: string | null }[];
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const dataSources =
    sources.length > 0
      ? sources.map((s) => `✓ CH2 ${s.replace(/^CH2\s*/, "")}`)
      : ["✓ CH2 회귀분석", "✓ CH2 VIF", "✓ CH2 상관"];

  return (
    <div className="relative shrink-0" ref={ref}>
      <button
        type="button"
        className="flex items-center gap-1 text-[10px] px-2 py-1 rounded-full border border-slate-200 bg-white hover:bg-slate-50 text-slate-600"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span>{trustDot(level)}</span>
        <span className="font-medium">AI 신뢰도</span>
        <span className="text-slate-400">{trustLabel(level)}</span>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-[110] w-56 rounded-lg border border-slate-200 bg-white shadow-lg p-3 text-[10px] text-slate-600 space-y-2">
          <p className="font-semibold text-slate-800">사용한 데이터</p>
          <ul className="space-y-0.5">
            {dataSources.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <div className="border-t border-slate-100 pt-2">
            <p className="font-semibold text-slate-800 mb-0.5">AI 해석</p>
            <p>{llmUsed ? aiInterpretation ?? "GPT" : aiInterpretation ?? "CH2 템플릿"}</p>
            <p className="text-slate-400 mt-1">
              {webEvidence?.length
                ? `웹검색 · ${webEvidence.length}건`
                : "웹검색 · 사용 안 함"}
            </p>
            {webEvidence && webEvidence.length > 0 && (
              <ul className="mt-1 space-y-0.5 max-h-24 overflow-y-auto">
                {webEvidence.slice(0, 4).map((w) => (
                  <li key={w.url ?? w.label} className="truncate">
                    {w.url ? (
                      <a
                        href={w.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline"
                      >
                        {w.label}
                      </a>
                    ) : (
                      w.label
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <p className="text-slate-400 border-t border-slate-100 pt-2">{scopeHint}</p>
        </div>
      )}
    </div>
  );
}

function deriveTrustFromContext(context: AiContextPayload): {
  level: "high" | "medium" | "low";
  sources: string[];
} {
  const primary = (context.facts?.primary ?? context.facts) as Record<string, unknown> | undefined;
  const n = primary?.n as number | undefined;
  const adj = primary?.adj_r_squared as number | undefined;
  const sources = ["회귀분석 결과"];
  if (primary?.vif || context.facts?.vif) sources.push("다중공선성(VIF)");
  if (context.facts?.correlations) sources.push("변수간 상관관계");

  let level: "high" | "medium" | "low" = "high";
  if (n != null && n < 50) level = "low";
  else if (n != null && n < 200) level = "medium";
  if (adj != null && adj < 0.4) level = level === "high" ? "low" : level;
  return { level, sources };
}

function AiAssistantModal({
  open,
  onClose,
  context,
}: {
  open: boolean;
  onClose: () => void;
  context: AiContextPayload;
}) {
  const [purpose, setPurpose] = useState<AiPurpose>(context.purpose);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggested, setSuggested] = useState<string[]>([]);
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; text: string; meta?: AiChatResponse }[]>(
    [],
  );
  const [lastMeta, setLastMeta] = useState<AiChatResponse | null>(null);

  const baseTrust = useMemo(() => deriveTrustFromContext(context), [context]);

  useEffect(() => {
    if (!open) return;
    fetchSuggestedQuestions(context.panel, purpose, context.app)
      .then(setSuggested)
      .catch(() => setSuggested([]));
  }, [context.panel, purpose, context.app, open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const runChat = useCallback(
    async (text: string) => {
      const q = text.trim();
      if (!q || loading) return;
      setLoading(true);
      setError(null);
      setMessages((m) => [...m, { role: "user", text: q }]);
      setInput("");
      try {
        const ctx = { ...context, purpose };
        const resp = await sendAiChat(q, ctx, sessionId);
        setSessionId(resp.session_id);
        setLastMeta(resp);
        setMessages((m) => [...m, { role: "assistant", text: resp.answer, meta: resp }]);
        if (resp.suggested_followups?.length) {
          setSuggested(resp.suggested_followups);
        }
      } catch (e) {
        setError((e as Error).message ?? "AI 요청 실패");
      } finally {
        setLoading(false);
      }
    },
    [context, loading, purpose, sessionId],
  );

  if (!open) return null;

  const scopeHint = context.scope?.region_label ?? "현재 scope";
  const trustLevel = lastMeta?.trust_level ?? baseTrust.level;
  const trustSources = lastMeta?.trust_sources?.length ? lastMeta.trust_sources : baseTrust.sources;
  const webEvidence =
    lastMeta?.evidence
      ?.filter((e) => e.type === "web" && e.url)
      .map((e) => ({ label: e.label, url: e.url })) ?? [];

  return (
    <div
      className="fixed inset-0 z-[100] bg-black/35"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ai-assistant-modal-title"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 modal-shell rounded-xl shadow-xl max-w-2xl w-[calc(100%-2rem)] max-h-[85vh] flex flex-col border bg-white border-slate-200"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="px-4 py-3 border-b border-slate-100 shrink-0">
          <div className="flex justify-between items-start gap-2">
            <div className="min-w-0">
              <h2 id="ai-assistant-modal-title" className="text-sm font-bold">
                통계 분석 어시스턴트
              </h2>
              <p className="text-[11px] text-slate-500 mt-0.5 truncate">{scopeHint}</p>
            </div>
            <div className="flex items-start gap-2">
              <TrustBadge
                level={trustLevel}
                sources={trustSources}
                aiInterpretation={lastMeta?.ai_interpretation}
                llmUsed={lastMeta?.llm_used}
                scopeHint={scopeHint}
                webEvidence={webEvidence}
              />
              <button
                type="button"
                aria-label="닫기"
                className="text-slate-400 hover:text-slate-700 text-xl leading-none px-1 shrink-0"
                onClick={onClose}
              >
                ×
              </button>
            </div>
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto px-4 py-3 space-y-3 text-xs">
          <div className="flex flex-wrap gap-2 items-center">
            <span className="text-slate-500">목적</span>
            {(
              [
                ["statistics", "통계 해석"],
                ["prediction", "예측"],
                ["market_analysis", "시장 패턴"],
                ["methodology", "방법론"],
              ] as const
            ).map(([v, label]) => (
              <button
                key={v}
                type="button"
                className={clsx(
                  "px-2 py-0.5 rounded border",
                  purpose === v
                    ? "bg-slate-800 text-white border-slate-800"
                    : "bg-white text-slate-600 border-slate-200",
                )}
                onClick={() => setPurpose(v)}
              >
                {label}
              </button>
            ))}
          </div>

          {suggested.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-1">
                다음 질문
              </p>
              <div className="flex flex-wrap gap-1.5">
                {suggested.map((q) => (
                  <button
                    key={q}
                    type="button"
                    className="text-left px-2 py-1 rounded border border-slate-200 hover:border-slate-400 text-slate-700"
                    disabled={loading}
                    onClick={() => runChat(q)}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="min-h-[12rem] max-h-[40vh] overflow-y-auto space-y-3 border border-slate-100 rounded-lg p-3 bg-slate-50/50">
            {messages.length === 0 && (
              <p className="text-slate-400 text-center py-8">질문을 선택하거나 입력하세요.</p>
            )}
            {messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "text-slate-800" : "text-slate-700"}>
                {m.role === "user" ? (
                  <>
                    <span className="font-medium text-slate-500">Q </span>
                    <span>{m.text}</span>
                  </>
                ) : (
                  <AnswerBody text={m.text} />
                )}
              </div>
            ))}
          </div>

          {error && <p className="text-red-600">{error}</p>}
        </div>

        <div className="shrink-0 px-4 py-3 border-t border-slate-100 space-y-2">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              runChat(input);
            }}
          >
            <input
              className="input flex-1 text-xs py-1.5 border border-slate-200 rounded px-2"
              placeholder="질문 입력…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
              autoFocus
            />
            <button
              type="submit"
              className="btn btn-primary text-xs py-1.5 px-3 rounded bg-slate-800 text-white disabled:opacity-50"
              disabled={loading || !input.trim()}
            >
              {loading ? "…" : "전송"}
            </button>
          </form>
          <p className="text-[10px] text-slate-400 bg-slate-100 rounded px-2 py-1.5">{PANEL_DISCLAIMER}</p>
        </div>
      </div>
    </div>
  );
}

export default function AiAssistantPanel({
  context,
  className,
}: {
  context: AiContextPayload;
  className?: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        className={clsx("btn btn-ghost shrink-0", className)}
        onClick={() => setOpen(true)}
      >
        AI 어시스턴트
      </button>
      <AiAssistantModal open={open} onClose={() => setOpen(false)} context={context} />
    </>
  );
}
