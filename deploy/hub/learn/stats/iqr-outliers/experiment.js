export function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

export function halves(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const n = sorted.length;
  return {
    q1: median(sorted.slice(0, Math.floor(n / 2))),
    q2: median(sorted),
    q3: median(sorted.slice(Math.floor((n + 1) / 2))),
  };
}

export function type7(values, p) {
  const sorted = [...values].sort((a, b) => a - b);
  const h = (sorted.length - 1) * p;
  const j = Math.floor(h);
  return sorted[j] + (h - j) * (sorted[Math.min(j + 1, sorted.length - 1)] - sorted[j]);
}

export function fence(values, method, k) {
  const quartiles = method === 'type7'
    ? { q1: type7(values, 0.25), q2: type7(values, 0.5), q3: type7(values, 0.75) }
    : halves(values);
  const iqr = quartiles.q3 - quartiles.q1;
  const lo = quartiles.q1 - k * iqr;
  const hi = quartiles.q3 + k * iqr;
  const inside = values.filter((value) => value >= lo && value <= hi);
  const candidates = values.filter((value) => value < lo || value > hi);
  return { ...quartiles, iqr, lo, hi, inside, candidates, whiskerLo: Math.min(...inside), whiskerHi: Math.max(...inside) };
}

if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('iq-data').textContent);
  const prices = data.rows.map((row) => row.price);
  const byScope = {
    전체: prices,
    주거: data.rows.filter((row) => row.group === '주거').map((row) => row.price),
    상업: data.rows.filter((row) => row.group === '상업').map((row) => row.price),
  };
  let method = 'halves';
  let multiplier = 1.5;
  let scope = '전체';
  let part = 'fence';
  let inclusion = 'all';
  let adjustment = 'raw';

  function num(value) {
    const rounded = Math.round(value * 100) / 100;
    return rounded.toLocaleString('ko-KR', { maximumFractionDigits: 2 });
  }

  function names(list) {
    const wanted = new Set(list);
    return data.rows
      .filter((row) => wanted.has(row.price) && list.includes(row.price))
      .map((row) => `${row.id}번 ${num(row.price)}`)
      .join(', ');
  }

  function renderPart() {
    const stats = fence(prices, method, multiplier);
    const x = (value) => 110 + value * 0.95;
    const move = (id, value) => {
      const node = document.getElementById(id);
      node.setAttribute('x1', x(value));
      node.setAttribute('x2', x(value));
    };
    move('iq-fence-lo', stats.lo);
    move('iq-fence-hi', stats.hi);
    move('iq-whisker-lo', stats.whiskerLo);
    move('iq-whisker-hi', stats.whiskerHi);
    const span = document.getElementById('iq-whisker-span');
    span.setAttribute('x1', x(stats.whiskerLo));
    span.setAttribute('x2', x(stats.whiskerHi));
    move('iq-q1', stats.q1);
    move('iq-q3', stats.q3);
    move('iq-median', stats.q2);
    document.getElementById('iq-label-lo').setAttribute('x', Math.max(36, x(stats.lo)));
    document.getElementById('iq-label-hi').setAttribute('x', Math.min(600, x(stats.hi)));
    document.getElementById('iq-label-lo').textContent = `하한 ${num(stats.lo)}`;
    document.getElementById('iq-label-hi').textContent = `상한 ${num(stats.hi)}`;
    document.getElementById('iq-label-wlo').setAttribute('x', x(stats.whiskerLo));
    document.getElementById('iq-label-whi').setAttribute('x', x(stats.whiskerHi));
    document.getElementById('iq-label-wlo').textContent = `수염 ${num(stats.whiskerLo)}`;
    document.getElementById('iq-label-whi').textContent = `수염 ${num(stats.whiskerHi)}`;
    document.getElementById('iq-p268').setAttribute('fill', stats.candidates.includes(268) ? '#d97706' : '#2563eb');
    document.getElementById('iq-p480').setAttribute('fill', stats.candidates.includes(480) ? '#d97706' : '#2563eb');
    const box = document.getElementById('iq-box');
    box.setAttribute('x', x(stats.q1));
    box.setAttribute('width', x(stats.q3) - x(stats.q1));
    const marks = {
      q1: ['iq-q1'],
      median: ['iq-median'],
      q3: ['iq-q3'],
      iqr: ['iq-box'],
      fence: ['iq-fence-lo', 'iq-fence-hi'],
      whisker: ['iq-whisker-lo', 'iq-whisker-hi'],
      p268: ['iq-p268'],
      p480: ['iq-p480'],
    };
    document.querySelectorAll('#fences [data-part]').forEach((node) => {
      const on = (marks[part] || []).includes(node.id);
      node.setAttribute('stroke', on ? '#d97706' : '#64748b');
      node.setAttribute('stroke-width', on ? '3' : '1.5');
    });
    document.querySelectorAll('[data-part-choice]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.partChoice === part ? 'true' : 'false');
    });
    const text = {
      q1: `Q1은 ${num(stats.q1)}만원/㎡입니다. 상자의 왼쪽 끝입니다.`,
      median: `중앙값은 ${num(stats.q2)}만원/㎡입니다.`,
      q3: `Q3는 ${num(stats.q3)}만원/㎡입니다. 상자의 오른쪽 끝입니다.`,
      iqr: `IQR은 ${num(stats.iqr)}만원/㎡입니다. Q3에서 Q1을 뺀 값입니다.`,
      fence: `하한 ${num(stats.lo)}, 상한 ${num(stats.hi)}입니다. 점선이며 음수 하한은 계산된 경계입니다. 경계와 같은 값은 후보가 아닙니다.`,
      whisker: `수염은 울타리 안의 실제 값인 ${num(stats.whiskerLo)}과 ${num(stats.whiskerHi)}까지입니다. 울타리 끝까지 그리지 않습니다.`,
      p268: `24번 268은 이번 조건에서 ${stats.candidates.includes(268) ? '상한 밖 후보' : '울타리 안'}입니다.`,
      p480: `7번 480은 상한 ${num(stats.hi)}보다 커서 후보입니다. 후보라는 사실만으로 입력 오류는 아닙니다.`,
    };
    document.getElementById('iq-part-status').textContent = text[part];
    document.getElementById('fences-caption').textContent =
      `그림 1. 공통 30건, ${method === 'halves' ? '두 절반' : 'Type 7'}, k=${num(multiplier)}. 울타리 ${num(stats.lo)}·${num(stats.hi)}, 수염 ${num(stats.whiskerLo)}·${num(stats.whiskerHi)}. 음수 하한은 관측된 단가가 아닙니다.`;
  }

  function renderMultiplier() {
    const stats = fence(prices, method, multiplier);
    document.querySelectorAll('#multipliers [data-k]').forEach((node) => {
      const on = method === 'halves' && Number(node.dataset.k) === multiplier;
      node.setAttribute('stroke', on ? '#d97706' : '#64748b');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('#multipliers [data-rule="type7"]').forEach((node) => {
      node.setAttribute('visibility', method === 'type7' ? 'visible' : 'hidden');
      const on = Number(node.dataset.multiple) === multiplier;
      if (node.tagName === 'rect') {
        node.setAttribute('stroke', on ? '#d97706' : '#64748b');
        node.setAttribute('stroke-width', on ? '3' : '1');
      }
    });
    document.querySelectorAll('#multipliers [data-rule="halves"]').forEach((node) => {
      node.setAttribute('opacity', method === 'halves' ? '1' : '0');
    });
    document.querySelectorAll('[data-method-choice]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.methodChoice === method ? 'true' : 'false');
    });
    document.querySelectorAll('[data-k-choice]').forEach((button) => {
      button.setAttribute('aria-pressed', Number(button.dataset.kChoice) === multiplier ? 'true' : 'false');
    });
    const who = stats.candidates.length ? names(stats.candidates) : '없음';
    document.getElementById('iq-k-status').textContent =
      `${method === 'halves' ? '두 절반' : 'Type 7'}, k=${num(multiplier)}. Q1 ${num(stats.q1)}, Q3 ${num(stats.q3)}, IQR ${num(stats.iqr)}. 하한 ${num(stats.lo)}, 상한 ${num(stats.hi)}. 후보 ${stats.candidates.length}건: ${who}. 포함 ${prices.length - stats.candidates.length}건. 자료와 분위수를 고정한 채 배수만 키우면 후보는 줄거나 그대로입니다.`;
    document.getElementById('multipliers-caption').textContent =
      `그림 2. 지금 보이는 울타리는 ${method === 'halves' ? '두 절반' : 'Type 7'}입니다. 자료는 30건 그대로이고, 선택한 배수는 ${num(multiplier)}입니다.`;
  }

  function renderScope() {
    const values = byScope[scope];
    const stats = fence(values, method, multiplier);
    document.querySelectorAll('#group-fences [data-group]').forEach((node) => {
      const own = fence(byScope[node.dataset.group], method, multiplier);
      node.setAttribute('x', 90 + own.q1);
      node.setAttribute('width', own.q3 - own.q1);
      const line = document.getElementById(`iq-fence-${node.dataset.group}`);
      const at = Math.min(620, 90 + own.hi);
      line.setAttribute('x1', at);
      line.setAttribute('x2', at);
      document.getElementById(`iq-scope-${node.dataset.group}`).textContent =
        `${node.dataset.group} ${byScope[node.dataset.group].length}건 · Q1 ${num(own.q1)}, Q3 ${num(own.q3)}, 상한 ${num(own.hi)}`;
    });
    document.querySelectorAll('#group-fences [data-scope]').forEach((node) => {
      const on = node.dataset.scope === scope;
      const own = fence(byScope[node.dataset.scope], method, multiplier);
      node.setAttribute('opacity', on ? '1' : '0.25');
      if (node.tagName === 'circle') {
        const out = own.candidates.includes(Number(node.dataset.price));
        node.setAttribute('fill', out ? '#d97706' : '#2563eb');
        node.setAttribute('stroke', on && out ? '#d97706' : '#1e3a8a');
      }
    });
    document.querySelectorAll('#group-fences [data-group]').forEach((node) => {
      const on = node.dataset.group === scope;
      node.setAttribute('stroke', on ? '#d97706' : '#64748b');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('[data-scope-choice]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.scopeChoice === scope ? 'true' : 'false');
    });
    const who = stats.candidates.length ? names(stats.candidates) : '없음';
    document.getElementById('iq-group-status').textContent =
      `${scope} ${values.length}건을 ${method === 'halves' ? '두 절반' : 'Type 7'}과 k=${num(multiplier)}로 다시 계산했습니다. Q1 ${num(stats.q1)}, Q3 ${num(stats.q3)}, IQR ${num(stats.iqr)}, 상한 ${num(stats.hi)}. 후보 ${stats.candidates.length}건: ${who}. 전체 울타리를 하위 집단에 그대로 씌우지 않았습니다. 그림 1의 30건은 그대로입니다.`;
    document.getElementById('group-fences-caption').textContent =
      `그림 3. ${method === 'halves' ? '두 절반' : 'Type 7'}, k=${num(multiplier)}. 선택한 ${scope}의 상한은 ${num(stats.hi)}입니다. 각 집단의 사분위수는 그 집단에서 다시 계산합니다.`;
  }

  function renderInclusion() {
    const values = inclusion === 'drop' ? prices.filter((_, index) => data.rows[index].id !== 7) : prices;
    const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
    const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
    const middle = median(values);
    document.querySelectorAll('#iq-sensitivity [data-series]').forEach((node) => {
      const on = node.dataset.series === (inclusion === 'drop' ? 'without' : 'all');
      node.setAttribute('stroke', on ? '#d97706' : '#64748b');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('[data-inclusion]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.inclusion === inclusion ? 'true' : 'false');
    });
    const note = inclusion === 'drop'
      ? '남은 29건의 평균으로 표준편차를 다시 계산했습니다. 표준편차가 줄었다고 결과가 더 정확한 것은 아닙니다. 그림 1~3의 원자료는 바꾸지 않습니다.'
      : '7번 480을 포함한 30건입니다. 제외 여부는 이 비교만으로 정하지 않습니다.';
    document.getElementById('iq-drop-status').textContent =
      `${values.length}건, 합계 ${num(values.reduce((sum, value) => sum + value, 0))}, 평균 ${num(mean)}, 중앙값 ${num(middle)}, n 방식 표준편차 ${num(Math.sqrt(variance))}만원/㎡. ${note}`;
  }

  function renderAdjustment() {
    const replaced = prices.map((value, index) => (data.rows[index].id === 7 ? 273 : value));
    const chosen = adjustment === 'drop' ? prices.filter((_, index) => data.rows[index].id !== 7) : adjustment === 'winsor' ? replaced : prices;
    const mean = chosen.reduce((sum, value) => sum + value, 0) / chosen.length;
    document.querySelectorAll('[data-adjustment]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.adjustment === adjustment ? 'true' : 'false');
    });
    const note = adjustment === 'winsor'
      ? '273은 교육용 대체값이며 새 거래단가가 아닙니다. 관측수는 30건입니다.'
      : adjustment === 'drop'
        ? '절사는 그 관측을 분석 건수에서 빼는 예입니다.'
        : '원자료 480을 유지합니다.';
    document.getElementById('iq-adjust-status').textContent =
      `${chosen.length}건, 합계 ${num(chosen.reduce((sum, value) => sum + value, 0))}, 평균 ${num(mean)}만원/㎡. ${note}`;
  }

  document.querySelectorAll('[data-part-choice]').forEach((button) => {
    button.addEventListener('click', () => { part = button.dataset.partChoice; renderPart(); });
  });
  document.querySelectorAll('#fences [data-part]').forEach((node) => {
    node.addEventListener('click', () => { part = node.dataset.part; renderPart(); });
  });
  document.querySelectorAll('[data-method-choice]').forEach((button) => {
    button.addEventListener('click', () => { method = button.dataset.methodChoice; renderPart(); renderMultiplier(); renderScope(); });
  });
  document.querySelectorAll('[data-k-choice]').forEach((button) => {
    button.addEventListener('click', () => { multiplier = Number(button.dataset.kChoice); renderPart(); renderMultiplier(); renderScope(); });
  });
  document.querySelectorAll('[data-scope-choice]').forEach((button) => {
    button.addEventListener('click', () => { scope = button.dataset.scopeChoice; renderScope(); });
  });
  document.querySelectorAll('[data-inclusion]').forEach((button) => {
    button.addEventListener('click', () => { inclusion = button.dataset.inclusion; renderInclusion(); });
  });
  document.querySelectorAll('[data-adjustment]').forEach((button) => {
    button.addEventListener('click', () => { adjustment = button.dataset.adjustment; renderAdjustment(); });
  });
  document.querySelectorAll('.iq-controls').forEach((node) => node.removeAttribute('hidden'));
  renderPart();
  renderMultiplier();
  renderScope();
  renderInclusion();
  renderAdjustment();
}
