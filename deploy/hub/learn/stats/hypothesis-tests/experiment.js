/* Chapter 13 teaching comparisons. All t-tail probabilities and critical
 * values come from SciPy at build time; no Macro API or data is changed. */
export function comparison(mu0, alpha, data) {
  const row = data.comparisons.find(row => row.mu0 === mu0);
  const critical = data.criticals[String(alpha)];
  if (!row || !Number.isFinite(critical)) throw new RangeError('Unsupported teaching comparison');
  const t = (data.mean - mu0) / (data.sd / Math.sqrt(data.n));
  return { mu0, alpha, t, p: row.p, critical, reject: row.p <= alpha };
}

export function tailPoints(cut, df, densityAtZero) {
  const point = t => [320 + t * 60, 235 - densityAtZero * (1 + t * t / df) ** (-(df + 1) / 2) * 400];
  return [[-4.5, -cut], [cut, 4.5]].map(([a, b]) => {
    const points = [[point(a)[0], 235]];
    for (let i = 0; i <= 100; i++) points.push(point(a + (b - a) * i / 100));
    points.push([point(b)[0], 235]);
    return points.map(p => p.join(',')).join(' ');
  });
}

if (typeof document !== 'undefined') {
  const first = document.querySelector('#ht-p-tails');
  const panel = first?.querySelector('.ht-experiment');
  if (panel) {
    const data = JSON.parse(first.querySelector('#ht-experiment-data').textContent);
    const figures = [first, document.querySelector('#ht-rejection')];
    const originals = figures.map(figure => ({ svg: figure.querySelector('svg').innerHTML, caption: figure.querySelector('figcaption').textContent }));
    const slider = panel.querySelector('#ht-mu');
    const alpha = panel.querySelector('#ht-alpha');
    const pText = p => p < 0.0001 ? p.toExponential(3) : p.toFixed(4);
    function draw(figure, state, index) {
      const svg = figure.querySelector('svg');
      const prefix = index === 0 ? 'p-tails' : 'rejection';
      // Preserve the curve's accessible title/description identifiers for zoom.
      svg.querySelectorAll('text, line, circle, polygon, polyline').forEach(node => node.remove());
      const add = (tag, attrs, value) => {
        const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
        Object.entries(attrs).forEach(([k,v]) => e.setAttribute(k,v));
        if (value !== undefined) e.textContent = value;
        svg.append(e);
      };
      const x = t => 320 + t * 60;
      const y = t => 235 - data.densityAtZero * (1 + t * t / data.df) ** (-(data.df + 1) / 2) * 400;
      const cut = index === 0 ? Math.abs(state.t) : state.critical;
      add('text',{x:24,y:28}, index === 0 ? `가상 μ₀=${state.mu0}: t=${state.t.toFixed(3)}, 양측 p=${pText(state.p)}` : `공유 설정 α=${state.alpha.toFixed(2)}: ±${state.critical.toFixed(3)} 경계부터 기각`);
      add('line',{x1:50,x2:590,y1:235,y2:235,stroke:'#64748b'});
      tailPoints(cut,data.df,data.densityAtZero).forEach(points => add('polygon',{points,fill:index===0?'#bfdbfe':'#ffedd5'}));
      const points = Array.from({length:361},(_,i)=>{const t=-4.5+i*.025;return `${x(t)},${y(t)}`;}).join(' ');
      add('polyline',{points,fill:'none',stroke:'#2563eb','stroke-width':2});
      for (const t of [-4,-2,0,2,4]) add('text',{x:x(t),y:260,'text-anchor':'middle'},t);
      for (const t of [-state.critical,state.critical]) {
        add('line',{x1:x(t),x2:x(t),y1:45,y2:235,stroke:'#d97706','stroke-width':2,'stroke-dasharray':'5 4',class:'ht-critical'});
        add('text',{x:x(t),y:312,'text-anchor':'middle'},`임계 ${t.toFixed(3)}`);
      }
      add('line',{x1:x(state.t),x2:x(state.t),y1:45,y2:235,stroke:'#0f766e','stroke-width':3,class:'ht-observed','data-observed-t':state.t});
      add('circle',{cx:x(state.t),cy:y(state.t),r:4,fill:'#0f766e',class:'ht-observed-dot'});
      add('text',{x:24,y:285},`관측 t=${state.t.toFixed(3)} · 기준 μ₀=${state.mu0}만원/㎡ · 가로축 t는 단위 없음`);
      add('text',{x:24,y:340},'주황 점선: ±임계값 · 청록 실선: 관측 t · t=0: 귀무가설 중심');
      const desc = `그림 ${index+1} · 가상 비교. n=30과 반올림 전 평균·표준편차를 고정하고 기준 평균 μ₀=${state.mu0}만원/㎡와 α=${state.alpha.toFixed(2)}를 적용했습니다. t=${state.t.toFixed(3)}, 양측 p=${pText(state.p)}, 임계값 ±${state.critical.toFixed(3)}. ${state.reject?'H₀ 기각':'H₀를 기각하지 않음'}. ${index===0?'옅은 파랑은 p값 영역':'옅은 주황은 기각영역'}입니다. 파란 곡선은 자유도 29의 t분포, 주황 점선은 기각 경계, 청록 실선은 관측 t입니다. p값은 화면 밖 꼬리도 포함합니다. 본문과 그림 3·4의 기본 계산값은 그대로입니다.`;
      figure.querySelector('figcaption').textContent=desc;
      svg.querySelector(`#${prefix}-desc`).textContent=desc;
    }
    function update() {
      const state = comparison(Number(slider.value),Number(alpha.value),data);
      panel.querySelector('#ht-mu-value').textContent=`${state.mu0}만원/㎡`;
      const result = panel.querySelector('#ht-result');
      result.replaceChildren();
      const values = document.createElement('div');
      values.className='ht-comparison';
      for (const text of [`양측 p값 ${pText(state.p)}`,`유의수준 α ${state.alpha.toFixed(2)}`]) {
        const span=document.createElement('span');span.textContent=text;values.append(span);
      }
      const decision=document.createElement('p');
      decision.textContent=`t=${state.t.toFixed(3)} · 자유도 29 → ${state.reject?'H₀ 기각':'H₀를 기각하지 않음'}`;
      result.append(values,decision);
      figures.forEach((figure,index)=>{
        if (state.mu0===130 && state.alpha===.05) {
          figure.querySelector('svg').innerHTML=originals[index].svg;
          figure.querySelector('figcaption').textContent=originals[index].caption;
        } else draw(figure,state,index);
      });
    }
    slider.addEventListener('input',update);
    alpha.addEventListener('change',update);
    panel.querySelector('#ht-reset').addEventListener('click',()=>{slider.value='130';alpha.value='0.05';update();});
    update();
    panel.hidden=false;
  }
}
