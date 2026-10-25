"""Chapter 26: fold-local fitting and honest selection."""
from pathlib import Path
from statistics import mean
from html import escape
import json,re,math
from _build_regression_chapter import fit
from _build_errors_chapter import metrics
ROOT=Path(__file__).resolve().parent

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];folds=[];all_y=[];all_p=[]
 for k in range(3):
  va=rows[k*10:(k+1)*10];tr=rows[:k*10]+rows[(k+1)*10:];m=fit([r['area'] for r in tr],[r['price'] for r in tr]);pred=[m['intercept']+m['slope']*r['area'] for r in va];y=[r['price'] for r in va];all_y+=y;all_p+=pred
  folds.append(dict(fold=k+1,train_ids=[r['id'] for r in tr],validation_ids=[r['id'] for r in va],intercept=m['intercept'],slope=m['slope'],predictions=pred,metrics=metrics(y,pred)))
 pooled=metrics(all_y,all_p);average_rmse=mean(f['metrics']['RMSE'] for f in folds)
 d=dict(description='공통 학습 자료의 번호 순 3폴드. 시간·집단 검증 또는 최종 운영 성능 추정이 아님.',folds=folds,pooled=pooled,mean_fold_RMSE=average_rmse,unequal_example=dict(sizes=[2,8],MAE=[10,2],unweighted=6,pooled=3.6))
 (ROOT/'cross-validation-example.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def box(x,y,w,h,c):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{c}"/>'
 def ln(x,y,a,b):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="#94a3b8"/>'
 def fig(id,title,b,cap,h=410):return f'<figure class="learn-chart learn-chart--wide"><svg class="cv-chart-svg" viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=tx(24,28,'3폴드: 매번 20건으로 새로 학습하고 10건을 예측')
 for j,label in enumerate(['1~10번','11~20번','21~30번']):b+=tx(140+j*160,80,label)
 for k in range(3):
  yy=105+k*75;b+=f'<g data-fold-row="{k+1}">'+tx(24,yy+32,f'{k+1}회')
  for j in range(3):b+=box(120+j*160,yy,145,55,'#ffedd5' if j==k else '#dbeafe')+tx(160+j*160,yy+32,'검증' if j==k else '학습')
  b+='</g>'
 b+=tx(24,370,'파랑: 학습 / 주황: 검증 · 한 관측은 검증에 정확히 한 번 사용')
 g1=fig('folds','3폴드의 자료 배정',b,'그림 1. 번호 블록별 교재용 분할입니다. 세 모형의 학습 자료가 서로 겹치므로 폴드 점수들을 독립 반복 측정으로 간주하지 않습니다.')
 b=tx(24,28,'폴드별 검증 MAE와 선택 폴드의 회귀')+ln(65,320,325,320)
 for i,f in enumerate(folds):
  v=f['metrics']['MAE'];xx=90+i*80;b+=f'<rect data-fold-bar="{f["fold"]}" x="{xx}" y="{320-v*3.5}" width="45" height="{v*3.5}" fill="#2563eb"/>'+tx(xx,307-v*3.5,f'{v:.2f}')+tx(xx,350,f'{i+1}폴드')
 for v in [0,20,40,60]:b+=tx(25,325-v*3.5,v)
 px=lambda x:390+(x-22)*.65;py=lambda y:320-y*.48
 b+=ln(390,320,590,320)+ln(390,65,390,320)+tx(390,56,'X → Y · 공통 학습 자료')
 for value in [0,250,500]:b+=tx(350,py(value)+5,value)
 for value in [22,160,310]:b+=tx(px(value)-7,345,value)
 for f in folds:
  hidden=' hidden=""' if f['fold']!=1 else ''
  b+=f'<g data-fold-scatter="{f["fold"]}"{hidden}>'
  for row in rows:
   validation=row['id'] in f['validation_ids'];color='#d97706' if validation else '#2563eb'
   b+=f'<circle data-id="{row["id"]}" data-role="{"validation" if validation else "train"}" cx="{px(row["area"])}" cy="{py(row["price"])}" r="{4 if validation else 3}" fill="{color}"><title>{row["id"]}번 · X={row["area"]}, 실제 Y={row["price"]} · {"검증" if validation else "학습"}</title></circle>'
  b+=f'<line data-fit-line="{f["fold"]}" x1="{px(22)}" y1="{py(f["intercept"]+f["slope"]*22)}" x2="{px(310)}" y2="{py(f["intercept"]+f["slope"]*310)}" stroke="#111827"/>'
  for id,prediction in zip(f['validation_ids'],f['predictions']):
   row=next(r for r in rows if r['id']==id)
   b+=f'<line x1="{px(row["area"])}" x2="{px(row["area"])}" y1="{py(row["price"])}" y2="{py(prediction)}" stroke="#94a3b8" stroke-dasharray="3 3"/><circle data-prediction-id="{id}" cx="{px(row["area"])}" cy="{py(prediction)}" r="4" fill="none" stroke="#0f766e"><title>{id}번 검증 예측 {prediction:.2f}</title></circle>'
  b+='</g>'
 b+=tx(24,382,'오른쪽: 파랑 학습 실제 / 주황 검증 실제 / 빈 원 검증 예측')+tx(24,409,'검정선: 해당 학습 20건의 회귀 · 점선: 검증 오차 · X·Y는 학습용 수치')
 g2=fig('scores','폴드별 MAE와 검증 예측',b,'그림 2. 왼쪽 MAE는 Y와 같은 단위입니다. 오른쪽은 선택 폴드의 학습·검증 실제값, 새로 적합한 직선과 검증 예측입니다. 점수 차이를 독립 반복의 신뢰구간으로 해석하지 않습니다.',440)
 b=tx(24,28,'가상 불균등 폴드: 2건 MAE 10 / 8건 MAE 2')+ln(80,320,570,320)
 for i,(label,v) in enumerate([('폴드 단순 평균',6),('관측별 통합',3.6)]):
  xx=180+i*220;b+=box(xx,320-v*32,80,v*32,'#2563eb' if i==0 else '#d97706')+tx(xx+25,307-v*32,v)+tx(xx-18,350,label)
 for v in [0,2,4,6]:b+=tx(35,325-v*32,v)
 b+=tx(24,385,'(10+2)/2 = 6 / (2×10+8×2)/10 = 3.6')
 g3=fig('aggregation','폴드와 관측 가중치',b,'그림 3. 별도 가상 예제입니다. 폴드에 같은 비중을 주는 것과 관측에 같은 비중을 주는 것은 다른 집계입니다. 어떤 대상을 평균하는지 밝혀야 합니다.')
 b=tx(24,28,'중첩 교차검증: 바깥은 평가, 안쪽은 선택')+'<g data-nested-part="train">'+box(55,65,370,250,'#f1f5f9')+tx(75,95,'바깥 학습 부분')+'</g>'+'<g data-nested-part="inner">'+box(80,115,330,75,'#dbeafe')+tx(100,144,'안쪽 CV: 전처리·후보·설정 선택')+tx(100,174,'바깥 학습자료 안에서만 수행')+'</g>'+'<g data-nested-part="refit">'+box(80,215,330,65,'#dcfce7')+tx(100,241,'선택 후 바깥 학습 전체로')+tx(100,267,'전처리·모형을 재적합')+'</g>'+'<g data-nested-part="evaluation">'+box(435,115,125,165,'#ffedd5')+tx(450,153,'바깥 평가')+tx(448,190,'안쪽 선택에')+tx(455,218,'미사용')+'</g>'+tx(417,252,'→')+tx(24,370,'바깥 분할을 바꾸며 선택·학습 절차 전체를 평가합니다')
 g4=fig('nested','선택과 평가의 중첩 구조',b,'그림 4. 한 번의 바깥 반복 개념도입니다. 바깥 평가자료는 안쪽 선택·전처리·재적합에 사용하지 않습니다. 바깥 반복마다 선택되는 설정은 달라도 됩니다.')
 g1=g1.replace('<svg ','<div class="cv-controls" hidden=""><label for="cv-fold">검증할 폴드 선택</label><select id="cv-fold">'+''.join(f'<option value="{f["fold"]}">{f["fold"]}폴드</option>' for f in folds)+'</select><p id="cv-fold-status" role="status" aria-live="polite"></p><div class="cv-blocks" id="cv-blocks"></div></div><svg ',1)
 g2=g2.replace('<svg ','<p id="cv-score-status" role="status" aria-live="polite"></p><svg ',1)
 g2+='<details class="learn-more"><summary>선택 폴드의 검증 10건과 OOF 예측</summary><div id="cv-predictions" class="learn-data learn-data--full"></div></details>'
 g4=g4.replace('<svg ','<div class="cv-controls" hidden=""><label for="cv-stage">중첩 CV 단계</label><select id="cv-stage"><option value="split">바깥 분리</option><option value="inner">안쪽 선택</option><option value="refit">재적합</option><option value="evaluation">바깥 평가</option></select><p id="cv-stage-status" role="status" aria-live="polite"></p></div><svg ',1)
 parts=render_content([g1,g2,g3,g4])
 p=ROOT/'cross-validation/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="교차검증과 모형 선택">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1K폴드·OOF·점수 집계와 중첩 교차검증, 시간·집단 분할 및 모형 선택의 한계를 학습합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);html=add_assets(html,dict(folds=folds,rows=rows));p.write_text(html,encoding='utf-8')

def add_assets(html,data):
 html=html.replace('별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.','활용도는 CH2 Macro의 분석 결과를 이해하는 데 얼마나 도움이 되는지를 나타냅니다.')
 if 'cross-validation/chapter.css' not in html:html=html.replace('</head>','<link rel="stylesheet" href="/learn/stats/cross-validation/chapter.css?v=20261025-1" /></head>')
 payload='<script type="application/json" id="cv-data">'+json.dumps(data,ensure_ascii=False)+'</script>'
 if 'id="cv-data"' in html:html=re.sub(r'<script type="application/json" id="cv-data">.*?</script>',lambda _:payload,html,flags=re.S)
 else:html=html.replace('</body>',payload+'</body>')
 if 'cross-validation/experiment.js' not in html:html=html.replace('</body>','<script type="module" src="/learn/stats/cross-validation/experiment.js?v=20261025-1"></script></body>')
 return html

def macro_notes():
 return '<details class="learn-more"><summary>현재 Macro의 CV·Holdout과 교재 예제의 차이</summary><div class="learn-more__body"><p>교재 코드는 번호 블록별로 나머지 20건에 회귀계수를 새로 적합하고 검증 10건을 예측합니다. 결측 대체·표준화·변수 선택은 이 단순 예제에서 수행하지 않습니다. 이를 실제 서비스의 전처리 전체가 fold 안에서 학습된다는 증거로 사용하지 않습니다.</p><p>확인한 복합 롤링 CV는 계약연도로 과거 학습→이후 연도 평가를 구성합니다. 고정 3폴드·무작위 시드 3폴드가 아니며 기간과 유효 표본수에 따라 가능한 평가 연도 수가 달라집니다. 마지막 연도를 확인용으로 남기는 경로가 있고 탐색 CV 순위와 확인 CV가 UI에 구분됩니다. 확인 CV가 대표모형 확정에 쓰이는 경로도 있으므로 완전히 독립적인 최종 시험이라고 단정하지 않습니다.</p><p>복합 로그 역변환 보정과 시점 보정은 각 학습 fold에서 계산합니다. 다만 전체 설계행렬을 만든 뒤 연도로 나누는 경로가 있어 범주 전처리까지 모두 fold 내부라고 설명하지 않습니다. CV-MAPE는 유효 평가 관측의 APE를 모아 평균하며 실제값 0과 비유한값을 제외합니다. 이 경로의 응답은 점수·연도·유효 평가 정보 중심이며 교재처럼 30건의 OOF 예측표를 일반 서비스에서 저장·노출한다고 가정하지 않습니다.</p><p>집합 주거 지역회귀는 후보별 적격 단지에서 시드 42의 무작위 Holdout을 사용하는 경로가 있습니다. 이는 교재 K폴드나 중첩 CV와 다릅니다. 선택에 쓰는 Holdout 점수와 최종 독립 평가를 구분하고 후보별 동일 평가 단지 여부도 확인해야 합니다. 지역·단지·계약연도 구분과 당시 정보 공개·대장 판본은 각각 별도 검증 경계입니다.</p><p>복합 예측형은 CV-MAPE 우선, 집합 주거 예측형은 Holdout MAPE 우선이며, 설명형은 AIC 또는 수정 R² 등의 별도 기준을 사용합니다. 일반 추천의 CV-MAE·CV-RMSE, 중첩 CV, 모든 후보의 OOF 저장이나 랩의 릿지·라쏘·다항 실험을 현재 공통 서비스 기능으로 소개하지 않습니다. 실제 회귀·추천·검증 정책은 변경하지 않았습니다.</p></div></details>'

def render_content(graphs):
 page=ROOT/'cross-validation/index.html'
 old=page.read_text(encoding='utf8')
 refs=re.search(r'<details class="learn-references">.*?</details>',old,re.S)[0]
 source=(ROOT/'cross-validation/content.md').read_text(encoding='utf8').replace('**','').replace('<text color="secondary">그림에 표시할 핵심 계산값</text>','지표별 계산 비교')
 formulas=['ŷ = 209.579−0.5902X','ŷ = 236.411−0.6928X','ŷ = 250.703−0.7603X','(10+2)/2 = 6','(2×10+8×2)/10 = 3.6','RMSE = √[(1/n) Σ (yᵢ−ŷᵢ)²]','RMSEOOF = √[Σ nₖ RMSEₖ² / Σ nₖ]','폴드 평균 RMSE = (1/K) Σ RMSEₖ','MAPE = (100/n) Σ |(yᵢ−ŷᵢ)/yᵢ|']

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
   out.append('<p'+(' class="cv-formula"' if (any(line==formula for formula in formulas) or line.startswith(('ME =','MSE =','MAE =','RMSE =','MAPE ='))) else '')+'>'+inline(line)+'</p>')
  return '\n'.join(out)
 ids=['quick-start','cross-validation','scores','oof','aggregation','rmse','mape','pipeline','selection','evaluation','nested','fold-count','design','uncertainty','report','macro','practice','recap']
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
  if id in {'mape','selection'}:content='<span id="'+{'mape':'cv-mape','selection':'model-recommendation'}[id]+'" aria-hidden="true"></span>'+content
  if id=='quick-start':content=content.replace('<ul>','<ul class="learn-objectives">',1)
  content=content.replace('교차검증은 26장에서','교차검증은 <a href="/learn/stats/cross-validation/">26장</a>에서').replace('27장 「규제: 릿지와 라쏘」','<a href="/learn/stats/regularization/">27장 「규제: 릿지와 라쏘」</a>')
  parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{heading}</h2>{content}</section>')
 return parts
if __name__=='__main__':build()
