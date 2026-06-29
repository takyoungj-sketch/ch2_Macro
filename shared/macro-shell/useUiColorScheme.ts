// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
import { useCallback, useLayoutEffect, useState } from "react";
import {
  type UiColorScheme,
  applyColorScheme,
  persistColorScheme,
  readStoredColorScheme,
} from "./displayUi";

export function useUiColorScheme() {
  const [colorScheme, setColorScheme] = useState<UiColorScheme>(readStoredColorScheme);

  useLayoutEffect(() => {
    applyColorScheme(colorScheme);
  }, [colorScheme]);

  const toggleUiColorScheme = useCallback(() => {
    setColorScheme((prev) => {
      const next: UiColorScheme = prev === "dark" ? "light" : "dark";
      persistColorScheme(next);
      applyColorScheme(next);
      return next;
    });
  }, []);

  return { colorScheme, isDark: colorScheme === "dark", toggleUiColorScheme };
}
