/** 기본 통계 / 필터 분석 등 2줄 CTA (제목 + 기간 방식 부제) */
export default function AnalysisActionButton({
  primary,
  caption,
  onClick,
  disabled,
  variant = "basic",
  className = "",
}: {
  primary: string;
  caption: string;
  onClick: () => void;
  disabled?: boolean;
  variant?: "basic" | "filter" | "free";
  className?: string;
}) {
  const variantClass =
    variant === "filter"
      ? "bg-indigo-600 hover:bg-indigo-700"
      : variant === "free"
        ? "bg-slate-800 hover:bg-slate-900"
        : "bg-blue-600 hover:bg-blue-700";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`w-full py-2 rounded-lg text-white text-sm font-semibold disabled:opacity-40 transition-colors ${variantClass} ${className}`}
    >
      <span className="block leading-tight">{primary}</span>
      <span className="block text-[11px] font-normal opacity-90 mt-0.5 leading-tight">{caption}</span>
    </button>
  );
}
