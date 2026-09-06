// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import clsx from "clsx";
import type { AiChatResponse, AiContextPayload, EvidenceItem } from "./aiClient";
import { isAiChatAborted, readAiSessionId, sendAiChat } from "./aiClient";
import { emptyAiContext, useActiveAiView } from "./ActiveAiView";
import { setAiChatOpen } from "./aiHost";
import {
  applyAiScreenAction,
  CH2_AI_ENGINE_DONE_EVENT,
  type AiScreenAction,
} from "./aiActions";
import {
  clampBox,
  persistBox,
  readStoredBox,
  ResizeHandles,
  usePanelDrag,
} from "../ui-window/resizableWindow";

type ChatMessage = { role: "user" | "assistant"; text: string; meta?: AiChatResponse };

const PANEL_DISCLAIMER = "본 답변은 시장통계 해석이며 감정평가를 대체하지 않습니다.";

const PURPOSE_COPY =
  "CH2 데이터와 기능을 이해하고, 분석 목적에 맞는 경로를 제안하며, 엔진이 낸 결과를 해석합니다. 숫자는 CH2가 계산한 값만 인용합니다.";

const LIMITS_COPY =
  "감정평가·적정가·투자·매수 추천에는 답하지 않습니다. 분석 경로 추천은 가능합니다. 실험 기간 서버 전체 월 200회·1만 원 한도이며, 한도에 닿으면 멈춥니다.";

const ENTRY_CHIPS = [
  {
    id: "now",
    label: "지금 결과가 궁금해",
    q: "이 화면의 분석 결과를 설명해 주세요.",
  },
  {
    id: "path",
    label: "이런 분석을 하고 싶어",
    q: "아파트와 오피스텔 가격 차이를 보고 싶어요.",
  },
  {
    id: "memo",
    label: "결과를 정리하고 싶어",
    q: "지금까지 실행한 분석을 정리해 주세요.",
  },
];

function ScreenActionButtons({
  actions,
  pendingId,
  onPending,
}: {
  actions: AiScreenAction[];
  pendingId: string | null;
  onPending: (id: string | null) => void;
}) {
  if (!actions?.length) return null;
  return (
    <div className="mt-3 space-y-1.5">
      <p className="text-[0.85em] font-semibold tracking-wide text-slate-500 dark:text-slate-400 mb-1">
        다음 단계 (기존 화면)
      </p>
      {actions.map((a) => {
        const confirming = pendingId === a.id;
        return (
          <div key={a.id}>
            {confirming && a.confirm_message ? (
              <p className="text-[0.9em] text-amber-800 dark:text-amber-200 mb-1">{a.confirm_message}</p>
            ) : null}
            <button
              type="button"
              className="text-left w-full px-3 py-2 rounded-lg border border-sky-300 bg-sky-50/80 hover:border-sky-500 text-[0.95em] text-slate-800 dark:border-sky-600 dark:bg-slate-800 dark:text-slate-100"
              onClick={() => {
                if (a.kind === "run_engine" && !confirming) {
                  onPending(a.id);
                  return;
                }
                onPending(null);
                if (a.kind === "run_engine") {
                  try {
                    sessionStorage.setItem("ch2-ai-expect-interpret", "1");
                  } catch {
                    /* ignore */
                  }
                }
                applyAiScreenAction(a);
              }}
            >
              {confirming ? "승인하고 실행" : a.label}
            </button>
          </div>
        );
      })}
    </div>
  );
}

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
        <strong key={i} className="font-semibold text-slate-800 dark:text-slate-100">
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
    return (
      <span className="whitespace-pre-wrap text-[1em] text-slate-700 dark:text-slate-200">{renderInline(text)}</span>
    );
  }
  return (
    <div className="space-y-2.5 mt-1 text-[1em] text-slate-700 dark:text-slate-200">
      {sections.map((s: { title: string; body: string }) => {
        const isInsight = s.title.includes("AI Insight");
        const isTable = s.title === "주요 변수" && s.body.includes("|");
        return (
          <div key={s.title}>
            {!isInsight && (
              <div className="text-[0.85em] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-0.5">
                {s.title}
              </div>
            )}
            {isInsight ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50/90 px-3 py-2 dark:border-amber-700/80 dark:bg-amber-950/55">
                <div className="text-[0.85em] font-semibold text-amber-900 dark:text-amber-200 mb-1">
                  💡 AI Insight
                </div>
                <div className="text-slate-800 dark:text-amber-50/95 leading-relaxed whitespace-pre-wrap text-[1em]">
                  {s.body.split("\n").map((line: string, i: number) => (
                    <p key={i}>{renderInline(line)}</p>
                  ))}
                </div>
              </div>
            ) : isTable ? (
              <div
                className="prose prose-xs max-w-none text-slate-700 dark:text-slate-200 [&_table]:text-[1em] [&_td]:px-2 [&_th]:px-2 [&_p]:text-slate-700 [&_p]:dark:text-slate-200"
                dangerouslySetInnerHTML={{
                  __html: s.body
                    .split("\n\n")
                    .map((part: string) =>
                      part.startsWith("|")
                        ? `<table class="border-collapse border border-slate-200 dark:border-slate-600 w-full text-slate-700 dark:text-slate-200">${part
                            .split("\n")
                            .filter((row: string) => !row.match(/^\|[-| ]+\|$/))
                            .map((row: string, ri: number) => {
                              const cells = row.split("|").filter(Boolean);
                              const tag = ri === 0 ? "th" : "td";
                              const cellClass =
                                tag === "th"
                                  ? ' class="border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-900/70 text-slate-700 dark:text-slate-100 font-semibold px-2 py-1"'
                                  : ' class="border border-slate-200 dark:border-slate-600 px-2 py-1"';
                              return `<tr>${cells.map((c: string) => `<${tag}${cellClass}>${c.trim()}</${tag}>`).join("")}</tr>`;
                            })
                            .join("")}</table>`
                        : `<p class="mt-2 text-[1em] text-slate-700 dark:text-slate-200">${part.replace(/^- /, "• ")}</p>`,
                    )
                    .join(""),
                }}
              />
            ) : (
              <div className="whitespace-pre-wrap leading-relaxed text-[1em]">
                {s.body.split("\n").map((line: string, i: number) => (
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
        className="flex items-center gap-1 text-[10px] px-2 py-1 rounded-full border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-200"
        onClick={() => setOpen((v: boolean) => !v)}
        aria-expanded={open}
      >
        <span>{trustDot(level)}</span>
        <span className="font-medium">AI 신뢰도</span>
        <span className="text-slate-400">{trustLabel(level)}</span>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-[110] w-56 rounded-lg border border-slate-200 bg-white shadow-lg p-3 text-[10px] text-slate-600 space-y-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:shadow-black/40">
          <p className="font-semibold text-slate-800 dark:text-slate-100">사용한 데이터</p>
          <ul className="space-y-0.5">
            {dataSources.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <div className="border-t border-slate-100 dark:border-slate-700 pt-2">
            <p className="font-semibold text-slate-800 dark:text-slate-100 mb-0.5">AI 해석</p>
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
                        className="text-blue-600 hover:underline dark:text-blue-400"
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
          <p className="text-slate-400 dark:text-slate-500 border-t border-slate-100 dark:border-slate-700 pt-2">{scopeHint}</p>
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

const DEFAULT_WIN = { w: 640, h: 560 };
const MIN_WIN = { w: 360, h: 320 };
const FONT_SCALES = [0.85, 1, 1.15, 1.3, 1.5] as const;
const FONT_STORAGE_KEY = "ch2-ai-font-scale";
const WIN_STORAGE_KEY = "ch2-ai-win-box";
const BASE_FONT_PX = 12;

function readStoredFontScale(): number {
  try {
    const v = Number(localStorage.getItem(FONT_STORAGE_KEY));
    if (FONT_SCALES.includes(v as (typeof FONT_SCALES)[number])) return v;
  } catch {
    /* ignore */
  }
  return 1;
}

function clampWin(next: { x: number; y: number; w: number; h: number }) {
  return clampBox(next, MIN_WIN.w, MIN_WIN.h);
}

function defaultWinPos() {
  const vw = typeof window !== "undefined" ? window.innerWidth : 1200;
  const vh = typeof window !== "undefined" ? window.innerHeight : 800;
  const stored = readStoredBox(WIN_STORAGE_KEY);
  return clampWin({
    x: stored?.x ?? Math.max(8, (vw - DEFAULT_WIN.w) / 2),
    y: stored?.y ?? Math.max(78, (vh - DEFAULT_WIN.h) / 2),
    w: stored?.w ?? DEFAULT_WIN.w,
    h: stored?.h ?? DEFAULT_WIN.h,
  });
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
  const [sessionId, setSessionId] = useState<string | null>(() => readAiSessionId());
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stoppedNotice, setStoppedNotice] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [lastMeta, setLastMeta] = useState<AiChatResponse | null>(null);
  const [win, setWin] = useState(defaultWinPos);
  const [fontScale, setFontScale] = useState(readStoredFontScale);
  const [pendingActionId, setPendingActionId] = useState<string | null>(null);
  const chatLogRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const loadingRef = useRef(false);
  const userStopRef = useRef(false);

  const baseTrust = useMemo(() => deriveTrustFromContext(context), [context]);

  const { beginMove, beginResize } = usePanelDrag(open, MIN_WIN.w, MIN_WIN.h, (next) => {
    setWin(next);
    persistBox(WIN_STORAGE_KEY, next);
  });

  useEffect(() => {
    if (!open) return;
    const clamp = () => {
      setWin((prev) => {
        const next = clampWin(prev);
        if (next.x === prev.x && next.y === prev.y && next.w === prev.w && next.h === prev.h) return prev;
        persistBox(WIN_STORAGE_KEY, next);
        return next;
      });
    };
    clamp();
    window.addEventListener("resize", clamp);
    return () => window.removeEventListener("resize", clamp);
  }, [open]);

  useEffect(() => {
    const el = chatLogRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, loading]);

  useEffect(() => {
    setAiChatOpen(open);
    return () => setAiChatOpen(false);
  }, [open]);

  const stopChat = useCallback(() => {
    userStopRef.current = true;
    abortRef.current?.abort();
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.preventDefault();
      e.stopPropagation();
      if (loadingRef.current) {
        stopChat();
        return;
      }
      onClose();
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open, onClose, stopChat]);

  const bumpFont = useCallback((dir: -1 | 1) => {
    setFontScale((cur) => {
      const idx = FONT_SCALES.findIndex((s) => s === cur);
      const next = FONT_SCALES[Math.min(FONT_SCALES.length - 1, Math.max(0, (idx < 0 ? 1 : idx) + dir))];
      try {
        localStorage.setItem(FONT_STORAGE_KEY, String(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  const runChat = useCallback(
    async (text: string) => {
      const q = text.trim();
      if (!q || loadingRef.current) return;
      userStopRef.current = false;
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;
      loadingRef.current = true;
      setLoading(true);
      setError(null);
      setStoppedNotice(false);
      setMessages((m: ChatMessage[]) => [...m, { role: "user", text: q }]);
      setInput("");
      try {
        const resp = await sendAiChat(q, context, sessionId, { signal: ac.signal });
        if (ac.signal.aborted) return;
        setSessionId(resp.session_id);
        setLastMeta(resp);
        setMessages((m: ChatMessage[]) => [...m, { role: "assistant", text: resp.answer, meta: resp }]);
      } catch (e) {
        if (isAiChatAborted(e) || ac.signal.aborted) {
          setError(null);
          if (userStopRef.current) setStoppedNotice(true);
          return;
        }
        setError((e as Error).message ?? "AI 요청 실패");
      } finally {
        if (abortRef.current === ac) abortRef.current = null;
        loadingRef.current = false;
        setLoading(false);
      }
    },
    [context, sessionId],
  );

  useEffect(() => {
    if (!open) abortRef.current?.abort();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onDone = () => {
      try {
        if (sessionStorage.getItem("ch2-ai-expect-interpret") !== "1") return;
        sessionStorage.removeItem("ch2-ai-expect-interpret");
      } catch {
        return;
      }
      window.setTimeout(() => {
        void runChat("이 화면의 분석 결과를 설명해 주세요.");
      }, 50);
    };
    window.addEventListener(CH2_AI_ENGINE_DONE_EVENT, onDone);
    return () => window.removeEventListener(CH2_AI_ENGINE_DONE_EVENT, onDone);
  }, [open, runChat]);

  if (!open) return null;

  const scopeHint = context.scope?.region_label ?? "현재 scope";
  const trustLevel = lastMeta?.trust_level ?? baseTrust.level;
  const trustSources = lastMeta?.trust_sources?.length ? lastMeta.trust_sources : baseTrust.sources;
  const webEvidence =
    lastMeta?.evidence
      ?.filter((e: EvidenceItem) => e.type === "web" && e.url)
      .map((e: EvidenceItem) => ({ label: e.label, url: e.url })) ?? [];

  return createPortal(
    <div
      data-ch2-ai
      className="fixed z-[150] modal-shell rounded-xl shadow-2xl border flex flex-col overflow-hidden"
      role="dialog"
      aria-modal="false"
      aria-labelledby="ai-assistant-modal-title"
      style={{ left: win.x, top: win.y, width: win.w, height: win.h }}
    >
      <div
        className="px-4 py-3 border-b border-slate-100 dark:border-slate-700 shrink-0 cursor-grab active:cursor-grabbing select-none"
        onPointerDown={(e) => {
          const t = e.target as HTMLElement;
          if (t.closest("button, a, input, textarea, select")) return;
          beginMove(e, win);
        }}
      >
        <div className="flex justify-between items-start gap-2">
          <div className="min-w-0">
            <h2 id="ai-assistant-modal-title" className="text-sm font-bold text-slate-900 dark:text-slate-100">
              통계 분석 어시스턴트
            </h2>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 truncate">
              {scopeHint}
              <span className="ml-2 text-slate-400 dark:text-slate-500">· 드래그로 이동 · 모서리로 크기 조절</span>
            </p>
          </div>
          <div className="flex items-start gap-2">
            <div
              className="flex items-center rounded-full border border-slate-200 bg-white dark:border-slate-600 dark:bg-slate-800 overflow-hidden"
              title="글자 크기"
            >
              <button
                type="button"
                aria-label="글자 작게"
                className="px-1.5 py-1 text-[10px] text-slate-600 hover:bg-slate-50 disabled:opacity-40 dark:text-slate-300 dark:hover:bg-slate-700 cursor-pointer"
                disabled={fontScale <= FONT_SCALES[0]}
                onClick={() => bumpFont(-1)}
              >
                A−
              </button>
              <span className="px-1 text-[10px] tabular-nums text-slate-400 dark:text-slate-500 border-x border-slate-200 dark:border-slate-600 min-w-[2.25rem] text-center">
                {Math.round(fontScale * 100)}%
              </span>
              <button
                type="button"
                aria-label="글자 크게"
                className="px-1.5 py-1 text-[12px] font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-40 dark:text-slate-300 dark:hover:bg-slate-700 cursor-pointer"
                disabled={fontScale >= FONT_SCALES[FONT_SCALES.length - 1]}
                onClick={() => bumpFont(1)}
              >
                A+
              </button>
            </div>
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
              className="text-slate-400 hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-200 text-xl leading-none px-1 shrink-0 cursor-pointer"
              onClick={onClose}
            >
              ×
            </button>
          </div>
        </div>
      </div>

      <div
        className="flex-1 min-h-0 overflow-y-auto px-4 py-3 space-y-3"
        style={{ fontSize: `${BASE_FONT_PX * fontScale}px` }}
      >
        <div className="rounded-lg border border-slate-200 bg-white/70 px-3 py-2.5 space-y-2 text-[0.92em] leading-relaxed dark:border-slate-600 dark:bg-slate-800/40">
          <div>
            <p className="text-[0.85em] font-semibold tracking-wide text-slate-500 dark:text-slate-400 mb-0.5">
              목적과 기능
            </p>
            <p className="text-slate-700 dark:text-slate-200">{PURPOSE_COPY}</p>
          </div>
          <div className="border-t border-slate-200/80 dark:border-slate-600/80 pt-2">
            <p className="text-[0.85em] font-semibold tracking-wide text-slate-500 dark:text-slate-400 mb-0.5">
              제한사항 및 사용량
            </p>
            <p className="text-slate-700 dark:text-slate-200">{LIMITS_COPY}</p>
          </div>
        </div>

        <div
          ref={chatLogRef}
          className="min-h-[8rem] flex-1 overflow-y-auto space-y-0 border border-slate-200 rounded-lg bg-slate-50/80 dark:border-slate-600 dark:bg-slate-900/50 max-h-[calc(100%-0.5rem)]"
          aria-busy={loading}
        >
          {messages.length === 0 && !loading && (
            <div className="px-3 py-4 space-y-3">
              <p className="text-slate-500 dark:text-slate-400 text-center text-[1em]">
                무엇을 도와드릴까요?
              </p>
              <div className="flex flex-col gap-1.5">
                {ENTRY_CHIPS.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    className="text-left px-3 py-2 rounded-lg border border-slate-200 hover:border-sky-400 hover:bg-sky-50/80 text-[0.95em] text-slate-800 dark:border-slate-600 dark:text-slate-100 dark:hover:border-sky-500 dark:hover:bg-slate-800"
                    onClick={() => runChat(c.q)}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m: ChatMessage, i: number) => (
            <div
              key={i}
              className={clsx(
                "px-3 py-2.5",
                i > 0 && "border-t border-slate-200/90 dark:border-slate-600/80",
                m.role === "user" ? "bg-white/70 dark:bg-slate-800/40" : "bg-transparent",
              )}
            >
              {m.role === "user" ? (
                <div className="flex gap-2.5">
                  <div
                    className="mt-0.5 w-0.5 shrink-0 rounded-full bg-sky-500/80 dark:bg-sky-400/70"
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1">
                    <div className="text-[0.85em] font-semibold tracking-wide text-sky-700 dark:text-sky-300 mb-0.5">
                      질문
                    </div>
                    <p className="text-[1.1em] font-medium leading-snug text-slate-900 dark:text-slate-50">
                      {m.text}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="min-w-0">
                  <div className="text-[0.85em] font-semibold tracking-wide text-slate-500 dark:text-slate-400 mb-1">
                    답변
                  </div>
                  <div className="text-[1em] leading-relaxed text-slate-700 dark:text-slate-200">
                    <AnswerBody text={m.text} />
                  </div>
                  {m.meta?.actions?.length > 0 && (
                    <ScreenActionButtons
                      actions={m.meta.actions}
                      pendingId={pendingActionId}
                      onPending={setPendingActionId}
                    />
                  )}
                  {m.meta?.suggested_followups?.length > 0 && (
                      <div className="mt-3">
                        <p className="text-[0.85em] font-semibold tracking-wide text-slate-500 dark:text-slate-400 mb-1.5">
                          관련 질문
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {m.meta.suggested_followups.map((q: string) => (
                            <button
                              key={q}
                              type="button"
                              className="text-left px-2 py-1 rounded border border-slate-200 hover:border-slate-400 text-[0.95em] text-slate-700 dark:border-slate-600 dark:text-slate-200 dark:bg-slate-800/60 dark:hover:border-slate-500 dark:hover:bg-slate-800 disabled:opacity-50"
                              disabled={loading}
                              onClick={() => runChat(q)}
                            >
                              {q}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div
              className={clsx(
                "px-3 py-2.5",
                messages.length > 0 && "border-t border-slate-200/90 dark:border-slate-600/80",
              )}
              role="status"
              aria-live="polite"
            >
              <div className="text-[0.85em] font-semibold tracking-wide text-slate-500 dark:text-slate-400 mb-1">
                답변
              </div>
              <div className="flex items-center gap-3 text-[1em] text-slate-500 dark:text-slate-400">
                <span className="inline-flex gap-1" aria-hidden>
                  <span className="h-1.5 w-1.5 rounded-full bg-sky-500 animate-bounce [animation-delay:-0.3s]" />
                  <span className="h-1.5 w-1.5 rounded-full bg-sky-500 animate-bounce [animation-delay:-0.15s]" />
                  <span className="h-1.5 w-1.5 rounded-full bg-sky-500 animate-bounce" />
                </span>
                답변중
                <button
                  type="button"
                  aria-label="답변 멈춤"
                  className="ml-auto px-2.5 py-1 rounded-lg border border-rose-300 bg-rose-50 text-rose-800 hover:bg-rose-100 text-[0.95em] font-medium dark:border-rose-500 dark:bg-rose-950/50 dark:text-rose-200 dark:hover:bg-rose-900/60"
                  onClick={stopChat}
                >
                  멈춤
                </button>
              </div>
            </div>
          )}
        </div>

        {error && <p className="text-red-600 dark:text-red-400 text-[1em]">{error}</p>}
        {stoppedNotice && !loading && !error && (
          <p className="text-slate-500 dark:text-slate-400 text-[1em]">답변을 멈췄습니다.</p>
        )}
      </div>

      <div
        className="shrink-0 px-4 py-3 border-t border-slate-100 dark:border-slate-700 space-y-2"
        style={{ fontSize: `${BASE_FONT_PX * fontScale}px` }}
      >
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            runChat(input);
          }}
        >
          <input
            className="input flex-1 text-[1em] py-1.5 border border-slate-200 rounded px-2 dark:border-slate-600"
            placeholder="질문 입력…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            autoFocus
          />
          {loading ? (
            <button
              type="button"
              aria-label="답변 멈춤"
              className="text-[1em] py-1.5 px-3 rounded border border-rose-400 bg-rose-50 text-rose-800 hover:bg-rose-100 font-medium dark:border-rose-500 dark:bg-rose-950/50 dark:text-rose-200 dark:hover:bg-rose-900/60"
              onClick={stopChat}
            >
              멈춤
            </button>
          ) : (
            <button
              type="submit"
              className="btn btn-primary text-[1em] py-1.5 px-3 rounded disabled:opacity-50"
              disabled={!input.trim()}
            >
              전송
            </button>
          )}
        </form>
        <p className="text-[0.85em] text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-900/70 rounded px-2 py-1.5 border border-transparent dark:border-slate-700">
          {PANEL_DISCLAIMER}
        </p>
      </div>

      <ResizeHandles onPointerDown={(edge, e) => beginResize(edge, e, win)} />
    </div>,
    document.body,
  );
}

export default function AiAssistantPanel({
  context,
  className,
}: {
  context?: AiContextPayload;
  className?: string;
}) {
  const fromView = useActiveAiView();
  const ctx = context ?? fromView ?? emptyAiContext("built", "RegressionCard");
  const [open, setOpen] = useState(false);

  return (
    <>
      <span data-ch2-ai className="inline-flex shrink-0">
        <button
          type="button"
          className={clsx("btn btn-ghost shrink-0", className)}
          onClick={() => setOpen(true)}
        >
          AI 어시스턴트
        </button>
      </span>
      <AiAssistantModal open={open} onClose={() => setOpen(false)} context={ctx} />
    </>
  );
}
