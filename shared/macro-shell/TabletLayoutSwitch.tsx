// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
import { useLayoutChoice, useTabletChoiceBand, writeLayoutChoice } from "./useNarrowScreen";

export default function TabletLayoutSwitch() {
  const tablet = useTabletChoiceBand();
  const choice = useLayoutChoice();
  if (!tablet) return null;

  return (
    <div className="macro-layout-switch" role="group" aria-label="화면 구성">
      <button type="button" aria-pressed={choice === "pc"} onClick={() => writeLayoutChoice("pc")}>
        PC
      </button>
      <button type="button" aria-pressed={choice === "mobile"} onClick={() => writeLayoutChoice("mobile")}>
        모바일
      </button>
    </div>
  );
}
