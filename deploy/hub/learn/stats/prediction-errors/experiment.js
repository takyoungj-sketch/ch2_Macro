// Chapter-only calculations. Original example data and Macro policies are unchanged.
export function predictionMetrics(actual, predicted) {
  const errors = actual.map((y, i) => y - predicted[i]);
  const average = values => values.reduce((a, b) => a + b, 0) / values.length;
  const MSE = average(errors.map(e => e ** 2));
  return { errors, ME: average(errors), MAE: average(errors.map(Math.abs)), MSE, RMSE: Math.sqrt(MSE), MAPE: actual.some(y => y === 0) ? null : 100 * average(errors.map((e, i) => Math.abs(e / actual[i]))) };
}
export function constantLoss(actual, value) {
  return predictionMetrics(actual, actual.map(() => value));
}
if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('errors-data').textContent);
  const view = document.getElementById('errors-model');
  const metric = document.getElementById('errors-metric');
  const slider = document.getElementById('errors-constant');
  const scores = Object.fromEntries(['A', 'B'].map(key => [key, predictionMetrics(data.ranking.actual, data.ranking[`${key}_predictions`])]));
  function updateRanking() {
    const key = metric.value;
    const winner = scores.A[key] < scores.B[key] ? 'A' : 'B';
    document.getElementById('errors-ranking-status').textContent = `${key} 기준 · A=${scores.A[key].toFixed(2)}, B=${scores.B[key].toFixed(2)} · 낮은 모형 ${winner}. ${key === 'MAE' ? '절대오차를 그대로 평균하면 A가 낮습니다.' : '제곱을 이용해 큰 실패에 더 민감하게 평가하면 B가 낮습니다.'} 같은 네 관측을 사용하며 다른 상황의 우열을 보장하지 않습니다.`;
    document.querySelectorAll('[data-rank-metric]').forEach(bar => {
      bar.setAttribute('stroke', bar.dataset.rankMetric === key ? '#0f766e' : 'none');
      bar.setAttribute('stroke-width', bar.dataset.rankMetric === key ? '3' : '0');
    });
    document.querySelectorAll('[data-error-model]').forEach(group => {
      group.toggleAttribute('hidden', view.value !== 'all' && group.dataset.errorModel !== view.value);
      const bar = group.querySelector('rect');
      bar.setAttribute('stroke', group.dataset.errorModel === winner ? '#0f766e' : 'none');
      bar.setAttribute('stroke-width', group.dataset.errorModel === winner ? '3' : '0');
    });
    const selected = view.value === 'all' ? ['A', 'B'] : [view.value];
    const winnerShown = view.value === 'all' || view.value === winner;
    document.getElementById('errors-model-status').textContent = `${view.value === 'all' ? '함께 비교' : '모형 ' + view.value} · 현재 ${key} 기준 낮은 모형은 ${winner}입니다. ${winnerShown ? '해당 모형의 막대를 테두리로 강조합니다.' : '함께 비교를 선택하면 해당 모형의 강조를 볼 수 있습니다.'} 표의 오차는 실제−예측, 막대는 절대오차입니다.`;
    const table = document.createElement('table');
    const head = table.createTHead().insertRow();
    ['모형', '관측', '실제', '예측', '오차', '절대오차'].forEach(label => { const th = document.createElement('th'); th.scope = 'col'; th.textContent = label; head.append(th); });
    const body = table.createTBody();
    selected.forEach(model => data.ranking.actual.forEach((y, i) => {
      const row = body.insertRow();
      [model, i + 1, y, data.ranking[`${model}_predictions`][i], scores[model].errors[i], Math.abs(scores[model].errors[i])].forEach(value => { row.insertCell().textContent = value; });
    }));
    document.getElementById('errors-observations').replaceChildren(table);
    document.getElementById('ranking-desc').textContent = document.getElementById('errors-ranking-status').textContent;
  }
  function updateLoss() {
    const c = Number(slider.value), result = constantLoss(data.loss.actual, c);
    document.getElementById('errors-loss-status').textContent = `c=${c.toFixed(2)} · MAE=${result.MAE.toFixed(4)}（Y와 같은 단위） · MSE=${result.MSE.toFixed(4)}（Y의 제곱 단위）. MAE 최소는 중앙값 2, MSE 최소는 평균 4입니다.`;
    ['MAE', 'MSE'].forEach((key, i) => {
      const point = document.querySelector(`[data-current-loss="${key}"]`);
      point.setAttribute('cx', 65 + i * 300 + c * 23);
      point.setAttribute('cy', 315 - result[key] / (key === 'MAE' ? 10 : 60) * 220);
    });
  }
  view.addEventListener('change', updateRanking);
  metric.addEventListener('change', updateRanking);
  slider.addEventListener('input', updateLoss);
  document.querySelectorAll('[data-constant]').forEach(button => button.addEventListener('click', () => { slider.value = button.dataset.constant; updateLoss(); }));
  updateRanking(); updateLoss();
  document.querySelectorAll('.errors-controls').forEach(control => { control.hidden = false; });
}
