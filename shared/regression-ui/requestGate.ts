/** 입력 변경·닫기·재실행 이전에 시작한 응답이 최신 결과를 덮지 않게 한다. */
export function createRequestGate() {
  let revision = 0;
  return {
    start: () => ++revision,
    invalidate: () => { revision++; },
    isCurrent: (ticket: number) => ticket === revision,
  };
}
