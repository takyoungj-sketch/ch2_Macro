// Display stored chapter simulations; no sampling or production-analysis calls.
export function selectedSummary(models, degree) {
  return degree === 'all' ? null : models.find(model => model.degree === Number(degree));
}
if (typeof document !== 'undefined') {
  const models = JSON.parse(document.getElementById('overfit-data').textContent);
  const select = document.getElementById('overfit-degree');
  function update() {
    const selected = selectedSummary(models, select.value);
    document.querySelectorAll('#fits polyline[data-degree]').forEach(curve => {
      curve.toggleAttribute('hidden', !!selected && Number(curve.dataset.degree) !== selected.degree);
    });
    document.querySelectorAll('[data-error-degree]').forEach(point => {
      point.setAttribute('r', selected && Number(point.dataset.errorDegree) === selected.degree ? '8' : '4');
    });
    const first = document.getElementById('overfit-fit-status');
    const error = document.getElementById('overfit-error-status');
    const stability = document.getElementById('overfit-stability-status');
    if (selected) {
      first.textContent = `${selected.degree}차 · 절편 포함 계수 ${selected.degree + 1}개 · 첫 표본 학습 MSE ${selected.first_train_MSE.toFixed(5)}. 참 평균과 관측점 12개는 그대로입니다.`;
      error.textContent = `${selected.degree}차의 300회 평균 · 학습 MSE ${selected.train_MSE.toFixed(5)} / 새 관측 기대 MSE ${selected.expected_MSE.toFixed(5)}. 해당 차수의 점을 크게 표시했습니다. 시험 표본의 측정값은 아닙니다.`;
      stability.textContent = `${selected.degree}차 · X=0.8의 참 평균 2.248 · 전체 300회 예측 평균 ${selected.mean08.toFixed(5)} · 편향 ${selected.bias08.toFixed(5)} · 예측 분산 ${selected.variance08.toFixed(5)}. 그림의 점은 차수별 처음 30회만 표시합니다.`;
    } else {
      first.textContent = '전체 비교 · 같은 첫 번째 표본 12점에 1·2·5·9차를 적합했습니다. 점선은 가상 참 평균이며 X·Y는 단위가 없습니다.';
      error.textContent = '전체 차수의 300회 평균 · 학습 12개 위치 / 새 관측 기대오차 201개 위치 + 잡음분산 0.0225. 두 선의 간격 전체가 과적합의 크기는 아닙니다.';
      stability.textContent = '모든 차수의 처음 30회 예측을 같은 축에서 비교합니다. 통계량과 오차 분해는 전체 300회로 계산합니다. 참 평균 f(0.8)=2.248입니다.';
    }
    document.querySelector('#fits-desc').textContent = first.textContent;
    document.querySelector('#errors-desc').textContent = error.textContent;
  }
  select.addEventListener('change', update);
  update();
  select.closest('.overfit-controls').hidden = false;
}
