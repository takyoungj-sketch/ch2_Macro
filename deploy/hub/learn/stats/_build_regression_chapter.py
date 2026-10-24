"""Generate chapter 17 using exact ordinary least squares from shared data."""
from pathlib import Path
from statistics import mean
from html import escape
import math,json,re
ROOT=Path(__file__).resolve().parent

def fit(x,y):
 xm,ym=mean(x),mean(y);sxx=sum((v-xm)**2 for v in x);sxy=sum((a-xm)*(b-ym) for a,b in zip(x,y));b=sxy/sxx;a=ym-b*xm;res=[v-(a+b*u) for u,v in zip(x,y)];sse=sum(e*e for e in res);sst=sum((v-ym)**2 for v in y)
 return {'intercept':a,'slope':b,'xmean':xm,'ymean':ym,'Sxx':sxx,'Sxy':sxy,'residuals':res,'SSE':sse,'R2':1-sse/sst}


def macro_details():
 return '''<details class="learn-more"><summary>실제 토지 회귀분석 구현에서 확인한 항목</summary><div class="learn-more__body"><p>확인한 토지 회귀의 종속변수는 거래총액이 아니라 거래단가(만원/㎡)입니다. 선형 모형과 log(단가) 모형을 구분합니다. 면적은 ㎡ 또는 log(면적)으로 투입할 수 있고, 선택한 경우 연도 추세는 중심화하며 공시지가는 로그로 투입합니다. 설명변수를 여러 개 선택하면 이 장의 단순회귀와 달리 다중회귀가 됩니다.</p><p>도로조건·거래유형·법정동 등 범주형 변수는 기준 범주를 둔 더미로 처리합니다. 확인한 토지 설계행렬은 선택한 변수와 더미를 더하는 구조이며 상호작용항을 자동으로 추가하지 않습니다. 다른 앱의 모형 구조까지 같다고 전제하지 않습니다.</p><p>지역·기간·유형 등 요청 필터로 추린 거래에서 단가·면적 결측을 제외하고, 선택한 IQR 이상치 제외와 공시지가의 양수·결측 조건도 반영합니다. 범주형 결측은 선택한 정책에 따라 미상 범주로 처리하거나 행을 제외하므로, 정책과 제외 건수도 확인해야 합니다. 화면의 n은 최종 적합에 사용한 관측수입니다. 같은 단지·지역·시점 거래의 의존성이 이 처리만으로 해소되지는 않습니다.</p><p>절편을 포함한 OLS를 적합하고 계수·일반 표준오차·t값·p값을 산출합니다. 이 경로는 군집 또는 강건한 표준오차를 자동 적용하지 않습니다. 계수별 검정은 다른 포함 변수를 고려한 계수=0 가설이며 이 장의 단순 기울기와 구별합니다. 효과 표의 표준오차와 t값은 소수 둘째 자리, p값은 다섯째 자리까지 표시합니다. 반올림된 0.00000은 확률이 정확히 0이라는 뜻이 아닙니다.</p><p>R²·조정 R²·표본수와 예측 성능은 구별해야 합니다. 특히 로그 모형의 R²는 log(단가) 척도의 표본 내 적합도입니다. 높은 R²가 별도 거래의 정확도를 보장하지 않습니다. 예측 입력 면적과 연도가 학습 범위를 벗어나면 외삽 안내가 제공됩니다. 적용 범위를 점검하는 기능이며 시장의 타당한 가격이나 인과효과를 보증하지 않습니다.</p></div></details>'''

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];x=[r['area'] for r in rows];y=[r['price'] for r in rows];d=fit(x,y);a,b=d['intercept'],d['slope'];pred=lambda v:a+b*v
 smallx=[1,2,3];smally=[2,2,5];small=fit(smallx,smally);other=[r for r in rows if r['id']!=7];reduced=fit([r['area'] for r in other],[r['price'] for r in other]);result={'description':'공통 학습 자료 30건의 면적(㎡)·거래단가(만원/㎡) OLS 계산과 별도 가상 세 점.','fit':d,'without_id7':reduced,'small':{'x':smallx,'y':smally,'fit':small},'predictions':{str(v):pred(v) for v in [100,200,400]}}
 (ROOT/'regression-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def t(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def line(x,y,xx,yy,c='#64748b',extra=''):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{c}" {extra}/>'
 def fig(id,title,body,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{body}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 body=t(24,28,f'ŷ={a:.3f} {b:+.4f}×X')+line(70,320,580,320)+line(70,55,70,320)
 for row in rows:body+=f'<circle cx="{70+row["area"]*1.5}" cy="{320-row["price"]*.5}" r="4" fill="#2563eb" data-id="{row["id"]}"><title>{row["id"]}번 · 면적 {row["area"]}㎡ · 단가 {row["price"]}만원/㎡</title></circle>'
 body+=line(70+min(x)*1.5,320-pred(min(x))*.5,70+max(x)*1.5,320-pred(max(x))*.5,'#d97706','stroke-width="3" data-fit="true"')
 for v in [0,100,200,300]:body+=t(70+v*1.5,345,v,'text-anchor="middle"')
 for v in [0,100,200,300,400,500]:body+=t(58,325-v*.5,v,'text-anchor="end"')
 body+=t(24,52,'거래단가(만원/㎡)')+t(430,380,'면적(㎡)')
 body+='<line id="rg-selected-residual" x1="0" x2="0" y1="0" y2="0" stroke="#0f766e" stroke-width="3" stroke-dasharray="4 3" hidden=""/>'
 f1=fig('fit','면적과 거래단가의 OLS 회귀직선 및 관측값',body,'그림 1. 공통 학습 자료 30건의 절편 포함 OLS입니다. 가로축은 면적(㎡), 세로축은 단가(만원/㎡)입니다. 파란 점은 관측값, 주황 실선은 관측 면적 22~310㎡의 회귀직선입니다.',407)
 controls='<div class="rg-controls" hidden><label for="rg-observation">관측값의 잔차 확인</label><select id="rg-observation"><option value="">관측값 선택</option>'+''.join(f'<option value="{row["id"]}">{row["id"]}번 · {row["group"]} · {row["area"]}㎡</option>' for row in rows)+'</select><p id="rg-observation-status" role="status" aria-live="polite">관측값을 선택하면 그 점의 세로 잔차만 표시합니다.</p></div>'
 f1=f1.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="rg-fit">').replace('<svg',controls+'<svg',1).replace('<svg ', '<svg class="rg-fit-svg" ',1)
 body=t(24,28,'세로 잔차를 제곱해 더합니다: 가상 세 점')+line(70,290,550,290)+line(70,45,70,290)
 px=lambda v:70+v*140;py=lambda v:290-v*43
 body+=line(px(.5),py(-.0+1.5*.5),px(3.2),py(1.5*3.2),'#d97706','stroke-width="2"')
 for xx,yy,e in zip(smallx,smally,small['residuals']):
  hat=small['intercept']+small['slope']*xx;body+=line(px(xx),py(yy),px(xx),py(hat),'#0f766e' if e>0 else '#b45309',f'stroke-width="3" data-residual="{e}"')+f'<circle cx="{px(xx)}" cy="{py(yy)}" r="5" fill="#2563eb"/>'+f'<rect x="{px(xx)-4}" y="{py(hat)-4}" width="8" height="8" fill="none" stroke="#d97706" stroke-width="2"/>'+t(px(xx)+12,py(yy),f'e={e:+.1f}')
 for v in [1,2,3]:body+=t(px(v),316,v,'text-anchor="middle"')

 for v in [0,2,4]:body+=t(58,py(v)+5,v,'text-anchor="end"')
 body+=t(24,52,'Y')+t(550,316,'X')+t(24,350,'점'+': 관측값 · 빈 네모: 적합값 · 청록: 양의 잔차 / 주황: 음의 잔차')+t(24,380,'ŷ=1.5X · 잔차 합=0 · SSE=0.5²+(−1)²+0.5²=1.5')
 f2=fig('residuals','관측값과 적합값의 차이',body,'그림 2. 별도 가상 (1,2)·(2,2)·(3,5) 예제입니다. 잔차는 같은 X에서의 세로 차이이며 점에서 직선까지의 최단거리가 아닙니다. 축은 단위 없는 가상 변수입니다.',410)
 f2=f2.replace('<svg ', '<svg class="rg-residual-svg" ',1)
 body=t(24,28,'기울기와 잔차제곱합(SSE) · 각 기울기마다 절편 재계산')
 pts=[]
 for i in range(101):
  slope=-1.2+i*.01;inter=mean(y)-slope*mean(x);sse=sum((v-inter-slope*u)**2 for u,v in zip(x,y));cx=80+(slope+1.2)*450;cy=285-(sse-d['SSE'])/250;pts.append((cx,cy))
 body+=line(70,285,560,285)+ '<polyline points="'+' '.join(f'{xx:.5f},{yy:.5f}' for xx,yy in pts)+'" fill="none" stroke="#2563eb" stroke-width="2"/>'
 body+=f'<circle cx="{80+(b+1.2)*450}" cy="285" r="5" fill="#d97706" id="rg-optimum"/>'
 for val in [-1.2,-1,-.8,-.6,-.4,-.2]:body+=t(80+(val+1.2)*450,312,f'{val:.1f}','text-anchor="middle"')
 body+=f'<circle id="rg-current" cx="{80+(b+1.2)*450}" cy="285" r="7" fill="none" stroke="#0f766e" stroke-width="3"/>'
 for delta in [0,20000,40000]:body+=t(65,290-delta/250,f'{d["SSE"]+delta:,.0f}','text-anchor="end"')
 body+=t(450,335,'기울기 b₁')
 body+=t(24,360,f'최소 기울기 {b:.4f} · 최소 SSE {d["SSE"]:,.2f}')+t(24,390,'세로축: SSE (만원/㎡)² · 주황 점: OLS 최소 · 청록 원: 현재값')
 body+='<g class="rg-line-panel" transform="translate(0 420)">'+t(24,28,'같은 30건에 현재 직선을 적용합니다 · 인과효과가 아닙니다')+line(70,320,580,320)+line(70,60,70,320)+line(70,280,580,280,'#94a3b8','stroke-dasharray="4 3"')
 for row in rows:body+=f'<circle cx="{70+row["area"]*1.5}" cy="{280-row["price"]*.4}" r="4" fill="#2563eb" data-experiment-id="{row["id"]}"/>'
 body+=line(70+22*1.5,280-pred(22)*.4,70+310*1.5,280-pred(310)*.4,'#d97706','stroke-width="3" id="rg-current-line"')
 for v in [0,100,200,300]:body+=t(70+v*1.5,345,v,'text-anchor="middle"')
 for v in [-100,0,100,300,500]:body+=t(58,285-v*.4,v,'text-anchor="end"')
 body+=t(24,52,'단가(만원/㎡)')+t(440,380,'면적(㎡)')+'</g>'
 f3=fig('objective','기울기에 따른 잔차제곱합',body,'그림 3. 기울기마다 절편을 ȳ−b₁x̄로 맞춥니다. 위의 SSE 곡선과 아래의 직선은 같은 학습 자료 30건을 사용합니다. SSE 곡선은 확률분포나 신뢰구간이 아닙니다.',830)
 controls=f'<div class="rg-controls" hidden><label for="rg-slope">기울기 b₁ 조절</label><input type="range" id="rg-slope" min="-1.2" max="-0.2" step="any" value="{b}" aria-describedby="rg-slope-help"><p id="rg-slope-help" class="learn-source-note">범위 −1.2~−0.2 · 방향키로 0.001씩 조절합니다. 매번 절편을 ȳ−b₁x̄로 계산합니다.</p><button type="button" id="rg-reset">OLS 최적값으로 복원</button><p id="rg-experiment-status" role="status" aria-live="polite"></p><p class="learn-source-note">그림 1의 OLS 기준선은 고정됩니다. 실험에서 바뀌는 직선은 이 그림의 아래 패널입니다.</p></div>'
 f3=f3.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="rg-experiment">').replace('<svg',controls+'<script type="application/json" id="rg-rows">'+json.dumps(rows,ensure_ascii=False)+'</script><svg',1)
 f3=f3.replace('<svg ', '<svg class="rg-experiment-svg" ',1)
 body=t(24,28,'관측 범위 밖의 직선 연장은 별도 가정입니다');xx=lambda v:70+v*1.2;yy=lambda v:280-v*.7
 body+=f'<rect x="{xx(22)}" y="55" width="{(310-22)*1.2}" height="275" fill="#2563eb" opacity=".06"/>'+line(70,80,70,330)+line(70,280,580,280,'#64748b','stroke-width="2" data-zero="true"')+line(xx(22),yy(pred(22)),xx(310),yy(pred(310)),'#2563eb','stroke-width="3"')+line(xx(310),yy(pred(310)),xx(400),yy(pred(400)),'#d97706','stroke-width="3" stroke-dasharray="5 4"')
 for val in [100,200,400]:body+=f'<circle cx="{xx(val)}" cy="{yy(pred(val))}" r="5" fill="#2563eb"/>'+t(xx(val)-5,yy(pred(val))-14,f'{pred(val):.2f}','text-anchor="middle"')
 for val in [22,100,200,310,400]:body+=t(xx(val),350,val,'text-anchor="middle"')

 for val in [-50,0,100,200]:body+=t(58,yy(val)+5,val,'text-anchor="end"')
 body+=t(24,52,'단가(만원/㎡)')+t(400,385,'면적(㎡)')+t(24,415,'옅은 배경·실선: 관측 범위 22~310㎡ / 주황 점선: 외삽')
 f4=fig('extrapolation','내삽과 외삽',body,'그림 4. 세로축은 단가(만원/㎡)이며 기준선은 단가 0입니다. 400㎡는 관측 범위 밖이고 계산값 −41.21만원/㎡는 비현실적입니다. 시장 가격 전망으로 해석하지 않습니다.',445)
 page=ROOT/'regression/index.html';old=page.read_text(encoding='utf-8')
 references=re.search(r'<details class="learn-more"><summary>참고자료</summary>.*?</details>',old,re.S)[0].replace('세 점 예제와 식 ŷ=20+5x는 원리를 설명하기 위한 가상 예시입니다.','세 점 예제는 원리를 설명하기 위한 별도 가상 자료입니다.').replace('30쌍 계산은 공통 학습 자료의 두 수치열을 단위 없는 X,Y로 사용했습니다.','30건 계산은 공통 학습 자료의 면적(㎡)과 거래단가(만원/㎡)를 사용했습니다.')
 parts=[];source=(ROOT/'regression/content.md').read_text(encoding='utf-8').replace('\\*','*').replace('**','').replace('\\~','~')
 formulas={r'e_i=y_i-\hat y_i':'eᵢ = yᵢ − ŷᵢ',r'SSE=\sum\_{i=1}^{n}[y_i-(b_0+b_1x_i)]^2':'SSE = Σᵢ₌₁ⁿ [yᵢ − (b₀ + b₁xᵢ)]²',r'b_1=\frac{\sum (x_i-\bar x)(y_i-\bar y)}{\sum (x_i-\bar x)^2}':'b₁ = Σ(xᵢ−x̄)(yᵢ−ȳ) / Σ(xᵢ−x̄)²',r'b_0=\bar y-b_1\bar x':'b₀ = ȳ − b₁x̄',r'R^2=1-\frac{SSE}{SST}':'R² = 1 − SSE / SST',r'b_1=r\frac{s_y}{s_x}':'b₁ = r × sᵧ / sₓ',r'R^2=r^2':'R² = r²'}
 source=re.sub(r'^\[\s*\n(.*?)\n\]$',lambda m:formulas[m[1].strip()],source,flags=re.M|re.S)
 ids=['quick-start','core','coefficients','residuals','ols','objective','prediction','extrapolation','correlation','assumptions','sensitivity','practice','macro','recap']
 def inline(value):return re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',escape(value))
 def render(block):
  out=[];lines=block.strip().split('\n');i=0
  while i<len(lines):
   line=lines[i].strip()
   if not line or line=='---':i+=1;continue
   if line.startswith('### '):out.append('<h3>'+inline(line[4:])+'</h3>');i+=1;continue
   if line.startswith('[그림 '):out.append({1:f1,2:f2,3:f3,4:f4}[int(re.search(r'그림 (\d)',line)[1])]);i+=1;continue
   if line=='[CH2 Macro 통계·데이터분석 열기 →]':out.append('<p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 통계·데이터분석 열기 →</a></p>');i+=1;continue
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
   formula=line.startswith(('ŷ','Y =','eᵢ','SSE','b₀','b₁','R²','잔차 =','10 ×','(만원/㎡)',"X' ="))
   out.append('<p'+(' class="rg-formula"' if formula else '')+'>'+inline(line)+'</p>');i+=1
  return '\n'.join(out)
 for id,section in zip(ids,re.split(r'^## ',source,flags=re.M)[1:],strict=True):
  label,body=section.split('\n',1);heading=re.search(r'^### (.+)$',body,re.M)[1];body=re.sub(r'^### .+\n','',body,count=1,flags=re.M)
  if id=='practice':
   items=[]
   for q in re.split(r'^\d+\. ',body,flags=re.M)[1:]:
    question,answer=q.split('▶ 답과 해설',1);items.append('<li>'+inline(question.strip())+'<details><summary>답과 해설</summary><div class="learn-more__body">'+render(answer)+'</div></details></li>')
   html='<ol class="learn-exercises">'+''.join(items)+'</ol>'
  else:html=render(body)
  if id=='quick-start':html=html.replace('<ul>','<ul class="learn-objectives">',1).replace('16장에서 배운 상관계수','<a href="/learn/stats/correlation/">16장에서 배운 상관계수</a>')+'<p class="learn-source-note"><a href="/learn/stats/graphs/#data">공통 학습 자료 30건</a> · <a href="../regression-example.json">계수·잔차·계산 결과 JSON</a>. 실제 거래 출처와 대표성이 확인되지 않은 학습 자료입니다.</p>'
  if id=='objective':html=html.replace('세로축은 잔차제곱합입니다.','세로축은 잔차제곱합(SSE)입니다. 세로 눈금은 0이 아닌 최소 SSE 부근에서 시작합니다.')
  if id=='sensitivity':html+='<p class="learn-source-note">원자료 id=7(상업, 면적 22㎡, 단가 480만원/㎡) 한 건만 제외해 29건으로 계수와 절편을 모두 다시 계산했습니다. 상관계수의 변화와 기울기의 변화는 다른 수치입니다.</p>'
  if id=='macro':html+=macro_details()
  if id=='recap':html=html.replace('18장 「잔차와 회귀모형의 가정」','<a href="/learn/stats/residuals/">18장 「잔차와 회귀모형의 가정」</a>')
  parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{heading}</h2>{html}</section>')
 p=ROOT/'regression/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="단순선형회귀와 최소제곱법">\n'+'\n'.join(parts)+'\n</article>',html,count=1,flags=re.S)
 html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1단순선형회귀의 기울기·절편·잔차와 최소제곱 계산, 예측·외삽의 한계를 설명합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);
 html=html.replace('별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.','활용도는 CH2 Macro의 분석 결과를 이해하는 데 얼마나 도움이 되는지를 나타냅니다.')
 if 'regression/chapter.css' not in html:html=html.replace('</head>','<link rel="stylesheet" href="/learn/stats/regression/chapter.css?v=20261024-1" />\n</head>')
 if 'regression/experiment.js' not in html:html=html.replace('</body>','<script type="module" src="/learn/stats/regression/experiment.js?v=20261024-1"></script>\n</body>')
 p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
