import clsx from "clsx";

function fmtNum(n: number) {
  return n.toLocaleString();
}

export default function RegionChipPanel({
  title,
  hint,
  selected,
  options,
  formatLabel,
  onToggle,
  onSelectAll,
  onClear,
}: {
  title: string;
  hint: string;
  selected: string[];
  options: { id?: string; name: string; count: number; parent?: string | null }[];
  formatLabel?: (o: { name: string; count: number; parent?: string | null }) => string;
  onToggle: (name: string) => void;
  onSelectAll: () => void;
  onClear: () => void;
}) {
  const label = formatLabel ?? ((o) => o.name);
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-slate-700">{title}</span>
        <span className="text-[10px] text-slate-400">{selected.length ? `${selected.length}개` : "전체"}</span>
      </div>
      <p className="text-[10px] text-slate-500 leading-snug">{hint}</p>
      <div className="flex gap-1">
        <button type="button" className="btn btn-ghost text-[10px] py-0.5 px-1.5" onClick={onSelectAll} disabled={!options.length}>
          전체
        </button>
        <button type="button" className="btn btn-ghost text-[10px] py-0.5 px-1.5" onClick={onClear} disabled={!selected.length}>
          해제
        </button>
      </div>
      <div className="flex flex-wrap gap-1 max-h-32 overflow-y-auto border border-slate-100 rounded p-1.5">
        {options.map((o) => (
          <label
            key={o.id ?? o.name}
            className={clsx(
              "flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded border cursor-pointer",
              selected.includes(o.name)
                ? "bg-slate-800 text-white border-slate-800"
                : "bg-white text-slate-700 border-slate-200 hover:border-slate-400",
            )}
          >
            <input type="checkbox" className="sr-only" checked={selected.includes(o.name)} onChange={() => onToggle(o.name)} />
            {label(o)}
            <span className={clsx("opacity-70", selected.includes(o.name) && "text-slate-300")}>({fmtNum(o.count)})</span>
          </label>
        ))}
        {!options.length && <span className="text-[10px] text-slate-400">항목 없음</span>}
      </div>
    </div>
  );
}
