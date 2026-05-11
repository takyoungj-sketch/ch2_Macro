import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchRegions } from "../api/client";
import { useAppStore } from "../store";
import type { RegionItem } from "../types";

export default function RegionSelector() {
  const { viewMode, selectedCode, selectedCodes, setSelectedCode, toggleSelectedCode } =
    useAppStore();
  const [sidoFilter, setSidoFilter] = useState("");
  const [search, setSearch] = useState("");

  const { data: regions = [], isLoading } = useQuery({
    queryKey: ["regions"],
    queryFn: () => fetchRegions(),
  });

  // 시도 목록
  const sidoList = [...new Set(regions.map((r) => r.sido_name))].sort();

  const filtered = regions.filter((r) => {
    const matchSido = !sidoFilter || r.sido_name === sidoFilter;
    const q = search.trim().toLowerCase();
    const matchSearch =
      !q ||
      r.beopjungri_name.includes(q) ||
      r.eupmyeondong_name.includes(q) ||
      r.sigungu_name.includes(q);
    return matchSido && matchSearch;
  });

  const handleClick = (r: RegionItem) => {
    if (viewMode === "free") {
      setSelectedCode(r.beopjungri_code);
    } else {
      toggleSelectedCode(r.beopjungri_code);
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm p-4 flex flex-col gap-2">
      <h2 className="text-sm font-bold text-slate-700">지역 선택</h2>

      <div className="flex gap-2">
        <select
          value={sidoFilter}
          onChange={(e) => setSidoFilter(e.target.value)}
          className="border border-slate-300 rounded px-2 py-1 text-xs flex-1"
        >
          <option value="">전체 시도</option>
          {sidoList.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <input
        type="text"
        placeholder="동/리 명칭 검색"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="border border-slate-300 rounded px-2 py-1 text-xs"
      />

      <div className="overflow-y-auto max-h-64 divide-y divide-slate-50">
        {isLoading ? (
          <p className="text-xs text-slate-400 py-4 text-center">불러오는 중...</p>
        ) : filtered.length === 0 ? (
          <p className="text-xs text-slate-400 py-4 text-center">결과 없음</p>
        ) : (
          filtered.slice(0, 200).map((r) => {
            const isSelected =
              viewMode === "free"
                ? selectedCode === r.beopjungri_code
                : selectedCodes.includes(r.beopjungri_code);
            return (
              <button
                key={r.beopjungri_code}
                onClick={() => handleClick(r)}
                className={`w-full text-left px-2 py-1.5 text-xs transition-colors ${
                  isSelected
                    ? "bg-blue-50 text-blue-700 font-medium"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                <span className="text-slate-400 text-[10px] mr-1">
                  {r.sigungu_name}
                </span>
                {r.eupmyeondong_name} {r.beopjungri_name}
              </button>
            );
          })
        )}
      </div>

      {viewMode === "paid" && selectedCodes.length > 0 && (
        <p className="text-xs text-blue-600 font-medium">
          {selectedCodes.length}개 지역 선택됨
        </p>
      )}
    </div>
  );
}
