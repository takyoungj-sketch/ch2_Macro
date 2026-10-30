import { useEffect, useState } from "react";
import { useNarrowScreen } from "@ch2/macro-shell/useNarrowScreen";

function useMedia(query: string): boolean {
  const [on, setOn] = useState(() => typeof window !== "undefined" && window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const sync = () => setOn(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, [query]);
  return on;
}

/** 세로 휴대폰과, 가로로 돌린 휴대폰. 가로 폭이 767을 넘어도 휴대폰 화면으로 본다. */
const PHONE = "(max-width: 767px), (max-height: 500px) and (max-width: 1024px)";
const PORTRAIT = "(orientation: portrait) and (max-width: 767px)";

export function useCollectivePhone(): boolean {
  const hardwarePhone = useMedia(PHONE);
  const narrow = useNarrowScreen();
  return hardwarePhone || narrow;
}

export function useCollectivePortrait(): boolean {
  return useMedia(PORTRAIT);
}
