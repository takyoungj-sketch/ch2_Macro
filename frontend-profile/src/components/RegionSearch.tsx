import { useEffect, useMemo, useRef, useState } from "react";
import { searchRegions } from "../api/profile";
import type { RegionLevel, RegionNameInfo } from "../types";

export interface RegionSearchResult {
  level: RegionLevel;
  code: string;
  label: string;
  sublabel: string;
}

interface Props {
  onSelect: (region: RegionSearchResult) => void;
}

/** 법정동(리) grain 검색 결과를 시/도·시군구·읍면동 단위로 dedup — D-027. */
function groupResults(rows: RegionNameInfo[]): {
  sido: RegionSearchResult[];
  sigungu: RegionSearchResult[];
  eup: RegionSearchResult[];
} {
  const sidoMap = new Map<string, RegionSearchResult>();
  const sigunguMap = new Map<string, RegionSearchResult>();
  const eupMap = new Map<string, RegionSearchResult>();

  for (const r of rows) {
    if (r.sido_code && !sidoMap.has(r.sido_code)) {
      sidoMap.set(r.sido_code, {
        level: "sido",
        code: r.sido_code,
        label: `${r.sido_name} 전체`,
        sublabel: "시/도",
      });
    }
    if (r.sigungu_code && !sigunguMap.has(r.sigungu_code)) {
      sigunguMap.set(r.sigungu_code, {
        level: "sigungu",
        code: r.sigungu_code,
        label: `${r.sigungu_name} 전체`,
        sublabel: r.sido_name,
      });
    }
    if (r.eupmyeondong_code && !eupMap.has(r.eupmyeondong_code)) {
      eupMap.set(r.eupmyeondong_code, {
        level: "eupmyeondong",
        code: r.eupmyeondong_code,
        label: r.eupmyeondong_name,
        sublabel: `${r.sido_name} ${r.sigungu_name}`,
      });
    }
  }

  return {
    sido: [...sidoMap.values()],
    sigungu: [...sigunguMap.values()],
    eup: [...eupMap.values()],
  };
}

export default function RegionSearch({ onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<RegionNameInfo[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    let active = true;
    setLoading(true);
    const timer = setTimeout(() => {
      searchRegions(query)
        .then((r) => {
          if (active) setResults(r);
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query]);

  const grouped = useMemo(() => groupResults(results), [results]);
  const hasAny = grouped.sido.length > 0 || grouped.sigungu.length > 0 || grouped.eup.length > 0;

  const pick = (target: RegionSearchResult) => {
    onSelect(target);
    setQuery(target.sublabel ? `${target.sublabel} ${target.label}` : target.label);
    setOpen(false);
  };

  return (
    <div ref={boxRef} className="relative w-full max-w-md">
      <input
        type="text"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        placeholder="지역명 또는 법정동코드 검색 (예: 가경동, 흥덕구)"
        className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-slate-500 dark:border-slate-600 dark:bg-slate-900"
      />
      {open && (query.trim().length >= 2 || loading) && (
        <div className="absolute z-10 mt-1 w-full rounded-md border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800">
          {loading ? (
            <div className="px-3 py-2 text-sm text-slate-400">검색 중...</div>
          ) : !hasAny ? (
            <div className="px-3 py-2 text-sm text-slate-400">결과 없음</div>
          ) : (
            <ul className="max-h-80 overflow-y-auto py-1">
              {grouped.sido.map((opt) => (
                <ResultItem key={`sido-${opt.code}`} opt={opt} onPick={pick} />
              ))}
              {grouped.sigungu.map((opt) => (
                <ResultItem key={`sigungu-${opt.code}`} opt={opt} onPick={pick} />
              ))}
              {grouped.eup.map((opt) => (
                <ResultItem key={`eup-${opt.code}`} opt={opt} onPick={pick} />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function ResultItem({ opt, onPick }: { opt: RegionSearchResult; onPick: (opt: RegionSearchResult) => void }) {
  return (
    <li>
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-700"
        onClick={() => onPick(opt)}
      >
        <span>
          <span className="font-medium">{opt.label}</span>
          <span className="ml-1.5 text-xs text-slate-400">{opt.sublabel}</span>
        </span>
        {opt.level !== "eupmyeondong" && (
          <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500 dark:bg-slate-700 dark:text-slate-300">
            {opt.level === "sido" ? "시/도" : "시군구"}
          </span>
        )}
      </button>
    </li>
  );
}
