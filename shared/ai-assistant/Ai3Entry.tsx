// @ts-nocheck — 기존 공유 AI 컴포넌트와 같은 프런트별 React 해석 경로 사용
/** 각 앱 안에서 공유 AI3 대화창을 연다. 닫았다 열어도 대화·실행을 유지한다. */
import { lazy, Suspense, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { clampBox, persistBox, readStoredBox, ResizeHandles, usePanelDrag } from "../ui-window/resizableWindow";
import "./aiAssistantPanel.css";

const Ai3Assistant = lazy(() => import("./Ai3Assistant"));
const STORAGE_KEY = "ch2-ai3-win-box";
const MIN_WIDTH = 360;
const MIN_HEIGHT = 320;
const LABELS = { land: "토지", built: "복합", collective: "집합 주거", commercial: "집합 비주거", rent: "임대", profile: "지역프로필", insight: "Insight" };

function initialBox() {
  const stored = readStoredBox(STORAGE_KEY);
  return clampBox(stored || {
    x: Math.max(8, (window.innerWidth - 720) / 2),
    y: Math.max(78, (window.innerHeight - 620) / 2),
    w: 720, h: 620,
  }, MIN_WIDTH, MIN_HEIGHT);
}

export default function Ai3Entry({ domain, screenRegion = "" }: {
  domain: "land" | "built" | "collective" | "commercial" | "rent" | "profile" | "insight";
  screenRegion?: string;
}) {
  const [open, setOpen] = useState(false);
  const [started, setStarted] = useState(false);
  const [box, setBox] = useState(initialBox);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const updateBox = (next) => { setBox(next); persistBox(STORAGE_KEY, next); };
  const { beginMove, beginResize } = usePanelDrag(open, MIN_WIDTH, MIN_HEIGHT, updateBox);

  useEffect(() => {
    if (!open) return;
    const resize = () => setBox(previous => clampBox(previous, MIN_WIDTH, MIN_HEIGHT));
    window.addEventListener("resize", resize);
    panelRef.current?.focus();
    return () => window.removeEventListener("resize", resize);
  }, [open]);

  function close() {
    setOpen(false);
    buttonRef.current?.focus();
  }

  return (
    <>
      <button ref={buttonRef} type="button" className="btn btn-ghost inline-flex shrink-0 items-center"
        aria-haspopup="dialog" aria-expanded={open} title="AI3 통합 어시스턴트"
        onClick={() => { setStarted(true); setOpen(true); }}>
        AI3
      </button>
      {started && createPortal(
        <div ref={panelRef} role="dialog" aria-modal="false" aria-labelledby={titleId}
          tabIndex={-1} hidden={!open} data-ch2-ai
          className="ch2-ai-modal fixed isolate rounded-xl flex-col overflow-hidden"
          style={{ display: open ? "flex" : "none", zIndex: 450, left: box.x, top: box.y, width: box.w, height: box.h }}
          onKeyDown={event => { if (event.key === "Escape") { event.stopPropagation(); close(); } }}>
          <div className="ch2-ai-modal-header px-4 py-3 shrink-0 cursor-grab select-none"
            onPointerDown={event => { if (!(event.target as HTMLElement).closest("button, a, input, select")) beginMove(event, box); }}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 id={titleId} className="font-bold text-slate-900 dark:text-slate-100">AI3 통합 어시스턴트</h2>
                <p className="text-xs text-slate-500 dark:text-slate-400 truncate mt-1">
                  {LABELS[domain]}{screenRegion ? ` · ${screenRegion}` : ""} · 드래그로 이동 · 모서리로 크기 조절
                </p>
              </div>
              <button type="button" className="btn btn-ghost text-sm shrink-0" aria-label="AI3 닫기" onClick={close}>닫기</button>
            </div>
          </div>
          <div className="flex-1 min-h-0 overflow-auto">
            <Suspense fallback={<p className="p-4 text-sm">AI3를 불러오고 있습니다.</p>}>
              <Ai3Assistant initialApp={domain} screenRegion={screenRegion} embedded />
            </Suspense>
          </div>
          <ResizeHandles onPointerDown={(edge, event) => beginResize(edge, event, box)} />
        </div>, document.body
      )}
    </>
  );
}
