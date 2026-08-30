import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import {
  MODAL_FONT_SCALE_STEPS,
  clampModalFontStep,
  persistModalFontStep,
  readStoredModalFontStep,
} from "@ch2/macro-shell/displayUi";
import { eventHitsCh2Ai, isAiChatOpen } from "@ch2/ai-assistant/aiHost";

type Props = {
  open: boolean;
  onClose: () => void;
  titleId: string;
  title: ReactNode;
  subtitle?: ReactNode;
  /** 제목 아래(탭 등) — 드래그 제외, 클릭 가능 */
  headerExtra?: ReactNode;
  /** 닫기 버튼 왼쪽(AI 등) */
  headerActions?: ReactNode;
  children: ReactNode;
  maxWidthClass?: string;
  /** 모서리·경계 드래그로 크기 조절 */
  resizable?: boolean;
  /** 헤더에 전체화면 토글 (브라우저 줌 대신 모달만 확대) */
  allowFullscreen?: boolean;
  /** 헤더 A−/A+ — 모달 안 글자·버튼·옵션을 zoom으로 함께 확대 */
  allowFontScale?: boolean;
  defaultWidth?: number;
  defaultHeight?: number;
  minWidth?: number;
  minHeight?: number;
  zClassName?: string;
  backdropClassName?: string;
  /** document.body 포털 (토지 연도별 모달 등) */
  usePortal?: boolean;
  /** Escape를 capture 단계에서 처리 */
  escapeCapture?: boolean;
  bodyClassName?: string;
};

type DragState = {
  pointerId: number;
  startX: number;
  startY: number;
  origX: number;
  origY: number;
};

type ResizeEdge = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

type ResizeState = {
  pointerId: number;
  edge: ResizeEdge;
  startX: number;
  startY: number;
  origX: number;
  origY: number;
  origW: number;
  origH: number;
};

type PanelBox = { x: number; y: number; w: number; h: number };

const RESIZE_HANDLES: { edge: ResizeEdge; className: string; cursor: string }[] = [
  { edge: "n", className: "left-2 right-2 top-0 h-1.5 -translate-y-1/2", cursor: "ns-resize" },
  { edge: "s", className: "left-2 right-2 bottom-0 h-1.5 translate-y-1/2", cursor: "ns-resize" },
  { edge: "e", className: "top-2 bottom-2 right-0 w-1.5 translate-x-1/2", cursor: "ew-resize" },
  { edge: "w", className: "top-2 bottom-2 left-0 w-1.5 -translate-x-1/2", cursor: "ew-resize" },
  { edge: "nw", className: "left-0 top-0 h-3 w-3 -translate-x-1/2 -translate-y-1/2", cursor: "nwse-resize" },
  { edge: "ne", className: "right-0 top-0 h-3 w-3 translate-x-1/2 -translate-y-1/2", cursor: "nesw-resize" },
  { edge: "sw", className: "left-0 bottom-0 h-3 w-3 -translate-x-1/2 translate-y-1/2", cursor: "nesw-resize" },
  { edge: "se", className: "right-0 bottom-0 h-3 w-3 translate-x-1/2 translate-y-1/2", cursor: "nwse-resize" },
];

function clampBox(box: PanelBox, minW: number, minH: number): PanelBox {
  const pad = 8;
  const maxW = Math.max(minW, window.innerWidth - pad * 2);
  const maxH = Math.max(minH, window.innerHeight - pad * 2);
  let { x, y, w, h } = box;
  w = Math.min(Math.max(minW, w), maxW);
  h = Math.min(Math.max(minH, h), maxH);
  const maxX = Math.max(pad, window.innerWidth - w - pad);
  const maxY = Math.max(pad, window.innerHeight - h - pad);
  x = Math.min(Math.max(pad, x), maxX);
  y = Math.min(Math.max(pad, y), maxY);
  return { x, y, w, h };
}

function defaultCenteredBox(width: number, height: number, minW: number, minH: number): PanelBox {
  const w = Math.min(Math.max(minW, width), window.innerWidth - 16);
  const h = Math.min(Math.max(minH, height), window.innerHeight - 16);
  return clampBox(
    {
      x: Math.round((window.innerWidth - w) / 2),
      y: Math.round((window.innerHeight - h) / 2),
      w,
      h,
    },
    minW,
    minH,
  );
}

export default function DraggableModalShell({
  open,
  onClose,
  titleId,
  title,
  subtitle,
  headerExtra,
  headerActions,
  children,
  maxWidthClass = "max-w-3xl",
  resizable = false,
  allowFullscreen = true,
  allowFontScale = true,
  defaultWidth,
  defaultHeight,
  minWidth = 360,
  minHeight = 240,
  zClassName = "z-50",
  backdropClassName = "bg-black/40",
  usePortal = false,
  escapeCapture = false,
  bodyClassName = "flex-1 min-h-0 overflow-y-auto px-4 py-3",
}: Props) {
  const panelRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<DragState | null>(null);
  const resizeRef = useRef<ResizeState | null>(null);
  const preFullscreenBoxRef = useRef<PanelBox | null>(null);
  const [box, setBox] = useState<PanelBox | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [fontStep, setFontStep] = useState(readStoredModalFontStep);
  const modalZoom = MODAL_FONT_SCALE_STEPS[clampModalFontStep(fontStep)];
  const fontPct = Math.round(modalZoom * 100);
  const fontStepMin = clampModalFontStep(fontStep) <= 0;
  const fontStepMax = clampModalFontStep(fontStep) >= MODAL_FONT_SCALE_STEPS.length - 1;

  const bumpFontScale = useCallback((direction: 1 | -1) => {
    setFontStep((prev) => {
      const next = clampModalFontStep(prev + direction);
      persistModalFontStep(next);
      return next;
    });
  }, []);

  useEffect(() => {
    if (!open) {
      setBox(null);
      setFullscreen(false);
      setMinimized(false);
      preFullscreenBoxRef.current = null;
      return;
    }
    if (resizable && (defaultWidth != null || defaultHeight != null)) {
      const w = defaultWidth ?? Math.min(768, window.innerWidth - 32);
      const h = defaultHeight ?? Math.min(window.innerHeight * 0.85, 640);
      setBox(defaultCenteredBox(w, h, minWidth, minHeight));
    }
  }, [open, resizable, defaultWidth, defaultHeight, minWidth, minHeight]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (isAiChatOpen()) return;
      if (fullscreen) {
        e.preventDefault();
        e.stopPropagation();
        setFullscreen(false);
        setBox((prev) => {
          const rest = preFullscreenBoxRef.current;
          preFullscreenBoxRef.current = null;
          return rest ?? prev;
        });
        return;
      }
      onClose();
    };
    window.addEventListener("keydown", onKey, escapeCapture);
    return () => window.removeEventListener("keydown", onKey, escapeCapture);
  }, [open, onClose, escapeCapture, fullscreen]);

  useEffect(() => {
    if (!open || !box || fullscreen) return;
    const onWinResize = () => setBox((prev) => (prev ? clampBox(prev, minWidth, minHeight) : prev));
    window.addEventListener("resize", onWinResize);
    return () => window.removeEventListener("resize", onWinResize);
  }, [open, box, minWidth, minHeight, fullscreen]);

  useEffect(() => {
    if (!open || !fullscreen) return;
    const syncFs = () => {
      const pad = 8;
      setBox({
        x: pad,
        y: pad,
        w: Math.max(minWidth, window.innerWidth - pad * 2),
        h: Math.max(minHeight, window.innerHeight - pad * 2),
      });
    };
    syncFs();
    window.addEventListener("resize", syncFs);
    return () => window.removeEventListener("resize", syncFs);
  }, [open, fullscreen, minWidth, minHeight]);

  const ensureBoxFromDom = useCallback((): PanelBox | null => {
    if (box) return box;
    const panel = panelRef.current;
    if (!panel) return null;
    const rect = panel.getBoundingClientRect();
    const next = clampBox(
      { x: rect.left, y: rect.top, w: rect.width, h: rect.height },
      minWidth,
      minHeight,
    );
    setBox(next);
    return next;
  }, [box, minWidth, minHeight]);

  const toggleFullscreen = useCallback(() => {
    setFullscreen((fs) => {
      if (fs) {
        const rest = preFullscreenBoxRef.current;
        preFullscreenBoxRef.current = null;
        if (rest) setBox(rest);
        return false;
      }
      const current = box ?? ensureBoxFromDom();
      if (current) preFullscreenBoxRef.current = current;
      const pad = 8;
      setBox({
        x: pad,
        y: pad,
        w: Math.max(minWidth, window.innerWidth - pad * 2),
        h: Math.max(minHeight, window.innerHeight - pad * 2),
      });
      return true;
    });
  }, [box, ensureBoxFromDom, minWidth, minHeight]);

  const beginDrag = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      if (fullscreen) return;
      if (e.button !== 0) return;
      const target = e.target as HTMLElement;
      if (target.closest("button, input, summary, a, label, select, textarea, [data-no-drag]")) return;
      if (target.closest("[data-resize-handle]")) return;

      const current = ensureBoxFromDom();
      if (!current) return;

      dragRef.current = {
        pointerId: e.pointerId,
        startX: e.clientX,
        startY: e.clientY,
        origX: current.x,
        origY: current.y,
      };
      e.currentTarget.setPointerCapture(e.pointerId);
      e.preventDefault();
    },
    [ensureBoxFromDom, fullscreen],
  );

  const moveDrag = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      const drag = dragRef.current;
      if (!drag || drag.pointerId !== e.pointerId) return;
      setBox((prev) => {
        if (!prev) return prev;
        return clampBox(
          {
            ...prev,
            x: drag.origX + (e.clientX - drag.startX),
            y: drag.origY + (e.clientY - drag.startY),
          },
          minWidth,
          minHeight,
        );
      });
    },
    [minWidth, minHeight],
  );

  const endDrag = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== e.pointerId) return;
    dragRef.current = null;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
  }, []);

  const beginResize = useCallback(
    (edge: ResizeEdge) => (e: ReactPointerEvent<HTMLDivElement>) => {
      if (fullscreen) return;
      if (e.button !== 0) return;
      e.stopPropagation();
      e.preventDefault();
      const current = ensureBoxFromDom();
      if (!current) return;
      resizeRef.current = {
        pointerId: e.pointerId,
        edge,
        startX: e.clientX,
        startY: e.clientY,
        origX: current.x,
        origY: current.y,
        origW: current.w,
        origH: current.h,
      };
      e.currentTarget.setPointerCapture(e.pointerId);
    },
    [ensureBoxFromDom, fullscreen],
  );

  const moveResize = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      const rs = resizeRef.current;
      if (!rs || rs.pointerId !== e.pointerId) return;
      const dx = e.clientX - rs.startX;
      const dy = e.clientY - rs.startY;
      let x = rs.origX;
      let y = rs.origY;
      let w = rs.origW;
      let h = rs.origH;
      const { edge } = rs;

      if (edge.includes("e")) w = rs.origW + dx;
      if (edge.includes("s")) h = rs.origH + dy;
      if (edge.includes("w")) {
        w = rs.origW - dx;
        x = rs.origX + dx;
      }
      if (edge.includes("n")) {
        h = rs.origH - dy;
        y = rs.origY + dy;
      }

      if (w < minWidth) {
        if (edge.includes("w")) x = rs.origX + rs.origW - minWidth;
        w = minWidth;
      }
      if (h < minHeight) {
        if (edge.includes("n")) y = rs.origY + rs.origH - minHeight;
        h = minHeight;
      }

      setBox(clampBox({ x, y, w, h }, minWidth, minHeight));
    },
    [minWidth, minHeight],
  );

  const endResize = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    const rs = resizeRef.current;
    if (!rs || rs.pointerId !== e.pointerId) return;
    resizeRef.current = null;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
  }, []);

  if (!open) return null;

  const panelStyle: CSSProperties = box
    ? minimized
      ? {
          left: 16,
          bottom: 16,
          width: "min(420px, calc(100vw - 2rem))",
          height: "auto",
          maxWidth: "none",
          maxHeight: "none",
          transform: "none",
        }
      : {
          left: box.x,
          top: box.y,
          width: box.w,
          height: box.h,
          maxWidth: "none",
          maxHeight: "none",
          transform: "none",
        }
    : minimized
      ? {
          left: 16,
          bottom: 16,
          width: "min(420px, calc(100vw - 2rem))",
          height: "auto",
          maxWidth: "none",
          maxHeight: "none",
          transform: "none",
        }
      : {
          left: "50%",
          top: "50%",
          transform: "translate(-50%, -50%)",
        };

  const overlayStyle: CSSProperties | undefined = fullscreen
    ? undefined
    : { top: "var(--ch2-macro-header-height, 70px)" };

  const tree = (
    <div
      className={`fixed ${fullscreen ? "inset-0" : "inset-x-0 bottom-0"} ${zClassName} ${
        minimized ? "bg-transparent pointer-events-none" : backdropClassName
      }`}
      style={overlayStyle}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onMouseDown={(e) => {
        if (fullscreen) return;
        if (e.target !== e.currentTarget) return;
        if (eventHitsCh2Ai(e)) return;
        onClose();
      }}
    >
      <div
        ref={panelRef}
        data-fullscreen={fullscreen ? "true" : undefined}
        className={`fixed modal-shell bg-white dark:bg-slate-800 shadow-xl pointer-events-auto ${
          fullscreen ? "rounded-none" : "rounded-xl"
        } ${box ? "" : maxWidthClass} ${
          box || minimized ? "" : "w-[calc(100%-2rem)] max-h-[85vh]"
        } flex flex-col border overflow-hidden`}
        style={panelStyle}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex flex-col min-h-0 w-full overflow-hidden">
        <div
          className={`px-4 py-3 modal-header shrink-0 border-b border-slate-200 dark:border-slate-700 select-none touch-none ${
            fullscreen
              ? "cursor-default"
              : "cursor-grab active:cursor-grabbing"
          }`}
          onPointerDown={beginDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
        >
          <div className="flex justify-between items-start gap-2">
            <div className="min-w-0 pointer-events-none">
              <h2 id={titleId} className={`font-bold ${fullscreen ? "text-base" : "text-sm"}`}>
                {title}
              </h2>
              {subtitle && (
                <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">{subtitle}</div>
              )}
            </div>
            <div className="flex items-center gap-1 shrink-0" data-no-drag>
              {headerActions}
              <button
                type="button"
                aria-label={minimized ? "모달 복원" : "모달 최소화"}
                title={minimized ? "모달 복원" : "모달 최소화"}
                className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 text-sm leading-none px-1.5 py-0.5 shrink-0 cursor-pointer rounded border border-transparent hover:border-slate-200"
                onClick={() => setMinimized((prev) => !prev)}
              >
                {minimized ? "▣" : "−"}
              </button>
              {allowFontScale && (
                <div
                  className="flex items-center gap-0.5 border border-slate-200 dark:border-slate-600 rounded-md bg-slate-50/90 dark:bg-slate-700/90 p-0.5"
                  aria-label="모달 글자 크기"
                  title="모달 글자·버튼 크기"
                >
                  <button
                    type="button"
                    className="w-7 h-6 rounded text-sm font-semibold leading-none text-slate-700 dark:text-slate-200 hover:bg-white dark:hover:bg-slate-600 disabled:opacity-40"
                    aria-label="글자 크기 줄이기"
                    disabled={fontStepMin}
                    onClick={() => bumpFontScale(-1)}
                  >
                    −
                  </button>
                  <span
                    className="min-w-[2.5rem] text-center tabular-nums font-medium text-[10px] text-slate-600 dark:text-slate-300"
                    aria-live="polite"
                  >
                    {fontPct}%
                  </span>
                  <button
                    type="button"
                    className="w-7 h-6 rounded text-sm font-semibold leading-none text-slate-700 dark:text-slate-200 hover:bg-white dark:hover:bg-slate-600 disabled:opacity-40"
                    aria-label="글자 크기 키우기"
                    disabled={fontStepMax}
                    onClick={() => bumpFontScale(1)}
                  >
                    +
                  </button>
                </div>
              )}
              {allowFullscreen && (
                <button
                  type="button"
                  aria-label={fullscreen ? "전체화면 나가기" : "전체화면"}
                  title={fullscreen ? "전체화면 나가기" : "전체화면"}
                  className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 text-sm leading-none px-1.5 py-0.5 shrink-0 cursor-pointer rounded border border-transparent hover:border-slate-200"
                  onClick={toggleFullscreen}
                >
                  {fullscreen ? "⛶" : "⛶"}
                  <span className="sr-only">{fullscreen ? "축소" : "확대"}</span>
                  <span className="ml-0.5 text-[10px] font-medium tabular-nums" aria-hidden>
                    {fullscreen ? "축소" : "전체"}
                  </span>
                </button>
              )}
              <button
                type="button"
                aria-label="닫기"
                className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 text-xl leading-none px-1 shrink-0 cursor-pointer"
                onClick={onClose}
              >
                ×
              </button>
            </div>
          </div>
          {headerExtra && <div className="mt-2 pointer-events-auto" data-no-drag>{headerExtra}</div>}
        </div>

        {!minimized && (
          <div
            className={bodyClassName}
            style={allowFontScale ? { zoom: modalZoom } : undefined}
          >
            {children}
          </div>
        )}
        </div>

        {resizable &&
          !fullscreen &&
          RESIZE_HANDLES.map(({ edge, className, cursor }) => (
            <div
              key={edge}
              data-resize-handle={edge}
              role="separator"
              aria-orientation={edge === "n" || edge === "s" ? "horizontal" : "vertical"}
              aria-label={`모달 크기 조절 (${edge})`}
              className={`absolute z-10 ${className}`}
              style={{ cursor }}
              onPointerDown={beginResize(edge)}
              onPointerMove={moveResize}
              onPointerUp={endResize}
              onPointerCancel={endResize}
            />
          ))}
      </div>
    </div>
  );

  return usePortal ? createPortal(tree, document.body) : tree;
}
