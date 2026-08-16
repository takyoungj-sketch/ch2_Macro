import type { ReactNode } from "react";
import clsx from "clsx";
import { getDecision, STATUS_LABEL, type DecisionCard } from "../labContent";

export function WhyLinks({
  ids,
  onWhy,
  className,
}: {
  ids: string[];
  onWhy: (id: string) => void;
  className?: string;
}) {
  if (!ids.length) return null;
  return (
    <div className={clsx("flex flex-wrap items-center gap-2", className)}>
      {ids.map((id) => (
        <button
          key={id}
          type="button"
          className="text-[11px] text-amber-800 dark:text-amber-200 underline underline-offset-2"
          onClick={() => onWhy(id)}
        >
          왜 이렇게? {id}
        </button>
      ))}
    </div>
  );
}

export default function WhyDecision({
  id,
  onClose,
}: {
  id: string;
  onClose: () => void;
}) {
  const d = getDecision(id);
  if (!d) {
    return (
      <Modal onClose={onClose}>
        <p className="text-sm">결정 카드가 없습니다: {id}</p>
        <p className="text-xs text-slate-500 mt-1">원장은 docs/DECISIONS.md 입니다.</p>
      </Modal>
    );
  }
  return (
    <Modal onClose={onClose}>
      <DecisionBody d={d} />
    </Modal>
  );
}

export function DecisionBody({ d }: { d: DecisionCard }) {
  return (
    <div className="space-y-3 text-sm">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{d.id}</p>
        <h3 className="text-base font-bold mt-0.5">{d.topic}</h3>
        <p className="text-xs text-slate-500 mt-1">
          {d.date} ·{" "}
          <span
            className={clsx(
              d.status === "confirmed" && "text-emerald-700 dark:text-emerald-300",
              d.status === "experimental" && "text-amber-700 dark:text-amber-300",
            )}
          >
            {STATUS_LABEL[d.status]}
          </span>
        </p>
      </div>
      <Field k="배경" v={d.background} />
      <Field k="결정" v={d.decision} />
      <Field k="근거" v={d.rationale} />
      <Field k="재검토 조건" v={d.revisit} />
    </div>
  );
}

function Field({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <p className="text-[11px] font-semibold text-slate-500">{k}</p>
      <p className="mt-0.5 leading-relaxed">{v}</p>
    </div>
  );
}

function Modal({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center bg-slate-900/40 p-4 overflow-y-auto">
      <div className="card w-full max-w-lg my-10 p-4 space-y-3">
        <div className="flex justify-between items-start gap-2">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-200">
            왜 이렇게 만들어졌지?
          </p>
          <button type="button" className="text-xs text-slate-500" onClick={onClose}>
            닫기
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
