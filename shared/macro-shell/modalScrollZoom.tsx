// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
import { useEffect, useRef, useState, type ReactNode } from "react";

const MIN_SCALE = 1;
const MAX_SCALE = 4;

function clampScale(value: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, value));
}

/** 전체화면 모달 본문. 한 손가락은 상하좌우 스크롤, 두 손가락과 버튼은 확대. */
export default function ModalScrollZoom({ children }: { children: ReactNode }) {
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const scaleRef = useRef(1);
  const gestureRef = useRef({ dist: 0, scale: 1 });
  const [scale, setScale] = useState(1);

  const applyScale = (next: number) => {
    const clamped = clampScale(next);
    scaleRef.current = clamped;
    setScale(clamped);
  };

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const distance = (touches: TouchList) => {
      const dx = touches[0].clientX - touches[1].clientX;
      const dy = touches[0].clientY - touches[1].clientY;
      return Math.hypot(dx, dy);
    };
    const onStart = (event: TouchEvent) => {
      if (event.touches.length !== 2) return;
      gestureRef.current = { dist: distance(event.touches), scale: scaleRef.current };
    };
    const onMove = (event: TouchEvent) => {
      if (event.touches.length !== 2 || gestureRef.current.dist <= 0) return;
      event.preventDefault();
      const next = gestureRef.current.scale * (distance(event.touches) / gestureRef.current.dist);
      applyScale(next);
    };
    const onEnd = () => {
      gestureRef.current.dist = 0;
    };
    el.addEventListener("touchstart", onStart, { passive: true });
    el.addEventListener("touchmove", onMove, { passive: false });
    el.addEventListener("touchend", onEnd);
    el.addEventListener("touchcancel", onEnd);
    return () => {
      el.removeEventListener("touchstart", onStart);
      el.removeEventListener("touchmove", onMove);
      el.removeEventListener("touchend", onEnd);
      el.removeEventListener("touchcancel", onEnd);
    };
  }, []);

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <div
        ref={scrollerRef}
        className="min-h-0 flex-1 overflow-auto overscroll-contain"
        style={{ touchAction: "pan-x pan-y", WebkitOverflowScrolling: "touch" }}
      >
        <div className="px-3 py-3" style={{ zoom: scale }}>
          {children}
        </div>
      </div>
      <div className="pointer-events-none absolute bottom-3 right-3 z-10 flex gap-1">
        <button
          type="button"
          className="pointer-events-auto rounded-md border border-slate-300 bg-white/95 px-2 py-1 text-sm font-semibold text-slate-800 shadow-sm dark:border-slate-500 dark:bg-slate-800/95 dark:text-slate-100"
          aria-label="축소"
          onClick={() => applyScale(scaleRef.current - 0.25)}
        >
          −
        </button>
        <button
          type="button"
          className="pointer-events-auto rounded-md border border-slate-300 bg-white/95 px-2 py-1 text-xs font-semibold text-slate-800 shadow-sm dark:border-slate-500 dark:bg-slate-800/95 dark:text-slate-100"
          aria-label="화면 맞춤"
          onClick={() => applyScale(1)}
        >
          맞춤
        </button>
        <button
          type="button"
          className="pointer-events-auto rounded-md border border-slate-300 bg-white/95 px-2 py-1 text-sm font-semibold text-slate-800 shadow-sm dark:border-slate-500 dark:bg-slate-800/95 dark:text-slate-100"
          aria-label="확대"
          onClick={() => applyScale(scaleRef.current + 0.25)}
        >
          +
        </button>
      </div>
    </div>
  );
}
