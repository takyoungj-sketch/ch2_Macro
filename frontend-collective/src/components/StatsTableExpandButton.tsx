export default function StatsTableExpandButton({
  expanded,
  onToggle,
  title,
}: {
  expanded: boolean;
  onToggle: () => void;
  title: string;
}) {
  return (
    <button
      type="button"
      className="shrink-0 text-xs font-medium text-slate-700 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white underline"
      aria-pressed={expanded}
      title={title}
      onClick={onToggle}
    >
      {expanded ? "테이블 줄이기" : "테이블 키우기"}
    </button>
  );
}
