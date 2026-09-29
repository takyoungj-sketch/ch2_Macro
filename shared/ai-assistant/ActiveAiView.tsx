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

export type AiContextRole = "base" | "overlay";

type Layer = { id: string; role: AiContextRole; ctx: AiContextPayload };

type Api = {
  context: AiContextPayload;
  fallback: AiContextPayload;
  upsert: (id: string, ctx: AiContextPayload, role: AiContextRole) => void;
  remove: (id: string) => void;
};

/** 기본통계(base)는 유지하고, 그 위에 마지막 모달(overlay) 결과를 얹는다. */
export function composeAiContext(layers: Layer[], fallback: AiContextPayload): AiContextPayload {
  if (layers.length === 0) return fallback;
  const bases = layers.filter((layer) => layer.role === "base");
  const overlays = layers.filter((layer) => layer.role !== "base");
  if (overlays.length === 0) {
    return bases.length > 0 ? bases[bases.length - 1].ctx : fallback;
  }
  const front = overlays[overlays.length - 1].ctx;
  if (bases.length === 0) return front;
  const base = bases[bases.length - 1].ctx;
  const baseFacts = { ...(base.facts || {}) };
  delete baseFacts.base_screen;
  return {
    ...front,
    scope: {
      ...(base.scope || {}),
      ...(front.scope || {}),
    },
    facts: {
      ...(front.facts || {}),
      base_screen: {
        panel: base.panel,
        purpose: base.purpose,
        scope: base.scope,
        facts: baseFacts,
      },
    },
    explain: front.explain ?? base.explain,
  };
}

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

  const upsert = useCallback((id: string, ctx: AiContextPayload, role: AiContextRole) => {
    setLayers((prev) => {
      const i = prev.findIndex((e) => e.id === id);
      if (i >= 0) {
        if (prev[i].ctx === ctx && prev[i].role === role) return prev;
        try {
          if (prev[i].role === role && JSON.stringify(prev[i].ctx) === JSON.stringify(ctx)) return prev;
        } catch {
          /* ignore */
        }
        const next = prev.slice();
        next[i] = { id, role, ctx };
        return next;
      }
      return [...prev, { id, role, ctx }];
    });
  }, []);

  const remove = useCallback((id: string) => {
    setLayers((prev) => prev.filter((e) => e.id !== id));
  }, []);

  const context = useMemo(() => composeAiContext(layers, fallback), [layers, fallback]);
  const value = useMemo(
    () => ({ context, fallback, upsert, remove }),
    [context, fallback, upsert, remove],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useActiveAiView(): AiContextPayload | null {
  return useContext(Ctx)?.context ?? null;
}

export function PublishAiContext({
  context,
  role = "overlay",
}: {
  context: AiContextPayload | null | undefined;
  role?: AiContextRole;
}) {
  const api = useContext(Ctx);
  const id = useId();

  useEffect(() => {
    if (!api) return;
    if (!context) {
      api.remove(id);
      return;
    }
    api.upsert(id, context, role);
    return () => api.remove(id);
  }, [api, id, context, role]);

  return null;
}
