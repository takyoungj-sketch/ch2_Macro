/** 모바일은 지역 하나. 지도 복수는 PC에서만. */
let single = false;

export function setLandPickSingle(next: boolean) {
  single = next;
}

export function landPickIsSingle(): boolean {
  return single;
}
