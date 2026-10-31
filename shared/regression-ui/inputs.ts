/** 수치는 보존하고 새 모형에 없는 범주만 새 기준값으로 돌린다. */
export function reconcileListedInputs<T extends object>(defaults: T, current: T,
  categories: Partial<Record<keyof T, readonly unknown[]>>): T {
  const next = { ...defaults, ...current };
  for (const key of Object.keys(categories) as (keyof T)[]) {
    const allowed = categories[key];
    if (allowed && !allowed.includes(current[key])) next[key] = defaults[key];
  }
  return next;
}
