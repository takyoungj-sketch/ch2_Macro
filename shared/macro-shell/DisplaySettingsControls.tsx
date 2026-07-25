// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
type Props = {
  fontPct: number;
  fontStepMin: boolean;
  fontStepMax: boolean;
  onBump: (direction: 1 | -1) => void;
  isDark: boolean;
  onToggleTheme: () => void;
};

/** 복합부동산 페이지 기준 — 테마·글자 크기 컨트롤 (네 Macro 화면 공통, px 고정) */
export default function DisplaySettingsControls({
  fontPct,
  fontStepMin,
  fontStepMax,
  onBump,
  isDark,
  onToggleTheme,
}: Props) {
  return (
    <div className="macro-display-controls" aria-label="화면 표시 설정">
      <button
        type="button"
        role="switch"
        aria-checked={isDark}
        aria-label={isDark ? "밝은 테마로 전환" : "어두운 테마로 전환"}
        title={isDark ? "밝은 테마" : "어두운 테마"}
        className={`macro-theme-btn ${isDark ? "is-dark" : "is-light"}`}
        onClick={onToggleTheme}
      >
        <span aria-hidden>{isDark ? "☀" : "☾"}</span>
        <span>{isDark ? "밝게" : "어둡게"}</span>
      </button>
      <span className="macro-font-label">글자</span>
      <div className="macro-font-stepper">
        <button
          type="button"
          aria-label="글자 크기 줄이기"
          disabled={fontStepMin}
          onClick={() => onBump(-1)}
        >
          −
        </button>
        <span className="macro-font-pct" aria-live="polite">
          {fontPct}%
        </span>
        <button
          type="button"
          aria-label="글자 크기 키우기"
          disabled={fontStepMax}
          onClick={() => onBump(1)}
        >
          +
        </button>
      </div>
    </div>
  );
}
