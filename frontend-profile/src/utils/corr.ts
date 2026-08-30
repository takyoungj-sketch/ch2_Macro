/** Pearson r. n<3 또는 분산 0이면 null. */
export function pearson(xs: number[], ys: number[]): number | null {
  const n = xs.length;
  if (n < 3 || n !== ys.length) return null;
  let sx = 0;
  let sy = 0;
  for (let i = 0; i < n; i++) {
    sx += xs[i];
    sy += ys[i];
  }
  const mx = sx / n;
  const my = sy / n;
  let num = 0;
  let dx = 0;
  let dy = 0;
  for (let i = 0; i < n; i++) {
    const vx = xs[i] - mx;
    const vy = ys[i] - my;
    num += vx * vy;
    dx += vx * vx;
    dy += vy * vy;
  }
  if (dx <= 0 || dy <= 0) return null;
  return num / Math.sqrt(dx * dy);
}

export function formatCorr(r: number | null | undefined, n: number, minN = 10): string {
  if (n < minN || r == null || Number.isNaN(r)) return "—";
  const sign = r > 0 ? "+" : "";
  return `${sign}${r.toFixed(2)}`;
}
