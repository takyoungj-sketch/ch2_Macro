import scopeJson from "../../../docs/lab/twin_eup_scope_region_vs_national.json";

type RegionRow = {
  n: number;
  median_region_score: number | null;
  median_national_score: number | null;
  median_lift: number | null;
  share_lift_ge_0_05: number | null;
  share_lift_ge_0_10: number | null;
  share_national_outside: number | null;
};

type LiftExample = {
  anchor_name: string;
  sigungu_name: string;
  sido_name: string;
  region: string;
  lift: number;
  region_top: { name: string; sigungu_name: string; sido_name: string; score: number };
  national_top: { name: string; sigungu_name: string; sido_name: string; score: number };
};

const snap = scopeJson as {
  as_of_month: string;
  window_years: number;
  n_profiles: number;
  stored_region_top_match: { checked: number; matched: number; code_match: number };
  summary: {
    n_with_both_tops: number;
    median_region_score: number;
    median_national_score: number;
    median_lift: number;
    share_lift_ge_0_05: number;
    share_lift_ge_0_10: number;
    share_national_outside: number;
    by_region: Record<string, RegionRow>;
    largest_lifts: LiftExample[];
  };
};

const REGION_ORDER = ["수도권", "충청권", "호남권", "대경권", "동남권", "강원권", "제주권"];

function pct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function points(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return (v * 100).toFixed(1);
}

function share(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${Math.round(v * 100)}%`;
}

function place(ex: { sido_name: string; sigungu_name: string; name: string }): string {
  return `${ex.sido_name} ${ex.sigungu_name} ${ex.name}`;
}

export default function TwinScopeExperimentLab() {
  const s = snap.summary;
  const regions = [
    ...REGION_ORDER.filter((name) => s.by_region[name]),
    ...Object.keys(s.by_region).filter((name) => !REGION_ORDER.includes(name)),
  ];
  const examples = s.largest_lifts.slice(0, 3);

  return (
    <div className="max-w-6xl mx-auto px-4 py-4 space-y-4">
      <div className="card p-4 space-y-2">
        <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">
          읍면동 후보를 전국으로 넓혀도, 전형적인 1위는 거의 그대로입니다.
        </p>
        <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
          제품 카드의 알고리즘 21 점수를 유지하고, 읍면동 후보 범위만 권역과 전국으로 나눠 1위를
          비교했습니다. 카드와 마트는 바꾸지 않았습니다. 프로필 v2.1-national, 기준월 {snap.as_of_month}, 창{" "}
          {snap.window_years}년, 일반 프로필, {snap.n_profiles.toLocaleString("ko-KR")}곳입니다.
        </p>
        <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
          같은 지역에서 뺀 점수 차의 중앙값은 {points(s.median_lift)}점입니다. 5점 이상 오른 곳은{" "}
          {share(s.share_lift_ge_0_05)}, 10점 이상은 {share(s.share_lift_ge_0_10)}입니다. 권역 1위 점수의
          중앙값은 {pct(s.median_region_score)}, 전국 1위 점수의 중앙값은 {pct(s.median_national_score)}입니다.
          카드는 읍면동을 권역 안에서 계속 찾습니다.
        </p>
      </div>

      <div className="card p-4 overflow-x-auto">
        <table className="data w-full text-[13px] whitespace-nowrap">
          <thead>
            <tr>
              <th className="text-left">권역</th>
              <th>곳</th>
              <th>권역 1위 중앙</th>
              <th>전국 1위 중앙</th>
              <th>차이 중앙</th>
              <th>5점 이상</th>
              <th>10점 이상</th>
              <th>1위가 권역 밖</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="text-left font-medium">전체</td>
              <td>{s.n_with_both_tops.toLocaleString("ko-KR")}</td>
              <td>{pct(s.median_region_score)}</td>
              <td>{pct(s.median_national_score)}</td>
              <td>{points(s.median_lift)}</td>
              <td>{share(s.share_lift_ge_0_05)}</td>
              <td>{share(s.share_lift_ge_0_10)}</td>
              <td>{share(s.share_national_outside)}</td>
            </tr>
            {regions.map((name) => {
              const row = s.by_region[name];
              return (
                <tr key={name}>
                  <td className="text-left">{name}</td>
                  <td>{row.n.toLocaleString("ko-KR")}</td>
                  <td>{pct(row.median_region_score)}</td>
                  <td>{pct(row.median_national_score)}</td>
                  <td>{points(row.median_lift)}</td>
                  <td>{share(row.share_lift_ge_0_05)}</td>
                  <td>{share(row.share_lift_ge_0_10)}</td>
                  <td>{share(row.share_national_outside)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="mt-3 text-xs text-slate-500 leading-relaxed">
          점수는 카드와 같이 0–100으로 적었습니다. 차이 중앙은 같은 읍면동에서 전국 1위 점수에서 권역 1위
          점수를 뺀 값의 중앙입니다. 1위가 권역 밖인 비율은 전국 1위의 시도가 다른 권역인 경우이고, 점수가
          의미 있게 오른 비율과 같지 않습니다.
        </p>
      </div>

      <div className="card p-4 space-y-2">
        <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">차이가 가장 큰 세 곳</p>
        <p className="text-xs text-slate-500 leading-relaxed">
          권역 1위가 이미 아주 낮던 꼬리입니다. 전체의 중앙을 대표하지 않습니다.
        </p>
        <ul className="text-sm text-slate-700 dark:text-slate-200 space-y-1.5">
          {examples.map((ex) => (
            <li key={ex.anchor_name + ex.sigungu_name}>
              {ex.sido_name} {ex.sigungu_name} {ex.anchor_name}: 권역 {place(ex.region_top)}{" "}
              {pct(ex.region_top.score)} → 전국 {place(ex.national_top)} {pct(ex.national_top.score)} (차이{" "}
              {points(ex.lift)}점)
            </li>
          ))}
        </ul>
      </div>

      <p className="text-xs text-slate-500 leading-relaxed">
        다시 계산한 권역 1위 코드는 저장된 카드와 {snap.stored_region_top_match.code_match.toLocaleString("ko-KR")}
        /{snap.stored_region_top_match.checked.toLocaleString("ko-KR")}곳이 같습니다. 점수까지 같은 곳은{" "}
        {snap.stored_region_top_match.matched.toLocaleString("ko-KR")}곳입니다. 아파트 자료가 없는 쌍은 지금
        식이 그 가중치를 빼서 점수가 더 높습니다. 위 표는 그 식으로 권역과 전국을 동시에 계산한 차이입니다.
        가격 식에 붙이는 지역은 이 실험에서 바꾸지 않았습니다.
      </p>
    </div>
  );
}
