"""Generate chapter 11 from shared teaching observations."""
from pathlib import Path
from statistics import stdev
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
 f1=fig('sd-se','표본표준편차와 추정 표준오차 비교 (만원/㎡)',b,'그림 1. 공통 학습 자료 30건에서 n−1로 계산한 s=81.53, s/√30=14.89입니다. 막대는 0에서 시작하며 이 SE는 독립·동일분포 표본을 가정한 계산입니다.',305)
 b=t(24,28,'퍼짐 s를 고정한 표본수 비교입니다')
 for i,n in enumerate([10,30,120,480]):
  value=s/math.sqrt(n);y=70+i*65;b+=t(24,y+19,f'n={n}')+bar(145,y,value,14,f'data-n="{n}" data-se="{value}"')+t(155+value*14,y+19,f'{value:.2f}')
 b+=t(24,345,'가로축: 추정 표준오차(만원/㎡), 모두 0에서 시작')
 f2=fig('size','표본수별 추정 표준오차 · 표준편차 고정 가상 비교 (만원/㎡)',b,'그림 2. s=81.5286…을 고정한 가상 비교입니다. 실제로 10·120·480건을 추출한 결과가 아니며, 새 표본에서는 s도 달라질 수 있습니다.',370)
 b=t(24,28,'건수가 같아도 자료의 퍼짐이 다를 수 있습니다')
 for i,label in enumerate(['주거','상업']):
  a=[r['price'] for r in rows if r['group']==label];sd=stdev(a);err=sd/math.sqrt(len(a));y=80+i*100
  b+=t(24,y,f'{label} n={len(a)} · s={sd:.2f}')+bar(160,y+20,err,13,f'data-group="{label}" data-se="{err}"')+t(170+err*13,y+40,f'{err:.2f}')
 b+=t(24,300,'가로축: 추정 표준오차(만원/㎡), 모두 0에서 시작')
 f3=fig('groups','같은 표본수에서 주거·상업의 추정 표준오차 비교 (만원/㎡)',b,'그림 3. 공통 자료의 주거·상업 각 15건을 별도로 계산했습니다. 단순 독립 표본 공식을 적용한 학습 예제이며 집단 간 차이의 유의성 검정은 아닙니다.',325)
 b=t(24,28,'목표 표준오차가 작아질수록 필요한 n이 빠르게 늘어납니다')
 for i,target in enumerate([20,10,5]):
  n=math.ceil((s/target)**2);y=75+i*75;b+=t(24,y+19,f'목표 SE {target}')+bar(175,y,n,1.3,f'data-target="{target}" data-required="{n}"')+t(185+n*1.3,y+19,f'{n}건')
 b+=t(24,325,'가로축: 필요 표본수 / 계획용 퍼짐 s≈81.53')
 f4=fig('planning','목표 표준오차별 계획 표본수 (건)',b,'그림 4. n≥(s/목표 SE)²을 올림했습니다. 목표 SE의 단위는 만원/㎡입니다. 이는 모집단 퍼짐을 학습 자료의 s로 가정한 계획 표본수이며 실제 추정오차를 보장하지 않습니다. 신뢰수준을 지정한 오차한계 계산과 다릅니다.',352)
 experiment='''<details class="learn-more se-experiment" hidden><summary>직접 확인하기 · 표본수 n을 바꾸면?</summary><div class="learn-more__body">
<p id="se-experiment-note">표본표준편차 s=81.53만원/㎡를 고정한 가상 계산입니다. 실제 재표집 결과가 아닙니다. 기존 그림은 반올림 전 s=81.5286…을 사용하며, 이 실험은 표시값 81.53을 사용합니다.</p>
<label for="se-n">표본수 n <output id="se-n-value" for="se-n">30건</output></label>
<input id="se-n" type="range" min="10" max="480" step="1" value="30" aria-describedby="se-experiment-note">
<div class="se-presets" role="group" aria-label="표본수 빠른 선택"><button type="button" data-se-n="10" aria-pressed="false">10건</button><button type="button" data-se-n="30" aria-pressed="true">30건</button><button type="button" data-se-n="120" aria-pressed="false">120건</button><button type="button" data-se-n="480" aria-pressed="false">480건</button></div>
<p class="se-formula">추정 SE = 81.53 / √<span id="se-formula-n">30</span> = <output id="se-result" for="se-n" aria-live="polite">14.89만원/㎡</output></p>
<p class="learn-source-note">막대는 0에서 시작하며, n=10일 때의 SE(25.78)를 최대로 표시합니다. 위 그림 2와 비교해 보세요.</p>
<div class="se-meter" role="meter" aria-label="선택한 표본수의 추정 표준오차 (만원/㎡)" aria-valuemin="0" aria-valuemax="25.7820536419776" aria-valuenow="14.88527343159583"><span></span></div>
</div></details>'''
 parts=[]
 source=(ROOT/'sample-size/content.md').read_text(encoding='utf-8')
 ids=['quick-start','calculation','size','groups','planning','interpretation','design','practice','macro','recap']
 # This renderer handles only the approved chapter copy, not arbitrary Markdown.
 def inline(value):
  value=escape(value)
  return re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',value)
 def render(block):
  out=[];lines=block.strip().split('\n');i=0
  while i<len(lines):
   line=lines[i].strip()
   if not line or line=='---':i+=1;continue
   if line.startswith('**[그림 '):
    number=int(re.search(r'그림 (\d)',line)[1]);out.append([f1,f2,f3,f4][number-1]);i+=1;continue
   if line.startswith('|'):
    table=[]
    while i<len(lines) and lines[i].strip().startswith('|'):
     cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
     if not all(re.fullmatch(r'[:\-]+',c) for c in cells):table.append(cells)
     i+=1
    out.append('<div class="learn-data learn-data--full"><table><thead><tr>'+''.join('<th scope="col">'+inline(c)+'</th>' for c in table[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join(('<th scope="row">'+inline(c)+'</th>') if j==0 else '<td>'+inline(c)+'</td>' for j,c in enumerate(row))+'</tr>' for row in table[1:])+'</tbody></table></div>');continue
   if line.startswith('- ') or re.match(r'\d+\. ',line):
    ordered=not line.startswith('- ');tag='ol' if ordered else 'ul';items=[]
    while i<len(lines) and (re.match(r'\d+\. ',lines[i]) if ordered else lines[i].startswith('- ')):
     items.append('<li>'+inline(re.sub(r'^(?:- |\d+\. )','',lines[i]))+'</li>');i+=1
    out.append('<'+tag+'>'+''.join(items)+'</'+tag+'>');continue
   if line.startswith('**▶ '):
    title=line.removeprefix('**▶ ').removesuffix('**');rest=[];i+=1
    while i<len(lines) and lines[i].strip()!='---':rest.append(lines[i]);i+=1
    out.append('<details class="learn-more"><summary>'+inline(title)+'</summary><div class="learn-more__body">'+render('\n'.join(rest))+'</div></details>');continue
   if line=='▶ 참고자료':out.append(references);i+=1;continue
   if line=='[CH2 Macro 토지 통계 열기 →]':
    out.append('<p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 통계 열기 →</a></p>');i+=1;continue
   formula=line in ['**SE = σ / √n**','**추정 SE = s / √n**','**n ≥ (σ₀ / e)²**'] or line.startswith('SE = ')
   out.append('<p'+(' class="se-formula"' if formula else '')+'>'+inline(line)+'</p>');i+=1
  return '\n'.join(out)
 old=(ROOT/'sample-size/index.html').read_text(encoding='utf-8')
 references=re.search(r'<details class="learn-more"><summary>참고자료</summary>.*?</details>',old,re.S)[0]
 sections=re.split(r'^## ',source,flags=re.M)[1:]
 for id,section in zip(ids,sections,strict=True):
  label,body=section.split('\n',1);heading=re.search(r'^### (.+)$',body,re.M)[1];body=re.sub(r'^### .+\n','',body,count=1,flags=re.M)
  if id=='practice':
   questions=re.split(r'^\*\*(?=\d+\.)',body,flags=re.M)[1:];items=[]
   for q in questions:
    question,answer=q.split('▶ 답과 해설',1)
    question=re.sub(r'^\d+\. ','',question.strip().removesuffix('**'))
    items.append('<li>'+inline(question)+'<details><summary>답과 해설</summary><div class="learn-more__body">'+render(answer)+'</div></details></li>')
   html='<ol class="learn-exercises">'+''.join(items)+'</ol>'
  else:html=render(body)
  if id=='quick-start':html=html.replace('<ul>','<ul class="learn-objectives">',1);html+='<p>이전 <a href="/learn/stats/sampling-distributions/">10장 「표본분포와 중심극한정리」</a>에서 표본평균의 변동을 살펴보았습니다.</p>'
  if id=='calculation':
   html=html.replace('<p>공통 학습 자료 30건에','<p><a href="/learn/stats/graphs/#data">공통 학습 자료 30건</a>에')
   html+='<p class="learn-source-note"><a href="../example-data.json">공통 학습 자료 JSON</a> · 실제 자료 계산과 기존 네 그래프는 반올림 전 값을 사용하고, 표시만 소수 둘째 자리로 반올림합니다.</p>'
  if id=='size':html=html.replace(f2,f2+experiment)
  if id=='planning':html+='<p class="learn-source-note">계산값은 필요한 최소 정수로 올림합니다. 그림 4는 계획 표본수이며 실제 추정오차를 보장하지 않습니다.</p>'
  if id=='recap':html=html.replace('<ul>','<ul class="learn-recap-list">',1);html=html.replace('12장 「점추정과 신뢰구간」','<a href="/learn/stats/confidence-intervals/">12장 「점추정과 신뢰구간」</a>')
  parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{heading}</h2>{html}</section>')
 p=ROOT/'sample-size/index.html';text=p.read_text(encoding='utf-8');text=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="표준오차와 표본수">\n'+'\n'.join(parts)+'\n</article>',text,count=1,flags=re.S)
 text=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1표준편차와 표준오차의 차이, 표본수와 정밀도, 표집 설계의 한계를 공통 예제와 그림으로 설명합니다.\2',text,count=1,flags=re.S);text=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',text);text=text.replace('별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.','활용도는 CH2 Macro의 분석 결과를 이해하는 데 얼마나 도움이 되는지를 나타냅니다.')
 if 'sample-size/chapter.css' not in text:text=text.replace('</head>','<link rel="stylesheet" href="/learn/stats/sample-size/chapter.css?v=20261024-1" />\n  </head>')
 if 'sample-size/experiment.js' not in text:text=text.replace('</body>','<script src="/learn/stats/sample-size/experiment.js?v=20261024-1" defer></script>\n  </body>')
 p.write_text(text,encoding='utf-8')
if __name__=='__main__':build()
