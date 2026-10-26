export function share(count, total) {
  return count / total;
}

export function meanOf(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('var-data').textContent);
  const byId = new Map(data.rows.map((row) => [row.id, row]));
  let selectedId = 7;
  let column = 'area';
  let frequency = 'count';
  let missingMode = 'drop';

  const columns = {
    id: '관측번호는 행을 구별하는 식별자입니다. 거래 시점이 아니고, 번호가 크다고 면적이나 단가가 큰 것도 아닙니다.',
    group: '구분은 범주형 변수입니다. 주거와 상업의 종류를 나타냅니다.',
    area: '면적은 수치형 측정값이며 단위는 ㎡입니다. 정수로 적혀도 거래 건수처럼 하나씩 세는 값은 아닙니다.',
    floor: '층은 숫자로 기록된 층 정보입니다. 층 번호의 차이가 실제 높이와 같다고 보지 않습니다.',
    price: '단가는 수치형 변수이며 단위는 만원/㎡입니다.',
  };

  function renderSheet() {
    document.querySelectorAll('#sheet [data-id]').forEach((node) => {
      const on = Number(node.dataset.id) === selectedId;
      node.setAttribute('fill', on ? '#fff7ed' : '#ffffff');
      node.setAttribute('stroke', on ? '#d97706' : '#94a3b8');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('#sheet [data-col]').forEach((node) => {
      const on = node.dataset.col === column;
      node.setAttribute('stroke', on ? '#d97706' : '#94a3b8');
    });
    document.querySelectorAll('[data-row-button]').forEach((button) => {
      button.setAttribute('aria-pressed', Number(button.dataset.rowButton) === selectedId ? 'true' : 'false');
    });
    document.querySelectorAll('[data-col-button]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.colButton === column ? 'true' : 'false');
    });
    const row = byId.get(selectedId);
    const shown = data.preview.includes(selectedId);
    const place = shown
      ? '이 행은 그림 1에 표시된 3건 가운데 하나입니다.'
      : '이 관측은 그림 1의 기본 3행 밖입니다. 산점도의 점과 이 설명에서 확인합니다.';
    document.getElementById('var-row-status').textContent =
      `관측 ${row.id}. 한 건의 학습용 거래 기록. 구분 ${row.group}, 면적 ${row.area}㎡, 층 ${row.floor}, 단가 ${row.price}만원/㎡. ${place} 선택한 열: ${columns[column]}`;
    const input = document.querySelector('.var-id');
    if (input && document.activeElement !== input) input.value = String(selectedId);
  }

  function renderPoint() {
    document.querySelectorAll('#scatter circle').forEach((node) => {
      const on = Number(node.dataset.id) === selectedId;
      node.setAttribute('fill', on ? '#d97706' : '#2563eb');
      node.setAttribute('stroke', on ? '#d97706' : '#1e3a8a');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    renderSheet();
  }

  function renderFrequency() {
    const countMode = frequency === 'count';
    data.groups.forEach((group, index) => {
      const width = countMode ? group.count * 14 : group.share * 100 * 4.2;
      const bar = document.querySelector(`#frequency [data-bar="${index}"]`);
      bar.setAttribute('width', width);
      document.getElementById(`var-freq-${index}`).textContent = countMode ? `${group.count}건` : `${group.share * 100}%`;
      document.getElementById(`var-freq-${index}`).setAttribute('x', 24 + width);
    });
    const ticks = countMode ? ['0', '5', '10', '15'] : ['0', '25', '50', ''];
    const places = countMode ? [24, 94, 164, 234] : [24, 129, 234, 234];
    ticks.forEach((label, index) => {
      const node = document.getElementById(`var-freq-tick-${index}`);
      node.textContent = label;
      node.setAttribute('x', places[index]);
    });
    document.getElementById('var-freq-axis').textContent = countMode ? '건수(건)' : '비율(%)';
    document.querySelectorAll('[data-freq]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.freq === frequency ? 'true' : 'false');
    });
    document.getElementById('var-freq-status').textContent = countMode
      ? '주거 15건, 상업 15건, 전체 30건. 비율은 15/30=50%입니다. 이 구성은 학습 예제이며 실제 시장의 거래 비중이 아닙니다.'
      : '주거 50%, 상업 50%. 두 비율의 합은 100%입니다. 범주 이름의 평균은 계산하지 않습니다.';
  }

  function renderMissing() {
    const drop = missingMode === 'drop';
    document.querySelectorAll('#missing-chart rect').forEach((node) => {
      const on = node.dataset.missing === missingMode;
      node.setAttribute('stroke', on ? '#d97706' : '#94a3b8');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('[data-missing-button]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.missingButton === missingMode ? 'true' : 'false');
    });
    document.getElementById('var-missing-status').textContent = drop
      ? '확인된 값만 계산합니다. 관측 2건, 합계 220, 평균 (100+120)/2=110. 이는 확인된 두 건의 평균이며 세 건 전체의 실제 평균은 아닙니다.'
      : '미확인 값을 임의로 0으로 대체했습니다. 실제 단가가 0으로 확인된 것은 아닙니다. 관측 3건, 합계 220, 평균 (100+120+0)/3≈73.33. 원자료에는 0을 저장하지 않습니다.';
  }

  document.querySelectorAll('#sheet [data-id], [data-row-button]').forEach((node) => {
    node.addEventListener('click', () => {
      selectedId = Number(node.dataset.id ?? node.dataset.rowButton);
      if (node.dataset.col) column = node.dataset.col;
      renderPoint();
    });
  });
  document.querySelectorAll('#sheet [data-col], [data-col-button]').forEach((node) => {
    node.addEventListener('click', () => {
      column = node.dataset.col ?? node.dataset.colButton;
      renderSheet();
    });
  });
  document.querySelectorAll('#scatter circle').forEach((node) => {
    node.addEventListener('click', () => {
      selectedId = Number(node.dataset.id);
      renderPoint();
    });
  });
  document.querySelectorAll('.var-id').forEach((input) => {
    input.addEventListener('input', () => {
      const value = Number(input.value);
      if (!byId.has(value)) return;
      selectedId = value;
      renderPoint();
    });
  });
  document.querySelectorAll('[data-freq]').forEach((button) => {
    button.addEventListener('click', () => {
      frequency = button.dataset.freq;
      renderFrequency();
    });
  });
  document.querySelectorAll('[data-missing-button]').forEach((button) => {
    button.addEventListener('click', () => {
      missingMode = button.dataset.missingButton;
      renderMissing();
    });
  });
  document.querySelectorAll('.var-controls').forEach((node) => node.removeAttribute('hidden'));
  renderPoint();
  renderFrequency();
  renderMissing();
}
