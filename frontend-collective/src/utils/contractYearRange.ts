export type YearField = number | "";

export function isYearRangeValid(from: YearField, to: YearField): boolean {
  if (from === "" || to === "") return true;
  return from <= to;
}

/** from 변경 시 to가 더 이르면 to를 from에 맞춘다. */
export function applyYearFrom(from: YearField, to: YearField): YearField {
  if (from === "" || to === "") return to;
  return from > to ? from : to;
}

/** to 변경 시 from이 더 늦으면 from을 to에 맞춘다. */
export function applyYearTo(from: YearField, to: YearField): YearField {
  if (from === "" || to === "") return from;
  return to < from ? to : from;
}

export function filterFromYearOptions(years: number[], to: YearField): number[] {
  if (to === "") return years;
  return years.filter((y) => y <= to);
}

export function filterToYearOptions(years: number[], from: YearField): number[] {
  if (from === "") return years;
  return years.filter((y) => y >= from);
}

export function clampYearsToAvailable(
  from: YearField,
  to: YearField,
  years: number[],
): { from: YearField; to: YearField } {
  const set = new Set(years);
  let nextFrom = from;
  let nextTo = to;
  if (nextFrom !== "" && !set.has(nextFrom)) nextFrom = "";
  if (nextTo !== "" && !set.has(nextTo)) nextTo = "";
  if (nextFrom !== "" && nextTo !== "" && nextFrom > nextTo) nextTo = nextFrom;
  return { from: nextFrom, to: nextTo };
}

export function hasYearFilter(from: YearField, to: YearField): boolean {
  return from !== "" || to !== "";
}
