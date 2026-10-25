// Display experiments for chapter 22, independent of Macro regression/selection APIs.
export function evaluateModel(data, mode) {
  const predictions = data.test.map(row => ({ id: row.id, actual: row.actual, predicted: mode === 'baseline' ? data.baseline_mean : row.predicted }));
  return { predictions, mae: predictions.reduce((sum, row) => sum + Math.abs(row.actual - row.predicted), 0) / predictions.length };
}
export function classificationMetrics({ TP, FN, FP, TN }) {
  return { accuracy: (TP + TN) / (TP + FN + FP + TN), recall: TP + FN ? TP / (TP + FN) : null, precision: TP + FP ? TP / (TP + FP) : null };
}
export function clusterSummary({ points, labels, centers }) {
  return { centers: centers.map((_, group) => {
    const members = points.filter((_, i) => labels[i] === group);
    return centers[group].map((_, axis) => members.reduce((sum, point) => sum + point[axis], 0) / members.length);
  }), inertia: points.reduce((sum, point, i) => sum + point.reduce((distance, value, axis) => distance + (value - centers[labels[i]][axis]) ** 2, 0), 0) };
}
if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('sl-data').textContent);
  const figure = document.getElementById('sl-regression'), select = document.getElementById('sl-model');
  function updateRegression() {
    const mode = select.value, result = evaluateModel(data, mode);
    const name = mode === 'baseline' ? '학습 평균 기준모형' : '단순회귀';
    result.predictions.forEach(row => {
      const point = figure.querySelector(`[data-id="${row.id}"]`);
      point.setAttribute('cy', 465 - row.predicted * 1.35);
      point.querySelector('title').textContent = `${row.id}번 · 실제 ${row.actual.toFixed(2)}, 예측 ${row.predicted.toFixed(2)}만원/㎡`;
    });
    const formula = mode === 'baseline' ? `항상 ${data.baseline_mean.toFixed(2)}만원/㎡를 예측합니다. 이 평균은 학습 자료 20건에서만 계산했습니다.` : `학습식 ŷ=${data.fit.intercept.toFixed(3)}−${Math.abs(data.fit.slope).toFixed(4)}×면적입니다. 면적에 따라 예측값이 달라집니다.`;
    document.getElementById('sl-eval-status').textContent = `${name} · 같은 평가 10건의 MAE ${result.mae.toFixed(2)}만원/㎡. ${formula}`;
    const caption = `그림 1. ${name} · 1~20번 학습, 21~30번 평가 10건 · 평가 MAE ${result.mae.toFixed(2)}만원/㎡. 두 축은 같은 배율이며 회색 45도 선은 예측=실제입니다. 시간순 분할이 아닙니다.`;
    figure.querySelector('figcaption').textContent = caption;figure.querySelector('#regression-desc').textContent = caption;
  }
  select.addEventListener('change', updateRegression);updateRegression();figure.querySelector('.sl-controls').hidden = false;
  const clusterFigure = document.getElementById('sl-clusters'), clusterSelect = document.getElementById('sl-cluster-mode');
  const summary = clusterSummary(data.clustering);
  function updateClusters() {
    const showClusters = clusterSelect.value === 'cluster';
    clusterFigure.querySelectorAll('[data-cluster]').forEach(point => point.setAttribute('fill', showClusters && point.dataset.cluster === '1' ? '#d97706' : '#2563eb'));
    clusterFigure.querySelectorAll('[data-cluster-center]').forEach(center => center.toggleAttribute('hidden', !showClusters));
    clusterFigure.querySelector('#sl-cluster-legend').textContent = showClusters ? '파랑 A / 주황 B · ×: 중심 · 군집 번호는 정답 범주가 아님' : '같은 가상 관측점 8개 · 군집 색과 중심을 숨긴 보기';
    document.getElementById('sl-cluster-status').textContent = showClusters ? `K=2 · A 중심 (${summary.centers[0].join(', ')}), B 중심 (${summary.centers[1].join(', ')}) · 군집 내 제곱거리 합 ${summary.inertia}. 군집 이름을 바꾸어도 같은 분할입니다.` : '관측점만 표시합니다. 좌표는 바꾸지 않습니다. 정답 유형을 알고 색칠한 자료가 아닙니다.';
    const caption = showClusters ? '그림 3. 단위 없는 가상 8점의 K=2 결과. 중심 (1.5,1.5), (6.5,6.5), 군집 내 제곱거리 합 4. 색은 실제 시장의 정답 범주가 아닙니다.' : '그림 3. 동일한 단위 없는 가상 8점. 군집 색과 중심을 숨긴 상태이며 관측 좌표는 같습니다.';
    clusterFigure.querySelector('figcaption').textContent = caption;clusterFigure.querySelector('#clusters-desc').textContent = caption;
  }
  clusterSelect.addEventListener('change', updateClusters);updateClusters();clusterFigure.querySelector('.sl-controls').hidden = false;
}
