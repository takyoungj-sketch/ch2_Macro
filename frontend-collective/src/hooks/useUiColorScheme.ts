import { useCallback, useLayoutEffect, useState } from "react";
import {
  type UiColorScheme,
  applyColorScheme,
  persistColorScheme,
  readStoredColorScheme,
} from "../constants/displayUi";

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
