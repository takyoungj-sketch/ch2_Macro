// Chapter 28 illustrations only. No production regression or classification APIs.
export function sigmoidAt(x) {
  const eta = -2 + 0.8 * x;
  const p = 1 / (1 + Math.exp(-eta));
  return { eta, p, q: 1 - p, odds: p / (1 - p), slope: 0.8 * p * (1 - p) };
}

export function oddsShift(p, ratio = 2) {
  if (!(p > 0 && p < 1) || !(ratio > 0)) throw new RangeError('probability and odds ratio must be positive and probability below 1');
  const beforeOdds = p / (1 - p);
  const after = (ratio * p) / (1 - p + ratio * p);
  return { before: p, beforeOdds, ratio, afterOdds: beforeOdds * ratio, after, deltaPp: (after - p) * 100 };
}

export function confusionAt(probabilities, labels, threshold) {
  let TP = 0, FP = 0, FN = 0, TN = 0;
  const rows = probabilities.map((p, index) => {
    const y = labels[index];
    const pred = p >= threshold ? 1 : 0;
    if (y === 1 && pred === 1) TP += 1;
    else if (y === 0 && pred === 1) FP += 1;
    else if (y === 1 && pred === 0) FN += 1;
    else TN += 1;
    return { id: index + 1, p, y, pred };
  });
  const n = probabilities.length;
  const ratio = (num, den) => den === 0 ? null : num / den;
  return {
    TP, FP, FN, TN,
    accuracy: (TP + TN) / n,
    precision: ratio(TP, TP + FP),
    recall: ratio(TP, TP + FN),
    specificity: ratio(TN, TN + FP),
    f1: ratio(2 * TP, 2 * TP + FP + FN),
    rows
  };
}

export function pointLoss(y, p) {
  if (!(p > 0 && p < 1) || (y !== 0 && y !== 1)) throw new RangeError('loss is defined for y in {0,1} and p strictly between 0 and 1');
  return { logLoss: -(y * Math.log(p) + (1 - y) * Math.log(1 - p)), brier: (y - p) ** 2 };
}

export function rocAuc(probabilities, labels) {
  let score = 0, pairs = 0;
  probabilities.forEach((positive, i) => {
    if (labels[i] !== 1) return;
    probabilities.forEach((negative, j) => {
      if (labels[j] !== 0) return;
      pairs += 1;
      if (positive > negative) score += 1;
      else if (positive === negative) score += 0.5;
    });
  });
  return pairs === 0 ? null : score / pairs;
}

if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('cls-data').textContent);
  const xSlider = document.getElementById('cls-x');
  const p0Slider = document.getElementById('cls-p0');
  const threshold = document.getElementById('cls-threshold');
  const lossP = document.getElementById('cls-loss-p');
  const formatRate = value => value == null ? '정의되지 않음' : `${(value * 100).toFixed(2)}%`;
  const formatCount = value => String(value);

  function updateSigmoid() {
    const x = Number(xSlider.value);
    const result = sigmoidAt(x);
    const point = document.getElementById('cls-sigmoid-point');
    const guide = document.getElementById('cls-sigmoid-guide');
    point.setAttribute('cx', 70 + x * 100);
    point.setAttribute('cy', 320 - result.p * 250);
    guide.setAttribute('x1', 70 + x * 100);
    guide.setAttribute('x2', 70 + x * 100);
    guide.setAttribute('y2', 320 - result.p * 250);
    document.getElementById('cls-sigmoid-status').textContent = `그림 1의 가상식 η=−2+0.8X. X=${x.toFixed(1)}이면 η=${result.eta.toFixed(2)}, 양성 확률 ${result.p.toFixed(4)} (${(result.p * 100).toFixed(2)}%), 음성 확률 ${result.q.toFixed(4)}, 오즈 ${result.odds.toFixed(3)}. 이 지점의 확률 기울기 βp(1−p)=${result.slope.toFixed(4)}입니다. 계수 0.8은 확률이 0.8만큼 늘어난다는 뜻이 아니며, 오즈비 exp(0.8)=${Math.exp(0.8).toFixed(4)}입니다. 유한한 η에서 확률은 0과 1 사이입니다.`;
    document.getElementById('sigmoid-desc').textContent = document.getElementById('cls-sigmoid-status').textContent;
  }

  function updateOdds() {
    const p0 = Number(p0Slider.value);
    const result = oddsShift(p0, 2);
    document.querySelectorAll('[data-odds-p]').forEach(mark => {
      const on = Math.abs(Number(mark.dataset.oddsP) - p0) < 0.001;
      mark.setAttribute('stroke', on ? '#0f766e' : 'none');
      mark.setAttribute('stroke-width', on ? '3' : '0');
    });
    document.getElementById('cls-odds-status').textContent = `그림 2는 오즈비 2를 고정한 별도 예제입니다. 시작 확률 ${(result.before * 100).toFixed(0)}%, 시작 오즈 ${result.beforeOdds.toFixed(3)}, 새 오즈 ${result.afterOdds.toFixed(3)}, 새 확률 ${(result.after * 100).toFixed(2)}%, 변화 ${result.deltaPp.toFixed(2)}%p. 확률비는 ${(result.after / result.before).toFixed(3)}배이며 오즈비 2와 다릅니다. 그림 1의 오즈비 약 2.23과는 다른 예제이고, 조건부 오즈비를 인과효과로 읽지 않습니다.`;
    document.getElementById('odds-desc').textContent = document.getElementById('cls-odds-status').textContent;
  }

  function updateThreshold() {
    const t = Number(threshold.value);
    const result = confusionAt(data.probabilities, data.labels, t);
    document.getElementById('cls-live-title').textContent = `선택 임계값 ${t.toFixed(2)}`;
    ['TN', 'FP', 'FN', 'TP'].forEach(key => { document.getElementById(`cls-${key}`).textContent = formatCount(result[key]); });
    const metrics = `정확도 ${formatRate(result.accuracy)} · 정밀도 ${formatRate(result.precision)} · 재현율 ${formatRate(result.recall)} · 특이도 ${formatRate(result.specificity)} · F1 ${formatRate(result.f1)}`;
    document.getElementById('cls-live-metrics').textContent = `정밀도 ${formatRate(result.precision)} / 재현율 ${formatRate(result.recall)}`;
    const list = document.getElementById('cls-observations');
    list.replaceChildren();
    result.rows.forEach(row => {
      const item = document.createElement('li');
      const kind = row.y === 1 && row.pred === 1 ? 'TP' : row.y === 0 && row.pred === 1 ? 'FP' : row.y === 1 ? 'FN' : 'TN';
      item.textContent = `관측 ${row.id} · 예측확률 ${row.p.toFixed(2)} · 실제 ${row.y === 1 ? '양성' : '음성'} · 예측 ${row.pred === 1 ? '양성' : '음성'} · ${kind}`;
      list.append(item);
    });
    const undefinedNote = document.getElementById('cls-undefined');
    undefinedNote.hidden = result.precision != null;
    const fixed = confusionAt(data.probabilities, data.labels, 0.3);
    const sameAccuracy = Math.abs(result.accuracy - fixed.accuracy) < 1e-12;
    const comparison = Math.abs(t - 0.3) < 1e-9
      ? '선택한 임계값이 오른쪽 비교 기준과 같습니다. 0.5로 복원하면 정확도는 75%로 같고 재현율과 정밀도는 75%가 됩니다.'
      : (sameAccuracy ? '정확도는 오른쪽 0.3과 같습니다. 오탐과 누락의 구성은 다를 수 있습니다.' : '정확도는 오른쪽 0.3과 다릅니다.');
    document.getElementById('cls-threshold-status').textContent = `양성 판정은 p≥${t.toFixed(2)}입니다. ${metrics}. 오른쪽 비교 기준 0.3은 정확도 ${formatRate(fixed.accuracy)}, 정밀도 ${formatRate(fixed.precision)}, 재현율 ${formatRate(fixed.recall)}, 특이도 ${formatRate(fixed.specificity)}, F1 ${formatRate(fixed.f1)}입니다. ${comparison} 이 8건으로 운영 임계값을 정하지 않으며, 그림 4의 손실은 임계값과 연동되지 않습니다.`;
    document.getElementById('threshold-desc').textContent = document.getElementById('cls-threshold-status').textContent;
  }

  function updateLoss() {
    const y = Number(document.querySelector('[data-loss-y][aria-pressed="true"]').dataset.lossY);
    const p = Number(lossP.value);
    const result = pointLoss(y, p);
    const point = document.getElementById('cls-loss-point');
    point.setAttribute('cx', 70 + p * 500);
    point.setAttribute('cy', 320 - result.logLoss * 50);
    point.setAttribute('fill', y === 1 ? '#2563eb' : '#d97706');
    document.getElementById('cls-loss-status').textContent = `한 관측의 예시입니다. 실제 Y=${y}, 양성 예측확률 ${p.toFixed(2)}, 로그손실 ${result.logLoss.toFixed(4)}, 브라이어 손실 ${result.brier.toFixed(4)}. 자연로그를 사용하고 슬라이더는 0.01~0.99입니다. p가 0 또는 1이면 틀린 방향의 로그손실은 무한대이며, 화면의 유한한 끝값이 그 사실을 바꾸지 않습니다. 가상 8건의 평균 로그손실 0.4940과 브라이어 점수 0.1688은 이 슬라이더와 임계값을 바꿔도 그대로입니다. 두 점수의 숫자 크기를 서로 비교하지 않습니다.`;
    document.getElementById('loss-desc').textContent = document.getElementById('cls-loss-status').textContent;
  }

  xSlider.addEventListener('input', updateSigmoid);
  p0Slider.addEventListener('input', updateOdds);
  document.querySelectorAll('[data-odds-choice]').forEach(button => button.addEventListener('click', () => {
    p0Slider.value = button.dataset.oddsChoice;
    updateOdds();
  }));
  threshold.addEventListener('input', updateThreshold);
  document.querySelectorAll('[data-threshold-choice]').forEach(button => button.addEventListener('click', () => {
    threshold.value = button.dataset.thresholdChoice;
    updateThreshold();
  }));
  lossP.addEventListener('input', updateLoss);
  document.querySelectorAll('[data-loss-y]').forEach(button => button.addEventListener('click', () => {
    document.querySelectorAll('[data-loss-y]').forEach(item => item.setAttribute('aria-pressed', item === button ? 'true' : 'false'));
    updateLoss();
  }));
  updateSigmoid();
  updateOdds();
  updateThreshold();
  updateLoss();
  document.querySelectorAll('.cls-controls').forEach(control => { control.hidden = false; });
}
