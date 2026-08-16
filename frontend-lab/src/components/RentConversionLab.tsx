import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ConversionComparePanel from "../../../frontend-rent/src/components/ConversionComparePanel";
import { fetchRentMeta } from "../../../frontend-rent/src/api/client";
import type { RentAssetType } from "../../../frontend-rent/src/types";

const KINDS: RentAssetType[] = ["apartment", "rowhouse", "officetel"];

export default function RentConversionLab({ onBack }: { onBack: () => void }) {
  const [addr1, setAddr1] = useState("서울특별시");
  const metaQ = useQuery({
    queryKey: ["rent-meta-lab"],
    queryFn: () => fetchRentMeta(5),
  });
  const sidos = metaQ.data?.addr1 ?? ["서울특별시"];

  return (
    <div className="space-y-3 pb-8">
      <div className="max-w-6xl mx-auto px-4 pt-3 flex flex-wrap items-center gap-3">
        <label className="text-sm flex items-center gap-2">
          <span className="text-slate-500">시도</span>
          <select
            className="rounded border border-slate-300 px-2 py-1 dark:border-slate-600 dark:bg-slate-800"
            value={addr1}
            onChange={(e) => setAddr1(e.target.value)}
          >
            {sidos.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <p className="text-xs text-slate-500">
          연구 종료 · 적용은 단순평균(mean_simple). 검증 탭은 서울 1회 리포트. 근거는 상단 D-040.
        </p>
      </div>
      <ConversionComparePanel
        addr1={addr1}
        assetKinds={KINDS}
        layout="page"
        onClose={onBack}
      />
    </div>
  );
}
