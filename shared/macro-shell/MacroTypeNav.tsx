// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
export type MacroAppKind = "land" | "built" | "collective";

const NAV_ITEMS: { kind: MacroAppKind; href: string; label: string }[] = [
  { kind: "land", href: "/land/", label: "토지" },
  { kind: "built", href: "/built/", label: "복합" },
  { kind: "collective", href: "/collective/", label: "집합" },
];

type Props = {
  current: MacroAppKind;
};

export default function MacroTypeNav({ current }: Props) {
  return (
    <nav
      className="flex items-center gap-0.5 border border-slate-200 dark:border-slate-600 rounded-md p-0.5 bg-slate-50/90 dark:bg-slate-700/90"
      aria-label="유형 이동"
    >
      {NAV_ITEMS.map(({ kind, href, label }) =>
        kind === current ? (
          <span
            key={kind}
            className="px-2.5 py-1 text-[11px] font-semibold rounded bg-white dark:bg-slate-600 text-slate-800 dark:text-slate-100 shadow-sm"
            aria-current="page"
          >
            {label}
          </span>
        ) : (
          <a
            key={kind}
            href={href}
            className="px-2.5 py-1 text-[11px] font-medium rounded text-slate-600 dark:text-slate-300 hover:bg-white dark:hover:bg-slate-600 transition-colors"
          >
            {label}
          </a>
        ),
      )}
    </nav>
  );
}
