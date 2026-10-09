"""Generate chapter 09 and numerical distribution illustrations."""
from pathlib import Path
from html import escape
import math,json,re
ROOT=Path(__file__).resolve().parent

def binomial(n,p):return [math.comb(n,k)*p**k*(1-p)**(n-k) for k in range(n+1)]
def normal(z):return math.exp(-z*z/2)/math.sqrt(2*math.pi)
def build():
 probs=binomial(3,.4)
 (ROOT/'distributions-example.json').write_text(json.dumps({'description':'가상 확률모형. 실제 거래 분포가 아님.','binomial':{'n':3,'p':.4,'probabilities':probs},'uniform':{'a':0,'b':.5},'normal':{'mu':0,'sigma':1}},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def t(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def line(x,y,xx,yy,extra=''):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="#64748b" {extra}/>'
 def fig(id,title,b,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=t(24,27,'3회 추출에서 주거가 몇 건인지 셉니다')+line(70,245,570,245)+line(70,45,70,245)
 for q in [0,.1,.2,.3,.4,.5]:b+=t(58,250-q*380,f'{q:.1f}','text-anchor="end"')
 for k,p in enumerate(probs):
  x=115+k*130;b+=f'<rect x="{x}" y="{245-p*380}" width="50" height="{p*380}" fill="#2563eb" data-k="{k}" data-p="{p}"/>'+t(x+25,235-p*380,f'{p:.3f}','text-anchor="middle"')+t(x+25,272,k,'text-anchor="middle"')
 b+=t(440,301,'X: 주거 건수')+t(80,49,'P(X=x)')
 f1=fig('pmf','이항분포의 확률질량',b,'그림 1. 주거 확률 0.4인 독립 추출을 3회 가정했습니다. 막대 높이는 각 건수의 확률이며 네 확률의 합은 1입니다.',325)
 b=t(24,27,'F(x)는 x 이하의 확률을 누적합니다')+line(70,250,570,250)+line(70,45,70,250)
 cumulative=0
 for k,p in enumerate(probs):
  previous=cumulative;cumulative+=p;x=130+k*110;y=250-cumulative*180
  b+=line(x,y,x+110,y,'stroke-width="3"')+f'<circle cx="{x}" cy="{y}" r="4" fill="#2563eb" data-k="{k}" data-cdf="{cumulative}"/>'+f'<circle cx="{x}" cy="{250-previous*180}" r="4" fill="white" stroke="#2563eb"/>'+t(x+40,y-10,f'{cumulative:.3f}')+t(x,276,k,'text-anchor="middle"')
 b+=line(70,250,130,250)+t(24,72,'1.0')+t(24,254,'0')+t(470,310,'x: 주거 건수')
 f2=fig('cdf','이산 누적분포함수',b,'그림 2. F(0)=0.216, F(1)=0.648, F(2)=0.936, F(3)=1. 채운 점은 해당 x에서의 함수값이며 빈 점은 포함하지 않는 끝입니다.',334)
 b=t(24,27,'연속형에서는 높이가 아니라 면적이 확률입니다')+line(70,235,590,235)+line(70,50,70,235)
 b+=f'<rect x="170" y="85" width="200" height="150" fill="#bfdbfe" data-area="0.4"/>'+line(70,85,570,85,'stroke-width="3"')+line(570,85,570,235)+t(48,90,'2','text-anchor="end"')+t(24,58,'밀도')
 for i in range(6):b+=t(70+i*100,263,f'{i/10:.1f}','text-anchor="middle"')
 b+=t(205,152,'면적 0.2×2=0.4')+t(370,299,'X: 대기시간(시간)')
 f3=fig('density','균등분포의 구간 확률',b,'그림 3. 대기시간이 0~0.5시간에 균등하다는 별도 가상 모형. 밀도는 2/시간이며 0.1~0.3시간 사이 확률은 0.4입니다. 밀도 2는 확률 200%가 아닙니다.',323)
 def point(z):return (320+z*65,245-normal(z)*430)
 pts=[point(-4+i*.025) for i in range(321)]
 b=t(24,27,'표준정규분포: 중심 0, 표준편차 1')+line(60,245,580,245)
 shade=[point(-1+i*.02) for i in range(101)]
 b+='<polygon points="255,245 '+' '.join(f'{x:.4f},{y:.4f}' for x,y in shade)+' 385,245" fill="#bfdbfe"/>'
 b+='<polyline points="'+' '.join(f'{x:.4f},{y:.4f}' for x,y in pts)+'" fill="none" stroke="#2563eb" stroke-width="2" data-normal="standard"/>'
 for z in range(-4,5):b+=t(320+z*65,270,z,'text-anchor="middle"')
 b+=t(280,166,'약 68.27%')+t(24,310,'−2~2: 약 95.45% / −3~3: 약 99.73%')+t(525,295,'z')
 f4=fig('normal-curve','표준정규분포와 중심 구간',b,'그림 4. 파란 면적은 −1≤Z≤1입니다. 곡선은 시각화를 위해 −4~4만 그렸으며 정규분포의 꼬리는 양쪽으로 무한히 이어집니다.',340)
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','핵심 이해','확률변수는 우연한 결과를 숫자로 바꾸는 규칙입니다','''<p>목록에서 거래 한 건을 뽑으면 결과는 거래의 ID입니다. 그 결과에 ‘주거이면 1, 아니면 0’이라는 숫자를 붙이거나, 그 거래의 면적을 대응시킬 수 있습니다. 이처럼 결과를 실수에 대응시키는 함수를 <strong>확률변수</strong>라고 합니다.</p><p>보통 대문자 X는 확률변수, 소문자 x는 가능한 값이나 관측값을 나타냅니다. ‘X≤2’는 확률변수의 값으로 표현한 사건입니다. <a href="/learn/stats/probability/">08장의 사건과 확률</a>이 이 장에서는 숫자와 분포로 연결됩니다.</p><p>확률분포는 가능한 값들에 확률이 어떻게 배분되는지를 나타냅니다. 이 장의 모든 분포는 학습을 위한 가상 모형이며 실제 부동산 자료에 적합시킨 결과가 아닙니다.</p>''')
 sec('discrete','이산 확률변수','셀 수 있는 값마다 확률을 붙입니다','''<p>거래 건수처럼 가능한 값을 하나씩 셀 수 있으면 이산 확률변수입니다. 값이 반드시 정수일 필요는 없지만, 여기서는 X를 ‘독립적으로 3회 추출했을 때의 주거 건수’로 정의합니다. 가능한 값은 0·1·2·3입니다. 08장 가상 목록에서 매번 복원한 뒤 동일한 방식으로 추출하면 각 시행의 주거 확률은 0.4입니다.</p>'''+f1+'''<p><strong>확률질량함수 p(x)=P(X=x)</strong>는 각 값의 확률입니다. 모든 확률은 음수가 아니고 합계가 1이어야 합니다. 이 예제는 0.216+0.432+0.288+0.064=1입니다. P(X≥2)=0.288+0.064=0.352처럼 해당하는 값의 확률을 더합니다.</p><p>막대 높이는 확률이며 막대 너비에는 의미를 두지 않습니다. 관측한 건수를 그린 빈도 막대그래프와 구별하세요. <a href="../distributions-example.json">가상 모형의 매개변수와 확률표</a>를 확인할 수 있습니다.</p>''')
 sec('cdf','누적분포함수','한 지점까지의 확률을 모읍니다','''<p><strong>누적분포함수 F(x)=P(X≤x)</strong>는 이산형과 연속형에 공통으로 사용할 수 있습니다. x가 커질수록 감소하지 않고, 왼쪽 끝에서는 0, 오른쪽 끝에서는 1에 가까워집니다. 이산형에서는 가능한 값마다 계단처럼 뛰어오릅니다.</p>'''+f2+'''<p>P(X&gt;1)=1−F(1)=0.352입니다. 그러나 P(X≥1)=1−P(X=0)=0.784이므로 부등호를 구별해야 합니다. 일반적으로 P(a&lt;X≤b)=F(b)−F(a)입니다. 이산형에서는 끝점에 확률이 있으므로 구간의 포함 여부가 결과를 바꿉니다.</p>''')
 sec('moments','기대값과 분산','확률을 가중치로 중심과 퍼짐을 구합니다','''<p>이산형에서 <strong>E[X]=Σx p(x)</strong>는 값에 확률을 곱해 더한 기대값입니다. 기대값이 존재할 때 이를 분포의 평균 μ라고 부릅니다. 예제에서는 0×0.216+1×0.432+2×0.288+3×0.064=<strong>1.2건</strong>입니다. 한 번의 결과로 1.2건이 나온다는 뜻이 아니라, 이 실험을 반복했을 때의 평균 수준입니다.</p><p>분산은 <strong>Var(X)=E[(X−μ)²]=Σ(x−μ)²p(x)</strong>이고 표준편차는 그 제곱근입니다. 예제의 E[X²]=2.16이므로 Var(X)=2.16−1.2²=0.72, 표준편차는 약 0.849건입니다. 최빈값은 확률이 가장 큰 1건으로, 기대값 1.2건과 다릅니다.</p><p>06장의 관측 자료 평균·분산은 실제 값들을 요약했습니다. 여기서는 모형이 정한 확률로 가중합니다. 표본분산의 n−1 보정을 이 확률분포 계산에 다시 붙이지 않습니다. 모든 분포가 유한한 기대값이나 분산을 갖는 것은 아니지만, 이 장의 예제들은 모두 갖습니다.</p><p>기대값이 존재하면 E[aX+b]=aE[X]+b이고, 분산이 유한하면 Var(aX+b)=a²Var(X)입니다. E[X+Y]=E[X]+E[Y]에는 독립이 필요하지 않습니다. 반면 분산을 단순히 더하려면 공분산이 0이어야 하며, 독립이고 분산이 유한한 경우에는 이 조건이 성립합니다.</p>''')
 sec('binomial','베르누이와 이항분포','성공 확률이 같은 독립 시행의 횟수를 셉니다','''<p>한 번의 시행에서 관심 사건이면 1, 아니면 0인 변수는 <strong>베르누이 분포</strong>로 표현합니다. P(X=1)=p, P(X=0)=1−p이며 평균은 p, 분산은 p(1−p)입니다. ‘성공’은 관심 사건의 이름일 뿐 좋은 결과라는 가치 판단이 아닙니다.</p><p>고정된 n회 시행이 서로 독립이고 성공 확률 p가 같을 때 성공 횟수는 <strong>이항분포 X~Bin(n,p)</strong>를 따릅니다. P(X=k)=C(n,k)pᵏ(1−p)ⁿ⁻ᵏ이며 C(n,k)는 n개 중 성공할 k개 위치를 고르는 조합 수입니다. 평균은 np, 분산은 np(1−p)입니다.</p><p>앞 그림의 n=3, p=0.4에서 정확히 2건이 주거일 확률은 C(3,2)×0.4²×0.6=3×0.16×0.6=0.288입니다. 주거·주거·비주거 순서 하나의 확률 0.096에 가능한 세 순서를 반영한 것입니다.</p><p>비복원 추출은 다음 시행의 확률을 바꾸므로 이항분포를 정확히 적용할 수 없습니다. 지역이나 시점별 성공 확률이 다르거나 거래가 서로 의존하는 경우에도 조건을 다시 검토합니다. 특정 기간의 거래 건수라는 이유만으로 이항분포가 되는 것은 아닙니다.</p>''')
 sec('continuous','연속 확률변수와 밀도','구간 아래의 면적이 확률입니다','''<p>시간이나 길이를 연속적인 값으로 모형화할 때는 <strong>확률밀도함수 f(x)</strong>를 사용할 수 있습니다. 밀도는 음수가 아니며 전체 곡선 아래 면적은 1입니다. 구간 확률 P(a≤X≤b)는 a부터 b까지의 면적, 즉 적분 ∫f(x)dx로 계산합니다.</p>'''+f3+'''<p>그림의 균등분포는 길이 0.5시간 전체에 밀도 2/시간을 둡니다. 전체 면적은 0.5×2=1이고, 0.1~0.3시간 구간은 0.2×2=0.4입니다. 밀도 높이는 1보다 커도 됩니다. 확률은 높이가 아니라 단위까지 상쇄되는 면적입니다.</p><p>밀도를 갖는 연속분포에서는 한 점의 확률 P(X=x)=0입니다. 폭이 0인 구간의 면적이 0이기 때문이며, 실제 관측값이 존재할 수 없다는 뜻이 아닙니다. 끝점 한 개의 포함 여부는 구간 확률을 바꾸지 않습니다. 반올림해 기록한 ‘0.2시간’은 실제로 일정 구간을 대표할 수 있으므로 기록 단위와 모형을 구분합니다.</p><p>밀도를 적분해 얻는 누적분포 F(x) 역시 0~1 사이입니다. 연속형 기대값은 E[X]=∫x f(x)dx로 확장됩니다. 여기서는 적분 기법보다 ‘면적’과 ‘확률 가중 평균’이라는 의미를 먼저 이해하면 충분합니다.</p>''')
 sec('normal','정규분포와 표준화','평균은 위치를, 표준편차는 너비를 정합니다','''<p><strong>정규분포 X~N(μ,σ²)</strong>는 평균 μ를 중심으로 대칭인 종 모양의 연속분포입니다. 여기서 두 번째 매개변수는 표준편차가 아닌 분산이며 σ&gt;0입니다. 밀도는 f(x)=exp(−(x−μ)²/(2σ²))/(σ√(2π))입니다. 평균을 바꾸면 중심이 이동하고 표준편차를 키우면 더 넓고 낮아져 전체 면적 1을 유지합니다.</p>'''+f4+'''<p>정규분포라면 <strong>Z=(X−μ)/σ</strong>는 평균 0·분산 1인 표준정규분포입니다. 가상 X~N(100,20²)에서 120은 z=1, 80은 z=−1이므로 P(80≤X≤120)≈68.27%입니다. μ±2σ는 약 95.45%, μ±3σ는 약 99.73%를 포함합니다.</p><p>이 비율은 정규분포의 성질입니다. 아무 자료나 평균과 표준편차로 표준화한다고 정규분포가 되지는 않습니다. 원자료의 치우침이나 여러 봉우리는 그대로 남습니다. 부동산 단가가 반드시 정규분포라는 뜻도 아니며, 양수 변수에 정규모형을 쓰면 음수에 확률을 부여하는 한계도 살펴야 합니다.</p><p>μ±1.96σ가 정규분포 관측값의 약 95%를 포함한다는 말과, 표본으로 추정한 평균의 95% 신뢰구간은 다릅니다. 다음 장에서 개별 관측의 분포와 표본평균의 분포를 구분합니다.</p>''')
 sec('model','관측 분포와 확률모형','히스토그램이 곧 이론 분포는 아닙니다','''<p>히스토그램은 관측 자료를 구간으로 묶은 그림이고, 확률분포는 결과가 발생하는 방식을 나타내는 모형입니다. 표본이 같아도 구간 폭에 따라 히스토그램 모양이 달라질 수 있습니다. 밀도와 비교하려면 막대 면적 합이 1이 되도록 정규화했는지도 확인해야 합니다.</p><p>분포를 고를 때는 변수의 범위, 정수 여부, 꼬리와 대칭성, 0의 빈도, 집단 혼합, 관측 간 의존성을 살펴봅니다. 분포 이름을 먼저 정해 자료를 맞추기보다 분석 질문과 자료의 생성 과정을 먼저 설명하세요.</p>''')
 sec('practice','확인 문제','확률의 합과 면적을 구별해 보세요','''<ol class="learn-exercises"><li>Bin(3,0.4)에서 2건 이상 주거일 확률은?<details><summary>답과 해설</summary><p>0.288+0.064=0.352입니다. 또는 1−F(1)로 계산합니다.</p></details></li><li>기대값 1.2건은 불가능한 관측이므로 계산 오류인가요?<details><summary>답과 해설</summary><p>아니요. 개별 결과는 0~3의 정수지만 확률 가중 평균은 소수일 수 있습니다.</p></details></li><li>밀도 높이가 2이면 확률 규칙 위반인가요?<details><summary>답과 해설</summary><p>아니요. 전체 면적이 1이어야 합니다. 0~0.5시간의 균등분포는 높이 2/시간으로 전체 확률 1이 됩니다.</p></details></li><li>모든 자료를 z점수로 바꾸면 약 68%가 −1~1에 들어오나요?<details><summary>답과 해설</summary><p>아니요. 표준화는 분포의 모양을 정규분포로 바꾸지 않습니다. 약 68%는 정규모형에서의 성질입니다.</p></details></li></ol>''')
 sec('macro','CH2 Macro에서 읽기','분포의 형태와 집계 조건을 함께 확인합니다','''<p>CH2 Macro에서 선택한 지역·기간·유형의 평균, 중앙값, 분위수와 분포 그림을 함께 읽으세요. 표준편차 한 개만으로 꼬리나 여러 집단의 혼합을 알 수는 없습니다. 이 장의 가상 모형은 서비스의 실제 가격분포나 예측 성능을 뜻하지 않습니다.</p><p>거래가 많이 모여도 개별 단가의 분포가 저절로 정규분포가 되는 것은 아닙니다. 다음 장의 중심극한정리는 일정 조건 아래 ‘표본평균의 분포’에 관한 결과라는 점을 구분해야 합니다.</p><p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 통계 열기 →</a></p>''')
 sec('recap','정리와 참고자료','값의 확률에서 표본의 불확실성으로 이어집니다','''<p>이산형은 값별 확률을 더하고, 연속형은 밀도 아래 면적을 계산합니다. 기대값·분산은 확률을 반영한 중심·퍼짐이며, 이항분포와 정규분포는 각각의 가정이 있는 모형입니다.</p><p>다음 <a href="/learn/stats/sampling-distributions/">10장 「표본분포와 중심극한정리」</a>에서는 반복 표집에서 평균이 어떻게 달라지는지 배웁니다.</p><ul><li><a href="https://openstax.org/books/introductory-statistics-2e/pages/4-2-mean-or-expected-value-and-standard-deviation">OpenStax §4.2</a> — 기대값과 분산.</li><li><a href="https://openstax.org/books/introductory-statistics-2e/pages/4-3-binomial-distribution">OpenStax §4.3</a> — 이항분포.</li><li><a href="https://openstax.org/books/introductory-statistics-2e/pages/6-1-the-standard-normal-distribution">OpenStax §6.1</a> — 표준정규분포.</li></ul><p class="learn-source-note">모든 예제와 그림은 설명용 가상 모형으로 직접 작성했습니다. 실제 거래 자료가 아닙니다. 참고자료 확인: 2026-10-07.</p>''')
 p=ROOT/'probability-distributions/index.html';p.parent.mkdir(exist_ok=True);s=p.read_text(encoding='utf-8') if p.exists() else (ROOT/'probability/index.html').read_text(encoding='utf-8')
 s=s.replace('https://ch2data.com/learn/stats/probability/','https://ch2data.com/learn/stats/probability-distributions/')
 s=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="확률변수와 확률분포">\n'+'\n'.join(parts)+'\n</article>',s,count=1,flags=re.S)
 s=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1이산·연속 확률변수, 기대값과 분산, 이항분포·정규분포를 계산과 그림으로 설명합니다.\2',s,count=1,flags=re.S);p.write_text(s,encoding='utf-8')
if __name__=='__main__':build()
