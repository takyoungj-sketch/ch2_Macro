"""Chapter 27: explicit penalty normalization and coefficient paths."""
from pathlib import Path
from statistics import mean,pstdev
from html import escape
import math,json,re
ROOT=Path(__file__).resolve().parent

def build():
 z=[3,1,-.5];path=[dict(lam=i/25,ridge=[v/(1+i/25) for v in z],lasso=[math.copysign(max(abs(v)-i/25,0),v) for v in z]) for i in range(101)]
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];cv=[]
 for lam in [0,.1,1,10]:
  folds=[]
  for k in range(3):
   va=rows[k*10:(k+1)*10];tr=rows[:k*10]+rows[(k+1)*10:];xm=mean(r['area'] for r in tr);xs=pstdev(r['area'] for r in tr);ym=mean(r['price'] for r in tr);cov=mean((r['area']-xm)/xs*(r['price']-ym) for r in tr);b=cov/(1+lam);pred=[ym+b*(r['area']-xm)/xs for r in va];mse=mean((r['price']-v)**2 for r,v in zip(va,pred));folds.append(dict(fold=k+1,xmean=xm,xscale=xs,ymean=ym,b=b,predictions=pred,MSE=mse))
  cv.append(dict(lam=lam,folds=folds,RMSE=math.sqrt(mean(f['MSE'] for f in folds))))
 best=min(cv,key=lambda v:v['RMSE'])
 d=dict(description='직교 가상 예제와 공통 자료의 면적 단일 변수 릿지 3폴드. 최종 성능 평가 아님.',normalization='SSE/(2n)+lambda*L2_squared/2 or SSE/(2n)+lambda*L1; intercept excluded',orthogonal=dict(z=z,path=path),cv=cv,best_lambda=best['lam'])
 (ROOT/'regularization-example.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def ln(x,y,a,b):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="#94a3b8"/>'
 def fig(id,title,b,cap):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 410" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 colors=['#2563eb','#d97706','#16a34a'];charts=[]
 for key,label in [('ridge','릿지'),('lasso','라쏘')]:
  b=tx(24,28,f'직교 가상 예제: {label} 계수 경로')+ln(70,290,570,290)+ln(70,55,70,335)
  for j,c in enumerate(colors):b+='<polyline data-index="'+str(j)+'" points="'+' '.join(f"{70+r['lam']*120},{290-r[key][j]*70}" for r in path)+'" fill="none" stroke="'+c+'" stroke-width="2"/>'
  for v in [0,1,2,3,4]:b+=tx(65+v*120,355,v)
  for v in [-.5,0,1,2,3]:b+=tx(25,295-v*70,v)
  b+=tx(24,390,'가로 λ / 세로 계수 · 파랑 z=3, 주황 z=1, 초록 z=−0.5')
  charts.append(fig(key,label+' 계수 경로',b,'그림 '+('1' if key=='ridge' else '2')+'. ZᵀZ/n=I인 별도 가상 조건에서 계산한 경로입니다. 실제 상관된 변수의 계수 경로가 항상 이 모양이거나 각 계수 절댓값이 단조 감소하는 것은 아닙니다.'))
 b=tx(24,28,'두 계수의 제약 영역: 반지름·한계값을 1로 둔 개념도')
 for cx,label in [(180,'릿지: b₁²+b₂² ≤ 1'),(470,'라쏘: |b₁|+|b₂| ≤ 1')]:b+=ln(cx-110,205,cx+110,205)+ln(cx,95,cx,315)+tx(cx-105,365,label)+tx(cx+95,227,'b₁')+tx(cx+10,100,'b₂')
 b+='<circle cx="180" cy="205" r="85" fill="#dbeafe" fill-opacity=".6" stroke="#2563eb"/><polygon points="470,120 555,205 470,290 385,205" fill="#ffedd5" fill-opacity=".6" stroke="#d97706"/>'
 charts.append(fig('geometry','L2와 L1 제약',b,'그림 3. 라쏘의 꼭짓점은 한 계수가 0인 축에 놓입니다. 손실 등고선과 만나는 위치에 따라 0인 계수가 생길 수 있음을 돕는 개념도이며 λ=1의 해를 그린 것은 아닙니다.'))
 ymax=max(v['RMSE'] for v in cv)*1.2;b=tx(24,28,'공통 자료: 면적 단일 변수 릿지의 3폴드 OOF RMSE')+ln(70,320,570,320)
 for i,v in enumerate(cv):
  h=v['RMSE']/ymax*240;xx=110+i*130;b+=f'<rect x="{xx}" y="{320-h}" width="65" height="{h}" fill="#2563eb"/>'+tx(xx+4,308-h,f'{v["RMSE"]:.2f}')+tx(xx+4,350,f'λ={v["lam"]}')
 for v in [0,40,80]:b+=tx(25,325-v/ymax*240,v)
 b+=tx(24,390,'세로: 만원/㎡ · 각 폴드의 학습 부분에서만 면적 표준화')
 charts.append(fig('cv','규제 강도와 검증 오차',b,'그림 4. 번호 블록 3폴드의 교재용 비교입니다. 단일 변수 릿지이며 라쏘·다중공선성 성능 실험은 아닙니다. 선택에 사용한 점수를 독립 최종 성능으로 읽지 않습니다.'))
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','규제의 목적','적합 오차에 계수 크기의 벌점을 더합니다','<p>OLS는 학습 잔차제곱합만 최소화합니다. 설명변수가 많거나 서로 강하게 겹치면 계수가 표본의 작은 변화에도 크게 움직일 수 있습니다. 규제는 계수 크기에 벌점을 주어 적합과 안정성 사이를 조절하는 방법입니다.</p><p>일부 편향을 감수하고 예측 분산을 줄여 새 자료 오차를 낮추려는 선택이지만 항상 개선되는 것은 아닙니다. 너무 강한 규제는 중요한 관계도 눌러 과소적합을 만들 수 있습니다. 누락변수·측정오차·인과 식별 문제를 자동으로 해결하는 방법도 아닙니다.</p>')
 sec('objective','산식과 λ','정규화 규칙을 먼저 고정합니다','<p>이 장에서는 표준화된 설명변수 Z를 사용하고 절편은 벌점에서 제외합니다. 릿지는 <strong>SSE/(2n)+(λ/2)Σbⱼ²</strong>, 라쏘는 <strong>SSE/(2n)+λΣ|bⱼ|</strong>를 최소화합니다. λ≥0이며 벌점 합에는 절편이 들어가지 않습니다.</p><p>λ=0은 규제 없는 최소제곱 문제입니다. λ가 커지면 계수 크기에 더 큰 비용을 부과합니다. 소프트웨어마다 SSE 앞의 1/n·1/2와 벌점 계수가 다르므로 숫자 λ만 비교하지 않습니다. 예컨대 SSE+αΣbⱼ²의 릿지는 이 장의 α=nλ에 해당합니다.</p><p>설명변수를 중심화하면 절편은 Y 평균이 됩니다. 절편까지 강제로 0 쪽으로 줄이면 자료의 기준 수준도 바뀌므로 보통 별도로 취급합니다.</p>')
 sec('ridge','릿지의 축소','계수를 부드럽게 줄여 함께 사용합니다','<p>릿지는 L2 제곱 벌점을 씁니다. 중심화된 자료에서 해는 b=(ZᵀZ+nλI)⁻¹Zᵀy입니다. λ&gt;0이면 설명변수 열이 중복되어도 계수 해를 고유하게 정할 수 있습니다. 다만 식별되지 않은 인과효과를 알아냈다는 뜻은 아닙니다.</p>'+charts[0]+'<p>이 그림은 ZᵀZ/n=I, 규제 없는 계수 z=(3,1,−0.5)인 직교 예제입니다. 릿지 해는 bⱼ=zⱼ/(1+λ)이므로 λ=1에서 (1.5,0.5,−0.25)입니다. 유한한 λ에서 일반적으로 계수를 정확히 0으로 만들지는 않습니다.</p><p>실제 변수들이 상관되어 있으면 모든 계수를 같은 비율로 줄이는 공식은 성립하지 않습니다. 총 L2 크기를 제약하는 것과 각 계수가 반드시 단조롭게 줄어드는 것은 구별합니다.</p>')
 sec('lasso','라쏘의 축소','일부 계수를 정확히 0으로 만들 수 있습니다','<p>라쏘는 L1 벌점을 사용해 희소한 계수, 즉 일부 계수가 0인 해를 만들 수 있습니다. 계수 0은 선택한 표본·스케일·λ 아래에서 그 항을 쓰지 않았다는 뜻이며 실제 영향이 전혀 없다는 증거는 아닙니다.</p>'+charts[1]+'<p>같은 직교 예제의 해는 <strong>bⱼ=sign(zⱼ)max(|zⱼ|−λ,0)</strong>인 소프트 임계값입니다. λ=1에서 (2,0,0), λ≥3에서는 세 계수가 모두 0입니다. 이 간단한 항별 공식은 직교 조건에서만 직접 적용합니다.</p><p>상관된 변수들이 비슷한 정보를 담으면 어느 변수가 남는지 표본에 민감할 수 있습니다. 완전 공선성 등에서는 계수 해가 유일하지 않을 수 있으므로 ‘선택된 변수 목록’을 확정적인 과학적 발견으로 해석하지 않습니다.</p>')
 sec('geometry','기하적 이해','L1의 모서리가 희소성의 직관을 줍니다','<p>벌점형 문제는 적절히 대응하는 한계값에서 계수 크기에 제약을 둔 문제로도 볼 수 있습니다. 릿지의 L2 영역은 원형, 라쏘의 L1 영역은 마름모 모양입니다.</p>'+charts[2]+'<p>라쏘는 축 위의 꼭짓점에서 최적점이 나올 수 있어 0 계수가 생기는 직관을 줍니다. 모든 자료·모든 λ에서 변수가 삭제된다는 뜻은 아닙니다. 두 제약 영역의 크기를 같게 그렸다고 같은 규제 강도라는 뜻도 아닙니다.</p>')
 sec('scale','표준화와 단위','벌점은 계수의 숫자 크기에 반응합니다','<p>면적을 ㎡에서 다른 단위로 바꾸면 같은 예측식을 표현하는 계수 숫자도 바뀝니다. 벌점은 그 숫자를 사용하므로 스케일을 맞추지 않으면 단위 선택에 따라 규제 결과가 달라질 수 있습니다.</p><p>연속변수는 보통 학습 평균과 표준편차로 Zⱼ=(Xⱼ−평균)/표준편차로 변환합니다. 교차검증에서는 매 폴드의 학습 부분에서 기준을 추정해야 합니다. 상수 열은 표준편차가 0이므로 별도 처리하며, 더미변수의 스케일 선택도 분석 목적에 맞춰 정합니다.</p><p>원 단위 계수는 bⱼ/표준편차ⱼ로 복원하고, 절편도 평균 이동을 반영해야 합니다. 표준화된 계수 크기만으로 인과적 중요성을 순위 매기지 않습니다.</p>')
 sec('cv','강도 선택','작은 λ와 큰 λ를 같은 분할에서 비교합니다',f'<p>공통 30건의 면적 하나로 단가를 예측하는 릿지를 번호 블록 3폴드로 비교합니다. 후보 λ는 0·0.1·1·10이고 주 지표는 전체 OOF RMSE입니다. 각 폴드에서 면적 평균·표준편차와 계수를 다시 학습합니다.</p>'+charts[3]+f'<p>이 네 후보 중 최소 점수는 λ={best["lam"]}, RMSE={best["RMSE"]:.2f}만원/㎡입니다. 이 결과는 규제가 항상 유리하거나 해당 λ가 다른 자료에도 적합하다는 근거가 아닙니다. 번호는 시간이 아니며 출처 미확인 학습 자료를 사용한 계산 연습입니다.</p><p>실제 탐색은 다양한 규모의 λ를 비교하되 전처리·후보 탐색을 학습 경계 안에 둡니다. 최저 CV 점수의 선택 편향을 고려해 독립 시험이나 중첩 평가를 사용합니다. 점수 차이가 작으면 안정성·해석·비용도 함께 고려합니다.</p>')
 sec('elastic','엘라스틱넷과 확장','L1과 L2를 함께 쓸 수도 있습니다','<p>엘라스틱넷은 SSE/(2n)+λ[ρΣ|bⱼ|+(1−ρ)Σbⱼ²/2]처럼 두 벌점을 섞습니다. 이 표기에서 ρ=1은 라쏘, ρ=0은 릿지이며 중간값은 두 성질을 결합합니다. λ와 혼합 비율 모두 선택 대상입니다.</p><p>상관된 변수에서 안정성과 희소성을 함께 고려할 때 검토할 수 있지만 자동으로 최선인 것은 아닙니다. 다항식·상호작용을 만든 뒤 규제할 수도 있으며, 어떤 항을 만들고 표준화했는지까지 모형 절차에 포함합니다.</p>')
 sec('interpretation','해석과 추론','축소된 계수를 OLS 검정표처럼 읽지 않습니다','<p>규제 계수는 벌점에 의해 의도적으로 축소되며 λ도 자료를 보고 선택하는 경우가 많습니다. 따라서 규제 후 계수에 일반 OLS 표준오차·p값을 그대로 붙이면 선택과 축소의 불확실성을 놓칠 수 있습니다.</p><p>라쏘로 고른 변수만 OLS에 다시 넣었다고 선택 이전의 고전적 추론 조건이 자동으로 회복되지 않습니다. 해석·인과 추론이 목적이라면 설계와 적절한 추론 방법을 별도로 정합니다. 예측 목적이라면 전체 절차의 검증 성능을 확인합니다.</p>')
 sec('practice','확인 문제','벌점의 대상과 선택 절차를 확인하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('릿지는 모든 계수를 같은 비율로 줄이나요?','직교·정규화된 예제에서는 그렇지만 일반적인 상관된 변수에서는 아닙니다.'),('라쏘 계수 0은 실제 영향이 없다는 증거인가요?','아니요. 표본·스케일·규제 강도에 따른 모형 선택의 결과입니다.'),('CV 전에 전체 자료로 표준화해도 되나요?','학습되는 변환은 각 폴드의 학습 부분에서 추정해야 합니다.'),('프로그램마다 λ=1이면 같은 모형인가요?','목적함수 정규화와 변수 스케일이 다를 수 있으므로 산식을 확인해야 합니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','규제 설정과 전처리를 함께 확인합니다','<p>모형 설명에서 벌점 종류·강도 선택 기준·변수 스케일·절편 처리·평가 설계를 함께 읽으세요. 이 장의 단일 변수 릿지 예제가 서비스에 구현된 산식이나 실제 성능이라고 전제하지 않습니다.</p><p>계수 축소나 변수 선택을 개별 적정가나 인과효과의 확정으로 해석하지 않습니다. 예측·설명 목적에 맞게 결과의 적용 범위를 확인합니다.</p>')
 sec('recap','정리와 참고자료','축소와 선택은 검증해야 하는 모형의 일부입니다','<p>릿지는 L2로 계수를 줄이고, 라쏘는 L1로 일부 계수를 0으로 만들 수 있습니다. 스케일·벌점 산식·검증 절차까지 함께 정해야 의미 있는 비교가 됩니다.</p><p>다음 <a href="/learn/stats/classification/">28장 「분류와 로지스틱 회귀」</a>에서 확률과 분류를 살펴봅니다.</p><ul><li><a href="https://scikit-learn.org/stable/modules/linear_model.html">scikit-learn: Ridge·Lasso·Elastic-Net</a></li><li><a href="../regularization-example.json">계수 경로와 폴드별 계산 자료</a></li></ul><p class="learn-source-note">본문·그림은 직교 가상 예제와 공통 학습 자료로 직접 작성했습니다. 참고자료 확인: 2026-10-09.</p>')
 p=ROOT/'regularization/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="규제: 릿지와 라쏘">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1릿지·라쏘의 벌점과 계수 경로, 표준화·규제 강도 선택·해석의 한계를 학습합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
