// Chapter-local OLS exercise. No Macro APIs or production model code are used.
export function summarize(rows) {
  const n = rows.length;
  const xmean = rows.reduce((s, r) => s + r.area, 0) / n;
  const ymean = rows.reduce((s, r) => s + r.price, 0) / n;
  const sxx = rows.reduce((s, r) => s + (r.area - xmean) ** 2, 0);
  const sxy = rows.reduce((s, r) => s + (r.area - xmean) * (r.price - ymean), 0);
  return { n, xmean, ymean, sxx, sxy, slope: sxy / sxx };
}

export function evaluateSlope(rows, slope) {
  const summary = summarize(rows);
  const intercept = summary.ymean - slope * summary.xmean;
  const residuals = rows.map(row => row.price - (intercept + slope * row.area));
  return { ...summary, slope, intercept, residuals, sse: residuals.reduce((s, e) => s + e * e, 0) };
}

if (typeof document !== 'undefined') {
  const experiment = document.getElementById('rg-experiment');
  if (experiment) {
    const rows = JSON.parse(document.getElementById('rg-rows').textContent);
    const optimum = evaluateSlope(rows, summarize(rows).slope);
    const slider = document.getElementById('rg-slope');
    const num = (n, digits = 2) => n.toLocaleString('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    function update(slope) {
      const current = evaluateSlope(rows, slope);
      slider.value = String(slope);
      slider.setAttribute('aria-valuetext', `기울기 ${num(slope, 4)}, 절편 ${num(current.intercept, 4)}, SSE ${num(current.sse)}`);
      const marker = document.getElementById('rg-current');
      marker.setAttribute('cx', 80 + (slope + 1.2) * 450);
      marker.setAttribute('cy', 285 - (current.sse - optimum.sse) / 250);
      const line = document.getElementById('rg-current-line');
      for (const [end, x] of [[1, 22], [2, 310]]) {
        line.setAttribute(`y${end}`, 280 - (current.intercept + slope * x) * .4);
      }
      const increase = Math.max(0, current.sse - optimum.sse);
      document.getElementById('rg-experiment-status').textContent = `현재 ŷ=${num(current.intercept, 4)} ${slope < 0 ? '−' : '+'} ${num(Math.abs(slope), 4)}×면적. 현재 SSE ${num(current.sse)} / 최소 SSE ${num(optimum.sse)} / 증가량 ${num(increase)} (만원/㎡)². 직선은 표본평균점 (${num(current.xmean, 4)}㎡, ${num(current.ymean, 4)}만원/㎡)을 지납니다.`;
    }
    slider.addEventListener('input', () => update(Number(slider.value)));
    slider.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'ArrowDown', 'ArrowUp'].includes(event.key)) return;
      event.preventDefault();
      const direction = ['ArrowLeft', 'ArrowDown'].includes(event.key) ? -1 : 1;
      update(Math.max(-1.2, Math.min(-.2, Number(slider.value) + direction * (event.shiftKey ? .01 : .001))));
    });
    document.getElementById('rg-reset').addEventListener('click', () => update(optimum.slope));
    update(optimum.slope);
    experiment.querySelector('.rg-controls').hidden = false;

    const figure = document.getElementById('rg-fit');
    const select = document.getElementById('rg-observation');
    select.addEventListener('change', () => {
      const row = rows.find(row => String(row.id) === select.value);
      const residual = document.getElementById('rg-selected-residual');
      figure.querySelectorAll('circle[data-id]').forEach(dot => dot.setAttribute('data-selected', String(dot.dataset.id === select.value)));
      residual.toggleAttribute('hidden', !row);
      if (row) {
        const predicted = optimum.intercept + optimum.slope * row.area;
        const e = row.price - predicted;
        residual.setAttribute('x1', 70 + row.area * 1.5);
        residual.setAttribute('x2', 70 + row.area * 1.5);
        residual.setAttribute('y1', 320 - row.price * .5);
        residual.setAttribute('y2', 320 - predicted * .5);
        residual.setAttribute('stroke', e >= 0 ? '#0f766e' : '#b45309');
        document.getElementById('rg-observation-status').textContent = `${row.id}번 · ${row.group} · 면적 ${row.area}㎡ · 관측 단가 ${num(row.price)} · 적합 단가 ${num(predicted)} · 잔차 ${e >= 0 ? '+' : '−'}${num(Math.abs(e))} (단가·잔차 단위: 만원/㎡). 세로 점선이 이 잔차입니다.`;
      } else {
        document.getElementById('rg-observation-status').textContent = '관측값을 선택하면 그 점의 세로 잔차만 표시합니다.';
      }
    });
    figure.querySelector('.rg-controls').hidden = false;
  }
}
