/** 반올림 때문에 유의확률·작은 계수가 0으로 오인되지 않도록 표시한다. */
export function formatProbability(value?: number | null): string {
  if (value == null || !Number.isFinite(value) || value < 0 || value > 1) return "—";
  return value < 0.001 ? "<0.001" : value.toFixed(3);
}

export function formatStatistic(value?: number | null, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return "—";
  if (value !== 0 && Math.abs(value) < 0.5 * 10 ** -digits) return value.toExponential(2);
  return value.toLocaleString("ko-KR", { maximumFractionDigits: digits });
}
