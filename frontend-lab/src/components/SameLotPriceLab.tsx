const rows = [
  ["기존 104곳", "가격비율 중앙값 62.0%", "기준 결과로 유지"],
  ["면적 ±10%, 계약일 92일", "62곳, 중앙값 61.4%", "방향은 그대로. 62.0%를 바꾸지 않음"],
  ["지번", "104곳 모두 열림", "동일 지번은 확인"],
  ["사용승인연도", "104곳 모두 1년 이내의 한 덩어리", "물리적 한 동은 확정하지 않음"],
  ["회귀 95% 구간", "88곳 중 84곳이 통째로 0 아래", "이 88곳에 한정"],
];

export default function SameLotPriceLab() {
  return (
    <div className="space-y-6 text-sm leading-relaxed text-slate-700 dark:text-slate-200">
      <p>
        2021년 11월부터 2026년 10월까지, 같은 지번에서 면적·층 구간·계약연도를 맞춘 104곳의
        오피스텔/아파트 ㎡당 가격비율 중앙값은 62.0%입니다. 104곳 가운데 102곳에서 오피스텔이 더 낮습니다.
        공개 글은 Macro Insight 13번입니다.
      </p>
      <p>
        <a href="/insight/?q=13" className="text-indigo-700 dark:text-indigo-300 font-medium hover:underline">
          공개 글 보기
        </a>
      </p>
      <table className="data w-full text-[13px]">
        <caption className="sr-only">추가 검증</caption>
        <thead>
          <tr>
            <th className="text-left">항목</th>
            <th className="text-left">결과</th>
            <th className="text-left">읽는 법</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row[0]}>
              {row.map((cell) => (
                <td key={cell}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        표제부에 아파트와 오피스텔 문구가 모두 있는 71곳의 중앙값은 57.2%입니다. 문구가 그렇게 갖춰지지
        않은 33곳(아파트만 5, 오피스텔만 10, 둘 다 없음 18)의 중앙값은 82.3%입니다. 둘 다 100% 아래라
        62.0%는 유지합니다. 33곳을 업무용으로만 부르지 않습니다. 104곳 전체를 동일 건물이라고 부르지 않습니다.
      </p>
      <p>
        서울 24곳 80.1%, 광역시 45곳 56.8%, 도 지역 시 34곳 59.9%. 군은 1곳이라 중앙값을 읽지 않습니다.
        같은 지역 안에서 신축과 구축을 나란히 읽을 칸은 없어, 지역 차이와 연식 차이는 추가 가설로 둡니다.
        제품 회귀식과 층 효용지수는 바꾸지 않았습니다.
      </p>
    </div>
  );
}
