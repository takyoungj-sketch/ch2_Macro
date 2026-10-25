// Chapter 30 illustrations. The tree uses the shared 20 training rows only.
export function leafIndex(x, t1 = 31, t2 = 80) {
  if (x <= t1) return 0;
  if (x <= t2) return 1;
  return 2;
}

export function cost(risk, leaves, alpha) {
  return risk + alpha * leaves;
}

if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('tree-data').textContent);
  const state = { x: 75, threshold: data.t1, alpha: 0 };
  const names = ['잎 1', '잎 2', '잎 3'];
  const money = (v) => (Math.round((v + Number.EPSILON) * 100) / 100).toFixed(2);
  const count = (v) => Math.round(v).toLocaleString('ko-KR');

  function renderPath() {
    const x = state.x;
    const leaf = leafIndex(x, data.t1, data.t2);
    document.querySelectorAll('.tree-x').forEach((input) => {
      if (document.activeElement !== input) input.value = String(x);
    });
    document.querySelectorAll('button[data-x]').forEach((button) => {
      button.setAttribute('aria-pressed', String(Number(button.dataset.x) === x));
    });
    const active = new Set(['root']);
    if (leaf === 0) active.add('leaf1');
    else {
      active.add('split');
      active.add(leaf === 1 ? 'leaf2' : 'leaf3');
    }
    document.querySelectorAll('[data-node]').forEach((node) => {
      const on = active.has(node.dataset.node);
      node.setAttribute('stroke', on ? '#d97706' : '#94a3b8');
      node.setAttribute('stroke-width', on ? '3' : '1.5');
      node.setAttribute('opacity', on ? '1' : '0.55');
    });
    const line = document.getElementById('tree-x-line');
    const label = document.getElementById('tree-x-label');
    const drawn = Math.min(Math.max(x, 0), 310);
    const px = 65 + drawn * 1.65;
    const py = 325 - data.means[leaf] * 0.5;
    if (line) {
      line.setAttribute('x1', String(px));
      line.setAttribute('x2', String(px));
    }
    if (label) {
      label.setAttribute('x', String(Math.min(px + 6, 520)));
      label.textContent = `X=${x} · ${names[leaf]} · ${money(data.means[leaf])}`;
    }
    const marker = document.getElementById('tree-x-mark');
    if (marker) {
      marker.setAttribute('cx', String(px));
      marker.setAttribute('cy', String(py));
    }
    const outside = x < data.trainMin || x > data.trainMax;
const route = leaf === 0
    ? `X=${x}. ${data.t1} 이하이므로 첫 질문에서 잎 1로 갑니다. 두 번째 질문은 적용하지 않습니다.`
    : `X=${x}. ${data.t1}보다 커서 두 번째 질문으로 갑니다. ${x <= data.t2 ? `${data.t2} 이하이므로 잎 2` : `${data.t2}보다 크므로 잎 3`}에 도착합니다.`;
    const sensitive = leaf === 0 ? ' 잎 1은 학습 관측 1건이라 표본이 바뀌면 경계와 예측이 달라질 수 있습니다.' : '';
    const extra = outside ? ` 학습 X는 ${data.trainMin}부터 ${data.trainMax}까지입니다. 범위 밖에서는 끝 잎의 평균만 반환하며, 추세를 연장한 값은 아닙니다.` : '';
    const text = `${route} 학습 관측 ${data.counts[leaf]}건, 예측 ${money(data.means[leaf])}.${sensitive}${extra}`;
    document.querySelectorAll('[data-path-status]').forEach((node) => { node.textContent = text; });
  }

  function renderSplit() {
    const row = data.candidates.find((item) => Math.abs(item.threshold - state.threshold) < 1e-9) || data.candidates[0];
    state.threshold = row.threshold;
    const select = document.getElementById('tree-split');
    if (select) select.value = String(row.threshold);
    document.querySelectorAll('#split circle[data-threshold]').forEach((mark) => {
      const on = Math.abs(Number(mark.dataset.threshold) - row.threshold) < 1e-9;
      mark.setAttribute('fill', on ? '#d97706' : '#2563eb');
      mark.setAttribute('r', on ? '6' : '4');
    });
    const best = data.candidates.reduce((a, b) => (a.sse <= b.sse ? a : b));
    const weighted = row.sse / 20;
    const plain = row.sse_left / row.n_left + row.sse_right / row.n_right;
    const gate = row.n_left >= 2 && row.n_right >= 2
      ? '최소 잎 크기 2에서도 양쪽이 남습니다.'
      : '최소 잎 크기를 2로 두면 한쪽에 1건만 남아 이 후보는 제외됩니다.';
    document.getElementById('tree-split-status').textContent =
      `경계 ${row.threshold}. 왼쪽 ${row.n_left}건, 평균 ${money(row.mean_left)}, SSE ${count(row.sse_left)}. 오른쪽 ${row.n_right}건, 평균 ${money(row.mean_right)}, SSE ${count(row.sse_right)}. 자식 SSE 합 ${count(row.sse)}. 관측수로 가중한 MSE는 ${money(weighted)}이고, 두 MSE를 그냥 더하면 ${money(plain)}입니다. SSE가 가장 작은 경계(값 ${best.threshold})와 비교한 차이는 ${count(row.sse - best.sse)}입니다. ${gate} 확인 10건은 넣지 않았습니다.`;
  }

  function renderAlpha() {
    document.querySelectorAll('button[data-alpha]').forEach((button) => {
      button.setAttribute('aria-pressed', String(Number(button.dataset.alpha) === state.alpha));
    });
    const rows = data.risks.map((item) => ({ leaves: item.leaves, value: cost(item.risk, item.leaves, state.alpha) }));
    const best = rows.reduce((a, b) => (a.value < b.value ? a : b));
    document.getElementById('tree-alpha-status').textContent =
      `α=${state.alpha}. R(T)는 학습 SSE를 20으로 나눈 값입니다. 1잎 ${money(rows[0].value)}, 2잎 ${money(rows[1].value)}, 3잎 ${money(rows[2].value)}. 이 세 후보 중 ${best.leaves}잎의 값이 가장 작습니다. 가능한 모든 나무의 가지치기 경로는 아닙니다.`;
  }

  document.querySelectorAll('.tree-x').forEach((input) => {
    input.addEventListener('input', () => {
      const value = Number(input.value);
      if (!Number.isFinite(value)) return;
      state.x = value;
      renderPath();
    });
  });
  document.querySelectorAll('button[data-x]').forEach((button) => {
    button.addEventListener('click', () => {
      state.x = Number(button.dataset.x);
      renderPath();
    });
  });
  document.getElementById('tree-split').addEventListener('change', () => {
    state.threshold = Number(document.getElementById('tree-split').value);
    renderSplit();
  });
  document.querySelectorAll('#split circle[data-threshold]').forEach((mark) => {
    mark.style.cursor = 'pointer';
    mark.addEventListener('click', () => {
      state.threshold = Number(mark.dataset.threshold);
      renderSplit();
    });
  });
  document.querySelectorAll('button[data-alpha]').forEach((button) => {
    button.addEventListener('click', () => {
      state.alpha = Number(button.dataset.alpha);
      renderAlpha();
    });
  });
  document.querySelectorAll('.tree-controls').forEach((panel) => { panel.hidden = false; });
  renderPath();
  renderSplit();
  renderAlpha();
}
