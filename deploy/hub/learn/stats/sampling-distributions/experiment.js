export function meanSe(sampleSize) {
  return 0.4 / Math.sqrt(sampleSize);
}

export function bandProbability(probabilities, sampleSize) {
  return probabilities.reduce((sum, probability, count) => (
    15 * sampleSize <= 100 * count && 100 * count <= 25 * sampleSize ? sum + probability : sum
  ), 0);
}

const ROW_SIZES = [1, 5, 30, 100];
const ERROR_SIZES = [1, 4, 16, 64];
let sampleSize = 5;
let errorSize = 4;
let repetitions = 1000;

function trim(value) {
  return value.toFixed(6).replace(/0+$/, '').replace(/\.$/, '');
}

function press(selector, attr, value) {
  document.querySelectorAll(selector).forEach((button) => {
    button.setAttribute('aria-pressed', button.dataset[attr] === String(value) ? 'true' : 'false');
  });
}

function renderRepeated() {
  const se = meanSe(5);
  document.getElementById('cl-repeat-status').textContent =
    `한 표본의 관측수는 5개입니다. 반복 횟수 B는 ${repetitions.toLocaleString('ko-KR')}입니다. 그때 생기는 표본평균도 ${repetitions.toLocaleString('ko-KR')}개입니다. 이론적 표준오차는 0.4/√5 ≈ ${trim(se)}로, B를 바꿔도 그대로입니다. 그림의 세 줄은 구조를 보여주는 개념도입니다.`;
  press('[data-b]', 'b', repetitions);
}

function renderRows() {
  document.querySelectorAll('#cl-fig2 line[data-n]').forEach((line) => {
    const selected = line.dataset.n === String(sampleSize);
    line.setAttribute('stroke', selected ? '#d97706' : '#64748b');
    line.setAttribute('stroke-width', selected ? '4' : '2');
  });
  const lines = [...document.querySelectorAll(`#cl-fig2 line[data-n="${sampleSize}"]`)];
  const probabilities = lines
    .sort((a, b) => Number(a.dataset.k) - Number(b.dataset.k))
    .map((line) => Number(line.dataset.probability));
  const included = probabilities.reduce((sum, probability, count) => (
    15 * sampleSize <= 100 * count && 100 * count <= 25 * sampleSize ? sum + probability : sum
  ), 0);
  const counts = probabilities.flatMap((probability, count) => (
    15 * sampleSize <= 100 * count && 100 * count <= 25 * sampleSize ? [count] : []
  ));
  const se = meanSe(sampleSize);
  document.getElementById('cl-pmf-status').textContent =
    `선택한 표본수는 n=${sampleSize}입니다. 가능한 평균은 ${sampleSize + 1}개이고 간격은 ${trim(1 / sampleSize)}입니다. 기대값은 0.2, 분산은 ${trim(0.16 / sampleSize)}, 표준오차는 ${trim(se)}입니다. 개별 관측의 표준편차는 0.4입니다. 막대 높이는 확률 P(K=k)입니다.`;
  const countText = counts.length ? `해당하는 횟수는 K=${counts.join(', ')}입니다.` : '이 구간에 들어가는 정수 횟수는 없습니다.';
  document.getElementById('cl-band-note').textContent =
    `0.15 이상 0.25 이하인 표본평균의 정확한 확률은 ${included.toFixed(4)}입니다. ${countText} 독서 동아리 모형의 확률이며, 거래가격의 예측확률은 아닙니다.`;
  press('#cl-fig2-controls [data-n-choice]', 'nChoice', sampleSize);
  renderNormal();
}

function renderError() {
  document.querySelectorAll('#cl-fig3 rect[data-n]').forEach((bar) => {
    const selected = bar.dataset.n === String(errorSize);
    bar.setAttribute('stroke', selected ? '#d97706' : 'none');
    bar.setAttribute('stroke-width', selected ? '3' : '0');
  });
  const se = meanSe(errorSize);
  document.getElementById('cl-se-status').textContent =
    `이 그림에서 고른 표본수는 n=${errorSize}입니다. 그림 2의 1·5·30·100과는 다른 비교이며, 네 배씩 늘릴 때 표준오차가 절반이 되는 경우를 보여 줍니다. 개별 표준편차는 0.4입니다. 평균의 분산은 ${trim(0.16 / errorSize)}, 표준오차는 ${trim(se)}입니다. n=1의 표준오차 0.4와 비교하면 ${trim(se / 0.4)}배입니다.`;
  press('[data-se-choice]', 'seChoice', errorSize);
}

function renderNormal() {
  const shown = sampleSize === 5 || sampleSize === 100;
  document.querySelectorAll('#cl-fig4 line[data-n]').forEach((line) => {
    const selected = shown && line.dataset.n === String(sampleSize);
    line.setAttribute('stroke', selected ? '#d97706' : '#64748b');
    line.setAttribute('opacity', shown && !selected ? '0.35' : '1');
  });
  const status = document.getElementById('cl-z-status');
  if (!shown) {
    status.textContent = `그림 4에 그려진 표본수는 n=5와 n=100입니다. 지금 그림 2에서 고른 n=${sampleSize}의 곡선은 이 그림에 없습니다. 가로축은 z이고, 막대 높이는 확률을 z 간격으로 나눈 밀도 환산값입니다.`;
  } else {
    const step = 1 / Math.sqrt(0.16 * sampleSize);
    status.textContent = `지금 강조한 분포는 n=${sampleSize}입니다. 가로축은 z=(평균−0.2)/(0.4/√n)입니다. 인접한 z의 간격 Δz는 ${trim(step)}이고, 막대 높이는 P(K=k)/Δz입니다. 높이 자체가 그 점의 확률은 아닙니다. 주황 곡선은 표준정규 밀도이며, 그림은 −4~4만 그렸습니다. 꼬리는 그 밖으로 이어집니다. 개별 X는 0 또는 1입니다.`;
  }
  press('#cl-fig4-controls [data-n-choice]', 'nChoice', shown ? sampleSize : '');
}

function bind(root) {
  root.querySelectorAll('.cl-controls').forEach((panel) => { panel.hidden = false; });
  root.addEventListener('click', (event) => {
    const button = event.target.closest('button');
    if (!button || !root.contains(button)) return;
    if (button.dataset.b) repetitions = Number(button.dataset.b);
    if (button.dataset.nChoice) sampleSize = Number(button.dataset.nChoice);
    if (button.dataset.seChoice) errorSize = Number(button.dataset.seChoice);
    renderRepeated();
    renderRows();
    renderError();
  });
  renderRepeated();
  renderRows();
  renderError();
}

if (typeof document !== 'undefined') bind(document);
