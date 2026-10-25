// Independent chapter experiments; no calls to production regression APIs.
export function orthogonalCoefficients(z, lambda) {
  if (!Number.isFinite(lambda) || lambda < 0) throw new RangeError('λ must be nonnegative');
  return {
    ridge: z.map(value => value / (1 + lambda)),
    lasso: z.map(value => Math.abs(value) <= lambda ? 0 : Math.sign(value) * (Math.abs(value) - lambda))
  };
}
export function restoreCoefficients(fold) {
  const slope = fold.b / fold.xscale;
  return { slope, intercept: fold.ymean - slope * fold.xmean };
}
if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('reg-data').textContent);
  const slider = document.getElementById('reg-lambda');
  const candidate = document.getElementById('reg-cv-lambda');
  const tuple = values => '(' + values.map(value => value.toFixed(4)).join(', ') + ')';
  function updateOrthogonal() {
    const lambda = Number(slider.value), result = orthogonalCoefficients(data.orthogonal.z, lambda);
    document.getElementById('reg-orthogonal-status').textContent = `직교 예제 λ=${lambda.toFixed(2)} · OLS ${tuple(data.orthogonal.z)} → 릿지 ${tuple(result.ridge)}. 절편은 규제하지 않습니다. 같은 비율 축소는 이 직교 조건의 결과입니다.`;
    document.getElementById('reg-lasso-status').textContent = `같은 직교 예제 λ=${lambda.toFixed(2)} · 라쏘 ${tuple(result.lasso)} · 0인 계수 ${result.lasso.filter(value => value === 0).length}개. 계수 0은 실제 영향이 없다는 증거가 아닙니다. 같은 λ 숫자도 L1·L2에서 동일한 실질 강도를 뜻하지 않습니다.`;
    document.querySelectorAll('[data-current-method]').forEach(point => {
      point.setAttribute('cx', 70 + lambda * 120);
      point.setAttribute('cy', 290 - result[point.dataset.currentMethod][Number(point.dataset.currentIndex)] * 70);
    });
    ['ridge', 'lasso'].forEach(method => {
      const guide = document.querySelector(`[data-lambda-guide="${method}"]`);
      guide.setAttribute('x1', 70 + lambda * 120); guide.setAttribute('x2', 70 + lambda * 120);
      document.getElementById(`${method}-current-label`).textContent = `현재 λ=${lambda.toFixed(2)}`;
      document.getElementById(`${method}-desc`).textContent = document.getElementById(method === 'ridge' ? 'reg-orthogonal-status' : 'reg-lasso-status').textContent;
    });
  }
  function updateCV() {
    const selected = data.cv.find(item => item.lam === Number(candidate.value));
    const best = data.cv.reduce((a, b) => a.RMSE <= b.RMSE ? a : b);
    const foldText = selected.folds.map(f => `${f.fold}폴드 ${Math.sqrt(f.MSE).toFixed(2)}`).join(' / ');
    document.getElementById('reg-cv-status').textContent = `공통 단일 변수 릿지 λ=${selected.lam} · 전체 OOF RMSE ${selected.RMSE.toFixed(2)} · ${foldText}. ${selected.lam === 0 ? '규제 없는 OLS 최소화 문제입니다.' : '기울기에 L2 규제를 적용합니다.'} ${selected === best ? '네 후보 중 가장 낮습니다.' : `현재 네 후보 중 최소는 λ=${best.lam}입니다.`} 선택용 점수이며 독립 시험 성능이 아닙니다. 그림 1·2의 λ는 바꾸지 않습니다.`;
    document.querySelectorAll('[data-cv-lambda]').forEach(bar => {
      bar.setAttribute('stroke', Number(bar.dataset.cvLambda) === selected.lam ? '#0f766e' : 'none');
      bar.setAttribute('stroke-width', '3');
    });
    const table = document.createElement('table'), head = table.createTHead().insertRow();
    ['폴드', '학습 X 평균', '학습 X SD', '표준화 기울기 b', '원 단위 β₁', '원 단위 β₀', '검증 RMSE'].forEach(label => {
      const th = document.createElement('th'); th.scope = 'col'; th.textContent = label; head.append(th);
    });
    const body = table.createTBody();
    selected.folds.forEach(f => {
      const restored = restoreCoefficients(f), row = body.insertRow();
      [f.fold, f.xmean.toFixed(4), f.xscale.toFixed(4), f.b.toFixed(4), restored.slope.toFixed(4), restored.intercept.toFixed(4), Math.sqrt(f.MSE).toFixed(2)].forEach(value => { row.insertCell().textContent = value; });
    });
    document.getElementById('reg-cv-table').replaceChildren(table);
    document.getElementById('cv-desc').textContent = document.getElementById('reg-cv-status').textContent;
  }
  slider.addEventListener('input', updateOrthogonal);
  candidate.addEventListener('change', updateCV);
  document.querySelectorAll('[data-orthogonal-lambda]').forEach(button => button.addEventListener('click', () => {
    slider.value = button.dataset.orthogonalLambda; updateOrthogonal();
  }));
  updateOrthogonal(); updateCV();
  document.querySelectorAll('.reg-controls').forEach(control => { control.hidden = false; });
}
