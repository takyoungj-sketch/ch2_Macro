export function weightedMean(aShare) {
  return 100 * aShare + 200 * (1 - aShare);
}

export function samplingBias(expectedMean, targetMean) {
  return expectedMean - targetMean;
}

if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('smp-data').textContent);
  let stage = 'population';
  let source = 'population';
  let sampleSize = 5;
  let design = 'draw';
  let mix = 80;

  const stageCopy = {
    population: '모집단 100건입니다. A 80건(80%), B 20건(20%), 평균 120만원/㎡입니다. 이 가운데 A 60건은 표집틀에 없습니다.',
    frame: '표집틀 40건입니다. A 20건(50%), B 20건(50%), 평균 150만원/㎡입니다. 목록에 없는 A 60건은 이 목록에서 무작위로 뽑을 수 없습니다.',
    sample: '예시 표본 20건은 A 10건·B 10건으로 고정한 교육용 결과입니다. 평균은 150만원/㎡입니다. 표집틀에서 20건을 뽑을 때마다 10건씩 나온다는 뜻은 아닙니다.',
  };

  function money(value) {
    return (Math.round(value * 100) / 100).toLocaleString('ko-KR', { maximumFractionDigits: 2 });
  }

  function renderStage() {
    document.querySelectorAll('#smp-flow [data-stage], #smp-composition [data-stage]').forEach((node) => {
      const on = node.dataset.stage === stage;
      if (node.dataset.role === 'hit') {
        node.setAttribute('fill', on ? '#fff7ed' : '#ffffff');
        node.setAttribute('stroke', on ? '#d97706' : '#94a3b8');
        node.setAttribute('stroke-width', on ? '3' : '1');
      } else {
        node.setAttribute('stroke', on ? '#d97706' : '#64748b');
        node.setAttribute('stroke-width', on ? '3' : '1');
      }
    });
    document.querySelectorAll('[data-stage-button]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.stageButton === stage ? 'true' : 'false');
    });
    const status = document.getElementById('smp-stage-status');
    const extra = stage === 'sample'
      ? ' 이 10대10은 그림 3의 반복표집 분포가 아닙니다.'
      : ' 그림 3은 같은 추출 범위의 반복분포를 표시합니다.';
    status.textContent = stageCopy[stage] + extra;
  }

  function renderRepeat() {
    document.querySelectorAll('#smp-repeat rect').forEach((node) => {
      const on = node.dataset.source === source && Number(node.dataset.n) === sampleSize;
      node.setAttribute('stroke', on ? '#d97706' : '#1e3a8a');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('[data-source-button]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.sourceButton === source ? 'true' : 'false');
    });
    document.querySelectorAll('[data-n-button]').forEach((button) => {
      button.setAttribute('aria-pressed', Number(button.dataset.nButton) === sampleSize ? 'true' : 'false');
    });
    const trial = data.trials.find((item) => item.source === source && item.n === sampleSize);
    const where = source === 'population' ? '모집단 100건' : '표집틀 40건';
    const center = source === 'population' ? 120 : 150;
    const spread = sampleSize === 20
      ? '같은 범위에서 5건보다 20건일 때 표본평균이 덜 퍼집니다.'
      : '5건은 20건보다 표본평균이 더 넓게 퍼집니다.';
    const centerText = source === 'population'
      ? '중심은 모집단 평균 120 쪽입니다.'
      : '중심은 표집틀 평균 150 쪽이며, 표본수를 늘려도 120으로 이동하지 않습니다.';
    document.getElementById('smp-repeat-status').textContent =
      `${where}에서 ${sampleSize}건을 비복원으로 500회 다시 뽑았습니다. 반복평균 ${money(trial.mean)}만원/㎡, 반복 표준편차 ${money(trial.sd)}입니다. 추출 대상의 평균은 ${center}입니다. ${spread} ${centerText} 이 표준편차는 시드 20261007의 500회 결과입니다.`;
  }

  function renderMix() {
    const mean = weightedMean(mix / 100);
    document.getElementById('smp-mix-status').textContent =
      `실험 계산입니다. A ${mix}% · B ${100 - mix}% · 평균 ${money(mean)}만원/㎡. 모집단 80대20과 표집틀 20대20은 바꾸지 않습니다.`;
    const input = document.getElementById('smp-mix');
    input.value = String(mix);
    input.setAttribute('aria-valuetext', `A ${mix}%`);
    document.querySelectorAll('[data-mix]').forEach((button) => {
      button.setAttribute('aria-pressed', Number(button.dataset.mix) === mix ? 'true' : 'false');
    });
  }

  function renderDesign() {
    document.querySelectorAll('#smp-design [data-design]').forEach((node) => {
      const on = node.dataset.design === design;
      node.setAttribute('fill', on ? '#fff7ed' : '#eff6ff');
      node.setAttribute('stroke', on ? '#d97706' : '#94a3b8');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('[data-design-button]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.designButton === design ? 'true' : 'false');
    });
    document.getElementById('smp-design-status').textContent = design === 'draw'
      ? '무작위 추출은 누구를 조사할지의 문제입니다. 목표 모집단에서 고르면 그 범위로 일반화하는 데 도움이 됩니다. 처치의 원인을 확인해 주지는 않습니다.'
      : '무작위 배정은 참여한 대상에게 어떤 처치를 둘지의 문제입니다. 참여 건물 20채를 두 안내 방식에 나누는 예제이며, 절전 효과의 수치는 두지 않았습니다. 자발적 참여 집단이 전체 건물을 대표하지는 않습니다.';
  }

  function render() {
    renderStage();
    renderRepeat();
    renderMix();
    renderDesign();
  }

  document.querySelectorAll('[data-stage-button], #smp-flow [data-stage], #smp-composition [data-stage]').forEach((node) => {
    node.addEventListener('click', () => {
      stage = node.dataset.stageButton || node.dataset.stage;
      if (stage === 'population' || stage === 'frame') source = stage;
      render();
    });
  });
  document.querySelectorAll('[data-source-button]').forEach((button) => {
    button.addEventListener('click', () => {
      source = button.dataset.sourceButton;
      if (stage !== 'sample') stage = source;
      render();
    });
  });
  document.querySelectorAll('[data-n-button]').forEach((button) => {
    button.addEventListener('click', () => {
      sampleSize = Number(button.dataset.nButton);
      render();
    });
  });
  document.querySelectorAll('#smp-repeat rect').forEach((node) => {
    node.addEventListener('click', () => {
      source = node.dataset.source;
      sampleSize = Number(node.dataset.n);
      if (stage !== 'sample') stage = source;
      render();
    });
  });
  document.querySelectorAll('[data-design-button], #smp-design [data-design]').forEach((node) => {
    node.addEventListener('click', () => {
      design = node.dataset.designButton || node.dataset.design;
      render();
    });
  });
  document.getElementById('smp-mix').addEventListener('input', (event) => {
    mix = Number(event.target.value);
    renderMix();
  });
  document.querySelectorAll('[data-mix]').forEach((button) => {
    button.addEventListener('click', () => {
      mix = Number(button.dataset.mix);
      renderMix();
    });
  });
  document.querySelectorAll('.smp-controls').forEach((node) => node.removeAttribute('hidden'));
  render();
}
