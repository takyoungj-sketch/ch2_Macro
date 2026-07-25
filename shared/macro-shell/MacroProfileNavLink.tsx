// @ts-nocheck — shared 패키지: 각 frontend node_modules 기준으로 tsc 경로가 달라짐
type Props = {
  active?: boolean;
  href?: string;
};

/** 토지·복합·집합 pill 그룹과 분리된 지역프로필 이동 버튼 */
export default function MacroProfileNavLink({ active = false, href = "/profile/" }: Props) {
  const className = `macro-profile-nav${active ? " is-active" : ""}`;

  if (active) {
    return (
      <span className={className} aria-current="page">
        지역프로필
      </span>
    );
  }

  return (
    <a href={href} className={className}>
      지역프로필
    </a>
  );
}
