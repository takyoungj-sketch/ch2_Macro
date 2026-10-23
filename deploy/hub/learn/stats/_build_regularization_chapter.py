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
 d=dict(description='직교 가상 예제와 공통 자료의 X 단일 변수 릿지 3폴드. 최종 성능 평가 아님.',normalization='SSE/(2n)+lambda*L2_squared/2 or SSE/(2n)+lambda*L1; intercept excluded',orthogonal=dict(z=z,path=path),cv=cv,best_lambda=best['lam'])
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
 ymax=max(v['RMSE'] for v in cv)*1.2;b=tx(24,28,'공통 자료: X 단일 변수 릿지의 3폴드 OOF RMSE')+ln(70,320,570,320)
 for i,v in enumerate(cv):
  h=v['RMSE']/ymax*240;xx=110+i*130;b+=f'<rect x="{xx}" y="{320-h}" width="65" height="{h}" fill="#2563eb"/>'+tx(xx+4,308-h,f'{v["RMSE"]:.2f}')+tx(xx+4,350,f'λ={v["lam"]}')
 for v in [0,40,80]:b+=tx(25,325-v/ymax*240,v)
 b+=tx(24,390,'세로: Y와 같은 단위 · 각 폴드의 학습 부분에서만 X 표준화')
 charts.append(fig('cv','규제 강도와 검증 오차',b,'그림 4. 번호 블록 3폴드의 교재용 비교입니다. 단일 변수 릿지이며 라쏘·다중공선성 성능 실험은 아닙니다. 선택에 사용한 점수를 독립 최종 성능으로 읽지 않습니다.'))
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','학습 목표','잘 맞추는 것과 계수의 안정성을 함께 생각합니다','<p>설명변수가 많거나 비슷한 정보를 담고 있으면, 학습 자료를 조금 바꾸어도 회귀계수가 크게 달라질 수 있습니다. 학습 오차를 줄이는 것만으로는 새 자료에서 안정적으로 예측하기 어려운 경우입니다.</p><p>규제는 학습 오차에 계수 크기에 대한 벌점을 더하는 방법입니다. 이 장에서는 릿지와 라쏘가 계수를 어떻게 조절하는지 비교하고, 변수의 단위와 규제 강도를 정할 때 주의할 점을 살펴봅니다.</p><ul class="learn-objectives"><li>계수에 벌점을 주는 이유와 너무 강한 규제의 문제를 설명합니다.</li><li>릿지의 계수 축소와 라쏘의 변수 선택을 구별합니다.</li><li>표준화가 필요한 이유와 교차검증 안에서 수행할 위치를 이해합니다.</li><li>검증으로 규제 강도를 고르고 계수의 해석 범위를 설명합니다.</li></ul>')
 sec('purpose','핵심 이해','학습 오차만 줄이기보다 계수 크기도 고려합니다','<p>일반 최소제곱법(OLS)은 학습 잔차제곱합을 최소화합니다. 규제는 여기에 <strong>계수가 클수록 커지는 벌점</strong>을 더합니다. 오차를 조금 더 허용하더라도 계수를 지나치게 크게 만들지 않는 쪽을 선택할 수 있습니다.</p><p>24장의 표현으로는 일부 편향을 감수하는 대신 예측의 분산을 줄이려는 방법입니다. 새 자료의 오차가 줄어들 수 있지만 항상 좋아지는 것은 아닙니다. 규제가 너무 강하면 중요한 관계까지 약하게 표현해 과소적합할 수 있습니다.</p><p>규제는 빠진 변수를 찾아 주거나 측정 오류를 없애는 방법은 아닙니다. 계수를 안정적으로 정했다고 인과관계를 밝혀낸 것도 아닙니다.</p>')
 sec('objective','산식과 λ','규제 강도는 λ로 조절합니다','<p>이 장에서는 설명변수를 표준화하고 절편은 벌점에서 제외합니다. 학습 잔차제곱합을 SSE, 관측 수를 n, 계수를 bⱼ라고 하면 다음 값을 최소화합니다.</p><ul><li><strong>릿지:</strong> SSE/(2n) + (λ/2)Σbⱼ²</li><li><strong>라쏘:</strong> SSE/(2n) + λΣ|bⱼ|</li></ul><p>λ(람다)는 0 이상입니다. λ=0이면 규제 없는 최소제곱 문제이고, λ가 커질수록 계수 크기에 더 큰 비용을 둡니다. 어떤 λ를 쓸지는 검증으로 비교합니다.</p><p>절편은 예측의 기준 수준을 나타내므로 보통 벌점을 주지 않습니다. 설명변수를 평균 0으로 중심화하면, 이 설정에서 절편은 학습 Y의 평균이 됩니다.</p><details><summary>프로그램마다 λ를 바로 비교할 수 없는 이유</summary><p>소프트웨어마다 SSE 앞의 1/n·1/2나 벌점 앞의 계수가 다릅니다. 예를 들어 SSE+αΣbⱼ² 형태의 릿지에서 α는 이 장의 nλ에 해당합니다. 변수 스케일과 목적함수의 산식을 확인해야 같은 규제 강도인지 알 수 있습니다.</p></details>')
 sec('ridge','릿지의 축소','계수의 제곱에 벌점을 줍니다','<p>릿지는 계수의 제곱합을 벌점으로 쓰는 <strong>L2 규제</strong>입니다. 계수를 대체로 0 쪽으로 줄이면서 변수들을 함께 사용합니다. 유한한 규제 강도에서 일반적으로 계수를 정확히 0으로 만들지는 않습니다.</p>'+charts[0]+'<p>그림은 표준화된 변수들이 서로 직교하는 가상 예제입니다. 규제 없는 계수가 (3, 1, −0.5)일 때, 이 특별한 조건에서는 각 계수를 1+λ로 나눕니다. λ=1이면 (1.5, 0.5, −0.25)가 됩니다.</p><p>실제 변수들이 서로 상관되어 있으면 모든 계수를 같은 비율로 줄이는 공식은 성립하지 않습니다. 규제 강도를 높일 때 개별 계수의 절댓값이 매번 줄어든다고 가정해서도 안 됩니다.</p><details><summary>릿지 해의 식</summary><p>중심화한 자료에서 b=(ZᵀZ+nλI)⁻¹Zᵀy입니다. λ&gt;0이면 변수 열이 중복되어도 계수 해를 하나로 정할 수 있습니다. 그림은 ZᵀZ/n=I인 경우여서 bⱼ=zⱼ/(1+λ)이 됩니다. 여기서 zⱼ는 규제 없는 계수입니다. 계수 해가 하나라는 사실은 인과효과를 식별했다는 뜻이 아닙니다.</p></details>')
 sec('lasso','라쏘의 축소','일부 계수는 정확히 0이 될 수 있습니다','<p>라쏘는 계수의 절댓값 합을 벌점으로 쓰는 <strong>L1 규제</strong>입니다. 계수를 줄이다가 일부를 정확히 0으로 만들 수 있습니다. 계수가 0인 변수의 항은 예측식에서 빠지므로 변수 선택의 역할도 합니다.</p>'+charts[1]+'<p>같은 직교 예제에서는 각 계수의 절댓값에서 λ를 빼고, 0보다 작아지면 0으로 둡니다. 남은 값에는 원래 부호를 붙입니다. 규제 없는 계수가 (3, 1, −0.5)이므로 λ=1이면 (2, 0, 0), λ가 3 이상이면 모두 0입니다. 절편은 벌점에서 제외되어 그대로 별도로 추정합니다.</p><p><strong>계수 0은 실제 영향이 없다는 증거가 아닙니다.</strong> 그 표본과 변수 스케일, 규제 강도에서 해당 항을 사용하지 않았다는 뜻입니다. 비슷한 정보를 담은 변수들이 있으면 어느 변수가 남는지 자료에 따라 달라질 수 있습니다.</p><details><summary>소프트 임계값과 해의 조건</summary><p>이 직교 예제의 공식은 bⱼ=sign(zⱼ)max(|zⱼ|−λ,0)이며 소프트 임계값이라고 합니다. 일반적인 상관된 변수에 이 항별 공식을 바로 적용할 수는 없습니다. 완전 공선성 등이 있으면 라쏘 계수 해가 하나로 정해지지 않을 수도 있습니다.</p></details>')
 sec('geometry','그림으로 이해하기','라쏘의 꼭짓점은 계수가 0인 축에 놓입니다','<p>벌점을 더하는 대신 계수 크기가 일정한 한계를 넘지 못하도록 제한한다고 생각할 수도 있습니다. 두 계수만 그리면 릿지의 제약 영역은 원, 라쏘의 제약 영역은 마름모입니다.</p>'+charts[2]+'<p>마름모의 꼭짓점은 한 계수가 0인 축 위에 있습니다. 오차가 작아지는 방향으로 해를 찾을 때 이런 꼭짓점에서 최적점이 나올 수 있다는 것이 라쏘의 변수 선택을 이해하는 단서입니다.</p><p>모든 자료나 모든 λ에서 계수가 0이 되는 것은 아닙니다. 그림은 제약 영역만 보여 주는 개념도이며, 두 영역을 비슷한 크기로 그렸다고 같은 규제 강도라는 뜻도 아닙니다.</p>')
 sec('scale','표준화와 단위','같은 정보라도 단위가 바뀌면 계수 숫자가 바뀝니다','<p>학습 시간을 분으로 나타낼 때와 시간으로 나타낼 때는 같은 예측식을 써도 계수의 숫자가 다릅니다. 벌점은 그 숫자의 크기에 적용됩니다. 따라서 단위를 맞추지 않으면 단위 선택 자체가 규제 결과에 영향을 줄 수 있습니다.</p><p>연속변수는 보통 <strong>Zⱼ=(Xⱼ−학습 평균)/학습 표준편차</strong>로 표준화합니다. 교차검증에서는 각 폴드의 학습 부분에서 평균과 표준편차를 구하고 검증 부분에는 그 기준을 적용합니다. 표준편차가 0인 상수 열은 따로 처리해야 합니다. 범주를 나타내는 더미변수의 스케일도 목적에 맞게 정합니다.</p><p>원래 단위의 계수로 되돌리려면 표준화된 계수를 학습 표준편차로 나눕니다. 절편에는 평균을 옮긴 효과도 반영합니다. 표준화한 계수가 크다는 이유만으로 인과적으로 중요한 변수라고 판단할 수는 없습니다.</p>')
 sec('cv','강도 선택','같은 분할에서 여러 λ를 비교합니다',f'<p>공통 학습 자료의 두 수치 열을 단위 없는 X와 Y로 놓습니다. X 하나로 Y를 예측하는 릿지를 번호 블록 3폴드로 비교합니다. 후보 λ는 0·0.1·1·10이고 주 지표는 전체 OOF RMSE입니다. 각 반복에서 X의 평균·표준편차와 회귀계수를 학습 부분에서 다시 구합니다.</p>'+charts[3]+f'<p>이 네 후보 중 가장 작은 점수는 <strong>λ={best["lam"]}, RMSE={best["RMSE"]:.2f}</strong>입니다. RMSE는 Y와 같은 단위입니다. 이 결과가 규제의 개선을 보장하거나 다른 자료에도 같은 λ를 권한다는 뜻은 아닙니다.</p><p>번호는 시간 순서를 뜻하지 않으며 원자료는 출처가 확인되지 않은 학습용 자료입니다. 이 예제는 변수 하나의 계산 연습이므로, 상관된 여러 변수에서 릿지와 라쏘의 성능을 비교한 실험으로 읽지 않습니다.</p><p>실제 탐색에서는 여러 크기의 λ를 비교하고 전처리도 학습 안에서 수행합니다. 선택에 사용한 최저 CV 점수를 독립적인 최종 성능으로 제시하지 않고, 별도 시험이나 중첩 교차검증으로 평가합니다. 점수 차이가 작으면 안정성·설명 가능성·비용도 고려합니다.</p>')
 sec('elastic','엘라스틱넷','L1과 L2를 섞어 사용할 수도 있습니다','<p><strong>엘라스틱넷</strong>은 라쏘와 릿지의 벌점을 함께 사용합니다. 상관된 변수에서 변수 선택과 안정성을 함께 고려할 때 검토할 수 있습니다. 규제 강도뿐 아니라 두 벌점을 섞는 비율도 검증으로 고릅니다.</p><details><summary>엘라스틱넷의 산식</summary><p>이 장의 표기로는 SSE/(2n)+λ[ρΣ|bⱼ|+(1−ρ)Σbⱼ²/2]입니다. 0≤ρ≤1이며 ρ=1이면 라쏘, ρ=0이면 릿지가 됩니다.</p></details><p>다항식이나 상호작용 항을 만든 뒤 규제할 수도 있습니다. 어떤 항을 만들고 어떻게 표준화할지까지 학습 절차에 포함해야 합니다. 두 벌점을 섞었다고 모든 자료에서 더 좋은 결과가 나오는 것은 아닙니다.</p>')
 sec('interpretation','해석과 추론','축소한 계수에 일반 OLS 검정을 그대로 붙이지 않습니다','<p>규제 계수는 벌점으로 의도적으로 줄인 값이고, λ도 자료를 보고 선택하는 경우가 많습니다. 일반 OLS의 표준오차와 p값을 그대로 적용하면 축소와 선택 과정의 불확실성을 놓칠 수 있습니다.</p><p>라쏘가 고른 변수만 OLS에 다시 넣었다고 선택의 영향이 사라지는 것도 아닙니다. 계수 해석이나 인과 추론이 목적이라면 그에 맞는 설계와 추론 방법을 별도로 정해야 합니다. 예측이 목적이라면 전처리·규제 강도 선택·재학습을 포함한 전체 절차를 검증합니다.</p>')
 sec('practice','확인 문제','벌점의 대상과 선택 절차를 확인하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('릿지는 모든 계수를 같은 비율로 줄이나요?','직교·정규화된 예제에서는 그렇지만 일반적인 상관된 변수에서는 아닙니다.'),('라쏘 계수 0은 실제 영향이 없다는 증거인가요?','아니요. 표본·스케일·규제 강도에 따른 모형 선택의 결과입니다.'),('CV 전에 전체 자료로 표준화해도 되나요?','학습되는 변환은 각 폴드의 학습 부분에서 추정해야 합니다.'),('프로그램마다 λ=1이면 같은 모형인가요?','목적함수 정규화와 변수 스케일이 다를 수 있으므로 산식을 확인해야 합니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','규제 설정과 전처리를 함께 확인합니다','<p>모형 설명에서 벌점 종류·강도 선택 기준·변수 스케일·절편 처리·평가 설계를 함께 읽으세요. 이 장의 단일 변수 릿지 예제가 서비스에 구현된 산식이나 실제 성능이라고 전제하지 않습니다.</p><p>계수 축소나 변수 선택을 개별 적정가나 인과효과의 확정으로 해석하지 않습니다. 예측·설명 목적에 맞게 결과의 적용 범위를 확인합니다.</p>')
 sec('recap','학습 요약','규제는 적합과 안정성 사이를 조절하는 방법입니다','<ul class="learn-recap-list"><li>규제는 학습 오차에 계수 크기의 벌점을 더합니다. 너무 강하면 과소적합할 수 있습니다.</li><li><strong>릿지</strong>는 계수의 제곱합(L2)으로 계수를 줄이고, <strong>라쏘</strong>는 절댓값 합(L1)으로 일부 계수를 0으로 만들 수 있습니다.</li><li>단위에 따라 벌점이 달라지므로 표준화 방법을 정합니다. 교차검증에서는 각 학습 부분에서 기준을 구합니다.</li><li>규제 강도 λ는 검증으로 고르고 벌점 산식까지 함께 확인합니다. 선택한 CV 점수와 최종 평가를 구별합니다.</li><li>계수 0은 영향이 없다는 증거가 아니며, 규제 계수에 일반 OLS 추론을 그대로 적용하지 않습니다.</li></ul><p>다음 <a href="/learn/stats/classification/">28장 「분류와 로지스틱 회귀」</a>에서는 범주를 예측하는 방법과 확률을 살펴봅니다.</p><details class="learn-references"><summary>참고자료와 예제 데이터</summary><ul><li><a href="https://scikit-learn.org/stable/modules/linear_model.html">scikit-learn: Ridge·Lasso·Elastic-Net</a></li><li><a href="../regularization-example.json">계수 경로와 폴드별 계산 자료</a></li></ul><p class="learn-source-note">본문·그림은 직교 가상 예제와 공통 학습 자료로 직접 작성했습니다. 참고자료 기존 확인일: 2026-10-09.</p></details>')
 p=ROOT/'regularization/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="규제: 릿지와 라쏘">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1릿지·라쏘의 벌점과 계수 경로, 표준화·규제 강도 선택·해석의 한계를 학습합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
