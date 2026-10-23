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
 result=dict(description='가상 고정 X에서 독립 정규 오차를 300회 다시 생성한 시뮬레이션. 모형의 복잡도와 예측 오차를 설명하기 위한 자료.',seed=seed,repeats=300,sigma=sigma,x=x.tolist(),training_y=ys.tolist(),grid=grid.tolist(),truth=truth(grid).tolist(),models=models)
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
 sec('quick-start','학습 목표','배운 자료를 잘 맞히면 새 자료도 잘 맞힐까요?','<p>연습 문제의 답을 외우면 연습 점수는 높아집니다. 하지만 조금 다른 문제가 나왔을 때도 잘 풀 수 있을지는 별개의 문제입니다. 모형도 학습 자료를 세밀하게 따라갈수록 그 안에 우연히 섞인 흔들림까지 배울 수 있습니다.</p><p>이 장에서는 단순한 모형과 복잡한 모형을 같은 자료에 적용해 봅니다. 이어서 자료를 바꾸어 학습을 반복하면 예측이 어떻게 달라지는지 살펴보고, 편향·분산·잡음으로 예측 오차를 나누어 이해합니다.</p><ul class="learn-objectives"><li>과소적합과 과적합을 학습 오차·새 자료의 오차와 연결해 설명합니다.</li><li>편향, 예측의 분산, 관측 잡음이 각각 무엇인지 구별합니다.</li><li>학습곡선에서 살펴볼 점과 진단의 한계를 이해합니다.</li><li>검증을 이용해 모형의 복잡도를 조절하는 이유를 설명합니다.</li></ul>')
 sec('fits','핵심 이해','관계의 모양과 우연한 흔들림을 구별합니다','<p>곡선 모양의 관계를 직선 하나로 설명하면 중요한 굽음을 놓칠 수 있습니다. 이처럼 모형이 관계를 충분히 표현하지 못하는 상태를 <strong>과소적합</strong>이라고 합니다. 반대로 작은 흔들림까지 따라가 학습 자료에서는 잘 맞지만 새 자료에서 성능이 나빠지는 현상을 <strong>과적합</strong>이라고 합니다.</p>'+g1+'<p>그림의 점은 단위 없는 가상 변수 X와 Y입니다. X를 −1부터 1까지 같은 간격으로 12개 두고, Y는 <strong>1+X+0.7X²에 작은 잡음을 더해</strong> 만듭니다. 검정 점선은 잡음이 없는 참 평균입니다. 주황 직선은 굽음을 충분히 담지 못하고, 보라 곡선은 점을 더 가깝게 따라가면서 점 사이에서 더 흔들립니다.</p><p>학습 자료를 얼마나 잘 맞혔는지만으로는 어느 모형이 좋은지 정할 수 없습니다. 앞으로 만날 자료에서도 관계를 잘 표현하는지 확인해야 합니다.</p>')
 sec('experiment','반복실험','잡음이 달라진 자료로 학습을 300회 반복합니다','<p>한 번 그린 곡선만 보면 우연히 잘 맞은 결과를 고를 수 있습니다. 그래서 X의 위치와 참 평균은 그대로 두고 잡음만 다시 뽑아 학습을 300회 반복합니다. 매번 1·2·5·9차 다항식을 최소제곱으로 적합합니다. 잡음은 평균 0, 표준편차 0.15인 독립 정규분포에서 생성합니다.</p><p>이 실험에서 ‘복잡도’는 다항식의 차수입니다. 차수가 높으면 더 다양한 곡선을 표현할 수 있습니다. 비교할 차수와 난수 시드(20261009)를 미리 정했으므로 같은 계산을 재현할 수 있습니다.</p><p>X는 매번 같으므로 X의 구성까지 달라질 때 생기는 불확실성은 포함하지 않습니다. <a href="../overfitting-example.json">반복실험 자료</a>에는 표본, 곡선, 오차 계산값을 담았습니다.</p><details><summary>계산 방법 자세히 보기</summary><p>같은 다항식 공간을 르장드르 기저로 표현해 계산했습니다. 거듭제곱 항을 직접 쓰는 것보다 수치 계산을 안정적으로 하기 위한 방법이며, 비교하는 곡선의 범위나 입력 정보가 추가되는 것은 아닙니다.</p></details>')
 sec('errors','학습과 새 관측 오차','학습 오차가 줄어도 새 자료의 오차는 커질 수 있습니다','<p>이 실험처럼 같은 자료에 최소제곱으로 다항식을 적합하면, 차수를 높여도 학습 제곱오차는 늘지 않습니다. 더 높은 차수의 모형이 낮은 차수의 모형도 표현할 수 있기 때문입니다. 하지만 학습 자료의 잡음을 따라간 곡선이 새로운 잡음까지 맞힐 수는 없습니다.</p>'+g2+'<p>파란 선은 300회 반복한 학습 평균제곱오차(MSE)의 평균입니다. 주황 선은 같은 X 범위에서 새 관측을 예측할 때의 기대 MSE입니다. 이 실험에서는 2차 모형이 참 관계를 표현하면서 흔들림도 작아 새 관측 오차가 작습니다. 9차 모형은 학습 오차가 더 작지만 새 관측 오차는 커집니다.</p><p>실제 검증 오차가 언제나 매끈한 U자 모양인 것은 아닙니다. 모형, 규제, 표본 수에 따라 달라지고 작은 평가 표본의 점수는 우연히 흔들릴 수 있습니다. 이 실험에서 2차가 좋았다는 결과를 다른 자료의 모형 선택 규칙으로 적용해서는 안 됩니다.</p><details><summary>두 오차의 계산 범위</summary><p>학습 오차는 12개 학습 위치에서 계산했습니다. 새 관측의 기대 오차는 201개 X 격자에서 예측과 참 평균의 제곱차를 평균한 뒤, 독립적인 새 잡음의 분산 0.0225를 더했습니다. 별도 시험 표본의 점수가 아니라 참 관계를 아는 시뮬레이션에서 계산한 값입니다. 두 오차는 X에 부여하는 가중치도 달라서 1차 모형에서는 학습 오차가 더 크게 나옵니다. 두 선 사이의 간격 전체를 과적합의 크기로 해석하지 않습니다.</p></details>')
 sec('decomposition','편향·분산·잡음','반복 예측의 중심과 흔들림을 나누어 봅니다','<p>같은 X에서 모형을 반복해서 학습한다고 생각해 봅시다. 예측들이 참 평균에서 한쪽으로 벗어나 모이는지, 매번 넓게 흩어지는지를 나누어 볼 수 있습니다. 제곱오차를 사용할 때 기대 예측오차는 <strong>편향² + 예측의 분산 + 잡음의 분산</strong>으로 분해됩니다.</p>'+g3+'<p><strong>편향</strong>은 반복 예측의 평균과 참 평균의 차이입니다. 직선으로 곡선 관계를 설명할 때처럼 모형이 관계의 일부를 놓치면 커질 수 있습니다. 여기서 말하는 모형의 편향은 표집 편향이나 사회적 편향과는 다른 개념입니다.</p><p><strong>예측의 분산</strong>은 학습 자료가 바뀔 때 같은 X에서 예측값이 얼마나 달라지는지 나타냅니다. 원자료 Y 자체의 분산과 구별해야 합니다. <strong>잡음</strong>은 현재 입력으로 설명하고도 개별 관측에 남는 변동입니다. 입력이나 측정 방법이 좋아지면 그 크기도 달라질 수 있습니다.</p><details><summary>제곱오차 분해의 식과 조건</summary><p>참 평균을 f(x), 학습 자료 D에서 얻은 예측을 f̂_D(x)라고 하면 기대 제곱오차는 [E_D f̂_D(x)−f(x)]² + Var_D[f̂_D(x)] + Var(ε|x)입니다. 새 잡음은 조건부 평균이 0이고 학습 자료와 독립이라고 가정합니다. 이 분해를 MAE나 분류 정확도에 그대로 적용할 수는 없습니다.</p></details>')
 sec('stability','예측의 안정성','같은 위치의 예측이 얼마나 달라지는지 봅니다','<p>다음 그림은 X=0.8에서 반복 학습한 모형들의 예측값을 보여 줍니다. 점 하나가 한 번의 학습에서 얻은 예측입니다. 점들이 좁게 모이면 자료가 달라져도 예측이 비교적 안정적이고, 넓게 흩어지면 자료에 민감하다는 뜻입니다.</p>'+g4+'<p>단순한 모형은 안정적이어도 참 평균을 놓칠 수 있고, 유연한 모형은 관계를 잘 표현하면서도 잡음에 민감할 수 있습니다. 편향과 분산 중 하나만 작게 만드는 것으로 충분하지 않은 이유입니다.</p><p>그림에는 처음 30회의 예측만 표시했지만 앞의 오차 분해에는 300회를 모두 사용했습니다. 반복 횟수가 유한하므로 추정한 편향과 분산에도 오차가 있습니다. 실제 자료에서는 참 평균을 모르기 때문에 보통 검증 결과와 자료를 바꿨을 때의 민감도를 살펴봅니다.</p>')
 sec('diagnosis','학습곡선과 진단','자료가 늘어날 때 두 오차가 어떻게 바뀌나요?','<p>앞 그림은 모형의 복잡도를 바꾼 비교입니다. <strong>학습곡선</strong>은 학습 자료의 수를 바꾸면서 학습 오차와 검증 오차를 살펴봅니다. 두 오차가 모두 크고 비슷하다면 모형이 관계를 충분히 표현하지 못하거나 입력 정보가 부족할 수 있습니다. 학습 오차는 작은데 검증 오차가 크다면 과적합을 의심할 수 있습니다.</p><p>이 모양만으로 원인을 확정하지는 않습니다. 비교 기준에 비해 오차가 큰지 살피고, 데이터 누수, 학습과 평가 대상의 차이, 시간에 따른 변화, 측정 오류, 학습 과정의 문제도 확인합니다.</p><p>자료를 더 모으면 예측의 흔들림을 줄이는 데 도움이 될 수 있습니다. 다만 잘못 정한 관계의 모양이나 반복되는 측정 오류까지 자동으로 해결해 주는 것은 아닙니다.</p>')
 sec('control','복잡도 조절','검증 결과를 보며 표현력을 조절합니다','<p>다항식에서는 차수를 낮추고, 의사결정나무에서는 깊이를 제한하거나 마지막 가지에 필요한 관측 수를 늘릴 수 있습니다. 릿지·라쏘처럼 계수의 크기를 제한하는 규제도 있습니다. 학습을 적절한 시점에 멈추는 조기 종료 역시 한 방법입니다. 각 방법은 뒤의 장에서 자세히 다룹니다.</p><p>이런 설정은 검증 자료나 교차검증으로 비교합니다. 시험 점수가 좋아질 때까지 차수나 규제 강도를 바꾸면 시험 자료도 선택에 사용하게 됩니다. 전처리와 변수 선택 역시 23장에서 살펴본 학습 자료의 경계를 지켜야 합니다.</p><p>목표는 무조건 단순한 모형을 고르는 것이 아닙니다. 필요한 관계를 표현하면서 새 자료에서도 안정적으로 작동하는 모형을 찾는 것입니다. 검증 성능이 비슷하다면 설명하기 쉬운지, 예측이 안정적인지, 계산 비용은 어느 정도인지 함께 고려합니다.</p>')
 sec('practice','확인 문제','편향·분산·잡음의 대상을 구별하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('학습 오차가 0이면 좋은 예측 모형인가요?','학습 관측을 보간했다는 뜻일 수 있습니다. 새 자료 성능과 안정성은 별도로 확인합니다.'),('분산은 학습 Y의 표본분산인가요?','이 분해에서는 학습 자료가 달라질 때 같은 x의 예측이 얼마나 흔들리는지를 뜻합니다.'),('편향²+분산+잡음 공식을 MAE에도 쓰나요?','그대로 쓸 수 없습니다. 여기서는 독립 새 오차와 제곱손실 아래의 분해입니다.'),('시험 오차가 가장 작은 차수를 고르면 독립 평가인가요?','시험을 선택에 사용했으므로 독립적인 최종 평가 역할을 잃습니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','좋은 학습 적합과 활용 성능을 구별합니다','<p>모형의 복잡도와 학습 오차뿐 아니라 어떤 시점·지역·집단에서 검증했는지 확인하세요. 특정 표본에만 맞는 곡선이나 규칙을 시장의 고정 법칙으로 읽지 않습니다.</p><p>이 장은 별도 가상 자료로 원리를 설명합니다. 서비스의 실제 알고리즘이나 성능 수치가 아니며 개별 적정가·미래 결과를 보장하지 않습니다.</p>')
 sec('recap','학습 요약','좋은 적합은 새 자료에서도 이어져야 합니다','<ul class="learn-recap-list"><li><strong>과소적합</strong>은 관계를 충분히 표현하지 못하고, <strong>과적합</strong>은 학습 자료의 우연한 흔들림까지 따라가 새 자료에서 성능이 나빠지는 현상입니다.</li><li>학습 오차가 작아져도 새 자료의 오차가 작아진다고 보장할 수 없습니다.</li><li>제곱손실의 기대 예측오차는 조건 아래에서 편향², 예측의 분산, 잡음의 분산으로 나뉩니다.</li><li>학습곡선은 진단에 도움이 되지만 오차의 격차만으로 원인을 확정할 수는 없습니다.</li><li>복잡도는 검증으로 조절하고, 선택을 마친 뒤 시험 자료로 평가합니다.</li></ul><p>다음 <a href="/learn/stats/prediction-errors/">25장 「예측오차: MAE·RMSE·MAPE」</a>에서는 예측이 얼마나 틀렸는지 측정하는 여러 방법을 비교합니다.</p><details class="learn-references"><summary>참고자료와 예제 데이터</summary><ul><li><a href="https://scikit-learn.org/stable/auto_examples/model_selection/plot_underfitting_overfitting.html">scikit-learn: Underfitting vs. Overfitting</a></li><li><a href="../overfitting-example.json">가상 반복실험 자료</a></li></ul><p class="learn-source-note">본문과 그림은 직접 구성한 가상 생성 과정으로 계산했습니다. 참고자료 기존 확인일: 2026-10-09.</p></details>')
 p=ROOT/'overfitting/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="과적합과 편향–분산의 균형">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1과소적합·과적합과 편향–분산 분해를 반복실험으로 이해하고 복잡도와 검증의 관계를 학습합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
