// Display only: the chapter's reproducible diagnostics are generated from raw data.
export function patternLayout(mode) {
  const keys = ['none', 'curve', 'fan'];
  if (mode !== 'all' && !keys.includes(mode)) throw new Error('Unknown residual pattern');
  return { height: mode === 'all' ? 785 : 275, panels: keys.map((key, i) => ({ key, hidden: mode !== 'all' && mode !== key, y: mode === 'all' ? i * 255 : 0 })) };
}

export function observation(rows, id) {
  return rows.find(row => row.id === Number(id)) ?? null;
}

if (typeof document !== 'undefined') {
  const data = document.getElementById('rd-data');
  if (data) {
    const rows = JSON.parse(data.textContent);
    const number = (n, digits) => n.toLocaleString('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    document.querySelectorAll('.rd-observations').forEach(figure => {
      const select = figure.querySelector('select');
      function update() {
        const row = observation(rows, select.value);
        figure.querySelectorAll('circle[data-id]').forEach(dot => dot.setAttribute('data-selected', String(Number(dot.dataset.id) === row.id)));
        const core = `${row.id}번 · ${row.group} · 실제 단가 ${number(row.price, 2)} · 적합 단가 ${number(row.fitted, 2)} · 잔차 ${row.residual >= 0 ? '+' : '−'}${number(Math.abs(row.residual), 2)} (만원/㎡)`;
        const influence = `레버리지 h=${number(row.leverage, 3)} · 내부 표준화 잔차 r=${number(row.standardized, 2)} · Cook D=${number(row.cook, 3)} (단위 없음)`;
        figure.querySelector('.rd-observation-status').textContent = `${core}. ${influence}. 관측번호는 시간 순서가 아니며, 잔차는 적정가격과의 차이가 아닙니다.`;
      }
      select.addEventListener('change', update);
      update();
      figure.querySelector('.rd-controls').hidden = false;
    });
  }

  const figure = document.getElementById('rd-patterns');
  if (figure) {
    const patterns = JSON.parse(document.getElementById('rd-pattern-data').textContent);
    const buttons = figure.querySelectorAll('button[data-mode]');
    function update(mode) {
      const layout = patternLayout(mode);
      const svg = figure.querySelector('svg');
      svg.setAttribute('viewBox', `0 0 640 ${layout.height}`);
      layout.panels.forEach(panel => {
        const group = figure.querySelector(`[data-pattern="${panel.key}"]`);
        group.toggleAttribute('hidden', panel.hidden);
        group.setAttribute('transform', `translate(0 ${panel.y})`);
      });
      buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.mode === mode)));
      const status = mode === 'all'
        ? '세 패턴을 같은 축 범위와 배율로 비교합니다. 곡선형은 평균 관계의 중심, 부채꼴은 오차의 폭에 주목하세요. 모든 점은 학습용으로 구성한 가상 자료입니다.'
        : `${patterns[mode].title}: ${patterns[mode].note} 비교 화면과 같은 축 범위·좌표입니다.`;
      document.getElementById('rd-pattern-status').textContent = status;
      const caption = `그림 2. ${status} 진단의 단서이며 검정 결과나 원인에 대한 확정이 아닙니다.`;
      figure.querySelector('figcaption').textContent = caption;
      figure.querySelector('#patterns-desc').textContent = caption;
    }
    buttons.forEach(button => button.addEventListener('click', () => update(button.dataset.mode)));
    update('all');
    figure.querySelector('.rd-controls').hidden = false;
  }
}
