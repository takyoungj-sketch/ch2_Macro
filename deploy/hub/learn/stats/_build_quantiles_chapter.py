"""Generate chapter 05 using explicit median-of-halves and type-7 conventions."""
from pathlib import Path
from statistics import median
from html import escape
import json, re, math
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parent

def summary(values):
 a=sorted(values);n=len(a);q1=median(a[:n//2]);q2=median(a);q3=median(a[(n+1)//2:]);iqr=q3-q1
 inside=[v for v in a if q1-1.5*iqr<=v<=q3+1.5*iqr]
 return q1,q2,q3,min(inside),max(inside),[v for v in a if v not in inside]
def type7(values,p):
 a=sorted(values);h=(len(a)-1)*p;j=math.floor(h);return a[j]+(h-j)*(a[min(j+1,len(a)-1)]-a[j])

def build():
 rows = json.loads((ROOT / 'example-data.json').read_text(encoding='utf-8'))['rows']
 prices = [row['price'] for row in rows]
 ordered = sorted(prices)
 assert ordered[7] == 98 and ordered[8] == 102
 assert ordered[14] == 120 and ordered[15] == 124
 assert ordered[21] == 160 and ordered[22] == 168
 assert summary(prices) == (98, 122, 168, 62, 268, [480])
 assert [type7(prices, p) for p in (.25, .5, .75)] == [99, 122, 166]
 groups = {name: [row['price'] for row in rows if row['group'] == name] for name in ('주거', '상업')}
 assert len(groups['주거']) == 15 and len(groups['상업']) == 15
 assert summary(groups['주거'])[:3] == (88, 105, 120)
 assert summary(groups['상업'])[:3] == (124, 168, 235)
 assert sum(value <= 98 for value in prices) == 8
 assert sum(98 <= value <= 168 for value in prices) == 16
 q1, q3 = 99, 166
 iqr7 = q3 - q1
 upper7 = q3 + 1.5 * iqr7
 lower7 = q1 - 1.5 * iqr7
 inside7 = [value for value in ordered if lower7 <= value <= upper7]
 assert lower7 == -1.5 and upper7 == 266.5
 assert max(inside7) == 240 and min(inside7) == 62
 assert [value for value in ordered if value > upper7] == [268, 480]

 def t(x, y, text, extra=''):
  return f'<text x="{x}" y="{y}" {extra}>{escape(str(text))}</text>'
 def line(x1, y1, x2, y2, extra=''):
  return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#64748b" {extra}/>'
 def fig(svg_id, title, desc, body, caption, height):
  return (
   f'<figure class="learn-chart learn-chart--wide qn-chart"><svg id="{svg_id}" viewBox="0 0 640 {height}" role="img" aria-labelledby="{svg_id}-title {svg_id}-desc">'
   f'<title id="{svg_id}-title">{title}</title><desc id="{svg_id}-desc">{desc}</desc>{body}</svg>'
   f'<figcaption class="learn-chart__caption">{caption}</figcaption></figure>'
  )

 body = t(16, 28, '누적 비율의 눈금') + line(50, 112, 590, 112)
 for ratio, label in ((0, '0%'), (.25, '25%'), (.5, '50%'), (.75, '75%'), (1, '100%')):
  x = 50 + ratio * 540
  body += line(x, 96, x, 128, f'data-p="{ratio}"') + t(x, 84, label, 'text-anchor="middle"')
 body += t(16, 168, '간격은 비율입니다. 단가 간격이 아닙니다.')
 f1 = fig('qn-map', '분위수와 누적 비율', '0%, 25%, 50%, 75%, 100% 위치가 같은 간격으로 표시된 개념도입니다.', body,
  '그림 1. 분위수는 누적 비율에 대응하는 값입니다. 이 눈금에 공통 30건의 단가를 넣지 않았습니다.', 200)

 body = t(16, 24, '정렬 순위 · Q1은 8번째, 중앙값은 15·16번째, Q3는 23번째')
 for index, value in enumerate(ordered, start=1):
  x = 12 + (index - 1) * 16
  on = index in (8, 15, 16, 23)
  fill = '#fff7ed' if on else '#f1f5f9'
  stroke = '#d97706' if on else '#94a3b8'
  width = '3' if on else '1'
  body += f'<rect data-rank="{index}" data-price="{value}" x="{x}" y="48" width="14" height="36" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'
 body += t(131, 108, '8번째 98', 'text-anchor="middle"')
 body += t(251, 128, '15·16번째', 'text-anchor="middle"')
 body += t(371, 108, '23번째 168', 'text-anchor="middle"')
 body += t(16, 160, 'Q1 98 · 중앙값 (120+124)/2 = 122 · Q3 168')
 body += t(16, 184, '가로 간격은 순위입니다')
 f2 = fig('qn-ranks', '공통 30건의 사분위수', '8번째 98, 15번째 120, 16번째 124, 23번째 168입니다.', body,
  '그림 2. 칸의 위치는 크기순 번호입니다. 98과 168의 차이를 칸 간격으로 읽지 않습니다.', 210)

 def box(values, y, style, label):
  q1, q2, q3, lo, hi, outliers = summary(values)
  if style == 'range':
   lo, hi, outliers = min(values), max(values), []
  extra = f'data-rule-row="{style}" data-box="{label}" data-q1="{q1}" data-q2="{q2}" data-q3="{q3}" data-low="{lo}" data-high="{hi}"'
  named = label == 'iqr'
  marks = f'<rect x="{60 + q1}" y="{y - 15}" width="{q3 - q1}" height="30" fill="#93c5fd" stroke="#64748b" {extra}/>'
  median_extra = 'id="qn-iqr-median" ' if named else ''
  whisker_id = 'id="qn-iqr-whisker" ' if named else ''
  marks += f'<line {median_extra}x1="{60 + q2}" y1="{y - 15}" x2="{60 + q2}" y2="{y + 15}" stroke="#64748b" stroke-width="3" data-rule-row="{style}"/>'
  marks += f'<line {whisker_id}x1="{60 + lo}" y1="{y}" x2="{60 + hi}" y2="{y}" stroke="#64748b" stroke-width="2" data-rule-row="{style}"/>'
  for value, edge in ((lo, 'low'), (hi, 'high')):
   cap = f'data-cap="{edge}" ' if named else ''
   marks += line(60 + value, y - 8, 60 + value, y + 8, f'{cap}data-rule-row="{style}"')
  for value in outliers:
   opacity = '0' if value != 480 else '1'
   marks += f'<circle cx="{60 + value}" cy="{y}" r="5" fill="#d97706" stroke="#d97706" data-outlier="{value}" opacity="{opacity}"/>'
  return marks

 body = t(16, 24, '위: 최솟값–최댓값 · 아래: 1.5×IQR')
 body += t(16, 48, '실선 수염 · 점선 울타리')
 body += box(prices, 96, 'range', 'range')
 body += box(prices, 176, 'iqr', 'iqr')
 body += '<circle cx="328" cy="176" r="5" fill="#d97706" stroke="#d97706" data-outlier="268" opacity="0"/>'
 body += line(53, 150, 53, 202, 'id="qn-fence-low" data-rule-row="iqr" stroke-dasharray="5 4"')
 body += line(333, 150, 333, 202, 'id="qn-fence-high" data-rule-row="iqr" stroke-dasharray="5 4"')
 body += line(60, 230, 560, 230)
 for tick in (0, 100, 200, 300, 400, 500):
  body += t(60 + tick, 252, tick, 'text-anchor="middle"')
 body += t(16, 278, '단가(만원/㎡) · 기본은 아래 규칙')
 f3 = fig('qn-whiskers', '수염과 울타리', '최솟값-최댓값 수염은 62와 480, 1.5배 IQR 수염은 62와 268, 별도 점은 480입니다. 상자는 98에서 168입니다.', body,
  '그림 3. 점선은 계산된 울타리, 실선은 울타리 안의 실제 관측까지 그린 수염입니다. 480은 삭제 대상이 아닙니다.', 300)

 body = t(16, 24, '같은 단가 축 · 두 절반 방식 · 각 15건')
 for name, y in (('주거', 96), ('상업', 186)):
  q1, q2, q3, lo, hi, outliers = summary(groups[name])
  body += t(16, y - 28, f'{name} · Q1 {q1:g} · 중앙값 {q2:g} · Q3 {q3:g}')
  body += box(groups[name], y, 'iqr', name)
 body += line(60, 236, 560, 236)
 for tick in (0, 100, 200, 300, 400, 500):
  body += t(60 + tick, 258, tick, 'text-anchor="middle"')
 body += t(16, 286, '단가(만원/㎡)')
 f4 = fig('qn-groups', '주거와 상업의 상자그림', '주거 15건은 88, 105, 120. 상업 15건은 124, 168, 235입니다.', body,
  '그림 4. 각 집단의 사분위수를 따로 계산했습니다. 상자의 세로 두께에는 건수 의미를 두지 않았습니다.', 310)

 body = t(16, 24, '같은 30건 · 계산법만 다름')
 for y, label, values, key in (
  (88, '두 절반 방식', (98, 122, 168), 'halves'),
  (168, 'Type 7', (99, 122, 166), 'type7'),
 ):
  body += t(16, y - 16, label)
  body += line(240, y, 580, y, f'data-method-row="{key}"')
  for value in values:
   x = 240 + (value - 90) * 4
   body += line(x, y - 8, x, y + 8, f'data-method-row="{key}"') + t(x, y + 24, f'{value:g}', 'text-anchor="middle"')
 body += t(16, 230, '단가(만원/㎡) · 90~174 구간')
 f5 = fig('qn-methods', '분위수 계산법 비교', '두 절반 방식은 98, 122, 168이고 Type 7은 99, 122, 166입니다.', body,
  '그림 5. 계산법이 바뀌면 IQR과 울타리 밖의 후보도 바뀝니다. 그림 3의 아래 상자가 함께 바뀝니다.', 250)

 def scale(price, high):
  return 40 + price / high * 400
 full = ''.join([
  t(16, 28, '최솟값–최댓값 · 단가(만원/㎡)'),
  line(scale(3.3, 320), 110, scale(296.6, 320), 110),
  f'<rect x="{scale(16.1, 320)}" y="90" width="{scale(40, 320) - scale(16.1, 320)}" height="40" fill="#99f6e4" stroke="#0f766e" data-source-box="full" data-q1="16.1" data-median="26" data-q3="40"/>',
  line(scale(26, 320), 90, scale(26, 320), 130, 'stroke-width="3"'),
  t(scale(3.3, 320), 78, '3.3', 'text-anchor="middle"'),
  t(scale(296.6, 320), 78, '296.6', 'text-anchor="middle"'),
  t(16, 220, '상자만 확대 · 수염 생략 (0~60)'),
  f'<rect x="{scale(16.1, 60)}" y="250" width="{scale(40, 60) - scale(16.1, 60)}" height="42" fill="#99f6e4" stroke="#0f766e" data-source-box="zoom" data-q1="16.1" data-median="26" data-q3="40"/>',
  line(scale(26, 60), 250, scale(26, 60), 292, 'stroke-width="3"'),
  t(scale(16.1, 60), 242, 'Q1 16.1', 'text-anchor="middle"'),
  t(scale(26, 60), 318, '중앙값 26.0', 'text-anchor="middle"'),
  t(scale(40, 60), 242, 'Q3 40.0', 'text-anchor="middle"'),
 ])
 source = (
  '<figure class="learn-chart learn-chart--wide learn-source-boxplot"><svg viewBox="0 0 480 360" role="img" aria-labelledby="source-box-title source-box-desc">'
  f'<title id="source-box-title">화면의 다섯 수치로 그린 상자그림</title><desc id="source-box-desc">최솟값 3.3, Q1 16.1, 중앙값 26.0, Q3 40.0, 최댓값 296.6입니다. 원자료가 없어 1.5배 IQR 수염 끝은 그리지 않았습니다.</desc>{full}</svg>'
  '<figcaption class="learn-chart__caption">캡처의 다섯 요약값으로 그린 그림입니다. 공통 30건이 아니며, 위 수염은 최댓값 296.6까지입니다. 75.85는 계산된 울타리이지 수염 끝이 아닙니다.</figcaption></figure>'
 )

 controls = lambda buttons, status: f'<div class="qn-controls" hidden><div class="qn-shortcuts">{buttons}</div><p role="status" id="{status}"></p></div>'
 sections = f'''
<section class="learn-chapter__step" id="quick-start" data-toc-label="서두 · 학습목표"><p class="learn-chapter__label">서두 · 학습목표</p><h2>평균과 중앙값만으로 거래가격의 분포를 이해할 수 있을까요?</h2>
<p>어느 지역의 토지 거래단가 중앙값이 100만원/㎡라고 해 보겠습니다. 그렇다면 대부분의 거래가 100만원/㎡ 부근에서 일어났을까요? 반드시 그렇지는 않습니다. 90~110만원/㎡에 모여 있을 수도 있고, 30만원/㎡부터 300만원/㎡까지 퍼져 있을 수도 있습니다. 중앙값이 같아도 분포는 다를 수 있습니다.</p>
<p>가운데 하나뿐 아니라 자료의 여러 위치를 보려면 <strong>분위수</strong>를 사용합니다. 분위수는 정렬한 자료에서 특정 누적 비율에 대응하는 값입니다. Q1·중앙값·Q3로 상자그림을 그릴 수 있습니다.</p>
<ul class="learn-objectives"><li>분위수와 백분위수의 의미를 이해합니다.</li><li>분위수와 백분위 순위를 구별합니다.</li><li>Q1·Q2·Q3와 IQR을 계산합니다.</li><li>상자·중앙선·수염·별도 점을 읽습니다.</li><li>울타리와 실제 수염 끝의 차이를 알아봅니다.</li><li>집단별 상자그림을 비교합니다.</li><li>계산법에 따라 분위수가 달라지는 이유를 이해합니다.</li><li>CH2 Macro의 25%값·중위·75%값을 읽습니다.</li></ul>
<p>먼저 <a href="/learn/stats/mean-and-median/#median">중앙값</a>과 <a href="/learn/stats/graphs/#shape">분포의 모양</a>을 떠올려 보세요.</p>
{controls('<button type="button" data-ratio="0.25">25%</button><button type="button" data-ratio="0.5" aria-pressed="true">50%</button><button type="button" data-ratio="0.75">75%</button>', 'qn-map-status')}
{f1}</section>
<section class="learn-chapter__step" id="percentiles" data-toc-label="분위수와 백분위 순위"><p class="learn-chapter__label">분위수와 백분위 순위</p><h2>비율로 값을 찾는 것과 값으로 순위를 찾는 것은 다릅니다</h2>
<p>4장에서 중앙값은 정렬한 자료의 가운데였습니다. 아래쪽 25%에 대응하는 값은 <strong>25백분위수</strong>, 75%에 대응하는 값은 <strong>75백분위수</strong>입니다. p분위수의 p는 0부터 1까지의 누적 비율입니다. p=0.25는 Q1, p=0.50은 중앙값, p=0.75는 Q3입니다.</p>
<p>75백분위수가 168만원/㎡라면, 정렬한 분포의 75% 위치에 대응하는 단가입니다. <strong>평균보다 75% 높은 단가라는 뜻이 아닙니다.</strong> 표본에서는 같은 값이 반복되거나 건수가 적어, 관측이 정확히 75대 25로 나뉘지 않을 수 있습니다.</p>
<p>「75백분위수는 얼마인가」와 「168만원/㎡는 어느 순위인가」는 다른 질문입니다. 뒤의 질문이 <strong>백분위 순위</strong>입니다.</p>
<div class="learn-data learn-data--full qn-table"><table><caption>100, 100, 100, 200에서 100의 위치</caption><thead><tr><th scope="col">기준</th><th scope="col">건수</th><th scope="col">비율</th></tr></thead><tbody><tr><th scope="row">100 미만</th><td>0</td><td>0%</td></tr><tr><th scope="row">100 이하</th><td>3</td><td>75%</td></tr></tbody></table></div>
<p>같은 값 100이라도 미만과 이하의 비율이 다릅니다. 동점의 중간 순위를 쓰는 방법도 있습니다. 분위수는 비율에서 값을 찾고, 백분위 순위는 값이 차지하는 위치를 찾습니다.</p></section>
<section class="learn-chapter__step" id="calculation" data-toc-label="사분위수 계산"><p class="learn-chapter__label">사분위수 계산</p><h2>정렬한 30건을 아래 15건과 위 15건으로 나눕니다</h2>
<p>Q1은 제1사분위수, Q2는 중앙값, Q3는 제3사분위수입니다. 이번 장의 기본 계산은 <strong>두 절반의 중앙값</strong>입니다. 자료는 1~4장과 같은 공통 학습자료 30건입니다. 출처와 표집 설계가 확인되지 않은 학습 예제이며, 번호는 거래 시점이 아닙니다. <a href="/learn/stats/graphs/#data">전체 표</a>와 <a href="../example-data.json">원자료</a>에서 확인할 수 있습니다.</p>
<p>관측 30건, 최솟값 62, 최댓값 480, 중앙값 122만원/㎡입니다. 30건은 짝수이므로 중앙값은 15번째 120과 16번째 124의 평균인 122입니다. 아래쪽 15건의 가운데인 8번째가 Q1=98입니다. 위쪽 15건의 가운데인 전체 23번째가 Q3=168입니다.</p>
{controls('<button type="button" data-step="all" aria-pressed="true">결과</button><button type="button" data-step="center">15·16번째</button><button type="button" data-step="lower">아래 15건</button><button type="button" data-step="q1">Q1</button><button type="button" data-step="upper">위 15건</button><button type="button" data-step="q3">Q3</button>', 'qn-rank-status')}
{f2}
<p>홀수 개이면 전체 중앙 관측을 두 절반에서 제외합니다. 98 이하인 관측은 8건입니다. 30의 25%인 7.5건이 아닙니다. Q1부터 Q3까지 양 끝을 포함하면 16건, 전체의 53.3%입니다. 사분위수는 누적 비율의 위치를 요약한 값입니다. 유한한 표본을 관측 건수로 언제나 정확히 네 등분하지는 않습니다. 상자가 가운데 50%를 나타낸다는 말은 위치의 요약으로 읽습니다.</p></section>
<section class="learn-chapter__step" id="iqr" data-toc-label="사분위범위"><p class="learn-chapter__label">사분위범위</p><h2>IQR은 가운데 부분의 퍼짐입니다</h2>
<p>IQR = Q3 − Q1 = 168 − 98 = <strong>70만원/㎡</strong>입니다. 전체 범위는 480 − 62 = 418만원/㎡입니다. 극단값의 크기에 평균이나 전체 범위보다 덜 민감할 수 있습니다. 다만 관측을 넣거나 빼면, 그리고 계산법이 바뀌면 IQR도 달라질 수 있습니다.</p>
<p>IQR이 작다는 것은 가운데 부분이 상대적으로 좁다는 뜻입니다. 모든 거래단가가 비슷하다는 뜻은 아닙니다. Q1에서 중앙값까지는 122 − 98 = 24이고, 중앙값에서 Q3까지는 168 − 122 = 46입니다. 상자 안의 중앙선이 상자의 정가운데에 있지 않습니다.</p></section>
<section class="learn-chapter__step" id="whiskers" data-toc-label="수염과 울타리"><p class="learn-chapter__label">수염과 울타리</p><h2>수염의 끝과 이상치 경계는 다를 수 있습니다</h2>
<p>상자그림은 Q1, 중앙값, Q3, 수염, 별도 점으로 분포를 요약합니다. 수염을 실제 최솟값과 최댓값까지 그리는 방법도 있고, 1.5×IQR 울타리 안의 실제 관측까지 그리는 방법도 있습니다. 이번 과정은 <strong>1.5×IQR</strong>을 기본으로 합니다.</p>
<p>1.5×70 = 105입니다. 아래 울타리 L = 98 − 105 = −7, 위 울타리 U = 168 + 105 = 273입니다. 수염은 −7과 273까지가 아니라, 울타리 안에 있는 실제 최솟값 62와 최댓값 268까지입니다. 480은 273을 넘으므로 별도 점입니다.</p>
{controls('<button type="button" data-rule="range">최솟값–최댓값</button><button type="button" data-rule="iqr" aria-pressed="true">1.5×IQR</button><button type="button" data-part="q1">Q1</button><button type="button" data-part="median">중앙값</button><button type="button" data-part="q3">Q3</button><button type="button" data-part="iqr">IQR</button><button type="button" data-part="fence-low">아래 울타리</button><button type="button" data-part="fence-high" aria-pressed="true">위 울타리</button><button type="button" data-part="whisker-low">아래 수염</button><button type="button" data-part="whisker-high">위 수염</button><button type="button" data-part="outlier">별도 점</button>', 'qn-whisker-status')}
{f3}
<p>−7은 음수 단가가 관측되었다는 뜻이 아닙니다. Q1과 IQR로 계산한 경계입니다. 273도 그 단가의 거래가 있다는 뜻이 아닙니다. 480이 울타리 밖에 있다고 입력 오류나 삭제할 거래로 확정되지는 않습니다. 면적, 금액과 단가의 산식, 거래 유형, 용도지역, 이용상황, 중복·정정, 비교 범위를 확인합니다. 상자그림은 확인할 관측을 찾는 도구입니다. 처리는 <a href="/learn/stats/iqr-outliers/">7장 「이상치와 IQR」</a>에서 다룹니다.</p></section>
<section class="learn-chapter__step" id="comparison" data-toc-label="집단별 상자그림"><p class="learn-chapter__label">집단별 상자그림</p><h2>집단을 나누면 사분위수도 다시 계산합니다</h2>
<p>주거와 상업은 각각 15건입니다. 전체 30건의 Q1=98과 Q3=168을 두 집단에 그대로 쓰지 않습니다. 15건의 중앙값은 8번째입니다. Q1은 가운데를 뺀 아래 7건의 중앙값, Q3는 위 7건의 중앙값입니다.</p>
<div class="learn-data learn-data--full qn-table"><table><caption>공통 학습자료의 집단별 사분위수</caption><thead><tr><th scope="col">항목</th><th scope="col">주거 15건</th><th scope="col">상업 15건</th></tr></thead><tbody><tr><th scope="row">Q1</th><td>88</td><td>124</td></tr><tr><th scope="row">중앙값</th><td>105</td><td>168</td></tr><tr><th scope="row">Q3</th><td>120</td><td>235</td></tr><tr><th scope="row">IQR</th><td>32</td><td>111</td></tr></tbody></table></div>
{controls('<button type="button" data-group="주거" aria-pressed="true">주거</button><button type="button" data-group="상업">상업</button>', 'qn-group-status')}
{f4}
<p>이 예제에서는 상업의 중앙값과 IQR이 더 큽니다. 모든 주거·상업 시장에 적용되는 결과도 아니고, 용도가 가격 차이의 원인으로 확인된 것도 아닙니다. 면적, 입지, 시점이 다를 수 있습니다. 두 상자는 같은 축에 있습니다. 표본은 각 15건입니다.</p>
<p>비교할 때는 단위와 축, 계산법, 건수를 맞춥니다. 상자가 겹친다고 통계적 유의성이 정해지지는 않습니다. 상자는 신뢰구간이 아닙니다. 두 봉우리나 빈 구간은 상자그림에 숨겨질 수 있으므로, 차이가 중요하면 히스토그램이나 개별 점도 함께 봅니다.</p></section>
<section class="learn-chapter__step" id="methods" data-toc-label="계산 관례"><p class="learn-chapter__label">계산 관례</p><h2>같은 30건도 계산법에 따라 후보가 달라질 수 있습니다</h2>
<p>다른 프로그램에서 Q1=99, 중앙값=122, Q3=166이 나왔다고 해서 어느 한쪽이 반드시 틀린 것은 아닙니다. 표본 분위수의 계산법은 하나가 아닙니다. Type 7은 h = 1 + (n − 1)p를 사용합니다. n=30, p=0.25이면 h=8.25이므로 Q1 = 98 + 0.25×(102 − 98) = 99입니다. p=0.75이면 h=22.75이므로 Q3 = 160 + 0.75×(168 − 160) = 166입니다. IQR은 67입니다.</p>
{controls('<button type="button" data-method="halves" aria-pressed="true">두 절반 방식</button><button type="button" data-method="type7">Type 7</button>', 'qn-method-status')}
{f5}
<div class="learn-data learn-data--full qn-table"><table><caption>같은 30건의 위쪽 경계</caption><thead><tr><th scope="col">구분</th><th scope="col">두 절반 방식</th><th scope="col">Type 7</th></tr></thead><tbody><tr><th scope="row">Q1 / Q3</th><td>98 / 168</td><td>99 / 166</td></tr><tr><th scope="row">IQR</th><td>70</td><td>67</td></tr><tr><th scope="row">위 울타리</th><td>273</td><td>266.5</td></tr><tr><th scope="row">위 수염</th><td>268</td><td>240</td></tr><tr><th scope="row">울타리 밖</th><td>480</td><td>268, 480</td></tr></tbody></table></div>
<p>Type 7의 위 수염은 266.5가 아닙니다. 266.5 이하인 실제 최댓값은 240입니다. 268은 두 절반 방식에서는 울타리 안이고, Type 7에서는 울타리 밖입니다. 이상치 기준을 설명할 때는 IQR 배수와 분위수 계산법을 함께 적습니다. 후보를 뺄지는 별도의 판단입니다.</p>
<p>모든 프로그램이 Type 7을 기본으로 쓰지는 않습니다. 원자료, 정렬, 결측, 가중치, 분위수 함수, 상자그림 함수, IQR 배수, 경계와 같은 값의 처리가 같은지 확인합니다. 이번 학습 예제의 기본은 두 절반 방식입니다. 교재의 계산법을 실제 Macro에 그대로 적용하지는 않습니다.</p>
<details class="learn-more"><summary>가중 분위수와 적은 표본</summary><div class="learn-more__body"><p>거래 한 건을 같게 보면 거래 건수 기준 분위수입니다. 면적에 비중을 두면 면적가중 분위수가 되지만, 가중치와 보간 규칙을 정해야 합니다. 100건의 중간 거래 단가와, 누적 면적 50%에 대응하는 단가는 다른 질문입니다. 이번 30건은 거래별 동일 비중입니다.</p>
<p>단가 50, 80, 100, 150, 300의 중앙값은 100입니다. 300을 빼면 (80+100)/2 = 90입니다. 건수가 적으면 분위수가 크게 움직일 수 있습니다. 건수가 많다고 대표성이 보장되지는 않습니다. 건수, 계산법, 극단값, 기간·지역·유형, 결측과 이상치 처리를 함께 봅니다.</p></div></details></section>
<section class="learn-chapter__step" id="practice" data-toc-label="확인 문제"><p class="learn-chapter__label">확인 문제</p><h2>위치값·울타리·수염을 구별해 보세요</h2>
<ol class="learn-exercises"><li>Q1=98이고 Q3=168이라면 IQR과 위쪽 1.5×IQR 울타리는 얼마일까요?<details><summary>답과 해설</summary><p>IQR은 70, 위 울타리는 168+105=273입니다. 수염은 273까지가 아니라 울타리 안의 최댓값 268까지입니다.</p></details></li>
<li>75백분위수가 168만원/㎡라면 평균보다 75% 높은 단가일까요?<details><summary>답과 해설</summary><p>아닙니다. 75는 정렬한 분포의 누적 비율이고, 168은 그 위치의 단가입니다.</p></details></li>
<li>같은 30건인데 어떤 프로그램은 Q1=98·Q3=168, 다른 프로그램은 Q1=99·Q3=166입니다. 반드시 한쪽이 틀렸을까요?<details><summary>답과 해설</summary><p>그렇지 않습니다. 두 절반 방식과 Type 7은 규칙이 다릅니다. 원자료와 계산 옵션을 함께 확인합니다.</p></details></li>
<li>수염 밖에 480만원/㎡가 표시되었습니다. 분석에서 자동으로 제외할까요?<details><summary>답과 해설</summary><p>아닙니다. 울타리 규칙에 따라 별도로 표시한 관측입니다. 유효성과 비교 가능성을 확인한 뒤 처리합니다.</p></details></li>
<li>읍면동 두 곳의 중위단가가 100과 200입니다. 시군구 중위를 150으로 계산해도 될까요?<details><summary>답과 해설</summary><p>일반적으로 적절하지 않습니다. 집단별 중앙값만으로는 전체의 가운데 위치를 알 수 없습니다. 거래를 합쳐 다시 계산합니다.</p></details></li></ol></section>
<section class="learn-chapter__step" id="macro" data-toc-label="CH2 Macro에서 읽기"><p class="learn-chapter__label">CH2 Macro에서 읽기</p><h2>25%값·중위·75%값을 함께 읽어 보세요</h2>
<p>토지 기본통계에서는 지역, 기간, 용도지역, 지목으로 나눈 거래단가의 요약값을 볼 수 있습니다. 아래는 자녹과 답이 만나는 칸의 과거 화면입니다.</p>
<div class="learn-quantile-pair"><figure class="learn-capture learn-capture--detail"><a href="../assets/captures/land-quantile-cell.png" target="_blank" rel="noopener" aria-label="분위수 화면 크게 보기"><img src="../assets/captures/land-quantile-cell.png" width="251" height="180" loading="lazy" alt="자녹과 답의 교차 칸. 오른쪽 열은 위에서부터 최솟값 3.3, 25%값 16.1, 중앙값 26.0, 75%값 40.0, 최댓값 296.6입니다. 칸의 평균은 33.2입니다."/></a><figcaption class="learn-capture__caption">자녹·답 칸입니다. 오른쪽 열은 3.3, 16.1, 26.0, 40.0, 296.6만원/㎡입니다. 33.2는 그 칸의 평균입니다. 캡처 당시의 값이며 공통 30건이나 현재 운영 통계가 아닙니다. <a href="../assets/captures/land-quantile-cell.png" target="_blank" rel="noopener">원본 크게 보기 ↗</a></figcaption></figure>{source}</div>
<ol class="learn-screen-reading"><li><strong>25%값:</strong> 아래쪽 25% 위치의 단가입니다. 최저 적정가격이나 자동 저평가 기준이 아닙니다.</li><li><strong>중위값:</strong> 정렬한 가운데입니다. 극단값의 크기에 평균보다 덜 민감할 수 있지만, 시장 전체의 유일한 대표가격은 아닙니다.</li><li><strong>75%값:</strong> 아래쪽 75% 위치의 단가입니다. 개별 물건의 고평가 기준이 아닙니다.</li><li><strong>IQR:</strong> 75%값에서 25%값을 뺀 값입니다. 같은 산식과 같은 표본인지 확인합니다. 이 칸은 40.0−16.1=23.9입니다.</li><li><strong>건수와 필터:</strong> 용도지역, 지목, 기간, 이상치 제외에 따라 구성이 바뀝니다.</li><li><strong>계산법:</strong> 확인한 기본통계의 25%·75%는 거래단가 목록의 백분위입니다. 이번 장의 두 절반 방식과 같지 않습니다. 같은 30건이면 99와 166입니다. 이상치를 나누는 계산도 그 백분위를 사용합니다. 배수는 1.5만 있는 것이 아니며 화면에서 고를 수 있습니다.</li><li><strong>지역을 합칠 때:</strong> 읍면동 25%값을 평균해도 시군구 25%값이 되지 않습니다. 그 범위의 거래를 모아 다시 계산합니다.</li></ol>
<p>기본통계의 분위수는 선택한 거래의 가격 분포를 읽는 지표입니다. 개별 부동산의 적정가격을 자동으로 판정하지 않습니다.</p>
<p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 기본통계 열기 →</a></p></section>
<section class="learn-chapter__step" id="recap" data-toc-label="결론 · 학습 요약"><p class="learn-chapter__label">결론 · 학습 요약</p><h2>분위수는 가격의 위치를, IQR은 가운데 부분의 퍼짐을 보여 줍니다</h2>
<ul class="learn-recap-list"><li><strong>분위수:</strong> 정렬한 자료의 누적 비율에 대응하는 값입니다.</li><li><strong>백분위 순위:</strong> 특정 값이 차지하는 위치입니다.</li><li><strong>Q1·Q2·Q3:</strong> 25%·50%·75% 위치입니다. Q2는 중앙값입니다.</li><li><strong>IQR:</strong> Q3−Q1입니다.</li><li><strong>울타리와 수염:</strong> 울타리는 계산된 경계이고, 수염은 그 안의 실제 관측까지입니다.</li><li><strong>계산법:</strong> 같은 자료라도 Q1·Q3·후보가 달라질 수 있습니다.</li></ul>
<p>다음 <a href="/learn/stats/spread/">6장 「분산과 표준편차」</a>에서는 각 값이 평균에서 얼마나 떨어져 있는지로 퍼짐을 측정합니다.</p>
<p>분위수를 읽을 때는 위치뿐 아니라 계산 규칙과 표본의 구성도 함께 확인하세요.</p>
<details class="learn-more"><summary>참고자료</summary><div class="learn-more__body"><ul><li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/boxplot.htm">NIST/SEMATECH e-Handbook: Box Plot</a></li><li><a href="https://stat.ethz.ch/R-manual/R-devel/library/stats/html/quantile.html">R 공식 문서: Sample Quantiles</a> — Type 7을 포함한 계산 관례.</li></ul>
<p class="learn-source-note">참고자료 확인일: 2026-10-07. 그림 1은 개념도이고 그림 2~5는 공통 학습자료입니다. 실제 서비스의 분위수 산식은 화면의 함수를 따로 확인합니다.</p></div></details></section>
'''
 page = f'''<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>05. 분위수와 상자그림 | 통계학 &amp; 데이터 분석</title>
    <meta name="description" content="분위수, 사분위수, IQR, 상자그림의 수염과 울타리, 집단 비교와 계산 관례를 공통 학습자료로 설명합니다." />
    <link rel="canonical" href="https://ch2data.com/learn/stats/quantiles/" />
    <script src="/learn/stats/learn-stats-theme.js?v=20261023-1"></script>
    <link rel="stylesheet" href="/style.css" />
    <link rel="stylesheet" href="/learn/stats/learn-stats.css?v=20261023-1" />
    <link rel="stylesheet" href="/learn/stats/learn-reader.css?v=20261026-toc" />
    <link rel="stylesheet" href="/learn/stats/quantiles/chapter.css?v=20261026-10" />
  </head>
  <body>
    <div class="page">
      <header class="hero hero--document">
        <p class="learn-breadcrumb"><a href="https://ch2data.com/">CH2 DATA</a> · <a href="/learn/stats/">통계학 &amp; 데이터 분석</a></p>
        <p class="hero__eyebrow">I. 데이터와 기술통계</p>
        <h1 class="hero__title">05. 분위수와 상자그림</h1>
        <p class="learn-chapter-relevance">Macro 활용도 <span class="learn-relevance" aria-label="Macro 활용도 3단계, 핵심"><span aria-hidden="true">★★★</span></span></p>
        <p class="learn-relevance-guide">Macro 활용도: ★★★ 핵심 · ★★☆ 권장 · ★☆☆ 심화<br>별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.</p>
      </header>
      <article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="분위수와 상자그림">{sections}</article>
      <nav class="learn-chapter-nav" aria-label="장 이동">
        <a href="/learn/stats/mean-and-median/">← 04. 평균과 중앙값</a>
        <a href="/learn/stats/spread/">06. 분산과 표준편차 →</a>
      </nav>
      <footer class="footer"><nav class="footer__links"><a href="https://ch2data.com/">홈</a><a href="/learn/stats/">통계학 &amp; 데이터 분석</a></nav><p>© CH2 DATA</p></footer>
    </div>
    <script src="/learn/stats/learn-stats-toc.js?v=20261026-10" defer></script>
    <script type="application/json" id="qn-data">{json.dumps({'rows': [{'id': row['id'], 'group': row['group'], 'price': row['price']} for row in rows]}, ensure_ascii=False)}</script>
    <script type="module" src="/learn/stats/quantiles/experiment.js?v=20261026-10"></script>
  </body>
</html>
'''
 charts = [ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>', page, re.S)]
 assert len(charts) == 6
 for svg in charts:
  for node in svg.iter('rect'):
   label = node.attrib.get('data-box')
   if not label:
    continue
   group = groups[label] if label in groups else prices
   q1, q2, q3, lo, hi, _out = summary(group)
   if label == 'range':
    lo, hi = min(group), max(group)
   assert [float(node.attrib[key]) for key in ('data-q1', 'data-q2', 'data-q3', 'data-low', 'data-high')] == [q1, q2, q3, lo, hi]
   assert float(node.attrib['x']) == 60 + q1 and float(node.attrib['width']) == q3 - q1
 ids = re.findall(r'id="([^"]+)"', page)
 assert len(ids) == len(set(ids))
 assert page.count('<details') == 7
 assert '★★☆ 권장' in page and '★☆☆ 심화' in page and '3단계, 핵심' in page
 assert 'land-quantile-cell.png' in page and '[그림 ' not in page
 (ROOT / 'quantiles' / 'index.html').write_text(page, encoding='utf-8')
 promote()
 home = summary(groups['주거'])
 shop = summary(groups['상업'])
 print('groups', home, shop)
 print('type7 whisker', min(inside7), max(inside7), 'out', [value for value in ordered if value > upper7 or value < lower7])

def promote():
 old = '''        "slug": "quantiles",
        "title": "분위수와 상자그림",
        "soon": false,
        "macro_relevance": 2'''
 new = old.replace('"macro_relevance": 2', '"macro_relevance": 3')
 for path in (ROOT / 'course.json', ROOT / 'learn-stats-toc.js'):
  text = path.read_text(encoding='utf-8')
  if old not in text:
   if new not in text:
    raise SystemExit(f'missing quantiles block: {path}')
   continue
  path.write_text(text.replace(old, new, 1), encoding='utf-8')
 listing = ROOT / 'index.html'
 text = listing.read_text(encoding='utf-8')
 before = 'data-macro-relevance="2"><a href="/learn/stats/quantiles/">05. 분위수와 상자그림 <span class="learn-relevance" aria-label="Macro 활용도 2단계, 권장"><span aria-hidden="true">★★☆</span>'
 after = 'data-macro-relevance="3"><a href="/learn/stats/quantiles/">05. 분위수와 상자그림 <span class="learn-relevance" aria-label="Macro 활용도 3단계, 핵심"><span aria-hidden="true">★★★</span>'
 if before in text:
  listing.write_text(text.replace(before, after, 1), encoding='utf-8')
 elif after not in text:
  raise SystemExit('missing quantiles listing')

if __name__ == '__main__':
 build()
