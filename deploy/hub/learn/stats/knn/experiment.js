// Chapter 29 illustrations only. Neighbor search uses X. Y is aggregated after selection.
export function neighborOrder(xs, x0) {
  return xs.map((x, i) => ({ i, d: Math.abs(x - x0) })).sort((a, b) => a.d - b.d || a.i - b.i);
}

function aggregate(chosen, ys, weight) {
  const zeros = chosen.filter((n) => n.d === 0);
  const rows = zeros.length ? zeros : chosen;
  if (weight === 'distance' && zeros.length === 0) {
    const weights = rows.map((n) => 1 / n.d);
    const sum = weights.reduce((s, w) => s + w, 0);
    return rows.reduce((s, n, i) => s + weights[i] * ys[n.i], 0) / sum;
  }
  return rows.reduce((s, n) => s + ys[n.i], 0) / rows.length;
}

export function uniformPredict(xs, ys, x0, k) {
  return aggregate(neighborOrder(xs, x0).slice(0, k), ys, 'uniform');
}

export function weightedPredict(xs, ys, x0, k) {
  return aggregate(neighborOrder(xs, x0).slice(0, k), ys, 'distance');
}

if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('knn-data').textContent);
  const state = { k: 3, weight: 'uniform' };
  const fmt = (v) => (Math.round((v + Number.EPSILON) * 10000) / 10000).toFixed(4).replace(/0+$/, '').replace(/\.$/, '');

  function render() {
    const order = neighborOrder(data.x, data.query);
    const chosen = order.slice(0, state.k);
    const pred = state.weight === 'distance'
      ? weightedPredict(data.x, data.y, data.query, state.k)
      : uniformPredict(data.x, data.y, data.query, state.k);
    document.querySelectorAll('button[data-k]').forEach((button) => {
      button.setAttribute('aria-pressed', String(Number(button.dataset.k) === state.k));
    });
    document.querySelectorAll('button[data-weight]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.weight === state.weight));
    });
    document.querySelectorAll('[aria-labelledby="neighbors-title neighbors-desc"] circle[data-index]').forEach((mark) => {
      const on = chosen.some((n) => n.i === Number(mark.dataset.index));
      mark.setAttribute('fill', on ? '#2563eb' : '#94a3b8');
      mark.setAttribute('r', on ? '7' : '5');
    });
    document.querySelectorAll('[aria-labelledby="complexity-title complexity-desc"] polyline[data-k]').forEach((line) => {
      const on = line.dataset.k === `k${state.k}`;
      line.setAttribute('stroke-width', on ? '3.2' : '1.4');
      line.setAttribute('opacity', on ? '1' : '0.38');
    });
    const rows = chosen.map((n, rank) => `${rank + 1}위 X=${data.x[n.i]} (거리 ${fmt(n.d)}, Y=${data.y[n.i]})`).join(' → ');
    const weightName = state.weight === 'distance' ? '역거리 가중' : '균등 가중';
    const zeroNote = chosen.some((n) => n.d === 0)
      ? ' 선택한 이웃에 거리 0이 있어 그 관측만 같은 비중으로 평균했습니다.'
      : ' 이 입력에는 거리 0인 이웃이 없습니다.';
    const curveNote = state.weight === 'distance'
      ? ' 그림 3의 곡선은 균등 가중으로 고정되어 있습니다.'
      : ' 그림 3에서 같은 K의 균등 가중 곡선을 굵게 표시합니다.';
    const note = document.getElementById('knn-fig1-note');
    if (note) note.textContent = `가로 입력 X / 세로 목표 Y · 주황선 x=3.2 · 파랑은 K=${state.k} 이웃`;
    document.getElementById('knn-neighbor-status').textContent =
      `K=${state.k}, ${weightName}. ${rows}. 예측 ${fmt(pred)}. 이웃은 X만으로 골랐습니다.${zeroNote}${curveNote}`;
    const uniform = uniformPredict(data.x, data.y, data.query, state.k);
    document.getElementById('knn-curve-status').textContent =
      `그림 3은 균등 가중입니다. K=${state.k}일 때 x=3.2의 예측은 ${fmt(uniform)}입니다. K=5의 균등 가중 예측은 모든 x에서 4.4입니다. 0.05 간격 격자라 계단 경계가 정확한 중간점과 조금 다를 수 있습니다.`;
  }

  document.querySelectorAll('button[data-k]').forEach((button) => {
    button.addEventListener('click', () => {
      state.k = Number(button.dataset.k);
      render();
    });
  });
  document.querySelectorAll('button[data-weight]').forEach((button) => {
    button.addEventListener('click', () => {
      state.weight = button.dataset.weight;
      render();
    });
  });
  document.querySelectorAll('button[data-scale]').forEach((button) => {
    button.addEventListener('click', () => {
      const mode = button.dataset.scale;
      document.querySelectorAll('button[data-scale]').forEach((item) => {
        item.setAttribute('aria-pressed', String(item.dataset.scale === mode));
      });
      document.getElementById('knn-table-raw').classList.toggle('knn-table-active', mode === 'raw');
      document.getElementById('knn-table-std').classList.toggle('knn-table-active', mode === 'std');
      document.getElementById('knn-panel-raw').setAttribute('stroke', mode === 'raw' ? '#d97706' : '#cbd5e1');
      document.getElementById('knn-panel-std').setAttribute('stroke', mode === 'std' ? '#d97706' : '#cbd5e1');
      document.getElementById('knn-scale-status').textContent = mode === 'raw'
        ? '원래 단위입니다. 거리 √[(면적 차이)²+(층 차이)²]. 최단은 B(8.2462)이고 A는 2위(12.0416)입니다. 면적의 숫자 차이가 거리에 크게 들어갑니다. 위와 아래 막대 높이는 서로 다른 척도입니다.'
        : '표준화 거리입니다. 학습 4건, 분모 4의 표준편차는 면적 25.4951, 층 3.2016입니다. 평균 80㎡와 5.5층은 차이에서 빠집니다. 최단은 A(0.5649)이고 B는 4위(2.5000)입니다. A가 시장에서 더 유사하다고 단정하지 않습니다.';
    });
  });
  document.querySelectorAll('button[data-task]').forEach((button) => {
    button.addEventListener('click', () => {
      const task = button.dataset.task;
      document.querySelectorAll('button[data-task]').forEach((item) => {
        item.setAttribute('aria-pressed', String(item.dataset.task === task));
      });
      document.getElementById('knn-box-reg').setAttribute('stroke', task === 'reg' ? '#d97706' : '#94a3b8');
      document.getElementById('knn-box-cls').setAttribute('stroke', task === 'cls' ? '#d97706' : '#94a3b8');
      document.getElementById('knn-task-status').textContent = task === 'reg'
        ? '회귀 예제입니다. 그림 1과 같은 X·Y에서 K=3 균등 가중 예측은 (5+3+2)/3≈3.3333입니다. 분류 상자의 라벨과 다른 자료입니다.'
        : '분류 예제입니다. 따로 둔 라벨 1·0·1에서 양성 2건, 음성 1건입니다. 균등 다수결은 양성이고 비율은 2/3입니다. 본문의 다섯 라벨 3/5와 다른 예제이며, 회귀 Y를 라벨로 바꾼 값이 아닙니다. 2/3를 보정된 확률로 읽지 않습니다.';
    });
  });
  document.querySelectorAll('.knn-controls').forEach((panel) => { panel.hidden = false; });
  render();
}
