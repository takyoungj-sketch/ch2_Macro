export function predict(x, intercept, slope) {
  return intercept + slope * x;
}

export function rangeNote(x, xmin, xmax) {
  if (x < xmin || x > xmax) return 'out';
  return 'in';
}

export function versusThreshold(low, high, threshold) {
  if (threshold == null) return 'none';
  if (high < threshold) return 'below';
  if (low > threshold) return 'above';
  return 'overlap';
}

if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('read-data').textContent);
  let step = 0;
  let effect = 0;
  let procedure = 0;
  let xValue = 100;
  let threshold = null;

  const money = (value) => {
    const text = Math.abs(value) >= 100 ? value.toFixed(2) : value.toFixed(4);
    return text.replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '');
  };

  function renderStep() {
    document.querySelectorAll('#workflow rect').forEach((node) => {
      const on = Number(node.dataset.step) === step;
      node.setAttribute('stroke', on ? '#d97706' : '#94a3b8');
      node.setAttribute('stroke-width', on ? '3' : '1');
    });
    document.querySelectorAll('[data-step-button]').forEach((button) => {
      button.setAttribute('aria-pressed', Number(button.dataset.stepButton) === step ? 'true' : 'false');
    });
    const row = data.steps[step];
    document.getElementById('read-step-status').textContent =
      `${row.title}. 질문: ${row.ask} 흔들릴 수 있는 읽기: ${row.mistake} 판단: ${row.rule} 복습: ${row.review}`;
  }

  function renderEffect() {
    const row = data.effects[effect];
    document.querySelectorAll('#uncertainty [data-effect]').forEach((node) => {
      const on = Number(node.dataset.effect) === effect;
      node.setAttribute('stroke', on ? '#d97706' : '#2563eb');
      node.setAttribute('stroke-width', on ? '3' : '2');
    });
    document.querySelectorAll('[data-effect-button]').forEach((button) => {
      button.setAttribute('aria-pressed', Number(button.dataset.effectButton) === effect ? 'true' : 'false');
    });
    const line = document.getElementById('read-threshold');
    if (threshold == null) {
      line.setAttribute('visibility', 'hidden');
    } else {
      line.setAttribute('visibility', 'visible');
      const px = 48 + (threshold + 1) * 46;
      line.setAttribute('x1', px);
      line.setAttribute('x2', px);
    }
    document.querySelectorAll('[data-threshold]').forEach((button) => {
      const value = button.dataset.threshold;
      const on = (value === 'none' && threshold == null) || Number(value) === threshold;
      button.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    const crossesZero = row.low <= 0 && row.high >= 0;
    const stat = crossesZero
      ? '구간이 0을 포함합니다. 이 가상 구간만으로 효과가 없다고 확정하지 않습니다.'
      : '구간이 0을 포함하지 않습니다. 같은 검정과 구간이 대응하면 통계적으로 유의할 수 있지만, 그만큼 실무적으로 중요하다고 확정하지 않습니다.';
    const place = versusThreshold(row.low, row.high, threshold);
    const practical = threshold == null
      ? '업무상 기준선은 아직 정하지 않았습니다. 기준은 교육용이며 가상 추정치를 바꾸지 않습니다.'
      : `교육용 기준 ${threshold}: 구간은 기준보다 ${place === 'below' ? '아래에 있습니다' : place === 'above' ? '위에 있습니다' : '겹칩니다'}.`;
    document.getElementById('read-effect-status').textContent =
      `${row.label}. 추정 ${row.estimate}, 구간 ${row.low}~${row.high}. ${stat} ${practical} 이 그림은 공통 학습자료의 회귀계수가 아닙니다.`;
  }

  function renderProcedure() {
    document.querySelectorAll('#prediction rect').forEach((node) => {
      const on = Number(node.dataset.eval) === procedure;
      node.setAttribute('stroke', on ? '#d97706' : '#1e3a8a');
      node.setAttribute('stroke-width', on ? '3' : '0');
    });
    document.querySelectorAll('[data-eval-button]').forEach((button) => {
      button.setAttribute('aria-pressed', Number(button.dataset.evalButton) === procedure ? 'true' : 'false');
    });
    const row = data.procedures[procedure];
    document.getElementById('read-eval-status').textContent =
      `${row.name}. 학습: ${row.train}. 평가: ${row.test}. 평가 ${row.n}건, 적합 ${row.fits}번. MAE ${row.mae.toFixed(2)}. ${row.note}`;
  }

  function renderScope() {
    const yhat = predict(xValue, data.fit.intercept, data.fit.slope);
    const where = rangeNote(xValue, data.fit.xmin, data.fit.xmax);
    const near = data.xs.filter((value) => Math.abs(value - xValue) <= 20).length;
    const px = 28 + xValue * 0.86;
    const marker = document.getElementById('read-x');
    marker.setAttribute('x1', px);
    marker.setAttribute('x2', px);
    document.getElementById('read-x-label').setAttribute('x', Math.min(px + 6, 300));
    document.getElementById('read-x-label').textContent = `X=${xValue}`;
    document.querySelectorAll('[data-x]').forEach((button) => {
      button.setAttribute('aria-pressed', Number(button.dataset.x) === xValue ? 'true' : 'false');
    });
    const inputs = document.querySelectorAll('.read-x');
    inputs.forEach((input) => {
      if (document.activeElement !== input) input.value = String(xValue);
    });
    let caution = where === 'out'
      ? `이 값은 관측 X 범위 ${data.fit.xmin}~${data.fit.xmax} 밖입니다. 식을 대입한 값이지 검증된 관계는 아닙니다.`
      : '이 값은 관측 X 범위 안입니다. 범위 안이라는 사실만으로 예측이 타당해지지는 않습니다.';
    if (yhat < data.fit.ymin) {
      caution += ` 예측값 ${yhat.toFixed(2)}은 관측 Y의 최솟값 ${data.fit.ymin}보다 낮습니다. 계산 오류로 단정하지 않고, 그 구간의 관측 밀도와 직선 형태를 함께 봅니다.`;
    }
    document.getElementById('read-scope-status').textContent =
      `입력 X=${xValue}. 반올림 전 계수로 계산한 Ŷ=${yhat.toFixed(2)}. ${caution} X±20 안에 관측 ${near}건이 있습니다. 번호는 거래 시점이 아닙니다.`;
  }

  document.querySelectorAll('[data-step-button], #workflow rect').forEach((node) => {
    node.addEventListener('click', () => {
      step = Number(node.dataset.stepButton ?? node.dataset.step);
      renderStep();
    });
  });
  document.querySelectorAll('[data-effect-button], #uncertainty [data-effect]').forEach((button) => {
    button.addEventListener('click', () => {
      effect = Number(button.dataset.effectButton ?? button.dataset.effect);
      renderEffect();
    });
  });
  document.querySelectorAll('[data-threshold]').forEach((button) => {
    button.addEventListener('click', () => {
      threshold = button.dataset.threshold === 'none' ? null : Number(button.dataset.threshold);
      renderEffect();
    });
  });
  document.querySelectorAll('[data-eval-button], #prediction rect').forEach((node) => {
    node.addEventListener('click', () => {
      procedure = Number(node.dataset.evalButton ?? node.dataset.eval);
      renderProcedure();
    });
  });
  document.querySelectorAll('[data-x]').forEach((button) => {
    button.addEventListener('click', () => {
      xValue = Number(button.dataset.x);
      renderScope();
    });
  });
  document.querySelectorAll('.read-x').forEach((input) => {
    input.addEventListener('input', () => {
      const value = Number(input.value);
      if (!Number.isFinite(value)) return;
      xValue = value;
      renderScope();
    });
  });
  document.querySelectorAll('.read-controls').forEach((node) => node.removeAttribute('hidden'));
  renderStep();
  renderEffect();
  renderProcedure();
  renderScope();
}
