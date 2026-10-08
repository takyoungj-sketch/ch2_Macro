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
 d=dict(description='출처 미확인 공통 학습 자료 30건의 절편 포함 단순 OLS 진단',n=n,df=n-2,SSE=f['SSE'],s=s,RMSE=math.sqrt(f['SSE']/n),MAE=mean(abs(e) for e in f['residuals']),rows=ds,qq=qq)
 (ROOT/'residuals-example.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def text(x,y,v):return f'<text x="{x}" y="{y}">{escape(str(v))}</text>'
 def line(x,y,xx,yy):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="#94a3b8"/>'
 def dot(x,y,id='',color='#2563eb'):return f'<circle cx="{x}" cy="{y}" r="4" fill="{color}" data-id="{id}"/>'
 def fig(id,title,b,cap,h=390):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=text(24,28,'잔차(만원/㎡)')+line(65,255,580,255)+line(65,55,65,335)
 for v in [-100,0,100,200]:b+=text(24,260-v*.7,v)
 for v in [0,50,100,150,200]:b+=text(65+v*2.2,355,v)
 for row in ds:
  cx=65+row['fitted']*2.2;cy=255-row['residual']*.7;b+=dot(cx,cy,row['id'])
  if row['id']==7:b+=text(cx-42,cy-12,'7번')
 b+=text(400,382,'적합 단가(만원/㎡)');g1=fig('resplot','적합값과 잔차',b,'그림 1. 공통 자료 30건의 적합값과 잔차입니다. 0선 주변의 모양과 큰 잔차를 함께 봅니다. 가로축은 관측 단가가 아닌 적합 단가입니다.',410)
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
 b+=text(24,378,'세로: 잔차(만원/㎡) · 주황: 잔차 0, 척도 s의 참고선')
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
 sec('quick-start','잔차 읽기','직선을 그린 다음에는 남은 차이를 살펴봅니다',f'<p>17장에서 구한 직선이 자료를 충분히 설명하는지 확인하려면 <strong>잔차 eᵢ=yᵢ−ŷᵢ</strong>를 봅니다. 양수는 모형이 관측값보다 낮게, 음수는 높게 적합했다는 뜻입니다. 미지의 모집단 오차 ε와 표본에서 계산한 잔차 e는 구별합니다.</p><p>공통 자료 7번의 관측 단가는 480, 적합값은 {seven["fitted"]:.2f}, 잔차는 +{seven["residual"]:.2f}만원/㎡입니다. 반올림 전 계수로 계산했습니다. 이 자료는 출처 미확인 학습 예제이며 실제 시장의 가격모형이 아닙니다.</p>'+g1)
 sec('scale','잔차의 크기','오차의 크기를 요약할 때 분모를 확인합니다',f'<p>잔차 합이 0이라는 사실은 절편 포함 OLS의 계산 성질입니다. 잘 맞는 모형이라는 증거는 아닙니다. 공통 자료의 SSE=Σeᵢ²는 {f["SSE"]:,.2f}, MAE=Σ|eᵢ|/n은 {d["MAE"]:.2f}, 학습 RMSE=√(SSE/n)은 {d["RMSE"]:.2f}입니다.</p><p>절편과 기울기 두 모수를 적합했으므로 잔차 자유도는 n−2=28입니다. 오차 표준편차의 추정값인 <strong>잔차 표준오차 s=√(SSE/(n−2))={s:.2f}</strong>는 학습 RMSE와 분모가 다릅니다. s²의 불편성에는 올바른 선형 평균·등분산·비상관 오차 등의 조건이 필요합니다. s 자체가 불편추정량이라는 뜻은 아닙니다.</p><p>MAE·RMSE·s는 모두 Y와 같은 단위입니다. 여기서는 만원/㎡이며, 학습 자료의 크기 요약을 새 거래의 예측 정확성으로 옮겨 읽지 않습니다.</p>')
 sec('patterns','선형성과 등분산','잔차의 중심과 폭을 따로 봅니다','<p>적합값에 따라 잔차의 중심이 U자나 물결 모양으로 움직이면 직선이 평균 관계를 놓쳤을 수 있습니다. 제곱항·변환·누락된 집단 등 가능한 설명을 자료의 생성 과정과 함께 검토합니다. 단순히 곡선을 더 복잡하게 만들어 학습 오차를 줄이는 것이 목적은 아닙니다.</p>'+g2+'<p>중심은 0 근처여도 폭이 커지면 이분산을 의심합니다. 등분산은 Var(ε|X)=σ²라는 조건으로, X나 Y 자체의 분산이 일정하다는 말이 아닙니다. 이분산에서도 E[ε|X]=0 등 조건이 맞으면 OLS 계수는 불편할 수 있지만, 일반적인 등분산 표준오차는 잘못될 수 있습니다.</p><p>가능한 대응에는 분산 구조를 반영한 가중최소제곱, 의미 있는 변환, 이분산 강건 표준오차가 있습니다. 강건 표준오차는 평균 함수의 오류·내생성·극단적인 외삽을 해결하지 않습니다.</p>')
 sec('independence','독립성과 순서','시간과 집단 구조는 자료 수집 과정에서 확인합니다','<p>잔차를 거래 시점 순서로 그렸을 때 양수가 연속되거나 주기적으로 오르내리면 시간 의존성이나 빠진 추세를 의심합니다. 동일 단지·지역에서 나온 거래는 공통 요인 때문에 서로 닮을 수 있습니다. 독립성과 단순한 무상관은 같은 조건이 아닙니다.</p><p>공통 자료의 번호는 시간 정보가 아니므로 번호 순 잔차를 시계열 진단으로 해석하지 않습니다. 실제 거래일·단지 식별자를 확인한 후 시간 그래프나 집단별 잔차를 살펴야 합니다. 의존성이 있으면 군집 표준오차·시계열 모형 등 설계에 맞는 방법을 검토합니다.</p><p>모집단 오차가 독립이더라도 같은 자료로 적합한 OLS 잔차들은 잔차 합 0 등의 제약으로 서로 연결됩니다. 잔차를 완전히 독립인 오차 관측치처럼 취급해서는 안 됩니다.</p>')
 sec('normality','정규성','정규성은 계수 계산보다 추론의 조건입니다','<p>OLS 직선을 계산하는 데 정규성은 필요하지 않습니다. 고전적인 작은 표본 t·F 검정과 구간을 정확하게 적용할 때는 설명변수에 조건부인 오차의 정규성 등 가정이 사용됩니다. X나 Y의 히스토그램이 정규 모양이어야 한다는 뜻은 아닙니다.</p>'+g3+'<p>Q–Q 그림에서 점들이 대체로 직선에 놓이는지, 특히 양쪽 꼬리가 벗어나는지 봅니다. 이탈은 극단 관측·두꺼운 꼬리·평균 함수의 오류 등 여러 원인과 관련될 수 있습니다. 이 그림만으로 원인을 특정하거나 정규성을 확정하지 않습니다.</p><p>표본 30건에서는 진단의 불확실성도 큽니다. 정규성 검정의 p값 하나로 합격·불합격을 정하기보다 잔차 패턴, 설계, 영향 관측과 함께 판단합니다. 큰 표본의 근사 추론도 적절한 의존성·분산 조건을 필요로 합니다.</p>')
 sec('influence','레버리지와 영향력','큰 잔차와 멀리 있는 X를 구별합니다',f'<p>절편 포함 단순회귀의 레버리지는 <strong>hᵢ=1/n+(xᵢ−x̄)²/Sxx</strong>입니다. X가 평균에서 멀수록 커지며 합은 추정 모수 수인 2입니다. 같은 오차분산에서도 Var(eᵢ|X)=σ²(1−hᵢ)이므로 원 잔차의 크기만으로 관측을 비교하면 불공평할 수 있습니다.</p>'+g4+f'<p>내부 표준화 잔차 rᵢ=eᵢ/[s√(1−hᵢ)]는 이러한 차이를 보정합니다. 여기서는 모든 관측으로 추정한 s를 사용하며, 해당 관측을 제외해 분산을 추정하는 외부 스튜던트화 잔차와 구별합니다.</p><p>Cook 거리 Dᵢ=(rᵢ²/2)·hᵢ/(1−hᵢ)는 그 점을 뺐을 때 적합값이 얼마나 달라지는지 요약합니다. 7번은 h={seven["leverage"]:.3f}, r={seven["standardized"]:.2f}, D={seven["cook"]:.3f}입니다. 임계값은 점검을 위한 경험적 기준일 뿐 자동 삭제 규칙이 아닙니다.</p><p>높은 레버리지라도 직선과 잘 맞으면 영향력이 작을 수 있습니다. 원자료 오류, 특이한 거래 조건, 포함·제외 결과를 확인하고 판단 근거를 기록하세요.</p>')
 sec('workflow','진단 순서','목적과 설계를 먼저 확인하고 모형을 다시 점검합니다','<ol><li>관측 단위·표집·시간·집단 구조와 분석 목적을 확인합니다.</li><li>잔차 대 적합값·설명변수 그림으로 평균 관계와 분산을 봅니다.</li><li>실제 시간·집단별 패턴, Q–Q 그림, 영향 관측을 살펴봅니다.</li><li>이론과 수집 과정에 근거해 모형이나 추론 방법을 조정합니다.</li><li>조정 후 진단을 반복하고, 예측 목적이면 별도 자료로 성능을 확인합니다.</li></ol><p>잔차 그림이 깔끔해도 E[ε|X]=0이나 인과 식별을 입증한 것은 아닙니다. 관측되지 않은 교란은 잔차만으로 확인하기 어렵습니다. 변환·관측 제외 등을 시도한 과정을 숨기지 말고 민감도와 한계를 함께 보고합니다.</p>')
 sec('practice','확인 문제','무엇을 점검하는 그림인지 구별하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('잔차 합이 0이면 가정이 모두 만족되나요?','아니요. 절편 포함 OLS의 대수적 성질이며 곡선·이분산·의존성은 남을 수 있습니다.'),('Y가 비대칭이면 회귀계수를 계산할 수 없나요?','계산할 수 있습니다. 고전적 추론의 정규성은 조건부 오차에 관한 가정입니다.'),('큰 레버리지의 관측은 반드시 삭제하나요?','아니요. 원자료와 영향력, 포함·제외 민감도를 확인합니다.'),('강건 표준오차를 쓰면 누락변수 편향도 없어지나요?','아니요. 분산 추정의 조정과 평균 관계·내생성 문제는 구별해야 합니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','모형의 결과와 적용 조건을 함께 읽습니다','<p>회귀 결과를 읽을 때는 변수 정의·변환, 관측 단위·기간·건수, 잔차 진단과 구간 계산 방법을 함께 확인하세요. 서비스에 해당 진단이 제공되는지 먼저 확인하고, 제공되지 않은 통계량을 이미 검증된 것으로 간주하지 않습니다.</p><p>자료가 여러 지역·유형을 섞고 있다면 하나의 직선으로 설명할 수 있는 범위를 점검합니다. 잔차가 양수라는 이유만으로 개별 물건이 고평가되었다고 판단하지 않습니다.</p>')
 sec('recap','정리와 참고자료','진단은 모형을 이해하고 개선하는 과정입니다','<p>잔차의 중심·폭·순서·꼬리·영향력을 나누어 점검하세요. 적합도 숫자 하나나 검정 하나로 모형의 타당성을 확정할 수 없습니다.</p><p>다음 <a href="/learn/stats/multiple-regression/">19장 「다중회귀와 변수의 해석」</a>에서 여러 변수를 함께 고려합니다.</p><ul><li><a href="https://www.itl.nist.gov/div898/handbook/pmd/section4/pmd44.htm">NIST: Model validation and residual analysis</a></li><li><a href="../residuals-example.json">공통 자료 잔차·레버리지·Cook 거리와 Q–Q 좌표</a></li></ul><p class="learn-source-note">본문·그림은 공통 학습 자료와 별도 개념도로 직접 작성했습니다. 참고자료 확인: 2026-10-08.</p>')
 p=ROOT/'residuals/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="잔차와 회귀모형의 가정">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1잔차 그림으로 선형성·등분산·독립성·정규성과 영향력을 점검하는 방법을 학습합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
