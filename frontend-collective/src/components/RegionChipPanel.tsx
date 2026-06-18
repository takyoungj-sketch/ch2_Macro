import clsx from "clsx";

function fmtNum(n: number) {
  return n.toLocaleString();
}

type ChipOption = {
  id?: string;
  name: string;
  count: number;
  parent?: string | null;
  disabled?: boolean;
  min_reliable_count?: number;
};

function isDisabled(o: ChipOption): boolean {
  return Boolean(o.disabled);
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
  options: ChipOption[];
  formatLabel?: (o: ChipOption) => string;
  onToggle: (name: string) => void;
  onSelectAll: () => void;
  onClear: () => void;
}) {
  const label = formatLabel ?? ((o) => o.name);
  const enabledOptions = options.filter((o) => !isDisabled(o));
  const minN = options.find((o) => o.min_reliable_count)?.min_reliable_count ?? 15;
  const densityHint =
    options.some((o) => isDisabled(o)) ? `회색 항목은 거래 ${minN}건 미만으로 선택 불가` : null;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-slate-700 dark:text-slate-200">{title}</span>
        <span className="text-[10px] text-slate-400 dark:text-slate-500">{selected.length ? `${selected.length}개` : "전체"}</span>
      </div>
      <p className="text-[10px] text-slate-500 dark:text-slate-400 leading-snug">{hint}</p>
      {densityHint && <p className="text-[10px] text-amber-700 dark:text-amber-400">{densityHint}</p>}
      <div className="flex gap-1">
        <button
          type="button"
          className="btn btn-ghost text-[10px] py-0.5 px-1.5"
          onClick={onSelectAll}
          disabled={!enabledOptions.length}
        >
          전체
        </button>
        <button type="button" className="btn btn-ghost text-[10px] py-0.5 px-1.5" onClick={onClear} disabled={!selected.length}>
          해제
        </button>
      </div>
      <div className="flex flex-wrap gap-1 max-h-32 overflow-y-auto border border-slate-100 dark:border-slate-700 rounded p-1.5">
        {options.map((o) => {
          const disabled = isDisabled(o);
          return (
            <label
              key={o.id ?? o.name}
              title={disabled ? `거래 ${minN}건 미만` : undefined}
              className={clsx(
                "flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded border",
                disabled
                  ? "opacity-45 cursor-not-allowed bg-slate-50 dark:bg-slate-800 text-slate-400 border-slate-200 dark:border-slate-700"
                  : "cursor-pointer",
                !disabled &&
                  (selected.includes(o.name)
                    ? "bg-slate-800 dark:bg-slate-500 text-white border-slate-800 dark:border-slate-500"
                    : "bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border-slate-200 dark:border-slate-600 hover:border-slate-400 dark:hover:border-slate-500"),
              )}
            >
              <input
                type="checkbox"
                className="sr-only"
                checked={selected.includes(o.name)}
                disabled={disabled}
                onChange={() => {
                  if (!disabled) onToggle(o.name);
                }}
              />
              {label(o)}
              <span className={clsx("opacity-70", selected.includes(o.name) && !disabled && "text-slate-300")}>
                ({fmtNum(o.count)})
              </span>
            </label>
          );
        })}
        {!options.length && <span className="text-[10px] text-slate-400">항목 없음</span>}
      </div>
    </div>
  );
}
