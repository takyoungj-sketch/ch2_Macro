// @ts-nocheck — React는 각 앱의 런타임에서 제공한다.
import { useId, useMemo, useState } from "react";

export type AnalysisTarget = { key: string; label: string; address?: string; count: number };

/** 조회된 후보 안에서 이름·주소로 찾는다. 제한된 목록을 전체 후보처럼 보이지 않게 한다. */
export default function TargetPicker({ label, options, onChoose, disabled = false }: {
  label: string; options: AnalysisTarget[]; onChoose: (key: string) => void; disabled?: boolean;
}) {
  const [query, setQuery] = useState("");
  const id = useId();
  const filtered = useMemo(() => {
    const tokens = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    return options.filter(option => tokens.every(token => `${option.label} ${option.address ?? ""}`.toLocaleLowerCase().includes(token)));
  }, [query, options]);
  return <div className="mt-2 space-y-1 text-slate-800 dark:text-slate-100">
    <label htmlFor={`${id}-query`} className="block font-semibold">{label} · 이름/주소 검색</label>
    <input id={`${id}-query`} type="search" value={query} disabled={disabled}
      onChange={event => setQuery(event.target.value)} placeholder="이름 또는 주소 입력"
      className="block w-full border border-slate-400 dark:border-slate-500 rounded px-2 py-1 bg-white dark:bg-slate-900 text-sm" />
    <label htmlFor={`${id}-select`} className="sr-only">{label}</label>
    <select id={`${id}-select`} value="" disabled={disabled || filtered.length === 0}
      className="block w-full border-2 border-indigo-400 dark:border-indigo-300 rounded px-2 py-1.5 bg-white dark:bg-slate-900 text-sm"
      onChange={event => { if (event.target.value) onChoose(event.target.value); }}>
      <option value="">{filtered.length ? "추가할 대상 선택…" : "검색 결과 없음"}</option>
      {filtered.slice(0, 80).map(option => <option key={option.key} value={option.key}>
        {option.label}{option.address ? ` · ${option.address}` : ""} · 조회 {option.count}건
      </option>)}
    </select>
    <p className="text-xs text-slate-700 dark:text-slate-200" role="status">
      조회된 후보 {options.length}개 중 검색 결과 {filtered.length}개{filtered.length > 80 ? " · 처음 80개 표시. 검색어를 좁혀 나머지 후보를 찾으세요." : ""}
    </p>
  </div>;
}
