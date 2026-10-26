export function binCount(rows, low, width) {
  return rows.filter((row) => low <= row.price && row.price < low + width).length;
}

if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('grp-data').textContent);
  const byId = new Map(data.rows.map((row) => [row.id, row]));
  let frequency = 'count';
  let binWidth = 60;
  let binLow = 60;
  let shape = 'symmetric';
  let selectedId = 7;
  let group = 'all';
  let boxPart = 'extreme';

  const shapeCopy = {
    symmetric: '대칭에 가까운 분포는 가운데를 기준으로 양쪽 모양이 비슷합니다. 이 그림은 공통 30건의 밀도가 아닙니다.',
    right: '오른쪽 꼬리는 큰 값 쪽으로 드문 관측이 길게 이어진다는 뜻입니다. 관측 대부분이 오른쪽에 있다는 뜻이 아닙니다.',
    peaks: '봉우리가 여러 개이면 서로 다른 집단이 섞였을 가능성을 생각할 수 있습니다. 구간 폭과 표본 변동도 함께 봅니다. 시장이 둘로 나뉜다고 단정하지 않습니다.',
  };
  const boxCopy = {
    q1: 'Q1은 정렬한 30개를 아래 15개와 위 15개로 나눈 뒤, 아래 15개의 중앙값 98만원/㎡입니다.',
    median: '중앙값은 30개 전체의 중앙값 122만원/㎡입니다.',
    q3: 'Q3는 위 15개의 중앙값 168만원/㎡입니다.',
    iqr: 'IQR은 168−98=70만원/㎡입니다. 가운데 50%의 범위를 요약합니다.',
    low: '아래쪽 경계는 98−105=−7입니다. 수염은 그 안의 실제 최솟값 62만원/㎡까지 뻗습니다. 자료의 최솟값이 경계와 같다는 뜻은 아닙니다.',
    high: '위쪽 경계는 273이지만 수염은 경계 안의 실제 최댓값 268만원/㎡까지 뻗습니다. 최댓값이 268이라는 뜻은 아닙니다.',
    extreme: '480만원/㎡는 관측 7번, 상업, 면적 22㎡, 1층입니다. 위쪽 경계 273을 넘어 별도 점으로 표시합니다. 경계 밖이라는 표시가 입력 오류라는 뜻은 아닙니다.',
  };

  function renderFrequency() {
    const countMode = frequency === 'count';
    document.querySelectorAll('#grp-bars rect[data-bar]').forEach((node) => {
      node.setAttribute('width', countMode ? '180' : '180');
    });
    document.querySelectorAll('#grp-bars [data-freq-label]').forEach((node) => {
      node.textContent = countMode ? '15건' : '50%';
    });
    const tickText = countMode ? ['0', '5', '10', '15'] : ['0%', '25%', '50%', ''];
    const tickX = countMode ? [24, 84, 144, 204] : [24, 114, 204, 204];
    document.querySelectorAll('#grp-bars [data-freq-tick]').forEach((node) => {
      const index = Number(node.dataset.freqTick);
      node.textContent = tickText[index];
      node.setAttribute('x', String(tickX[index]));
    });
    const axis = document.getElementById('grp-freq-axis');
    axis.textContent = countMode ? '건수(건) · 0부터' : '비율(%) · 0부터';
    document.querySelectorAll('[data-freq]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.freq === frequency ? 'true' : 'false');
    });
    document.getElementById('grp-freq-status').textContent = countMode
      ? '주거 15건, 상업 15건, 합계 30건입니다. 건수가 같다고 단가나 면적 분포가 같은 것은 아닙니다.'
      : '주거 15/30=50%, 상업 15/30=50%, 합계 100%입니다. 이 비율은 학습 예제의 구성이며 실제 시장의 거래 비중이 아닙니다.';
  }

  function renderHistogram() {
    document.querySelectorAll('#grp-histogram rect[data-bin-width]').forEach((node) => {
      const onWidth = Number(node.dataset.binWidth) === binWidth;
      const onBin = onWidth && Number(node.dataset.low) === binLow;
      node.setAttribute('opacity', onWidth ? '1' : '0');
      node.setAttribute('pointer-events', onWidth ? 'auto' : 'none');
      node.setAttribute('stroke', onBin ? '#d97706' : '#64748b');
      node.setAttribute('stroke-width', onBin ? '3' : '1');
    });
    document.querySelectorAll('[data-width]').forEach((button) => {
      button.setAttribute('aria-pressed', Number(button.dataset.width) === binWidth ? 'true' : 'false');
    });
    const bins = data.bins[String(binWidth)];
    const tickNodes = document.querySelectorAll('#grp-histogram [data-hist-tick]');
    const tickLows = binWidth === 30 ? [60, 180, 300, 480] : [60, 180, 360, 480];
    tickNodes.forEach((node, index) => {
      const low = tickLows[index];
      node.textContent = String(low);
      node.setAttribute('x', String(70 + (low - 60) * 1.1));
    });
    const selected = bins.find((bin) => bin.low === binLow) || bins[0];
    binLow = selected.low;
    const ids = selected.ids.join(', ');
    const merged = binWidth === 120 && selected.low === 60
      ? ' 폭 60의 14건과 10건을 합쳐 24건으로 표시했습니다. 새 거래가 추가된 것은 아니며 전체는 여전히 30건입니다.'
      : '';
    document.getElementById('grp-histogram-status').textContent =
      `구간 폭 ${binWidth}만원/㎡ · ${selected.low} 이상 ${selected.high} 미만 · ${selected.count}건 · 번호 ${ids || '없음'}. 왼쪽 포함, 오른쪽 제외입니다. 모든 구간의 합은 30건입니다.${merged}`;
  }

  function renderShape() {
    document.querySelectorAll('#grp-shapes [data-shape]').forEach((node) => {
      const on = node.dataset.shape === shape;
      if (node.dataset.role === 'card') {
        node.setAttribute('fill', on ? '#fff7ed' : '#ffffff');
        node.setAttribute('stroke', on ? '#d97706' : '#94a3b8');
        node.setAttribute('stroke-width', on ? '3' : '1');
      }
    });
    document.querySelectorAll('[data-shape-button]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.shapeButton === shape ? 'true' : 'false');
    });
    document.getElementById('grp-shape-status').textContent = shapeCopy[shape];
  }

  function renderScatter() {
    document.querySelectorAll('#grp-scatter [data-observation]').forEach((node) => {
      const row = byId.get(Number(node.dataset.observation));
      const visible = group === 'all' || row.group === group;
      const on = Number(node.dataset.observation) === selectedId;
      node.setAttribute('opacity', visible ? '1' : '0.15');
      node.setAttribute('stroke', on ? '#d97706' : '#1e3a8a');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('[data-group]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.group === group ? 'true' : 'false');
    });
    const row = byId.get(selectedId);
    const input = document.getElementById('grp-id');
    if (document.activeElement !== input) input.value = String(selectedId);
    const hidden = group !== 'all' && row.group !== group;
    document.getElementById('grp-scatter-status').textContent =
      `${selectedId}번 · ${row.group} · 면적 ${row.area}㎡ · ${row.floor}층 · 단가 ${row.price}만원/㎡. 좌표 (${row.area}, ${row.price}). ${hidden ? '이 유형은 지금 흐리게 표시됩니다. ' : ''}화면에 점을 겹쳐 세지 않고, 전체는 30건입니다. 번호는 거래 시점이 아닙니다.`;
  }

  function renderBox() {
    document.querySelectorAll('#grp-box [data-part]').forEach((node) => {
      const on = node.dataset.part === boxPart;
      node.setAttribute('stroke', on ? '#d97706' : (node.dataset.part === 'median' ? '#1d4ed8' : '#475569'));
      node.setAttribute('stroke-width', on ? '4' : (node.dataset.part === 'median' ? '3' : '1'));
    });
    document.querySelectorAll('[data-box]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.box === boxPart ? 'true' : 'false');
    });
    document.getElementById('grp-box-status').textContent = boxCopy[boxPart] || '상자, 수염, 480 점을 선택할 수 있습니다.';
  }

  function render() {
    renderFrequency();
    renderHistogram();
    renderShape();
    renderScatter();
    renderBox();
  }

  document.querySelectorAll('[data-freq]').forEach((button) => {
    button.addEventListener('click', () => {
      frequency = button.dataset.freq;
      renderFrequency();
    });
  });
  document.querySelectorAll('[data-width]').forEach((button) => {
    button.addEventListener('click', () => {
      binWidth = Number(button.dataset.width);
      binLow = data.bins[String(binWidth)][0].low;
      renderHistogram();
    });
  });
  document.querySelectorAll('#grp-histogram rect[data-bin-width]').forEach((node) => {
    node.addEventListener('click', () => {
      binWidth = Number(node.dataset.binWidth);
      binLow = Number(node.dataset.low);
      renderHistogram();
    });
  });
  document.querySelectorAll('[data-shape-button], #grp-shapes [data-role=card]').forEach((node) => {
    node.addEventListener('click', () => {
      shape = node.dataset.shapeButton || node.dataset.shape;
      renderShape();
    });
  });
  document.querySelectorAll('[data-group]').forEach((button) => {
    button.addEventListener('click', () => {
      group = button.dataset.group;
      renderScatter();
    });
  });
  document.querySelectorAll('#grp-scatter [data-observation]').forEach((node) => {
    node.addEventListener('click', () => {
      selectedId = Number(node.dataset.observation);
      boxPart = selectedId === 7 ? 'extreme' : '';
      renderScatter();
      renderBox();
    });
  });
  document.getElementById('grp-id').addEventListener('input', (event) => {
    const value = Number(event.target.value);
    if (!byId.has(value)) return;
    selectedId = value;
    boxPart = selectedId === 7 ? 'extreme' : '';
    renderScatter();
    renderBox();
  });
  document.querySelectorAll('[data-box], #grp-box [data-part]').forEach((node) => {
    node.addEventListener('click', () => {
      boxPart = node.dataset.box || node.dataset.part;
      if (boxPart === 'extreme') selectedId = 7;
      renderBox();
      renderScatter();
    });
  });
  document.querySelectorAll('.grp-controls').forEach((node) => node.removeAttribute('hidden'));
  render();
}
