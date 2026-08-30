// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { AiApp, AiContextPayload, AiPurpose } from "./aiClient";

type Layer = { id: string; ctx: AiContextPayload };

type Api = {
  context: AiContextPayload;
  fallback: AiContextPayload;
  upsert: (id: string, ctx: AiContextPayload) => void;
  remove: (id: string) => void;
};

const Ctx = createContext<Api | null>(null);

export function emptyAiContext(
  app: AiApp,
  panel: string,
  opts?: { purpose?: AiPurpose; regionLabel?: string },
): AiContextPayload {
  return {
    app,
    panel,
    purpose: opts?.purpose ?? (app === "profile" ? "market_analysis" : "statistics"),
    scope: opts?.regionLabel ? { region_label: opts.regionLabel } : {},
    facts: {},
  };
}

export function ActiveAiViewProvider({
  fallback,
  children,
}: {
  fallback: AiContextPayload;
  children: ReactNode;
}) {
  const [layers, setLayers] = useState<Layer[]>([]);

  const upsert = useCallback((id: string, ctx: AiContextPayload) => {
    setLayers((prev) => {
      const i = prev.findIndex((e) => e.id === id);
      if (i >= 0) {
        if (prev[i].ctx === ctx) return prev;
        try {
          if (JSON.stringify(prev[i].ctx) === JSON.stringify(ctx)) return prev;
        } catch {
          /* ignore */
        }
        const next = prev.slice();
        next[i] = { id, ctx };
        return next;
      }
      return [...prev, { id, ctx }];
    });
  }, []);

  const remove = useCallback((id: string) => {
    setLayers((prev) => prev.filter((e) => e.id !== id));
  }, []);

  const context = layers[layers.length - 1]?.ctx ?? fallback;
  const value = useMemo(
    () => ({ context, fallback, upsert, remove }),
    [context, fallback, upsert, remove],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useActiveAiView(): AiContextPayload | null {
  return useContext(Ctx)?.context ?? null;
}

export function PublishAiContext({ context }: { context: AiContextPayload | null | undefined }) {
  const api = useContext(Ctx);
  const id = useId();

  useEffect(() => {
    if (!api) return;
    if (!context) {
      api.remove(id);
      return;
    }
    api.upsert(id, context);
    return () => api.remove(id);
  }, [api, id, context]);

  return null;
}
