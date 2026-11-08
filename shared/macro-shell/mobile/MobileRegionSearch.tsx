// @ts-nocheck — React is supplied by the consuming frontend.
import { useEffect, useRef, useState } from "react";

export type MobileRegion = {
  code: string; level: "sigungu" | "eupmyeondong" | "beopjungri";
  label: string; sido: string; sigungu: string; eup: string; ri: string;
};

/** Shared canonical catalogue search; no full-country catalogue or auth dependency. */
export default function MobileRegionSearch({ token = "", selected, onSelect }: {
  token?: string; selected: MobileRegion | null; onSelect: (region: MobileRegion | null) => void;
}) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<MobileRegion[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [active, setActive] = useState(-1);
  const input = useRef<HTMLInputElement>(null);
  const generation = useRef(0);
  useEffect(() => {
    const request = ++generation.current;
    const q = query.trim();
    setHits([]); setActive(-1); setError("");
    if (q.length < 2) { setBusy(false); return; }
    setBusy(true);
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(`/api/free/v2/regions?search=${encodeURIComponent(q)}&limit=400`, {
          headers: token ? { "X-Api-Token": token } : {}, signal: controller.signal,
        });
        if (!response.ok) throw new Error("검색을 불러오지 못했습니다. 다시 입력해 주세요.");
        const rows = await response.json();
        const unique = new Map<string, MobileRegion>();
        for (const row of rows) {
          const base = { sido: row.sido_name, sigungu: row.sigungu_name, eup: row.eupmyeondong_name, ri: row.beopjungri_name };
          const parent = [base.sido, base.sigungu].filter(Boolean).join(" ");
          if (base.sigungu?.includes(q) || parent === q) {
            unique.set(row.sigungu_code, { ...base, code: row.sigungu_code, level: "sigungu", label: parent });
          }
          const eupLabel = [parent, base.eup].filter(Boolean).join(" ");
          if (row.eupmyeondong_code) unique.set(row.eupmyeondong_code, { ...base, code: row.eupmyeondong_code, level: "eupmyeondong", label: eupLabel });
          if (base.ri && base.ri !== base.eup && !base.eup?.endsWith("동")) {
            unique.set(row.beopjungri_code, { ...base, code: row.beopjungri_code, level: "beopjungri", label: `${eupLabel} ${base.ri}` });
          }
        }
        if (generation.current === request) setHits([...unique.values()]);
      } catch (e) {
        if (!controller.signal.aborted && generation.current === request) setError(e.message);
      } finally { if (generation.current === request) setBusy(false); }
    }, 220);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query, token]);
  const choose = (hit: MobileRegion) => { ++generation.current; setQuery(""); setHits([]); setBusy(false); onSelect(hit); input.current?.blur(); };
  const submit = () => {
    if (busy) return;
    const q = query.trim();
    const exact = hits.filter(hit => hit.label === q || (hit.level === "sigungu" ? hit.sigungu.split(/\s+/).at(-1) : hit.level === "beopjungri" ? hit.ri : hit.eup) === q);
    if (active >= 0 && hits[active]) choose(hits[active]);
    else if (exact.length === 1) choose(exact[0]);
    else if (hits.length === 1) choose(hits[0]);
    else if (hits.length > 1) setError("목록에서 분석할 지역을 선택해 주세요.");
    else setError(query.trim().length < 2 ? "지역명을 두 글자 이상 입력해 주세요." : "일치하는 지역이 없습니다.");
  };
  return <div className="ch2-field-region-search">
    <form onSubmit={e => { e.preventDefault(); submit(); }}>
      <input ref={input} type="search" aria-label="지역명 입력" autoComplete="off" value={query}
        aria-controls="mobile-region-options" aria-expanded={hits.length > 0} aria-activedescendant={active >= 0 ? `mobile-region-${active}` : undefined}
        onChange={e => setQuery(e.target.value)} onKeyDown={e => {
          if (e.nativeEvent.isComposing) { if (e.key === "Enter") e.preventDefault(); return; }
          if (e.key === "ArrowDown") { e.preventDefault(); setActive(i => Math.min(i + 1, hits.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActive(i => Math.max(i - 1, 0)); }
          if (e.key === "Escape") { setQuery(""); setHits([]); }
        }} />
      <button type="submit" disabled={busy}>{busy ? "검색 중" : "검색"}</button>
      <button type="button" aria-label="지역 초기화" onClick={() => { ++generation.current; setQuery(""); setHits([]); onSelect(null); input.current?.focus(); }}>×</button>
    </form>
    <p className="ch2-field-region-label">{selected?.label || "지역명을 입력해 주세요."}<span>5년 롤링</span></p>
    {hits.length > 0 && <ul id="mobile-region-options" role="listbox" aria-label="지역 검색 결과">{hits.map((hit, i) => <li key={`${hit.level}:${hit.code}`}><button type="button" id={`mobile-region-${i}`} role="option" aria-selected={active === i} onClick={() => choose(hit)}>{hit.label}</button></li>)}</ul>}
    {error && <p role="alert">{error}</p>}
    {!busy && !error && query.trim().length >= 2 && hits.length === 0 && <p role="status">일치하는 지역이 없습니다.</p>}
  </div>;
}
