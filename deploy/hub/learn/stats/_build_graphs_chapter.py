"""Build chapter 03 figures and text from the shared teaching dataset."""
from pathlib import Path
import json,re
from statistics import median
from html import escape
ROOT=Path(__file__).resolve().parent

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows']
 prices=[r['price'] for r in rows]
 def txt(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def line(x,y,x2,y2,color='#cbd5e1',extra=''):return f'<line x1="{x}" y1="{y}" x2="{x2}" y2="{y2}" stroke="{color}" {extra}/>'
 def rect(x,y,w,h,color='#93c5fd',extra=''):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{color}" {extra}/>'
 def figure(id,title,desc,body,caption,height):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {height}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{desc}</desc>{body}</svg><figcaption class="learn-chart__caption">{caption}</figcaption></figure>'
 body=txt(24,28,'구분별 빈도 · 공통 예시 30건')
 for group,y in [('주거',62),('상업',120)]:
  count=sum(r['group']==group for r in rows)
  body+=txt(24,y+21,group)+rect(100,y,count*26,30)+txt(505,y+21,f'{count}건 ({count/len(rows):.0%})')
 body+=line(100,184,490,184)
 for n in [0,5,10,15]:body+=txt(100+n*26,207,n,'text-anchor="middle"')
 body+=txt(530,207,'건수(건)')
 f1=figure('category-bars','범주형 변수의 막대그래프','주거 15건과 상업 15건. 두 막대 사이에는 간격이 있고 가로축은 0부터 시작합니다.',body,'그림 1. 범주별 빈도는 관측 수입니다. 두 유형의 건수가 같아도 단가나 면적 분포가 같다는 뜻은 아닙니다.',230)
 body='';hist=[]
 for idx,width in enumerate([60,120]):
  top=35+idx*265;base=top+180;counts=[sum(lo<=v<lo+width for v in prices) for lo in range(60,540,width)];hist.append({'width':width,'start':60,'end':540,'counts':counts})
  body+=txt(24,top,f'구간 폭 {width}만원/㎡ · 건수(건)')
  for n in [0,10,20,30]:
   y=base-n*5;body+=line(70,y,598,y)+txt(58,y+4,n,'text-anchor="end"')
  for j,count in enumerate(counts):
   x=70+j*width*1.1;body+=rect(x,base-count*5,width*1.1,count*5,'#93c5fd','stroke="#1d4ed8" data-bin-width="'+str(width)+'" data-count="'+str(count)+'"')
   body+=txt(x+width*.55,base-count*5-7,count,'text-anchor="middle"')
  for n in range(60,541,120):body+=txt(70+(n-60)*1.1,base+24,n,'text-anchor="middle"')
  body+=txt(435,base+48,'단가(만원/㎡)')
 f2=figure('histogram-widths','같은 자료의 두 히스토그램','60만원 구간별 건수는 14,10,3,2,0,0,0,1. 120만원 구간별 건수는 24,5,0,1입니다.',body,'그림 2. 같은 30건, 같은 가로 범위와 세로 눈금입니다. 각 구간은 왼쪽 경계를 포함하고 오른쪽 경계는 제외합니다. 폭을 바꾸면 막대의 높이와 보이는 굴곡이 달라집니다.',540)
 shapes=[('대칭',[1,3,7,11,7,3,1]),('오른쪽 꼬리',[12,9,6,4,2,1,1]),('두 봉우리',[1,7,11,2,11,7,1])]
 body=txt(24,25,'분포를 읽는 세 가지 모양 · 개념도')
 for idx,(name,counts) in enumerate(shapes):
  x=28+idx*208;base=175
  body+=txt(x,55,name)+line(x,base,x+177,base)
  for j,c in enumerate(counts):body+=rect(x+j*25,base-c*8,24,c*8)
  body+=txt(x,199,'작은 값 → 큰 값')
 body+=txt(24,230,'높이는 상대적인 빈도를 나타냅니다. 실제 관측 자료가 아닙니다.')
 f3=figure('distribution-shapes','대칭과 왜도, 두 봉우리','대칭은 양쪽 모양이 비슷하고, 오른쪽 꼬리는 큰 값 방향으로 길어집니다. 두 봉우리는 두 구간에 값이 몰린 모습입니다.',body,'그림 3. 분포 모양을 설명하기 위해 직접 정한 도식입니다. 원자료 30건에서 계산한 그래프가 아니며, 모양만으로 원인이나 분포 종류를 확정하지 않습니다.',255)
 body=txt(24,26,'구분을 함께 표시한 면적–단가 산점도')+txt(24,51,'단가(만원/㎡)')
 for val in [0,100,200,300,400,500]:
  y=285-val*.42;body+=line(70,y,590,y)+txt(58,y+4,val,'text-anchor="end"')
 for val in [0,100,200,300]:body+=txt(70+val*1.6,309,val,'text-anchor="middle"')
 for r in rows:
  x=70+r['area']*1.6;y=285-r['price']*.42
  if r['group']=='주거':body+=f'<circle cx="{x}" cy="{y}" r="4.5" fill="#2563eb" data-observation="{r["id"]}"/>'
  else:body+=rect(x-4.5,y-4.5,9,9,'#d97706' if r['id']==7 else '#475569',f'data-observation="{r["id"]}"')
 body+=txt(117,76,'7번: 22㎡ · 480만원/㎡')+txt(470,335,'면적(㎡)')
 body+='<circle cx="42" cy="357" r="4.5" fill="#2563eb"/>'+txt(54,362,'주거')+rect(128,352,9,9,'#475569')+txt(144,362,'상업')+rect(222,352,9,9,'#d97706')+txt(238,362,'상업 7번')
 f4=figure('grouped-scatter','유형을 나누어 보는 산점도','공통 예시 30건. 주거는 파란 원, 상업은 회색 사각형, 7번은 주황 사각형으로 구분합니다.',body,'그림 4. 점의 위치는 면적과 단가, 모양은 유형을 나타냅니다. 번호 순서대로 선을 잇지 않습니다. 모양과 색을 함께 사용해 집단을 구분합니다.',385)
 ordered=sorted(prices);q1=median(ordered[:15]);q2=median(ordered);q3=median(ordered[15:]);iqr=q3-q1
 within=[v for v in prices if q1-1.5*iqr<=v<=q3+1.5*iqr];lo=min(within);hi=max(within)
 body=txt(24,25,'상자그림은 중앙의 위치와 퍼짐을 압축합니다')
 body+=line(60+lo,100,60+hi,100,'#475569')+rect(60+q1,80,q3-q1,40,'#93c5fd')+line(60+q2,80,60+q2,120,'#1d4ed8','stroke-width="3"')
 for v in [lo,hi]:body+=line(60+v,90,60+v,110,'#475569')
 body+='<circle cx="540" cy="100" r="5" fill="#d97706"/>'
 for x,y,label in [(60+lo,144,'62'),(60+q1,65,'Q1 98'),(60+q2,165,'중앙값 122'),(60+q3,65,'Q3 168'),(60+hi,144,'268'),(540,78,'7번 480')]:body+=txt(x,y,label,'text-anchor="middle"')
 body+=line(60,195,560,195)
 for v in [0,100,200,300,400,500]:body+=txt(60+v,217,v,'text-anchor="middle"')
 body+=txt(430,244,'단가(만원/㎡)')
 f5=figure('box-summary','공통 예시의 상자그림','Q1은98, 중앙값122, Q3는168. 1.5IQR 규칙에서 수염 끝은62와268이며480은 별도 점입니다.',body,'그림 5. 정렬 자료를 반으로 나눈 뒤 각 절반의 중앙값을 사분위수로 사용했습니다. 수염은 1.5×IQR 경계 안의 실제 관측값까지 뻗습니다.',265)
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}">\n<p class="learn-chapter__label">{label}</p>\n<h2>{title}</h2>\n{body}\n</section>')
 sec('quick-start','핵심 이해','질문에 맞는 그래프를 고릅니다','''<p>같은 표라도 무엇을 알고 싶은지에 따라 필요한 그림이 달라집니다. 유형별로 몇 건인지 궁금하다면 막대그래프, 단가가 어디에 몰렸는지 궁금하다면 히스토그램, 면적과 단가의 관계가 궁금하다면 산점도를 선택합니다.</p><p>이 장에서는 그래프를 고르고, 분포의 중심·퍼짐·꼬리·봉우리를 읽으며, 축과 구간 설정이 해석에 미치는 영향을 살펴봅니다. 선수 개념은 <a href="/learn/stats/data-and-variables/#types">변수 유형</a>과 <a href="/learn/stats/population-and-sampling/#population-frame">자료가 대표하는 대상</a>입니다.</p><div class="learn-data learn-data--full"><table><caption>질문과 그래프 연결하기</caption><thead><tr><th scope="col">질문</th><th scope="col">주요 그래프</th><th scope="col">읽는 대상</th></tr></thead><tbody><tr><th scope="row">유형별로 몇 건인가?</th><td>막대그래프</td><td>범주별 건수·비율</td></tr><tr><th scope="row">값이 어디에 몰렸는가?</th><td>히스토그램·점도표</td><td>한 수치형 변수의 분포</td></tr><tr><th scope="row">집단별 중심과 퍼짐은?</th><td>상자그림</td><td>중앙값·사분위수·끝부분</td></tr><tr><th scope="row">두 변수가 어떻게 관련되는가?</th><td>산점도</td><td>같은 관측의 두 값</td></tr><tr><th scope="row">시간에 따라 어떻게 변했는가?</th><td>시계열 선그래프</td><td>정의가 일관된 시점별 값</td></tr></tbody></table></div>''')
 table='<div class="learn-data"><table><caption>공통 학습 예시 30건 전체</caption><thead><tr>'+''.join(f'<th scope="col">{x}</th>' for x in ['번호','구분','면적(㎡)','층','단가(만원/㎡)'])+'</tr></thead><tbody>'
 for r in rows:table+='<tr'+(' class="is-outlier"' if r['id']==7 else '')+'>'+''.join(f'<td>{escape(str(v))}</td>' for v in r.values())+'</tr>'
 table+='</tbody></table></div>'
 sec('data','예제 자료','같은 30건을 여러 관점으로 봅니다','''<p>01장에서 사용한 공통 예시를 다시 씁니다. 주거 15건·상업 15건이며, 면적은 22~310㎡, 단가는 62~480만원/㎡입니다. 번호는 식별용 순서이며 거래 시점이 아닙니다.</p><p>출처는 학습계획의 ‘흥덕 예시 30건’입니다. 실제 거래 원천이 확인되지 않았으므로 학습 예시로만 사용하며, 실제 지역의 시장 수준을 설명하지 않습니다. 그림 3만 별도의 분포 개념도이고 나머지 그림은 이 30건에서 계산합니다.</p><details class="learn-more"><summary>원자료 30건 보기</summary><div class="learn-more__body">'''+table+'''<p><a href="../example-data.json">동일한 원자료(JSON)</a>도 확인할 수 있습니다. 숫자와 그림의 계산 과정은 이 자료를 기준으로 재현합니다.</p></div></details>''')
 sec('bar-chart','막대그래프','범주별 건수와 비율을 비교합니다','''<p>막대그래프는 범주마다 하나의 막대를 놓아 크기를 비교합니다. 주거와 상업은 별개의 범주이므로 막대 사이의 간격으로 구분합니다. 범주 순서는 설명 목적에 따라 바꿀 수 있지만, 등급처럼 본래 순서가 있는 범주는 그 순서를 유지하는 편이 좋습니다.</p>'''+f1+'''<p>집단의 총건수가 다르면 건수와 비율을 구별해야 합니다. 예를 들어 A지역 100건 중 상업 20건, B지역 20건 중 상업 10건이라면 상업 거래 건수는 A가 많지만 비율은 A 20%, B 50%입니다. ‘어디에 더 많은가’와 ‘어디에서 더 큰 비중인가’는 서로 다른 질문입니다.</p>''')
 sec('histograms','히스토그램과 구간 폭','값의 범위를 나누고 각 구간의 건수를 셉니다','''<p>히스토그램은 수치형 변수의 범위를 연속된 구간으로 나누어 그 안의 관측 수를 표시합니다. 범주별 막대그래프와 달리 가로축에는 크기와 간격의 의미가 있어 구간의 순서를 임의로 바꿀 수 없습니다. 빈 구간도 지우지 않고 자리를 남겨야 값 사이의 거리를 읽을 수 있습니다.</p>'''+f2+'''<p>위 그림의 첫 구간은 60 이상 120 미만으로 14건입니다. 단가가 정확히 120인 관측은 다음 구간으로 들어갑니다. 480도 420~480 구간이 아니라 480~540 구간에 들어갑니다. 경계값이 두 구간에 중복되거나 빠지지 않도록 규칙을 정합니다.</p><p>구간 폭을 120으로 넓히면 60 이상 180 미만의 24건이 한 막대에 들어갑니다. 자료가 늘어난 것이 아니라 더 넓은 범위를 묶은 것입니다. 좁은 구간은 세부 차이를 보여 주지만 우연한 굴곡이 두드러질 수 있고, 넓은 구간은 그 차이를 숨길 수 있습니다. 구간의 시작점도 모양에 영향을 줍니다.</p><details class="learn-more"><summary>구간 폭이 서로 다르면 높이를 어떻게 읽을까요?</summary><div class="learn-more__body"><p>폭이 다른 구간에 건수를 그대로 높이로 그리면 넓은 구간이 과장될 수 있습니다. 밀도 히스토그램은 높이를 ‘구간 건수 ÷ 전체 건수 ÷ 구간 폭’으로 계산하여 막대의 면적이 비율을 나타내게 합니다. 이 장의 두 그림은 각각 같은 폭의 구간을 쓰는 빈도 히스토그램이므로 세로축이 건수입니다.</p></div></details>''')
 sec('shape','분포의 모양','중심·퍼짐·꼬리·봉우리를 함께 읽습니다','''<p><strong>분포</strong>는 값들이 어디에 얼마나 놓여 있는지를 뜻합니다. 그래프에서는 먼저 값이 많이 모인 위치와 전체 범위를 보고, 어느 방향으로 꼬리가 긴지, 여러 봉우리나 떨어진 점이 있는지를 차례로 살펴봅니다.</p>'''+f3+'''<p>대칭에 가까운 분포는 가운데를 기준으로 양쪽 모양이 비슷합니다. 오른쪽 꼬리가 긴 분포는 큰 값 방향으로 드문 관측이 멀리 이어집니다. ‘오른쪽으로 치우쳤다’는 말은 관측 대부분이 오른쪽에 있다는 뜻과 다르므로 꼬리의 방향을 명시하는 편이 정확합니다.</p><p>공통 예제에서는 30건 중 24건, 즉 80%가 60 이상 180 미만에 있고, 큰 값 쪽에 480이 떨어져 있습니다. 작은 표본이므로 이 모양만으로 실제 모집단의 분포를 확정하지는 않습니다. 두 봉우리가 보이면 여러 집단이 섞였는지 살펴볼 수 있지만, 구간 선택이나 우연한 표집 변동도 원인일 수 있습니다.</p><p>외따로 보이는 값은 확인할 대상입니다. 입력 오류인지, 다른 조건의 관측인지, 드물지만 유효한 값인지 조사하기 전에 삭제하지 않습니다. 이상치 판단은 <a href="/learn/stats/iqr-outliers/">07장</a>에서 이어집니다.</p>''')
 sec('scatter','산점도','한 점에 같은 관측의 두 값을 놓습니다','''<p>산점도의 한 점은 같은 관측에서 얻은 두 수치형 변수의 짝입니다. 가로 위치를 면적, 세로 위치를 단가로 정하면 면적이 비슷한 거래들의 단가가 얼마나 다른지 함께 볼 수 있습니다. 집단 정보는 색과 점 모양으로 더할 수 있습니다.</p>'''+f4+'''<p>그림에서는 면적이 큰 관측들이 대체로 낮은 단가 쪽에 놓이고, 작은 면적 쪽의 단가 범위가 넓습니다. 그러나 그림만으로 면적 증가가 단가 하락을 일으킨다고 말할 수는 없습니다. 유형이나 다른 조건이 함께 달라질 수 있으며, 7번처럼 떨어진 관측의 영향도 살펴봐야 합니다.</p><p>같은 위치에 관측이 겹치면 점의 개수보다 거래가 적어 보일 수 있습니다. 투명도나 겹친 건수 표시로 보완할 수 있습니다. 원자료가 시간 순서가 아닌 이 예제에서는 번호 순서대로 선을 잇지 않습니다. 그런 선의 굴곡은 가격 추세를 나타내지 않습니다.</p>''')
 sec('boxplot','상자그림','분포를 요약하되 숨겨지는 모양도 기억합니다','''<p>상자그림은 가운데 50%가 놓인 범위와 중앙값을 압축해서 보여 줍니다. 여러 집단의 중심과 퍼짐을 나란히 비교할 때 유용합니다. 여기서는 모양을 읽는 데 집중하고, 사분위수 계산은 <a href="/learn/stats/quantiles/">05장</a>에서 자세히 다룹니다.</p>'''+f5+'''<p>상자의 왼쪽·오른쪽 끝은 98과 168이고 내부 선은 중앙값 122입니다. 이 예제의 IQR은 168−98=70, 1.5×IQR은 105입니다. 경계는 −7과 273이므로 그 안의 실제 최솟값 62와 최댓값 268까지 수염을 그립니다. 480은 별도 점으로 표시합니다. 수염 끝을 언제나 최솟값·최댓값이라고 읽으면 안 되는 이유입니다.</p><p>상자그림만으로는 봉우리 개수나 빈 구간을 알기 어렵습니다. 요약값이 같은데 히스토그램 모양이 다른 자료도 가능합니다. 표본이 작다면 원래 점들을 함께 보거나 히스토그램과 비교하는 편이 좋습니다. 프로그램마다 사분위수와 수염의 규칙이 다를 수 있으므로 범례도 확인합니다.</p>''')
 sec('reading','오해를 피하는 읽기','그림의 인상보다 축과 조건을 먼저 확인합니다','''<ul><li><strong>막대의 시작점:</strong> 100과 110은 10% 차이입니다. 막대 길이를 90부터 그리면 보이는 길이가 10과 20이 되어 두 배처럼 느껴집니다. 길이로 비교하는 막대는 원칙적으로 0을 기준으로 읽습니다.</li><li><strong>축 범위:</strong> 같은 두 집단을 서로 다른 세로축으로 그리면 퍼짐이나 변화의 크기를 직접 비교하기 어렵습니다. 축을 확대했다면 범위를 명확히 확인합니다.</li><li><strong>선의 의미:</strong> 시간 추이를 보려면 실제 시점과 일관된 집계 기준이 필요합니다. 누락된 기간을 0으로 채우거나 관측 번호를 시간으로 해석하지 않습니다.</li><li><strong>표본 조건:</strong> 기간·지역·유형이 바뀌면 그림이 달라질 수 있습니다. 다른 시기의 평균 차이가 동일 물건의 가격 변화인지, 거래 구성의 변화인지 구분합니다.</li></ul><p>이 원칙을 모든 그래프의 축을 무조건 0부터 그리라는 뜻으로 확장하지는 않습니다. 산점도나 선그래프는 필요한 구간을 확대해 관계나 변화를 살필 수 있습니다. 중요한 것은 축의 범위와 그래프가 전달하는 비교를 명확히 하는 일입니다.</p>''')
 sec('practice','확인 문제','같은 자료에서 다른 그림이 나오는 이유를 설명해 보세요','''<ol class="learn-exercises"><li>그림 2에서 구간 폭을 60에서 120으로 바꾸자 첫 막대가 14건에서 24건이 되었습니다. 관측이 10건 늘어난 것일까요?<details><summary>답과 해설</summary><p>아니요. 원래 60~120의 14건과 120~180의 10건을 한 구간에 합쳤습니다. 두 히스토그램 모두 전체 관측은 30건입니다.</p></details></li><li>그림 4의 점을 번호 순서대로 연결하면 거래 단가의 시간 추이를 볼 수 있을까요?<details><summary>답과 해설</summary><p>아니요. 번호는 식별자이며 거래 시점이 아닙니다. 시간 추이를 보려면 날짜가 필요하고, 시점별 비교 대상과 집계 기준도 맞춰야 합니다.</p></details></li><li>상자그림의 위쪽 수염에 해당하는 큰 값 쪽 끝은 268입니다. 가장 큰 값도 268일까요?<details><summary>답과 해설</summary><p>아니요. 1.5×IQR 경계 안의 가장 큰 관측이 268이며 실제 최댓값 480은 별도 점으로 남아 있습니다. 수염 규칙과 점을 함께 읽어야 합니다.</p></details></li></ol>''')
 sec('macro','CH2 Macro에서 읽기','요약표를 읽을 때 분포의 모양을 함께 떠올립니다','''<p>CH2 Macro 토지 기본통계의 평균·중위·25%값·75%값은 분포를 요약하는 수치입니다. 요약표만으로 전체 모양을 복원할 수는 없지만, 중심과 퍼짐을 구별해서 읽는 출발점이 됩니다.</p><figure class="learn-capture"><img src="../assets/captures/land-heungdeok-stats.png" loading="lazy" alt="CH2 Macro 토지 기본통계의 거래 건수와 단가 요약표"/><figcaption class="learn-capture__caption">기존 로컬 캡처: 토지 · 청주시 흥덕구 · 5년 롤링. 이 장의 예시 30건과 다른 자료이며 현재 운영 수치를 뜻하지 않습니다.</figcaption></figure><p>평균 하나를 비교하기 전에 기간·유형·건수·단위가 같은지 확인하세요. 이 장의 히스토그램과 산점도는 학습용 그림이며 해당 화면에 같은 그래프 기능이 구현되어 있다는 뜻은 아닙니다.</p><p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 기본통계 열기 →</a></p>''')
 sec('recap','정리와 참고자료','그림마다 드러내는 정보가 다릅니다','''<p>막대그래프는 범주별 크기, 히스토그램은 한 변수의 분포, 산점도는 두 변수의 관계, 상자그림은 중심과 퍼짐의 요약을 보여 줍니다. 같은 자료를 여러 그림으로 보고, 축·구간·표본 조건을 함께 확인하면 한 그림의 인상에만 기대는 해석을 줄일 수 있습니다.</p><p>다음 <a href="/learn/stats/mean-and-median/">04장 「평균과 중앙값」</a>에서는 분포의 중심을 숫자로 표현하는 두 방법을 비교합니다.</p><ul><li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/histogra.htm">NIST/SEMATECH e-Handbook: Histogram</a> — 히스토그램의 정의와 정규화 방식.</li><li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/scatterp.htm">NIST/SEMATECH e-Handbook: Scatter Plot</a> — 두 변수의 관계와 산점도 해석.</li></ul><p class="learn-source-note">본문과 그림은 공통 예제에 맞춰 새로 작성했습니다. 그림 3은 실제 자료가 아닌 개념도입니다. 참고자료 확인: 2026-10-07.</p>''')
 page=ROOT/'graphs/index.html';s=page.read_text(encoding='utf-8')
 s=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="그래프로 보는 데이터와 분포">\n'+'\n'.join(parts)+'\n</article>',s,count=1,flags=re.S)
 s=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1막대그래프·히스토그램·산점도·상자그림으로 같은 자료를 읽고, 구간 폭과 축 설정에 따른 차이를 이해합니다.\2',s,count=1,flags=re.S)
 page.write_text(s,encoding='utf-8')
 return hist
if __name__=='__main__':print(build())
