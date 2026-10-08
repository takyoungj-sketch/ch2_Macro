"""Exact sampling distributions for a fictional Bernoulli population."""
from pathlib import Path
from html import escape
import math,json,re
from _build_distributions_chapter import binomial
ROOT=Path(__file__).resolve().parent

def build():
 data={'description':'가상 독립 베르누이 모형 p=0.2의 정확한 표본평균 분포. 모의실험 빈도가 아님.','p':.2,'distributions':[{'n':n,'probabilities':binomial(n,.2)} for n in [1,5,30,100]]}
 (ROOT/'sampling-distributions-example.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def t(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def line(x,y,xx,yy,extra=''):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="#64748b" {extra}/>'
 def fig(id,title,b,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=t(24,28,'같은 n=5로 반복 추출하고, 매번 평균 하나를 남깁니다')
 for i,values in enumerate([[0,0,0,0,0],[0,1,0,0,0],[1,0,1,0,0]]):
  y=85+i*65;b+=t(24,y,f'표본 {i+1}')+t(130,y,' · '.join(map(str,values)))+t(350,y,'→')+t(400,y,f'평균 {sum(values)/5:.1f}')
 b+=t(24,293,'각 표본 안의 값 5개 ≠ 반복해서 모은 평균 3개')
 f1=fig('repeated','표본과 표본평균',b,'그림 1. 반복 추출의 구조를 설명하는 가상 세 표본입니다. 실제 시뮬레이션 결과나 같은 확률로 나타나는 대표 표본이 아닙니다. 반복마다 n=5를 유지합니다.',320)
 b=t(24,26,'원자료는 계속 0 또는 1, 평균의 분포만 달라집니다')
 for i,d in enumerate(data['distributions']):
  n=d['n'];base=140+i*140;b+=t(200,base-90,f'n={n} · 평균 0.20 · SE={.4/math.sqrt(n):.3f}')+line(70,base,570,base)
  for k,p in enumerate(d['probabilities']):b+=line(70+500*k/n,base,70+500*k/n,base-100*p/.8,f'stroke-width="3" data-n="{n}" data-k="{k}" data-probability="{p}"')
  for v in [0,.2,.4,.6,.8,1]:b+=t(70+500*v,base+23,f'{v:.1f}','text-anchor="middle"')
 b+=t(24,605,'공통 세로축: 확률 0~0.8 / 공통 가로축: 표본평균')
 f2=fig('exact','표본수별 정확한 표본평균 분포',b,'그림 2. p=0.2인 독립 베르누이 시행. 막대 위치 k/n과 높이 P(K=k)를 이항공식으로 계산했습니다. 각 줄의 확률 합은 1이며 n이 커져도 유한 n에서는 이산분포입니다.',636)
 b=t(24,28,'표준오차를 절반으로 줄이려면 n을 네 배로 늘립니다')
 for i,n in enumerate([1,4,16,64]):
  y=75+i*65;se=.4/math.sqrt(n);b+=t(24,y+19,f'n={n}')+f'<rect x="145" y="{y}" width="{se*900}" height="25" fill="#2563eb" data-n="{n}" data-se="{se}"/>'+t(155+se*900,y+19,f'{se:.2f}')
 b+=t(24,367,'개별 X의 표준편차 σ=0.40은 그대로입니다')
 f3=fig('se','표본수와 표준오차',b,'그림 3. 같은 가상 모집단에서 SE=0.4/√n입니다. 표준오차는 표본평균의 퍼짐이며 개별 관측값의 표준편차와 다릅니다.',392)
 b=t(24,28,'표본평균을 표준화해 모양을 비교합니다')
 for i,n in enumerate([5,100]):
  base=215+i*220;b+=t(24,base-150,f'n={n} · Z=(평균−0.2)/(0.4/√n)')+line(60,base,580,base)
  for k,p in enumerate(binomial(n,.2)):
   z=(k/n-.2)/(.4/math.sqrt(n));dz=1/(n*(.4/math.sqrt(n)))
   if -4<=z<=4:b+=line(320+z*60,base,320+z*60,base-p/dz*270,'stroke="#93c5fd" stroke-width="3"'.replace('stroke="#93c5fd" ',''))
  pts=[(320+z*60,base-math.exp(-z*z/2)/math.sqrt(2*math.pi)*270) for z in [-4+j*.04 for j in range(201)]]
  b+='<polyline points="'+' '.join(f'{x:.4f},{y:.4f}' for x,y in pts)+'" fill="none" stroke="#d97706" stroke-width="2"/>'
  for z in [-4,-2,0,2,4]:b+=t(320+z*60,base+24,z,'text-anchor="middle"')
 b+=t(24,503,'선: 표준정규 밀도 / 막대 높이: 확률÷격자 간격')
 f4=fig('standardized','표준화한 표본평균과 정규 근사',b,'그림 4. 막대 높이는 확률질량을 z값의 간격으로 나눈 밀도 환산값입니다. 주황선은 표준정규 밀도입니다. 높이 자체가 한 점의 확률은 아니며 −4~4 구간만 표시했습니다.',533)
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','핵심 이해','같은 모집단에서도 표본평균은 매번 달라집니다','''<p>한 지역에서 거래 30건을 뽑아 평균을 구했다고 생각해 보세요. 같은 방식으로 다시 30건을 뽑으면 다른 거래가 포함되어 평균도 달라질 수 있습니다. <strong>표본분포</strong>는 이렇게 표집을 반복할 때 통계량이 가질 수 있는 값과 확률의 분포입니다.</p><p>09장에서 개별 확률변수의 분포를 배웠다면, 이 장에서는 여러 관측으로 계산한 평균을 새로운 확률변수로 봅니다. 실제로 표본을 여러 번 수집해야만 표본분포가 정의되는 것은 아닙니다. 반복 표집은 그 의미를 이해하는 사고실험이고, 분포는 수학적으로도 구할 수 있습니다.</p>'''+f1)
 sec('distinctions','세 분포의 구분','모집단·한 표본·통계량의 분포는 서로 다릅니다','''<p><strong>모집단 분포</strong>는 관측 대상의 값들이 어떻게 분포하는지 나타냅니다. <strong>표본의 경험분포</strong>는 실제로 뽑은 n개 값의 분포이고, <strong>표본평균의 표본분포</strong>는 같은 n과 같은 표집 방법을 반복했을 때 얻는 평균들의 분포입니다.</p><p>표본 한 개에 값이 n개 있다는 것과 표본 추출을 B번 반복했다는 것을 구분하세요. 반복 횟수 B를 늘리면 시뮬레이션으로 그린 분포가 안정되지만, 한 표본의 정보량 n이 늘어난 것은 아닙니다. 같은 n의 이론적 표준오차도 B 때문에 작아지지 않습니다.</p><p>표본분포는 평균뿐 아니라 비율·중앙값·회귀계수에도 있습니다. 다만 이 장의 평균 공식과 중심극한정리를 모든 통계량에 그대로 적용할 수는 없습니다.</p>''')
 sec('exact','정확한 계산 예제','0과 1의 평균으로 표본분포를 직접 구합니다','''<p>설명용 가상 모집단에서 X=1일 확률을 0.2, X=0일 확률을 0.8로 정합니다. 각 관측은 독립이고 같은 분포를 따릅니다. 실제 부동산 비율이 아닙니다. 개별 X의 평균 μ=0.2, 분산 σ²=0.16, 표준편차 σ=0.4입니다.</p><p>n개 중 1의 개수 K는 Bin(n,0.2)이므로 표본평균 X̄=K/n입니다. 따라서 P(X̄=k/n)=C(n,k)0.2ᵏ0.8ⁿ⁻ᵏ입니다. n=5이면 가능한 평균은 0·0.2·0.4·0.6·0.8·1이고 확률은 각각 0.32768·0.4096·0.2048·0.0512·0.0064·0.00032입니다.</p>'''+f2+'''<p>네 줄은 같은 원자료 모형을 사용합니다. n이 커질수록 평균은 0.2 근처에 모이지만 개별 X가 0 또는 1이라는 사실은 바뀌지 않습니다. 그림은 난수 시뮬레이션이 아니라 <a href="../sampling-distributions-example.json">이항공식으로 계산한 정확한 확률표</a>입니다.</p>''')
 sec('standard-error','평균의 중심과 표준오차','평균의 분산은 독립 표본수로 나뉩니다','''<p>독립이고 동일한 분포에서 얻은 X₁,…,Xₙ이 유한한 평균 μ와 분산 σ²를 가질 때 <strong>E[X̄]=μ, Var(X̄)=σ²/n, SE(X̄)=σ/√n</strong>입니다. 이 평균·분산 공식은 정규근사를 하지 않아도 성립합니다.</p><p>X̄=(X₁+…+Xₙ)/n이므로 기대값은 nμ/n=μ입니다. 독립인 관측의 분산을 더한 nσ²를 n²으로 나누면 σ²/n이 됩니다. 표준오차(SE)는 통계량의 표본분포의 표준편차입니다.</p>'''+f3+'''<p>가상 모형에서 n=25이면 SE=0.08, n=100이면 SE=0.04입니다. 표본수를 네 배로 늘려야 표준오차가 절반이 됩니다. 모집단 σ를 모를 때 흔히 s/√n으로 추정하지만 표집 설계와 의존성을 확인해야 합니다. 자세한 계산은 11장에서 이어집니다.</p>''')
 sec('clt','중심극한정리','표준화한 평균의 분포가 정규분포에 가까워집니다','''<p>독립·동일분포, 유한한 평균과 양의 유한 분산이라는 기본 조건 아래, n이 커지면 <strong>Zₙ=(X̄−μ)/(σ/√n)</strong>의 분포가 표준정규분포에 수렴합니다. 이를 표본평균에 대한 중심극한정리라고 합니다. 유한 n에서는 X̄를 대략 N(μ,σ²/n)으로 근사합니다. 여기서 두 번째 매개변수는 분산입니다.</p>'''+f4+'''<p>원자료가 비대칭이어도 평균의 분포는 정규모양에 가까워질 수 있습니다. 표준화하지 않은 평균은 μ 주변으로 좁아지므로, 정리의 정확한 진술은 표준화한 Zₙ의 분포에 관한 것입니다. 원자료가 정규분포이고 독립이라면 표본평균은 모든 n에서 정확히 정규분포입니다.</p><p>n=30은 보편적인 보장 기준이 아닙니다. 원자료의 치우침·꼬리·희귀 사건 비율과 어떤 구간의 확률을 근사하는지에 따라 필요한 표본수가 달라집니다. 이항모형에서는 np와 n(1−p)가 모두 충분한지 살펴야 하며, 경계와 꼬리 확률에는 특히 주의합니다.</p>''')
 sec('approximation','정확한 확률과 근사','연속성 보정은 정수 경계를 반영합니다','''<p>같은 모형에서 n=100이면 K의 평균은 20, 표준편차는 4입니다. ‘표본비율이 0.15 이상 0.25 이하’는 정수 개수로 15≤K≤25입니다. 정확한 확률은 이항확률을 k=15부터 25까지 합한 값입니다.</p>'''+f'''<p>정확한 값은 <strong>{sum(binomial(100,.2)[15:26]):.4f}</strong>입니다. 정규근사에서 정수 칸의 폭을 고려해 14.5~25.5를 쓰면 z 경계는 ±1.375이고 근사 확률은 <strong>{math.erf(1.375/math.sqrt(2)):.4f}</strong>입니다. 이것이 연속성 보정입니다. 두 값이 가깝더라도 모든 표본수·꼬리 구간에서 근사가 정확하다는 뜻은 아닙니다.</p>''')
 sec('limits','가정과 해석의 한계','큰 표본도 편향과 의존성을 자동으로 없애지 않습니다','''<p>특정 유형만 목록에 잡히는 수집 편향이 있으면 큰 표본이 그 목록의 평균을 정밀하게 추정할 뿐 목표 모집단의 평균과 같아지지는 않을 수 있습니다. 02장의 표집틀과 편향 문제는 중심극한정리로 해결되지 않습니다.</p><p>같은 단지·지역·시점의 관측은 서로 연관될 수 있습니다. 일반적으로 Var(X̄)=[ΣVar(Xᵢ)+2Σᵢ&lt;ⱼCov(Xᵢ,Xⱼ)]/n²입니다. 양의 상관이 크면 독립을 가정한 σ/√n이 불확실성을 과소평가할 수 있습니다.</p><p>유한 모집단 N개에서 단순무작위 비복원으로 n개를 뽑는 경우에도 독립 공식과 다릅니다. 모집단 분산을 N으로 나눈 σ²로 정의하면 SE=σ/√n×√((N−n)/(N−1))입니다. 전수 n=N이면 고정된 그 모집단 평균에 대한 표집오차는 0이지만 측정 오류나 미래에 대한 불확실성까지 없어지지는 않습니다.</p><p>분산이 무한한 매우 두꺼운 꼬리 모형은 이 기본 정리의 조건을 벗어납니다. 심한 꼬리·군집·시간 의존성이 있으면 다른 이론이나 표집 설계에 맞는 방법을 검토해야 합니다. 반복 관측을 독립 표본으로 단순히 세지 않습니다.</p>''')
 sec('lln','대수의 법칙과의 구분','평균이 안정되는 것과 오차의 모양을 설명하는 것은 다릅니다','''<p>대수의 법칙은 적절한 조건 아래 표본평균이 모집단 평균에 가까워진다는 결과입니다. 중심극한정리는 표준화한 평균의 오차 분포를 정규분포로 설명합니다. 두 결과는 관련 있지만 같은 문장은 아닙니다.</p><p>‘많이 모으면 원자료가 정규분포가 된다’, ‘오차가 항상 0이 된다’, ‘다음 관측이 평균 근처여야 한다’는 해석은 모두 피해야 합니다. 평균 추정의 불확실성과 개별 거래의 다양성을 구분하세요.</p>''')
 sec('practice','확인 문제','n과 반복 횟수, SD와 SE를 구별하세요','''<ol class="learn-exercises"><li>n=25 표본을 1,000회에서 10,000회로 더 많이 모의 추출하면 이론적 SE가 줄어드나요?<details><summary>답과 해설</summary><p>아니요. 분포를 더 정확하게 그릴 수 있지만 한 표본의 n과 표집 모형이 같으므로 SE는 같습니다.</p></details></li><li>σ=0.4일 때 n=25와 n=100의 SE는?<details><summary>답과 해설</summary><p>각각 0.08과 0.04입니다. 표본수 네 배가 SE 절반에 대응합니다.</p></details></li><li>평균의 분포가 정규모양에 가까워지면 원자료의 치우침도 사라지나요?<details><summary>답과 해설</summary><p>아니요. 원자료와 표본평균의 분포는 다른 대상입니다.</p></details></li><li>표본수가 크면 수집 편향이 사라지나요?<details><summary>답과 해설</summary><p>아니요. 잘못된 표집틀에서 많이 수집하면 목표와 다른 평균을 정밀하게 추정할 수 있습니다.</p></details></li></ol>''')
 sec('macro','CH2 Macro에서 읽기','거래 건수만으로 정밀도를 판단하지 않습니다','''<p>CH2 Macro에서 지역·기간별 평균을 비교할 때는 건수뿐 아니라 거래 구성, 퍼짐, 수집 범위와 관측 간 의존성을 함께 보세요. 큰 건수는 정보량을 늘릴 수 있지만 모든 거래가 동일하고 독립적인 정보 한 단위라는 보장은 없습니다.</p><p>이 장의 가상 베르누이 모형과 표준오차를 서비스 가격 통계에 그대로 적용하지 않습니다. 미래 가격이나 개별 물건의 불확실성은 과거 표본평균의 표집오차와 다릅니다.</p><p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 통계 열기 →</a></p>''')
 sec('recap','정리와 참고자료','분포의 대상을 먼저 확인합니다','''<p>표본분포는 반복 표집에서 통계량이 달라지는 모습입니다. 독립·동일분포와 유한 분산 조건에서 평균의 SE는 σ/√n이며, 표준화한 평균의 분포는 n이 커지면 정규분포에 가까워집니다. 정밀도와 대표성을 함께 확인해야 합니다.</p><p>다음 <a href="/learn/stats/sample-size/">11장 「표준오차와 표본수」</a>에서 관측 자료로 불확실성을 읽는 방법을 이어갑니다.</p><ul><li><a href="https://openstax.org/books/introductory-statistics-2e/pages/7-1-the-central-limit-theorem-for-sample-means-averages">OpenStax §7.1: Central Limit Theorem for Sample Means</a> — 표본평균의 분포와 표준오차.</li></ul><p class="learn-source-note">그림은 직접 계산한 가상 확률모형과 개념도입니다. 실제 거래 결과가 아닙니다. 참고자료 확인: 2026-10-07.</p>''')
 p=ROOT/'sampling-distributions/index.html';p.parent.mkdir(exist_ok=True);s=p.read_text(encoding='utf-8') if p.exists() else (ROOT/'probability-distributions/index.html').read_text(encoding='utf-8')
 s=s.replace('https://ch2data.com/learn/stats/probability-distributions/','https://ch2data.com/learn/stats/sampling-distributions/')
 s=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="표본분포와 중심극한정리">\n'+'\n'.join(parts)+'\n</article>',s,count=1,flags=re.S)
 s=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1표본평균의 분포, 표준오차와 중심극한정리를 정확한 확률 계산과 그림으로 설명합니다.\2',s,count=1,flags=re.S);p.write_text(s,encoding='utf-8')
if __name__=='__main__':build()
