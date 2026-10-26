export function uniformProb(start, end) {
  return (end - start) / 10;
}

export function mass(probabilities, k) {
  return probabilities[k];
}

export function cdf(probabilities, k) {
  return probabilities.slice(0, k + 1).reduce((sum, value) => sum + value, 0);
}

export function tail(probabilities, k) {
  return probabilities.slice(k).reduce((sum, value) => sum + value, 0);
}

if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('pd-data').textContent);
  const probabilities = data.probabilities;
  let k = 2;
  let mode = 'exact';
  let start = 2;
  let end = 6;
  let sigma = 1;

  function num(value) {
    return (Math.round(value * 1000) / 1000).toLocaleString('ko-KR', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
  }
  function hours(index) {
    const tenths = index / 2;
    return Number.isInteger(tenths) ? String(tenths / 10) : (index / 20).toFixed(2);
  }

  function renderDiscrete() {
    const exact = mass(probabilities, k);
    const below = cdf(probabilities, k);
    const above = tail(probabilities, k);
    const ways = [1, 3, 3, 1][k];
    const one = exact / ways;
    document.querySelectorAll('#pmf [data-k]').forEach((node) => {
      const index = Number(node.dataset.k);
      const on = mode === 'exact' ? index === k : mode === 'below' ? index <= k : index >= k;
      node.setAttribute('stroke', on ? '#d97706' : '#1e3a8a');
      node.setAttribute('stroke-width', on ? '3' : '0');
    });
    document.querySelectorAll('#cdf [data-cdf]').forEach((node) => {
      const on = Number(node.dataset.k) === k;
      node.setAttribute('stroke', on ? '#d97706' : '#1e3a8a');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('[data-k-choice]').forEach((button) => {
      button.setAttribute('aria-pressed', Number(button.dataset.kChoice) === k ? 'true' : 'false');
    });
    document.querySelectorAll('[data-mode]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.mode === mode ? 'true' : 'false');
    });
    const names = { exact: '정확히', below: '이하', above: '이상' };
    const text = `선택 ${k}번, 기준은 ${names[mode]}입니다. 정확히 ${k}번: ${num(exact)} (순서 ${ways}가지, 한 순서 ${num(one)}). ${k} 이하 F(${k})=${num(below)}. ${k} 이상: ${num(above)}. 정확히 ${k}번과 ${k} 이하는 다른 사건입니다.`;
    document.getElementById('pd-pmf-status').textContent = text;
    document.getElementById('pd-cdf-status').textContent = text;
  }

  function renderUniform() {
    const rect = document.getElementById('pd-density-area');
    rect.setAttribute('x', 70 + start * 50);
    rect.setAttribute('width', (end - start) * 50);
    const probability = uniformProb(start, end);
    rect.setAttribute('data-area', String(probability));
    document.getElementById('pd-density-label').textContent = probability === 0
      ? '폭 0, 면적 0'
      : `면적 ${hours(end - start)}×2=${num(probability).replace(/0+$/, '').replace(/\.$/, '')}`;
    document.querySelectorAll('[data-span]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.span === `${start}-${end}` ? 'true' : 'false');
    });
    document.getElementById('pd-uniform-start').value = String(start);
    document.getElementById('pd-uniform-end').value = String(end);
    document.getElementById('pd-uniform-start-label').textContent = `${hours(start)}시간`;
    document.getElementById('pd-uniform-end-label').textContent = `${hours(end)}시간`;
    const widthHours = (end - start) / 20;
    document.getElementById('pd-uniform-status').textContent = probability === 0
      ? `${hours(start)}시간은 폭이 없는 한 점입니다. 연속 밀도에서 이 점의 확률은 0입니다. 0%의 관측 비율과 같은 말이 아닙니다.`
      : `${hours(start)}~${hours(end)}시간(${start * 3}~${end * 3}분). 폭 ${widthHours}시간, 밀도 2/시간, 면적 ${probability}. 분으로 보면 밀도는 1/30이고 확률은 같습니다. 끝점 포함은 이 면적을 바꾸지 않습니다.`;
  }

  function renderNormal() {
    const polygon = document.getElementById('pd-normal-shade');
    const points = [`${320 - sigma * 65},245`];
    const steps = sigma * 100;
    for (let i = 0; i <= steps; i += 1) {
      const z = -sigma + (2 * sigma * i) / steps;
      const y = 245 - (Math.exp(-z * z / 2) / Math.sqrt(2 * Math.PI)) * 430;
      points.push(`${(320 + z * 65).toFixed(4)},${y.toFixed(4)}`);
    }
    points.push(`${320 + sigma * 65},245`);
    polygon.setAttribute('points', points.join(' '));
    const percent = data.bands[String(sigma)];
    document.getElementById('pd-normal-label').textContent = `약 ${percent}`;
    document.querySelectorAll('[data-sigma]').forEach((button) => {
      button.setAttribute('aria-pressed', Number(button.dataset.sigma) === sigma ? 'true' : 'false');
    });
    document.getElementById('pd-normal-status').textContent =
      `표준정규분포에서 −${sigma}~${sigma}의 포함확률은 약 ${percent}입니다. 이 비율은 정규분포일 때의 성질입니다. 곡선은 −4~4만 그렸고 꼬리는 양쪽으로 이어집니다.`;
    document.getElementById('normal-curve-caption').textContent =
      `그림 4. 색 면적은 −${sigma}≤Z≤${sigma}이며 포함확률은 약 ${percent}입니다. 정규분포가 아닌 자료를 표준화해도 이 비율이 되지는 않습니다.`;
  }

  document.querySelectorAll('[data-k-choice]').forEach((button) => {
    button.addEventListener('click', () => { k = Number(button.dataset.kChoice); renderDiscrete(); });
  });
  document.querySelectorAll('[data-mode]').forEach((button) => {
    button.addEventListener('click', () => { mode = button.dataset.mode; renderDiscrete(); });
  });
  document.querySelectorAll('[data-span]').forEach((button) => {
    button.addEventListener('click', () => {
      [start, end] = button.dataset.span.split('-').map(Number);
      renderUniform();
    });
  });
  document.getElementById('pd-uniform-start').addEventListener('input', (event) => {
    start = Number(event.target.value);
    if (start > end) end = start;
    renderUniform();
  });
  document.getElementById('pd-uniform-end').addEventListener('input', (event) => {
    end = Number(event.target.value);
    if (end < start) start = end;
    renderUniform();
  });
  document.querySelectorAll('[data-sigma]').forEach((button) => {
    button.addEventListener('click', () => { sigma = Number(button.dataset.sigma); renderNormal(); });
  });
  document.querySelectorAll('.pd-controls').forEach((node) => node.removeAttribute('hidden'));
  renderDiscrete();
  renderUniform();
  renderNormal();
}
