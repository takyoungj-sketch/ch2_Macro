export function medianOf(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) return sorted[mid];
  return (sorted[mid - 1] + sorted[mid]) / 2;
}

export function halves(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const n = sorted.length;
  return {
    q1: medianOf(sorted.slice(0, Math.floor(n / 2))),
    q2: medianOf(sorted),
    q3: medianOf(sorted.slice(Math.floor((n + 1) / 2))),
  };
}

export function type7(values, p) {
  const sorted = [...values].sort((a, b) => a - b);
  const h = (sorted.length - 1) * p;
  const j = Math.floor(h);
  const next = sorted[Math.min(j + 1, sorted.length - 1)];
  return sorted[j] + (h - j) * (next - sorted[j]);
}

export function fenceEnds(values, quartiles) {
  const iqr = quartiles.q3 - quartiles.q1;
  const low = quartiles.q1 - 1.5 * iqr;
  const high = quartiles.q3 + 1.5 * iqr;
  const inside = values.filter((value) => value >= low && value <= high);
  const outliers = values.filter((value) => value < low || value > high);
  return {
    iqr,
    low,
    high,
    whiskerLow: Math.min(...inside),
    whiskerHigh: Math.max(...inside),
    outliers,
  };
}

if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('qn-data').textContent);
  const prices = data.rows.map((row) => row.price);
  let ratio = 0.5;
  let step = 'all';
  let method = 'halves';
  let rule = 'iqr';
  let part = 'fence-high';
  let group = '주거';

  function money(value) {
    const rounded = Math.round(value * 100) / 100;
    return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(2);
  }

  function currentQuartiles() {
    if (method === 'type7') {
      return { q1: type7(prices, 0.25), q2: type7(prices, 0.5), q3: type7(prices, 0.75) };
    }
    return halves(prices);
  }

  function renderMap() {
    document.querySelectorAll('#qn-map [data-p]').forEach((node) => {
      const on = Number(node.dataset.p) === ratio;
      node.setAttribute('stroke', on ? '#d97706' : '#64748b');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('[data-ratio]').forEach((button) => {
      button.setAttribute('aria-pressed', Number(button.dataset.ratio) === ratio ? 'true' : 'false');
    });
    const names = { 0.25: '25% 위치는 Q1, 제1사분위수입니다.', 0.5: '50% 위치는 Q2, 중앙값입니다.', 0.75: '75% 위치는 Q3, 제3사분위수입니다.' };
    document.getElementById('qn-map-status').textContent =
      `${names[ratio]} 이 눈금의 간격은 누적 비율입니다. 단가의 간격이 아니고, 평균보다 그 비율만큼 높다는 뜻도 아닙니다.`;
  }

  function renderRanks() {
    document.querySelectorAll('#qn-ranks [data-rank]').forEach((node) => {
      const rank = Number(node.dataset.rank);
      let on = false;
      if (step === 'all') on = rank === 8 || rank === 15 || rank === 16 || rank === 23;
      if (step === 'center') on = rank === 15 || rank === 16;
      if (step === 'lower') on = rank <= 15;
      if (step === 'q1') on = rank === 8;
      if (step === 'upper') on = rank >= 16;
      if (step === 'q3') on = rank === 23;
      node.setAttribute('fill', on ? '#fff7ed' : '#f1f5f9');
      node.setAttribute('stroke', on ? '#d97706' : '#94a3b8');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('[data-step]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.step === step ? 'true' : 'false');
    });
    const copy = {
      all: '두 절반 방식의 결과입니다. Q1은 8번째 98, 중앙값은 (120+124)/2=122, Q3는 23번째 168입니다.',
      center: '30건의 가운데는 15번째 120과 16번째 124입니다. 중앙값은 그 평균인 122입니다.',
      lower: '아래쪽 15건은 1번째부터 15번째입니다. 그 가운데인 8번째가 Q1입니다.',
      q1: '8번째 단가는 98만원/㎡입니다. 98 이하인 관측은 8건이며, 30의 25%인 7.5건이 아닙니다.',
      upper: '위쪽 15건은 16번째부터 30번째입니다. 그 가운데인 23번째가 Q3입니다.',
      q3: '23번째 단가는 168만원/㎡입니다. 98 이상 168 이하인 관측은 16건입니다. 상자는 가운데 부분의 위치를 요약합니다.',
    };
    document.getElementById('qn-rank-status').textContent = copy[step];
  }

  function renderMethod() {
    const quartiles = currentQuartiles();
    const ends = fenceEnds(prices, quartiles);
    const box = document.querySelector('#qn-whiskers [data-box="iqr"]');
    box.setAttribute('x', String(60 + quartiles.q1));
    box.setAttribute('width', String(quartiles.q3 - quartiles.q1));
    const medianLine = document.getElementById('qn-iqr-median');
    medianLine.setAttribute('x1', String(60 + quartiles.q2));
    medianLine.setAttribute('x2', String(60 + quartiles.q2));
    const whisker = document.getElementById('qn-iqr-whisker');
    whisker.setAttribute('x1', String(60 + ends.whiskerLow));
    whisker.setAttribute('x2', String(60 + ends.whiskerHigh));
    const lowCap = document.querySelector('#qn-whiskers [data-cap="low"]');
    const highCap = document.querySelector('#qn-whiskers [data-cap="high"]');
    lowCap.setAttribute('x1', String(60 + ends.whiskerLow));
    lowCap.setAttribute('x2', String(60 + ends.whiskerLow));
    highCap.setAttribute('x1', String(60 + ends.whiskerHigh));
    highCap.setAttribute('x2', String(60 + ends.whiskerHigh));
    document.getElementById('qn-fence-low').setAttribute('x1', String(60 + ends.low));
    document.getElementById('qn-fence-low').setAttribute('x2', String(60 + ends.low));
    document.getElementById('qn-fence-high').setAttribute('x1', String(60 + ends.high));
    document.getElementById('qn-fence-high').setAttribute('x2', String(60 + ends.high));
    document.querySelectorAll('#qn-whiskers [data-outlier]').forEach((node) => {
      const value = Number(node.dataset.outlier);
      node.setAttribute('opacity', ends.outliers.includes(value) ? '1' : '0');
    });
    document.querySelectorAll('#qn-methods [data-method-row]').forEach((node) => {
      const on = node.dataset.methodRow === method;
      node.setAttribute('stroke', on ? '#d97706' : '#64748b');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('[data-method]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.method === method ? 'true' : 'false');
    });
    document.querySelectorAll('#qn-whiskers [data-rule-row]').forEach((node) => {
      node.setAttribute('opacity', node.dataset.ruleRow === rule ? '1' : '0.35');
    });
    document.querySelectorAll('[data-rule]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.rule === rule ? 'true' : 'false');
    });
    const outlierIds = data.rows.filter((row) => ends.outliers.includes(row.price)).map((row) => `${row.id}번 ${row.price}`);
    const methodName = method === 'type7' ? 'Type 7' : '두 절반 방식';
    document.getElementById('qn-method-status').textContent =
      `${methodName} · Q1 ${money(quartiles.q1)} · 중앙값 ${money(quartiles.q2)} · Q3 ${money(quartiles.q3)} · IQR ${money(ends.iqr)} · 울타리 ${money(ends.low)}와 ${money(ends.high)} · 수염 ${money(ends.whiskerLow)}와 ${money(ends.whiskerHigh)} · 울타리 밖 ${outlierIds.join(', ') || '없음'}. 같은 30건입니다.`;
    const partCopy = {
      q1: `Q1은 ${money(quartiles.q1)}만원/㎡입니다. 상자의 시작입니다.`,
      median: `중앙값은 ${money(quartiles.q2)}만원/㎡입니다. 상자 한가운데에 있지 않을 수 있습니다.`,
      q3: `Q3는 ${money(quartiles.q3)}만원/㎡입니다. 상자의 끝입니다.`,
      iqr: `IQR은 ${money(quartiles.q3)}−${money(quartiles.q1)}=${money(ends.iqr)}입니다. 가운데 부분의 너비입니다.`,
      'fence-low': `아래 울타리는 ${money(ends.low)}입니다. 계산된 경계이며 관측된 단가가 아닙니다.`,
      'fence-high': `위 울타리는 ${money(ends.high)}입니다. 수염 끝 ${money(ends.whiskerHigh)}과 다른 값입니다.`,
      'whisker-low': `아래 수염은 울타리 안 실제 최솟값 ${money(ends.whiskerLow)}까지입니다.`,
      'whisker-high': `위 수염은 울타리 안 실제 최댓값 ${money(ends.whiskerHigh)}까지입니다. 울타리 ${money(ends.high)}까지 그리지 않습니다.`,
      outlier: `울타리 밖은 ${outlierIds.join(', ') || '없습니다'}. 별도 점이 입력 오류라는 뜻은 아닙니다.`,
    };
    const ruleNote = rule === 'range'
      ? ' 위 그림은 수염을 실제 최솟값 62와 최댓값 480까지 그립니다.'
      : ' 아래 그림은 1.5×IQR 규칙입니다. 점선이 울타리, 실선이 수염입니다.';
    document.getElementById('qn-whisker-status').textContent = `${partCopy[part]} ${methodName}.${ruleNote}`;
    document.querySelectorAll('[data-part]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.part === part ? 'true' : 'false');
    });
    const boxOn = part === 'q1' || part === 'q3' || part === 'iqr';
    box.setAttribute('stroke', boxOn ? '#d97706' : '#64748b');
    box.setAttribute('stroke-width', boxOn ? '3' : '1');
    medianLine.setAttribute('stroke', part === 'median' ? '#d97706' : '#64748b');
    medianLine.setAttribute('stroke-width', part === 'median' ? '3' : '3');
    whisker.setAttribute('stroke', part === 'whisker-low' || part === 'whisker-high' ? '#d97706' : '#64748b');
    document.getElementById('qn-fence-low').setAttribute('stroke', part === 'fence-low' ? '#d97706' : '#64748b');
    document.getElementById('qn-fence-high').setAttribute('stroke', part === 'fence-high' ? '#d97706' : '#64748b');
  }

  function renderGroup() {
    const rows = data.rows.filter((row) => row.group === group);
    const values = rows.map((row) => row.price);
    const quartiles = halves(values);
    const ends = fenceEnds(values, quartiles);
    document.querySelectorAll('#qn-groups [data-box]').forEach((node) => {
      const on = node.dataset.box === group;
      node.setAttribute('stroke', on ? '#d97706' : '#64748b');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('[data-group]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.group === group ? 'true' : 'false');
    });
    document.getElementById('qn-group-status').textContent =
      `${group} ${values.length}건 · 두 절반 방식 · Q1 ${money(quartiles.q1)} · 중앙값 ${money(quartiles.q2)} · Q3 ${money(quartiles.q3)} · IQR ${money(ends.iqr)} · 울타리 ${money(ends.low)}와 ${money(ends.high)} · 수염 ${money(ends.whiskerLow)}와 ${money(ends.whiskerHigh)} · 별도 점 ${ends.outliers.length}개. 전체 30건의 Q1·Q3를 이 집단에 그대로 쓰지 않습니다.`;
  }

  document.querySelectorAll('[data-ratio]').forEach((button) => {
    button.addEventListener('click', () => {
      ratio = Number(button.dataset.ratio);
      renderMap();
    });
  });
  document.querySelectorAll('[data-step]').forEach((button) => {
    button.addEventListener('click', () => {
      step = button.dataset.step;
      renderRanks();
    });
  });
  document.querySelectorAll('[data-method]').forEach((button) => {
    button.addEventListener('click', () => {
      method = button.dataset.method;
      renderMethod();
    });
  });
  document.querySelectorAll('[data-rule]').forEach((button) => {
    button.addEventListener('click', () => {
      rule = button.dataset.rule;
      renderMethod();
    });
  });
  document.querySelectorAll('[data-part]').forEach((button) => {
    button.addEventListener('click', () => {
      part = button.dataset.part;
      renderMethod();
    });
  });
  document.querySelectorAll('[data-group], #qn-groups [data-box]').forEach((node) => {
    node.addEventListener('click', () => {
      group = node.dataset.group || node.dataset.box;
      renderGroup();
    });
  });
  document.querySelectorAll('.qn-controls').forEach((node) => node.removeAttribute('hidden'));
  renderMap();
  renderRanks();
  renderMethod();
  renderGroup();
}
