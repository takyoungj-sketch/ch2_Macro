// Chapter-local classical OLS illustration; no Macro API or model-selection calls.
export function intervalAt(parameters, x) {
  const { n, xmean, Sxx, intercept, slope, s, critical } = parameters;
  const fit = intercept + slope * x;
  const h = 1 / n + (x - xmean) ** 2 / Sxx;
  const ciHalf = critical * s * Math.sqrt(h);
  const piHalf = critical * s * Math.sqrt(1 + h);
  return { x, fit, h, ciHalf, piHalf, ci: [fit - ciHalf, fit + ciHalf], pi: [fit - piHalf, fit + piHalf] };
}
if (typeof document !== 'undefined') {
  const parameters = JSON.parse(document.getElementById('mf-model-data').textContent);
  const slider = document.getElementById('mf-area'), figure = document.getElementById('mf-point');
  const axis = value => 90 + (value + 150) * .85;
  const fmt = value => value.toFixed(2);
  function update() {
    const x = Number(slider.value), point = intervalAt(parameters, x);
    document.getElementById('mf-area-value').textContent = `${fmt(x)}㎡`;
    const status = document.getElementById('mf-point-status');status.replaceChildren();
    const lines = [
      `면적 ${fmt(x)}㎡ · 적합 단가 ${fmt(point.fit)}만원/㎡`,
      `평균 95% 신뢰구간: ${fmt(point.ci[0])}~${fmt(point.ci[1])}만원/㎡ · 반폭 ${fmt(point.ciHalf)}만원/㎡`,
      `개별 거래 95% 예측구간: ${fmt(point.pi[0])}~${fmt(point.pi[1])}만원/㎡ · 반폭 ${fmt(point.piHalf)}만원/㎡`
    ];
    if (point.pi[0] < 0) lines.push('음수 하한도 계산 그대로 표시합니다. 실제 음수 거래단가를 뜻하지 않으며 모형의 오차 구조와 적용 범위를 점검할 단서입니다.');
    for (const line of lines) {const p = document.createElement('p');p.textContent = line;status.append(p);}
    figure.querySelector('#mf-point-heading').textContent = `면적 ${fmt(x)}㎡에서 같은 중심, 다른 불확실성`;
    for (const key of ['ci', 'pi']) {
      const line = figure.querySelector(`[data-point-interval="${key}"]`);
      line.setAttribute('x1', axis(point[key][0]));line.setAttribute('x2', axis(point[key][1]));
      figure.querySelector(`[data-point-center="${key}"]`).setAttribute('cx', axis(point.fit));
      figure.querySelector(`[data-point-label="${key}"]`).textContent = `${fmt(point[key][0])} ~ ${fmt(point[key][1])}`;
    }
    const caption = `그림 3. 면적 ${fmt(x)}㎡: 적합값 ${fmt(point.fit)}, 평균 95% 구간 ${fmt(point.ci[0])}~${fmt(point.ci[1])}, 개별 95% 구간 ${fmt(point.pi[0])}~${fmt(point.pi[1])}만원/㎡. 고전적 가정의 점별 구간이며 실제 가격의 보장 범위가 아닙니다.`;
    figure.querySelector('figcaption').textContent = caption;figure.querySelector('#at100-desc').textContent = caption;
    document.querySelectorAll('[data-selected-area]').forEach(line => {line.setAttribute('x1', 65 + x * 1.55);line.setAttribute('x2', 65 + x * 1.55);});
    document.getElementById('mf-bands-position').textContent = `선택 면적 ${fmt(x)}㎡ · 청록 점선 · 그림 3에서 면적을 조절할 수 있습니다.`;
  }
  slider.addEventListener('input', update);
  figure.querySelectorAll('[data-area]').forEach(button => button.addEventListener('click', () => {slider.value = button.dataset.area;update();}));
  update();figure.querySelector('.mf-controls').hidden = false;
}
