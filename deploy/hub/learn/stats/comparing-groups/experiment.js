/* Display controls for chapter 14. Uses unchanged teaching observations. */
export function changeRows(rows) {
  return rows.map(row => ({ ...row, change: row.after - row.before }));
}

if (typeof document !== 'undefined') {
  const distribution = document.querySelector('#gg-distribution');
  const controls = distribution?.querySelector('.gg-controls');
  if (controls) {
    const mean = controls.querySelector('#gg-mean');
    const sd = controls.querySelector('#gg-sd');
    const update = () => {
      distribution.querySelectorAll('.gg-mean').forEach(line => line.style.display = mean.checked ? '' : 'none');
      distribution.querySelectorAll('.gg-sd').forEach(group => {
        if (sd.checked) group.removeAttribute('hidden');
        else group.setAttribute('hidden', '');
      });
    };
    mean.addEventListener('change', update);
    sd.addEventListener('change', update);
    update();
    controls.hidden = false;
  }
  const figure = document.querySelector('#gg-paired');
  const panel = figure?.querySelector('.gg-paired-controls');
  if (panel) {
    const data = JSON.parse(figure.querySelector('#gg-paired-data').textContent);
    const svg = figure.querySelector('svg');
    const originalSvg = svg.innerHTML;
    const caption = figure.querySelector('figcaption');
    const originalCaption = caption.textContent;
    const original = panel.querySelector('#gg-original');
    const changes = panel.querySelector('#gg-changes');
    function render(showChanges) {
      original.setAttribute('aria-pressed', !showChanges);
      changes.setAttribute('aria-pressed', showChanges);
      if (!showChanges) {
        svg.innerHTML = originalSvg;
        caption.textContent = originalCaption;
        panel.querySelector('#gg-paired-status').textContent = '원래 점수 보기: 같은 학생의 이전·이후 점수를 연결합니다.';
        return;
      }
      svg.querySelectorAll('line, circle, text, polyline, rect').forEach(node => node.remove());
      const add = (tag, attrs, text) => {
        const e = document.createElementNS('http://www.w3.org/2000/svg',tag);
        Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));
        if (text !== undefined) e.textContent=text;
        svg.append(e);
      };
      const x = value => 110 + value*40;
      add('text',{x:24,y:28},'각 학생의 변화량 = 이후 점수 − 이전 점수');
      add('line',{x1:x(0),x2:x(0),y1:55,y2:263,stroke:'#94a3b8','stroke-dasharray':'3 3'});
      add('line',{x1:x(data.mean),x2:x(data.mean),y1:55,y2:263,stroke:'#d97706','stroke-dasharray':'4 3'});
      changeRows(data.rows).forEach((row,i)=>{
        const y=75+i*35;
        add('text',{x:24,y:y+4},`학생 ${row.student}`);
        add('line',{x1:x(0),x2:x(row.change),y1:y,y2:y,stroke:'#94a3b8','stroke-width':2});
        add('circle',{cx:x(row.change),cy:y,r:5,fill:'#2563eb','data-student':row.student,'data-change':row.change});
        add('text',{x:x(row.change)+12,y:y+4},`+${row.change}점`);
      });
      for (const value of [0,2,4,6,8,10]) add('text',{x:x(value),y:280,'text-anchor':'middle'},value);
      add('text',{x:24,y:318},'평균 CI');
      add('line',{x1:x(data.low),x2:x(data.high),y1:312,y2:312,stroke:'#2563eb','stroke-width':5,'data-change-ci':'true'});
      add('circle',{cx:x(data.mean),cy:312,r:5,fill:'#d97706'});
      add('text',{x:x(data.low),y:342,'text-anchor':'middle'},data.low.toFixed(2));
      add('text',{x:x(data.high),y:342,'text-anchor':'middle'},data.high.toFixed(2));
      add('text',{x:24,y:374},'가로축: 변화량(점) · 주황 점선: 평균 변화 6.00점');
      const desc='그림 3 · 변화량 보기. 표시 학생 1~6의 변화량은 6, 8, 5, 7, 4, 6점입니다. 점은 학생별 변화량, 아래 굵은 선은 평균 변화의 95% t 신뢰구간 4.52~7.48점입니다. 이 구간은 학생별 변화량의 범위가 아닙니다. 원래 여섯 점수 쌍을 그대로 사용한 가상 학습 자료이며 수업의 인과효과를 검증한 결과가 아닙니다.';
      caption.textContent=desc;
      svg.querySelector('#pairs-desc').textContent=desc;
      panel.querySelector('#gg-paired-status').textContent='변화량 보기: 각 학생의 차이를 먼저 계산합니다. 평균 6.00점, 변화량 표본표준편차 1.414점, SE 0.577점, 자유도 5.';
    }
    original.addEventListener('click',()=>render(false));
    changes.addEventListener('click',()=>render(true));
    render(false);
    panel.hidden=false;
  }
}
