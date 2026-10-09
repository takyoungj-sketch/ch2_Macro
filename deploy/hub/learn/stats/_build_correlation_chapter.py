"""Generate chapter 16: association, nonlinear patterns and causal limits."""
from pathlib import Path
from statistics import mean
from html import escape
import json,math,re
from scipy.stats import pearsonr,spearmanr
ROOT=Path(__file__).resolve().parent

def corr(x,y):
 xm,ym=mean(x),mean(y);return sum((a-xm)*(b-ym) for a,b in zip(x,y))/math.sqrt(sum((a-xm)**2 for a in x)*sum((b-ym)**2 for b in y))

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];x=[r['area'] for r in rows];y=[r['price'] for r in rows];r=corr(x,y);rho=float(spearmanr(x,y).statistic);without=[v for v in rows if v['id']!=7];rwithout=corr([v['area'] for v in without],[v['price'] for v in without]);floor=corr([v['floor'] for v in rows],y)
 curved=[(i,i*i) for i in range(-3,4)];mixA=[(1,8),(2,9),(3,10)];mixB=[(7,2),(8,3),(9,4)];mix=mixA+mixB;mixr=corr([v[0] for v in mix],[v[1] for v in mix])
 result={'description':'공통 학습 자료 및 별도 가상 관계 예제. 인과효과가 아님.','pearson_area_price':r,'spearman_area_price':rho,'pearson_floor_price':floor,'without_id7':rwithout,'curved':curved,'mixture':{'A':mixA,'B':mixB,'overall_r':mixr}}
 (ROOT/'correlation-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def t(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def line(x,y,xx,yy,c='#64748b',extra=''):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{c}" {extra}/>'
 def fig(id,title,b,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=t(24,28,f'면적과 단가 · Pearson r={r:.3f}')+line(70,320,580,320)+line(70,55,70,320)
 for row in rows:
  cx=70+row['area']*1.5;cy=320-row['price']*.5;b+=f'<circle cx="{cx}" cy="{cy}" r="4" fill="{"#2563eb" if row["group"]=="주거" else "#d97706"}" data-id="{row["id"]}"/>'
  if row['id']==7:b+=t(cx+10,cy,'7번 480')
 for v in [0,100,200,300]:b+=t(70+v*1.5,345,v,'text-anchor="middle"')
 for v in [0,100,200,300,400,500]:b+=t(58,325-v*.5,v,'text-anchor="end"')
 b+=t(400,374,'면적(㎡)')+t(24,52,'단가(만원/㎡)')+t(24,405,'파랑: 주거 / 주황: 상업 · 각 점은 거래 한 건')
 f1=fig('scatter','공통 자료의 면적과 단가',b,'그림 1. 공통 학습 자료 30건의 산점도입니다. 면적이 큰 쪽에서 단가가 낮은 경향이 있지만, 유형과 조건을 통제한 효과가 아닙니다.',431)
 b=t(24,28,'r=0이어도 뚜렷한 곡선 관계가 있을 수 있습니다')+line(80,285,560,285)+line(320,60,320,285)
 for xx,yy in curved:b+=f'<circle cx="{320+xx*65}" cy="{285-yy*22}" r="6" fill="#2563eb" data-x="{xx}" data-y="{yy}"/>'
 for v in range(-3,4):b+=t(320+v*65,311,v,'text-anchor="middle"')
 b+=t(24,345,'가상 자료 Y=X² / X=−3,−2,−1,0,1,2,3')+t(24,375,'Pearson r=0 · 선형 상관이 없다는 뜻')
 f2=fig('nonlinear','상관 0과 비선형 관계',b,'그림 2. 별도 가상 예제입니다. Y는 X로 완전히 정해지지만 대칭적인 U자 관계여서 Pearson 상관은 0입니다. 축은 단위 없는 가상 변수입니다.',403)
 b=t(24,28,f'집단 안에서는 r=1, 전체를 합치면 r={mixr:.3f}')+line(70,320,570,320)+line(70,60,70,320)
 for label,pts,color in [('A',mixA,'#2563eb'),('B',mixB,'#d97706')]:
  for xx,yy in pts:b+=f'<circle cx="{70+xx*48}" cy="{320-yy*23}" r="6" fill="{color}" data-group="{label}" data-x="{xx}" data-y="{yy}"/>'
 for v in [0,2,4,6,8,10]:b+=t(70+v*48,346,v,'text-anchor="middle"')+t(57,325-v*23,v,'text-anchor="end"')
 b+=t(24,385,'파랑: A / 주황: B · 축은 단위 없는 가상 X와 Y')
 f3=fig('mixture','집단 혼합에 따른 상관 방향 변화',b,'그림 3. A=(1,8)·(2,9)·(3,10), B=(7,2)·(8,3)·(9,4)인 별도 가상 예제입니다. 전체와 집단 내부의 관계가 다를 수 있음을 보여 줍니다.',412)
 b='<defs><marker id="causal-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b"/></marker></defs>'+t(24,28,'같은 연관성에도 서로 다른 설명이 가능합니다')
 for i,(label,nodes) in enumerate([('직접 영향 가설','X → Y'),('역방향 가설','X ← Y'),('공통 원인 가설','X ← Z → Y')]):
  yy=80+i*75;b+=t(24,yy,label)+t(275,yy,nodes)
 b+=t(24,307,'예: 입지 Z가 접근성 X와 단가 Y 모두에 영향을 줄 수 있음')+t(24,340,'화살표는 검토할 가설이며 관측 상관으로 입증한 경로가 아닙니다')
 f4=fig('causes','상관을 설명하는 인과 가설',b,'그림 4. 방향과 공통 원인을 구분하는 개념도입니다. 실제 데이터로 추정한 인과모형이 아닙니다.',367)
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','핵심 이해','함께 달라지는 모습과 원인·결과를 구분합니다','''<p>면적이 큰 거래일수록 단가가 낮게 보인다면 두 변수 사이에 연관성이 있습니다. 하지만 면적을 바꾸면 단가가 그만큼 내려간다는 결론은 별개의 주장입니다. 상관은 관측된 동행 패턴을 요약하고, 인과는 개입했을 때 결과가 어떻게 달라지는지를 묻습니다.</p><p>이 장에서는 산점도, Pearson·Spearman 상관, 비선형 관계와 집단 혼합을 살펴보고 인과 해석에 필요한 조건을 구분합니다. <a href="/learn/stats/graphs/">03장의 산점도</a>와 <a href="/learn/stats/spread/">06장의 편차</a>가 기초가 됩니다.</p>''')
 sec('scatter','산점도부터 읽기','상관계수 하나보다 점들의 모양을 먼저 봅니다','''<p>같은 관측에서 얻은 두 변수의 짝 (xᵢ,yᵢ)을 점 하나로 그립니다. 방향, 직선·곡선 모양, 퍼짐의 변화, 군집과 극단값을 함께 확인합니다. 행의 짝을 잘못 맞추면 상관 계산 자체가 다른 질문이 됩니다.</p>'''+f1+f'''<p>공통 30건의 면적·단가 Pearson 상관은 {r:.3f}, 층·단가는 {floor:.3f}입니다. 실제 거래 출처가 확인되지 않은 학습 자료이며 실제 지역 시장의 관계를 뜻하지 않습니다. <a href="/learn/stats/graphs/#data">원자료</a>와 <a href="../correlation-example.json">계산 결과</a>를 확인할 수 있습니다.</p><p>단가는 금액을 면적으로 나눈 값이므로 면적과 단가의 관계에는 공통 분모에서 생기는 구조도 영향을 줄 수 있습니다. 총액·유형·시점의 관계까지 살펴야 하며 단순 음의 상관만으로 ‘면적 할인율’을 추정하지 않습니다.</p>''')
 sec('pearson','Pearson 상관','함께 움직이는 편차를 표준화합니다','''<p>표본 Pearson 상관은 <strong>r=Σ(xᵢ−x̄)(yᵢ−ȳ)/√[Σ(xᵢ−x̄)²Σ(yᵢ−ȳ)²]</strong>입니다. 각 변수의 평균보다 함께 높거나 함께 낮은 관측은 분자에 양수로, 서로 반대쪽인 관측은 음수로 기여합니다. 표본 공분산을 두 표본표준편차의 곱으로 나눈 식과 같습니다.</p><p>두 변수 모두 퍼짐이 있을 때 −1≤r≤1입니다. 부호는 선형 관계의 방향, |r|는 직선적 결합의 정도를 요약합니다. r=±1이면 점들이 완전한 직선에 놓입니다. 한 변수가 모두 같은 값이면 분모가 0이므로 r은 정의되지 않습니다.</p><p>r에는 단위가 없습니다. 한 변수에 상수를 더하거나 양의 상수를 곱해 단위를 바꿔도 변하지 않고, 음의 상수를 곱하면 부호가 뒤집힙니다. r(X,Y)=r(Y,X)이므로 원인 방향도 담고 있지 않습니다.</p><p>r=0.6이 ‘X가 1 증가하면 Y가 0.6 증가한다’는 뜻은 아닙니다. 그런 기울기는 단위와 퍼짐에 좌우됩니다. 강함·약함의 고정 경계도 모든 분야에 공통인 판단 기준이 아니므로 산점도와 분석 목적을 함께 제시합니다.</p>''')
 sec('nonlinear','상관 0의 한계','선형 관계가 약해도 다른 관계는 남을 수 있습니다','''<p>Pearson 상관은 선형 관계를 요약합니다. 곡선 관계를 단일 직선으로 요약하면 상쇄되어 0 근처가 될 수 있습니다.</p>'''+f2+'''<p>적절한 유한 모멘트 조건에서 독립이면 공분산과 상관이 0이지만, 상관 0이 일반적으로 독립을 뜻하지는 않습니다. 두 변수가 공동 정규분포를 따르는 등 추가 조건이 있을 때 성립하는 특별한 결과와 구분합니다.</p><p>정규성을 가정하지 않아도 표본 상관은 계산할 수 있습니다. 다만 모집단 상관에 대한 p값·신뢰구간을 구할 때는 표집과 분포 가정이 별도로 필요합니다.</p>''')
 sec('spearman','Spearman 순위상관','값 대신 순위로 단조 관계를 요약합니다',f'''<p>Spearman의 ρ는 각 변수의 값을 순위로 바꾸고 그 순위 사이의 Pearson 상관을 계산합니다. 동점에는 보통 평균 순위를 부여합니다. 숫자 간 간격보다 대체로 함께 증가·감소하는 단조 관계에 관심 있을 때 도움이 됩니다.</p><p>공통 자료의 면적·단가 순위상관은 {rho:.3f}입니다. 원래 값의 Pearson {r:.3f}와 계산 대상이 다릅니다. 순위상관이 어느 상황에서나 더 옳거나 이상치 문제를 완전히 해결하는 것은 아닙니다.</p><p>단조적인 곡선은 순위상관이 높을 수 있지만 U자처럼 중간에 방향이 바뀌는 관계는 순위상관 하나로도 잘 표현하지 못합니다. 동점이 많은 서열 자료나 작은 표본에서는 계산 관례와 추론 방법을 확인합니다.</p>''')
 sec('sensitivity','이상치와 범위 제한','관측 구성에 따라 상관이 달라집니다',f'''<p>공통 자료의 7번을 제외하면 면적·단가 Pearson 상관은 {rwithout:.3f}입니다. 포함한 {r:.3f}와 함께 제시하면 민감도를 확인할 수 있습니다. 이 비교는 삭제를 권하는 것이 아니며 원자료 오류나 별도 거래 조건을 먼저 확인해야 합니다.</p><p>선형 관계에서 멀리 떨어진 관측 하나가 상관을 약화시킬 수도, 강하게 만들 수도 있습니다. 또 면적 범위를 좁혀 선택하면 같은 생성 과정에서도 상관이 작아질 수 있습니다. 표본수·범위·필터·결측 기준이 다른 상관계수를 숫자만으로 비교하지 않습니다.</p><p>두 변수 중 하나라도 결측인 행을 제외했다면 실제 쌍의 수를 보고합니다. 여러 변수의 상관행렬에서 쌍마다 사용된 표본이 다를 수 있고, 특정 집단의 누락은 결과를 왜곡할 수 있습니다.</p>''')
 sec('mixture','집단 혼합','전체의 방향이 집단 안의 방향과 다를 수 있습니다','''<p>서로 평균 수준이 다른 집단을 합치면 집단 간 차이가 전체 상관을 지배할 수 있습니다. 다음 예제에서는 두 집단 내부는 모두 양의 직선 관계인데 전체는 음의 상관입니다.</p>'''+f3+'''<p>이런 방향 반전은 심프슨 역설과 관련된 집계 문제를 보여 줍니다. 실제 분석에서는 유형·시점·지역을 구별한 산점도와 층별 결과를 함께 확인합니다. 그렇다고 어떤 변수를 무조건 통제하면 옳다는 뜻은 아닙니다. 통제할 변수는 인과 구조와 분석 질문에 따라 선택해야 합니다.</p>''')
 sec('causality','인과관계의 조건','상관의 크기가 원인 방향을 정하지 않습니다','''<p>X와 Y가 함께 움직일 때 X가 Y에 영향을 줄 수도, Y가 X에 영향을 줄 수도, 공통 원인 Z가 둘 모두에 영향을 줄 수도 있습니다. 어떤 표본에 포함되는지에 따른 선택 편향도 연관성을 만들 수 있습니다.</p>'''+f4+'''<p>인과효과는 같은 조건에서 X에 개입했을 때 결과가 어떻게 달라지는지에 관한 질문입니다. 무작위 배정은 비교 집단을 만드는 강력한 방법이지만, 무작위 표집과는 역할이 다릅니다. 02장에서 구분한 ‘누구를 뽑는가’와 ‘어느 처치를 배정하는가’를 떠올려 보세요.</p><p>관찰 자료에서는 교란 통제·시간 순서·선택 과정과 식별 가정을 검토해야 합니다. 모든 변수를 회귀에 넣는다고 인과효과가 자동으로 나오지는 않습니다. 매개변수를 통제하면 총효과와 다른 질문이 되고, 공통 결과에 조건을 걸면 없던 연관성이 생길 수도 있습니다.</p><p>유의한 상관이나 선행 시점의 예측력만으로 인과가 입증되지는 않습니다. 반대로 인과효과가 있어도 혼합·상쇄·측정 오류 때문에 단순 상관이 약하게 나타날 수 있습니다.</p>''')
 sec('inference','불확실성과 보고','상관의 크기와 p값을 따로 보고합니다','''<p>독립적으로 표집한 이변량 정규모형에서 H₀:모상관=0을 검정할 때 t=r√((n−2)/(1−r²)), 자유도 n−2를 사용할 수 있습니다. 이 공식은 n&gt;2, |r|&lt;1 등 계산 조건과 모형 가정이 필요합니다. 군집·시계열 관측을 독립으로 취급하면 불확실성을 과소평가할 수 있습니다.</p><p>큰 표본에서는 작은 상관도 유의할 수 있습니다. r 또는 ρ, 유효 쌍의 수, 산점도, 변수 단위·변환·범위와 적절한 신뢰구간을 함께 제시하세요. 많은 변수 쌍을 탐색하면 다중비교와 사후 선택도 고려합니다.</p><p>모집단·범위가 다른 두 상관을 비교할 때 p값의 크기만 비교하지 않습니다. 다음 장의 회귀는 방향과 단위를 정해 평균적 관계를 모형화하지만 그 자체로 인과 추론이 되지는 않습니다.</p>''')
 sec('practice','확인 문제','상관이 말하는 것과 말하지 않는 것을 구별하세요','''<ol class="learn-exercises"><li>r=0이면 두 변수는 독립인가요?<details><summary>답과 해설</summary><p>일반적으로 아닙니다. Y=X²의 대칭 예제처럼 비선형 관계가 남을 수 있습니다.</p></details></li><li>면적 단위를 ㎡에서 다른 단위로 양의 상수배하면 r은?<details><summary>답과 해설</summary><p>같은 관측을 쓰면 Pearson r은 변하지 않습니다. 기울기와 단위는 바뀔 수 있습니다.</p></details></li><li>집단별 상관이 모두 양수이면 전체도 양수인가요?<details><summary>답과 해설</summary><p>아니요. 집단 평균 수준의 차이 때문에 전체 방향이 반대일 수 있습니다.</p></details></li><li>상관이 유의하면 X를 바꾸어 Y를 바꿀 수 있나요?<details><summary>답과 해설</summary><p>그 결론에는 인과 설계와 가정이 필요합니다. 유의성만으로 교란·역인과를 배제하지 못합니다.</p></details></li></ol>''')
 sec('macro','CH2 Macro에서 읽기','거래 조건과 산점도를 함께 확인합니다','''<p>CH2 Macro에서 면적·단가·연식 등의 관계를 볼 때는 유형·기간·지역과 극단값, 동일 건물의 반복 거래, 단가의 분모를 확인하세요. 전체 산점도와 조건을 맞춘 비교가 서로 다른 질문임을 구분합니다.</p><p>이 장의 상관은 교재용 계산이며 개별 물건의 적정가나 특정 조건 변경의 가격 효과를 보장하지 않습니다. 화면에 어떤 상관이나 회귀가 제공되는지는 해당 기능의 설명을 함께 확인합니다.</p><p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 통계 열기 →</a></p>''')
 sec('recap','정리와 참고자료','산점도·계수·표집 조건을 함께 읽습니다','''<p>Pearson은 선형 관계, Spearman은 순위의 단조 관계를 요약합니다. 비선형·이상치·범위 제한·집단 혼합을 점검하고 상관을 인과효과로 바꾸어 읽지 않습니다.</p><p>다음 <a href="/learn/stats/regression/">17장 「단순선형회귀와 최소제곱법」</a>에서 관계의 기울기와 예측값을 다룹니다.</p><ul><li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/scatterp.htm">NIST/SEMATECH: Scatter Plot</a> — 산점도의 관계·곡선·이상치와 인과 해석의 한계.</li></ul><p class="learn-source-note">본문과 그림은 공통 학습 자료 및 별도 가상 예제로 직접 작성했습니다. 실제 시장의 인과효과가 아닙니다. 참고자료 확인: 2026-10-08.</p>''')
 p=ROOT/'correlation/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="상관관계와 인과관계">\n'+'\n'.join(parts)+'\n</article>',html,count=1,flags=re.S)
 html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1상관계수와 산점도, 비선형·집단 혼합의 영향, 인과관계의 차이를 예제와 그림으로 설명합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
