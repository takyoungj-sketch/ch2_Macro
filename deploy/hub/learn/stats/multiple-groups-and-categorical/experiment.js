// Display proportions only. Test statistics continue to use the original counts.
export function proportions(counts, mode) {
  if (!['group', 'participants', 'total'].includes(mode)) throw new Error('Unknown proportion mode');
  const total = counts.flat().reduce((sum, n) => sum + n, 0);
  const participants = counts.reduce((sum, row) => sum + row[0], 0);
  return counts.map((row, i) => {
    const denominator = mode === 'group' ? row[0] + row[1] : mode === 'participants' ? participants : total;
    return { label: 'ABC'[i], denominator, counts: [...row], values: [row[0] / denominator, mode === 'participants' ? null : row[1] / denominator] };
  });
}

if (typeof document !== 'undefined') {
  const figure = document.getElementById('mg-proportions');
  if (figure) {
    const counts = JSON.parse(document.getElementById('mg-counts').textContent);
    const select = document.getElementById('mg-mode');
    const pct = value => `${(value * 100).toLocaleString('ko-KR', { maximumFractionDigits: 2 })}%`;
    const descriptions = {
      group: ['집단 내 참여·비참여 비율 · 분모: 각 집단 50명', '각 집단 50명이 분모입니다. 각 행의 합계는 100%입니다.', '각 행 합계 100%'],
      participants: ['전체 참여자 중 집단별 구성비 · 분모: 참여자 60명', '전체 참여자 60명이 분모입니다. A·B·C의 참여자 구성비 합계는 100%입니다. 비참여자는 이 보기에서 제외합니다.', '세 집단의 참여 비중 합계 100%'],
      total: ['전체 학생 중 집단별 참여·비참여 비율 · 분모: 150명', '전체 학생 150명이 분모입니다. 세 집단의 참여·비참여 여섯 칸 합계는 100%입니다.', '여섯 칸 합계 100%'],
    };
    function update() {
      const mode = select.value;
      const rows = proportions(counts, mode);
      rows.forEach((row, i) => {
        const [yes, no] = row.values;
        const bar = figure.querySelector(`[data-row="${i}"]`);
        bar.setAttribute('width', yes * 400);
        const other = figure.querySelector(`[data-non="${i}"]`);
        other.setAttribute('x', 150 + yes * 400);
        other.setAttribute('width', no === null ? 0 : no * 400);
        figure.querySelector(`[data-label="${i}"]`).textContent = `${row.label} · ${mode === 'participants' ? '참여 ' + row.counts[0] + '명' : row.counts.reduce((a, b) => a + b, 0) + '명'}`;
        figure.querySelector(`[data-ratio="${i}"]`).textContent = `참여 ${row.counts[0]}/${row.denominator} = ${pct(yes)}` + (no === null ? '' : ` · 비참여 ${row.counts[1]}/${row.denominator} = ${pct(no)}`);
      });
      const [heading, status, legend] = descriptions[mode];
      figure.querySelector('#mg-chart-heading').textContent = heading;
      document.getElementById('mg-status').textContent = status;
      figure.querySelector('#mg-legend').textContent = (mode === 'participants' ? '파랑: 참여 · ' : '파랑: 참여 · 회색: 비참여 · ') + legend;
      const caption = `그림 4. 학습용 가상 학생 150명. ${status} 앞의 시험 점수 12개와 별도 자료이며 원래 관측도수는 바뀌지 않습니다.`;
      figure.querySelector('figcaption').textContent = caption;
      figure.querySelector('#categorical-desc').textContent = caption;
    }
    select.addEventListener('change', update);
    update();
    figure.querySelector('.mg-controls').hidden = false;
  }
}
