import { useState } from "react";
import clsx from "clsx";
import LabResume from "./LabResume";

type TrackId = "apt" | "officetel" | "shop";

const TRACKS: { id: TrackId; label: string }[] = [
  { id: "apt", label: "아파트" },
  { id: "officetel", label: "오피스텔" },
  { id: "shop", label: "집합상가" },
];

export default function FloorUtilityLab() {
  const [track, setTrack] = useState<TrackId>("shop");
  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-4 text-sm leading-relaxed">
      <p className="text-slate-600 dark:text-slate-300">
        2026-09-23 기록. 창 2021-09-01~2026-08-31. 세 질문은 숫자를 더하지 않는다. 제품 층 식은 바꾸지 않았다.
      </p>
      <div className="flex flex-wrap gap-1">
        {TRACKS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={clsx(
              "px-3 py-1.5 text-sm rounded border",
              track === item.id
                ? "border-amber-500 bg-amber-50 dark:bg-amber-950/40"
                : "border-slate-200 dark:border-slate-700",
            )}
            onClick={() => setTrack(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {track === "apt" ? <AptRecord /> : null}
      {track === "officetel" ? <OfficetelRecord /> : null}
      {track === "shop" ? <ShopRecord /> : null}
    </div>
  );
}

function AptRecord() {
  return (
    <div className="space-y-3">
      <LabResume
        resume={{
          next_id: "apt-floor-closed",
          title: "아파트 층 효용은 다시 맞추지 않는다",
          say: "공개는 Insight 8번. 최상 가운데값은 지역과 관계없이 108 안팎. 비도시 차이는 높이 세 칸에서 −2.4%, 최고층 연속에서 −0.8%로 없다와 구분되지 않는다.",
          do_not: "식을 다시 맞추기. 오피스텔 저층=100이나 집합상가 2층을 108에 더하기. 제품 층 식을 이 기록으로 바꾸기.",
          how: "docs/lab/APT_FLOOR_UTILITY_LAB.md · 화면 /insight/?q=8",
        }}
      />
      <RecordTable
        caption="1층=100. 단지 하나의 가운데값. 최상층."
        headers={["지역", "최상"]}
        rows={[
          ["수도권", "107.7"],
          ["광역시", "109.4"],
          ["기타 도시", "107.8"],
          ["비도시", "107.3"],
        ]}
      />
      <p>층 비교가 되는 단지는 6,958곳이다. 세종 최상은 9곳이라 적지 않는다.</p>
    </div>
  );
}

function OfficetelRecord() {
  return (
    <div className="space-y-3">
      <LabResume
        resume={{
          next_id: "officetel-floor-hold",
          title: "차이 찾기는 여기서 멈춘다",
          say: "1층이 5건 이상인 곳은 11곳이라 1층=100을 만들지 않았다. 저층=100으로 아파트와 나란히 보면 고층 차이는 2포인트 안이다. 공개는 Insight 8번 맨 끝.",
          do_not: "1층 문턱을 낮추기. 10포인트를 넘기려고 칸을 더 자르기. 이 100을 아파트 1층=100에 더하기. 26층 이상 최상(23곳)을 읽기.",
          how: "docs/lab/OFFICETEL_FLOOR_UTILITY_LAB.md · python -m app.officetel_floor_lab.ratio",
        }}
      />
      <RecordTable
        caption="저층=100. 차이 = 오피스텔 − 아파트. 둘 다 2포인트 안."
        headers={["최고층", "고층 차이", "최상/고층 차이"]}
        rows={[
          ["15층 이하", "−0.8", "+1.4"],
          ["16–25층", "+0.7", "+0.8"],
          ["26층 이상", "+0.8", "—"],
        ]}
      />
      <p>나중에 볼 수 있는 제품 확인은 하나다. 1층 거래가 없는 오피스텔 화면에서 빈 1층이 100으로 보이는지. 이 창에서 가격을 다시 돌리는 일은 아니다.</p>
    </div>
  );
}

function ShopRecord() {
  return (
    <div className="space-y-3">
      <LabResume
        resume={{
          next_id: "shop-floor-closed",
          title: "집합상가 2층 실험은 끝났다",
          say: "같은 도로의 1층=100. 연면적 ±20% 뒤 2층은 55.2와 68.1(89곳). 연식·용도·도로를 함께 고려하면 61.1(56.2–66.5)과 56.4(51.0–62.4). 공개는 Insight 10번.",
          do_not: "55·68을 회귀 숫자로 바꾸기. 3층 이상에 연식·용도 회귀를 열기. 10층 이상·수도권 밖 지수를 만들기. 낮은 이유를 적기. 아파트 108과 더하기.",
          how: "docs/lab/SHOP_FLOOR_UTILITY_LAB.md · python -m app.shop_floor_lab.ratio · python -m app.shop_floor_lab.fe",
        }}
      />
      <RecordTable
        caption="그 도로의 1층=100. 2층만."
        headers={["단계", "도로 하나=1", "거래가 많은 도로", "도로"]}
        rows={[
          ["같은 도로", "41.3", "43.7", "299"],
          ["연면적 ±20%", "55.2", "68.1", "89"],
          ["연식·용도·도로", "56.4", "61.1", "89"],
        ]}
      />
      <p>사분위는 같은 도로 32.2–55.7, 연면적을 맞춘 뒤 41.8–91.0이다. 모든 도로가 한 숫자였던 것은 아니다. 회귀 95% 구간은 둘 다 100보다 낮다.</p>
    </div>
  );
}

function RecordTable({
  caption,
  headers,
  rows,
}: {
  caption: string;
  headers: string[];
  rows: string[][];
}) {
  return (
    <div className="space-y-1">
      <p className="text-xs text-slate-500">{caption}</p>
      <table className="data w-full text-[13px]">
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header} className={header === headers[0] ? "text-left" : undefined}>
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.join("|")}>
              {row.map((cell, index) => (
                <td key={`${row[0]}-${index}`} className={index === 0 ? "text-left" : undefined}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
