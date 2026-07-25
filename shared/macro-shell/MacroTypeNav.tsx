// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
export type MacroAppKind = "land" | "built" | "collective";

const NAV_ITEMS: { kind: MacroAppKind; href: string; label: string }[] = [
  { kind: "land", href: "/land/", label: "토지" },
  { kind: "built", href: "/built/", label: "복합" },
  { kind: "collective", href: "/collective/", label: "집합" },
];

type Props = {
  current?: MacroAppKind | null;
};

export default function MacroTypeNav({ current = null }: Props) {
  return (
    <nav className="macro-type-nav" aria-label="유형 이동">
      {NAV_ITEMS.map(({ kind, href, label }) =>
        kind === current ? (
          <span key={kind} className="macro-type-nav-item is-active" aria-current="page">
            {label}
          </span>
        ) : (
          <a key={kind} href={href} className="macro-type-nav-item">
            {label}
          </a>
        ),
      )}
    </nav>
  );
}
