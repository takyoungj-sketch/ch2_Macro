"""Chapter 15: one-way ANOVA, Tukey and categorical independence."""
from pathlib import Path
from statistics import mean
from html import escape
import json,math,re
from scipy.stats import f,chi2,tukey_hsd
ROOT=Path(__file__).resolve().parent
GROUPS=[[90,100,110,100],[110,120,130,120],[130,140,150,140]]
COUNTS=[[30,20],[20,30],[10,40]]
def build():
 groups=GROUPS;allv=sum(groups,[]);grand=mean(allv);ssb=sum(len(g)*(mean(g)-grand)**2 for g in groups);ssw=sum(sum((x-mean(g))**2 for x in g) for g in groups);F=(ssb/2)/(ssw/9);p=float(f.sf(F,2,9));eta=ssb/(ssb+ssw)
 tuk=tukey_hsd(*groups);ci=tuk.confidence_interval();pairs=[{'label':f'{"ABC"[i]}−{"ABC"[j]}','i':i,'j':j,'difference':float(tuk.statistic[i,j]),'p':float(tuk.pvalue[i,j]),'low':float(ci.low[i,j]),'high':float(ci.high[i,j])} for i,j in [(1,0),(2,0),(2,1)]]
 expected=[[20,30] for _ in COUNTS];contrib=[[(o-e)**2/e for o,e in zip(row,ex)] for row,ex in zip(COUNTS,expected)];stat=sum(map(sum,contrib));cp=float(chi2.sf(stat,2));V=math.sqrt(stat/150)
 result={'description':'15장 전용 가상 예제. 평가 점수 12개와 동아리 참여 여부 150명은 서로 다른 가상 자료.','groups':groups,'anova':{'grand_mean':grand,'between_ss':ssb,'within_ss':ssw,'F':F,'df':[2,9],'p':p,'eta_squared':eta},'tukey':pairs,'categorical':{'observed':COUNTS,'expected':expected,'contributions':contrib,'chi2':stat,'df':2,'p':cp,'V':V}}
 (ROOT/'multiple-groups-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def t(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def line(x,y,xx,yy,c='#64748b',extra=''):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{c}" {extra}/>'
 def fig(id,title,b,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=t(24,28,'세 집단의 평균 차이와 집단 안의 퍼짐을 함께 봅니다');x=lambda v:80+(v-80)*6
 for i,g in enumerate(groups):
  y=90+i*85;b+=t(24,y+5,'ABC'[i])+line(80,y,560,y)
  for j,v in enumerate(g):b+=f'<circle cx="{x(v)}" cy="{y-(12 if v in g[:j] else 0)}" r="5" fill="#2563eb" data-group="{i}" data-value="{v}"><title>{"ABC"[i]} 관측 {j+1}: {v}점</title></circle>'
  b+=line(x(mean(g)),y-24,x(mean(g)),y+15,'#d97706')+t(x(mean(g)),y-32,f'평균 {mean(g):g} · n=4','text-anchor="middle"')
 for v in [80,100,120,140,160]:b+=t(x(v),310,v,'text-anchor="middle"')
 b+=t(350,342,'평가 점수(점) · 주황선: 평균')
 f1=fig('groups','A·B·C의 시험 점수 분포와 평균 (점)',b,'그림 1. A=90·100·110·100, B=110·120·130·120, C=130·140·150·140인 별도 가상 자료입니다. 200점 만점의 평가 점수이며 각 집단은 4명입니다. 점의 세로 간격은 겹침을 구분하기 위한 표시입니다.',370)
 b=t(24,28,'집단 간·집단 내 제곱합(SS) 비교 · 단위: 점²')
 for i,(label,value) in enumerate([('집단 간',ssb),('집단 내',ssw)]):
  y=85+i*85;b+=t(24,y+20,label)+f'<rect x="150" y="{y}" width="{value*.11}" height="28" fill="#2563eb" data-ss="{value}"/>'+t(160+value*.11,y+20,f'{value:,.0f}')
 b+=line(150,225,546,225)
 for tick in [0,1000,2000,3000]:b+=t(150+tick*.11,250,f'{tick:,}','text-anchor="middle"')
 b+=t(24,288,'SS 합계 3,800점²')+t(24,320,'F = MSB / MSW · 평균제곱 계산은 아래에서 확인합니다')
 f2=fig('variation','집단 간 SS 3,200과 집단 내 SS 600 (점²)',b,'그림 2. 집단 간 SS=3,200, 집단 내 SS=600입니다. 평균제곱은 각각 1,600과 66.67이며 F=24입니다. 막대 길이는 제곱합에 비례합니다.',350)
 b=t(24,28,'모든 쌍을 함께 고려한 Tukey 95% 동시 신뢰구간');xx=lambda v:115+v*6
 b+=line(xx(0),50,xx(0),295,'#d97706','stroke-dasharray="4 3"')
 for i,d in enumerate(pairs):
  y=90+i*85;b+=t(24,y+4,d['label'])+line(xx(d['low']),y,xx(d['high']),y,'#2563eb',f'stroke-width="3" data-pair="{i}"')+f'<circle cx="{xx(d["difference"])}" cy="{y}" r="4" fill="#2563eb"/>'+t(xx(d['low']),y+24,f'{d["low"]:.2f}','text-anchor="middle"')+t(xx(d['high']),y+24,f'{d["high"]:.2f}','text-anchor="middle"')

 for tick in [0,20,40,60]:b+=t(xx(tick),317,tick,'text-anchor="middle"')
 b+=t(24,344,'점: 평균 차이 · 선: 95% 동시구간 · 점선: 차이 0 (단위: 점)')
 f3=fig('tukey','다중비교를 반영한 쌍별 구간',b,'그림 3. 정규성·독립성·등분산을 가정한 Tukey HSD입니다. 세 쌍 전체의 동시 포함률을 다루며 보정 없는 개별 95% 구간을 나열한 그림과 다릅니다.',372)
 b=t(24,28,'집단 내 참여·비참여 비율 · 분모: 각 집단 50명','id="mg-chart-heading"')
 for i,row in enumerate(COUNTS):
  y=70+i*85;ratio=row[0]/sum(row)
  b+=t(24,y+20,f'{"ABC"[i]} · 50명',f'data-label="{i}"')
  b+=f'<rect x="150" y="{y}" width="{ratio*400}" height="30" fill="#2563eb" data-row="{i}"/><rect x="{150+ratio*400}" y="{y}" width="{(1-ratio)*400}" height="30" fill="#cbd5e1" data-non="{i}"/>'
  b+=t(150,y+54,f'참여 {row[0]}/50 = {ratio:.0%} · 비참여 {row[1]}/50 = {1-ratio:.0%}',f'data-ratio="{i}"')
 b+=line(150,303,550,303)
 for tick in [0,25,50,75,100]:b+=t(150+tick*4,328,f'{tick}%','text-anchor="middle"')
 b+=t(24,363,'파랑: 참여 · 회색: 비참여 · 각 행 합계 100%','id="mg-legend"')
 f4=fig('categorical','분모에 따른 동아리 참여 비율 비교',b,'그림 4. 별도 가상 학생 150명입니다. 각 집단 50명을 분모로 참여·비참여 비율을 표시합니다. 앞의 시험 점수 12개와 다른 자료입니다.',390)
 controls='''<div class="mg-controls" hidden><label for="mg-mode">비율의 기준</label><select id="mg-mode"><option value="group">집단 내 비율</option><option value="participants">참여자 구성비</option><option value="total">전체 학생 대비 비율</option></select><p id="mg-status" role="status" aria-live="polite">각 집단 50명이 분모입니다. 각 행의 합계는 100%입니다.</p><p class="learn-source-note">비율 보기만 바뀝니다. 카이제곱 검정은 원래 관측도수 30·20 / 20·30 / 10·40으로 계산하며 χ²≈16.6667, p≈0.0002404, V≈0.3333으로 유지됩니다.</p></div>'''
 f4=f4.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="mg-proportions">').replace('<svg',controls+'<script type="application/json" id="mg-counts">'+json.dumps(COUNTS)+'</script><svg',1)
 page=ROOT/'multiple-groups-and-categorical/index.html';old=page.read_text(encoding='utf-8')
 references=re.search(r'<details class="learn-more"><summary>참고자료</summary>.*?</details>',old,re.S)[0]
 parts=[];source=(ROOT/'multiple-groups-and-categorical/content.md').read_text(encoding='utf-8').replace('\\*','*').replace('**','').replace('\\~','~')
 formulas={r'SS_T=SS_B+SS_W':'SS_T = SS_B + SS_W',r'\chi^2=\sum\frac{(O-E)^2}{E}':'χ² = Σ [(O − E)² / E]',r'V=\sqrt{\frac{\chi^2}{N\min(r-1,c-1)}}':'V = √[χ² / (N × min(r−1, c−1))]'}
 source=re.sub(r'\\\[\s*(.*?)\s*\\\]',lambda m:formulas[m[1].strip()],source,flags=re.S)
 ids=['quick-start','anova','variation','posthoc','assumptions','categorical','chi-square','categorical-effect','sparse','practice','macro','recap']
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
   if re.fullmatch(r'\d+\. (집단 간 평균제곱|집단 내 평균제곱|F통계량|[ABC] 집단)',line):out.append('<p class="mg-step-title">'+inline(line)+'</p>');i+=1;continue
   if line.startswith('- ') or re.match(r'\d+\. ',line):
    ordered=not line.startswith('- ');tag='ol' if ordered else 'ul';items=[]
    while i<len(lines) and (re.match(r'\d+\. ',lines[i]) if ordered else lines[i].startswith('- ')):
     items.append('<li>'+inline(re.sub(r'^(?:- |\d+\. )','',lines[i]))+'</li>');i+=1
    out.append('<'+tag+'>'+''.join(items)+'</'+tag+'>');continue
   formula=line.startswith(('SS','MS','F =','χ²','V =','귀무가설 H₀:','대립가설 H₁:','기대도수 =','(행 수−1)'))
   out.append('<p'+(' class="mg-formula"' if formula else '')+'>'+inline(line)+'</p>');i+=1
  return '\n'.join(out)
 for id,section in zip(ids,re.split(r'^## ',source,flags=re.M)[1:],strict=True):
  label,body=section.split('\n',1);heading=re.search(r'^### (.+)$',body,re.M)[1];body=re.sub(r'^### .+\n','',body,count=1,flags=re.M)
  if id=='practice':
   items=[]
   for q in re.split(r'^\d+\. ',body,flags=re.M)[1:]:
    question,answer=q.split('▶ 답과 해설',1);items.append('<li>'+inline(question.strip())+'<details><summary>답과 해설</summary><div class="learn-more__body">'+render(answer)+'</div></details></li>')
   html='<ol class="learn-exercises">'+''.join(items)+'</ol>'
  else:html=render(body)
  if id=='quick-start':html=html.replace('<ul>','<ul class="learn-objectives">',1).replace('14장에서 배운 두 집단 비교','<a href="/learn/stats/comparing-groups/">14장에서 배운 두 집단 비교</a>')+'<p class="learn-source-note"><a href="../multiple-groups-example.json">원자료와 계산 결과 JSON</a></p>'
  if id=='posthoc':html+='<p class="learn-source-note">검산: k=3, 각 n=4, MSW=600/9, 자유도 9. Studentized range 임계값 q≈3.94849를 적용해 구간 반폭 q√(MSW/4)≈16.11965점을 얻습니다.</p>'
  if id=='macro':
   html=html.replace('이러한 기능이 CH2 Macro의 모든 통계 화면에서 제공된다는 뜻은 아닙니다.','확인한 토지 기본통계·매트릭스 화면은 이 장의 ANOVA·Tukey HSD·카이제곱 검정·Cramér의 V를 제공하지 않습니다.')
   html+='<details class="learn-more"><summary>실제 토지 통계의 자료 범위와 분모</summary><div class="learn-more__body"><p>토지 기본통계는 유효한 단가의 건수·평균·표본표준편차·평균의 신뢰구간 등을 제공합니다. 여러 지역을 합칠 때는 사전 집계된 분석 연도 구간의 공통 범위를 사용합니다. 매트릭스의 용도지역×지목별 셀과 전체·소계는 범위가 겹치므로, 셀에 소계를 더해 전체 건수를 다시 계산하면 중복됩니다.</p><p>기간·지역·용도·지목과 이상치 제외 여부를 맞춘 뒤 해당 범위의 유효 건수를 분모로 확인하세요. 합계·소계의 중복과 원자료의 중복 거래 여부는 별개의 점검입니다. 집계만으로 거래의 독립성이나 대표성이 입증되지는 않습니다.</p><p>Macro의 IQR 이상치 필터에 쓰이는 Tukey 펜스는 이 장의 Tukey HSD 사후 비교와 다른 방법입니다.</p></div></details>'
  if id=='recap':html=html.replace('16장 「상관관계와 인과관계」','<a href="/learn/stats/correlation/">16장 「상관관계와 인과관계」</a>')
  parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{heading}</h2>{html}</section>')
 pth=ROOT/'multiple-groups-and-categorical/index.html';pth.parent.mkdir(exist_ok=True);html=pth.read_text(encoding='utf-8') if pth.exists() else (ROOT/'comparing-groups/index.html').read_text(encoding='utf-8')
 html=html.replace('https://ch2data.com/learn/stats/comparing-groups/','https://ch2data.com/learn/stats/multiple-groups-and-categorical/')
 html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="여러 집단과 범주형 자료의 비교">\n'+'\n'.join(parts)+'\n</article>',html,count=1,flags=re.S)
 html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1ANOVA와 사후비교, 분할표와 카이제곱 검정을 가상 자료와 그림으로 설명합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);
 html=re.sub(r'(<p class="learn-chapter-relevance">).*?(</p>)',r'\1Macro 활용도 <span class="learn-relevance" aria-label="Macro 활용도 2단계, 권장"><span aria-hidden="true">★★☆</span></span>\2',html,count=1)
 html=html.replace('별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.','활용도는 CH2 Macro의 분석 결과를 이해하는 데 얼마나 도움이 되는지를 나타냅니다.')
 if 'multiple-groups-and-categorical/chapter.css' not in html:html=html.replace('</head>','<link rel="stylesheet" href="/learn/stats/multiple-groups-and-categorical/chapter.css?v=20261024-1" />\n</head>')
 if 'multiple-groups-and-categorical/experiment.js' not in html:html=html.replace('</body>','<script type="module" src="/learn/stats/multiple-groups-and-categorical/experiment.js?v=20261024-1"></script>\n</body>')
 pth.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
