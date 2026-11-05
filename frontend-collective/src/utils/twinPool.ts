/** 고른 지역과 체크한 쌍둥이를 중복 없이 붙인다. 순위만의 상위 읍·면은 식에 넣지 않는다. */
export function twinPoolRegionAddrs(selected: string[], anchor: string, twins: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  const push = (raw: string) => {
    const key = raw.trim();
    if (!key || seen.has(key)) return;
    seen.add(key);
    out.push(key);
  };
  const selectedKeys = selected.map((key) => key.trim()).filter(Boolean);
  const anchorKey = anchor.trim();
  if (selectedKeys.length === 0 || selectedKeys.includes(anchorKey)) push(anchorKey);
  for (const key of selectedKeys) push(key);
  for (const key of twins) push(key);
  return out;
}

/** 체크한 쌍둥이가 이미 고른 지역 밖에 하나라도 있으면 식이 넓어진다. */
export function checkedTwinsAddRegion(selected: string[], anchor: string, twins: string[]): boolean {
  const pool = twinPoolRegionAddrs(selected, anchor, twins);
  const base = selected.map((key) => key.trim()).filter(Boolean);
  const baseline = base.length > 0 ? base : [anchor.trim()].filter(Boolean);
  const have = new Set(baseline);
  return pool.some((key) => !have.has(key));
}
