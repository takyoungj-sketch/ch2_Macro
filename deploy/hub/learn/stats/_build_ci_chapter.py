"""Build mean confidence-interval lesson; requires scipy for t quantiles."""
from pathlib import Path
from statistics import mean,stdev
from html import escape
import math,json,re,random
from scipy.stats import t as student_t
ROOT=Path(__file__).resolve().parent

def interval(m,s,n,level=.95):
 critical=float(student_t.ppf((1+level)/2,n-1));margin=critical*s/math.sqrt(n)
 return {'mean':m,'sd':s,'n':n,'level':level,'critical':critical,'margin':margin,'low':m-margin,'high':m+margin}

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];v=[r['price'] for r in rows];m=mean(v);s=stdev(v);base=interval(m,s,30)
 rng=random.Random(20261007);repeats=[];critical=float(student_t.ppf(.975,24));mu=100;sigma=20;n=25
 for i in range(20):
  sample=[rng.gauss(mu,sigma) for _ in range(n)];d=interval(mean(sample),stdev(sample),n);repeats.append({'id':i+1,'sample':sample,**d,'covers':d['low']<=mu<=d['high']})
 levels=[interval(m,s,30,c) for c in [.9,.95,.99]];sizes=[interval(m,s,n) for n in [10,30,120]]
 (ROOT/'confidence-example.json').write_text(json.dumps({'description':'공통 교육자료 계산과 별도 정규모형 반복표집 예제. 실제 시장 결과가 아님.','base':base,'levels':levels,'sizes':sizes,'simulation':{'seed':20261007,'mu':mu,'sigma':sigma,'n':25,'critical':critical,'method':'two-sided t interval, df=24','repeats':repeats}},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def text(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def line(x,y,xx,yy,c='#64748b',extra=''):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{c}" {extra}/>'
 def fig(id,title,b,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 def draw(d,y,key,scale=4):
  x=lambda v:90+(v-90)*scale
  b=line(x(d['low']),y,x(d['high']),y,'#2563eb',f'stroke-width="4" data-key="{key}" data-low="{d["low"]}" data-high="{d["high"]}"')
  for v in [d['low'],d['high']]:b+=line(x(v),y-8,x(v),y+8,'#2563eb')
  return b+f'<circle cx="{x(d["mean"])}" cy="{y}" r="5" fill="#d97706"/>'+text(x(d['low']),y+29,f'{d["low"]:.2f}','text-anchor="middle"')+text(x(d['high']),y+29,f'{d["high"]:.2f}','text-anchor="middle"')
 b=text(24,28,'평균 추정값에 오차한계를 붙입니다')+draw(base,115,'base')+text(260,80,f'평균 {m:.2f}')+text(24,195,f'95% 구간 = {m:.2f} ± {base["margin"]:.2f}')+text(24,230,'단위: 만원/㎡ · 주황 점은 표본평균')
 f1=fig('estimate','표본평균과 평균의 95% t 신뢰구간 (만원/㎡)',b,'그림 1. 공통 30건으로 계산한 평균의 t 구간입니다. 실제 시장의 타당한 95% 구간임을 검증한 결과가 아니라 산식 학습 예제입니다.',260)
 b=text(24,28,'같은 자료에서 신뢰수준만 높이면 구간이 넓어집니다')
 for i,d in enumerate(levels):b+=text(24,85+i*90,f'{d["level"]:.0%}')+draw(d,80+i*90,f'level-{d["level"]}')
 b+=text(24,330,'중심·s·n 고정 / 단위: 만원/㎡')
 f2=fig('levels','같은 표본의 90%·95%·99% t 신뢰구간 (만원/㎡)',b,'그림 3. 같은 30건의 양측 t 구간을 90%·95%·99%로 비교했습니다. 같은 자료·같은 방법에서 높은 신뢰수준에는 더 넓은 구간이 필요합니다.',355)
 b=text(24,28,'평균과 퍼짐을 고정한 표본수 비교입니다')
 for i,d in enumerate(sizes):b+=text(24,85+i*90,f'n={d["n"]}')+draw(d,80+i*90,f'n-{d["n"]}',3.7)
 b+=text(24,330,'신뢰수준 95% / 단위: 만원/㎡')
 f3=fig('sizes','평균과 표준편차를 고정한 표본수별 t 신뢰구간 (만원/㎡)',b,'그림 4. 같은 평균과 s를 가정한 계획 비교입니다. 자유도에 따른 t 임계값도 다시 계산했습니다. 실제 10·120건을 수집한 결과가 아닙니다.',355)
 b=text(24,28,'반복하면 구간은 달라지고 모평균 100은 고정됩니다');x=lambda v:80+(v-80)*12
 b+=line(x(mu),45,x(mu),485,'#d97706','stroke-dasharray="4 3"')
 for i,d in enumerate(repeats):
  y=60+i*21;b+=text(24,y+4,d['id'])+line(x(d['low']),y,x(d['high']),y,'#2563eb' if d['covers'] else '#dc2626',f'stroke-width="2" data-repeat="{d["id"]}"')+f'<circle cx="{x(d["mean"])}" cy="{y}" r="3" fill="#475569"/>'
 b+=text(24,510,f'이번 20회: {sum(d["covers"] for d in repeats)}개 포함 / {sum(not d["covers"] for d in repeats)}개 미포함')
 for v in [80,90,100,110,120]:b+=text(x(v),545,v,'text-anchor="middle"')
 f4=fig('coverage','정규모형 반복표집 · 표본 25개로 만든 95% t 신뢰구간 20개',b,'그림 2. 가상 N(100,20²)에서 매번 독립 표본 25개를 뽑아 20회 반복했습니다. 각 표본의 s와 자유도 24의 t 임계값을 사용합니다. 파랑은 μ 포함, 빨강은 미포함. 초기 정적 예제의 시드는 20261007이며 원자료를 JSON에 보존했습니다. 브라우저에서는 새 무작위 표본으로 시작합니다.',575)
 p=ROOT/'confidence-intervals/index.html';old=p.read_text(encoding='utf-8')
 capture=re.search(r'<figure class="learn-capture.*?</figure>',old,re.S)[0]
 references=re.search(r'<details class="learn-more"><summary>참고자료</summary>.*?</details>',old,re.S)[0]
 references=references.replace('본문의 네 개 그림은 공통 학습 자료와 별도 가상 모형으로 작성했으며 임계값은 SciPy로 계산했습니다.','공통 자료와 초기 정적 예제의 임계값은 SciPy로 계산했습니다. 그림 2의 실험은 N(100,20²)에서 새 표본을 추출하고 각 표본의 s와 자유도 24로 t 구간을 계산합니다.')
 controls='''<div class="ci-experiment" hidden data-critical="CRITICAL">
<p id="ci-model">학습용 정규모형 N(100,20²) · μ=100, σ=20 · 매회 독립표본 25개 · 자유도 24 · t 임계값 약 2.064. 단위는 모형값입니다.</p>
<button type="button" id="ci-resample">새 표본 추출</button>
<p id="ci-status" role="status" aria-live="polite"></p>
<p class="learn-source-note">20개 모두 포함되거나 여러 개가 미포함되어도 결과를 그대로 표시합니다. 색상과 함께 선 모양·행 번호로 구분합니다. 주황 세로선은 μ=100입니다. 가로축은 이번 결과를 모두 담도록 자동 조정됩니다.</p>
<details class="learn-more"><summary>누적 실험 · 장기 포함률 확인하기</summary><div class="learn-more__body">
<p>누적 횟수에 도달할 때까지 독립 표본을 추가합니다. 그래프는 최근 20개만 보여줍니다. 누적 비율이 정확히 95%가 되도록 조정하지 않습니다.</p>
<div class="ci-actions"><button type="button" data-ci-total="100">100회까지 누적</button><button type="button" data-ci-total="500">500회까지 누적</button></div>
<p id="ci-total" role="status" aria-live="polite"></p>
</div></details></div>'''.replace('CRITICAL',repr(critical))
 f4=f4.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="ci-coverage">').replace('<figcaption',controls+'<figcaption')
 source=(ROOT/'confidence-intervals/content.md').read_text(encoding='utf-8')
 # The pasted copy wraps every paragraph in bold. Normalize that formatting,
 # preserving its words and handling only this chapter's small Markdown subset.
 source=source.replace('\\*','*').replace('**','').replace('\\~','~')
 ids=['quick-start','formula','calculation','coverage','levels','sizes','other-intervals','limits','practice','macro','recap'];parts=[]
 def inline(value):return escape(value)
 def render(block):
  out=[];lines=block.strip().split('\n');i=0
  while i<len(lines):
   line=lines[i].strip()
   if not line or line=='---':i+=1;continue
   if line.startswith('[그림 '):out.append({1:f1,2:f4,3:f2,4:f3}[int(re.search(r'그림 (\d)',line)[1])]);i+=1;continue
   if line=='[기존 CH2 Macro 실제 화면 이미지 유지]':out.append(capture);i+=1;continue
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
   if line.startswith('- '):
    items=[]
    while i<len(lines) and lines[i].startswith('- '):items.append('<li>'+inline(lines[i][2:])+'</li>');i+=1
    out.append('<ul>'+''.join(items)+'</ul>');continue
   formula=line.startswith(('신뢰구간 =','x̄ ±','오차한계 =','95% 신뢰구간:'))
   out.append('<p'+(' class="ci-formula"' if formula else '')+'>'+inline(line)+'</p>');i+=1
  return '\n'.join(out)
 for id,section in zip(ids,re.split(r'^## ',source,flags=re.M)[1:],strict=True):
  label,body=section.split('\n',1);heading=re.search(r'^### (.+)$',body,re.M)[1];body=re.sub(r'^### .+\n','',body,count=1,flags=re.M)
  if id=='practice':
   items=[]
   for q in re.split(r'^\d+\. ',body,flags=re.M)[1:]:
    question,answer=q.split('▶ 답과 해설',1);items.append('<li>'+inline(question.strip())+'<details><summary>답과 해설</summary><div class="learn-more__body">'+render(answer)+'</div></details></li>')
   html='<ol class="learn-exercises">'+''.join(items)+'</ol>'
  else:html=render(body)
  if id=='quick-start':html=html.replace('<ul>','<ul class="learn-objectives">',1);html+='<p>이전 <a href="/learn/stats/sample-size/">11장 「표준오차와 표본수」</a>에서 표준오차를 살펴보았습니다.</p>'
  if id=='calculation':html+='<p class="learn-source-note"><a href="/learn/stats/graphs/#data">공통 학습 자료 30건</a> · <a href="../confidence-example.json">계산 결과와 초기 정적 반복표집 원자료</a>. 버튼으로 새로 뽑은 실험 결과는 이 JSON과 다릅니다.</p>'
  if id=='macro':html+='''<ul class="learn-screen-reading"><li>점추정값: 평균 33.2만원/㎡</li><li>평균의 95% 신뢰구간: 30.4~36.0만원/㎡</li><li>제1~제3사분위수: 16.1~40.0만원/㎡</li><li>최솟값~최댓값: 3.3~296.6만원/㎡</li><li>거래 건수: 393건 · 표시 표본표준편차: 28.4만원/㎡</li></ul>
<details class="learn-more"><summary>실제 화면의 계산 방법과 확인 범위</summary><div class="learn-more__body"><p>기본통계 코드는 같은 분석 대상의 반올림 전 단가로 산술평균, n−1을 사용하는 표본표준편차, 유효 건수를 구합니다. 평균 ± t₀.₉₇₅,ₙ₋₁ × s/√n으로 95% 신뢰구간을 계산한 뒤 소수 첫째 자리로 반올림합니다.</p><p>기본통계 사전집계는 정상 거래, 해제 제외, 단가가 있는 거래를 사용합니다. 이상치 제외를 선택하는 유료 조회 경로는 제외 후 남은 자료로 평균·표준편차·건수·신뢰구간을 함께 다시 계산합니다. 기본통계에 이상치가 자동으로 제외된다고 해석하지 않습니다.</p><p>캡처의 반올림된 평균 33.2, 표준편차 28.4, n=393을 넣으면 양측 오차한계는 약 2.82로, 표시 구간 30.4~36.0과 일치하는 수준입니다. 다만 캡처 당시 원거래 자료와 필터 상태를 확인하지 못하여, 당시의 반올림 전 구간을 완전히 재현한 것은 아닙니다.</p><p>이 산식은 단순 독립표본을 전제로 합니다. 실제 거래의 의존성, 수집 편향이나 대표성을 자동으로 보정하지 않습니다.</p></div></details>'''
  if id=='recap':html=html.replace('<ul>','<ul class="learn-recap-list">',1).replace('13장 「가설검정과 p값」','<a href="/learn/stats/hypothesis-tests/">13장 「가설검정과 p값」</a>')
  parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{heading}</h2>{html}</section>')
 p=ROOT/'confidence-intervals/index.html';s=p.read_text(encoding='utf-8');s=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="점추정과 신뢰구간">\n'+'\n'.join(parts)+'\n</article>',s,count=1,flags=re.S)
 s=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1점추정과 평균의 t 신뢰구간, 95%의 의미와 구간 폭의 변화를 그림과 예제로 설명합니다.\2',s,count=1,flags=re.S);s=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',s);s=s.replace('별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.','활용도는 CH2 Macro의 분석 결과를 이해하는 데 얼마나 도움이 되는지를 나타냅니다.')
 if 'confidence-intervals/chapter.css' not in s:s=s.replace('</head>','<link rel="stylesheet" href="/learn/stats/confidence-intervals/chapter.css?v=20261024-1" />\n  </head>')
 if 'confidence-intervals/experiment.js' not in s:s=s.replace('</body>','<script type="module" src="/learn/stats/confidence-intervals/experiment.js?v=20261024-1"></script>\n  </body>')
 p.write_text(s,encoding='utf-8')
if __name__=='__main__':build()
