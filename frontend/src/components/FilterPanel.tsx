import { useAppStore } from "../store";

const ROAD_CONDITIONS = [
  "광대로한면", "광대로각지", "중로한면", "중로각지",
  "소로한면", "소로각지", "세로가", "세로불", "맹지", "구분없음",
];
const AREA_CATEGORIES = ["광소", "정상", "광대"];
const CURRENT_YEAR = new Date().getFullYear();

function MultiSelect({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: string[];
  value: string[] | null;
  onChange: (v: string[] | null) => void;
}) {
  const selected = value ?? [];
  const toggle = (opt: string) => {
    const next = selected.includes(opt)
      ? selected.filter((s) => s !== opt)
      : [...selected, opt];
    onChange(next.length === 0 ? null : next);
  };

  return (
    <div className="mb-4">
      <p className="text-xs font-semibold text-slate-500 mb-1 uppercase">{label}</p>
      <div className="flex flex-wrap gap-1">
        {options.map((opt) => (
          <button
            key={opt}
            onClick={() => toggle(opt)}
            className={`px-2 py-0.5 rounded text-xs border transition-colors ${
              selected.includes(opt)
                ? "bg-blue-600 text-white border-blue-600"
                : "bg-white text-slate-600 border-slate-300 hover:border-blue-400"
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  );
}

function YearRange() {
  const { paidRequest, setPaidRequest } = useAppStore();

  return (
    <div className="mb-4">
      <p className="text-xs font-semibold text-slate-500 mb-1 uppercase">기간</p>
      <div className="flex items-center gap-2">
        <input
          type="number"
          min={2006}
          max={CURRENT_YEAR}
          value={paidRequest.year_from ?? ""}
          placeholder="시작연도"
          onChange={(e) =>
            setPaidRequest({ year_from: e.target.value ? Number(e.target.value) : null })
          }
          className="w-24 border border-slate-300 rounded px-2 py-1 text-xs"
        />
        <span className="text-slate-400 text-xs">~</span>
        <input
          type="number"
          min={2006}
          max={CURRENT_YEAR}
          value={paidRequest.year_to ?? ""}
          placeholder="종료연도"
          onChange={(e) =>
            setPaidRequest({ year_to: e.target.value ? Number(e.target.value) : null })
          }
          className="w-24 border border-slate-300 rounded px-2 py-1 text-xs"
        />
      </div>
    </div>
  );
}

export default function FilterPanel() {
  const { paidRequest, setPaidRequest } = useAppStore();

  return (
    <div className="bg-white rounded-xl shadow-sm p-4">
      <h2 className="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
        <span className="inline-block w-2 h-2 rounded-full bg-blue-500" />
        유료 분석 필터
      </h2>

      <YearRange />

      <MultiSelect
        label="도로조건"
        options={ROAD_CONDITIONS}
        value={paidRequest.road_conditions ?? null}
        onChange={(v) => setPaidRequest({ road_conditions: v })}
      />

      <MultiSelect
        label="면적구분"
        options={AREA_CATEGORIES}
        value={paidRequest.area_categories ?? null}
        onChange={(v) => setPaidRequest({ area_categories: v })}
      />

      <div className="mb-4 space-y-2">
        <p className="text-xs font-semibold text-slate-500 uppercase">옵션</p>
        <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
          <input
            type="checkbox"
            checked={paidRequest.exclude_partial}
            onChange={(e) => setPaidRequest({ exclude_partial: e.target.checked })}
            className="rounded"
          />
          지분거래 제외
        </label>
        <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
          <input
            type="checkbox"
            checked={paidRequest.exclude_outlier}
            onChange={(e) => setPaidRequest({ exclude_outlier: e.target.checked })}
            className="rounded"
          />
          이상치 제외 (IQR×3)
        </label>
      </div>
    </div>
  );
}
