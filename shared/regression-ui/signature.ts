/** 객체의 생성 순서와 무관한 내용 식별. 배열 순서는 요청 의미대로 보존한다. */
export function contentSignature(value: unknown): string {
  function canonical(v: unknown): unknown {
    if (Array.isArray(v)) return v.map(canonical);
    if (v && typeof v === "object") return Object.fromEntries(
      Object.entries(v).filter(([, item]) => item !== undefined)
        .sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonical(item)]),
    );
    return v;
  }
  return JSON.stringify(canonical(value));
}
