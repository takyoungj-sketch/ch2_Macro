import { useEffect, useRef } from "react";
import type { RegionNameHit } from "../components/CollectiveMobileRegionBar";

/** 검색으로 고른 읍·면·동을, 시군구 구조가 준비된 뒤에 통계로 넘긴다. */
export function useApplyMobileRegion(opts: {
  phone: boolean;
  pending: RegionNameHit | null;
  setPending: (hit: RegionNameHit | null) => void;
  addr1: string;
  addr2: string;
  structureReady: boolean;
  hasIntermediate: boolean;
  guList: string[];
  leafList: string[];
  setGuList: (names: string[]) => void;
  setLeafList: (names: string[]) => void;
  run: () => void;
}) {
  const {
    phone,
    pending,
    setPending,
    addr1,
    addr2,
    structureReady,
    hasIntermediate,
    guList,
    leafList,
    setGuList,
    setLeafList,
    run,
  } = opts;
  const runRef = useRef(run);
  runRef.current = run;
  useEffect(() => {
    if (!phone || !pending) return;
    if (addr1 !== pending.addr1 || addr2 !== pending.addr2) return;
    if (!structureReady) return;
    if (hasIntermediate && pending.gu && guList[0] !== pending.gu) {
      setGuList([pending.gu]);
      return;
    }
    if (leafList[0] !== pending.leaf) {
      setLeafList([pending.leaf]);
      return;
    }
    runRef.current();
    setPending(null);
  }, [
    phone,
    pending,
    setPending,
    addr1,
    addr2,
    structureReady,
    hasIntermediate,
    guList,
    leafList,
    setGuList,
    setLeafList,
  ]);
}
