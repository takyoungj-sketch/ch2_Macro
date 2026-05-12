import { type ReactNode, useEffect, useId, useRef, useState } from "react";
import clsx from "clsx";

interface Props {
  /** 스크린리더용 */
  ariaLabel: string;
  /** 물음표 왼쪽 짧은 텍스트(선택) */
  compactLabel?: string;
  children: ReactNode;
  /** 패널 정렬: aside 좁을 때 right 권장 */
  align?: "left" | "right";
  className?: string;
}

/** 작은 물음표 — 클릭 시 패널, Escape·외부 클릭으로 닫힘 */
export default function HelpPopover({
  ariaLabel,
  compactLabel,
  children,
  align = "right",
  className,
}: Props) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (panelRef.current?.contains(t) || btnRef.current?.contains(t)) return;
      setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onDown);
    };
  }, [open]);

  return (
    <span className={clsx("relative inline-flex items-center gap-0.5 align-middle", className)}>
      {compactLabel ? (
        <span className="text-[10px] text-slate-500 font-normal">{compactLabel}</span>
      ) : null}
      <button
        ref={btnRef}
        type="button"
        className={clsx(
          "inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full border text-[11px] font-bold leading-none",
          open
            ? "border-blue-500 bg-blue-50 text-blue-800"
            : "border-slate-300 bg-white text-slate-600 hover:border-blue-400 hover:text-blue-800"
        )}
        aria-label={ariaLabel}
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => setOpen((v) => !v)}
      >
        ?
      </button>
      {open ? (
        <div
          ref={panelRef}
          id={id}
          role="region"
          className={clsx(
            "absolute z-[60] mt-1 top-full w-[min(22rem,calc(100vw-2rem))] rounded-lg border border-slate-200 bg-white p-3 shadow-lg text-left",
            align === "right" ? "right-0" : "left-0"
          )}
        >
          {children}
        </div>
      ) : null}
    </span>
  );
}
