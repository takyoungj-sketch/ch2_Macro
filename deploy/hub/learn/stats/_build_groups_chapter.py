"""Generate independent/paired comparisons and explicitly defined effect sizes."""
from pathlib import Path
from statistics import mean,stdev,variance
from html import escape
import math,json,re
from scipy.stats import t as student_t
ROOT=Path(__file__).resolve().parent

def welch(a,b):
 na,nb=len(a),len(b);va,vb=variance(a),variance(b);aa,bb=va/na,vb/nb;se=math.sqrt(aa+bb);df=(aa+bb)**2/(aa*aa/(na-1)+bb*bb/(nb-1));delta=mean(a)-mean(b);t=delta/se;crit=float(student_t.ppf(.975,df));pooled=math.sqrt(((na-1)*va+(nb-1)*vb)/(na+nb-2));d=delta/pooled
 return {'difference':delta,'se':se,'df':df,'t':t,'p':float(2*student_t.sf(abs(t),df)),'low':delta-crit*se,'high':delta+crit*se,'pooled_sd':pooled,'d':d,'g_approx':(1-3/(4*(na+nb-2)-1))*d}

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];a=[r['price'] for r in rows if r['group']=='상업'];b=[r['price'] for r in rows if r['group']=='주거'];w=welch(a,b);sensitivity=welch([r['price'] for r in rows if r['group']=='상업' and r['id']!=7],b)
 before=[80,100,120,140,160,180];after=[86,104,127,145,168,186];diff=[y-x for x,y in zip(before,after)];dm=mean(diff);ds=stdev(diff);dse=ds/math.sqrt(len(diff));crit=float(student_t.ppf(.975,len(diff)-1));paired={'before':before,'after':after,'differences':diff,'mean':dm,'sd':ds,'se':dse,'low':dm-crit*dse,'high':dm+crit*dse}
 result={'description':'공통 학습 자료 및 별도 가상 대응표본. 실제 인과효과가 아님.','welch':w,'without_id7':sensitivity,'paired':paired};(ROOT/'group-comparison-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def t(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def line(x,y,xx,yy,c='#64748b',extra=''):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{c}" {extra}/>'
 def fig(id,title,body,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{body}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 body=t(24,28,'집단별 평균과 개별 단가의 흩어짐을 함께 봅니다')
 for i,(label,values) in enumerate([('주거',b),('상업',a)]):
  y=100+i*120;avg=mean(values);sd=stdev(values)
  body+=t(24,y-52,f'{label} · n={len(values)} · 평균 {avg:.2f} · 표본 s={sd:.2f}')+line(70,y,570,y)
  placed=[]
  for row in sorted((r for r in rows if r['group']==label),key=lambda r:r['price']):
   value=row['price'];xx=70+value
   for lane in range(8):
    yy=y-lane*11
    if all(math.hypot(xx-px,yy-py)>=10 for px,py in placed):break
   placed.append((xx,yy));body+=f'<circle cx="{xx}" cy="{yy}" r="4" fill="#2563eb" data-group="{label}" data-value="{value}" data-source-id="{row["id"]}"><title>{label} 자료 {row["id"]}: {value}만원/㎡</title></circle>'
  body+=line(70+avg,y-40,70+avg,y+8,'#d97706','stroke-width="2" stroke-dasharray="4 3" class="gg-mean"')
  body+='<g class="gg-sd" hidden="">'+line(70+avg-sd,y+20,70+avg+sd,y+20,'#0f766e','stroke-width="3"')
  for xx in [70+avg-sd,70+avg+sd]:body+=line(xx,y+15,xx,y+25,'#0f766e','stroke-width="2"')
  body+='</g>'
 for value in [0,100,200,300,400,500]:body+=t(70+value,280,value,'text-anchor="middle"')
 body+=t(24,315,'점: 개별 단가 · 주황 점선: 평균 위치 · 가로축: 단가(만원/㎡)')+t(24,345,'청록선 선택 표시: 평균±표본표준편차 · 평균의 신뢰구간이 아닙니다')
 f1=fig('groups','주거·상업의 개별 단가와 평균·표본표준편차 (만원/㎡)',body,'그림 1. 공통 학습 자료 각 15건입니다. 상업의 480도 그대로 표시합니다. 점의 세로 위치는 겹침을 줄이기 위한 배치이며 별도 측정값이 아닙니다. 주황 점선은 평균 위치입니다.',375)
 group_controls='<div class="gg-controls" hidden><label><input type="checkbox" id="gg-mean" checked> 평균 위치선 표시</label><label><input type="checkbox" id="gg-sd"> 평균±표본표준편차 표시</label><p class="learn-source-note">표본표준편차는 개별 자료의 흩어짐입니다. 평균의 표준오차나 신뢰구간과 다릅니다. 선을 숨겨도 제목의 계산값과 개별 관측값은 유지됩니다.</p></div>'
 f1=f1.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="gg-distribution">').replace('<figcaption',group_controls+'<figcaption')
 body=t(24,28,'상업 − 주거: 차이 자체의 구간을 계산합니다');x=lambda value:100+value*3.3
 body+=line(x(0),65,x(0),185,'#d97706','stroke-dasharray="4 3"')+line(x(w['low']),120,x(w['high']),120,'#2563eb',f'stroke-width="4" data-diff-ci="true"')+f'<circle cx="{x(w["difference"])}" cy="120" r="5" fill="#2563eb"/>'
 body+=t(x(w['low']),153,f'{w["low"]:.2f}','text-anchor="middle"')+t(x(w['high']),153,f'{w["high"]:.2f}','text-anchor="middle"')+t(x(w['difference']),95,f'차이 {w["difference"]:.2f}','text-anchor="middle"')+t(x(0),210,'0','text-anchor="middle"')+t(24,250,f'Welch 95% 구간 / p={w["p"]:.4f} / 단위: 만원/㎡')
 f2=fig('difference','상업−주거 평균 차이의 Welch 95% 신뢰구간 (만원/㎡)',body,'그림 2. 독립 정규표본 모형을 적용한 교재 계산입니다. 표집 가정이 확인되지 않은 이 자료로 실제 시장의 유의성이나 용도의 인과효과를 주장하지 않습니다.',280)
 body=t(24,28,'같은 대상의 전후 값을 연결하면 짝을 볼 수 있습니다')
 for i,(v1,v2) in enumerate(zip(before,after)):
  yy=lambda value:300-(value-60)*1.7;body+=line(180,yy(v1),440,yy(v2),'#94a3b8',f'data-pair="{i+1}"')+f'<circle cx="180" cy="{yy(v1)}" r="4" fill="#2563eb"/><circle cx="440" cy="{yy(v2)}" r="4" fill="#d97706"/>'+t(165,yy(v1)+4,v1,'text-anchor="end"')+t(455,yy(v2)+4,v2)+t(85,yy(v1)+4,f'학생 {6-i}')+t(520,yy(v2)+4,f'+{v2-v1}점')
 body+=t(180,324,'이전','text-anchor="middle"')+t(440,324,'이후','text-anchor="middle"')+t(24,360,'표시 학생 1→6의 변화량: 6 · 8 · 5 · 7 · 4 · 6점')
 f3=fig('pairs','같은 학생 6명의 수업 전후 점수와 짝별 변화량 (점)',body,'그림 3. 같은 학생 6명의 수업 전후 평가 점수를 가정한 별도 예제입니다. 점수는 200점 만점이며 전후 변화만으로 수업의 인과효과를 알 수는 없습니다.',385)
 display_pairs=[{'student':i+1,'before':v1,'after':v2,'change':v2-v1} for i,(v1,v2) in enumerate(zip(reversed(before),reversed(after)))]
 controls='''<div class="gg-paired-controls" hidden><div class="gg-actions" role="group" aria-label="대응표본 그래프 보기"><button type="button" id="gg-original" aria-pressed="true">원래 점수 보기</button><button type="button" id="gg-changes" aria-pressed="false">변화량 보기</button></div><p id="gg-paired-status" role="status" aria-live="polite">원래 점수 보기: 같은 학생의 이전·이후 점수를 연결합니다.</p><p class="gg-formula">평균 변화 6.00점 · 변화량의 표본 s≈1.414점 · SE≈0.577점 · 자유도 5 · 평균 변화의 95% 구간 4.52~7.48점</p><p class="learn-source-note">학생 번호는 표시용입니다. 기존 여섯 점수 쌍을 높은 이전 점수부터 표시한 순서이며, 원자료의 값과 짝 연결은 바꾸지 않았습니다. 실제 수업 효과를 검증한 자료가 아닙니다.</p></div>'''
 paired_data={'rows':display_pairs,'mean':dm,'sd':ds,'se':dse,'df':5,'low':paired['low'],'high':paired['high']}
 f3=f3.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="gg-paired">').replace('<figcaption',controls+'<script type="application/json" id="gg-paired-data">'+json.dumps(paired_data,ensure_ascii=False)+'</script><figcaption')
 body=t(24,28,'원 단위 평균 차이와 Cohen의 d: 서로 다른 척도입니다')
 for i,(label,value,scale,maximum,unit) in enumerate([('원 단위 차이',w['difference'],4,100,'만원/㎡'),('Cohen의 d',w['d'],200,2,'단위 없음')]):
  y=80+i*115;body+=t(24,y+18,label)+f'<rect x="160" y="{y}" width="{value*scale}" height="26" fill="#2563eb" data-effect="{i}"/>'+t(170+value*scale,y+19,f'{value:.2f} {unit}')+line(160,y+40,560,y+40)
  for tick in [0,maximum/2,maximum]:body+=t(160+tick*scale,y+62,f'{tick:g}','text-anchor="middle"')
 body+=t(24,300,f'd = 평균 차이 {w["difference"]:.2f} / 합동 s_p {w["pooled_sd"]:.2f} ≈ {w["d"]:.2f}')+t(24,335,'행마다 단위와 눈금이 다릅니다. 막대 길이를 직접 비교하지 않습니다.')
 f4=fig('effect','서로 다른 척도 · 평균 차이와 합동 표준편차로 표준화한 d',body,'그림 4. 위 막대는 평균 차이 80.27만원/㎡, 아래 막대는 단위 없는 Cohen의 d≈1.12입니다. 분모는 합동 표본표준편차 약 71.82만원/㎡입니다. 두 막대는 축척이 달라 길이를 비교할 수 없으며, 집단별 분산 차이가 커 d만으로 큰 효과라고 단정하지 않습니다.',365)
 page=ROOT/'comparing-groups/index.html';old=page.read_text(encoding='utf-8')
 recap=re.search(r'<section class="learn-chapter__step" id="recap".*?</section>',old,re.S)[0]
 references=re.search(r'<details class="learn-more"><summary>참고자료</summary>.*?</details>',recap,re.S)[0]
 macro=re.search(r'<section class="learn-chapter__step" id="macro".*?</section>',old,re.S)[0]
 macro_body=re.sub(r'^.*?</h2>','',macro,flags=re.S).removesuffix('</section>')
 macro_tail=re.sub(r'^<p>.*?</p>','',macro_body,count=1,flags=re.S)
 parts=[];source=(ROOT/'comparing-groups/content.md').read_text(encoding='utf-8').replace('\\*','*').replace('**','').replace('\\~','~')
 # The supplied copy ends mid-sentence; retain the existing complete Macro
 # ending and recap rather than showing the unfinished fragment.
 source=re.sub(r'^같은 단가 단위를 사용하더라도 집단\s*$','',source,flags=re.M)
 ids=['quick-start','design','welch','example','paired','effect','sensitivity','report','practice','macro']
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
   if re.fullmatch(r'\d+\. (평균 차이|차이의 표준오차|Welch 검정통계량|차이의 95% 신뢰구간)',line):out.append('<p class="gg-step-title">'+inline(line)+'</p>');i+=1;continue
   if line.startswith('- ') or re.match(r'\d+\. ',line):
    ordered=not line.startswith('- ');tag='ol' if ordered else 'ul';items=[]
    while i<len(lines) and (re.match(r'\d+\. ',lines[i]) if ordered else lines[i].startswith('- ')):
     items.append('<li>'+inline(re.sub(r'^(?:- |\d+\. )','',lines[i]))+'</li>');i+=1
    out.append('<'+tag+'>'+''.join(items)+'</'+tag+'>');continue
   formula=line.startswith(('Δ̂ =','SE(','t =','d =','dᵢ =','s_p =','ν =','평균 차이의 신뢰구간','186.47 −','24.47~'))
   out.append('<p'+(' class="gg-formula"' if formula else '')+'>'+inline(line)+'</p>');i+=1
  return '\n'.join(out)
 for id,section in zip(ids,re.split(r'^## ',source,flags=re.M)[1:],strict=True):
  label,body=section.split('\n',1);heading=re.search(r'^### (.+)$',body,re.M)[1];body=re.sub(r'^### .+\n','',body,count=1,flags=re.M)
  if id=='practice':
   items=[]
   for q in re.split(r'^\d+\. ',body,flags=re.M)[1:]:
    question,answer=q.split('▶ 답과 해설',1);items.append('<li>'+inline(question.strip())+'<details><summary>답과 해설</summary><div class="learn-more__body">'+render(answer)+'</div></details></li>')
   html='<ol class="learn-exercises">'+''.join(items)+'</ol>'
  else:html=render(body)
  if id=='quick-start':html=html.replace('<ul>','<ul class="learn-objectives">',1).replace('13장에서 배운 가설검정','<a href="/learn/stats/hypothesis-tests/">13장에서 배운 가설검정</a>')
  if id=='example':
   html=html.replace(f2,f2+'<p class="learn-source-note">차이의 95% 신뢰구간이 0을 포함하지 않으면, 같은 가정의 양측 5% 검정에서 귀무가설을 기각합니다.</p>')
   html+='<p class="learn-source-note"><a href="/learn/stats/graphs/#data">공통 학습 자료 30건</a> · <a href="../group-comparison-example.json">계산 JSON</a>. 원자료의 Welch 구간 하한은 24.474513…이며 24.47로 표시합니다. 반올림된 평균과 표준편차를 다시 넣으면 24.478961…이 되어 24.48로 표시됩니다. 산식 오류가 아닌 중간 반올림의 차이입니다.</p>'
  if id=='macro':html+='<p>관측 단위와 단가 단위, 필터 조건을 맞추고, 건수와 평균만 보지 말고 분포·면적·위치·시점 구성을 함께 살펴보세요.</p>'+macro_tail
  parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{heading}</h2>{html}</section>')
 parts.append(recap)
 p=ROOT/'comparing-groups/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="두 집단 비교와 효과크기">\n'+'\n'.join(parts)+'\n</article>',html,count=1,flags=re.S)
 html=re.sub(r'(<p class="learn-chapter-relevance">).*?(</p>)',r'\1Macro 활용도 <span class="learn-relevance" aria-label="Macro 활용도 2단계, 권장"><span aria-hidden="true">★★☆</span></span>\2',html,count=1)
 html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1독립표본과 대응표본, Welch 평균 차이와 신뢰구간, 효과크기를 예제와 그림으로 설명합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);html=html.replace('별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.','활용도는 CH2 Macro의 분석 결과를 이해하는 데 얼마나 도움이 되는지를 나타냅니다.')
 if 'comparing-groups/chapter.css' not in html:html=html.replace('</head>','<link rel="stylesheet" href="/learn/stats/comparing-groups/chapter.css?v=20261024-1" />\n  </head>')
 if 'comparing-groups/experiment.js' not in html:html=html.replace('</body>','<script type="module" src="/learn/stats/comparing-groups/experiment.js?v=20261024-1"></script>\n  </body>')
 p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
