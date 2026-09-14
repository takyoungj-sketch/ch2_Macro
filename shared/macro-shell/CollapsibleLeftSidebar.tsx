// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
import { useCallback, useRef, useState, type ReactNode } from "react";
import "./collapsibleLeftSidebar.css";

const STORAGE_PREFIX = "ch2-left-sidebar-collapsed:";

function readStored(storageKey: string): boolean {
  try {
    return window.localStorage.getItem(`${STORAGE_PREFIX}${storageKey}`) === "1";
  } catch {
    return false;
  }
}

function persist(storageKey: string, collapsed: boolean) {
  try {
    window.localStorage.setItem(`${STORAGE_PREFIX}${storageKey}`, collapsed ? "1" : "0");
  } catch {
    /* ignore quota / private mode */
  }
}

export default function CollapsibleLeftSidebar({
  storageKey,
  label = "필터",
  className,
  children,
}: {
  storageKey: string;
  label?: string;
  className: string;
  children: ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(() => readStored(storageKey));
  const railRef = useRef<HTMLButtonElement | null>(null);

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      persist(storageKey, next);
      if (next) {
        queueMicrotask(() => railRef.current?.focus());
      }
      return next;
    });
  }, [storageKey]);

  return (
    <div className={`ch2-left-sidebar-wrap${collapsed ? " is-collapsed" : ""}`}>
      <aside
        className={`ch2-left-sidebar-panel ${className}`}
        aria-hidden={collapsed}
      >
        {children}
      </aside>
      <button
        ref={railRef}
        type="button"
        className="ch2-left-sidebar-rail"
        aria-expanded={!collapsed}
        aria-label={collapsed ? `${label} 펼치기` : `${label} 접기`}
        title={collapsed ? `${label} 펼치기` : `${label} 접기`}
        onClick={toggle}
      >
        <svg
          className="ch2-left-sidebar-rail-chevron"
          viewBox="0 0 16 16"
          aria-hidden
        >
          {collapsed ? (
            <path
              d="M6 3.5 L11 8 L6 12.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ) : (
            <path
              d="M10 3.5 L5 8 L10 12.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}
        </svg>
        {collapsed ? <span className="ch2-left-sidebar-rail-label">{label}</span> : null}
      </button>
    </div>
  );
}
