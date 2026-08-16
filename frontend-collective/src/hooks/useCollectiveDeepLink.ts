import { useEffect, useMemo, useRef } from "react";
import {
  fetchRegionNameRow,
  matchNamedOption,
  parseRegionDeepLink,
} from "@ch2/macro-shell/regionDeepLink";

type LeafOpt = { name: string; parent?: string | null };

export function useCollectiveDeepLink({
  addr1,
  addr2,
  addr1Options,
  addr2Options,
  leafOptions,
  setAddr1,
  setAddr2,
  setLeafList,
  setGuList,
}: {
  addr1: string;
  addr2: string;
  addr1Options: readonly string[];
  addr2Options: readonly string[];
  leafOptions: LeafOpt[];
  setAddr1: (v: string) => void;
  setAddr2: (v: string) => void;
  setLeafList: (v: string[]) => void;
  setGuList: (v: string[]) => void;
}) {
  const link = useMemo(() => parseRegionDeepLink(), []);
  const names = useRef<{ sido: string; sigungu: string; eup: string } | null>(null);
  const started = useRef(false);
  const leafApplied = useRef(false);

  useEffect(() => {
    if (!link || started.current) return;
    started.current = true;
    void (async () => {
      const row = await fetchRegionNameRow(link.regionLevel, link.regionCode);
      if (!row) return;
      names.current = {
        sido: row.sido_name,
        sigungu: link.regionLevel === "sido" ? "" : row.sigungu_name,
        eup:
          link.regionLevel === "eupmyeondong" || link.regionLevel === "beopjungri"
            ? row.eupmyeondong_name
            : "",
      };
      setAddr1(row.sido_name);
    })();
  }, [link, setAddr1]);

  useEffect(() => {
    const n = names.current;
    if (!n?.sido || !addr1Options.length) return;
    const a1 = matchNamedOption(addr1Options, n.sido);
    if (a1 && a1 !== addr1) setAddr1(a1);
  }, [addr1Options, addr1, setAddr1]);

  useEffect(() => {
    const n = names.current;
    if (!n?.sigungu || !addr2Options.length) return;
    const a2 = matchNamedOption(addr2Options, n.sigungu);
    if (a2 && a2 !== addr2) setAddr2(a2);
  }, [addr2Options, addr2, setAddr2]);

  useEffect(() => {
    const n = names.current;
    if (!n?.eup || leafApplied.current || !addr1 || !addr2) return;
    const hit = leafOptions.find((o) => o.name === n.eup);
    if (!hit) return;
    leafApplied.current = true;
    setLeafList([hit.name]);
    if (hit.parent) setGuList([hit.parent]);
  }, [leafOptions, addr1, addr2, setLeafList, setGuList]);
}
