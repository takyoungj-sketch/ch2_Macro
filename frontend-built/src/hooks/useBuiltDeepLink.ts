import { useEffect, useMemo, useRef } from "react";
import { fetchRegionNameRow, parseRegionDeepLink } from "@ch2/macro-shell/regionDeepLink";
import { lookupBuiltRegionCode } from "../api/client";

type LeafOpt = { name: string; parent?: string | null };

export function useBuiltDeepLink({
  assetType,
  setAddr1,
  setAddr2,
  setLeafList,
  setGuList,
  leafOptions,
}: {
  assetType: string;
  setAddr1: (v: string) => void;
  setAddr2: (v: string) => void;
  setLeafList: (v: string[]) => void;
  setGuList: (v: string[]) => void;
  leafOptions: LeafOpt[];
}) {
  const link = useMemo(() => parseRegionDeepLink(), []);
  const started = useRef(false);
  const pendingLeaf = useRef<string | null>(null);

  useEffect(() => {
    if (!link || started.current) return;
    started.current = true;
    void (async () => {
      const digits = link.regionCode.replace(/\D/g, "");
      if (digits.length >= 8) {
        try {
          const looked = await lookupBuiltRegionCode({
            code: digits,
            level: digits.length >= 10 ? "beopjungri" : "eupmyeondong",
            assetType,
          });
          if (looked.addr1) setAddr1(looked.addr1);
          if (looked.addr2) setAddr2(looked.addr2);
          if (looked.leaf) pendingLeaf.current = looked.leaf;
          return;
        } catch {
          /* catalog fallback */
        }
      }
      const row = await fetchRegionNameRow(link.regionLevel, link.regionCode);
      if (!row) return;
      setAddr1(row.sido_name);
      if (link.regionLevel !== "sido") setAddr2(row.sigungu_name);
      if (link.regionLevel === "eupmyeondong" || link.regionLevel === "beopjungri") {
        pendingLeaf.current = row.eupmyeondong_name;
      }
    })();
  }, [link, assetType, setAddr1, setAddr2]);

  useEffect(() => {
    const leaf = pendingLeaf.current;
    if (!leaf) return;
    const hit = leafOptions.find((o) => o.name === leaf);
    if (!hit) return;
    pendingLeaf.current = null;
    setLeafList([hit.name]);
    if (hit.parent) setGuList([hit.parent]);
  }, [leafOptions, setLeafList, setGuList]);
}
