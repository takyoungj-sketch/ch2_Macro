/**
 * 지도 클릭 메뉴가 overflow-hidden 상자 밖으로 잘리지 않게 좌표를 넣는다.
 * 아래 공간이 부족하면 클릭 위로 뒤집고, 좌하단 상태 배지와 겹치지 않게 밑여백을 둔다.
 */
export function clampMapMenuPos(
  x: number,
  y: number,
  container: HTMLElement | null,
  menuW = 256,
  menuH = 118,
  pad = 8,
  bottomReserve = 40,
): { x: number; y: number } {
  if (!container) return { x, y };
  const cw = container.clientWidth;
  const ch = container.clientHeight;
  const bottomPad = pad + bottomReserve;
  let nx = x;
  let ny = y;
  if (nx + menuW + pad > cw) nx = cw - menuW - pad;
  if (nx < pad) nx = pad;
  if (ny + menuH + bottomPad > ch) ny = y - menuH;
  if (ny + menuH + bottomPad > ch) ny = ch - menuH - bottomPad;
  if (ny < pad) ny = pad;
  return { x: nx, y: ny };
}
