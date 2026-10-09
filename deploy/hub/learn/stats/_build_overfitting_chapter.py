"""Reproducible fixed-design bias/variance simulation for chapter 24."""
from pathlib import Path
from html import escape
import numpy as np
import json,re
ROOT=Path(__file__).resolve().parent

def build():
 seed=20261009;rng=np.random.default_rng(seed);x=np.linspace(-1,1,12);grid=np.linspace(-1,1,201);truth=lambda z:1+z+.7*z*z;sigma=.15;degrees=[1,2,5,9];ys=truth(x)+rng.normal(0,sigma,(300,12));models=[]
 for degree in degrees:
  A=np.polynomial.legendre.legvander(x,degree);G=np.polynomial.legendre.legvander(grid,degree);coef=np.linalg.lstsq(A,ys.T,rcond=None)[0];pred=(G@coef).T;avg=pred.mean(axis=0);bias2=float(np.mean((avg-truth(grid))**2));variance=float(np.mean(np.var(pred,axis=0)));risk=float(np.mean((pred-truth(grid))**2)+sigma**2)
  models.append(dict(degree=degree,train_MSE=float(np.mean((ys-(A@coef).T)**2)),bias2=bias2,variance=variance,noise=sigma**2,expected_MSE=risk,first_curve=pred[0].tolist(),at08=(np.polynomial.legendre.legvander([.8],degree)@coef).ravel().tolist()))
 result=dict(description='가상 고정 X에서 독립 정규 오차를 300회 다시 생성한 시뮬레이션. 실제 시장 자료가 아님.',seed=seed,repeats=300,sigma=sigma,x=x.tolist(),training_y=ys.tolist(),grid=grid.tolist(),truth=truth(grid).tolist(),models=models)
 (ROOT/'overfitting-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def ln(x,y,a,b):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="#94a3b8"/>'
 def fig(id,title,b,cap):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 420" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 colors={1:'#d97706',2:'#2563eb',5:'#64748b',9:'#9333ea'};px=lambda v:70+(v+1)*250
 chosen=[m for m in models if m['degree'] in [1,2,9]];lo=min(0,min(min(m['first_curve']) for m in chosen));hi=max(3,max(max(m['first_curve']) for m in chosen));py=lambda v:320-(v-lo)/(hi-lo)*250
 b=tx(24,28,'같은 가상 학습 12점: 1차·2차·9차 다항식')+ln(70,320,570,320)+ln(70,60,70,320)
 for m in chosen:b+='<polyline data-degree="'+str(m['degree'])+'" points="'+' '.join(f'{px(v)},{py(w)}' for v,w in zip(grid,m['first_curve']))+'" fill="none" stroke="'+colors[m['degree']]+'" stroke-width="2"/>'
 b+='<polyline points="'+' '.join(f'{px(v)},{py(w)}' for v,w in zip(grid,truth(grid)))+'" fill="none" stroke="#111827" stroke-dasharray="4 4"/>'
 for v,w in zip(x,ys[0]):b+=f'<circle cx="{px(v)}" cy="{py(w)}" r="4" fill="#111827"/>'
 for v in [-1,0,1]:b+=tx(px(v)-5,345,v)
 for v in np.linspace(lo,hi,4):b+=tx(25,py(v)+5,f'{v:.1f}')
 b+=tx(24,382,'주황 1차 / 파랑 2차 / 보라 9차 / 검정 점선: 참 평균')
 g1=fig('fits','복잡도에 따른 곡선',b,'그림 1. 첫 번째 가상 표본을 모두 표시했습니다. X·Y는 단위 없는 변수이며 참 평균은 1+X+0.7X²입니다. 관측 범위 안에서도 복잡한 곡선이 흔들릴 수 있습니다.')
 ymax=max(m['expected_MSE'] for m in models)*1.2;ey=lambda v:320-v/ymax*240
 b=tx(24,28,'300회 평균: 학습 MSE와 새 관측의 기대 MSE')+ln(70,320,570,320)+ln(70,60,70,320)
 for key,c in [('train_MSE','#2563eb'),('expected_MSE','#d97706')]:
  b+='<polyline data-metric="'+key+'" points="'+' '.join(f"{120+i*140},{ey(m[key])}" for i,m in enumerate(models))+'" fill="none" stroke="'+c+'" stroke-width="2"/>'
  for i,m in enumerate(models):b+=f'<circle cx="{120+i*140}" cy="{ey(m[key])}" r="4" fill="{c}"/>'
 for i,m in enumerate(models):b+=tx(105+i*140,350,str(m['degree'])+'차')
 for v in np.linspace(0,ymax,4):b+=tx(20,ey(v)+5,f'{v:.3f}')
 b+=tx(24,385,'파랑: 학습 / 주황: 같은 X범위의 새 오차까지 포함')
 g2=fig('errors','복잡도와 기대 오차',b,'그림 2. 선은 비교를 돕기 위해 이은 것입니다. 새 관측 기대 MSE는 201개 고정 X에서 참 평균과의 제곱차를 평균하고 오차분산 0.0225를 더했습니다. 별도의 시험 표본 점수는 아닙니다.')
 b=tx(24,28,'기대 제곱오차 = 편향² + 분산 + 잡음')+ln(70,320,570,320)
 for i,m in enumerate(models):
  bottom=320
  for key,c in [('noise','#cbd5e1'),('variance','#d97706'),('bias2','#2563eb')]:
   h=m[key]/ymax*240;b+=f'<rect data-degree="{m["degree"]}" data-part="{key}" x="{95+i*140}" y="{bottom-h}" width="65" height="{h}" fill="{c}"/>';bottom-=h
  b+=tx(100+i*140,350,str(m['degree'])+'차')
 for v in np.linspace(0,ymax,4):b+=tx(20,ey(v)+5,f'{v:.3f}')
 b+=tx(24,385,'파랑: 편향² / 주황: 분산 / 회색: 새 관측 잡음')
 g3=fig('decomposition','시뮬레이션 오차 분해',b,'그림 3. 편향과 분산은 300개 적합식으로 추정했습니다. 분산은 반복 수 300으로 나누어 계산해 이 유한 반복에서도 합이 그림 2의 기대 MSE와 일치합니다.')
 vals=[v for m in models for v in m['at08'][:30]];low=min(vals)-.1;high=max(vals)+.1;vx=lambda v:100+(v-low)/(high-low)*450;truth08=float(truth(.8))
 b=tx(24,28,'학습 오차를 다시 뽑으면 X=0.8의 예측도 달라집니다')
 for i,m in enumerate(models):
  yy=95+i*65;b+=tx(25,yy+5,str(m['degree'])+'차')+ln(90,yy,570,yy)
  for j,v in enumerate(m['at08'][:30]):b+=f'<circle cx="{vx(v)}" cy="{yy+(j%3-1)*8}" r="3" fill="{colors[m["degree"]]}"/>'
 b+=f'<line x1="{vx(truth08)}" y1="65" x2="{vx(truth08)}" y2="315" stroke="#111827" stroke-dasharray="4 4"/>'
 for v in np.linspace(low,high,4):b+=tx(vx(v)-12,345,f'{v:.2f}')
 b+=tx(24,385,f'가로: 예측 Y · 점선: 참 평균 {truth08:.3f} · 처음 30회 표시')
 g4=fig('stability','표본에 따른 예측의 흔들림',b,'그림 4. 모든 반복에서 X는 같고 Y의 잡음만 달라집니다. 점의 세로 위치는 겹침을 줄이기 위한 배치이며 추가 변수나 확률을 뜻하지 않습니다.')
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('fits','핵심 이해','자료의 구조와 우연한 흔들림을 구별합니다','<p>과소적합은 선택한 모형이 관계의 구조를 충분히 표현하지 못하는 상태입니다. 과적합은 학습 표본의 우연한 흔들림까지 따라가면서 새 자료에서의 성능이 나빠지는 현상입니다. 학습 오차가 작다는 사실만으로 일반화 성능을 판단할 수 없습니다.</p>'+g1+'<p>이 장에서는 실제 시장과 구분한 가상 자료를 씁니다. X를 −1~1에 같은 간격으로 12개 고정하고 Y=1+X+0.7X²+ε, ε는 독립 N(0,0.15²)로 만듭니다. 참 관계를 알기 때문에 모형이 구조와 잡음 중 무엇을 따라가는지 확인할 수 있습니다.</p>')
 sec('experiment','재현 가능한 실험','같은 생성 과정에서 학습을 300회 반복합니다','<p>난수 시드 20261009로 잡음만 다시 뽑아 300개의 학습 표본을 만들고, 각 표본에 1·2·5·9차 다항식을 최소제곱으로 적합합니다. 비교 모형은 미리 정했으며, 유리한 결과가 나오도록 표본을 골라 바꾸지 않았습니다.</p><p>숫자가 큰 거듭제곱으로 인한 계산 불안정을 줄이기 위해 같은 다항식 공간의 르장드르 기저를 사용합니다. 이는 새로운 자료나 답을 추가하는 것이 아니라 같은 함수 공간을 다른 좌표로 계산하는 방법입니다.</p><p>이 실험은 X가 고정된 상황의 반복입니다. 실제 표본처럼 X까지 바뀌거나 지역·시점이 달라지는 모든 불확실성을 포함하지 않습니다. <a href="../overfitting-example.json">표본·곡선·오차 분해 자료</a>로 재현할 수 있습니다.</p>')
 sec('errors','학습과 새 관측 오차','학습 오차가 내려가도 새 관측 오차는 올라갈 수 있습니다','<p>같은 표본에서 중첩된 다항식 공간을 정확히 최소제곱으로 적합하면 차수를 높여도 학습 제곱오차는 늘지 않습니다. 하지만 새 자료의 잡음은 학습 때의 잡음과 다르므로 복잡한 곡선이 따라간 흔들림이 도움이 되지 않을 수 있습니다.</p>'+g2+'<p>여기서 새 관측 기대 오차는 201개 X 격자에서 적합식과 참 평균의 제곱차를 계산하고, 독립인 새 오차의 분산을 더한 값입니다. 실제 시험 자료 점수가 아니며 이 시뮬레이션의 알려진 생성 과정에만 가능한 계산입니다. 학습 오차는 12개 X, 새 관측 오차는 201개 격자에서 평균하므로 X의 가중 분포도 다릅니다. 1차 모형에서 학습 오차가 더 큰 것은 이 차이와 관련되며, 두 곡선의 격차 전체를 과적합의 양으로 읽지 않습니다.</p><p>복잡도에 따른 검증 오차가 항상 매끈한 U자여야 하는 것은 아닙니다. 모형·규제·표본 수에 따라 모양이 달라지고, 한 번의 작은 검증 표본에서는 우연한 요동도 큽니다. 차수 2가 유리한 이 결과를 실제 부동산 모형 선택의 규칙으로 일반화하지 않습니다.</p>')
 sec('decomposition','편향–분산 분해','반복해 얻는 예측의 평균과 퍼짐을 나눠 봅니다','<p>고정된 x에서 참 평균을 f(x), 학습 자료 D로 적합한 예측을 f̂_D(x)라 합시다. 새 오차의 평균이 0이고 학습 자료와 독립이면, 제곱손실의 기대 예측오차는 <strong>[E_D f̂_D(x)−f(x)]² + Var_D[f̂_D(x)] + Var(ε|x)</strong>로 나뉩니다.</p>'+g3+'<p><strong>편향</strong>은 반복 예측의 평균이 참 평균에서 벗어난 정도입니다. 여기서의 모형 편향은 표집 편향이나 사회적 편향과 같은 뜻이 아닙니다. <strong>분산</strong>은 학습 자료가 바뀔 때 예측이 흔들리는 정도로, 원자료 Y의 분산 자체가 아닙니다.</p><p><strong>잡음</strong>은 현재 입력으로 조건을 정해도 남는 새 관측의 변동입니다. 더 유용한 입력이나 나은 측정을 확보하면 그 크기가 달라질 수 있으므로 영원히 줄일 수 없는 절대적 한계라고 읽지는 않습니다. 이 분해는 제곱손실의 결과이며 MAE·분류 정확도에 그대로 적용하지 않습니다.</p>')
 sec('stability','예측의 안정성','한 번 잘 맞은 곡선보다 반복했을 때의 행동을 봅니다','<p>단순한 모형은 표본이 바뀌어도 비슷한 예측을 할 수 있지만 중요한 곡률을 놓칠 수 있습니다. 유연한 모형은 구조를 잘 표현할 수 있는 대신 잡음에 민감해질 수 있습니다. 어느 쪽이 나은지는 데이터와 목적에 달려 있습니다.</p>'+g4+'<p>이 그림은 앞 실험의 첫 30회만 표시하고 오차 분해에는 300회를 모두 사용했습니다. 유한 반복으로 계산한 편향²에는 몬테카를로 오차가 있으므로 정확한 모집단 편향²라고 부르지 않습니다. 실제 자료에서는 참 함수를 모르므로 이런 분해를 직접 관찰하기 어렵고, 검증과 민감도 분석을 사용합니다.</p>')
 sec('diagnosis','학습곡선과 진단','표본 수를 늘렸을 때의 변화도 살펴봅니다','<p>복잡도를 바꾸는 검증곡선과 달리 학습곡선은 학습 표본 수를 바꿔 학습·검증 오차를 봅니다. 두 오차가 모두 크고 가까우면 표현력이 부족하거나 입력 정보가 부족할 수 있습니다. 학습 오차는 작고 검증 오차가 크면 과적합을 의심할 수 있습니다.</p><p>그러나 오차 격차만으로 원인을 확정하지 않습니다. 누수·평가 집단의 차이·시간 변화·측정 품질·최적화 실패도 확인합니다. 자료가 더 많아지면 분산 문제를 줄이는 데 도움이 될 수 있지만 잘못된 함수 형태나 반복되는 측정 오류를 자동으로 해결하지는 않습니다.</p>')
 sec('control','복잡도 조절','모형을 단순하게 만드는 방법을 목적에 맞게 선택합니다','<p>다항식 차수나 나무 깊이를 제한하고, 잎의 최소 관측 수를 늘리거나, 릿지·라쏘 같은 규제를 사용할 수 있습니다. 최근접 이웃에서는 작은 K가 더 국소적인 예측을 만들어 표본에 민감해질 수 있습니다. 조기 종료도 학습 진행에 따른 복잡도를 조절하는 방법입니다.</p><p>이 조절값은 학습 계수와 달리 검증 또는 교차검증으로 선택합니다. 시험 자료에 맞춰 차수·규제 강도를 반복 변경하지 않습니다. 전처리와 변수 선택도 23장에서 배운 학습 경계 안에서 수행합니다.</p><p>복잡한 모형이 항상 나쁜 것은 아닙니다. 충분한 정보와 적절한 규제·검증이 있다면 단순 모형이 놓친 관계를 포착할 수 있습니다. 비슷한 검증 성능이라면 안정성·해석·운영 비용을 함께 고려합니다.</p>')
 sec('practice','확인 문제','편향·분산·잡음의 대상을 구별하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('학습 오차가 0이면 좋은 예측 모형인가요?','학습 관측을 보간했다는 뜻일 수 있습니다. 새 자료 성능과 안정성은 별도로 확인합니다.'),('분산은 학습 Y의 표본분산인가요?','이 분해에서는 학습 자료가 달라질 때 같은 x의 예측이 얼마나 흔들리는지를 뜻합니다.'),('편향²+분산+잡음 공식을 MAE에도 쓰나요?','그대로 쓸 수 없습니다. 여기서는 독립 새 오차와 제곱손실 아래의 분해입니다.'),('시험 오차가 가장 작은 차수를 고르면 독립 평가인가요?','시험을 선택에 사용했으므로 독립적인 최종 평가 역할을 잃습니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','좋은 학습 적합과 활용 성능을 구별합니다','<p>모형의 복잡도와 학습 오차뿐 아니라 어떤 시점·지역·집단에서 검증했는지 확인하세요. 특정 표본에만 맞는 곡선이나 규칙을 시장의 고정 법칙으로 읽지 않습니다.</p><p>이 장은 별도 가상 자료로 원리를 설명합니다. 서비스의 실제 알고리즘이나 성능 수치가 아니며 개별 적정가·미래 결과를 보장하지 않습니다.</p>')
 sec('recap','정리와 참고자료','복잡도는 검증 결과와 안정성을 함께 보고 정합니다','<p>학습 오차의 감소와 새 관측의 기대 오차 감소는 다릅니다. 제곱손실에서는 편향²·예측 분산·잡음을 구분할 수 있으며, 실제 선택에는 목적에 맞는 독립 평가가 필요합니다.</p><p>다음 <a href="/learn/stats/prediction-errors/">25장 「예측오차: MAE·RMSE·MAPE」</a>에서 지표의 산식과 해석을 살펴봅니다.</p><ul><li><a href="https://scikit-learn.org/stable/auto_examples/model_selection/plot_underfitting_overfitting.html">scikit-learn: Underfitting vs. Overfitting</a></li><li><a href="../overfitting-example.json">가상 반복실험 자료</a></li></ul><p class="learn-source-note">본문과 그림은 직접 구성한 가상 생성 과정으로 계산했습니다. 참고자료 확인: 2026-10-09.</p>')
 p=ROOT/'overfitting/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="과적합과 편향–분산의 균형">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1과소적합·과적합과 편향–분산 분해를 반복실험으로 이해하고 복잡도와 검증의 관계를 학습합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
