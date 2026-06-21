import type { RegionalProfileMeta } from "../../types";

const STATUS_LABEL: Record<string, string> = {
  PENDING: "검증 대기",
  PASS: "검증 통과",
  FAIL: "검증 실패",
};

export default function ProfileMetaBar({
  meta,
  regionLabel,
}: {
  meta: RegionalProfileMeta;
  regionLabel?: string | null;
}) {
  return (
    <dl className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-x-4 gap-y-2 text-xs border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2.5 bg-slate-50/80 dark:bg-slate-900/40">
      <div className="col-span-2 sm:col-span-3 lg:col-span-2">
        <dt className="text-slate-500">조회 지역</dt>
        <dd className="font-semibold text-sm text-slate-900 dark:text-slate-50 leading-snug">
          {regionLabel ?? `${meta.region_level}/${meta.region_code}`}
        </dd>
        {regionLabel ? (
          <dd className="font-mono text-[10px] text-slate-400 mt-0.5">
            {meta.region_level}/{meta.region_code}
          </dd>
        ) : null}
      </div>
      <div>
        <dt className="text-slate-500">버전</dt>
        <dd className="font-medium text-slate-800 dark:text-slate-100">{meta.profile_version}</dd>
      </div>
      <div>
        <dt className="text-slate-500">창</dt>
        <dd className="font-medium">{meta.window_years}년</dd>
      </div>
      <div>
        <dt className="text-slate-500">기준월</dt>
        <dd className="font-medium">{meta.as_of_month}</dd>
      </div>
      <div>
        <dt className="text-slate-500">검증</dt>
        <dd
          className={
            meta.validation_status === "PASS"
              ? "font-medium text-emerald-700 dark:text-emerald-400"
              : meta.validation_status === "FAIL"
                ? "font-medium text-red-700 dark:text-red-400"
                : "font-medium text-amber-700 dark:text-amber-400"
          }
        >
          {STATUS_LABEL[meta.validation_status] ?? meta.validation_status}
        </dd>
      </div>
      <div>
        <dt className="text-slate-500">feature</dt>
        <dd className="font-medium">{meta.feature_count ?? "—"}</dd>
      </div>
    </dl>
  );
}
