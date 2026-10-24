"""Generate chapter 16: association, nonlinear patterns and causal limits."""
from pathlib import Path
from statistics import mean
from html import escape
import json,math,re
from scipy.stats import pearsonr,spearmanr
ROOT=Path(__file__).resolve().parent

def corr(x,y):
 xm,ym=mean(x),mean(y);return sum((a-xm)*(b-ym) for a,b in zip(x,y))/math.sqrt(sum((a-xm)**2 for a in x)*sum((b-ym)**2 for b in y))


def macro_case():
 return '''<p>Macro Insight의 「부동산 유형별 상관관계」에서는 최근 3년 동안 전국 시·군·구의 유형별 거래 규모를 비교합니다. 아래는 사용자가 제공한 상가·아파트 화면입니다. 앞의 공통 학습 자료 30건과는 관측 단위가 다릅니다.</p>
<figure class="co-macro-case"><a href="macro-insight-correlation.png" target="_blank" rel="noopener"><img src="macro-insight-correlation.png" width="800" height="642" loading="lazy" alt="Macro Insight 상가와 아파트 사례. 원래 상관 +0.92, 인구 보정 +0.54, 원래 유효 지역 수 n=266. 가로축은 상가 로그 거래액, 세로축은 아파트 로그 거래액이며 지역별 점이 우상향합니다."></a><figcaption>Macro Insight 실제 화면 캡처 · 상가 × 아파트. +0.92·+0.54·n=266은 캡처 당시의 표시값입니다. 기준월은 이미지에 포함되어 있지 않으며 현재 조회값을 보장하지 않습니다. 이미지를 선택하면 원본 크기로 볼 수 있습니다.</figcaption></figure>
<p>점 하나는 개별 거래가 아니라 하나의 시·군·구를 나타냅니다. 가로축은 상가의 로그 거래액, 세로축은 아파트의 로그 거래액입니다. 이 산점도와 노란 추세선은 인구 보정 전의 로그 거래액 관계입니다. 인구 보정 후 잔차 산점도가 아닙니다.</p>
<p class="co-formula">화면의 원래 Pearson r = +0.92 → 로그 인구를 보정한 상관 = +0.54</p>
<p>원래 상관은 같은 시·군·구에서 두 유형의 거래 규모가 함께 큰 경향을 보여 줍니다. 인구를 보정하면 양의 관계가 약해지지만 남아 있습니다. 인구 외의 공통 요인이나 지역 구성의 영향도 남을 수 있으므로, 상가 거래가 아파트 거래를 늘린다는 인과효과로 해석할 수는 없습니다.</p>
<details class="learn-more"><summary>실제 구현의 계산 방식과 유효 표본수</summary><div class="learn-more__body">
<p>이 화면은 전국 시·군·구와 최근 3년의 집계 자료를 사용합니다. 기준월과 지역 코드 정리 기준이 적용되며, 개별 토지 화면의 지역·용도·지목 필터를 그대로 이어받는 분석은 아닙니다. 비교할 유형 쌍을 바꾸면 계산에 쓰는 지역도 달라질 수 있습니다.</p>
<p>두 유형의 거래액이 모두 양수인 지역만 사용해 각각 자연로그로 변환하고 Pearson 상관을 구합니다. 원자료에서 누락된 유형의 거래액은 0으로 읽힌 뒤 이 양수 조건에서 제외됩니다. 인구 보정에는 여기에 양수인 인구가 있는 지역만 사용합니다. 각 로그 거래액을 절편과 로그 인구에 선형 회귀한 뒤, 두 잔차 사이의 Pearson 상관을 계산합니다. 거래액을 인구로 단순히 나누는 방법과 다릅니다.</p>
<p>API는 유형 쌍별 원래 유효 지역 수 n과 인구 보정 유효 지역 수 n_pop을 별도로 반환합니다. 첨부 화면의 n=266은 원래 상관의 유효 지역 수이며, 인구 보정의 n_pop은 현재 카드에 따로 표시되지 않습니다. 두 표본수가 같다고 단정할 수 없습니다. 캡처만으로 +0.92와 +0.54의 원자료 재계산이나 같은 표본 여부를 확인할 수는 없습니다.</p>
<p>확인한 Insight 화면은 Pearson 상관과 인구 보정 상관을 제공합니다. Spearman, 상관의 p값·신뢰구간은 이 화면에서 제공하지 않습니다. 백엔드는 계수를 소수 넷째 자리로 반올림하고 화면은 둘째 자리까지 표시합니다.</p>
<p>인구 보정 상관은 회귀계수나 표준화 회귀계수가 아닙니다. 노란 선은 표시된 로그 좌표의 선형 추세입니다. 어느 쪽도 개별 물건의 적정가격이나 인과효과를 산출하지 않습니다. 지역 단위의 관계를 개별 거래의 관계로 옮겨 해석하지 않도록 주의하세요.</p></div></details>
<p>토지 면적과 거래단가를 비교하는 경우에는 단가가 거래금액을 면적으로 나눈 값이라는 구조도 확인해야 합니다. 거래총액·유형·시점과 자료 범위를 함께 살펴보고, 면적과 단가의 음의 상관을 가격 할인 효과로 바로 해석하지 마세요.</p>
<p class="learn-macro-cta"><a href="https://macro.ch2data.com/insight/?q=3">Macro Insight 유형별 상관관계 열기 →</a></p><p><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 통계 열기 →</a></p>'''

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];x=[r['area'] for r in rows];y=[r['price'] for r in rows];r=corr(x,y);rho=float(spearmanr(x,y).statistic);without=[v for v in rows if v['id']!=7];rwithout=corr([v['area'] for v in without],[v['price'] for v in without]);floor=corr([v['floor'] for v in rows],y)
 curved=[(i,i*i) for i in range(-3,4)];mixA=[(1,8),(2,9),(3,10)];mixB=[(7,2),(8,3),(9,4)];mix=mixA+mixB;mixr=corr([v[0] for v in mix],[v[1] for v in mix])
 result={'description':'공통 학습 자료 및 별도 가상 관계 예제. 인과효과가 아님.','pearson_area_price':r,'spearman_area_price':rho,'pearson_floor_price':floor,'without_id7':rwithout,'curved':curved,'mixture':{'A':mixA,'B':mixB,'overall_r':mixr}}
 (ROOT/'correlation-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def t(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def line(x,y,xx,yy,c='#64748b',extra=''):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{c}" {extra}/>'
 def fig(id,title,b,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=t(24,28,f'면적과 거래단가 · Pearson r={r:.3f} · n=30','id="co-scatter-heading"')+line(70,320,580,320)+line(70,55,70,320)
 for row in rows:
  cx=70+row['area']*1.5;cy=320-row['price']*.5;b+=f'<circle cx="{cx}" cy="{cy}" r="4" fill="{"#2563eb" if row["group"]=="주거" else "#d97706"}" data-id="{row["id"]}"><title>{row["id"]}번 · {row["group"]} · 면적 {row["area"]}㎡ · 단가 {row["price"]}만원/㎡</title></circle>'
  if row['id']==7:b+=t(cx+10,cy,'7번 480','id="co-id7-label"')
 for v in [0,100,200,300]:b+=t(70+v*1.5,345,v,'text-anchor="middle"')
 for v in [0,100,200,300,400,500]:b+=t(58,325-v*.5,v,'text-anchor="end"')
 b+=t(400,374,'면적(㎡)')+t(24,52,'단가(만원/㎡)')+t(24,405,'파랑: 주거 / 주황: 상업 · 각 점은 거래 한 건')
 f1=fig('scatter','공통 자료의 면적과 단가',b,'그림 1. 공통 학습 자료 30건의 산점도입니다. 면적이 큰 쪽에서 단가가 낮은 경향이 있지만, 유형과 조건을 통제한 효과가 아닙니다.',431)
 controls='<div class="co-controls" hidden><p id="co-scatter-stats" role="status" aria-live="polite"></p><label><input type="checkbox" id="co-exclude"> 7번 관측값을 제외해 비교 (30건 → 29건)</label><label for="co-observation">관측값 확인</label><select id="co-observation"><option value="">관측값 선택</option>'+''.join(f'<option value="{row["id"]}">{row["id"]}번 · {row["group"]}</option>' for row in rows)+'</select><p id="co-observation-status" role="status" aria-live="polite">점을 가리키거나 관측값을 선택하면 면적·단가·유형을 확인할 수 있습니다.</p><p class="learn-source-note">두 계수는 같은 원래 좌표에서 계산합니다. 순위 산점도가 아닙니다. 7번 제외는 민감도를 확인하는 예시이며 삭제 권장이 아닙니다.</p></div>'
 f1=f1.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="co-scatter">').replace('<svg',controls+'<script type="application/json" id="co-rows">'+json.dumps(rows,ensure_ascii=False)+'</script><svg',1)
 f1=f1.replace('<svg ', '<svg class="co-scatter-svg" ',1)
 b=t(24,28,'r=0이어도 뚜렷한 곡선 관계가 있을 수 있습니다')+line(80,285,560,285)+line(320,60,320,285)
 b+='<polyline points="'+' '.join(f'{320+xx*65},{285-xx*xx*22}' for xx in [i/20 for i in range(-60,61)])+'" fill="none" stroke="#2563eb" stroke-dasharray="4 4" data-curve="x-squared"/>'
 for xx,yy in curved:b+=f'<circle cx="{320+xx*65}" cy="{285-yy*22}" r="6" fill="#2563eb" data-x="{xx}" data-y="{yy}"/>'
 for v in range(-3,4):b+=t(320+v*65,311,v,'text-anchor="middle"')
 for v in [0,3,6,9]:b+=t(65,290-v*22,v,'text-anchor="end"')
 b+=t(535,311,'X')+t(24,57,'Y')
 b+=t(24,345,'가상 자료 Y=X² / X=−3,−2,−1,0,1,2,3')+t(24,375,'Pearson r=0 · 선형 상관이 없다는 뜻')
 f2=fig('nonlinear','상관 0과 비선형 관계',b,'그림 2. 별도 가상 예제입니다. Y는 X로 완전히 정해지지만 대칭적인 U자 관계여서 Pearson 상관은 0입니다. 축은 단위 없는 가상 변수입니다.',403)
 def fit(points):
  xx,yy=zip(*points);xm,ym=mean(xx),mean(yy);slope=sum((a-xm)*(b-ym) for a,b in points)/sum((a-xm)**2 for a in xx);return ym-slope*xm,slope
 b=t(24,28,f'전체 6개 관측값 · Pearson r={mixr:.3f}','id="co-mix-heading"')+line(70,320,570,320)+line(70,60,70,320)
 for label,pts,color in [('overall',mix,'#0f766e'),('A',mixA,'#2563eb'),('B',mixB,'#d97706')]:
  intercept,slope=fit(pts);lo=min(v[0] for v in pts);hi=max(v[0] for v in pts)
  b+=line(70+lo*48,320-(intercept+slope*lo)*23,70+hi*48,320-(intercept+slope*hi)*23,color,f'stroke-width="3" data-trend="{label}" '+('stroke-dasharray="6 4"' if label=='overall' else 'hidden=""'))
 for label,pts in [('A',mixA),('B',mixB)]:
  for xx,yy in pts:b+=f'<circle cx="{70+xx*48}" cy="{320-yy*23}" r="6" fill="#2563eb" data-group="{label}" data-x="{xx}" data-y="{yy}"><title>{label}: ({xx}, {yy})</title></circle>'
 for v in [0,2,4,6,8,10]:b+=t(70+v*48,346,v,'text-anchor="middle"')+t(57,325-v*23,v,'text-anchor="end"')
 b+=t(555,370,'X')+t(24,57,'Y')+t(24,395,'점: 전체 자료 · 청록 점선: 전체의 선형 추세','id="co-mix-legend"')
 f3=fig('mixture','전체와 집단별 관계 비교 (단위 없는 가상 X·Y)',b,'그림 3. A=(1,8)·(2,9)·(3,10), B=(7,2)·(8,3)·(9,4)인 가상 자료입니다. 전체 6점의 상관과 선형 추세를 표시합니다. 추세선은 인과효과가 아닙니다.',425)
 controls='''<div class="co-controls" hidden><label for="co-mode">집단 혼합 실험</label><select id="co-mode"><option value="overall">전체 관계 보기</option><option value="groups">집단별 관계 보기</option><option value="both">전체와 집단별 함께 보기</option></select><p id="co-mix-status" role="status" aria-live="polite"></p><p class="learn-source-note">관측값은 여섯 개로 고정됩니다. 보기만 바꾸며, 전체와 부분 집단은 서로 다른 질문에 답합니다. 집단을 나누면 반드시 더 정확해지는 것은 아닙니다.</p></div>'''
 f3=f3.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="co-mixture">').replace('<svg',controls+'<script type="application/json" id="co-mixture-data">'+json.dumps({'A':mixA,'B':mixB})+'</script><svg',1)
 f3=f3.replace('<svg ', '<svg class="co-mixture-svg" ',1)
 b=t(24,28,'X: 공부 시간 · Y: 시험 점수 · Z: 학습 의욕')
 for i,(label,nodes,explanation) in enumerate([('직접 영향 가설','X → Y','공부 시간이 늘면서 시험 점수가 높아질 수 있습니다.'),('역방향 가설','Y → X','높은 점수로 공부에 흥미가 생겨 시간이 늘 수 있습니다.'),('공통 원인 가설','Z → X / Z → Y','학습 의욕이 공부 시간과 점수 모두에 영향을 줄 수 있습니다.')]):
  yy=85+i*100;b+=t(24,yy,label)+t(300,yy,nodes)+t(24,yy+32,explanation)
 b+=t(24,365,'가능한 설명을 구분하는 개념도 · 실제 자료로 검증한 인과모형이 아닙니다')
 f4=fig('causes','공부 시간·시험 점수의 인과 방향과 학습 의욕의 공통 영향',b,'그림 4. X→Y, Y→X, Z→X와 Z→Y를 구별합니다. 관찰된 상관만으로 어느 구조인지 결정할 수 없습니다.',395)
 page=ROOT/'correlation/index.html';old=page.read_text(encoding='utf-8')
 references=re.search(r'<details class="learn-more"><summary>참고자료</summary>.*?</details>',old,re.S)[0]
 parts=[];source=(ROOT/'correlation/content.md').read_text(encoding='utf-8').replace('\\*','*').replace('**','').replace('\\~','~')
 ids=['quick-start','scatter','pearson','nonlinear','spearman','sensitivity','mixture','causality','inference','practice','macro','recap']
 def inline(value):return re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',escape(value))
 def render(block):
  out=[];lines=block.strip().split('\n');i=0
  while i<len(lines):
   line=lines[i].strip()
   if not line or line=='---':i+=1;continue
   if line.startswith('[그림 '):out.append({1:f1,2:f2,3:f3,4:f4}[int(re.search(r'그림 (\d)',line)[1])]);i+=1;continue
   if line=='[CH2 Macro 토지 통계 열기 →]':out.append('<p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 통계 열기 →</a></p>');i+=1;continue
   if line=='▶ 참고자료':out.append(references);i+=1;continue
   if line.startswith('▶ '):
    title=line[2:];rest=[];i+=1
    while i<len(lines) and lines[i].strip()!='---':rest.append(lines[i]);i+=1
    out.append('<details class="learn-more"><summary>'+inline(title)+'</summary><div class="learn-more__body">'+render('\n'.join(rest))+'</div></details>');continue
   if line.startswith('|'):
    table=[]
    while i<len(lines) and lines[i].strip().startswith('|'):
     cells=[c.strip() for c in lines[i].strip().strip('|').split('|')]
     if not all(re.fullmatch(r'[:\- ]+',c) for c in cells):table.append(cells)
     i+=1
    out.append('<div class="learn-data learn-data--full"><table><thead><tr>'+''.join('<th scope="col">'+inline(c)+'</th>' for c in table[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join(('<th scope="row">'+inline(c)+'</th>') if j==0 else '<td>'+inline(c)+'</td>' for j,c in enumerate(row))+'</tr>' for row in table[1:])+'</tbody></table></div>');continue
   if line.startswith('- ') or re.match(r'\d+\. ',line):
    ordered=not line.startswith('- ');tag='ol' if ordered else 'ul';items=[]
    while i<len(lines) and (re.match(r'\d+\. ',lines[i]) if ordered else lines[i].startswith('- ')):
     items.append('<li>'+inline(re.sub(r'^(?:- |\d+\. )','',lines[i]))+'</li>');i+=1
    out.append('<'+tag+'>'+''.join(items)+'</'+tag+'>');continue
   formula=line.startswith(('r =','t =','Y =','r(X,Y)='))
   out.append('<p'+(' class="co-formula"' if formula else '')+'>'+inline(line)+'</p>');i+=1
  return '\n'.join(out)
 for id,section in zip(ids,re.split(r'^## ',source,flags=re.M)[1:],strict=True):
  label,body=section.split('\n',1);heading=re.search(r'^### (.+)$',body,re.M)[1];body=re.sub(r'^### .+\n','',body,count=1,flags=re.M)
  if id=='practice':
   items=[]
   for q in re.split(r'^\d+\. ',body,flags=re.M)[1:]:
    question,answer=q.split('▶ 답과 해설',1);items.append('<li>'+inline(question.strip())+'<details><summary>답과 해설</summary><div class="learn-more__body">'+render(answer)+'</div></details></li>')
   html='<ol class="learn-exercises">'+''.join(items)+'</ol>'
  else:html=render(body)
  if id=='quick-start':html=html.replace('<ul>','<ul class="learn-objectives">',1)+'<p class="learn-source-note"><a href="/learn/stats/graphs/">3장의 산점도</a> · <a href="/learn/stats/graphs/#data">공통 학습 자료 30건</a> · <a href="../correlation-example.json">계산 결과 JSON</a></p>'
  if id=='sensitivity':html+='<p class="learn-source-note">7번은 행 위치가 아닌 원자료의 id=7입니다. 상업, 면적 22㎡, 단가 480만원/㎡인 한 건만 제외합니다. 전체는 유효한 면적·단가 쌍 30건, 제외 후에는 29건입니다. 층·단가도 유효한 쌍 30건입니다.</p>'
  if id=='macro':html=macro_case()
  if id=='recap':html=html.replace('17장 「단순선형회귀와 최소제곱법」','<a href="/learn/stats/regression/">17장 「단순선형회귀와 최소제곱법」</a>')
  parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{heading if id!="macro" else "Macro Insight의 상가·아파트 상관을 읽어 보세요"}</h2>{html}</section>')
 p=ROOT/'correlation/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="상관관계와 인과관계">\n'+'\n'.join(parts)+'\n</article>',html,count=1,flags=re.S)
 html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1상관계수와 산점도, 비선형·집단 혼합의 영향, 인과관계의 차이를 예제와 그림으로 설명합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);
 html=html.replace('별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.','활용도는 CH2 Macro의 분석 결과를 이해하는 데 얼마나 도움이 되는지를 나타냅니다.')
 if 'correlation/chapter.css' not in html:html=html.replace('</head>','<link rel="stylesheet" href="/learn/stats/correlation/chapter.css?v=20261024-1" />\n</head>')
 if 'correlation/experiment.js' not in html:html=html.replace('</body>','<script type="module" src="/learn/stats/correlation/experiment.js?v=20261024-1"></script>\n</body>')
 p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
