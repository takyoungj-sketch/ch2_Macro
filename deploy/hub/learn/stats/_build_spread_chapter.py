"""Rebuild chapter 06 with explicit descriptive and sample variance conventions."""
from pathlib import Path
from statistics import mean,pvariance,variance,pstdev,stdev
from html import escape
import json,re
ROOT=Path(__file__).resolve().parent

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];v=[r['price'] for r in rows];without=[r['price'] for r in rows if r['id']!=7];m=mean(v);ss=sum((x-m)**2 for x in v)
 def t(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def l(x,y,xx,yy,c='#cbd5e1',extra=''):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{c}" {extra}/>'
 def r(x,y,w,h,c='#93c5fd',extra=''):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}" {extra}/>'
 def fig(id,title,desc,b,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{desc}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=t(24,26,'평균이 같아도 관측값의 퍼짐은 다릅니다')
 for y,label,values in [(90,'A: 90 · 100 · 110',[90,100,110]),(180,'B: 50 · 100 · 150',[50,100,150])]:
  b+=t(24,y-25,label)+l(70,y,570,y)
  for x in values:b+=f'<circle cx="{70+x*3}" cy="{y}" r="6" fill="#2563eb"/>'
  b+=t(410,y-25,f'SD {pstdev(values):.2f}')
 b+=l(370,65,370,195,'#64748b','stroke-dasharray="4 3"')
 for x in [0,50,100,150]:b+=t(70+x*3,220,x,'text-anchor="middle"')
 b+=t(410,249,'단가(만원/㎡)')
 f1=fig('same-center','같은 평균과 다른 표준편차','가상 A와 B는 평균100이며 n으로 나눈 표준편차는8.16과40.82입니다.',b,'그림 1. 별도 가상 자료 두 묶음, 각 3건. SD는 각 묶음 자체를 요약해 n으로 나눈 표준편차입니다.',270)
 b=t(24,26,'80 · 100 · 120의 평균은 100입니다')
 for i,(x,d) in enumerate([(80,-20),(100,0),(120,20)]):
  y=75+i*70;b+=t(24,y+18,f'값 {x}')+l(200,y+12,400,y+12)
  b+=f'<circle cx="{300+d*4}" cy="{y+12}" r="5" fill="#2563eb"/>'+l(300,y-5,300,y+26,'#475569')+t(440,y+18,f'편차 {d:+d} → 제곱 {d*d}')
 b+=t(24,296,'편차 합: −20 + 0 + 20 = 0')+t(24,323,'제곱편차 합: 400 + 0 + 400 = 800')
 f2=fig('deviations','편차와 제곱편차','80,100,120에서 편차는 마이너스20,0,20이며 제곱합은800입니다.',b,'그림 2. 별도 가상 자료 3건. 가로 위치는 평균에서의 편차를 나타냅니다. 편차 단위는 만원/㎡, 제곱편차 단위는 (만원/㎡)²입니다.',348)
 b=t(24,26,'같은 공통 자료를 서로 다른 분모로 계산합니다')
 for y,label,sd,key in [(80,'30으로 나눔',pstdev(v),'n'),(155,'29로 나눔',stdev(v),'n-1')]:
  b+=t(24,y+21,label)+r(165,y,sd*4.7,28,extra=f'data-denominator="{key}" data-sd="{sd}"')+t(165+sd*4.7+9,y+21,f'{sd:.1f}')
 b+=l(165,218,588,218)
 for x in [0,20,40,60,80]:b+=t(165+x*4.7,243,x,'text-anchor="middle"')
 b+=t(390,273,'표준편차(만원/㎡)')
 f3=fig('denominators','n과 n-1의 표준편차 비교','n으로 나누면80.2, n-1로 나누면81.5만원/㎡입니다.',b,'그림 3. 같은 30건과 같은 평균으로 계산했습니다. 분모의 차이이며 자료를 한 건 제거한 비교가 아닙니다.',295)
 b=t(24,26,'7번 포함·제외에 따른 기술통계 변화')
 for y,label,values in [(80,'전체 30건',v),(155,'7번 제외 29건',without)]:
  sd=pstdev(values);b+=t(24,y+21,label)+r(190,y,sd*4.4,28,extra=f'data-count="{len(values)}" data-sd="{sd}"')+t(190+sd*4.4+9,y+21,f'{sd:.1f}')
 b+=l(190,220,586,220)
 for x in [0,20,40,60,80]:b+=t(190+x*4.4,244,x,'text-anchor="middle"')
 b+=t(392,274,'표준편차(만원/㎡)')
 f4=fig('extreme-effect','큰 관측의 영향','각 자료의 건수로 나눈 표준편차가 전체80.2에서 7번 제외51.7로 달라집니다.',b,'그림 4. 공통 예제의 민감도 비교. 각 자료에서 평균을 다시 구하고 각각 30과 29로 나눕니다. 관측 삭제를 권하는 그림이 아닙니다.',297)
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}">\n<p class="learn-chapter__label">{label}</p>\n<h2>{title}</h2>\n{body}\n</section>')
 sec('quick-start','핵심 이해','중심만으로는 자료의 모습을 알 수 없습니다','''<p>평균이 100인 두 집단이 있어도 하나는 모든 값이 100 근처에, 다른 하나는 넓은 범위에 놓일 수 있습니다. <strong>분산과 표준편차</strong>는 각 관측이 평균에서 얼마나 떨어져 있는지를 이용해 이런 퍼짐을 요약합니다.</p><p>이 장에서는 계산 과정, 제곱과 단위, n과 n−1의 구분, 극단값과 단위 변환의 영향을 익힙니다. 선수 개념은 <a href="/learn/stats/mean-and-median/#mean">산술평균</a>과 <a href="/learn/stats/quantiles/#iqr">IQR</a>입니다.</p>'''+f1)
 sec('deviation','편차와 제곱','부호가 상쇄되지 않도록 크기를 모읍니다','''<p><strong>편차</strong>는 관측값에서 평균을 뺀 값입니다. 평균보다 작으면 음수, 크면 양수입니다. 평균을 기준으로 한 편차를 모두 더하면 0이 되므로 그 합만으로는 퍼짐을 나타낼 수 없습니다.</p>'''+f2+'''<p>제곱하면 부호가 사라지고 멀리 떨어진 값의 영향이 커집니다. 편차가 10에서 20으로 두 배가 되면 제곱은 100에서 400으로 네 배가 됩니다. 제곱만이 유일한 방법은 아닙니다. 절댓값을 모으는 방법도 있지만 그것은 다른 퍼짐 지표가 됩니다.</p><p>그림 2의 자료를 그 자체로 요약하면 분산은 800÷3≈266.67이고, 그 제곱근인 표준편차는 약 16.33입니다. 절대편차의 평균은 (20+0+20)÷3≈13.33으로 다릅니다. 표준편차를 ‘평균에서 떨어진 절대거리의 평균’과 같은 값으로 읽지 않습니다.</p>''')
 sec('formulas','공식과 단위','분산은 제곱 단위, 표준편차는 원래 단위입니다','''<p>관측한 n개 값을 하나의 자료 집합으로 기술할 때는 평균 x̄를 구하고, <strong>분산 = Σ(xᵢ−x̄)² ÷ n</strong>으로 계산할 수 있습니다. Σ는 모든 관측에 대해 더한다는 뜻입니다. 표준편차는 이 분산의 제곱근입니다.</p><p>모집단 전체 N개를 알고 있다면 같은 방식으로 모집단 평균 μ와 모집단 분산 σ²=Σ(xᵢ−μ)²÷N을 구합니다. 일부 표본으로 더 큰 모집단의 분산을 추정할 때는 아래에서 설명하는 n−1 보정을 구별해서 사용합니다.</p><p>단가의 단위가 만원/㎡라면 편차도 만원/㎡, 분산은 (만원/㎡)², 표준편차는 다시 만원/㎡입니다. 분산 266.67을 ‘단가가 평균에서 266.67만원 떨어져 있다’고 읽으면 단위가 맞지 않습니다.</p><p>분산과 표준편차는 0 이상입니다. 모든 값이 같을 때 0이며, 표준편차가 크다는 말은 평균에서의 제곱편차가 큰 편이라는 뜻입니다. 반드시 최솟값·최댓값의 차이도 더 크다는 뜻은 아닙니다.</p>''')
 sec('example','30건 계산 예제','원자료의 평균을 기준으로 제곱편차를 더합니다',f'''<p>공통 학습 예시 30건의 평균은 4,390÷30=146.333…입니다. 계산 중에는 이 값을 반올림하지 않습니다. <a href="/learn/stats/graphs/#data">원자료 표</a>와 <a href="../example-data.json">JSON 자료</a>를 확인할 수 있습니다. 실제 거래 출처가 확인되지 않은 학습 예시이며 실제 시장의 변동성을 뜻하지 않습니다.</p><p>제곱편차 합은 약 {ss:,.2f}입니다. 이를 30으로 나누면 분산은 {pvariance(v):,.2f}, 제곱근을 구하면 표준편차는 <strong>{pstdev(v):.2f}만원/㎡</strong>입니다. 표시 자릿수에 따라 80.2로 적을 수 있습니다.</p><div class="learn-data learn-data--full"><table><caption>공통 자료의 계산 요약</caption><thead><tr><th scope="col">단계</th><th scope="col">값</th><th scope="col">단위</th></tr></thead><tbody><tr><th scope="row">관측 수</th><td>30</td><td>건</td></tr><tr><th scope="row">평균</th><td>146.333…</td><td>만원/㎡</td></tr><tr><th scope="row">제곱편차 합</th><td>{ss:,.2f}</td><td>(만원/㎡)²</td></tr><tr><th scope="row">n으로 나눈 분산</th><td>{pvariance(v):,.2f}</td><td>(만원/㎡)²</td></tr><tr><th scope="row">표준편차</th><td>{pstdev(v):.2f}</td><td>만원/㎡</td></tr></tbody></table></div>''')
 sec('sample-variance','n과 n−1','기술하는 목적과 추정하는 목적을 구별합니다','''<p>독립적이고 같은 분포에서 얻은 표본으로 유한한 모집단 분산을 추정할 때는 <strong>표본분산 s²=Σ(xᵢ−x̄)²÷(n−1)</strong>을 사용합니다. 모집단 평균 대신 같은 표본에서 구한 평균을 쓰면 제곱편차가 평균적으로 작아지는 점을 보정합니다.</p>'''+f3+f'''<p>공통 예제에서 29로 나눈 분산은 {variance(v):,.2f}, 표본표준편차 s는 <strong>{stdev(v):.2f}만원/㎡</strong>입니다. 30건 중 한 건을 버리는 것이 아닙니다. 같은 30개 편차제곱을 더하고 분모만 29로 바꿉니다.</p><p>편차들의 합이 0으로 정해져 있으므로 n−1개 편차가 정해지면 마지막 편차도 정해집니다. 이를 자유도 n−1과 연결해 이해할 수 있습니다. n−1 보정이 분산을 불편추정량으로 만드는 것은 위 표집 가정 아래에서의 성질이며, 수집 편향이나 관측 간 의존성을 없애 주지는 않습니다.</p><p>분산이 불편추정량이라고 해서 그 제곱근인 표준편차도 정확히 불편추정량인 것은 아닙니다. n=1이면 n−1 방식은 계산할 수 없습니다. 표본이 작을수록 두 분모의 차이가 커지므로 사용한 규칙을 표시해야 합니다.</p>''')
 sec('extremes','극단값과 다른 퍼짐 지표','큰 편차는 제곱합에 크게 기여합니다','''<p>공통 자료의 7번 단가는 480입니다. 평균과의 차이가 크므로 제곱편차 합에도 큰 영향을 줍니다. 포함한 결과와 제외한 결과를 함께 계산하면 그 영향을 확인할 수 있습니다.</p>'''+f4+'''<p>7번을 제외하면 평균부터 다시 계산해야 합니다. 나머지 29건의 평균은 약 134.83이며, 29로 나눈 표준편차는 약 51.72입니다. 같은 퍼짐을 계산하면서 분모만 바꾼 그림 3과 달리, 여기서는 관측 집합과 평균이 모두 달라졌습니다.</p><p>어느 결과가 더 작다는 이유로 관측을 삭제하지 않습니다. 기록 오류인지, 조건이 다른 거래인지, 유효한 큰 값인지 확인해야 합니다. IQR은 가운데 부분을 중심으로 읽고 표준편차는 모든 제곱편차를 반영하므로 두 지표가 다른 인상을 줄 수 있습니다. <a href="/learn/stats/iqr-outliers/">07장</a>에서 판단 기준을 이어서 다룹니다.</p>''')
 sec('scale','단위 변환과 상대적 퍼짐','상수를 더할 때와 곱할 때의 효과는 다릅니다','''<p>모든 관측에 같은 상수 c를 더하면 평균도 c만큼 이동하므로 평균에서의 편차는 그대로입니다. 따라서 분산과 표준편차는 바뀌지 않습니다. 모든 값에 a를 곱하면 분산은 a²배, 표준편차는 |a|배가 됩니다.</p><p>가상 자료 80·100·120에 100을 더해 180·200·220으로 바꾸면 표준편차는 둘 다 약 16.33입니다. 원래 값을 두 배로 바꾼 160·200·240에서는 표준편차가 약 32.66, 분산은 약 1,066.67로 네 배가 됩니다. 이 예제는 각 자료의 건수로 나눈 계산입니다.</p><p>서로 다른 단위로 표시한 표준편차를 숫자 크기만으로 비교하지 않습니다. 같은 단위에서도 평균 수준이 크게 다르면 상대적인 퍼짐을 따로 보고 싶을 수 있습니다. 변동계수(CV)는 표준편차÷평균으로 계산하지만, 의미 있는 0을 갖는 비율척도에서 평균이 양수이고 0에서 충분히 떨어져 있을 때 신중하게 사용합니다. 평균이 0 근처면 값이 불안정해집니다.</p>''')
 sec('interpretation','해석의 한계','표준편차는 신뢰구간도 예측오차도 아닙니다','''<p>표준편차는 관측값들의 퍼짐입니다. 평균 추정값이 표본마다 얼마나 달라질지를 나타내는 <strong>표준오차</strong>와는 다릅니다. 표본수가 늘어도 자료 자체의 표준편차가 반드시 작아지는 것은 아닙니다. 이 구분은 <a href="/learn/stats/sample-size/">11장</a>에서 자세히 설명합니다.</p><p>평균±표준편차 안에 항상 약 68%가 있다는 규칙도 아닙니다. 약 68%라는 수치는 정규분포에서의 성질이며, 치우치거나 여러 집단이 섞인 분포에 그대로 적용할 수 없습니다. 평균±표준편차를 95% 신뢰구간으로 읽어서도 안 됩니다.</p><p>모형의 예측값이 없다면 관측 단가의 표준편차를 그 모형의 예측오차라고 부를 수 없습니다. 거래 유형·면적·시점이 섞여 생기는 퍼짐과 예측값에서 벗어난 오차는 계산 대상이 다릅니다.</p>''')
 sec('practice','확인 문제','분모·단위·계산 대상을 확인하세요','''<ol class="learn-exercises"><li>80·100·120의 편차 합이 0이면 퍼짐도 0인가요?<details><summary>답과 해설</summary><p>아니요. 음수와 양수가 상쇄된 것입니다. 제곱편차 합은 800이고 n으로 나눈 표준편차는 약 16.33입니다.</p></details></li><li>같은 30건의 제곱편차 합을 29로 나누면 한 건을 제거한 것인가요?<details><summary>답과 해설</summary><p>아니요. 관측은 모두 유지하고 분모를 보정한 것입니다. 한 건을 제거한다면 평균과 제곱편차 합도 다시 계산해야 합니다.</p></details></li><li>모든 단가를 두 배로 바꾸면 분산과 표준편차는 각각 어떻게 되나요?<details><summary>답과 해설</summary><p>편차가 두 배가 되므로 분산은 네 배, 표준편차는 두 배가 됩니다. 같은 상수를 더하기만 하면 두 퍼짐 지표는 변하지 않습니다.</p></details></li></ol>''')
 sec('macro','CH2 Macro에서 읽기','선택한 거래의 퍼짐으로 읽습니다','''<p>CH2 Macro의 기본통계에서 퍼짐을 읽을 때는 지역·기간·유형과 건수, 단위, 제공된 산식 설명을 함께 확인하세요. 이 장의 n 또는 n−1 계산 관례가 모든 화면의 구현과 같다고 가정하지 않습니다.</p><p>서로 다른 거래 유형이나 기간을 묶으면 퍼짐의 원인이 달라질 수 있습니다. 표준편차가 크다는 사실만으로 데이터 오류나 특정 물건의 가격 위험을 단정하지 않습니다. 평균·중위·분위수와 분포를 함께 읽는 것이 도움이 됩니다.</p><p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 기본통계 열기 →</a></p>''')
 sec('recap','정리와 참고자료','퍼짐의 숫자에는 계산 목적과 단위를 붙입니다','''<p>분산은 평균에서의 제곱편차를 모아 만든 지표이고, 표준편차는 원래 단위로 되돌린 값입니다. n과 n−1의 선택, 큰 관측값, 단위 변환이 결과에 미치는 영향을 구별해 읽습니다.</p><p>다음 <a href="/learn/stats/iqr-outliers/">07장 「이상치와 IQR」</a>에서는 떨어진 관측을 발견하고 확인하는 절차를 살펴봅니다.</p><ul><li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/eda356.htm">NIST/SEMATECH: Measures of Scale</a> — 분산·표준편차와 다른 퍼짐 지표.</li><li><a href="https://openstax.org/books/introductory-statistics-2e/pages/2-7-measures-of-the-spread-of-the-data">OpenStax, Introductory Statistics 2e §2.7</a> — 퍼짐 지표의 계산과 해석.</li></ul><p class="learn-source-note">본문과 그림은 공통 자료와 별도 가상 예제로 작성했습니다. 반올림은 표시 단계에서만 적용합니다. 참고자료 확인: 2026-10-07.</p>''')
 p=ROOT/'spread/index.html';s=p.read_text(encoding='utf-8');s=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="분산과 표준편차">\n'+'\n'.join(parts)+'\n</article>',s,count=1,flags=re.S)
 s=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1분산과 표준편차의 계산·단위, n과 n−1, 극단값과 단위 변환의 영향을 그림과 예제로 설명합니다.\2',s,count=1,flags=re.S)
 p.write_text(s,encoding='utf-8');print(ss,pvariance(v),pstdev(v),variance(v),stdev(v),pstdev(without))
if __name__=='__main__':build()
