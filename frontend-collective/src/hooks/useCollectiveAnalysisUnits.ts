import { useCallback, useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchCollectiveMapResolveCodes, lookupCollectiveRegionCode } from "../api/mapClient";
import { formatScopeAddr2, resolveUnitAddr2 } from "../utils/flatSidoRegion";
import {
  analysisUnitLabel,
  MAX_COLLECTIVE_ANALYSIS_UNITS,
  unitsToRegionScope,
  type CollectiveAnalysisUnit,
} from "../utils/collectiveAnalysisUnits";
import { profileHref, resolveCollectiveProfileTargetFromUnits } from "../utils/profileLink";

export function useCollectiveAnalysisUnits(opts: {
  assetType: string;
  addr1: string;
  addr2: string;
  guList: string[];
  leafList: string[];
  setLeafList: Dispatch<SetStateAction<string[]>>;
  commercial?: boolean;
}) {
  const { assetType, addr1, addr2, guList, leafList, setLeafList, commercial = false } = opts;
  const [analysisUnits, setAnalysisUnits] = useState<CollectiveAnalysisUnit[]>([]);

  const resolveUnitsQ = useQuery({
    queryKey: [
      "collective-analysis-resolve",
      commercial ? "commercial" : "residential",
      assetType,
      addr1,
      addr2,
      guList.join(","),
      leafList.join(","),
    ],
    queryFn: () =>
      fetchCollectiveMapResolveCodes({
        assetType,
        addr1,
        addr2,
        gu: guList,
        leaf: leafList,
        commercial,
      }),
    enabled: !!addr1 && !!addr2 && leafList.length > 0,
    staleTime: 30_000,
  });

  useEffect(() => {
    const data = resolveUnitsQ.data;
    if (!data?.selected_codes?.length) {
      if (!leafList.length) {
        setAnalysisUnits((prev) => prev.filter((u) => u.crossParent));
      }
      return;
    }
    const level = data.level === "beopjungri" ? "beopjungri" : "eupmyeondong";
    const addr2Label = formatScopeAddr2(addr2, addr1) || addr2;
    const local: CollectiveAnalysisUnit[] = data.selected_codes.map((code, idx) => {
      const label = (data.labels?.[code] || "").trim();
      const parts = label.split(/\s+/).filter(Boolean);
      let name = parts[parts.length - 1] || "";
      if (!name || /^\d{8,10}$/.test(name)) {
        name =
          (leafList.length === data.selected_codes.length
            ? leafList[idx]
            : leafList.length === 1
              ? leafList[0]
              : "") ||
          name ||
          code;
      }
      const eup = level === "beopjungri" && parts.length >= 2 ? parts[parts.length - 2] : undefined;
      return { code, level, name, addr1, addr2: addr2Label, eup, crossParent: false };
    });
    setAnalysisUnits((prev) => {
      const localCodes = new Set(local.map((u) => u.code));
      const localKeys = new Set(local.map((u) => `${u.addr2}|${u.name}`.toLowerCase()));
      const anchorSig = (local[0]?.code || "").replace(/\D/g, "").slice(0, 5);
      const foreign = prev.filter((u) => {
        if (localCodes.has(u.code)) return false;
        if (localKeys.has(`${u.addr2}|${u.name}`.toLowerCase())) return false;
        if (u.crossParent) return true;
        if (u.addr1 && addr1 && u.addr1.trim() !== addr1.trim()) return true;
        if (u.addr2 && addr2Label && u.addr2 !== addr2Label && u.addr2 !== addr2) return true;
        const sig = u.code.replace(/\D/g, "").slice(0, 5);
        return Boolean(anchorSig && sig && sig !== anchorSig);
      });
      return [...local, ...foreign].slice(0, MAX_COLLECTIVE_ANALYSIS_UNITS);
    });
  }, [resolveUnitsQ.data, leafList, addr1, addr2]);

  const regionCodeScope = useMemo(() => unitsToRegionScope(analysisUnits), [analysisUnits]);
  const profileTarget = useMemo(
    () => resolveCollectiveProfileTargetFromUnits(analysisUnits),
    [analysisUnits],
  );

  const removeAnalysisUnit = useCallback(
    (code: string) => {
      setAnalysisUnits((prev) => {
        const target = prev.find((u) => u.code === code);
        const next = prev.filter((u) => u.code !== code);
        if (target?.level === "eupmyeondong") {
          setLeafList((leaves) => leaves.filter((n) => n !== target.name));
        }
        return next;
      });
    },
    [setLeafList],
  );

  const addUnit = useCallback(
    (unit: CollectiveAnalysisUnit) => {
      void (async () => {
        let next = { ...unit };
        const anchorAddr2 = formatScopeAddr2(addr2, addr1) || addr2;
        try {
          const looked = await lookupCollectiveRegionCode({
            addr1: next.addr1 || addr1 || undefined,
            addr2: next.addr2 || undefined,
            leaf: next.name,
            code: next.code,
            level: next.level,
            eup: next.eup,
          });
          next = {
            ...next,
            code: looked.code || next.code,
            addr1: looked.addr1 || next.addr1 || addr1,
            addr2: looked.addr2 || next.addr2,
            name: looked.leaf || next.name,
          };
        } catch {
          /* keep map fields */
        }

        const anchorSig = (analysisUnits[0]?.code || "").replace(/\D/g, "").slice(0, 5);
        const unitSig = next.code.replace(/\D/g, "").slice(0, 5);
        const unitAddr1 = (next.addr1 || addr1 || "").trim();
        const anchorAddr1 = (addr1 || "").trim();
        const crossParent =
          Boolean(unit.crossParent) ||
          Boolean(anchorSig && unitSig && anchorSig !== unitSig) ||
          Boolean(
            unitAddr1 &&
              anchorAddr1 &&
              unitAddr1 !== anchorAddr1 &&
              !unitAddr1.startsWith(anchorAddr1) &&
              !anchorAddr1.startsWith(unitAddr1),
          ) ||
          Boolean(next.addr2 && next.addr2 !== addr2 && next.addr2 !== anchorAddr2);
        next = {
          ...next,
          crossParent,
          addr2: resolveUnitAddr2(anchorAddr1, addr2, unitAddr1, next.addr2 || "", crossParent),
        };

        setAnalysisUnits((prev) => {
          if (prev.some((u) => u.code === next.code || (u.name === next.name && u.addr2 === next.addr2))) {
            return prev.map((u) =>
              u.code === next.code || (u.name === next.name && u.addr2 === next.addr2)
                ? { ...u, ...next }
                : u,
            );
          }
          if (prev.length >= MAX_COLLECTIVE_ANALYSIS_UNITS) return prev;
          return [...prev, next];
        });

        if (crossParent) return;
        if (next.level === "eupmyeondong") {
          setLeafList((prev) => (prev.includes(next.name) ? prev : [...prev, next.name]));
        }
      })();
    },
    [addr1, addr2, analysisUnits, setLeafList],
  );

  const clearUnits = useCallback(() => {
    setAnalysisUnits([]);
    setLeafList(() => []);
  }, [setLeafList]);

  return {
    analysisUnits,
    setAnalysisUnits,
    regionCodeScope,
    profileTarget,
    profileHref,
    analysisUnitLabel,
    maxUnits: MAX_COLLECTIVE_ANALYSIS_UNITS,
    removeAnalysisUnit,
    addUnit,
    clearUnits,
  };
}
