import { useEffect, useRef, useState } from "react";

export type RegionNameHit = {
  addr1: string;
  addr2: string;
  gu: string;
  leaf: string;
  label: string;
};

type Props = {
  search: (query: string) => Promise<RegionNameHit[]>;
  onPick: (hit: RegionNameHit) => void;
  onClear: () => void;
};

export default function CollectiveMobileRegionBar({ search, onPick, onClear }: Props) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<RegionNameHit[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const searchRef = useRef(search);
  searchRef.current = search;

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setHits([]);
      return;
    }
    let cancel = false;
    const timer = window.setTimeout(() => {
      setBusy(true);
      searchRef.current(q)
        .then((rows) => {
          if (!cancel) setHits(rows);
        })
        .catch(() => {
          if (!cancel) setHits([]);
        })
        .finally(() => {
          if (!cancel) setBusy(false);
        });
    }, 250);
    return () => {
      cancel = true;
      window.clearTimeout(timer);
    };
  }, [query]);

  const pick = (hit: RegionNameHit) => {
    setError(null);
    setQuery("");
    setHits([]);
    onPick(hit);
  };

  const confirm = () => {
    const q = query.trim();
    if (hits.length === 1) {
      pick(hits[0]!);
      return;
    }
    const exact = hits.filter((hit) => hit.leaf === q);
    if (exact.length === 1) {
      pick(exact[0]!);
      return;
    }
    if (hits.length > 1) {
      setError("여러 곳입니다. 목록에서 고르세요.");
      return;
    }
    if (q.length < 2) {
      setError("읍·면·동 이름을 두 글자 이상 입력하세요.");
      return;
    }
    if (busy) return;
    setError("맞는 읍·면·동이 없습니다.");
  };

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <input
          type="search"
          autoComplete="off"
          spellCheck={false}
          aria-label="지역 입력"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              confirm();
            }
          }}
          className="input !h-5 !w-1/2 !min-w-0 !shrink !py-0 !px-2 text-xs leading-none"
        />
        <button
          type="button"
          aria-label="선택 초기화"
          className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded border border-slate-300 text-xs leading-none text-slate-600"
          onClick={() => {
            setQuery("");
            setHits([]);
            setError(null);
            onClear();
          }}
        >
          ×
        </button>
        <button
          type="button"
          className="inline-flex h-5 shrink-0 items-center rounded bg-blue-600 px-2 text-xs font-medium leading-none text-white"
          onClick={confirm}
        >
          검색
        </button>
      </div>
      {hits.length > 0 ? (
        <ul className="max-h-28 overflow-auto rounded border border-slate-200 bg-white text-xs dark:border-slate-600 dark:bg-slate-800">
          {hits.map((hit) => (
            <li key={`${hit.addr1}|${hit.addr2}|${hit.gu}|${hit.leaf}`}>
              <button
                type="button"
                className="block w-full truncate px-2 py-1 text-left hover:bg-slate-50 dark:hover:bg-slate-700"
                onClick={() => pick(hit)}
              >
                {hit.label}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {error ? (
        <p className="text-xs text-red-600" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
