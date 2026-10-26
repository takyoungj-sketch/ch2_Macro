"""Generate chapter 13: fixed-reference one-sample inference and power."""
from pathlib import Path
from statistics import mean,stdev
from html import escape
import math,json,re
from scipy.stats import t as student_t,nct
ROOT=Path(__file__).resolve().parent

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];v=[r['price'] for r in rows];m=mean(v);s=stdev(v);n=len(v);df=n-1;se=s/math.sqrt(n);mu0=130;obs=(m-mu0)/se;p=float(2*student_t.sf(abs(obs),df));critical=float(student_t.ppf(.975,df));lo=m-critical*se;hi=m+critical*se
 power=[]
 for nn in [20,50,100,200]:
  c=float(student_t.ppf(.975,nn-1));nc=20/80*math.sqrt(nn);power.append({'n':nn,'power':float(nct.cdf(-c,nn-1,nc)+nct.sf(c,nn-1,nc))})
 result={'description':'공통 학습자료의 가상 사전 기준 130에 대한 양측 t 검정. 실제 시장 검정이 아님.','mu0':mu0,'n':n,'mean':m,'sd':s,'se':se,'t':obs,'df':df,'p':p,'critical':critical,'ci':[lo,hi],'power':{'sigma':80,'difference':20,'alpha':.05,'values':power}}
 (ROOT/'hypothesis-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def text(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def line(x,y,xx,yy,c='#64748b',extra=''):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{c}" {extra}/>'
 def fig(id,title,b,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 def curve(cut,label):
  point=lambda x:(320+x*60,235-float(student_t.pdf(x,df))*400)
  b=text(24,28,label)+line(50,235,590,235)
  for a,z in [(-4.5,-cut),(cut,4.5)]:
   pts=[point(a+(z-a)*i/100) for i in range(101)];b+='<polygon points="'+f'{point(a)[0]},235 '+' '.join(f'{x:.5f},{y:.5f}' for x,y in pts)+f' {point(z)[0]},235" fill="#bfdbfe"/>'
  pts=[point(-4.5+i*.025) for i in range(361)];b+='<polyline points="'+' '.join(f'{x:.5f},{y:.5f}' for x,y in pts)+'" fill="none" stroke="#2563eb" stroke-width="2"/>'
  for x in [-4,-2,0,2,4]:b+=text(320+x*60,264,x,'text-anchor="middle"')
  for x in [-cut,cut]:b+=text(320+x*60,295,f'{x:.3f}','text-anchor="middle"')
  for x in [-critical,critical]:b+=line(320+x*60,45,320+x*60,235,'#d97706','stroke-dasharray="5 4" stroke-width="2" class="ht-critical"')
  b+=line(320+obs*60,45,320+obs*60,235,'#0f766e','stroke-width="3" class="ht-observed"')
  b+=text(24,338,'주황 점선: ±임계값 · 청록 실선: 관측 t · t=0: 귀무가설 중심')
  return b+text(510,320,'t 값 (단위 없음)')
 f1=fig('p-tails','양측 p값 · 관측 |t| 바깥의 꼬리 확률',curve(abs(obs),f'관측 |t|={abs(obs):.3f} 바깥 면적: p={p:.4f}'),'그림 1. H₀와 가정이 맞을 때의 자유도 29 t분포입니다. 양측 p값은 양쪽 꼬리 확률의 합입니다. 가로축은 단위 없는 t값, 세로축은 확률밀도입니다. 색칠한 면적이 p값이며 곡선은 −4.5~4.5만 표시하지만 계산은 무한 꼬리까지 포함합니다.',365)
 f2=fig('rejection','유의수준에 따른 양측 기각영역 (자유도 29)',curve(critical,f'사전에 정한 α=0.05: 양쪽 꼬리 0.025씩'),'그림 2. 자유도 29, 양측 5% 기각역은 ±2.045 경계와 그 바깥입니다. 옅은 주황은 기각영역, 주황 점선은 임계값, 청록 실선은 관측 t입니다. 그림 1의 p값 영역과 사전 기준 기각영역을 구별하세요.',365)
 x=lambda a:90+(a-90)*4
 b=text(24,28,'같은 양측 t 검정과 95% t 신뢰구간을 연결합니다')+line(x(lo),115,x(hi),115,'#2563eb','stroke-width="4" data-ci="mean"')+text(x(lo),147,f'{lo:.2f}','text-anchor="middle"')+text(x(hi),147,f'{hi:.2f}','text-anchor="middle"')+line(x(mu0),65,x(mu0),180,'#d97706','stroke-dasharray="4 3"')+text(x(mu0),55,'기준 130','text-anchor="middle"')+f'<circle cx="{x(m)}" cy="115" r="5" fill="#2563eb"/>'+text(x(m)+10,93,f'평균 {m:.2f}')+text(24,225,'130이 구간 안에 있음 → 5% 양측 검정에서 기각하지 않음')+text(360,260,'단위: 만원/㎡')
 f3=fig('ci-link','평균의 95% t 신뢰구간과 기준 130 비교 (만원/㎡)',b,'그림 3. 동일한 자료·가정·양측 t 방법에서의 연결입니다. 기준값을 기각하지 않는 것이 그 값이 참임을 입증하는 것은 아닙니다.',285)
 b=text(24,28,'같은 실제 차이와 퍼짐을 가정한 사전 검정력 비교')
 for i,d in enumerate(power):
  y=70+i*65;b+=text(24,y+19,f'n={d["n"]}')+f'<rect x="145" y="{y}" width="{d["power"]*390}" height="25" fill="#2563eb" data-n="{d["n"]}" data-power="{d["power"]}"/>'+text(155+d['power']*390,y+19,f'{d["power"]:.1%}')
 b+=text(24,345,'가로축: 검정력(0~100%) / α=0.05, 차이 20, σ=80')
 f4=fig('power','표본수별 이론적 검정력 · 차이와 표준편차 고정 (%)',b,'그림 4. 독립 정규표본의 양측 단일표본 t 검정을 가정한 이론값입니다. 실제 차이 20만원/㎡와 σ=80만원/㎡를 사전에 설정한 가상 계획 예제이며 관측 p값에서 계산한 사후 검정력이 아닙니다.',375)
 page=ROOT/'hypothesis-tests/index.html';old=page.read_text(encoding='utf-8')
 references=re.search(r'<details class="learn-more"><summary>참고자료</summary>.*?</details>',old,re.S)[0]
 comparisons=[{'mu0':value,'t':(m-value)/se,'p':float(2*student_t.sf(abs((m-value)/se),df))} for value in range(80,211)]
 criticals={str(a):float(student_t.ppf(1-a/2,df)) for a in [.01,.05,.10]}
 controls='''<details class="learn-more ht-experiment" hidden><summary>직접 확인하기 · 기준 평균과 유의수준을 바꾸면?</summary><div class="learn-more__body">
<p id="ht-note">표본수 30건, 평균 약 146.33만원/㎡, 표본표준편차 약 81.53만원/㎡를 고정한 학습용 가상 비교입니다. 계산에는 반올림 전 값을 사용합니다. 그림 1·2가 같은 설정을 공유하며 그림 3·4와 본문의 계산 예제는 원래 조건을 유지합니다.</p>
<label for="ht-mu">기준 평균 μ₀ <output id="ht-mu-value" for="ht-mu">130만원/㎡</output></label>
<input id="ht-mu" type="range" min="80" max="210" step="1" value="130" aria-describedby="ht-note ht-range-note">
<p id="ht-range-note" class="learn-source-note">80~210만원/㎡ · 1만원/㎡ 간격. 기준값을 결과에 유리하게 고르는 실제 검정 절차를 권장하는 기능은 아닙니다.</p>
<label for="ht-alpha">유의수준 α</label><select id="ht-alpha"><option value="0.01">0.01 (1%)</option><option value="0.05" selected>0.05 (5%)</option><option value="0.1">0.10 (10%)</option></select>
<button type="button" id="ht-reset">학습 예제 μ₀=130 · α=0.05로 복원</button>
<div id="ht-result" class="ht-formula" role="status" aria-live="polite"></div>
<p class="ht-legend">파란 곡선: 귀무가설 아래의 t분포 · 옅은 파랑: 그림 1의 p값 영역 · 옅은 주황: 그림 2의 기각영역 · 주황 점선: ±기각 임계값 · 청록 실선: 부호를 가진 관측 t값 · t=0: 귀무가설의 기준 중심</p>
<p class="learn-source-note">p≤α이면 기각합니다. 표시값이 반올림되어 같아 보여도 판정은 반올림 전 확률로 합니다. 기준 평균과 관측 t는 단위가 다르므로 같은 가로축에 놓지 않습니다.</p>
</div></details>'''
 data={'df':df,'n':n,'mean':m,'sd':s,'se':se,'criticals':criticals,'densityAtZero':float(student_t.pdf(0,df)),'comparisons':comparisons}
 f1=f1.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="ht-p-tails">').replace('<figcaption',controls+'<script type="application/json" id="ht-experiment-data">'+json.dumps(data,ensure_ascii=False)+'</script><figcaption')
 f2=f2.replace('fill="#bfdbfe"','fill="#ffedd5"')
 f2=f2.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="ht-rejection">')
 parts=[];source=(ROOT/'hypothesis-tests/content.md').read_text(encoding='utf-8')
 source=source.replace('\\*','*').replace('**','').replace('\\~','~')
 ids=['quick-start','hypotheses','statistic','p-value','decision','ci','errors','effect','multiplicity','practice','macro','recap']
 def inline(value):return re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',escape(value))
 def render(block):
  out=[];lines=block.strip().split('\n');i=0
  while i<len(lines):
   line=lines[i].strip()
   if not line or line=='---':i+=1;continue
   if line.startswith('[그림 '):out.append({1:f1,2:f2,3:f3,4:f4}[int(re.search(r'그림 (\d)',line)[1])]);i+=1;continue
   if line=='[CH2 Macro 통계분석 열기 →]':out.append('<p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 통계분석 열기 →</a></p>');i+=1;continue
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
   if re.fullmatch(r'\d+\. (자료 확인|기준값과의 차이|검정통계량 계산)',line):out.append('<p class="ht-step-title">'+inline(line)+'</p>');i+=1;continue
   if line.startswith('- ') or re.match(r'\d+\. ',line):
    ordered=not line.startswith('- ');tag='ol' if ordered else 'ul';items=[]
    while i<len(lines) and (re.match(r'\d+\. ',lines[i]) if ordered else lines[i].startswith('- ')):
     items.append('<li>'+inline(re.sub(r'^(?:- |\d+\. )','',lines[i]))+'</li>');i+=1
    out.append('<'+tag+'>'+''.join(items)+'</'+tag+'>');continue
   formula=line.startswith(('H₀:','H₁:','T =','t =','t ≈','d =','p =','p ≈','95% 신뢰구간:','차이의 95%','검정력 =','1 − 0.95','1 − (1','146.33 −'))
   out.append('<p'+(' class="ht-formula"' if formula else '')+'>'+inline(line)+'</p>');i+=1
  return '\n'.join(out)
 for id,section in zip(ids,re.split(r'^## ',source,flags=re.M)[1:],strict=True):
  label,body=section.split('\n',1);heading=re.search(r'^### (.+)$',body,re.M)[1];body=re.sub(r'^### .+\n','',body,count=1,flags=re.M)
  if id=='practice':
   items=[]
   for q in re.split(r'^\d+\. ',body,flags=re.M)[1:]:
    question,answer=q.split('▶ 답과 해설',1);items.append('<li>'+inline(question.strip())+'<details><summary>답과 해설</summary><div class="learn-more__body">'+render(answer)+'</div></details></li>')
   html='<ol class="learn-exercises">'+''.join(items)+'</ol>'
  else:html=render(body)
  if id=='quick-start':html=html.replace('<ul>','<ul class="learn-objectives">',1).replace('12장에서 배운 신뢰구간','<a href="/learn/stats/confidence-intervals/">12장에서 배운 신뢰구간</a>')
  if id=='quick-start':html+='<p><a href="/learn/stats/confidence-intervals/">12장 「점추정과 신뢰구간」</a>과 연결해 살펴보세요.</p>'
  if id=='statistic':html+='<p class="learn-source-note"><a href="/learn/stats/graphs/#data">공통 학습 자료 30건</a> · <a href="../hypothesis-example.json">계산값 JSON</a>. 평균·표준편차·표준오차·t값·p값은 반올림 전 자료로 계산하고 표시만 반올림합니다.</p>'
  if id=='errors':heading='잘못 기각하거나, 있는 차이를 놓칠 수 있습니다';html+='<p class="learn-source-note">α는 제1종 오류를 통제하는 유의수준이고, β는 특정한 실제 차이에서의 제2종 오류 확률입니다. 오류 사건과 그 확률을 구별합니다.</p>'
  if id=='ci':html=html.replace('기준값이 신뢰구간 안에 있다면 기각하지 않습니다.','기준값이 신뢰구간의 내부(끝점 제외)에 있다면 기각하지 않습니다.');html+='<p class="learn-source-note">이 장은 p≤α를 기각 규칙으로 사용합니다. 신뢰구간 끝점에서는 p=α가 되어 기각 경계에 해당하므로, 끝점과 구간 내부를 구별합니다. 그림 3의 기준 130은 구간 내부에 있습니다.</p>'
  if id=='macro':
   html=html.replace('신뢰구간: 회귀계수 추정의 불확실성은 어느 정도인가?','신뢰구간: 제공되는 분석에서는 추정의 불확실성을 함께 살펴봅니다. 현재 토지 회귀의 계수 상세에는 계수별 신뢰구간이 표시되지 않습니다.')
   html+='<p>회귀계수의 검정과 불확실성은 <a href="/learn/stats/model-fit/">21장 「회귀모형의 적합도와 추정의 불확실성」</a>에서 이어서 살펴봅니다.</p>'
   html+='''<details class="learn-more"><summary>현재 토지 회귀 화면에서 확인할 수 있는 항목</summary><div class="learn-more__body"><p>계수 상세에는 계수, 표준오차(SE), t값, p값이 표시됩니다. 요약에는 분석 건수 n, R², 조정 R²와 전체 모형의 F p값 등이 표시됩니다. 계수별 신뢰구간과 잔차 자유도는 현재 이 표에 직접 표시되지 않습니다.</p><p>현재 토지 회귀는 기본 OLS를 적합하고, 각 계수에 대해 H₀: βⱼ=0인 양측 t검정을 사용합니다. t=계수/SE이며 p=2P(T≥|t|)입니다. 잔차 자유도는 분석 건수에서 상수항을 포함한 설계행렬의 순위를 뺀 값입니다. 따라서 이 장의 단일표본 검정처럼 항상 n−1인 것은 아닙니다.</p><p>표준오차는 기본 OLS의 잔차분산과 설계행렬로 계산합니다. 이 경로는 이분산 강건 또는 군집 표준오차를 자동 적용하지 않습니다. 오차의 독립성과 등분산 등 가정의 적절성을 함께 확인해야 합니다.</p><p>계수 상세의 p값은 소수 다섯째 자리, SE와 t는 소수 둘째 자리로 표시합니다. API는 반올림 전 계수·SE·t·p를 전달하므로 반올림된 표의 값으로 다시 나누면 차이가 날 수 있습니다. p가 0.00000으로 보이더라도 정확히 0이라는 뜻은 아닙니다.</p><p>토지 회귀 화면의 유의 변수 강조 기준은 p&lt;0.10입니다. 본문의 기본 α=0.05와 다르므로 색상이나 유의 변수 개수만으로 이 장의 5% 판정을 대신하지 않습니다. 전체 모형의 F p값과 개별 계수의 p값도 구별합니다.</p><p>도로 조건 같은 범주형 변수의 계수는 기준 범주와 비교한 조건부 관련성입니다. 변수 선택과 여러 모형 탐색 뒤의 p값을 사전에 정한 단일 검정처럼 해석하지 않습니다.</p></div></details>'''
  if id=='recap':html=html.replace('<ul>','<ul class="learn-recap-list">',1).replace('14장 「두 집단 비교와 효과크기」','<a href="/learn/stats/comparing-groups/">14장 「두 집단 비교와 효과크기」</a>')
  parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{heading}</h2>{html}</section>')
 pth=ROOT/'hypothesis-tests/index.html';html=pth.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="가설검정과 p값">\n'+'\n'.join(parts)+'\n</article>',html,count=1,flags=re.S)
 html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1가설검정과 p값, 유의수준·오류·검정력·효과크기를 그림과 예제로 구분해 설명합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);html=html.replace('별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.','활용도는 CH2 Macro의 분석 결과를 이해하는 데 얼마나 도움이 되는지를 나타냅니다.')
 if 'hypothesis-tests/chapter.css' not in html:html=html.replace('</head>','<link rel="stylesheet" href="/learn/stats/hypothesis-tests/chapter.css?v=20261024-1" />\n  </head>')
 if 'hypothesis-tests/experiment.js' not in html:html=html.replace('</body>','<script type="module" src="/learn/stats/hypothesis-tests/experiment.js?v=20261024-1"></script>\n  </body>')
 html=re.sub(r'(hypothesis-tests/(?:chapter\.css|experiment\.js)\?v=)[^"\s]+',r'\g<1>20261024-2',html)
 pth.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
