"""Reproducible chapter 18 residual diagnostics."""
from pathlib import Path
from statistics import mean,NormalDist
from html import escape
import json,math,re
from _build_regression_chapter import fit
ROOT=Path(__file__).resolve().parent

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];x=[r['area'] for r in rows];y=[r['price'] for r in rows];f=fit(x,y);n=len(x);s=math.sqrt(f['SSE']/(n-2))
 ds=[]
 for row,e in zip(rows,f['residuals']):
  h=1/n+(row['area']-mean(x))**2/f['Sxx'];r=e/(s*math.sqrt(1-h));cook=r*r*h/(2*(1-h))
  ds.append(dict(id=row['id'],fitted=row['price']-e,residual=e,leverage=h,standardized=r,cook=cook))
 qq=[dict(z=NormalDist().inv_cdf((i+.5)/n),residual=e) for i,e in enumerate(sorted(f['residuals']))]
 d=dict(description='공통 학습 자료의 두 수치열을 단위 없는 X,Y로 사용한 30쌍의 절편 포함 단순 OLS 진단',n=n,df=n-2,SSE=f['SSE'],s=s,RMSE=math.sqrt(f['SSE']/n),MAE=mean(abs(e) for e in f['residuals']),rows=ds,qq=qq)
 (ROOT/'residuals-example.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def text(x,y,v):return f'<text x="{x}" y="{y}">{escape(str(v))}</text>'
 def line(x,y,xx,yy):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="#94a3b8"/>'
 def dot(x,y,id='',color='#2563eb'):return f'<circle cx="{x}" cy="{y}" r="4" fill="{color}" data-id="{id}"/>'
 def fig(id,title,b,cap,h=390):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=text(24,28,'잔차(Y 단위)')+line(65,255,580,255)+line(65,55,65,335)
 for v in [-100,0,100,200]:b+=text(24,260-v*.7,v)
 for v in [0,50,100,150,200]:b+=text(65+v*2.2,355,v)
 for row in ds:
  cx=65+row['fitted']*2.2;cy=255-row['residual']*.7;b+=dot(cx,cy,row['id'])
  if row['id']==7:b+=text(cx-42,cy-12,'7번')
 b+=text(400,382,'적합값 ŷ');g1=fig('resplot','적합값과 잔차',b,'그림 1. 17장의 단위 없는 X,Y 수치쌍 30개에서 구한 적합값과 잔차입니다. 0선 주변의 모양과 큰 잔차를 함께 봅니다. 가로축은 관측 Y가 아닌 적합값 ŷ입니다.',410)
 b=text(24,28,'잔차 패턴의 개념도: 실제 자료·통계 검정 결과가 아닙니다')
 for j,title in enumerate(['곡선: 평균 함수 점검','부채꼴: 분산 점검']):
  left=55+j*310;b+=text(left,64,title)+line(left,210,left+235,210)
  for i in range(15):
   u=(i-7)/7
   for sign in [-1,1]:
    e=(u*u-.38)*100+sign*7 if j==0 else sign*(8+i*4)
    b+=dot(left+10+i*15,210-e)
  b+=text(left,326,'가로: 적합값 / 세로: 잔차')
 g2=fig('patterns','곡선과 부채꼴 패턴',b,'그림 2. 패턴을 비교하기 위해 직접 배치한 개념도입니다. 곡선은 평균 관계의 누락, 부채꼴은 비일정한 오차분산을 의심할 단서이며 원인을 확정하지 않습니다.',360)
 b=text(24,28,'정규 Q–Q: 정규 이론 분위수와 정렬한 잔차')+line(65,325,580,325)+line(65,55,65,325)
 for v in [-100,0,100,200]:b+=text(24,260-v*.7,v)
 for q in qq:b+=dot(320+q['z']*100,255-q['residual']*.7)
 b+=f'<line x1="{320-10000/s}" y1="325" x2="540" y2="{255-2.2*s*.7}" stroke="#d97706" stroke-dasharray="5 4"/>'
 for z in [-2,-1,0,1,2]:b+=text(315+z*100,350,z)
 b+=text(24,378,'세로: 잔차(Y 단위) · 주황: 잔차 0, 척도 s의 참고선')
 g3=fig('qq','잔차의 정규 Q–Q 그림',b,'그림 3. 가로축은 Φ⁻¹((i−0.5)/30), i=1,…,30입니다. 위쪽 꼬리의 이탈을 살펴보세요. 참고선은 검정 경계나 신뢰구간이 아닙니다.',405)
 b=text(24,28,'레버리지와 내부 표준화 잔차')+line(65,280,580,280)+line(65,55,65,335)
 for v in [-1,0,1,2,3,4]:b+=text(35,285-v*45,v)
 for row in ds:
  cx=65+row['leverage']*1800;cy=280-row['standardized']*45;b+=dot(cx,cy,row['id'])
  if row['id'] in [7,max(ds,key=lambda v:v['leverage'])['id']]:b+=text(cx+7,cy-8,str(row['id'])+'번')
 for h in [0,.1,.2]:b+=text(65+h*1800,355,h)
 b+=text(350,382,'가로: 레버리지 hᵢ')
 g4=fig('influence','잔차와 레버리지',b,'그림 4. 세로축은 eᵢ/[s√(1−hᵢ)]입니다. X방향의 극단성과 Y방향의 어긋남은 다른 개념입니다. 영향력은 계수 변화나 Cook 거리로 추가 확인합니다.',410)
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 seven=next(r for r in ds if r['id']==7)
 sec('quick-start','서두 · 학습목표','직선을 맞춘 뒤에는 남은 차이를 살펴봅니다','''<p>회귀선을 그었다고 분석이 끝나는 것은 아닙니다. 낮은 점수에서는 잘 맞지만 높은 점수에서 계속 빗나갈 수도 있고, 일부 관측값이 직선의 방향을 크게 바꿨을 수도 있습니다. <a href="/learn/stats/regression/">17장</a>에서 배운 <strong>잔차</strong>를 보면 모형이 놓친 패턴을 찾는 데 도움이 됩니다.</p><p>이 장에서는 잔차의 중심·퍼짐·순서·꼬리와 개별 관측값의 영향을 나누어 점검합니다. 계산할 수 있는 모형과 해석·추론에 적합한 모형을 구별하는 것이 목표입니다.</p><ul class="learn-objectives"><li>잔차 그림에서 곡선과 부채꼴 패턴이 무엇의 단서인지 설명합니다.</li><li>선형성·등분산·독립성·정규성이 각각 어떤 조건인지 구별합니다.</li><li>큰 잔차, 높은 레버리지, 큰 영향력의 차이를 이해합니다.</li><li>진단 결과를 근거로 모형을 점검하고 한계를 보고합니다.</li></ul>''')
 sec('reading','잔차 그림 읽기','0선 주변의 모양과 멀리 떨어진 점을 함께 보세요',f'''<p><strong>잔차 eᵢ=yᵢ−ŷᵢ</strong>는 관측값에서 적합값을 뺀 값입니다. 양수이면 모형이 관측값보다 낮게 적합했고, 음수이면 높게 적합했습니다. 미지의 모집단 오차 ε와 자료에서 계산한 잔차 e는 구별해야 합니다.</p><p>아래 계산은 17장과 같이 <a href="/learn/stats/graphs/#data">공통 학습 자료</a>의 두 수치열을 단위 없는 X,Y로 놓은 30쌍을 사용합니다. 7번의 관측 Y는 480, 적합값은 {seven['fitted']:.2f}, 잔차는 <strong>+{seven['residual']:.2f}</strong>입니다. 계산에는 반올림 전 계수를 사용했습니다.</p>'''+g1+'''<p>가로축은 직선에서 구한 적합값, 세로축은 잔차입니다. 0선 위아래로 특별한 모양 없이 퍼지는지, 적합값에 따라 중심이나 폭이 달라지는지, 유독 멀리 떨어진 점이 있는지 차례로 살펴보세요. 패턴이 보이면 원인을 검토할 단서가 되지만, 그림 하나로 가정이 성립하거나 깨졌다고 확정할 수는 없습니다.</p>''')
 sec('scale','잔차의 크기','크기를 요약할 때 계산식과 분모를 확인하세요',f'''<p>절편을 포함한 OLS에서 잔차 합이 0인 것은 계산의 성질입니다. 잘 맞는 모형이라는 증거는 아닙니다. 양수와 음수가 상쇄되지 않도록 절댓값이나 제곱을 사용해 크기를 요약합니다.</p><ul><li><strong>SSE=Σeᵢ²:</strong> 잔차제곱합이며, 예제에서는 {f['SSE']:,.2f}입니다.</li><li><strong>MAE=Σ|eᵢ|/n:</strong> 잔차 절댓값의 평균이며, {d['MAE']:.2f}입니다.</li><li><strong>학습 RMSE=√(SSE/n):</strong> 제곱잔차의 평균에 제곱근을 취한 값이며, {d['RMSE']:.2f}입니다.</li><li><strong>잔차 표준오차 s=√(SSE/(n−2)):</strong> 절편과 기울기를 추정한 자유도를 반영하며, {s:.2f}입니다.</li></ul><p>이 예제는 n=30이므로 잔차 자유도가 28입니다. 학습 RMSE와 s는 비슷한 형태지만 분모와 용도가 다릅니다. MAE·RMSE·s는 모두 Y와 같은 단위이고 SSE는 Y 단위의 제곱입니다.</p><p>이 값들은 자료에 맞춘 잔차의 요약입니다. 새로운 관측값의 예측 정확도로 그대로 옮겨 읽지 않습니다. 예측 목적이라면 별도 자료에서 오차를 확인해야 합니다.</p><details class="learn-more"><summary>s는 어떤 조건에서 오차의 퍼짐을 추정하나요?</summary><div class="learn-more__body"><p>올바른 선형 평균, 등분산, 비상관 오차 등의 조건 아래 s²=SSE/(n−2)는 오차분산의 불편추정량입니다. 제곱근을 취한 s 자체까지 불편추정량이라는 뜻은 아닙니다.</p></div></details>''')
 sec('patterns','선형성과 등분산','잔차의 중심이 움직이는지, 폭이 달라지는지 구별하세요','''<p><strong>잔차 중심이 곡선을 그리면</strong> 직선이 평균 관계를 놓쳤을 수 있습니다. X가 작은 곳과 큰 곳에서는 잔차가 양수이고 중간에서는 음수라면 U자 관계를 직선으로 요약한 결과일 수 있습니다. 빠진 변수나 집단 차이도 가능한 설명입니다.</p>'''+g2+'''<p><strong>중심은 0 근처인데 폭이 부채꼴로 커지면</strong> 오차의 분산이 일정하지 않은 이분산을 의심합니다. 등분산은 X가 달라도 오차의 조건부 분산이 일정하다는 뜻입니다. X나 Y 자체의 분산이 일정해야 한다는 말은 아닙니다.</p><p>두 그림은 패턴을 구별하려고 만든 개념도입니다. 실제 분석에서는 원자료와 수집 과정을 함께 확인해야 합니다. 학습 오차만 줄이려고 곡선을 복잡하게 만드는 것이 진단의 목적은 아닙니다.</p><details class="learn-more"><summary>이분산이 있으면 무엇이 달라지나요?</summary><div class="learn-more__body"><p>등분산은 Var(ε|X)=σ²라는 조건입니다. 이분산에서도 E[ε|X]=0 등 조건이 맞으면 OLS 계수는 불편할 수 있지만, 일반적인 등분산 표준오차는 부적절할 수 있습니다.</p><p>분산 구조에 맞는 가중최소제곱, 의미 있는 변환, 이분산 강건 표준오차 등을 검토할 수 있습니다. 강건 표준오차만으로 평균 함수의 오류·누락변수 편향·무리한 외삽이 해결되지는 않습니다.</p></div></details>''')
 sec('independence','독립성과 관측 순서','시간과 집단의 관계는 수집 과정에서 확인하세요','''<p>시간순으로 그린 잔차에서 양수가 오래 이어지거나 주기적인 움직임이 나타나면 시간 의존성이나 빠진 추세를 의심할 수 있습니다. 같은 학급·가구에 속한 관측값도 공통 요인 때문에 서로 닮을 수 있습니다.</p><p>시간 그래프에는 실제 측정 순서가 필요합니다. 이 예제의 자료 번호는 시간 정보가 아니므로 번호순 잔차를 시간에 따른 진단으로 해석하지 않습니다. 측정 시점과 집단 식별자를 확인한 뒤 순서별·집단별 패턴을 보세요.</p><p>의존성이 있다면 군집 표준오차나 시계열 모형처럼 구조에 맞는 방법을 검토합니다. 잔차가 겉보기에 불규칙하다는 사실만으로 독립성이 입증되지는 않습니다.</p><details class="learn-more"><summary>오차의 독립성과 잔차의 관계</summary><div class="learn-more__body"><p>독립성과 단순한 무상관은 같은 조건이 아닙니다. 또 모집단 오차가 독립이더라도 같은 자료로 적합한 OLS 잔차들은 잔차 합 0 같은 제약으로 서로 연결됩니다. 잔차를 완전히 독립된 오차 관측치처럼 취급해서는 안 됩니다.</p></div></details>''')
 sec('normality','정규성과 Q–Q 그림','정규성은 X나 Y보다 오차에 관한 조건입니다','''<p>OLS 직선을 계산하는 데 정규분포 가정이 필요한 것은 아닙니다. 고전적인 작은 표본의 정확한 t·F 검정과 신뢰구간에는 <strong>X가 주어졌을 때 오차가 정규분포를 따른다</strong>는 등의 가정을 사용합니다. X나 Y의 히스토그램이 정규 모양이어야 한다는 뜻은 아닙니다.</p><p><strong>정규 Q–Q 그림</strong>은 정렬한 잔차와 정규분포에서 기대하는 위치를 비교합니다. 점들이 대체로 직선에 놓이는지, 특히 양쪽 꼬리가 벗어나는지 살펴봅니다.</p>'''+g3+'''<p>꼬리의 이탈은 극단값이나 두꺼운 꼬리, 평균 관계를 잘못 맞춘 경우 등 여러 이유로 나타날 수 있습니다. 이 그림만으로 원인을 특정하거나 정규성을 확정하지는 않습니다. 주황 참고선도 합격·불합격의 경계가 아닙니다.</p><p>30쌍처럼 작은 자료에서는 진단 자체에도 불확실성이 있습니다. 정규성 검정의 p값 하나보다 잔차 패턴·수집 설계·영향 관측을 함께 판단하세요. 큰 표본의 근사 추론도 의존성과 분산에 대한 조건을 필요로 합니다.</p>''')
 sec('influence','레버리지와 영향력','Y방향의 어긋남과 X방향의 극단성을 구별하세요','''<p><strong>큰 잔차</strong>는 관측 Y가 적합값에서 많이 벗어났다는 뜻입니다. <strong>높은 레버리지</strong>는 X가 다른 관측값들과 멀리 떨어져 직선의 위치를 좌우할 여지가 크다는 뜻입니다. 둘은 다른 특성입니다.</p>'''+g4+f'''<p>같은 오차분산 아래에서도 레버리지에 따라 잔차의 분산이 달라집니다. 그림의 세로축은 이를 반영한 <strong>내부 표준화 잔차</strong>입니다. 단순한 원 잔차보다 관측값 사이의 어긋남을 비교하는 데 도움이 됩니다.</p><p><strong>영향력</strong>은 한 관측값을 뺐을 때 계수나 적합값이 얼마나 달라지는지에 관한 것입니다. Cook 거리는 이를 요약하는 지표입니다. 예제의 7번은 레버리지 h≈{seven['leverage']:.3f}, 표준화 잔차 r≈{seven['standardized']:.2f}, Cook 거리 D≈{seven['cook']:.3f}입니다.</p><p>높은 레버리지라도 직선과 잘 맞으면 영향력이 작을 수 있습니다. 반대로 큰 잔차와 높은 레버리지가 결합하면 영향력이 커질 수 있습니다. 경험적인 임계값은 추가 점검의 신호이며 자동 삭제 규칙이 아닙니다. 원자료와 조건, 포함·제외 결과를 확인하고 이유를 기록하세요.</p><details class="learn-more"><summary>레버리지·표준화 잔차·Cook 거리 산식</summary><div class="learn-more__body"><p>절편 포함 단순회귀에서 hᵢ=1/n+(xᵢ−x̄)²/Sxx이며 합은 추정 모수 수인 2입니다. 등분산 비상관 오차 모형에서 Var(eᵢ|X)=σ²(1−hᵢ)입니다.</p><p>내부 표준화 잔차 rᵢ=eᵢ/[s√(1−hᵢ)]는 전체 관측으로 추정한 s를 사용합니다. 해당 관측을 제외해 분산을 추정하는 외부 스튜던트화 잔차와 구별합니다.</p><p>이 단순회귀에서 Cook 거리 Dᵢ=(rᵢ²/2)·hᵢ/(1−hᵢ)입니다. 분모의 2는 절편과 기울기 두 모수를 뜻합니다. 이 예제에서는 모든 hᵢ가 1보다 작아 계산할 수 있습니다.</p></div></details>''')
 sec('workflow','진단 순서','그림의 단서를 수집 과정과 연결해 판단하세요','''<ol><li><strong>자료와 목적:</strong> 무엇을 한 관측으로 보았는지, 표집·시간·집단 구조와 분석 목적을 확인합니다.</li><li><strong>중심과 폭:</strong> 잔차 대 적합값·설명변수 그림에서 곡선이나 부채꼴 패턴을 봅니다.</li><li><strong>순서와 꼬리:</strong> 실제 시간·집단별 패턴과 Q–Q 그림을 확인합니다.</li><li><strong>영향 관측:</strong> 큰 잔차·레버리지·Cook 거리와 원자료를 살펴봅니다.</li><li><strong>조정과 재확인:</strong> 수집 과정과 이론에 근거해 모형이나 추론 방법을 조정하고 다시 점검합니다. 예측 목적이면 별도 자료로 평가합니다.</li></ol><p>잔차 그림이 깔끔해도 관측되지 않은 교란이 없거나 인과효과가 확인되었다는 뜻은 아닙니다. E[ε|X]=0 같은 조건은 잔차만으로 입증하기 어렵습니다. 변환·관측 제외 등 시도한 과정과 민감도, 남은 한계를 함께 보고해야 합니다.</p>''')
 sec('practice','확인 문제','무엇을 점검하는 그림인지 구별하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('잔차 합이 0이면 가정이 모두 만족되나요?','아니요. 절편 포함 OLS의 대수적 성질이며 곡선·이분산·의존성은 남을 수 있습니다.'),('Y가 비대칭이면 회귀계수를 계산할 수 없나요?','계산할 수 있습니다. 고전적 추론의 정규성은 조건부 오차에 관한 가정입니다.'),('큰 레버리지의 관측은 반드시 삭제하나요?','아니요. 원자료와 영향력, 포함·제외 민감도를 확인합니다.'),('강건 표준오차를 쓰면 누락변수 편향도 없어지나요?','아니요. 분산 추정의 조정과 평균 관계·내생성 문제는 구별해야 합니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','모형의 결과와 적용 조건을 함께 읽습니다','<p>회귀 결과를 읽을 때는 변수 정의·변환, 관측 단위·기간·건수, 잔차 진단과 구간 계산 방법을 함께 확인하세요. 서비스에 해당 진단이 제공되는지 먼저 확인하고, 제공되지 않은 통계량을 이미 검증된 것으로 간주하지 않습니다.</p><p>자료가 여러 지역·유형을 섞고 있다면 하나의 직선으로 설명할 수 있는 범위를 점검합니다. 잔차가 양수라는 이유만으로 개별 물건이 고평가되었다고 판단하지 않습니다.</p>')
 sec('recap','결론 · 학습 요약','잔차의 중심·폭·순서·꼬리·영향력을 나누어 점검하세요','''<p>잔차 진단은 모형을 한 번에 합격시키는 절차가 아니라, 자료와 모형의 어긋남을 이해하는 과정입니다. 다음을 구별해 두세요.</p><ul class="learn-recap-list"><li><strong>잔차의 중심:</strong> 곡선 패턴은 평균 관계를 직선으로 충분히 나타내지 못했을 가능성의 단서입니다.</li><li><strong>잔차의 폭:</strong> 부채꼴 패턴은 조건부 오차분산이 일정하지 않을 가능성의 단서입니다.</li><li><strong>관측 순서와 집단:</strong> 독립성은 실제 수집 과정과 시간·집단 구조에서 확인해야 합니다.</li><li><strong>정규성과 꼬리:</strong> 고전적 추론의 정규성은 오차에 관한 가정입니다. Q–Q 그림의 이탈만으로 원인을 확정하지 않습니다.</li><li><strong>관측값의 영향:</strong> 큰 잔차·높은 레버리지·큰 영향력은 다릅니다. 자동 삭제보다 원자료와 민감도 점검이 먼저입니다.</li></ul><p>다음 <a href="/learn/stats/multiple-regression/">19장 ‘다중회귀와 변수의 해석’</a>에서는 여러 변수를 함께 고려합니다.</p><details class="learn-more"><summary>참고자료와 계산값</summary><div class="learn-more__body"><ul><li><a href="https://www.itl.nist.gov/div898/handbook/pmd/section4/pmd44.htm">NIST: Model validation and residual analysis</a> — 모형 점검과 잔차 분석.</li><li><a href="../residuals-example.json">잔차·레버리지·Cook 거리와 Q–Q 좌표</a> — 반올림 전 계산값.</li></ul><p class="learn-source-note">참고자료의 기존 확인일: 2026-10-08. 계산은 17장과 같이 공통 학습 자료의 두 수치열을 단위 없는 X,Y로 사용했습니다. 곡선·부채꼴 그림은 설명을 위한 개념도입니다.</p></div></details>''')
 p=ROOT/'residuals/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="잔차와 회귀모형의 가정">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1잔차 그림으로 선형성·등분산·독립성·정규성과 영향력을 점검하는 방법을 학습합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261021-5',html);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
