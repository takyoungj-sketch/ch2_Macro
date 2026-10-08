"""Generate chapter 11 from shared teaching observations."""
from pathlib import Path
from statistics import mean,stdev
from html import escape
import math,json,re
ROOT=Path(__file__).resolve().parent

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];v=[r['price'] for r in rows];s=stdev(v);se=s/math.sqrt(len(v))
 def t(x,y,text,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(text))}</text>'
 def bar(x,y,value,scale,extra=''):return f'<rect x="{x}" y="{y}" width="{value*scale}" height="25" fill="#2563eb" {extra}/>'
 def fig(id,title,b,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=t(24,28,'같은 30건이지만 요약하는 대상이 다릅니다')
 for i,(label,value) in enumerate([('표본표준편차 s',s),('추정 표준오차 SE',se)]):
  y=80+i*85;b+=t(24,y+18,label)+bar(200,y,value,4,f'data-value="{value}"')+t(210+value*4,y+18,f'{value:.2f}')
 b+=t(24,245,'s: 관측값의 퍼짐 / SE: 평균 추정의 표집 변동')+t(360,277,'단위: 만원/㎡')
 f1=fig('sd-se','표준편차와 표준오차',b,'그림 1. 공통 학습 자료 30건에서 n−1로 계산한 s=81.53, s/√30=14.89입니다. 막대는 0에서 시작하며 이 SE는 독립·동일분포 표본을 가정한 계산입니다.',305)
 b=t(24,28,'퍼짐 s를 고정한 표본수 비교입니다')
 for i,n in enumerate([10,30,120,480]):
  value=s/math.sqrt(n);y=70+i*65;b+=t(24,y+19,f'n={n}')+bar(145,y,value,14,f'data-n="{n}" data-se="{value}"')+t(155+value*14,y+19,f'{value:.2f}')
 b+=t(24,345,'가로축: 추정 표준오차(만원/㎡), 모두 0에서 시작')
 f2=fig('size','표본수와 평균의 정밀도',b,'그림 2. s=81.5286…을 고정한 가상 비교입니다. 실제로 10·120·480건을 추출한 결과가 아니며, 새 표본에서는 s도 달라질 수 있습니다.',370)
 b=t(24,28,'건수가 같아도 자료의 퍼짐이 다를 수 있습니다')
 grouptext=[]
 for i,label in enumerate(['주거','상업']):
  a=[r['price'] for r in rows if r['group']==label];sd=stdev(a);err=sd/math.sqrt(len(a));y=80+i*100
  b+=t(24,y,f'{label} n={len(a)} · s={sd:.2f}')+bar(160,y+20,err,13,f'data-group="{label}" data-se="{err}"')+t(170+err*13,y+40,f'{err:.2f}')
  grouptext.append(f'{label}는 s={sd:.2f}, SE={err:.2f}')
 b+=t(24,300,'가로축: 추정 표준오차(만원/㎡), 모두 0에서 시작')
 f3=fig('groups','유형별 표준오차 비교',b,'그림 3. 공통 자료의 주거·상업 각 15건을 별도로 계산했습니다. 단순 독립 표본 공식을 적용한 학습 예제이며 집단 간 차이의 유의성 검정은 아닙니다.',325)
 b=t(24,28,'목표 표준오차가 작아질수록 필요한 n이 빠르게 늘어납니다')
 for i,target in enumerate([20,10,5]):
  n=math.ceil((s/target)**2);y=75+i*75;b+=t(24,y+19,f'목표 SE {target}')+bar(175,y,n,1.3,f'data-target="{target}" data-required="{n}"')+t(185+n*1.3,y+19,f'{n}건')
 b+=t(24,325,'가로축: 필요 표본수 / 계획용 퍼짐 s≈81.53')
 f4=fig('planning','목표 정밀도와 표본수 계획',b,'그림 4. n≥(s/목표 SE)²을 올림했습니다. 목표 SE의 단위는 만원/㎡입니다. 이는 모집단 퍼짐을 학습 자료의 s로 가정한 계획 예제이며 신뢰수준을 지정한 오차한계 계산과 다릅니다.',352)
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','핵심 이해','많은 자료와 정확한 추정은 같은 말이 아닙니다','''<p>표본수 n은 계산에 실제로 사용한 유효 관측 수입니다. 자료가 많으면 평균 추정의 표집 변동을 줄일 수 있지만, 관측값 자체의 다양성이나 수집 편향이 저절로 줄지는 않습니다. 이 장에서는 <a href="/learn/stats/sampling-distributions/">10장의 표본분포</a>를 실제 계산으로 연결합니다.</p><p><strong>표준편차(SD)</strong>는 개별 관측의 퍼짐이고, <strong>표준오차(SE)</strong>는 통계량이 반복 표집에서 달라지는 정도입니다. 이 장의 SE는 특별히 ‘산술평균의 표준오차’를 뜻합니다. 중앙값·회귀계수 등 다른 통계량은 별도의 산식이 필요합니다.</p>'''+f1)
 sec('calculation','30건 계산','표본표준편차를 유효 표본수의 제곱근으로 나눕니다',f'''<p>독립이고 같은 분포에서 뽑은 표본이며 분산이 유한하면 평균의 이론적 SE는 σ/√n입니다. 모집단 σ를 모르면 표본표준편차 s로 바꾸어 <strong>추정 SE=s/√n</strong>을 사용합니다. 이것은 표집 변동의 추정치이며 실제 평균 오차 |x̄−μ|를 관측한 값이 아닙니다.</p><p><a href="/learn/stats/graphs/#data">공통 학습 예시 30건</a>의 평균은 {mean(v):.2f}, n−1로 나눈 표본표준편차는 {s:.2f}만원/㎡입니다. 따라서 추정 SE={s:.5f}…/√30=<strong>{se:.2f}만원/㎡</strong>입니다. 중간값을 반올림하지 않고 계산했습니다.</p><p>이 자료는 실제 거래 출처와 무작위 표집 설계가 확인되지 않은 교육용 예시입니다. 숫자를 계산할 수 있다는 것과 더 큰 실제 시장의 불확실성을 타당하게 추정한다는 것은 구별해야 합니다.</p><p>06장에서 n으로 나눈 기술 표준편차는 약 80.16이었습니다. 여기서는 모집단 분산을 추정하는 n−1 방식의 s를 사용합니다. 표준편차 계산의 n−1과 표준오차 계산의 √n을 혼동하지 않습니다. n=1이면 s를 계산할 수 없어 이 추정 SE도 정의되지 않습니다.</p>''')
 sec('size','표본수의 효과','네 배의 관측으로 표준오차를 절반으로 줄입니다','''<p>모집단의 퍼짐과 표집 방식이 같다면 SE는 √n에 반비례합니다. n을 두 배로 늘리면 약 0.707배가 되고, 네 배로 늘리면 절반이 됩니다. 정확도를 두 배 높이려면 표본도 두 배면 된다는 식으로 읽으면 안 됩니다.</p>'''+f2+'''<p>이 그림은 퍼짐을 고정해 표본수의 효과만 비교합니다. 실제 추가 거래에는 다른 유형이나 시점이 포함될 수 있고 표본표준편차도 변합니다. 따라서 새로 계산한 추정 SE가 매번 단조롭게 감소해야 하는 것은 아닙니다.</p><p>숫자가 30 이상이면 무조건 충분하다는 기준은 없습니다. 분포의 치우침, 극단값, 목표 정밀도와 의존성에 따라 필요한 정보량이 달라집니다. 큰 n만 보고 평균을 확정적인 시장 수준으로 읽지 않습니다.</p>''')
 sec('groups','같은 n의 비교','정밀도는 건수와 퍼짐에 함께 좌우됩니다',f'''<p>공통 자료를 주거·상업으로 나누면 각각 15건입니다. 하지만 {grouptext[0]}, {grouptext[1]}만원/㎡입니다. 건수만 같은 두 집단의 평균 정밀도가 같다고 볼 수 없습니다.</p>'''+f3+'''<p>그룹을 나누면 평균·표준편차·n을 모두 그 그룹에서 다시 계산합니다. 전체의 s를 그대로 붙이지 않습니다. 두 집단 평균의 차이를 검정하려면 차이 자체의 표준오차와 표집 관계를 검토해야 합니다. 이 그림만으로 두 평균의 차이가 통계적으로 유의하다고 판정할 수 없습니다.</p>''')
 sec('planning','표본수 계획','원하는 정밀도를 먼저 정하고 필요한 건수를 계산합니다','''<p>계획용 모집단 표준편차를 σ₀, 목표 표준오차를 e라고 놓으면 σ₀/√n≤e에서 <strong>n≥(σ₀/e)²</strong>을 얻습니다. 건수는 정수이므로 올림합니다. σ₀는 예비조사나 관련 자료로 설정하며 불확실하면 여러 퍼짐 시나리오를 비교하는 편이 낫습니다.</p>'''+f4+'''<p>목표 SE 10은 ‘오차가 반드시 ±10 이내’라는 보장이 아닙니다. 대략적인 95% 오차한계를 E로 계획하려면 정규근사와 독립 표집 조건 아래 n≈(1.96σ₀/E)²처럼 신뢰계수를 포함합니다. σ₀=80, E=10이면 약 245.86을 올려 246건입니다. σ를 추정하는 상황이나 작은 표본에는 t분포와 반복 계산 등 추가 검토가 필요합니다.</p><p>건수 계획에는 결측·탈락도 반영합니다. 분석에 필요한 유효 246건과 수집할 원래 행 수는 같지 않을 수 있습니다. 무응답이 특정 집단에 집중되는 편향은 단순히 더 모으는 것으로 해결되지 않습니다.</p>''')
 sec('interpretation','SE와 신뢰구간','SE 하나가 완성된 신뢰구간은 아닙니다','''<p>평균±SE를 95% 신뢰구간이라고 부르지 않습니다. 정규모집단의 독립 표본에서 σ를 모를 때 평균의 t 신뢰구간은 x̄±t×s/√n 형태이며 자유도·신뢰수준에 따라 t가 달라집니다. 비정규 자료에서는 표본수와 분포 형태에 따른 근사의 적절성을 추가로 확인합니다.</p><p>SE가 작다는 것은 해당 표집 모형 아래 평균의 추정이 정밀하다는 뜻입니다. 개인 거래가 평균 근처에 모인다는 뜻도, 데이터가 정확히 입력되었다는 뜻도, 미래 가격 예측오차가 작다는 뜻도 아닙니다. 신뢰구간의 해석은 12장에서 이어집니다.</p><p>모든 값이 같으면 표본 s와 추정 SE가 0이 될 수 있습니다. 작은 표본에서 우연히 같은 값만 관측했다고 해서 모집단의 불확실성까지 0이라고 결론 내리지는 않습니다.</p>''')
 sec('design','표집 설계와 데이터 품질','행 수보다 독립적인 정보가 얼마나 있는지 봅니다','''<p>같은 거래를 여러 번 복사하거나 같은 단지의 강하게 연관된 관측을 추가하는 것은 독립적인 새 표본을 얻는 것과 다릅니다. 군집·시계열 의존성이 있으면 군집 표준오차나 설계에 맞는 방법이 필요합니다. s/√n을 그대로 사용하면 불확실성을 과소평가할 수 있습니다.</p><p>가중평균도 일반적인 단순평균과 산식이 다릅니다. 유효표본수라는 개념을 쓰기도 하지만 가중치만으로 모든 의존성이나 편향을 보정할 수는 없습니다. 거래 1건, 건물 1개, 단지 1개 중 무엇이 관측 단위인지 먼저 확인합니다.</p><p>결측값을 제외했다면 해당 변수의 유효 n을 사용합니다. 면적은 30건이고 단가는 27건만 유효하다면 단가 평균의 분모에 30을 쓰면 안 됩니다. 0과 결측도 구별해야 합니다.</p><p>유한 모집단에서 비복원 추출한 비율이 크면 10장에서 설명한 유한모집단 보정이 필요합니다. 전수 자료라도 분석 대상 기간과 기록 범위를 벗어난 미래·누락 거래까지 완전히 안다는 뜻은 아닙니다.</p>''')
 sec('practice','확인 문제','정밀도와 자료의 퍼짐을 나누어 읽으세요','''<ol class="learn-exercises"><li>s=80, n=100일 때 평균의 추정 SE는?<details><summary>답과 해설</summary><p>80/√100=8입니다. 80은 관측값의 퍼짐이고 8은 독립 표본 모형에서 평균의 표집 변동 추정치입니다.</p></details></li><li>퍼짐이 같을 때 SE를 절반으로 줄이려면 n을 몇 배로 해야 하나요?<details><summary>답과 해설</summary><p>네 배입니다. SE가 표본수의 제곱근에 반비례하기 때문입니다.</p></details></li><li>자료 30건을 복사해 120행으로 만들면 정보량이 네 배가 되나요?<details><summary>답과 해설</summary><p>아니요. 독립적인 새 관측이 아닙니다. 단순히 √120으로 나누는 계산은 정밀도를 과장합니다.</p></details></li><li>목표 SE 10이면 평균의 실제 오차가 항상 ±10 이내인가요?<details><summary>답과 해설</summary><p>아니요. SE는 반복 표집에서의 퍼짐이며 개별 표본의 오차 한계를 보장하지 않습니다.</p></details></li></ol>''')
 sec('macro','CH2 Macro에서 읽기','건수·퍼짐·표집 범위를 함께 확인합니다','''<p>CH2 Macro에서 지역이나 유형의 평균을 읽을 때는 적용한 필터, 유효 거래 건수, 표준편차와 분위수, 기간·관측 단위를 함께 확인하세요. 단가가 크게 다른 집단을 합치면 n도 커지지만 퍼짐과 분석 질문도 달라집니다.</p><p>이 장의 SE는 교재용 계산입니다. 모든 서비스 화면이 이 산식을 제공하거나 독립 표본 가정을 만족한다고 전제하지 않습니다. 시장의 구조적 차이와 개별 가격 위험을 표준오차 한 개로 요약하지 않습니다.</p><p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 통계 열기 →</a></p>''')
 sec('recap','정리와 참고자료','작은 SE는 조건이 명확할 때 의미가 있습니다','''<p>표준편차는 관측값의 퍼짐, 표준오차는 통계량의 표집 변동입니다. 평균의 s/√n 계산에는 표집 가정이 필요하며 표본수만으로 대표성·정확성을 판단할 수 없습니다.</p><p>다음 <a href="/learn/stats/confidence-intervals/">12장 「점추정과 신뢰구간」</a>에서 추정치에 불확실성의 범위를 붙이는 방법을 배웁니다.</p><ul><li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm">NIST/SEMATECH: Confidence Limits for the Mean</a> — 평균의 표준오차와 신뢰구간의 관계.</li></ul><p class="learn-source-note">공통 30건은 출처 미확인 학습 자료입니다. 표본수 비교와 계획 예제는 별도 가정이며 실제 서비스의 정밀도나 필요 건수를 뜻하지 않습니다. 참고자료 확인: 2026-10-07.</p>''')
 p=ROOT/'sample-size/index.html';text=p.read_text(encoding='utf-8');text=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="표준오차와 표본수">\n'+'\n'.join(parts)+'\n</article>',text,count=1,flags=re.S)
 text=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1표준편차와 표준오차의 차이, 표본수와 정밀도, 표집 설계의 한계를 공통 예제와 그림으로 설명합니다.\2',text,count=1,flags=re.S);p.write_text(text,encoding='utf-8')
if __name__=='__main__':build()
