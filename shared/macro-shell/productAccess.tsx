// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useNarrowScreen } from "./useNarrowScreen";

export type ProductAccessStatus = "loading" | "anonymous" | "login" | "macro";

type ProductAccessValue = {
  status: ProductAccessStatus;
  entitled: boolean;
  narrow: boolean;
  requestPaid: () => void;
};

const ProductAccessContext = createContext<ProductAccessValue | null>(null);

async function loadStatus(): Promise<ProductAccessStatus> {
  try {
    const auth = await fetch("/api/auth/status", { credentials: "include" });
    if (!auth.ok) return "anonymous";
    const body = (await auth.json()) as { logged_in?: boolean; role?: string; local_dev_access?: boolean };
    if (import.meta.env.DEV && ["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname) && body.local_dev_access === true) {
      return "macro";
    }
    if (!body.logged_in) return "anonymous";
    if (body.role === "admin") return "macro";
    const sub = await fetch("/api/billing/subscription/me", { credentials: "include" });
    if (!sub.ok) return "login";
    const subBody = (await sub.json()) as { entitlements?: { macro?: boolean } };
    return subBody.entitlements?.macro ? "macro" : "login";
  } catch {
    return "anonymous";
  }
}

export function ProductAccessProvider({ children }: { children: ReactNode }) {
  const narrow = useNarrowScreen();
  const [status, setStatus] = useState<ProductAccessStatus>("loading");
  const [lockOpen, setLockOpen] = useState(false);

  useEffect(() => {
    let cancel = false;
    loadStatus().then((next) => {
      if (!cancel) setStatus(next);
    });
    return () => {
      cancel = true;
    };
  }, []);

  const requestPaid = useCallback(() => setLockOpen(true), []);
  const value = useMemo<ProductAccessValue>(
    () => ({
      status,
      entitled: status === "macro",
      narrow,
      requestPaid,
    }),
    [status, narrow, requestPaid],
  );

  return (
    <ProductAccessContext.Provider value={value}>
      {children}
      <ProductLockDialog
        open={lockOpen}
        status={status}
        narrow={narrow}
        onClose={() => setLockOpen(false)}
      />
    </ProductAccessContext.Provider>
  );
}

export function useProductAccess(): ProductAccessValue {
  const value = useContext(ProductAccessContext);
  if (!value) {
    throw new Error("ProductAccessProvider가 필요합니다.");
  }
  return value;
}

function loginHref(provider: "google" | "kakao"): string {
  const next = `${window.location.pathname}${window.location.search}`;
  return `/api/auth/${provider}/login?next=${encodeURIComponent(next)}`;
}

export function ProductLockDialog({
  open,
  status,
  narrow,
  onClose,
  dismissible = true,
}: {
  open: boolean;
  status: ProductAccessStatus;
  narrow: boolean;
  onClose: () => void;
  dismissible?: boolean;
}) {
  if (!open) return null;
  const mobile = narrow;
  const subscribedAsk = !mobile && status === "login";
  const title = mobile
    ? "기본통계와 롤링"
    : subscribedAsk
      ? "구독이 필요합니다"
      : "로그인이 필요합니다";
  const body = mobile
    ? "이 화면은 기본통계와 5년 롤링만 보여 줍니다."
    : subscribedAsk
      ? "상세 분석은 구독 뒤에 열립니다. 기본통계와 가격 추이는 그대로 볼 수 있습니다."
      : "상세 분석은 로그인이 필요합니다. 기본통계와 가격 추이는 그대로 볼 수 있습니다.";

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="ch2-product-lock-title"
        className="w-full max-w-sm rounded-xl bg-white p-4 text-slate-800 shadow-lg dark:bg-slate-800 dark:text-slate-100"
      >
        <h2 id="ch2-product-lock-title" className="text-base font-semibold">
          {title}
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-300">{body}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {!mobile && !subscribedAsk ? (
            <>
              <a className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white" href={loginHref("google")}>
                Google 로그인
              </a>
              <a className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-semibold" href={loginHref("kakao")}>
                카카오 로그인
              </a>
            </>
          ) : null}
          {!mobile && subscribedAsk ? (
            <a className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white" href="/subscribe/">
              구독 안내
            </a>
          ) : null}
          {dismissible ? (
            <button
              type="button"
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm"
              onClick={onClose}
            >
              닫기
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function ProductWall({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ProductAccessStatus>("loading");

  useEffect(() => {
    let cancel = false;
    loadStatus().then((next) => {
      if (!cancel) setStatus(next);
    });
    return () => {
      cancel = true;
    };
  }, []);

  if (status === "loading") {
    return <p className="p-6 text-sm text-slate-500">권한 확인 중…</p>;
  }
  if (status === "macro") return children;
  return (
    <div className="min-h-screen bg-slate-50 p-6 dark:bg-slate-900">
      <ProductLockDialog open status={status} narrow={false} dismissible={false} onClose={() => undefined} />
    </div>
  );
}
