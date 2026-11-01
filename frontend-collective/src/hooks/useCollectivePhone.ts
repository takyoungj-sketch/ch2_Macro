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

/** 세로 휴대폰. 가로로 돌린 휴대폰은 폭이 767을 넘어 이 조건에 안 든다. */
const PORTRAIT = "(orientation: portrait) and (max-width: 767px)";

/** 헤더와 같은 화면 판정. 가로 휴대폰도 모바일이다. */
export function useCollectivePhone(): boolean {
  return useNarrowScreen();
}

export function useCollectivePortrait(): boolean {
  return useMedia(PORTRAIT);
}
