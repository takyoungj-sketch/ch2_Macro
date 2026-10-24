/* Independent teaching experiment. No Macro data or analysis API is used. */
export function summarize(sample, critical) {
  let mean = 0;
  let m2 = 0;
  sample.forEach((value, i) => {
    const delta = value - mean;
    mean += delta / (i + 1);
    m2 += delta * (value - mean);
  });
  const sd = Math.sqrt(m2 / (sample.length - 1));
  const se = sd / Math.sqrt(sample.length);
  const margin = critical * se;
  return { mean, sd, se, low: mean - margin, high: mean + margin };
}

export function normalSample(n, random = Math.random) {
  const sample = [];
  while (sample.length < n) {
    // Box–Muller: independent standard normals from two uniforms in (0, 1).
    const radius = Math.sqrt(-2 * Math.log(1 - random()));
    const angle = 2 * Math.PI * random();
    sample.push(100 + 20 * radius * Math.cos(angle));
    if (sample.length < n) sample.push(100 + 20 * radius * Math.sin(angle));
  }
  return sample;
}

if (typeof document !== 'undefined') {
  const figure = document.querySelector('#ci-coverage');
  const controls = figure?.querySelector('.ci-experiment');
  if (controls) {
    const critical = Number(controls.dataset.critical); // SciPy t(.975, df=24)
    const svg = figure.querySelector('svg');
    const caption = figure.querySelector('figcaption');
    let total = 0;
    let covered = 0;
    let recent = [];
    const bits = new Uint32Array(1);
    const random = () => {
      crypto.getRandomValues(bits);
      return (bits[0] + 0.5) / 4294967296;
    };
    const add = (tag, attributes, text) => {
      const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
      Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
      if (text !== undefined) node.textContent = text;
      svg.append(node);
      return node;
    };
    function render() {
      const count = recent.filter(row => row.covers).length;
      const missed = recent.filter(row => !row.covers).map(row => row.id);
      controls.querySelector('#ci-status').textContent =
        `최근 20개: ${count}개 포함 · ${20 - count}개 미포함 · 실제 포함 비율 ${(100 * count / 20).toFixed(1)}%. 미포함 행: ${missed.join(', ') || '없음'}.`;
      controls.querySelector('#ci-total').textContent =
        `누적 ${total}회: ${covered}개 포함 · 실제 포함 비율 ${(100 * covered / total).toFixed(1)}%.`;
      controls.querySelectorAll('[data-ci-total]').forEach(button => {
        button.disabled = total >= Number(button.dataset.ciTotal);
      });
      svg.querySelectorAll('line, circle, text').forEach(node => node.remove());
      const low = Math.floor(Math.min(100, ...recent.map(row => row.low)) / 5) * 5 - 5;
      const high = Math.ceil(Math.max(100, ...recent.map(row => row.high)) / 5) * 5 + 5;
      const x = value => 80 + 510 * (value - low) / (high - low);
      add('text', { x: 24, y: 28 }, '무작위 표본 25개 → 각 표본의 s로 계산한 95% t 구간');
      add('line', { x1: x(100), x2: x(100), y1: 45, y2: 485, stroke: '#d97706', 'stroke-dasharray': '4 3' });
      recent.forEach((row, i) => {
        const y = 60 + 21 * i;
        const color = row.covers ? '#2563eb' : '#dc2626';
        add('text', { x: 12, y: y + 4 }, `${row.id}${row.covers ? '' : ' ×'}`);
        const line = add('line', {
          x1: x(row.low), x2: x(row.high), y1: y, y2: y, stroke: color,
          'stroke-width': 3, 'stroke-dasharray': row.covers ? 'none' : '5 3',
          class: row.covers ? 'ci-hit' : 'ci-miss', 'data-repeat': row.id,
          'data-sample': JSON.stringify(row.sample), 'data-mean': row.mean,
          'data-sd': row.sd, 'data-low': row.low, 'data-high': row.high,
          'data-covers': row.covers,
        });
        const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        title.textContent = `${row.id}회: 평균 ${row.mean.toFixed(2)}, s ${row.sd.toFixed(2)}, 구간 ${row.low.toFixed(2)}~${row.high.toFixed(2)}, ${row.covers ? '포함' : '미포함'}`;
        line.append(title);
        add('circle', { cx: x(row.mean), cy: y, r: 3, fill: color, class: row.covers ? 'ci-hit' : 'ci-miss' });
      });
      add('text', { x: 24, y: 510 }, `이번 표시: ${count}/20 포함 (${(100 * count / 20).toFixed(1)}%) · 모평균 μ=100`);
      for (let i = 0; i <= 4; i++) {
        const value = low + i * (high - low) / 4;
        add('text', { x: x(value), y: 545, 'text-anchor': 'middle' }, value.toFixed(1));
      }
      add('text', { x: 24, y: 568 }, '가로축: 모형값 · 파랑 실선=포함 / 빨강 점선·×=미포함');
      const description = `그림 2. N(100,20²)에서 독립표본 25개를 매번 새로 추출했습니다. 각 표본의 평균과 표본표준편차, 자유도 24의 t 임계값 ${critical.toFixed(3)}을 사용합니다. 최근 20개 중 ${count}개 포함, ${20 - count}개 미포함. 결과를 인위적으로 조정하지 않습니다.`;
      caption.textContent = description;
      svg.querySelector('#coverage-desc').textContent = description;
    }
    function run(count) {
      for (let i = 0; i < count; i++) {
        const sample = normalSample(25, random);
        const row = { ...summarize(sample, critical), sample, id: ++total };
        row.covers = row.low <= 100 && 100 <= row.high;
        if (row.covers) covered++;
        recent.push(row);
        if (recent.length > 20) recent.shift();
      }
      render();
    }
    controls.querySelector('#ci-resample').addEventListener('click', () => run(20));
    controls.querySelectorAll('[data-ci-total]').forEach(button => {
      button.addEventListener('click', () => run(Math.max(0, Number(button.dataset.ciTotal) - total)));
    });
    run(20);
    controls.hidden = false;
  }
}
