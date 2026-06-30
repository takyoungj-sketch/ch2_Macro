import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  titleId: string;
  title: string;
  subtitle?: ReactNode;
  headerExtra?: ReactNode;
  children: ReactNode;
  maxWidthClass?: string;
};

type DragState = {
  pointerId: number;
  startX: number;
  startY: number;
  origX: number;
  origY: number;
};

function clampPanel(x: number, y: number, w: number, h: number) {
  const pad = 8;
  const maxX = Math.max(pad, window.innerWidth - w - pad);
  const maxY = Math.max(pad, window.innerHeight - h - pad);
  return {
    x: Math.min(Math.max(pad, x), maxX),
    y: Math.min(Math.max(pad, y), maxY),
  };
}

export default function DraggableModalShell({
  open,
  onClose,
  titleId,
  title,
  subtitle,
  headerExtra,
  children,
  maxWidthClass = "max-w-3xl",
}: Props) {
  const panelRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<DragState | null>(null);
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    if (!open) setPosition(null);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const beginDrag = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    const target = e.target as HTMLElement;
    if (target.closest("button, input, summary, a, label, select, textarea")) return;

    const panel = panelRef.current;
    if (!panel) return;

    const rect = panel.getBoundingClientRect();
    const origX = position?.x ?? rect.left;
    const origY = position?.y ?? rect.top;

    if (!position) {
      setPosition({ x: origX, y: origY });
    }

    dragRef.current = {
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      origX,
      origY,
    };
    e.currentTarget.setPointerCapture(e.pointerId);
    e.preventDefault();
  }, [position]);

  const moveDrag = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    const panel = panelRef.current;
    if (!drag || drag.pointerId !== e.pointerId || !panel) return;

    const dx = e.clientX - drag.startX;
    const dy = e.clientY - drag.startY;
    const rect = panel.getBoundingClientRect();
    const next = clampPanel(drag.origX + dx, drag.origY + dy, rect.width, rect.height);
    setPosition(next);
  }, []);

  const endDrag = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== e.pointerId) return;
    dragRef.current = null;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
  }, []);

  if (!open) return null;

  const panelStyle: React.CSSProperties = position
    ? { left: position.x, top: position.y, transform: "none" }
    : { left: "50%", top: "50%", transform: "translate(-50%, -50%)" };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        className={`fixed modal-shell rounded-xl shadow-xl ${maxWidthClass} w-[calc(100%-2rem)] max-h-[85vh] flex flex-col border`}
        style={panelStyle}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div
          className="px-4 py-3 modal-header shrink-0 border-b border-slate-200 dark:border-slate-700 cursor-grab active:cursor-grabbing select-none touch-none"
          onPointerDown={beginDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
        >
          <div className="flex justify-between items-start gap-2">
            <div className="min-w-0 pointer-events-none">
              <h2 id={titleId} className="text-sm font-bold">
                {title}
              </h2>
              {subtitle && (
                <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">{subtitle}</div>
              )}
            </div>
            <button
              type="button"
              aria-label="닫기"
              className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 text-xl leading-none px-1 shrink-0 cursor-pointer"
              onClick={onClose}
            >
              ×
            </button>
          </div>
          {headerExtra && <div className="mt-2 pointer-events-auto">{headerExtra}</div>}
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto px-4 py-3">{children}</div>
      </div>
    </div>
  );
}
