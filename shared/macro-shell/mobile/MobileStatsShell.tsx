// @ts-nocheck — React is supplied by the consuming frontend.
import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useUiColorScheme } from "../useUiColorScheme";
import "./mobileStats.css";

export type MobileProduct = "land" | "residential" | "commercial";
const products = [
  ["land", "/land/", "토지"],
  ["residential", "/collective/residential/", "주거집합"],
  ["commercial", "/collective/commercial/", "비주거집합"],
] as const;

export default function MobileStatsShell({ product, search, children }: {
  product: MobileProduct; search: ReactNode; children: ReactNode;
}) {
  const { isDark, toggleUiColorScheme } = useUiColorScheme();
  return <div className="ch2-field-stats">
    <header className="ch2-field-header">
      <nav aria-label="모바일 서비스 이동">
        {products.map(([key, href, label]) => <a key={key} href={href} aria-current={key === product ? "page" : undefined}>{label}</a>)}
      </nav>
      <button className="ch2-field-theme" aria-label={isDark ? "밝은 테마로 전환" : "어두운 테마로 전환"} onClick={toggleUiColorScheme}>{isDark ? "☀" : "☾"}</button>
    </header>
    <section className="ch2-field-search-bar" aria-label="분석 지역">{search}</section>
    <main className="ch2-field-results">{children}</main>
  </div>;
}

export function MobileRollingDialog({ title, subtitle, onClose, children }: {
  title: string; subtitle?: string; onClose: () => void; children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    ref.current?.showModal();
    return () => { previous?.focus({ preventScroll: true }); };
  }, []);
  return createPortal(<dialog ref={ref} className="ch2-field-rolling" aria-label={`${title} 5년 롤링`} onCancel={e => { e.preventDefault(); onClose(); }}>
    <header><div><h2>{title}</h2><p>{subtitle || "5년 롤링 · 만원/㎡"}</p></div><button autoFocus aria-label="롤링창 닫기" onClick={onClose}>×</button></header>
    <div className="ch2-field-rolling-body">{children}</div>
  </dialog>, document.body);
}
