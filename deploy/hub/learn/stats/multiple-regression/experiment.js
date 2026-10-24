// Display only, independent of Macro regression and variable-selection APIs.
export function simpleFit(x, y) {
  const mx = x.reduce((a, b) => a + b, 0) / x.length;
  const my = y.reduce((a, b) => a + b, 0) / y.length;
  const slope = x.reduce((s, v, i) => s + (v - mx) * (y[i] - my), 0) / x.reduce((s, v) => s + (v - mx) ** 2, 0);
  return { intercept: my - slope * mx, slope };
}

export function groupFit(demo) {
  const means = [0, 1].map(group => {
    const indices = demo.group.map((g, i) => g === group ? i : -1).filter(i => i >= 0);
    return { x: indices.reduce((s, i) => s + demo.x[i], 0) / indices.length, y: indices.reduce((s, i) => s + demo.y[i], 0) / indices.length };
  });
  const rx = demo.x.map((x, i) => x - means[demo.group[i]].x);
  const ry = demo.y.map((y, i) => y - means[demo.group[i]].y);
  const slope = rx.reduce((s, x, i) => s + x * ry[i], 0) / rx.reduce((s, x) => s + x * x, 0);
  return { slope, intercepts: means.map(m => m.y - slope * m.x), means, rx, ry };
}

if (typeof document !== 'undefined') {
  const figure = document.getElementById('mr-groups');
  if (figure) {
    const demo = JSON.parse(document.getElementById('mr-demo').textContent);
    const simple = simpleFit(demo.x, demo.y), adjusted = groupFit(demo);
    const select = document.getElementById('mr-group-mode');
    function update() {
      const mode = select.value;
      figure.querySelectorAll('[data-trend]').forEach(line => line.toggleAttribute('hidden', line.dataset.trend === 'overall' ? mode === 'adjusted' : mode === 'overall'));
      figure.querySelectorAll('circle[data-group]').forEach(dot => dot.setAttribute('fill', mode !== 'overall' && dot.dataset.group === '1' ? '#d97706' : '#2563eb'));
      const legend = mode === 'overall' ? '전체 6점 · 회색 점선: 집단 미조정 단순회귀' : mode === 'adjusted' ? '파랑: A · 주황: B · 실선: 집단별 절편, 공통 기울기 +1' : '파랑: A · 주황: B · 실선: 조정 모형 · 회색 점선: 단순회귀';
      figure.querySelector('#mr-group-legend').textContent = legend;
      figure.querySelector('#mr-group-heading').textContent = mode === 'overall' ? '가상 자료: 집단을 구분하지 않은 6개 관측값' : '가상 자료: 파랑 A집단 / 주황 B집단';
      const status = `전체 단순 기울기 ${simple.slope.toFixed(3)} → 집단을 포함한 공통 기울기 +${adjusted.slope.toFixed(3)}. A의 적합식 ŷ=7+X, B는 ŷ=−2+X입니다. A 평균 (2, 9), B 평균 (5, 3)의 차이가 전체 기울기에 섞여 있습니다. 현재 보기: ${select.options[select.selectedIndex].text}.`;
      document.getElementById('mr-group-status').textContent = status;
      const caption = `그림 1. 가상 6점 · ${select.options[select.selectedIndex].text}. ${legend}. 두 집단의 X범위는 겹치지 않으며, 조정이 인과적으로 옳은 결과라는 뜻은 아닙니다.`;
      figure.querySelector('figcaption').textContent = caption;
      figure.querySelector('#groups-desc').textContent = caption;
    }
    select.addEventListener('change', update);
    update();
    figure.querySelector('.mr-controls').hidden = false;
  }
}
