// Chapter-only views of stored, separately fitted fold models.
export function foldPredictions(fold, rows) {
  return fold.validation_ids.map((id, i) => {
    const row = rows.find(r => r.id === id), predicted = fold.predictions[i];
    return { id, x: row.area, actual: row.price, predicted, error: row.price - predicted };
  });
}
export function collectOOF(folds, rows) {
  return folds.flatMap(fold => foldPredictions(fold, rows)).sort((a, b) => a.id - b.id);
}
if (typeof document !== 'undefined') {
  const { folds, rows } = JSON.parse(document.getElementById('cv-data').textContent);
  const select = document.getElementById('cv-fold');
  function updateFold() {
    const fold = folds.find(f => f.fold === Number(select.value));
    const predictions = foldPredictions(fold, rows);
    const formula = `ŷ=${fold.intercept.toFixed(3)}−${Math.abs(fold.slope).toFixed(4)}X`;
    const status = `${fold.fold}폴드 · 학습 ${fold.train_ids.length}건 / 검증 ${predictions.length}건 · ${formula} · 검증 MAE ${fold.metrics.MAE.toFixed(2)}. 이 검증 관측은 해당 모형의 학습에 사용되지 않았습니다. 번호 분할은 시간순 검증이 아닙니다.`;
    document.getElementById('cv-fold-status').textContent = status;
    document.getElementById('cv-score-status').textContent = `${status} 파랑·주황은 학습·검증의 실제값, 빈 원은 검증 예측입니다. 학습 적합값을 OOF라고 표시하지 않습니다.`;
    const blocks = document.getElementById('cv-blocks');
    blocks.replaceChildren(...['A: 1~10번', 'B: 11~20번', 'C: 21~30번'].map((label, i) => {
      const block = document.createElement('div'), validation = i + 1 === fold.fold;
      block.className = validation ? 'cv-block cv-block--validation' : 'cv-block';
      block.textContent = `${label} · ${validation ? '검증' : '학습'}`;
      return block;
    }));
    document.querySelectorAll('[data-fold-row]').forEach(group => group.querySelectorAll('rect').forEach(rect => {
      rect.setAttribute('stroke', Number(group.dataset.foldRow) === fold.fold ? '#0f766e' : 'none');
      rect.setAttribute('stroke-width', '3');
    }));
    document.querySelectorAll('[data-fold-bar]').forEach(bar => {
      bar.setAttribute('stroke', Number(bar.dataset.foldBar) === fold.fold ? '#0f766e' : 'none');
      bar.setAttribute('stroke-width', '3');
    });
    document.querySelectorAll('[data-fold-scatter]').forEach(group => group.toggleAttribute('hidden', Number(group.dataset.foldScatter) !== fold.fold));
    document.getElementById('folds-desc').textContent = status;
    document.getElementById('scores-desc').textContent = document.getElementById('cv-score-status').textContent;
    const table = document.createElement('table'), head = table.createTHead().insertRow();
    ['관측', 'X', '실제 Y', 'OOF 예측', '오차 Y−예측'].forEach(label => {
      const th = document.createElement('th'); th.scope = 'col'; th.textContent = label; head.append(th);
    });
    const body = table.createTBody();
    predictions.forEach(p => {
      const row = body.insertRow();
      [p.id, p.x, p.actual, p.predicted.toFixed(4), p.error.toFixed(4)].forEach(value => { row.insertCell().textContent = value; });
    });
    document.getElementById('cv-predictions').replaceChildren(table);
  }
  const stage = document.getElementById('cv-stage');
  const stages = {
    split: ['train', 'evaluation', '바깥 학습과 평가를 먼저 분리합니다. 바깥 평가자료는 선택과 전처리에서 분리해 둡니다.'],
    inner: ['inner', '안쪽 CV는 바깥 학습자료 안에서만 수행합니다. 각 안쪽 학습 부분으로 전처리·모형을 적합해 후보와 설정을 고릅니다.'],
    refit: ['refit', '고른 설정으로 바깥 학습자료 전체의 전처리·모형을 다시 적합합니다. 바깥 평가자료는 사용하지 않습니다.'],
    evaluation: ['evaluation', '고정한 절차로 바깥 평가자료를 예측합니다. 바깥 분리를 바꾸어 반복하며, 반복마다 다른 설정이 선택될 수 있습니다. 이 점수를 보고 후보를 다시 바꾸면 평가에도 선택이 개입합니다.']
  };
  function updateStage() {
    const description = stages[stage.value];
    document.getElementById('cv-stage-status').textContent = description.at(-1);
    document.querySelectorAll('[data-nested-part]').forEach(group => {
      const rect = group.querySelector('rect');
      rect.setAttribute('stroke', description.slice(0, -1).includes(group.dataset.nestedPart) ? '#0f766e' : 'none');
      rect.setAttribute('stroke-width', '3');
    });
  }
  select.addEventListener('change', updateFold);
  stage.addEventListener('change', updateStage);
  updateFold(); updateStage();
  document.querySelectorAll('.cv-controls').forEach(control => { control.hidden = false; });
}
