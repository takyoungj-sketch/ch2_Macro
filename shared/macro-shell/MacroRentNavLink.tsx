// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
type Props = {
  active?: boolean;
  href?: string;
};

/** 토지·복합·집합 pill 그룹과 분리된 임대시장 이동 버튼 */
export default function MacroRentNavLink({ active = false, href = "/rent/" }: Props) {
  const className = `macro-rent-nav${active ? " is-active" : ""}`;

  if (active) {
    return (
      <span className={className} aria-current="page">
        임대
      </span>
    );
  }

  return (
    <a href={href} className={className}>
      임대
    </a>
  );
}
