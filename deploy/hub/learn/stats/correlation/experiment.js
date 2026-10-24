// Independent learning UI; never calls or changes Macro analysis APIs.
export function pearson(points) {
  if (points.length < 2) return null;
  const mx = points.reduce((s, p) => s + p[0], 0) / points.length;
  const my = points.reduce((s, p) => s + p[1], 0) / points.length;
  let xy = 0, xx = 0, yy = 0;
  points.forEach(([x, y]) => { xy += (x - mx) * (y - my); xx += (x - mx) ** 2; yy += (y - my) ** 2; });
  return xx > 0 && yy > 0 ? xy / Math.sqrt(xx * yy) : null;
}

export function ranks(values) {
  const sorted = values.map((value, i) => ({ value, i })).sort((a, b) => a.value - b.value);
  const result = Array(values.length);
  for (let i = 0; i < sorted.length;) {
    let end = i + 1;
    while (end < sorted.length && sorted[end].value === sorted[i].value) end++;
    const rank = (i + 1 + end) / 2;
    for (let j = i; j < end; j++) result[sorted[j].i] = rank;
    i = end;
  }
  return result;
}

export function scatterStats(rows, exclude7 = false) {
  const selected = rows.filter(row => (!exclude7 || row.id !== 7) && Number.isFinite(row.area) && Number.isFinite(row.price));
  const x = ranks(selected.map(row => row.area)), y = ranks(selected.map(row => row.price));
  return { n: selected.length, r: pearson(selected.map(row => [row.area, row.price])), rho: pearson(x.map((rank, i) => [rank, y[i]])) };
}

export function fit(points) {
  const mx = points.reduce((s, p) => s + p[0], 0) / points.length;
  const my = points.reduce((s, p) => s + p[1], 0) / points.length;
  const xx = points.reduce((s, p) => s + (p[0] - mx) ** 2, 0);
  if (!xx) return null;
  const slope = points.reduce((s, p) => s + (p[0] - mx) * (p[1] - my), 0) / xx;
  return { intercept: my - slope * mx, slope, r: pearson(points), n: points.length };
}

if (typeof document !== 'undefined') {
  const scatter = document.getElementById('co-scatter');
  const signed = value => (value > 0 ? '+' : '') + value.toFixed(3);
  if (scatter) {
    const rows = JSON.parse(document.getElementById('co-rows').textContent);
    const exclude = document.getElementById('co-exclude');
    const observation = document.getElementById('co-observation');
    function updateObservation() {
      const row = rows.find(row => String(row.id) === observation.value);
      scatter.querySelectorAll('circle[data-id]').forEach(dot => dot.setAttribute('data-selected', String(dot.dataset.id === observation.value)));
      const duplicates = row ? rows.filter(p => p.area === row.area && p.price === row.price).length : 0;
      document.getElementById('co-observation-status').textContent = row
        ? `${row.id}번 · ${row.group} · 면적 ${row.area}㎡ · 단가 ${row.price}만원/㎡ · 같은 좌표 ${duplicates}건`
        : '점을 가리키거나 관측값을 선택하면 면적·단가·유형을 확인할 수 있습니다.';
    }
    function updateScatter() {
      const stats = scatterStats(rows, exclude.checked);
      document.getElementById('co-scatter-stats').textContent = `유효한 쌍 ${stats.n}건 · Pearson r=${signed(stats.r)} · Spearman ρₛ=${signed(stats.rho)}`;
      scatter.querySelector('#co-scatter-heading').textContent = `면적과 거래단가 · Pearson r=${signed(stats.r)} · n=${stats.n}`;
      scatter.querySelector('circle[data-id="7"]').toggleAttribute('hidden', exclude.checked);
      document.getElementById('co-id7-label').toggleAttribute('hidden', exclude.checked);
      observation.querySelector('option[value="7"]').disabled = exclude.checked;
      if (exclude.checked && observation.value === '7') observation.value = '';
      const caption = `그림 1. 공통 학습 자료 ${stats.n}건의 면적·단가 산점도입니다. ${exclude.checked ? '원자료 id=7 한 건만 제외한 민감도 비교입니다.' : '원자료 30건을 모두 포함합니다.'} 좌표와 단위는 그대로이며 회귀기울기나 인과효과가 아닙니다.`;
      scatter.querySelector('figcaption').textContent = caption;
      scatter.querySelector('#scatter-desc').textContent = caption;
      updateObservation();
    }
    exclude.addEventListener('change', updateScatter);
    observation.addEventListener('change', updateObservation);
    updateScatter();
    scatter.querySelector('.co-controls').hidden = false;
  }
  const mixture = document.getElementById('co-mixture');
  if (mixture) {
    const groups = JSON.parse(document.getElementById('co-mixture-data').textContent);
    const points = groups.A.concat(groups.B);
    const overall = fit(points), a = fit(groups.A), b = fit(groups.B);
    const mode = document.getElementById('co-mode');
    const allText = `전체 n=${overall.n}, r=${signed(overall.r)}`;
    const groupsText = `A n=${a.n}, r=${signed(a.r)} · B n=${b.n}, r=${signed(b.r)}`;
    function updateMixture() {
      const grouped = mode.value !== 'overall', showOverall = mode.value !== 'groups';
      mixture.querySelectorAll('[data-trend]').forEach(line => {
        const name = line.dataset.trend;
        line.toggleAttribute('hidden', name === 'overall' ? !showOverall : !grouped);
      });
      mixture.querySelectorAll('circle[data-group]').forEach(dot => dot.setAttribute('fill', grouped && dot.dataset.group === 'B' ? '#d97706' : '#2563eb'));
      mixture.querySelector('#co-mix-heading').textContent = mode.value === 'overall' ? allText : mode.value === 'groups' ? groupsText : `${allText} · A/B는 각각 r=+1`;
      const legend = grouped ? '파랑: A · 주황: B · 실선: 집단별 추세' + (showOverall ? ' · 청록 점선: 전체' : '') : '점: 전체 자료 · 청록 점선: 전체의 선형 추세';
      mixture.querySelector('#co-mix-legend').textContent = legend;
      const status = `${allText}. ${groupsText}. A의 평균은 (2, 9), B의 평균은 (8, 3)입니다. 집단 내부에서는 함께 증가하지만, 평균 수준이 다른 두 집단을 합치면 방향이 반대가 됩니다.`;
      document.getElementById('co-mix-status').textContent = status;
      const caption = `그림 3. 별도 가상 6점 · ${mode.options[mode.selectedIndex].text}. ${legend}. 추세선은 단순 선형 요약이며 인과효과가 아닙니다.`;
      mixture.querySelector('figcaption').textContent = caption;
      mixture.querySelector('#mixture-desc').textContent = caption;
    }
    mode.addEventListener('change', updateMixture);
    updateMixture();
    mixture.querySelector('.co-controls').hidden = false;
  }
}
