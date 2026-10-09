"""Generate chapter 05 using explicit median-of-halves and type-7 conventions."""
from pathlib import Path
from statistics import median
from html import escape
import json,re,math
ROOT=Path(__file__).resolve().parent

def summary(values):
 a=sorted(values);n=len(a);q1=median(a[:n//2]);q2=median(a);q3=median(a[(n+1)//2:]);iqr=q3-q1
 inside=[v for v in a if q1-1.5*iqr<=v<=q3+1.5*iqr]
 return q1,q2,q3,min(inside),max(inside),[v for v in a if v not in inside]
def type7(values,p):
 a=sorted(values);h=(len(a)-1)*p;j=math.floor(h);return a[j]+(h-j)*(a[min(j+1,len(a)-1)]-a[j])
def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];v=[r['price'] for r in rows];a=sorted(v)
 def t(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def l(x,y,xx,yy,extra=''):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="#64748b" {extra}/>'
 def r(x,y,w,h,c='#93c5fd',extra=''):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}" {extra}/>'
 def fig(id,title,desc,b,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{desc}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=t(24,27,'분위수는 비율에 대응하는 값입니다')+l(50,112,590,112)
 for p,label in [(0,'최솟값'),(.25,'Q1'),(.5,'Q2 · 중앙값'),(.75,'Q3'),(1,'최댓값')]:
  x=50+p*540;b+=l(x,100,x,123)+t(x,87,label,'text-anchor="middle"')+t(x,148,f'{p:.0%}','text-anchor="middle"')
 b+=t(24,190,'여기서 같은 간격은 누적 비율의 간격입니다. 단가의 간격이 아닙니다.')
 f1=fig('quantile-map','누적 비율과 분위수','25%,50%,75%에 대응하는 값이 각각 Q1,Q2,Q3입니다.',b,'그림 1. 분위수의 위치를 설명하는 개념도. 백분위수는 단가처럼 변수의 단위를 가지며, 백분위 순위는 비율 또는 %로 표현합니다.',215)
 b=t(24,26,'아래 15건과 위 15건의 가운데를 찾습니다')
 for i,value in enumerate(a):
  x=24+(i%10)*60;y=68+(i//10)*67
  b+=r(x,y,54,31,'#93c5fd' if i in [7,14,15,22] else '#f1f5f9')+t(x+27,y-7,f'{i+1}번째','text-anchor="middle"')+t(x+27,y+22,value,'text-anchor="middle"')
 b+=t(24,285,'Q1: 8번째 98 / Q2: (120 + 124) ÷ 2 = 122 / Q3: 23번째 168')
 f2=fig('quartile-ranks','공통 자료의 사분위수 계산','하위15개 중앙값98, 전체 중앙값122, 상위15개 중앙값168입니다.',b,'그림 2. 이 장은 중앙값으로 나눈 두 절반의 중앙값을 Q1·Q3로 사용합니다. 홀수 자료에서는 전체 중앙 관측을 두 절반에서 제외합니다.',310)
 def box(values,y,style,id):
  q1,q2,q3,lo,hi,out=summary(values)
  if style=='range':lo,hi=min(values),max(values);out=[]
  b=l(60+lo,y,60+hi,y)+r(60+q1,y-15,q3-q1,30,'#93c5fd',f'data-box="{id}" data-q1="{q1}" data-q2="{q2}" data-q3="{q3}" data-low="{lo}" data-high="{hi}"')+l(60+q2,y-15,60+q2,y+15,'stroke-width="3"')
  for value in [lo,hi]:b+=l(60+value,y-9,60+value,y+9)
  for value in out:b+=f'<circle cx="{60+value}" cy="{y}" r="5" fill="#d97706" data-outlier="{value}"/>'
  return b
 b=t(24,26,'같은 자료도 수염 규칙에 따라 끝이 달라집니다')+t(24,64,'최솟값–최댓값 수염')+box(v,100,'range','range')+t(540,80,'480','text-anchor="middle"')+t(24,151,'1.5×IQR 경계 안의 관측값까지')+box(v,190,'iqr','iqr')+t(328,224,'수염 끝 268','text-anchor="middle"')+t(540,224,'별도 점 480','text-anchor="middle"')+l(60,255,560,255)
 for x in [0,100,200,300,400,500]:b+=t(60+x,277,x,'text-anchor="middle"')
 b+=t(440,303,'단가(만원/㎡)')
 f3=fig('whisker-rules','수염 규칙의 비교','위는수염이480까지, 아래는268까지이며480이 별도 점입니다. 상자는 모두98에서168입니다.',b,'그림 3. 두 규칙 모두 쓰이므로 범례를 확인합니다. 이 과정의 이상치 표시 상자그림은 아래의 1.5×IQR 규칙을 기본으로 사용합니다.',330)
 b=t(24,26,'같은 단가 축으로 두 집단을 비교합니다')
 groups={g:[r['price'] for r in rows if r['group']==g] for g in ['주거','상업']}
 for g,y in [('주거',100),('상업',195)]:
  q=summary(groups[g]);b+=t(24,y-34,f'{g} · n=15 · Q1 {q[0]:g} / 중앙값 {q[1]:g} / Q3 {q[2]:g}')+box(groups[g],y,'iqr',g)
 b+=l(60,255,560,255)
 for x in [0,100,200,300,400,500]:b+=t(60+x,277,x,'text-anchor="middle"')
 b+=t(435,307,'단가(만원/㎡)')
 f4=fig('group-boxes','주거와 상업의 상자그림','주거의사분위수88,105,120. 상업124,168,235. 두집단각15건입니다.',b,'그림 4. 공통 학습 예시에서 두 집단을 따로 계산했습니다. 상자의 가로 길이는 IQR이고 세로 두께에는 수치 의미를 부여하지 않았습니다.',330)
 b=t(24,26,'계산 관례가 다르면 사분위수도 조금 달라집니다')
 for y,label,q in [(90,'두 절반의 중앙값',(98,122,168)),(175,'선형 보간 (type 7)',tuple(type7(v,p) for p in [.25,.5,.75]))]:
  b+=t(24,y-26,label)+l(240,y,575,y)
  for value in q:
   x=240+(value-90)*4;b+=l(x,y-7,x,y+7)+t(x,y+25,f'{value:g}','text-anchor="middle"')
 b+=t(365,244,'단가(만원/㎡) · 90~174 구간 확대')
 f5=fig('quantile-methods','두 사분위수 계산 관례','두절반 방식98,122,168과 type7 방식99,122,166을 비교합니다.',b,'그림 5. 같은 자료와 단위에서 계산법만 바꾼 예입니다. 숫자가 다르다는 사실만으로 어느 한 계산을 오류라고 판단하지 않습니다.',270)
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}">\n<p class="learn-chapter__label">{label}</p>\n<h2>{title}</h2>\n{body}\n</section>')
 sec('quick-start','핵심 이해','가운데뿐 아니라 분포의 여러 위치를 봅니다','''<p>중앙값은 정렬한 자료의 가운데를 요약합니다. 그렇다면 아래쪽 25%와 위쪽 25%를 가르는 값은 무엇일까요? <strong>분위수</strong>는 이런 여러 위치를 나타내는 값입니다. 이를 이용하면 중심뿐 아니라 자료 가운데 부분의 퍼짐도 읽을 수 있습니다.</p><p>이 장에서는 백분위수·사분위수와 백분위 순위를 구별하고, 공통 예제의 사분위수를 계산한 뒤 상자와 수염을 해석합니다. 선수 개념은 <a href="/learn/stats/mean-and-median/#median">중앙값</a>과 <a href="/learn/stats/graphs/#shape">분포의 모양</a>입니다.</p>'''+f1)
 sec('percentiles','분위수와 백분위 순위','비율에 대응하는 값과 값의 순위를 구별합니다','''<p>p분위수는 분포에서 아래쪽 누적 비율 p에 대응하는 값입니다. p=0.25이면 25백분위수, p=0.75이면 75백분위수라고 합니다. 연속적인 분포에서는 그 값 아래에 놓이는 비율로 직관적으로 이해할 수 있습니다. 유한한 표본에서는 관측 개수와 동점 때문에 정확히 그 비율로 나뉘지 않을 수 있습니다.</p><p>단가의 75백분위수가 168만원/㎡라는 말에서 75는 위치를 지정하는 비율이고 168은 단가입니다. 이를 단가가 평균보다 75% 높다는 뜻으로 읽지 않습니다. 반대로 ‘단가 168이 자료에서 어느 위치인가’를 묻는 것은 백분위 순위의 질문입니다.</p><p>예를 들어 100·100·100·200에서 100보다 작은 관측의 비율은 0%, 100 이하의 비율은 75%입니다. 동점을 어떻게 처리하는지에 따라 순위 표현이 달라지므로, 값 아래인지 이하인지와 순위 산정 규칙을 확인해야 합니다.</p>''')
 sec('calculation','사분위수 계산','정렬한 자료를 두 번 나눕니다','''<p>Q1·Q2·Q3는 각각 25·50·75백분위수에 해당하는 사분위수입니다. Q2는 중앙값입니다. 이 장의 공통 자료 30건은 앞 장과 같으며, 실제 거래 출처가 확인되지 않은 학습 예시입니다. <a href="/learn/stats/graphs/#data">전체 표</a>와 <a href="../example-data.json">원자료</a>를 함께 볼 수 있습니다.</p>'''+f2+'''<p>먼저 전체 중앙값은 (120+124)÷2=122입니다. 하위 15건의 가운데인 8번째 값은 98이므로 Q1=98입니다. 상위 15건의 가운데는 전체의 23번째 값인 168이므로 Q3=168입니다.</p><p>자료 수 30의 25%는 7.5건입니다. 관측을 반 건으로 셀 수 없기 때문에 사분위수 아래에 정확히 7.5건이 있는 것은 아닙니다. 이 규칙에서는 98 이하가 8건이고, 98~168에 양 끝을 포함하면 16건입니다. ‘상자는 가운데 50%를 요약한다’는 뜻과 표본에서 경계값을 포함해 센 실제 건수는 구분합니다.</p>''')
 sec('iqr','IQR과 상자','상자의 길이는 가운데 부분의 퍼짐입니다','''<p><strong>사분위범위(IQR)</strong>는 Q3−Q1입니다. 공통 자료에서는 168−98=<strong>70만원/㎡</strong>입니다. 상자는 Q1에서 Q3까지 그리고 내부 선은 중앙값에 놓습니다. 따라서 상자의 양 끝은 평균에서 같은 거리일 필요가 없습니다.</p><p>상자가 짧으면 가운데 부분이 상대적으로 좁은 범위에 모였다는 뜻입니다. 전체 범위가 좁거나 모든 관측이 비슷하다는 뜻은 아닙니다. 이 자료는 가운데 부분의 길이가 70인 반면 전체 범위는 480−62=418입니다.</p><p>가로로 그린 상자에서는 가로 길이가 IQR입니다. 세로로 그린 상자에서는 세로 길이가 IQR입니다. 상자의 다른 방향 두께는 보통 장식적인 너비이며, 표본수에 비례하도록 설계한 경우에는 그 규칙이 따로 표시되어야 합니다.</p>''')
 sec('whiskers','수염과 별도 점','수염 끝과 이상치 경계는 다릅니다','''<p>상자그림에는 수염을 최솟값·최댓값까지 그리는 방식과 IQR 경계를 사용하는 방식이 있습니다. 앞 장부터 이 과정에서 사용하는 이상치 표시 방식은 Q1−1.5×IQR과 Q3+1.5×IQR을 경계로 삼습니다.</p>'''+f3+'''<p>이 자료의 경계는 98−105=−7과 168+105=273입니다. 경계 안에 놓인 실제 관측 중 가장 작은 62와 가장 큰 268까지 수염을 그립니다. 따라서 큰 값 쪽 수염 끝은 경계 273도, 최댓값 480도 아닌 <strong>268</strong>입니다. 480은 별도 점으로 표시합니다.</p><p>−7이라는 계산 결과가 음수 단가를 관측했다는 뜻은 아닙니다. 이는 탐지 규칙으로 정한 경계일 뿐입니다. 별도 점도 오류나 삭제 대상이라는 판정이 아니라 확인할 관측이라는 표시입니다. 구체적인 처리 판단은 <a href="/learn/stats/iqr-outliers/">07장 「이상치와 IQR」</a>에서 이어집니다.</p>''')
 sec('comparison','집단 비교','같은 축과 계산 규칙으로 나란히 봅니다','''<p>집단을 비교할 때는 각 집단 안에서 사분위수를 다시 계산합니다. 전체 자료의 경계로 각 집단의 상자를 대신 그리지 않습니다. 공통 예제의 주거·상업은 각각 15건이므로 홀수 자료 규칙에 따라 각 집단의 중앙 관측을 제외한 아래 7건·위 7건의 중앙값을 사용합니다.</p>'''+f4+'''<p>주거의 중앙값은 105, IQR은 120−88=32입니다. 상업의 중앙값은 168, IQR은 235−124=111입니다. 이 자료에서는 상업 집단의 중심이 높고 가운데 부분도 더 넓게 퍼져 있습니다.</p><p>이 차이를 모든 주거·상업 시장의 차이나 용도의 인과 효과로 일반화하지는 않습니다. 표본 구성·다른 조건·수집 범위를 함께 보아야 합니다. 상자의 겹침 여부만으로 통계적 유의성을 판정하지도 않습니다.</p><p>상자그림은 두 봉우리나 빈 구간을 숨길 수 있습니다. 값이 몇 개 안 되거나 같은 값이 반복되어 상자가 선처럼 보일 때는 원래 점이나 히스토그램을 함께 봅니다. 상자가 좁다는 사실만으로 평균의 추정이 정밀하다고 판단할 수도 없습니다.</p>''')
 sec('methods','계산 관례의 차이','프로그램마다 다른 값이 나올 수 있습니다','''<p>표본 분위수에는 여러 계산 관례가 있습니다. 앞에서 쓴 두 절반의 중앙값 방식 외에 정렬된 두 값 사이를 선형 보간하는 방식도 있습니다. 자료가 작거나 값 사이 간격이 크면 차이가 더 눈에 띌 수 있습니다.</p>'''+f5+'''<p>예를 들어 선형 보간 방식 중 type 7은 1부터 세는 위치 h=1+(n−1)p를 사용합니다. n=30, p=0.25라면 h=8.25이므로 8번째 98에서 9번째 102로 가는 간격의 25%를 더해 Q1=99입니다. p=0.75에서는 h=22.75이므로 160+0.75×(168−160)=166입니다.</p><p>이 장은 기존 공통 예제와의 일관성을 위해 두 절반 방식을 기본으로 유지합니다. 프로그램 결과를 비교할 때는 같은 원자료인지, 결측 처리·가중치·계산 옵션이 같은지 먼저 확인하세요. 분위수를 구하는 함수와 상자그림 함수가 같은 규칙을 쓰는지도 확인해야 합니다.</p>''')
 sec('practice','확인 문제','경계와 관측값을 구별해 보세요','''<ol class="learn-exercises"><li>Q1=98, Q3=168일 때 IQR과 큰 값 쪽 1.5×IQR 경계는 얼마인가요? 수염도 그 경계까지 가나요?<details><summary>답과 해설</summary><p>IQR은 70이고 경계는 168+105=273입니다. 수염은 경계 안의 실제 관측값인 268까지 갑니다.</p></details></li><li>75백분위수가 168만원/㎡이면 단가가 평균보다 75% 높다는 뜻인가요?<details><summary>답과 해설</summary><p>아니요. 75는 정렬 분포 안의 위치를 지정하는 비율입니다. 평균 대비 상승률이 아니며 168은 단가 단위를 갖는 값입니다.</p></details></li><li>다른 프로그램에서 Q1=99, Q3=166이 나왔다면 오류인가요?<details><summary>답과 해설</summary><p>같은 자료라도 type 7 선형 보간을 사용하면 그 값이 나옵니다. 원자료와 계산 관례를 맞춰 비교해야 합니다.</p></details></li></ol>''')
 sec('macro','CH2 Macro에서 읽기','25%값·중위·75%값을 함께 읽습니다','''<p>CH2 Macro 토지 기본통계의 25%값·중위·75%값은 단가 분포의 여러 위치를 읽는 데 도움이 됩니다. 이를 개별 물건의 저평가·고평가 경계로 해석하지 않고, 선택한 거래 집단의 분포 요약으로 읽습니다.</p><figure class="learn-capture"><img src="../assets/captures/land-heungdeok-stats.png" loading="lazy" alt="CH2 Macro 토지 기본통계의 분위 단가 요약"/><figcaption class="learn-capture__caption">기존 로컬 캡처. 이 장의 공통 예제 30건과 다른 자료이며 현재 운영 수치를 뜻하지 않습니다.</figcaption></figure><p>교재의 계산 관례를 서비스의 실제 산식과 같다고 가정하지 않습니다. 서비스 결과와 직접 대조하려면 동일한 지역·기간·필터·원자료 및 분위수 산식을 먼저 확인해야 합니다.</p><p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 기본통계 열기 →</a></p>''')
 sec('recap','정리와 참고자료','위치·퍼짐·규칙을 함께 확인하세요','''<p>분위수는 누적 비율에 대응하는 값입니다. Q1·중앙값·Q3로 상자를 만들고 IQR로 가운데 부분의 퍼짐을 요약합니다. 수염의 규칙과 계산 관례를 알아야 점과 경계도 정확하게 읽을 수 있습니다.</p><p>다음 <a href="/learn/stats/spread/">06장 「분산과 표준편차」</a>에서는 각 관측이 평균에서 얼마나 떨어져 있는지를 이용해 퍼짐을 측정합니다.</p><ul><li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/boxplot.htm">NIST/SEMATECH: Box Plot</a> — 상자그림의 구성과 수염의 변형.</li><li><a href="https://stat.ethz.ch/R-manual/R-devel/library/stats/html/quantile.html">R 공식 문서: Sample Quantiles</a> — 분위수 계산 유형과 선형 보간.</li></ul><p class="learn-source-note">본문과 그림은 이 과정의 자료로 새로 작성했습니다. 그림 1은 개념도입니다. 참고자료 확인: 2026-10-07.</p>''')
 p=ROOT/'quantiles/index.html';s=p.read_text(encoding='utf-8');s=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="분위수와 상자그림">\n'+'\n'.join(parts)+'\n</article>',s,count=1,flags=re.S)
 s=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1분위수·백분위수·사분위수의 계산과 상자그림의 수염, 집단 비교와 계산 관례를 다섯 그림으로 설명합니다.\2',s,count=1,flags=re.S)
 p.write_text(s,encoding='utf-8');print('Quartiles:',summary(v),'type7:',[type7(v,p) for p in [.25,.5,.75]])
if __name__=='__main__':build()
