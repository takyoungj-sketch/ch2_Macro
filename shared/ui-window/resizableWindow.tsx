// @ts-nocheck — shared: 앱별 tsc 경로가 다름
import { useCallback, useEffect, useRef, type PointerEvent as ReactPointerEvent } from "react";
import "./resize-handles.css";

export type PanelBox = { x: number; y: number; w: number; h: number };
export type ResizeEdge = "n" | "s" | "e" | "w" | "nw" | "ne" | "sw" | "se";

export const RESIZE_HANDLES: { edge: ResizeEdge; className: string; cursor: string }[] = [
  { edge: "n", className: "ch2-resize-handle", cursor: "ns-resize" },
  { edge: "s", className: "ch2-resize-handle", cursor: "ns-resize" },
  { edge: "e", className: "ch2-resize-handle", cursor: "ew-resize" },
  { edge: "w", className: "ch2-resize-handle", cursor: "ew-resize" },
  { edge: "nw", className: "ch2-resize-handle", cursor: "nwse-resize" },
  { edge: "ne", className: "ch2-resize-handle", cursor: "nesw-resize" },
  { edge: "sw", className: "ch2-resize-handle", cursor: "nesw-resize" },
  { edge: "se", className: "ch2-resize-handle", cursor: "nwse-resize" },
];

export function clampBox(box: PanelBox, minW: number, minH: number): PanelBox {
  const pad = 8;
  const vw = typeof window !== "undefined" ? window.innerWidth : 1200;
  const vh = typeof window !== "undefined" ? window.innerHeight : 800;
  const maxW = Math.max(minW, vw - pad * 2);
  const maxH = Math.max(minH, vh - pad * 2);
  let { x, y, w, h } = box;
  w = Math.min(Math.max(minW, w), maxW);
  h = Math.min(Math.max(minH, h), maxH);
  const maxX = Math.max(pad, vw - w - pad);
  const maxY = Math.max(pad, vh - h - pad);
  x = Math.min(Math.max(pad, x), maxX);
  y = Math.min(Math.max(pad, y), maxY);
  return { x, y, w, h };
}

export function boxesEqual(a: PanelBox | null, b: PanelBox | null): boolean {
  if (a === b) return true;
  if (!a || !b) return false;
  return a.x === b.x && a.y === b.y && a.w === b.w && a.h === b.h;
}

export function applyEdgeResize(
  orig: PanelBox,
  edge: ResizeEdge,
  dx: number,
  dy: number,
  minW: number,
  minH: number,
): PanelBox {
  let { x, y, w, h } = orig;
  if (edge.includes("e")) w = orig.w + dx;
  if (edge.includes("s")) h = orig.h + dy;
  if (edge.includes("w")) {
    w = orig.w - dx;
    x = orig.x + dx;
  }
  if (edge.includes("n")) {
    h = orig.h - dy;
    y = orig.y + dy;
  }
  if (w < minW) {
    if (edge.includes("w")) x = orig.x + orig.w - minW;
    w = minW;
  }
  if (h < minH) {
    if (edge.includes("n")) y = orig.y + orig.h - minH;
    h = minH;
  }
  return clampBox({ x, y, w, h }, minW, minH);
}

export function ResizeHandles({
  onPointerDown,
}: {
  onPointerDown: (edge: ResizeEdge, e: ReactPointerEvent<HTMLDivElement>) => void;
}) {
  return (
    <>
      {RESIZE_HANDLES.map(({ edge, className, cursor }) => (
        <div
          key={edge}
          data-resize-handle={edge}
          role="separator"
          aria-label="창 크기 조절"
          title="모서리를 드래그하여 크기 조절"
          className={className}
          style={{ cursor }}
          onPointerDown={(e) => {
            if (e.button !== 0) return;
            e.preventDefault();
            e.stopPropagation();
            try {
              e.currentTarget.setPointerCapture(e.pointerId);
            } catch {
              /* ignore */
            }
            onPointerDown(edge, e);
          }}
        />
      ))}
      <span className="ch2-resize-grip ch2-resize-grip--nw" aria-hidden />
      <span className="ch2-resize-grip ch2-resize-grip--ne" aria-hidden />
      <span className="ch2-resize-grip ch2-resize-grip--sw" aria-hidden />
      <span className="ch2-resize-grip ch2-resize-grip--se" aria-hidden />
    </>
  );
}

export function cursorForEdge(edge?: ResizeEdge): string {
  return RESIZE_HANDLES.find((h) => h.edge === edge)?.cursor ?? "nwse-resize";
}

export function readStoredSize(key: string): { w: number; h: number } | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const p = JSON.parse(raw);
    if (typeof p?.w === "number" && typeof p?.h === "number" && p.w > 40 && p.h > 40) {
      return { w: p.w, h: p.h };
    }
  } catch {
    /* ignore */
  }
  return null;
}

export function persistSize(key: string, box: { w: number; h: number }) {
  try {
    localStorage.setItem(key, JSON.stringify({ w: Math.round(box.w), h: Math.round(box.h) }));
  } catch {
    /* ignore */
  }
}

export function persistBox(key: string, box: PanelBox) {
  try {
    localStorage.setItem(
      key,
      JSON.stringify({
        x: Math.round(box.x),
        y: Math.round(box.y),
        w: Math.round(box.w),
        h: Math.round(box.h),
      }),
    );
  } catch {
    /* ignore */
  }
}

export function readStoredBox(key: string): PanelBox | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const p = JSON.parse(raw);
    if (
      typeof p?.x === "number" &&
      typeof p?.y === "number" &&
      typeof p?.w === "number" &&
      typeof p?.h === "number"
    ) {
      return p;
    }
  } catch {
    /* ignore */
  }
  return null;
}

export function usePanelDrag(
  enabled: boolean,
  minW: number,
  minH: number,
  onBoxChange: (box: PanelBox) => void,
) {
  const dragRef = useRef<{
    mode: "move" | "resize";
    edge?: ResizeEdge;
    startX: number;
    startY: number;
    orig: PanelBox;
  } | null>(null);
  const onChangeRef = useRef(onBoxChange);
  onChangeRef.current = onBoxChange;

  useEffect(() => {
    if (!enabled) return;
    const onMove = (e: PointerEvent) => {
      const d = dragRef.current;
      if (!d) return;
      const dx = e.clientX - d.startX;
      const dy = e.clientY - d.startY;
      const next =
        d.mode === "move"
          ? clampBox({ ...d.orig, x: d.orig.x + dx, y: d.orig.y + dy }, minW, minH)
          : d.edge
            ? applyEdgeResize(d.orig, d.edge, dx, dy, minW, minH)
            : null;
      if (next) onChangeRef.current(next);
    };
    const onUp = () => {
      dragRef.current = null;
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [enabled, minW, minH]);

  const beginMove = useCallback((e: ReactPointerEvent, orig: PanelBox) => {
    if (e.button !== 0) return;
    e.preventDefault();
    dragRef.current = {
      mode: "move",
      startX: e.clientX,
      startY: e.clientY,
      orig: { ...orig },
    };
    document.body.style.userSelect = "none";
    document.body.style.cursor = "grabbing";
  }, []);

  const beginResize = useCallback((edge: ResizeEdge, e: ReactPointerEvent, orig: PanelBox) => {
    if (e.button !== 0) return;
    e.preventDefault();
    dragRef.current = {
      mode: "resize",
      edge,
      startX: e.clientX,
      startY: e.clientY,
      orig: { ...orig },
    };
    document.body.style.userSelect = "none";
    document.body.style.cursor = cursorForEdge(edge);
  }, []);

  return { beginMove, beginResize };
}
