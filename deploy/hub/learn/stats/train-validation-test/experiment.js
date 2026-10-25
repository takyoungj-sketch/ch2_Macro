// Chapter-only experiment; does not call Macro analysis APIs.
export function standardize(train, held, includeHeld = false) {
  const values = includeHeld ? [...train, held] : [...train];
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const sd = Math.sqrt(values.reduce((sum, x) => sum + (x - mean) ** 2, 0) / values.length);
  return { values, mean, sd, z: (held - mean) / sd };
}
if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('split-data').textContent).scaling;
  const select = document.getElementById('split-scale');
  const figure = select.closest('figure');
  function update() {
    const leaked = select.value === 'all';
    const result = standardize(data.train, data.held_out, leaked);
    const status = `${leaked ? '누수 사례' : '학습 기준'} · 사용한 면적 [${result.values.join(', ')}]㎡ · 평균 ${result.mean.toFixed(2)}㎡ · 모집단형 표준편차 ${result.sd.toFixed(2)}㎡ · 평가값 140㎡의 z=${result.z.toFixed(2)}. ${leaked ? '평가값이 전처리 기준 계산에 포함되었습니다.' : '평가값은 기준 계산에서 제외하고 같은 기준만 적용합니다.'}`;
    document.getElementById('split-scale-status').textContent = status;
    figure.querySelectorAll('[data-scale]').forEach(row => {
      const selected = row.dataset.scale === select.value;
      row.querySelectorAll('circle').forEach(point => point.setAttribute('r', selected ? '10' : '6'));
      row.querySelectorAll('line').forEach(axis => axis.setAttribute('stroke-width', selected ? '3' : '1'));
    });
    figure.querySelector('#scaling-desc').textContent = status + ' 두 결과는 같은 z 축 배율입니다.';
  }
  select.addEventListener('change', update);
  update();
  select.closest('.split-controls').hidden = false;
}
