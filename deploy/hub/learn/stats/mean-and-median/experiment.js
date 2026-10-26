export function medianOf(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) return sorted[mid];
  return (sorted[mid - 1] + sorted[mid]) / 2;
}

if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('mm-data').textContent);
  const rows = data.rows;
  const basePrices = rows.map((row) => row.price);
  const baseSum = basePrices.reduce((total, price) => total + price, 0);
  const baseMean = baseSum / basePrices.length;
  const baseMedian = medianOf(basePrices);
  const byId = new Map(rows.map((row) => [row.id, row]));
  let selectedId = 7;
  let showMean = true;
  let showMedian = true;
  let rankStep = 'median';
  let sensitivity = '480';
  let weightMode = 'trade';
  let poolMode = 'count';

  function money(value) {
    const rounded = Math.round(value * 100) / 100;
    return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(2);
  }

  function renderDots() {
    document.querySelectorAll('#mm-dots [data-observation]').forEach((node) => {
      const on = Number(node.dataset.observation) === selectedId;
      node.setAttribute('stroke', on ? '#d97706' : '#1e3a8a');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('#mm-dots [data-guide="mean"]').forEach((node) => {
      node.setAttribute('opacity', showMean ? '1' : '0');
    });
    document.querySelectorAll('#mm-dots [data-guide="median"]').forEach((node) => {
      node.setAttribute('opacity', showMedian ? '1' : '0');
    });
    document.querySelectorAll('[data-show]').forEach((button) => {
      const on = button.dataset.show === 'mean' ? showMean : showMedian;
      button.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    const row = byId.get(selectedId);
    const side = row.price > baseMean ? '평균보다 큽니다' : (row.price < baseMean ? '평균보다 작습니다' : '평균과 같습니다');
    document.getElementById('mm-dot-status').textContent =
      `${row.id}번 · 단가 ${row.price}만원/㎡ · 평균과의 차이 ${money(row.price - baseMean)} · 중앙값과의 차이 ${money(row.price - baseMedian)}. ${side}. 평균보다 작다는 말은 하위 절반이라는 뜻이 아닙니다. 점의 세로 위치는 겹침을 피한 자리입니다.`;
  }

  function renderRanks() {
    document.querySelectorAll('#mm-ranks [data-order]').forEach((node) => {
      const order = Number(node.dataset.order);
      const focus = rankStep !== 'sort' && (order === 15 || order === 16);
      node.setAttribute('fill', focus ? '#fff7ed' : '#93c5fd');
      node.setAttribute('stroke', focus ? '#d97706' : '#64748b');
      node.setAttribute('stroke-width', focus ? '3' : '1');
    });
    document.querySelectorAll('[data-rank-step]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.rankStep === rankStep ? 'true' : 'false');
    });
    const copy = {
      sort: '30개 단가를 작은 순서대로 놓았습니다. 가로 간격은 순서이며 단가의 실제 거리가 아닙니다.',
      center: '관측수가 짝수이므로 가운데는 15번째와 16번째 사이입니다. 15.5번째는 위치가 아니라 두 값의 평균을 쓸 자리입니다.',
      pair: `15번째 단가는 ${data.rank15}만원/㎡, 16번째 단가는 ${data.rank16}만원/㎡입니다.`,
      median: `중앙값 = (${data.rank15}+${data.rank16})/2 = ${data.median}만원/㎡. 이 값은 가운데 두 단가의 평균이며, 원자료에 같은 단가가 없어도 됩니다.`,
    };
    document.getElementById('mm-rank-status').textContent = copy[rankStep];
  }

  function scenarioPrices() {
    if (sensitivity === 'drop') return basePrices.filter((_, index) => rows[index].id !== 7);
    const replacement = Number(sensitivity);
    return rows.map((row) => (row.id === 7 ? replacement : row.price));
  }

  function renderSensitivity() {
    document.querySelectorAll('#mm-sensitivity circle').forEach((node) => {
      const on = sensitivity !== 'drop' && node.dataset.replacement === sensitivity;
      node.setAttribute('stroke', on ? '#d97706' : '#334155');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('[data-case]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.case === sensitivity ? 'true' : 'false');
    });
    const prices = scenarioPrices();
    const total = prices.reduce((sum, price) => sum + price, 0);
    const average = total / prices.length;
    const middle = medianOf(prices);
    const sorted = [...prices].sort((a, b) => a - b);
    const pair = prices.length % 2 === 0
      ? [sorted[prices.length / 2 - 1], sorted[prices.length / 2]]
      : [sorted[Math.floor(prices.length / 2)]];
    const basePair = [...basePrices].sort((a, b) => a - b);
    const samePair = pair.length === 2 && pair[0] === basePair[14] && pair[1] === basePair[15];
    let note = '';
    if (sensitivity === '900') {
      note = ` 7번 단가가 ${900 - 480} 증가하면서 평균은 ${money(average - baseMean)} 증가했습니다. ${samePair ? '정렬된 가운데 두 값은 그대로이므로 ' : ''}중앙값은 ${money(middle)}입니다.`;
    } else if (sensitivity === 'drop') {
      note = ' 관측수가 29건으로 줄면서 평균과 중앙값을 다시 계산했습니다. 이는 값을 바꾸는 것과 다른 처리입니다.';
    } else if (samePair) {
      note = ' 가운데 두 값은 그대로입니다.';
    }
    document.getElementById('mm-sens-status').textContent =
      `${sensitivity === 'drop' ? '7번 제외' : `7번 ${sensitivity}만원/㎡`} · ${prices.length}건 · 합계 ${total} · 평균 약 ${money(average)} · 중앙값 ${money(middle)}. 원자료는 바꾸지 않은 가상 계산입니다.${note}`;
  }

  function renderWeights() {
    const area = weightMode === 'area';
    const widths = area ? [30, 270] : [150, 150];
    const shares = area ? ['10%', '90%'] : ['50%', '50%'];
    document.querySelectorAll('#mm-weights [data-bar]').forEach((node) => {
      const index = Number(node.dataset.bar);
      node.setAttribute('width', String(widths[index]));
    });
    document.querySelectorAll('#mm-weights [data-share]').forEach((node) => {
      const index = Number(node.dataset.share);
      node.textContent = shares[index];
      node.setAttribute('x', String(36 + widths[index] + 8));
    });
    document.querySelectorAll('[data-weight]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.weight === weightMode ? 'true' : 'false');
    });
    document.getElementById('mm-weight-status').textContent = area
      ? '면적 비중: A 10㎡는 10%, B 90㎡는 90%. (10×200+90×100)/(10+90)=110만원/㎡. 전체 금액 11,000만원÷전체 면적 100㎡와 같습니다.'
      : '거래별 동일 비중: A 50%, B 50%. (200+100)/2=150만원/㎡. 거래 한 건을 같은 비중으로 본 값입니다.';
  }

  function renderPool() {
    const byCount = poolMode === 'count';
    const widths = byCount ? [28, 252] : [140, 140];
    const shares = byCount ? ['10%', '90%'] : ['50%', '50%'];
    document.querySelectorAll('#mm-pool [data-bar]').forEach((node) => {
      node.setAttribute('width', String(widths[Number(node.dataset.bar)]));
    });
    document.querySelectorAll('#mm-pool [data-share]').forEach((node) => {
      const index = Number(node.dataset.share);
      node.textContent = shares[index];
      node.setAttribute('x', String(36 + widths[index] + 8));
    });
    document.querySelectorAll('[data-pool]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.pool === poolMode ? 'true' : 'false');
    });
    document.getElementById('mm-pool-status').textContent = byCount
      ? '거래 한 건을 같은 비중으로 보면 A 10%, B 90%입니다. (10×100+90×200)/100=190만원/㎡. A 10건·B 90건은 고정된 가상 예제입니다.'
      : '집단 평균을 같은 비중으로 보면 A 50%, B 50%입니다. (100+200)/2=150만원/㎡. 거래 건수가 다른 전체 평균은 아닙니다.';
  }

  document.querySelectorAll('#mm-dots [data-observation]').forEach((node) => {
    node.addEventListener('click', () => {
      selectedId = Number(node.dataset.observation);
      if (selectedId === 7) sensitivity = '480';
      renderDots();
      renderSensitivity();
    });
  });
  document.querySelectorAll('[data-show]').forEach((button) => {
    button.addEventListener('click', () => {
      if (button.dataset.show === 'mean') showMean = !showMean;
      else showMedian = !showMedian;
      renderDots();
    });
  });
  document.querySelectorAll('[data-rank-step]').forEach((button) => {
    button.addEventListener('click', () => {
      rankStep = button.dataset.rankStep;
      renderRanks();
    });
  });
  document.querySelectorAll('#mm-ranks [data-order]').forEach((node) => {
    node.addEventListener('click', () => {
      const order = Number(node.dataset.order);
      rankStep = order === 15 || order === 16 ? 'pair' : 'sort';
      renderRanks();
    });
  });
  document.querySelectorAll('[data-case]').forEach((button) => {
    button.addEventListener('click', () => {
      sensitivity = button.dataset.case;
      renderSensitivity();
    });
  });
  document.querySelectorAll('[data-weight]').forEach((button) => {
    button.addEventListener('click', () => {
      weightMode = button.dataset.weight;
      renderWeights();
    });
  });
  document.querySelectorAll('[data-pool]').forEach((button) => {
    button.addEventListener('click', () => {
      poolMode = button.dataset.pool;
      renderPool();
    });
  });
  document.querySelectorAll('.mm-controls').forEach((node) => node.removeAttribute('hidden'));
  renderDots();
  renderRanks();
  renderSensitivity();
  renderWeights();
  renderPool();
}
