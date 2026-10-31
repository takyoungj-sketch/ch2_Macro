// @ts-nocheck — React는 각 앱의 런타임에서 제공한다.
import { useEffect } from "react";

/** 닫기 후 원래 위치로 돌아가며, 모달 안의 Tab 순환을 유지한다. */
export function useModalFocus(active, panelRef, trap = true, returnFocusRef = undefined) {
  useEffect(() => {
    const panel = panelRef.current;
    if (!active || !panel) return;
    const previous = returnFocusRef?.current ?? document.activeElement;
    const candidates = () => Array.from(panel.querySelectorAll(
      'button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),a[href],[tabindex]:not([tabindex="-1"]),summary',
    )).filter(node => node.tabIndex >= 0 && node.getClientRects().length > 0 && !node.closest('[inert]'));
    if (!panel.contains(document.activeElement)) {
      (panel.querySelector('button[aria-label="닫기"]') ?? candidates()[0] ?? panel).focus({ preventScroll: true });
    }
    const onKey = event => {
      if (!trap || event.key !== "Tab" || !panel.contains(document.activeElement)) return;
      const list = candidates();
      if (!list.length) { event.preventDefault(); panel.focus(); return; }
      const first = list[0], last = list[list.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === panel)) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first.focus();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      if (previous?.isConnected && (document.activeElement === document.body || panel.contains(document.activeElement)))
        previous.focus?.({ preventScroll: true });
    };
  }, [active, panelRef, trap, returnFocusRef]);
}

/** 포털의 자식 창에서 누른 Esc를 부모 창이 먼저 소비하지 않는다. */
export function isForeignDialogEvent(event, panel) {
  const targetDialog = event.target?.closest?.('[role="dialog"]');
  const ownDialog = panel?.closest?.('[role="dialog"]');
  return Boolean(targetDialog && ownDialog && targetDialog !== ownDialog);
}
