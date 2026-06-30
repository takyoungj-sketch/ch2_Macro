// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
import { useCallback, useState } from "react";
import {
  UI_FONT_SCALE_STEPS,
  clampFontStep,
  persistFontStep,
  readStoredFontStep,
} from "./displayUi";

export function useUiFontScale() {
  const [fontStep, setFontStep] = useState(readStoredFontStep);

  const fontIdx = clampFontStep(fontStep);
  const contentZoom = UI_FONT_SCALE_STEPS[fontIdx];
  const fontPct = Math.round(contentZoom * 100);
  const fontStepMin = fontIdx <= 0;
  const fontStepMax = fontIdx >= UI_FONT_SCALE_STEPS.length - 1;

  const bumpUiFontScale = useCallback((direction: 1 | -1) => {
    setFontStep((prev) => {
      const next = clampFontStep(prev + direction);
      persistFontStep(next);
      return next;
    });
  }, []);

  return { contentZoom, fontPct, fontStepMin, fontStepMax, bumpUiFontScale };
}
