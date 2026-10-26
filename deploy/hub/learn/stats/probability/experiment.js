const EVENTS = {
  A: ['A_B', 'A_notB'],
  B: ['A_B', 'notA_B'],
  both: ['A_B'],
  either: ['A_B', 'A_notB', 'notA_B'],
  notA: ['notA_B', 'notA_notB'],
  neither: ['notA_notB'],
};

export function eventCount(table, event) {
  return EVENTS[event].reduce((sum, key) => sum + table[key], 0);
}

export function screen(percent) {
  const total = 1000;
  const errors = total * percent / 100;
  const normal = total - errors;
  const tp = errors * 9 / 10;
  const fp = normal / 10;
  const fn = errors - tp;
  const tn = normal - fp;
  return { total, errors, normal, tp, fp, fn, tn, flagged: tp + fp, ppv: tp / (tp + fp) };
}

if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('pr-data').textContent);
  const table = data.table;
  let event = 'either';
  let condition = 'A';
  let path = 'AB';
  let percent = 2;
  let empty = false;

  function pct(value) {
    const rounded = Math.round(value * 10000) / 100;
    return `${rounded.toLocaleString('ko-KR', { maximumFractionDigits: 2 })}%`;
  }

  function renderEvent() {
    const keys = new Set(EVENTS[event]);
    document.querySelectorAll('#events svg [data-cell]').forEach((node) => {
      const on = keys.has(node.dataset.cell);
      node.setAttribute('opacity', on ? '1' : '0.28');
      node.setAttribute('stroke', on ? '#d97706' : '#64748b');
      node.setAttribute('stroke-width', on ? '2' : '1');
    });
    document.querySelectorAll('#pr-split [data-cell]').forEach((node) => {
      node.dataset.on = keys.has(node.dataset.cell) ? 'yes' : 'no';
    });
    document.querySelectorAll('[data-event]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.event === event ? 'true' : 'false');
    });
    const count = eventCount(table, event);
    const names = {
      A: '주거 A',
      B: '면적 100㎡ 이상 B',
      both: '교집합 A∩B',
      either: '합집합 A∪B',
      notA: '여사건 Aᶜ',
      neither: '둘 다 아님 Aᶜ∩Bᶜ',
    };
    const note = event === 'either'
      ? '40과 30을 더하면 교집합 18이 두 번 들어가므로 한 번 뺍니다.'
      : '분할표에서 해당 칸을 더했습니다.';
    document.getElementById('pr-event-status').textContent =
      `${names[event]}는 ${count}건, ${pct(count / 100)}입니다. ${note} 칸의 위치는 지역이나 단가가 아닙니다.`;
  }

  function renderCondition() {
    const specs = {
      A: { num: 40, den: 100, label: '전체 중 주거', formula: '40/100' },
      'A|B': { num: 18, den: 30, label: '큰 면적 중 주거', formula: '18/30' },
      'B|A': { num: 18, den: 40, label: '주거 중 큰 면적', formula: '18/40' },
    };
    document.querySelectorAll('#conditional [data-numerator]').forEach((node) => {
      const on = !empty && node.dataset.numerator === String(specs[condition].num) && node.dataset.denominator === String(specs[condition].den);
      node.setAttribute('stroke', on ? '#d97706' : '#1e3a8a');
      node.setAttribute('stroke-width', on ? '3' : '0');
    });
    document.querySelectorAll('[data-condition]').forEach((button) => {
      button.setAttribute('aria-pressed', !empty && button.dataset.condition === condition ? 'true' : 'false');
    });
    document.querySelectorAll('[data-empty]').forEach((button) => {
      button.setAttribute('aria-pressed', empty ? 'true' : 'false');
    });
    document.getElementById('pr-condition-status').textContent = empty
      ? '조건에 해당하는 거래가 0건이면 분모가 없습니다. 이 비율은 0%가 아니라 계산할 수 없습니다. 20건 중 0건은 분모가 있으므로 0%입니다.'
      : `${specs[condition].label}: ${specs[condition].formula}=${pct(specs[condition].num / specs[condition].den)}. 교집합은 같은 18건이고 분모가 100·30·40으로 달라집니다.`;
  }

  function renderPath() {
    const paths = {
      AB: ['주거이면서 100㎡ 이상', 0.4, 0.45, 18],
      AnotB: ['주거이면서 100㎡ 미만', 0.4, 0.55, 22],
      notAB: ['비주거이면서 100㎡ 이상', 0.6, 0.2, 12],
      neither: ['비주거이면서 100㎡ 미만', 0.6, 0.8, 48],
    };
    document.querySelectorAll('#tree [data-path]').forEach((node) => {
      const on = node.dataset.path === path;
      node.setAttribute('stroke', on ? '#d97706' : '#64748b');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('[data-path-choice]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.pathChoice === path ? 'true' : 'false');
    });
    const [name, first, second, count] = paths[path];
    document.getElementById('pr-path-status').textContent =
      `${name}: ${first}×${second}=${pct(first * second)}. 분할표 ${count}건과 같습니다. 네 경로의 합은 100%입니다.`;
  }

  function renderScreen() {
    const result = screen(percent);
    const notes = [
      ['pr-flag-error', result.tp, `실제 오류 ${result.errors}건 중 ${result.tp}건 표시`],
      ['pr-flag-normal', result.fp, `정상 ${result.normal}건 중 ${result.fp}건 표시`],
    ];
    notes.forEach(([id, count, note]) => {
      const node = document.getElementById(id);
      node.setAttribute('width', count * 2.6);
      node.setAttribute('data-flagged', String(count));
      document.getElementById(`${id}-label`).textContent = `${count}건`;
      document.getElementById(`${id}-label`).setAttribute('x', 32 + count * 2.6);
      document.getElementById(`${id}-note`).textContent = note;
    });
    const cells = {
      'pr-tp': result.tp,
      'pr-fn': result.fn,
      'pr-err': result.errors,
      'pr-fp': result.fp,
      'pr-tn': result.tn,
      'pr-ok': result.normal,
      'pr-flagged': result.flagged,
      'pr-clear': result.tn + result.fn,
    };
    Object.entries(cells).forEach(([id, count]) => {
      document.getElementById(id).textContent = String(count);
    });
    document.querySelectorAll('[data-rate]').forEach((button) => {
      button.setAttribute('aria-pressed', Number(button.dataset.rate) === percent ? 'true' : 'false');
    });
    document.getElementById('pr-flag-summary').textContent =
      `표시 ${result.flagged}건 = 참양성 ${result.tp} + 거짓양성 ${result.fp}`;
    document.getElementById('pr-flag-precision').textContent =
      `정밀도 ${result.tp}/${result.flagged} ≈ ${pct(result.ppv)}. 탐지율 90%와 다릅니다.`;
    document.getElementById('pr-metric-sens').textContent =
      `${result.tp}/${result.errors}=${pct(result.tp / result.errors)}. 실제 오류 중 표시된 비율입니다.`;
    document.getElementById('pr-metric-fpr').textContent =
      `${result.fp}/${result.normal}=${pct(result.fp / result.normal)}. 실제 정상 중 잘못 표시된 비율입니다.`;
    document.getElementById('pr-metric-spec').textContent =
      `${result.tn}/${result.normal}=${pct(result.tn / result.normal)}. 실제 정상 중 정상으로 판정한 비율입니다.`;
    document.getElementById('pr-metric-ppv').textContent =
      `${result.tp}/${result.flagged}≈${pct(result.ppv)}. 표시된 거래 중 실제 오류 비율입니다.`;
    document.getElementById('pr-screen-status').textContent =
      `오류율 ${percent}%는 교육용 가정이고 기본 예제는 2%입니다. 오류 ${result.errors}건, 정상 ${result.normal}건. 참양성 ${result.tp}, 거짓음성 ${result.fn}, 거짓양성 ${result.fp}, 참음성 ${result.tn}. 탐지율 ${pct(result.tp / result.errors)}, 오탐률 ${pct(result.fp / result.normal)}, 정밀도 ${pct(result.ppv)}. 전체는 ${result.total}건입니다.`;
    document.getElementById('base-rate-caption').textContent =
      `그림 4. 탐지율 90%와 오탐률 10%는 고정입니다. 선택한 실제 오류율은 ${percent}%이고, 표시된 거래 중 실제 오류는 ${pct(result.ppv)}입니다. 서비스 성능이 아닙니다.`;
  }

  document.querySelectorAll('[data-event]').forEach((button) => {
    button.addEventListener('click', () => { event = button.dataset.event; renderEvent(); });
  });
  document.querySelectorAll('[data-condition]').forEach((button) => {
    button.addEventListener('click', () => { empty = false; condition = button.dataset.condition; renderCondition(); });
  });
  document.querySelectorAll('[data-empty]').forEach((button) => {
    button.addEventListener('click', () => { empty = true; renderCondition(); });
  });
  document.querySelectorAll('[data-path-choice]').forEach((button) => {
    button.addEventListener('click', () => { path = button.dataset.pathChoice; renderPath(); });
  });
  document.querySelectorAll('#tree [data-path]').forEach((node) => {
    node.addEventListener('click', () => { path = node.dataset.path; renderPath(); });
  });
  document.querySelectorAll('[data-rate]').forEach((button) => {
    button.addEventListener('click', () => { percent = Number(button.dataset.rate); renderScreen(); });
  });
  document.querySelectorAll('.pr-controls').forEach((node) => node.removeAttribute('hidden'));
  renderEvent();
  renderCondition();
  renderPath();
  renderScreen();
}
