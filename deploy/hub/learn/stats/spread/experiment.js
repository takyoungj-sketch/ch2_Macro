export function describe(values, denominator) {
  const n = values.length;
  const sum = values.reduce((total, value) => total + value, 0);
  const mean = sum / n;
  const ss = values.reduce((total, value) => total + (value - mean) ** 2, 0);
  const divisor = denominator === 'n-1' ? n - 1 : n;
  return { n, sum, mean, ss, divisor, variance: ss / divisor, sd: Math.sqrt(ss / divisor) };
}

if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('sd-data').textContent);
  const prices = data.rows.map((row) => row.price);
  const without = data.rows.filter((row) => row.id !== 7).map((row) => row.price);
  let group = 'both';
  let point = 120;
  let square = false;
  let denominator = 'n';
  let inclusion = 'all';
  let scale = 'base';

  function money(value) {
    return (Math.round(value * 100) / 100).toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function renderGroups() {
    document.querySelectorAll('#sd-groups [data-group]').forEach((node) => {
      const on = group === 'both' || node.dataset.group === group;
      node.setAttribute('opacity', on ? '1' : '0.25');
      if (node.tagName === 'circle') node.setAttribute('stroke', on && group !== 'both' ? '#d97706' : '#1e3a8a');
    });
    document.querySelectorAll('[data-spread-group]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.spreadGroup === group ? 'true' : 'false');
    });
    const a = describe([25, 30, 35], 'n');
    const b = describe([10, 30, 50], 'n');
    const chosen = group === 'A' ? a : b;
    const detail = group === 'both'
      ? `집단 A 표준편차 ${money(a.sd)}분, 집단 B ${money(b.sd)}분. B는 A의 네 배입니다.`
      : `${group}의 관측은 ${group === 'A' ? '25, 30, 35' : '10, 30, 50'}분. 제곱편차 합 ${money(chosen.ss)}, 분산 ${money(chosen.variance)}, 표준편차 ${money(chosen.sd)}분.`;
    document.getElementById('sd-group-status').textContent = `두 집단의 평균은 30분입니다. ${detail} 이 자료는 분 단위의 가상 예제입니다.`;
  }

  function renderPoint() {
    document.querySelectorAll('#sd-deviations [data-price]').forEach((node) => {
      const on = Number(node.dataset.price) === point;
      node.setAttribute('stroke', on ? '#d97706' : '#1e3a8a');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('#sd-deviations [data-dev]').forEach((node) => {
      node.setAttribute('opacity', square ? '0.25' : '1');
    });
    document.querySelectorAll('#sd-deviations [data-sq]').forEach((node) => {
      node.setAttribute('opacity', square ? '1' : '0.2');
    });
    document.querySelectorAll('[data-point]').forEach((button) => {
      button.setAttribute('aria-pressed', Number(button.dataset.point) === point ? 'true' : 'false');
    });
    document.querySelectorAll('[data-square]').forEach((button) => {
      button.setAttribute('aria-pressed', (button.dataset.square === 'yes') === square ? 'true' : 'false');
    });
    const deviation = point - 100;
    document.getElementById('sd-point-status').textContent = square
      ? `단가 ${point}의 편차 ${deviation}을 제곱하면 ${deviation * deviation}입니다. 단위는 (만원/㎡)²입니다. 편차 합은 0이지만 제곱편차 합은 800입니다.`
      : `단가 ${point}만원/㎡, 평균 100, 편차 ${deviation > 0 ? '+' : ''}${deviation}만원/㎡. 세 편차의 합은 0이고 표준편차는 약 16.33입니다.`;
  }

  function renderDenominator() {
    const stats = describe(prices, denominator);
    document.querySelectorAll('#sd-denoms [data-denominator]').forEach((node) => {
      const on = node.dataset.denominator === denominator;
      node.setAttribute('stroke', on ? '#d97706' : '#64748b');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('[data-denominator-choice]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.denominatorChoice === denominator ? 'true' : 'false');
    });
    const purpose = denominator === 'n'
      ? '관측한 30건 자체의 퍼짐을 요약합니다.'
      : '같은 30건으로 모집단 분산을 추정할 때 쓰는 분모입니다. 한 건을 뺀 것이 아닙니다.';
    document.getElementById('sd-denom-status').textContent =
      `관측 30건, 합계 4,390, 평균 ${money(stats.mean)}, 제곱편차 합 ${money(stats.ss)}. 분모 ${stats.divisor}, 분산 ${money(stats.variance)}, 표준편차 ${money(stats.sd)}만원/㎡. ${purpose}`;
  }

  function renderInclusion() {
    const values = inclusion === 'drop' ? without : prices;
    const stats = describe(values, 'n');
    document.querySelectorAll('#sd-extreme [data-count]').forEach((node) => {
      const on = (inclusion === 'drop' ? '29' : '30') === node.dataset.count;
      node.setAttribute('stroke', on ? '#d97706' : '#64748b');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('[data-inclusion]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.inclusion === inclusion ? 'true' : 'false');
    });
    const note = inclusion === 'drop'
      ? '7번 480을 빼고 남은 29건의 평균으로 제곱편차를 다시 계산했습니다. 그림 3처럼 분모만 바꾼 것이 아닙니다.'
      : '7번을 포함한 30건입니다. 표준편차가 크다는 이유만으로 이 거래를 지우지는 않습니다.';
    document.getElementById('sd-extreme-status').textContent =
      `${stats.n}건, 단가 합계 ${money(stats.sum).replace('.00', '')}, 평균 ${money(stats.mean)}, 제곱편차 합 ${money(stats.ss)}, n 방식 분산 ${money(stats.variance)}, 표준편차 ${money(stats.sd)}만원/㎡. ${note}`;
  }

  function renderScale() {
    const sets = {
      base: [80, 100, 120],
      plus: [180, 200, 220],
      double: [160, 200, 240],
    };
    const stats = describe(sets[scale], 'n');
    document.querySelectorAll('[data-scale]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.scale === scale ? 'true' : 'false');
    });
    const note = scale === 'plus'
      ? '모든 값에 100을 더해도 편차는 그대로라 표준편차가 유지됩니다.'
      : scale === 'double'
        ? '모든 값을 두 배로 하면 표준편차는 두 배, 분산은 네 배입니다.'
        : '기준 자료입니다. 절댓값의 평균은 약 13.33이고 표준편차와 다릅니다.';
    document.getElementById('sd-scale-status').textContent =
      `${sets[scale].join(', ')}. 평균 ${money(stats.mean)}, 분산 ${money(stats.variance)} (만원/㎡)², 표준편차 ${money(stats.sd)}만원/㎡. ${note}`;
  }

  document.querySelectorAll('[data-spread-group]').forEach((button) => {
    button.addEventListener('click', () => { group = button.dataset.spreadGroup; renderGroups(); });
  });
  document.querySelectorAll('[data-point]').forEach((button) => {
    button.addEventListener('click', () => { point = Number(button.dataset.point); renderPoint(); });
  });
  document.querySelectorAll('#sd-deviations [data-price]').forEach((node) => {
    node.addEventListener('click', () => { point = Number(node.dataset.price); renderPoint(); });
  });
  document.querySelectorAll('[data-square]').forEach((button) => {
    button.addEventListener('click', () => { square = button.dataset.square === 'yes'; renderPoint(); });
  });
  document.querySelectorAll('[data-denominator-choice]').forEach((button) => {
    button.addEventListener('click', () => { denominator = button.dataset.denominatorChoice; renderDenominator(); });
  });
  document.querySelectorAll('[data-inclusion]').forEach((button) => {
    button.addEventListener('click', () => { inclusion = button.dataset.inclusion; renderInclusion(); });
  });
  document.querySelectorAll('[data-scale]').forEach((button) => {
    button.addEventListener('click', () => { scale = button.dataset.scale; renderScale(); });
  });
  document.querySelectorAll('.sd-controls').forEach((node) => node.removeAttribute('hidden'));
  renderGroups();
  renderPoint();
  renderDenominator();
  renderInclusion();
  renderScale();
}
