// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
import { useEffect, useState } from "react";

const PHONE_QUERY = "(max-width: 767px)";
/** 터치 태블릿. 가로로 눕힌 휴대폰(높이 500 이하)은 빼 둔다. */
const TABLET_QUERY = "(min-width: 768px) and (max-width: 1366px) and (min-height: 501px) and (any-pointer: coarse)";
const CHOICE_KEY = "ch2.layout";
const CHOICE_EVENT = "ch2-layout-choice";

export type LayoutChoice = "pc" | "mobile";

let memoryChoice: LayoutChoice = "pc";

function readLayoutChoice(): LayoutChoice {
  try {
    const stored = window.localStorage.getItem(CHOICE_KEY);
    if (stored === "mobile" || stored === "pc") memoryChoice = stored;
  } catch {
    /* 저장소를 못 읽으면 이번 탭에서 고른 값을 쓴다 */
  }
  return memoryChoice;
}

export function writeLayoutChoice(choice: LayoutChoice) {
  memoryChoice = choice;
  try {
    window.localStorage.setItem(CHOICE_KEY, choice);
  } catch {
    /* 저장이 막혀 있어도 이번 화면에서는 선택을 반영한다 */
  }
  window.dispatchEvent(new Event(CHOICE_EVENT));
}

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia(query).matches : false,
  );

  useEffect(() => {
    const media = window.matchMedia(query);
    const apply = () => setMatches(media.matches);
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [query]);

  return matches;
}

export function useLayoutChoice(): LayoutChoice {
  const [choice, setChoice] = useState<LayoutChoice>(() =>
    typeof window !== "undefined" ? readLayoutChoice() : "pc",
  );

  useEffect(() => {
    const apply = () => setChoice(readLayoutChoice());
    window.addEventListener(CHOICE_EVENT, apply);
    window.addEventListener("storage", apply);
    return () => {
      window.removeEventListener(CHOICE_EVENT, apply);
      window.removeEventListener("storage", apply);
    };
  }, []);

  return choice;
}

/** 태블릿 너비의 터치 화면. 여기서만 PC/모바일 선택을 보여 준다. */
export function useTabletChoiceBand(): boolean {
  return useMediaQuery(TABLET_QUERY);
}

export function useNarrowScreen(): boolean {
  const phone = useMediaQuery(PHONE_QUERY);
  const tablet = useTabletChoiceBand();
  const choice = useLayoutChoice();
  return phone || (tablet && choice === "mobile");
}
