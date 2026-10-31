export type ModalBox = { x: number; y: number; w: number; h: number };
export type ModalViewport = { width: number; height: number; headerHeight: number };

export function modalViewport(): ModalViewport {
  const header = typeof document !== "undefined" ? document.querySelector(".ch2-macro-stats-header") : null;
  return {
    width: typeof window === "undefined" ? 1200 : window.innerWidth,
    height: typeof window === "undefined" ? 800 : window.innerHeight,
    headerHeight: header ? Math.max(0, header.getBoundingClientRect().bottom) : 0,
  };
}

/** 앱 헤더 아래 실제 화면에 제목·닫기·크기 조절 경계를 모두 남긴다. */
export function clampModalBox(box: ModalBox, minW: number, minH: number, view = modalViewport()): ModalBox {
  const pad = 8;
  const top = Math.min(Math.max(0, view.headerHeight), Math.max(0, view.height - pad * 2 - 1));
  const maxW = Math.max(1, view.width - pad * 2);
  const maxH = Math.max(1, view.height - top - pad * 2);
  const w = Math.min(Math.max(Math.min(minW, maxW), box.w), maxW);
  const h = Math.min(Math.max(Math.min(minH, maxH), box.h), maxH);
  const x = Math.min(Math.max(pad, box.x), Math.max(pad, view.width - w - pad));
  const y = Math.min(Math.max(top + pad, box.y), Math.max(top + pad, view.height - h - pad));
  return { x, y, w, h };
}

export function centeredModalBox(width: number, height: number, minW: number, minH: number, view = modalViewport()): ModalBox {
  const size = clampModalBox({ x: 0, y: 0, w: width, h: height }, minW, minH, view);
  return clampModalBox({ ...size, x: (view.width - size.w) / 2,
    y: view.headerHeight + (view.height - view.headerHeight - size.h) / 2 }, minW, minH, view);
}

export function fullscreenModalBox(minW: number, minH: number, view = modalViewport()): ModalBox {
  return clampModalBox({ x: 0, y: 0, w: view.width, h: view.height }, minW, minH, view);
}
