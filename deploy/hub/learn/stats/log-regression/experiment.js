// Chapter-local display calculations; no Macro analysis or selection API calls.
export function predict(model, key, x) {
  const z = key === 'log_x' || key === 'log_log' ? Math.log(x) : x;
  const value = model.intercept + model.slope * z;
  return key === 'log_y' || key === 'log_log' ? Math.exp(value) : value;
}
export function percentage(slope, change) {
  if (change === 0) return { exact: 0, approx: 0, gap: 0 };
  const exact = 100 * Math.expm1(slope * Math.log1p(change / 100));
  const approx = slope * change;
  return { exact, approx, gap: exact - approx };
}
if (typeof document !== 'undefined') {
  const models = JSON.parse(document.getElementById('lg-model-data').textContent);
  const names = { level: '원래 척도', log_y: '로그-선형', log_x: '선형-로그', log_log: '로그-로그' };
  const interpretations = {
    level: m => `면적 1㎡ 차이의 적합 단가 차이는 ${m.slope.toFixed(4)}만원/㎡입니다.`,
    log_y: m => `면적 1㎡ 차이의 단순 역변환 적합값 비율은 exp(${m.slope.toFixed(6)})입니다.`,
    log_x: m => `면적 +1%의 적합 단가 변화량은 b ln(1.01)=${(m.slope * Math.log1p(.01)).toFixed(3)}만원/㎡입니다.`,
    log_log: m => `단순 역변환 곡선의 탄력성은 ${m.slope.toFixed(5)}입니다. 면적 +1%일 때 약 ${m.slope.toFixed(2)}% 변화하는 작은 변화 근사입니다.`
  };
  const equations = {
    level: m => `ŷ = ${m.intercept.toFixed(4)} − ${Math.abs(m.slope).toFixed(4)}X`,
    log_y: m => `ln Y의 적합값 = ${m.intercept.toFixed(5)} − ${Math.abs(m.slope).toFixed(6)}X`,
    log_x: m => `ŷ = ${m.intercept.toFixed(3)} − ${Math.abs(m.slope).toFixed(3)} ln X`,
    log_log: m => `ln Y의 적합값 = ${m.intercept.toFixed(5)} − ${Math.abs(m.slope).toFixed(5)} ln X`
  };
  const figure = document.getElementById('lg-curves'), select = document.getElementById('lg-model');
  function updateModel() {
    const key = select.value;
    figure.querySelectorAll('[data-model]').forEach(curve => curve.toggleAttribute('hidden', key !== 'all' && curve.dataset.model !== key));
    const status = document.getElementById('lg-model-status');status.replaceChildren();
    (key === 'all' ? Object.keys(models) : [key]).forEach(k => {
      const p = document.createElement('p');
      p.textContent = `${names[k]} · ${equations[k](models[k])} · 100㎡: ${predict(models[k], k, 100).toFixed(2)}만원/㎡. ${interpretations[k](models[k])}`;
      status.append(p);
    });
    const cap = `그림 2. ${key === 'all' ? '네 모형 전체 비교' : names[key] + ' 보기'} · 같은 학습 자료 30건, 면적 22~310㎡. 주황·초록은 산술평균 보정 없는 단순 역변환입니다. 관측점은 변경하지 않습니다.`;
    figure.querySelector('figcaption').textContent = cap;
    figure.querySelector('#curves-desc').textContent = cap;
  }
  select.addEventListener('change', updateModel);updateModel();figure.querySelector('.lg-controls').hidden = false;
  const percentFigure = document.getElementById('lg-percent'), slider = document.getElementById('lg-change');
  function updatePercent() {
    const c = Number(slider.value), result = percentage(models.log_log.slope, c);
    document.getElementById('lg-change-value').textContent = `${c}%`;
    document.getElementById('lg-percent-status').textContent = `면적 +${c}%${c === 100 ? ' (두 배)' : ''}: 정확한 변화율 ${result.exact.toFixed(2)}%, 근삿값 ${result.approx.toFixed(2)}%, 차이 ${result.gap.toFixed(2)}%p (정확값−근삿값). 산술평균 보정 없는 지수변환 곡선의 비교입니다.`;
    for (const key of ['exact', 'approx']) {
      const height = -result[key] * 4.5;
      percentFigure.querySelector(`[data-percent="${key}"]`).setAttribute('height', height);
      const label = percentFigure.querySelector(`[data-percent-label="${key}"]`);
      label.textContent = `${result[key].toFixed(2)}%`;label.setAttribute('y', height + 92);
    }
    percentFigure.querySelector('svg > text').textContent = `면적 +${c}%${c === 100 ? ' (두 배)' : ''} · 정확한 변화율과 근사 변화율`;
    const cap = `그림 3. 공통 자료의 로그-로그 기울기 ${models.log_log.slope.toFixed(5)}를 고정한 가상 비교. 면적 +${c}%: 정확식 ${result.exact.toFixed(2)}%, 근사 ${result.approx.toFixed(2)}%.`;
    percentFigure.querySelector('figcaption').textContent = cap;percentFigure.querySelector('#percent-desc').textContent = cap;
  }
  slider.addEventListener('input', updatePercent);
  percentFigure.querySelectorAll('[data-change]').forEach(button => button.addEventListener('click', () => {slider.value = button.dataset.change;updatePercent();}));
  updatePercent();percentFigure.querySelector('.lg-controls').hidden = false;
}
