import clsx from "clsx";
import {
  COMMIT_LABEL,
  loadDecisions,
  loadJournals,
  plan,
  STATUS_LABEL,
  type PlanCell,
  type PlanDomainId,
} from "../labContent";

function formatDate(iso: string) {
  const [, m, d] = iso.split("-");
  return `${Number(m)}.${Number(d)}`;
}

export default function PlanLog({ onWhy }: { onWhy: (id: string) => void }) {
  const domains = plan.domains;
  const journals = loadJournals();
  const decisions = loadDecisions();

  return (
    <div className="max-w-[96rem] mx-auto px-4 py-5 space-y-8">
      <p className="text-sm text-slate-600 dark:text-slate-300">
        열은 CH2 제품 축입니다. 하루를 끝낼 때 「계획일지 정리」라고 하면 Cursor가 적습니다. 정리만 하고 커밋하지는 않습니다.
      </p>

      <div className="card overflow-x-auto">
        <table className="w-full table-fixed min-w-[84rem] text-sm border-collapse">
          <colgroup>
            <col className="w-[14.28%]" />
            {domains.map((d) => (
              <col key={d.id} className="w-[14.28%]" />
            ))}
          </colgroup>
          <thead>
            <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/80">
              <th className="px-4 py-2.5 text-left text-[11px] font-semibold text-slate-500">날짜</th>
              {domains.map((d) => (
                <th key={d.id} className="px-4 py-2.5 text-left text-[11px] font-semibold text-slate-500">
                  {d.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {plan.past.map((row) => (
              <GridRow key={row.date} label={formatDate(row.date)} cells={row.cells} domains={domains} onWhy={onWhy} />
            ))}
            <GridRow label="오늘" cells={plan.today.cells} domains={domains} onWhy={onWhy} emphasize />
            <GridRow label="다음" cells={plan.next.cells} domains={domains} onWhy={onWhy} />
            <tr className="border-t-2 border-slate-300 dark:border-slate-600">
              <th className="px-4 py-3 text-left text-[11px] font-semibold text-slate-500 align-top">공통</th>
              <td colSpan={domains.length} className="px-4 py-3">
                <CellView cell={{ text: plan.common.text, status: "planned", decision: plan.common.decision }} onWhy={onWhy} />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">이날 메모</h2>
        {journals.map((j) => (
          <article key={j.date} className="card p-4 space-y-2">
            <h3 className="font-semibold">{j.date.replace(/-/g, ".")}</h3>
            {j.work.length > 0 && <MemoList title="작업" items={j.work} />}
            {j.next.length > 0 && <MemoList title="다음" items={j.next} />}
            {j.commit.length > 0 && <MemoList title="커밋" items={j.commit} />}
            {j.tags.length > 0 && (
              <ul className="text-xs space-y-0.5">
                {j.tags.map((t) => (
                  <li key={t.kind + t.text}>
                    <span
                      className={clsx(
                        "rounded px-1 py-0.5 mr-1 font-semibold",
                        t.kind === "T" && "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900",
                        t.kind === "제안" && "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/50 dark:text-indigo-100",
                        t.kind === "구현" && "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-100",
                      )}
                    >
                      {t.kind}
                    </span>
                    {t.text}
                  </li>
                ))}
              </ul>
            )}
          </article>
        ))}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">관련 결정</h2>
        <p className="text-xs text-slate-500">번호 원장 docs/DECISIONS.md. 칸의 D-번호와 같습니다.</p>
        <div className="grid gap-2 sm:grid-cols-2">
          {decisions.map((d) => (
            <button
              key={d.id}
              type="button"
              className="card p-3 text-left hover:border-amber-400"
              onClick={() => onWhy(d.id)}
            >
              <p className="text-[10px] font-semibold text-slate-500">
                {d.id} · {STATUS_LABEL[d.status]}
              </p>
              <p className="font-semibold mt-0.5">{d.topic}</p>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

function GridRow({
  label,
  cells,
  domains,
  onWhy,
  emphasize,
}: {
  label: string;
  cells: Partial<Record<PlanDomainId, PlanCell>>;
  domains: { id: PlanDomainId; label: string }[];
  onWhy: (id: string) => void;
  emphasize?: boolean;
}) {
  return (
    <tr className={clsx("border-b border-slate-200 dark:border-slate-700", emphasize && "bg-amber-50/70 dark:bg-amber-950/20")}>
      <th className="px-4 py-3 text-left text-[11px] font-semibold text-slate-500 align-top">
        {label}
      </th>
      {domains.map((d) => (
        <td key={d.id} className="px-4 py-3 align-top break-words">
          {cells[d.id] ? <CellView cell={cells[d.id]!} onWhy={onWhy} /> : <span className="text-slate-300 dark:text-slate-600">·</span>}
        </td>
      ))}
    </tr>
  );
}

function CellView({ cell, onWhy }: { cell: PlanCell; onWhy: (id: string) => void }) {
  const commitLabel = cell.commit ? COMMIT_LABEL[cell.commit] : "";
  return (
    <div className="space-y-1">
      <p className="leading-snug">
        <span
          className={clsx(
            "inline-block w-1.5 h-1.5 rounded-full mr-1.5 align-middle",
            cell.status === "done" && "bg-emerald-500",
            cell.status === "stopped" && "bg-rose-500",
            cell.status === "planned" && "bg-amber-500",
          )}
        />
        {cell.text}
      </p>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px]">
        {commitLabel && (
          <span
            className={clsx(
              cell.commit === "needed" && "text-rose-700 dark:text-rose-300",
              cell.commit === "committed" && "text-emerald-700 dark:text-emerald-300",
            )}
          >
            {commitLabel}
          </span>
        )}
        {cell.decision && (
          <button type="button" className="text-amber-800 dark:text-amber-200 underline underline-offset-2" onClick={() => onWhy(cell.decision!)}>
            {cell.decision}
          </button>
        )}
      </div>
    </div>
  );
}

function MemoList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <p className="text-[11px] font-semibold text-slate-500">{title}</p>
      <ul className="list-disc pl-5 text-sm">
        {items.map((x) => (
          <li key={x}>{x}</li>
        ))}
      </ul>
    </div>
  );
}
