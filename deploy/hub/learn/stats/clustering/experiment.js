export function squaredDistance(a, b) {
  return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2;
}

export function assignLabels(points, centers) {
  return points.map((point) => {
    let best = 0;
    let bestDistance = Infinity;
    centers.forEach((center, index) => {
      const distance = squaredDistance(point, center);
      if (distance < bestDistance) {
        bestDistance = distance;
        best = index;
      }
    });
    return best;
  });
}

export function inertia(points, centers, labels) {
  return points.reduce((sum, point, index) => sum + squaredDistance(point, centers[labels[index]]), 0);
}

export function euclid(a, b) {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

export function silhouetteRows(points, labels) {
  const ids = [...new Set(labels)];
  if (ids.length < 2 || ids.length >= points.length) return null;
  return points.map((point, index) => {
    const mine = labels[index];
    const same = points.filter((_, other) => other !== index && labels[other] === mine);
    if (!same.length) return { a: null, b: null, s: 0, alone: true };
    const a = same.reduce((sum, other) => sum + euclid(point, other), 0) / same.length;
    let b = Infinity;
    ids.forEach((id) => {
      if (id === mine) return;
      const others = points.filter((_, other) => labels[other] === id);
      const mean = others.reduce((sum, other) => sum + euclid(point, other), 0) / others.length;
      if (mean < b) b = mean;
    });
    return { a, b, s: (b - a) / Math.max(a, b), alone: false };
  });
}

export function flatClusters(values, merges, height) {
  const count = values.length;
  const consumed = new Set();
  merges.forEach((row) => {
    if (row[2] <= height) {
      consumed.add(row[0]);
      consumed.add(row[1]);
    }
  });
  function members(node) {
    if (node < count) return [values[node]];
    const [left, right, mergeHeight] = merges[node - count];
    if (mergeHeight <= height) return members(left).concat(members(right));
    return null;
  }
  const clusters = [];
  for (let node = 0; node < count + merges.length; node += 1) {
    if (consumed.has(node)) continue;
    if (node >= count && merges[node - count][2] > height) continue;
    const group = members(node);
    if (group) clusters.push(group.slice().sort((a, b) => a - b));
  }
  return clusters.sort((a, b) => a[0] - b[0]);
}

if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('cluster-data').textContent);
  const names = ['A', 'B', 'C', 'D', 'E', 'F'];
  const fills = ['#2563eb', '#d97706', '#059669', '#7c3aed', '#db2777', '#0891b2'];
  let k = 2;
  let step = 3;
  let point = 0;
  let cut = 6;

  const money = (value) => {
    if (Math.abs(value - 8 / 3) < 1e-9) return '8/3 (약 2.6667)';
    if (Math.abs(value - 22 / 3) < 1e-9) return '22/3';
    if (Math.abs(value - 4 / 3) < 1e-9) return '4/3';
    if (Math.abs(value - 2 / 9) < 1e-9) return '2/9';
    if (Math.abs(value - 5 / 9) < 1e-9) return '5/9';
    if (Number.isInteger(value)) return String(value);
    return value.toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
  };
  const coord = (pair) => `(${pair.map((value) => money(value)).join(', ')})`;
  const place = (pair) => [36 + pair[0] * 36, 325 - pair[1] * 30];
  const groups = (labels) => names.map((name, index) => `${name}→군집 ${labels[index] + 1}`).join(', ');

  function currentModel() {
    if (k === 2) return data.demo[step];
    return data.models[k - 1];
  }

  function renderK() {
    document.querySelectorAll('[data-k]').forEach((node) => {
      const on = Number(node.dataset.k) === k;
      if (node.tagName === 'BUTTON') node.setAttribute('aria-pressed', on ? 'true' : 'false');
      else {
        node.setAttribute('r', on ? '7' : '5');
        node.setAttribute('fill', on ? '#d97706' : '#2563eb');
      }
    });
    document.querySelectorAll('[data-step]').forEach((button) => {
      button.disabled = k !== 2;
      button.setAttribute('aria-pressed', k === 2 && Number(button.dataset.step) === step ? 'true' : 'false');
    });
  }

  function renderScatter() {
    const model = currentModel();
    const labels = model.labels;
    data.points.forEach((pair, index) => {
      const dot = document.querySelector(`#kmeans circle[data-point="${index}"]`);
      dot.setAttribute('fill', labels ? fills[labels[index]] : '#64748b');
      dot.setAttribute('stroke', index === point ? '#d97706' : '#111827');
      dot.setAttribute('stroke-width', index === point ? '3' : '1');
      const mark = document.querySelector(`#kmeans text[data-member="${index}"]`);
      mark.textContent = labels ? String(labels[index] + 1) : '';
    });
    document.querySelectorAll('#kmeans [data-center]').forEach((node) => {
      const index = Number(node.dataset.center);
      const center = model.centers[index];
      if (!center) {
        node.setAttribute('visibility', 'hidden');
        return;
      }
      const [x, y] = place(center);
      node.setAttribute('visibility', 'visible');
      node.querySelector('[data-h]').setAttribute('x1', x - 8);
      node.querySelector('[data-h]').setAttribute('x2', x + 8);
      node.querySelector('[data-h]').setAttribute('y1', y);
      node.querySelector('[data-h]').setAttribute('y2', y);
      node.querySelector('[data-v]').setAttribute('x1', x);
      node.querySelector('[data-v]').setAttribute('x2', x);
      node.querySelector('[data-v]').setAttribute('y1', y - 8);
      node.querySelector('[data-v]').setAttribute('y2', y + 8);
    });
    const lines = model.centers.map((center, index) => `군집 ${index + 1} ${coord(center)}`).join(' · ');
    let text = '';
    if (k !== 2) {
      text = `K=${k}. 관측점 초기 조합 중 W가 가장 작은 최종 결과입니다. ${groups(labels)}. 중심 ${lines}. W=${money(model.inertia)}. `;
      if (k === 6) text += '각 관측이 자기 군집이므로 W=0입니다. 목적값이 0이라는 사실만으로 가장 좋은 군집은 아닙니다. ';
      text += '이 화면의 단계 시연은 K=2이고 초기 중심을 A와 D에 고정한 별도 절차입니다.';
    } else if (step === 0) {
      text = '초기 중심을 A=(1, 1), D=(7, 7)에 두었습니다. 아직 배정 전이라 W를 계산하지 않습니다. 이 시작점은 교육용으로 고정했고, 그림 2가 고른 초기 조합 전체 탐색과는 다른 절차입니다.';
    } else {
      const before = step === 1 ? null : data.demo[step - 1].w;
      const delta = before == null ? '' : ` 직전 W ${money(before)}에서 ${money(model.w - before)}만큼 변했습니다.`;
      text = `${['', '가까운 중심에 배정했습니다.', '배정을 고정하고 중심을 평균으로 옮겼습니다.', '다시 배정해도 소속이 바뀌지 않아 멈춥니다.'][step]} ${groups(labels)}. 중심 ${lines}. W=${money(model.w)}.${delta} 최종 중심은 (4/3, 4/3), (22/3, 22/3)이고 W=8/3입니다. 한 번의 수렴이 모든 초기값의 전역 최적해를 보장하지는 않습니다.`;
    }
    document.getElementById('cluster-kmeans-status').textContent = text;
    const elbow = data.models[k - 1];
    const counts = elbow.labels.reduce((bag, label) => {
      bag[label] = (bag[label] || 0) + 1;
      return bag;
    }, {});
    const countText = Object.keys(counts).map((label) => `군집 ${Number(label) + 1} ${counts[label]}건`).join(', ');
    const walk = k === 2 && step < 3 ? ' 그림 1은 초기 중심 A·D의 단계 시연이라 최종 점과 중심이 다를 수 있습니다.' : '';
    document.getElementById('cluster-elbow-status').textContent =
      `K=${k}. ${countText}. 그림 2의 W=${money(elbow.inertia)}. K=1의 W는 ${money(data.models[0].inertia)}이고 K=6의 W는 0입니다. 전역 최소 W는 K가 커져도 증가하지 않지만, 가장 작은 W가 분석 목적에 맞는 군집 수는 아닙니다.${walk}`;
  }

  function renderSilhouette() {
    const model = data.models[k - 1];
    const rows = silhouetteRows(data.points, model.labels);
    const status = document.getElementById('cluster-sil-status');
    document.querySelectorAll('#silhouette rect').forEach((bar) => {
      const index = Number(bar.dataset.point);
      const row = rows ? rows[index] : null;
      const width = row ? Math.max(0, row.s) * 230 : 0;
      bar.setAttribute('width', width);
      bar.setAttribute('fill', index === point ? '#d97706' : fills[model.labels[index]]);
      const label = document.querySelector(`#silhouette text[data-sil="${index}"]`);
      label.textContent = row ? row.s.toFixed(3) : '—';
      label.setAttribute('x', 86 + width);
    });
    if (!rows) {
      status.textContent = `K=${k}에서는 일반적인 전체 실루엣을 계산하지 않습니다. 군집 수가 1이거나 관측 수와 같기 때문입니다. 본문 예제는 K=2입니다. 지표의 범위는 −1부터 1입니다.`;
      return;
    }
    const row = rows[point];
    const mine = model.labels[point];
    const inside = data.points
      .map((pair, index) => ({ pair, index }))
      .filter((item) => item.index !== point && model.labels[item.index] === mine)
      .map((item) => `${names[item.index]} ${euclid(data.points[point], item.pair).toFixed(3)}`);
    const outside = [...new Set(model.labels)]
      .filter((label) => label !== mine)
      .map((label) => {
        const peers = data.points.filter((_, index) => model.labels[index] === label);
        const mean = peers.reduce((sum, pair) => sum + euclid(data.points[point], pair), 0) / peers.length;
        return `군집 ${label + 1} 평균 ${mean.toFixed(3)}`;
      });
    const alone = row.alone ? ' 같은 군집의 다른 관측이 없어 실루엣을 0으로 둡니다.' : '';
    const scope = k === 2 ? '본문의 K=2 배정입니다.' : `지금 값은 K=${k}의 최종 배정으로 다시 계산했습니다. 본문 A의 약 0.889는 K=2입니다.`;
    status.textContent =
      `${names[point]}=(${data.points[point].join(', ')}), 군집 ${mine + 1}. 내부 거리 ${inside.join(', ') || '없음'}. a=${row.a == null ? '—' : row.a.toFixed(3)}. 다른 군집 ${outside.join(', ')}. b=${row.b == null ? '—' : row.b.toFixed(3)}. s=${row.s.toFixed(3)}.${alone} 제곱하지 않은 유클리드 거리입니다. ${scope} 범위는 −1부터 1이며, 높은 값이 독립된 시장 유형의 증거는 아닙니다.`;
  }

  function renderCut() {
    const y = 325 - cut * 30;
    const line = document.getElementById('cluster-cut');
    line.setAttribute('y1', y);
    line.setAttribute('y2', y);
    document.getElementById('cluster-cut-label').setAttribute('y', Math.max(70, y - 10));
    const clusters = flatClusters(data.hierarchy.x, data.hierarchy.merges, cut);
    const text = clusters.map((group) => `{${group.join(', ')}}`).join(' · ');
    document.getElementById('cluster-cut-label').textContent = `높이 ${cut} · ${clusters.length}군집`;
    document.querySelectorAll('[data-cut]').forEach((button) => {
      button.setAttribute('aria-pressed', Number(button.dataset.cut) === cut ? 'true' : 'false');
    });
    document.getElementById('cluster-cut-status').textContent =
      `완전연결. 절단 높이 ${cut}. 병합 높이가 이 값 이하이면 합친 것으로 봅니다. 현재 ${clusters.length}군집: ${text}. 높이 6은 {1, 2}와 {6, 9}이고, 8 이상이면 한 군집입니다. 세로축은 병합 높이이고 가로 간격은 원자료의 거리가 아닙니다.`;
  }

  function render() {
    renderK();
    renderScatter();
    renderSilhouette();
    renderCut();
  }

  document.querySelectorAll('[data-k]').forEach((node) => {
    node.addEventListener('click', () => {
      k = Number(node.dataset.k);
      if (k === 2) step = 3;
      render();
    });
  });
  document.querySelectorAll('[data-step]').forEach((button) => {
    button.addEventListener('click', () => {
      if (k !== 2) return;
      step = Number(button.dataset.step);
      render();
    });
  });
  document.querySelectorAll('[data-point]').forEach((node) => {
    node.addEventListener('click', () => {
      point = Number(node.dataset.point);
      render();
    });
  });
  document.querySelectorAll('[data-cut]').forEach((button) => {
    button.addEventListener('click', () => {
      cut = Number(button.dataset.cut);
      render();
    });
  });
  document.querySelectorAll('.cluster-controls').forEach((node) => node.removeAttribute('hidden'));
  render();
}
