// @ts-nocheck — React is supplied by the consuming frontend.
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

const HIDE_KEY = "ch2-macro:hide-mobile-usage-guide";
const VISIT_KEY = "ch2-macro:mobile-usage-guide-seen";
let seenInMemory = false;

export default function MobileUsageGuide({ land = false }: { land?: boolean }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const open = () => {
    if (!dialog.current || dialog.current.open) return;
    previousFocus.current = document.activeElement as HTMLElement | null;
    dialog.current.showModal();
  };
  useEffect(() => {
    let suppressed = seenInMemory;
    try { suppressed ||= localStorage.getItem(HIDE_KEY) === "1" || sessionStorage.getItem(VISIT_KEY) === "1"; } catch { /* Storage is optional. */ }
    if (!suppressed) open();
  }, []);
  const close = (hide = false) => {
    seenInMemory = true;
    try {
      sessionStorage.setItem(VISIT_KEY, "1");
      if (hide) localStorage.setItem(HIDE_KEY, "1");
    } catch { /* Closing remains available in private browsing. */ }
    dialog.current?.close();
    (previousFocus.current?.isConnected ? previousFocus.current : trigger.current)?.focus({ preventScroll: true });
  };
  return <>
    <button ref={trigger} type="button" className="ch2-field-guide-trigger" aria-label="모바일 이용 안내" aria-haspopup="dialog" onClick={open}>안내</button>
    {createPortal(<dialog ref={dialog} className="ch2-field-guide" aria-labelledby="mobile-usage-title" aria-describedby="mobile-usage-summary" onCancel={e => { e.preventDefault(); close(); }}>
      <div className="ch2-field-guide-body">
        <h2 id="mobile-usage-title">CH2 Macro 모바일 이용 안내</h2>
        <p id="mobile-usage-summary">CH2 Macro 모바일은 현장에서 간단하게 통계치를 확인하는 용도입니다. 자세한 분석은 데스크탑을 이용해 주세요.</p>
        {land && <section aria-labelledby="mobile-matrix-legend-title">
          <h3 id="mobile-matrix-legend-title">토지 매트릭스 셀 읽는 방법</h3>
          <table className="ch2-field-guide-legend" aria-label="매트릭스 셀 구조 범례"><tbody>
            <tr><td>거래수</td><td>최소</td></tr>
            <tr><td rowSpan={2}>평균</td><td>25%값</td></tr>
            <tr><td>중앙값</td></tr>
            <tr><td>표준편차</td><td>75%값</td></tr>
            <tr><td>95% 신뢰구간</td><td>최대</td></tr>
          </tbody></table>
          <p className="ch2-field-guide-hint">가격 단위는 만원/㎡입니다. 표를 좌우로 밀어 지목을 확인하고, 수치를 누르면 5년 롤링창을 볼 수 있습니다.</p>
        </section>}
      </div>
      <footer><button autoFocus className="ch2-field-guide-confirm" onClick={() => close()}>확인</button><button onClick={() => close(true)}>다시 보지 않기</button></footer>
    </dialog>, document.body)}
  </>;
}
