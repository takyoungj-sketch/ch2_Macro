"""Reproducible fixed-design bias/variance simulation for chapter 24."""
from pathlib import Path
from html import escape
import numpy as np
import json,re
ROOT=Path(__file__).resolve().parent

def build():
 seed=20261009;rng=np.random.default_rng(seed);x=np.linspace(-1,1,12);grid=np.linspace(-1,1,201);truth=lambda z:1+z+.7*z*z;sigma=.15;degrees=[1,2,5,9];ys=truth(x)+rng.normal(0,sigma,(300,12));models=[]
 for degree in degrees:
  A=np.polynomial.legendre.legvander(x,degree);G=np.polynomial.legendre.legvander(grid,degree);coef=np.linalg.lstsq(A,ys.T,rcond=None)[0];pred=(G@coef).T;avg=pred.mean(axis=0);bias2=float(np.mean((avg-truth(grid))**2));variance=float(np.mean(np.var(pred,axis=0)));risk=float(np.mean((pred-truth(grid))**2)+sigma**2)
  models.append(dict(degree=degree,train_MSE=float(np.mean((ys-(A@coef).T)**2)),bias2=bias2,variance=variance,noise=sigma**2,expected_MSE=risk,first_curve=pred[0].tolist(),at08=(np.polynomial.legendre.legvander([.8],degree)@coef).ravel().tolist()))
 result=dict(description='가상 고정 X에서 독립 정규 오차를 300회 다시 생성한 시뮬레이션. 모형의 복잡도와 예측 오차를 설명하기 위한 자료.',seed=seed,repeats=300,sigma=sigma,x=x.tolist(),training_y=ys.tolist(),grid=grid.tolist(),truth=truth(grid).tolist(),models=models)
 (ROOT/'overfitting-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def ln(x,y,a,b):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="#94a3b8"/>'
 def fig(id,title,b,cap):return f'<figure class="learn-chart learn-chart--wide"><svg class="overfit-chart-svg" viewBox="0 0 640 420" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 colors={1:'#d97706',2:'#2563eb',5:'#64748b',9:'#9333ea'};px=lambda v:70+(v+1)*250
 chosen=models;lo=min(0,min(min(m['first_curve']) for m in chosen));hi=max(3,max(max(m['first_curve']) for m in chosen));py=lambda v:320-(v-lo)/(hi-lo)*250
 b=tx(24,28,'같은 가상 학습 12점 · 다항 차수 1·2·5·9')+ln(70,320,570,320)+ln(70,60,70,320)
 for m in chosen:b+='<polyline data-degree="'+str(m['degree'])+'" points="'+' '.join(f'{px(v)},{py(w)}' for v,w in zip(grid,m['first_curve']))+'" fill="none" stroke="'+colors[m['degree']]+'" stroke-width="2"/>'
 b+='<polyline points="'+' '.join(f'{px(v)},{py(w)}' for v,w in zip(grid,truth(grid)))+'" fill="none" stroke="#111827" stroke-dasharray="4 4"/>'
 for v,w in zip(x,ys[0]):b+=f'<circle cx="{px(v)}" cy="{py(w)}" r="4" fill="#111827"/>'
 for v in [-1,0,1]:b+=tx(px(v)-5,345,v)
 for v in np.linspace(lo,hi,4):b+=tx(25,py(v)+5,f'{v:.1f}')
 b+=tx(24,378,'주황 1차 / 파랑 2차 / 회색 5차 / 보라 9차')+tx(24,403,'검정 점: 관측 Y / 점선: 참 평균 · 가로 X / 세로 Y · 단위 없음')
 g1=fig('fits','복잡도에 따른 곡선',b,'그림 1. 첫 번째 가상 표본을 모두 표시했습니다. X·Y는 단위 없는 변수이며 참 평균은 1+X+0.7X²입니다. 관측 범위 안에서도 복잡한 곡선이 흔들릴 수 있습니다.')
 ymax=max(m['expected_MSE'] for m in models)*1.2;ey=lambda v:320-v/ymax*240
 b=tx(24,28,'300회 평균: 학습 MSE와 새 관측의 기대 MSE')+ln(70,320,570,320)+ln(70,60,70,320)
 for key,c in [('train_MSE','#2563eb'),('expected_MSE','#d97706')]:
  b+='<polyline data-metric="'+key+'" points="'+' '.join(f"{120+i*140},{ey(m[key])}" for i,m in enumerate(models))+'" fill="none" stroke="'+c+'" stroke-width="2"/>'
  for i,m in enumerate(models):b+=f'<circle data-error-degree="{m["degree"]}" cx="{120+i*140}" cy="{ey(m[key])}" r="4" fill="{c}"/>'
 for i,m in enumerate(models):b+=tx(105+i*140,350,str(m['degree'])+'차')
 for v in np.linspace(0,ymax,4):b+=tx(20,ey(v)+5,f'{v:.3f}')
 b+=tx(24,385,'파랑: 학습 / 주황: 같은 X범위의 새 오차까지 포함')
 g2=fig('errors','복잡도와 기대 오차',b,'그림 2. 선은 비교를 돕기 위해 이은 것입니다. 새 관측 기대 MSE는 201개 고정 X에서 참 평균과의 제곱차를 평균하고 오차분산 0.0225를 더했습니다. 별도의 시험 표본 점수는 아닙니다.')
 b=tx(24,28,'기대 제곱오차 = 편향² + 분산 + 잡음')+ln(70,320,570,320)
 for i,m in enumerate(models):
  bottom=320
  for key,c in [('noise','#cbd5e1'),('variance','#d97706'),('bias2','#2563eb')]:
   h=m[key]/ymax*240;b+=f'<rect data-degree="{m["degree"]}" data-part="{key}" x="{95+i*140}" y="{bottom-h}" width="65" height="{h}" fill="{c}"/>';bottom-=h
  b+=tx(100+i*140,350,str(m['degree'])+'차')
 for v in np.linspace(0,ymax,4):b+=tx(20,ey(v)+5,f'{v:.3f}')
 b+=tx(24,385,'파랑: 편향² / 주황: 분산 / 회색: 새 관측 잡음')
 g3=fig('decomposition','시뮬레이션 오차 분해',b,'그림 3. 편향과 분산은 300개 적합식으로 추정했습니다. 분산은 반복 수 300으로 나누어 계산해 이 유한 반복에서도 합이 그림 2의 기대 MSE와 일치합니다.')
 vals=[v for m in models for v in m['at08'][:30]];low=min(vals)-.1;high=max(vals)+.1;vx=lambda v:100+(v-low)/(high-low)*450;truth08=float(truth(.8))
 b=tx(24,28,'학습 오차를 다시 뽑으면 X=0.8의 예측도 달라집니다')
 for i,m in enumerate(models):
  yy=95+i*65;b+=tx(25,yy+5,str(m['degree'])+'차')+ln(90,yy,570,yy)
  for j,v in enumerate(m['at08'][:30]):b+=f'<circle data-stability-degree="{m["degree"]}" data-repeat="{j}" cx="{vx(v)}" cy="{yy+(j%3-1)*8}" r="3" fill="{colors[m["degree"]]}"/>'
 b+=f'<line x1="{vx(truth08)}" y1="65" x2="{vx(truth08)}" y2="315" stroke="#111827" stroke-dasharray="4 4"/>'
 for v in np.linspace(low,high,4):b+=tx(vx(v)-12,345,f'{v:.2f}')
 b+=tx(24,385,f'가로: 예측 Y · 점선: 참 평균 {truth08:.3f} · 처음 30회 표시')
 g4=fig('stability','표본에 따른 예측의 흔들림',b,'그림 4. 모든 반복에서 X는 같고 Y의 잡음만 달라집니다. 점의 세로 위치는 겹침을 줄이기 위한 배치이며 추가 변수나 확률을 뜻하지 않습니다.')
 ui=[]
 for m in models:
  degree=m['degree'];A=np.polynomial.legendre.legvander(x,degree);coef=np.linalg.lstsq(A,ys[0],rcond=None)[0]
  values=np.array(m['at08']);ui.append(dict(**m,first_train_MSE=float(np.mean((ys[0]-A@coef)**2)),mean08=float(values.mean()),bias08=float(values.mean()-truth08),variance08=float(values.var())))
 controls='<div class="overfit-controls" hidden=""><label for="overfit-degree">다항 차수 선택'+'</label><select id="overfit-degree"><option value="all">전체 비교</option>'+''.join(f'<option value="{degree}">{degree}차</option>' for degree in degrees)+'</select><p id="overfit-fit-status" role="status" aria-live="polite"></p></div>'
 g1=g1.replace('<svg ',controls+'<svg ',1)
 g2=g2.replace('<svg ','<p id="overfit-error-status" role="status" aria-live="polite">300회 평균 · 학습 12개 위치 / 새 관측 기대오차 201개 위치</p><svg ',1)
 g4=g4.replace('<svg ','<p id="overfit-stability-status" role="status" aria-live="polite">같은 X=0.8 · 그림은 처음 30회 / 통계량은 전체 300회</p><svg ',1)
 parts=render_content([g1,g2,g3,g4])
 p=ROOT/'overfitting/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="과적합과 편향–분산의 균형">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1과소적합·과적합과 편향–분산 분해를 반복실험으로 이해하고 복잡도와 검증의 관계를 학습합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);html=add_assets(html,ui);p.write_text(html,encoding='utf-8')

def add_assets(html,data):
 html=html.replace('별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.','활용도는 CH2 Macro의 분석 결과를 이해하는 데 얼마나 도움이 되는지를 나타냅니다.')
 if 'overfitting/chapter.css' not in html:html=html.replace('</head>','<link rel="stylesheet" href="/learn/stats/overfitting/chapter.css?v=20261025-1" /></head>')
 payload='<script type="application/json" id="overfit-data">'+json.dumps(data,ensure_ascii=False)+'</script>'
 if 'id="overfit-data"' in html:html=re.sub(r'<script type="application/json" id="overfit-data">.*?</script>',lambda _:payload,html,flags=re.S)
 else:html=html.replace('</body>',payload+'</body>')
 if 'overfitting/experiment.js' not in html:html=html.replace('</body>','<script type="module" src="/learn/stats/overfitting/experiment.js?v=20261025-1"></script></body>')
 return html

def macro_notes():
 return '<details class="learn-more"><summary>현재 확인한 Macro 구현과 교재 예제의 차이'+'</summary><div class="learn-more__body"><p>확인한 복합 회귀·지역회귀 추천은 설명형과 예측형을 구분합니다. 복합 척도 비교는 예측형에서 CV-MAPE를 우선하고 없으면 학습 MAPE 등을 참조하며, 설명형은 같은 로그 종속변수 후보의 AIC를 비교합니다. 집합 주거 지역회귀는 예측형 Holdout MAPE와 설명형 원 단위 수정 R²를 사용합니다. 교재의 MSE 분해가 이 실제 추천 기준은 아닙니다.</p><p>복합 회귀에는 연속변수 VIF와 모형 식별·계수 정보, 영향 관측 진단 경로가 있습니다. 지역회귀의 적합 최소 표본수 상수는 20이며 후보의 결측 조건과 선택 변수에 따라 유효 표본수가 달라질 수 있습니다. 최소 건수를 넘었다고 충분한 정보가 확보됐거나 계수가 안정적이라고 보장되지는 않습니다. 더미를 포함한 설계 열 수와 독립 계수 수가 다를 수도 있습니다.</p><p>이번에 확인한 복합·집합 주거 추천 경로를 교재의 1·2·5·9차 선택이나 릿지·라쏘 자동 선택 기능으로 소개하지 않습니다. 별도의 랩 scale_effect_lab에는 제곱항·릿지·라쏘 실험 코드가 있지만 일반 서비스 회귀와 구분해야 합니다. 지역·용도지역에 관계없이 임의 상호작용항을 사용할 수 있다고 가정하지 않습니다.</p><p>학습 MAPE와 탐색·확인 CV 또는 Holdout은 계산 자료와 용도가 다릅니다. 계약연도 롤링 검증이 새 단지·지역 검증까지 보장하지는 않으며, 선택에 사용한 Holdout은 독립 최종 시험과 구별합니다. 범주 전처리 경계·동일 평가 표본·과거 정보 판본은 기존 보류사항으로 이어서 점검합니다. 모든 후보에 대해 반복표집 계수 안정성이 검증된 것으로 설명하지 않습니다.</p><p>본 장의 참 평균·잡음·300회 반복 결과는 가상 실험입니다. 실제 Macro 분석·추천·자료 처리 로직은 변경하지 않았습니다.</p></div></details>'

def render_content(graphs):
 page=ROOT/'overfitting/index.html'
 old=page.read_text(encoding='utf8')
 refs=re.search(r'<details class="learn-references">.*?</details>',old,re.S)[0]
 source=(ROOT/'overfitting/content.md').read_text(encoding='utf8').replace('**','')
 formulas=['f(x) = 1+x+0.7x²','Y = f(X)+ε','Bias(x) = Eᴅ[f̂ᴅ(x)]−f(x)','Variance(x) = Varᴅ[f̂ᴅ(x)]','E[(Ynew−f̂ᴅ(x))²] = Bias(x)²+Variance(x)+σ²(x)','0.15² = 0.0225','E[(Ynew−f̂ᴅ(x))²] = [Eᴅ f̂ᴅ(x)−f(x)]²+Varᴅ[f̂ᴅ(x)]+Var(εnew | x)']
 blocks=re.findall(r'\\\[.*?\\\]',source,re.S)
 assert len(blocks)==len(formulas)
 for block,formula in zip(blocks,formulas):source=source.replace(block,formula,1)

 def inline(t):
  return re.sub(r'`([^`]+)`',r'<code>\1</code>',escape(t))
 def render(block):
  lines=block.strip().splitlines();i=0;out=[]
  while i<len(lines):
   line=lines[i].strip();i+=1
   if not line or line=='---':continue
   if line.startswith('### '):out.append('<h3>'+inline(line[4:])+'</h3>');continue
   if line.startswith('[그림 '):out.append(graphs[int(re.search(r'그림 (\d)',line)[1])-1]);continue
   if line=='[CH2 Macro 통계·데이터분석 열기 →]':out.append('<p><a href="https://macro.ch2data.com/">CH2 Macro 통계·데이터분석 열기 →</a></p>');continue
   if line=='▶ 참고자료':out.append(refs);continue
   if line.startswith('▶ '):
    rest=[]
    while i<len(lines) and lines[i].strip()!='---':rest.append(lines[i]);i+=1
    out.append('<details class="learn-more"><summary>'+inline(line[2:])+'</summary><div class="learn-more__body">'+render('\n'.join(rest))+'</div></details>');continue
   if line.startswith('|'):
    rows=[line]
    while i<len(lines) and lines[i].strip().startswith('|'):rows.append(lines[i].strip());i+=1
    cells=[[c.strip() for c in row.strip('|').split('|')] for row in rows]
    cells=[row for row in cells if not all(re.fullmatch(r'[:\- ]+',c) for c in row)]
    out.append('<div class="learn-data learn-data--full"><table><thead><tr>'+''.join('<th scope="col">'+inline(c)+'</th>' for c in cells[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join(('<th scope="row">'+inline(c)+'</th>') if j==0 else '<td>'+inline(c)+'</td>' for j,c in enumerate(row))+'</tr>' for row in cells[1:])+'</tbody></table></div>');continue
   if line.startswith('- '):
    items=[line[2:]]
    while i<len(lines) and lines[i].startswith('- '):items.append(lines[i][2:]);i+=1
    out.append('<ul>'+''.join('<li>'+inline(item)+'</li>' for item in items)+'</ul>');continue
   out.append('<p'+(' class="overfit-formula"' if line.startswith(('f(x) =','Y =','Bias(x) =','Variance(x) =','E[','0.15²','기대 예측 MSE =')) else '')+'>'+inline(line)+'</p>')
  return '\n'.join(out)
 ids=['quick-start','under-over','fits','experiment','errors','bias','variance','decomposition','stability','diagnosis','control','validation','practice','macro','recap']
 parts=[]
 for id,section in zip(ids,re.split(r'^## ',source,flags=re.M)[1:],strict=True):
  label,body=section.split('\n',1);heading=re.search(r'^### (.+)$',body,re.M)[1];body=re.sub(r'^### .+\n','',body,count=1,flags=re.M)
  if id=='practice':
   qs=[]
   for q in re.split(r'^\d+\. ',body,flags=re.M)[1:]:
    question,answer=q.split('▶ 답과 해설',1)
    qs.append('<li>'+inline(question.strip())+'<details><summary>답과 해설</summary><div class="learn-more__body">'+render(answer)+'</div></details></li>')
   content='<ol class="learn-exercises">'+''.join(qs)+'</ol>'
  else:content=render(body)
  if id=='macro':content+=macro_notes()
  if id=='quick-start':content=content.replace('<ul>','<ul class="learn-objectives">',1)
  if id=='control':content+='<p class="learn-source-note">릿지는 L2 규제, 라쏘는 L1 규제를 사용하며 라쏘는 일부 계수를 0으로 만들 수 있습니다. 계수 추정에 편향을 허용해 예측 분산을 줄일 수 있지만, 계수의 편향과 특정 X에서의 예측 편향은 같은 값이 아닙니다. 규제 강도도 검증으로 선택하며 성능 개선이 보장되지는 않습니다.</p>'
  content=content.replace('교차검증은 26장에서','교차검증은 <a href="/learn/stats/cross-validation/">26장</a>에서').replace('25장 「예측오차: MAE·RMSE·MAPE」','<a href="/learn/stats/prediction-errors/">25장 「예측오차: MAE·RMSE·MAPE」</a>')
  parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{heading}</h2>{content}</section>')
 return parts

if __name__=='__main__':build()
