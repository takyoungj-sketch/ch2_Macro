"""Build mean confidence-interval lesson; requires scipy for t quantiles."""
from pathlib import Path
from statistics import mean,stdev
from html import escape
import math,json,re,random
from scipy.stats import t as student_t,norm
ROOT=Path(__file__).resolve().parent

def interval(m,s,n,level=.95):
 critical=float(student_t.ppf((1+level)/2,n-1));margin=critical*s/math.sqrt(n)
 return {'mean':m,'sd':s,'n':n,'level':level,'critical':critical,'margin':margin,'low':m-margin,'high':m+margin}

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];v=[r['price'] for r in rows];m=mean(v);s=stdev(v);base=interval(m,s,30)
 rng=random.Random(20261007);repeats=[];z=float(norm.ppf(.975));mu=100;sigma=20;n=25
 for i in range(20):
  sample=[rng.gauss(mu,sigma) for _ in range(n)];avg=mean(sample);lo=avg-z*sigma/math.sqrt(n);hi=avg+z*sigma/math.sqrt(n);repeats.append({'id':i+1,'sample':sample,'mean':avg,'low':lo,'high':hi,'covers':lo<=mu<=hi})
 levels=[interval(m,s,30,c) for c in [.9,.95,.99]];sizes=[interval(m,s,n) for n in [10,30,120]]
 (ROOT/'confidence-example.json').write_text(json.dumps({'description':'공통 교육자료 계산과 별도 정규모형 반복표집 예제. 실제 시장 결과가 아님.','base':base,'levels':levels,'sizes':sizes,'simulation':{'seed':20261007,'mu':mu,'sigma':sigma,'n':25,'critical':z,'repeats':repeats}},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def text(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def line(x,y,xx,yy,c='#64748b',extra=''):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{c}" {extra}/>'
 def fig(id,title,b,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 def draw(d,y,key,scale=4):
  x=lambda v:90+(v-90)*scale
  b=line(x(d['low']),y,x(d['high']),y,'#2563eb',f'stroke-width="4" data-key="{key}" data-low="{d["low"]}" data-high="{d["high"]}"')
  for v in [d['low'],d['high']]:b+=line(x(v),y-8,x(v),y+8,'#2563eb')
  return b+f'<circle cx="{x(d["mean"])}" cy="{y}" r="5" fill="#d97706"/>'+text(x(d['low']),y+29,f'{d["low"]:.2f}','text-anchor="middle"')+text(x(d['high']),y+29,f'{d["high"]:.2f}','text-anchor="middle"')
 b=text(24,28,'평균 추정값에 오차한계를 붙입니다')+draw(base,115,'base')+text(260,80,f'평균 {m:.2f}')+text(24,195,f'95% 구간 = {m:.2f} ± {base["margin"]:.2f}')+text(24,230,'단위: 만원/㎡ · 주황 점은 표본평균')
 f1=fig('estimate','점추정과 구간추정',b,'그림 1. 공통 30건으로 계산한 평균의 t 구간입니다. 실제 시장의 타당한 95% 구간임을 검증한 결과가 아니라 산식 학습 예제입니다.',260)
 b=text(24,28,'같은 자료에서 신뢰수준만 높이면 구간이 넓어집니다')
 for i,d in enumerate(levels):b+=text(24,85+i*90,f'{d["level"]:.0%}')+draw(d,80+i*90,f'level-{d["level"]}')
 b+=text(24,330,'중심·s·n 고정 / 단위: 만원/㎡')
 f2=fig('levels','신뢰수준별 구간',b,'그림 3. 같은 30건의 양측 t 구간을 90%·95%·99%로 비교했습니다. 같은 자료·같은 방법에서 높은 신뢰수준에는 더 넓은 구간이 필요합니다.',355)
 b=text(24,28,'평균과 퍼짐을 고정한 표본수 비교입니다')
 for i,d in enumerate(sizes):b+=text(24,85+i*90,f'n={d["n"]}')+draw(d,80+i*90,f'n-{d["n"]}',3.7)
 b+=text(24,330,'신뢰수준 95% / 단위: 만원/㎡')
 f3=fig('sizes','표본수별 구간',b,'그림 4. 같은 평균과 s를 가정한 계획 비교입니다. 자유도에 따른 t 임계값도 다시 계산했습니다. 실제 10·120건을 수집한 결과가 아닙니다.',355)
 b=text(24,28,'반복하면 구간은 달라지고 모평균 100은 고정됩니다');x=lambda v:80+(v-80)*12
 b+=line(x(mu),45,x(mu),485,'#d97706','stroke-dasharray="4 3"')
 for i,d in enumerate(repeats):
  y=60+i*21;b+=text(24,y+4,d['id'])+line(x(d['low']),y,x(d['high']),y,'#2563eb' if d['covers'] else '#dc2626',f'stroke-width="2" data-repeat="{d["id"]}"')+f'<circle cx="{x(d["mean"])}" cy="{y}" r="3" fill="#475569"/>'
 b+=text(24,510,f'이번 20회: {sum(d["covers"] for d in repeats)}개 포함 / {sum(not d["covers"] for d in repeats)}개 미포함')
 for v in [80,90,100,110,120]:b+=text(x(v),545,v,'text-anchor="middle"')
 f4=fig('coverage','신뢰구간의 반복표집 해석',b,'그림 2. 가상 N(100,20²)에서 매번 독립 표본 25개를 뽑아 20회 반복했습니다. σ=20을 아는 별도 z 구간 예제입니다. 파랑은 μ 포함, 빨강은 미포함. 시드 20261007이며 표본 원자료를 JSON에 보존했습니다.',575)
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','핵심 이해','하나의 추정값과 그 불확실성을 함께 제시합니다','''<p>표본평균 하나로 모평균을 나타내면 <strong>점추정</strong>입니다. 표집 변동을 반영한 하한과 상한을 제시하면 <strong>구간추정</strong>입니다. 같은 표집을 다시 하면 점과 구간이 모두 달라질 수 있습니다.</p><p>이 장에서는 모평균 μ를 추정합니다. <a href="/learn/stats/sample-size/">11장의 표준오차</a>에 신뢰수준에 맞는 임계값을 곱해 구간을 만들고, 그 의미와 한계를 해석합니다. 관측값의 대부분이 어디에 있는지 나타내는 범위와는 다릅니다.</p>'''+f1)
 sec('formula','평균의 t 신뢰구간','추정값 ± 임계값 × 표준오차로 계산합니다','''<p>정규모집단에서 독립적으로 뽑은 동일분포 표본이며 모집단 표준편차 σ를 모를 때, 양측 100(1−α)% 신뢰구간은 <strong>x̄ ± t₁₋α/₂,ₙ₋₁ × s/√n</strong>입니다. s는 n−1로 계산한 표본표준편차, 자유도는 n−1입니다. n≥2이고 모집단 분산은 양수라고 가정합니다.</p><p>95%이면 α=0.05이며 양쪽 꼬리에 0.025씩 남깁니다. t 임계값은 자유도와 신뢰수준으로 결정됩니다. t분포는 σ를 s로 추정하는 불확실성을 반영해 표준정규분포보다 꼬리가 두껍고, 자유도가 커지면 정규분포에 가까워집니다.</p><p>σ를 알고 정규모집단을 가정하면 z×σ/√n을 사용합니다. ‘n이 30이면 무조건 z’라는 규칙으로 대체하지 않습니다. 비정규 자료의 t 구간은 충분한 표본과 적절한 조건에서 근사적으로 쓸 수 있지만, 심한 치우침·이상치·의존성에서는 명목 신뢰수준이 보장되지 않을 수 있습니다.</p>''')
 sec('calculation','공통 30건 계산','중간값은 반올림하지 않고 마지막에 표시합니다',f'''<p><a href="/learn/stats/graphs/#data">공통 학습 자료</a>에서 n=30, x̄={m:.5f}…, s={s:.5f}…, SE={s/math.sqrt(30):.5f}…입니다. 자유도 29의 95% 양측 t 임계값은 {base['critical']:.6f}…입니다.</p><p>오차한계는 t×SE={base['margin']:.5f}…이고, 구간은 <strong>{base['low']:.2f}~{base['high']:.2f}만원/㎡</strong>입니다. <a href="../confidence-example.json">계산 결과와 반복표집 원자료</a>에서 반올림 전 값을 확인할 수 있습니다.</p><p>이 30건은 실제 출처와 무작위 표집이 확인되지 않은 교육용 자료이며 분포도 치우쳐 있습니다. 위 계산은 t 산식을 익히는 예제입니다. 이 구간을 실제 시장 평균의 검증된 95% 신뢰구간으로 제시해서는 안 됩니다.</p>''')
 sec('coverage','95%의 의미','95%는 구간을 만드는 절차의 장기 포함률입니다','''<p>빈도주의 신뢰구간에서 모평균 μ는 고정된 값이고, 표집에 따라 구간이 달라집니다. 모형과 표집 가정이 맞을 때 같은 절차를 반복하면 만들어진 구간 중 장기적으로 약 95%가 μ를 포함한다는 뜻입니다.</p>'''+f4+'''<p>20회마다 정확히 19개가 포함되어야 하는 것은 아닙니다. 작은 반복 묶음에서는 비율이 흔들립니다. 이 그림은 그 원리를 보여 주는 별도 정규모형 실험이며 공통 30건의 표집 타당성을 검증하지 않습니다.</p><p>계산이 끝난 특정 구간에 대해 ‘고정된 μ가 이 안에 있을 확률이 95%’라고 해석하는 것은 이 빈도주의 절차의 의미가 아닙니다. 또한 ‘거래의 95%가 이 구간에 있다’, ‘다음 평균이 95% 확률로 이 안에 나온다’는 뜻도 아닙니다.</p>''')
 sec('levels','신뢰수준과 폭','더 높은 포함률을 원하면 더 넓은 구간이 필요합니다','''<p>같은 자료에서 90%·95%·99%를 비교하면 임계값이 커지면서 구간도 넓어집니다. 높은 신뢰수준이 항상 더 유용한 것은 아닙니다. 넓은 구간은 더 많은 값을 포함하지만 정밀한 구분에는 불리합니다.</p>'''+f2+'''<p>신뢰수준은 결과를 본 뒤 원하는 결론에 맞춰 바꾸지 말고 분석 목적에 맞게 정합니다. 여러 지역·변수의 구간을 동시에 살펴보면 각 구간의 95%와 전체가 동시에 포함되는 확률도 구별해야 합니다.</p>''')
 sec('sizes','표본수와 폭','퍼짐과 표집 조건이 같아야 건수 효과를 비교할 수 있습니다','''<p>평균의 오차한계는 t×s/√n입니다. 신뢰수준과 퍼짐이 같으면 표본수가 커질수록 좁아지고, 같은 n이면 퍼짐이 클수록 넓어집니다. t 임계값도 자유도에 따라 달라집니다.</p>'''+f3+'''<p>실제로 표본을 늘리면 평균과 s도 바뀔 수 있어 매번 구간 폭이 줄어든다고 보장하지 않습니다. 같은 거래를 복사하거나 같은 단지의 강하게 연관된 관측을 늘리는 것도 독립적인 새 정보를 늘리는 것과 다릅니다.</p>''')
 sec('other-intervals','다른 구간과 구별','평균 신뢰구간은 개별 거래 예측구간이 아닙니다','''<p><strong>평균 신뢰구간</strong>은 모평균을 추정합니다. <strong>예측구간</strong>은 같은 모형에서 새로 관측할 개별 값의 변동까지 고려합니다. 정규모형의 한 미래 독립 관측에 대한 구간은 x̄±t×s√(1+1/n) 형태로, 같은 조건의 평균 신뢰구간보다 넓습니다. 실제 미래 거래에는 시점 변화 등의 불확실성도 있어 이 공식만으로 해결되지 않습니다.</p><p>분위수 구간은 분포의 위치를, 허용구간은 정해진 모집단 비율을 일정 신뢰수준으로 포괄하는 범위를 다룹니다. 베이지안 신용구간은 사전분포와 자료를 반영한 사후분포에 대한 확률 진술입니다. 서로 다른 질문에 답하므로 같은 ‘95%’라는 표기만 보고 혼용하지 않습니다.</p>''')
 sec('limits','가정과 보고','좁은 구간도 편향된 자료를 바로잡지는 못합니다','''<p>수집 편향·누락·잘못된 단위·중복·군집 의존성이 있으면 단순 t 구간이 실제 불확실성을 반영하지 못할 수 있습니다. 표본수가 커지면 잘못된 대상을 더 정밀하게 추정할 수도 있습니다. 02장과 10장의 표집 가정을 먼저 확인합니다.</p><p>비율·중앙값·회귀계수에는 각 통계량에 맞는 구간 계산이 필요합니다. 재표집하는 부트스트랩도 대안이 될 수 있지만 표본의 대표성이나 의존성을 자동으로 해결하지 않습니다. 이 장의 평균 공식을 모든 지표에 붙이지 않습니다.</p><p>보고할 때는 추정 대상, 지역·기간·관측 단위, 유효 n, 점추정값, 구간 양 끝과 단위, 신뢰수준, 계산 방법과 가정을 함께 제시합니다. 두 집단의 구간이 겹친다는 이유만으로 차이가 없다고 결론 내리지 않습니다. 비교하려면 차이 자체의 구간이나 적절한 검정이 필요합니다.</p>''')
 sec('practice','확인 문제','구간이 답하는 질문부터 확인하세요','''<ol class="learn-exercises"><li>95% 평균 신뢰구간에 관측 거래의 95%가 포함되나요?<details><summary>답과 해설</summary><p>아니요. 모평균 추정 구간이며 관측값 분포를 포괄하는 범위가 아닙니다.</p></details></li><li>같은 표본에서 신뢰수준을 95%에서 99%로 높이면 폭은?<details><summary>답과 해설</summary><p>같은 방법이라면 임계값이 커져 넓어집니다.</p></details></li><li>20개의 95% 구간 중 반드시 19개가 μ를 포함하나요?<details><summary>답과 해설</summary><p>아니요. 95%는 장기 포함률이고 작은 반복 묶음의 결과는 달라질 수 있습니다.</p></details></li><li>자료가 편향되었어도 n이 커 구간이 좁으면 믿을 수 있나요?<details><summary>답과 해설</summary><p>구간 폭은 수집 편향을 포함하지 않을 수 있습니다. 좁다는 사실만으로 타당성이 확보되지 않습니다.</p></details></li></ol>''')
 sec('macro','CH2 Macro에서 읽기','추정 대상과 화면의 산식을 먼저 확인합니다','''<p>CH2 Macro의 평균·건수·분포를 읽을 때는 선택한 지역·기간·유형이 어떤 집단을 뜻하는지 확인하세요. 이 장의 교재 계산이 모든 화면에서 제공되는 산식이라고 가정하지 않습니다. 구간이 표시된 경우 무엇의 구간인지, 수준과 계산 가정이 무엇인지 설명을 함께 봅니다.</p><p>시장 평균의 구간을 개별 물건의 적정가격 범위나 미래 가격 상승 확률로 바꿔 해석하지 않습니다.</p><p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 통계 열기 →</a></p>''')
 sec('recap','정리와 참고자료','추정값·구간·가정을 함께 읽습니다','''<p>점추정은 하나의 값을, 신뢰구간은 표집 변동을 반영한 범위를 제시합니다. 95%는 구간 생성 절차의 장기 포함률이며 실제 자료의 대표성을 보장하는 숫자는 아닙니다.</p><p>다음 <a href="/learn/stats/hypothesis-tests/">13장 「가설검정과 p값」</a>에서 기준값과 관측 결과의 관계를 판단하는 방법을 배웁니다.</p><ul><li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm">NIST/SEMATECH: Confidence Limits for the Mean</a> — 평균 구간의 산식과 해석.</li></ul><p class="learn-source-note">본문과 그림은 공통 학습 자료 및 별도 가상 모형으로 직접 작성했습니다. 임계값은 SciPy t·정규 분위수로 계산했습니다. 참고자료 확인: 2026-10-07.</p>''')
 p=ROOT/'confidence-intervals/index.html';s=p.read_text(encoding='utf-8');s=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="점추정과 신뢰구간">\n'+'\n'.join(parts)+'\n</article>',s,count=1,flags=re.S)
 s=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1점추정과 평균의 t 신뢰구간, 95%의 의미와 구간 폭의 변화를 그림과 예제로 설명합니다.\2',s,count=1,flags=re.S);p.write_text(s,encoding='utf-8')
if __name__=='__main__':build()
