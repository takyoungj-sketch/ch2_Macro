"""Chapter 22: purposes, supervised tasks and unsupervised structure."""
from pathlib import Path
from statistics import mean
from html import escape
import json,re,math
from _build_regression_chapter import fit
ROOT=Path(__file__).resolve().parent

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];train=rows[:20];test=rows[20:];m=fit([r['area'] for r in train],[r['price'] for r in train]);baseline=mean(r['price'] for r in train)
 predictions=[dict(id=r['id'],actual=r['price'],predicted=m['intercept']+m['slope']*r['area']) for r in test];mae=mean(abs(r['actual']-r['predicted']) for r in predictions);base_mae=mean(abs(r['price']-baseline) for r in test)
 points=[[1,1],[1,2],[2,1],[2,2],[6,6],[6,7],[7,6],[7,7]];centers=[[1.5,1.5],[6.5,6.5]];labels=[min(range(2),key=lambda j:sum((v-c)**2 for v,c in zip(p,centers[j]))) for p in points]
 result=dict(description='공통 학습 자료의 면적 X(㎡)와 거래단가 Y(만원/㎡)를 사용한 번호 순서 분할. 시간 검증이 아니며 분류·군집 예제는 별도 가상 자료.',train_ids=[r['id'] for r in train],test=predictions,fit=m,MAE=mae,baseline_mean=baseline,baseline_MAE=base_mae,classification=dict(TN=90,FP=0,FN=10,TP=0,accuracy=.9,recall=0,precision=None),clustering=dict(points=points,centers=centers,labels=labels,inertia=sum(sum((v-c)**2 for v,c in zip(p,centers[j])) for p,j in zip(points,labels))))
 (ROOT/'learning-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def ln(x,y,a,b,c='#94a3b8'):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="{c}"/>'
 def rect(x,y,w,h,c):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{c}"/>'
 def fig(id,title,b,cap,h=410):return f'<figure class="learn-chart learn-chart--wide"><svg class="sl-chart-svg" viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 px=lambda v:120+v*1.35
 py=lambda v:465-v*1.35
 b=tx(24,28,'공통 자료: 학습에 쓰지 않은 21~30번, 같은 10건 평가')+ln(120,465,525,465)+ln(120,60,120,465)+ln(120,465,525,60,'#64748b')
 for row in predictions:b+=f'<circle data-id="{row["id"]}" data-actual="{row["actual"]}" cx="{px(row["actual"])}" cy="{py(row["predicted"])}" r="5" fill="#2563eb"><title>{row["id"]}번: 실제 {row["actual"]}, 예측 {row["predicted"]:.2f}만원/㎡</title></circle>'
 for v in [0,100,200,300]:b+=tx(px(v)-7,490,v)+tx(75,py(v)+5,v)
 b+=tx(24,525,'가로: 실제 거래단가 / 세로: 예측 거래단가 (만원/㎡)')+tx(24,550,'두 축은 같은 배율 · 회색 45도 선: 예측=실제')
 f1=fig('regression','같은 평가 자료에서 회귀와 기준모형 비교',b,'그림 1. 1~20번에서 학습하고 21~30번에서 평가합니다. 회색 45도 선은 예측=실제입니다. 번호는 시간순이 아니며 미래 예측 성능을 검증한 결과가 아닙니다.',575)
 controls='<div class="sl-controls" hidden><label for="sl-model">평가할 모형</label><select id="sl-model"><option value="regression">단순회귀</option><option value="baseline">학습 평균 기준모형</option></select><div id="sl-eval-status" role="status" aria-live="polite"></div><p class="learn-source-note">관측값과 평가 대상 10건은 고정합니다. 기준모형의 평균은 학습 20건에서만 계산합니다. 미래 시점 검증이 아닌 교재용 분할입니다.</p></div>'
 f1=f1.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="sl-regression">').replace('<svg ',controls+'<svg ',1)
 b=tx(24,28,'가상 분류: 100건 모두 음성으로 예측')+tx(220,75,'예측 양성')+tx(420,75,'예측 음성')
 cells=[('TP',190,100,0,'#f1f5f9',''),('FN',390,100,10,'#ffedd5',' · 놓침'),('FP',190,210,0,'#f1f5f9',''),('TN',390,210,90,'#dbeafe',' · 맞힘')]
 for key,xx,yy,count,color,note in cells:b+=rect(xx,yy,170,85,color).replace(' rx=',f' data-cell="{key}" data-count="{count}" rx=')+tx(xx+23,yy+48,f'{key} {count}{note}')
 b+=tx(35,148,'실제 양성')+tx(35,258,'실제 음성')+tx(24,340,'정확도 90% · 양성 재현율 0%')+tx(24,375,'정밀도: 정의되지 않음 (양성 예측 0건)')
 f2=fig('classification','정확도 90%지만 양성 10건을 모두 놓친 분류',b,'그림 2. 공통 30건과 별개인 가상 분류 자료 100건입니다. 행은 실제, 열은 예측입니다. 맞힌 음성 TN=90, 놓친 양성 FN=10이며 정밀도의 분모 TP+FP는 0입니다.')
 b=tx(24,28,'단위 없는 가상 두 특징 · K=2 군집 예제')+ln(145,355,465,355)+ln(145,35,145,355)
 for point,label in zip(points,labels):b+=f'<circle data-cluster="{label}" cx="{145+point[0]*40}" cy="{355-point[1]*40}" r="5" fill="'+('#2563eb' if label==0 else '#d97706')+'"><title>좌표 ('+str(point[0])+', '+str(point[1])+')</title></circle>'
 for label,(a,v) in enumerate(centers):
  cx=145+a*40;cy=355-v*40;b+='<g data-cluster-center="'+str(label)+'">'+ln(cx-8,cy-8,cx+8,cy+8,'#111827')+ln(cx-8,cy+8,cx+8,cy-8,'#111827')+'</g>'
 for v in [0,2,4,6,8]:b+=tx(140+v*40,380,v)+tx(110,360-v*40,v)
 b+=tx(24,415,'가로: 특징 1 / 세로: 특징 2 · 단위 없음, 같은 축 배율')+tx(24,445,'파랑 A / 주황 B · ×: 중심 · 군집 번호는 정답 범주가 아님').replace('<text ','<text id="sl-cluster-legend" ',1)
 f3=fig('clusters','가상 8점의 관측점과 K-means 군집',b,'그림 3. 단위 없는 가상 8점입니다. 중심은 (1.5,1.5), (6.5,6.5), 군집 내 제곱거리 합은 4입니다. 군집 번호를 교환해도 같은 분할입니다.',475)
 controls='<div class="sl-controls" hidden><label for="sl-cluster-mode">군집 표시</label><select id="sl-cluster-mode"><option value="cluster">군집과 중심 보기</option><option value="points">관측점만 보기</option></select><p id="sl-cluster-status" role="status" aria-live="polite"></p></div>'
 f3=f3.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="sl-clusters">').replace('<svg class="sl-chart-svg"',controls+'<svg class="sl-chart-svg sl-cluster-svg"',1)
 b=tx(24,28,'전체 자료를 역할에 따라 나누는 개념도')+rect(170,55,300,65,'#eaf2ff')+tx(253,95,'전체 원자료')
 b+=ln(320,120,320,150)+ln(120,150,520,150)
 for xx,label,line1,line2 in [(30,'학습 자료','전처리 기준·계수','학습 자료에서 계산'),(230,'검증 자료','모형·변수·설정','비교하고 선택'),(430,'시험 자료','최종 선택을 끝낸 뒤','마지막 성능 평가')]:
  b+=ln(xx+90,150,xx+90,178)+tx(xx+83,175,'↓')+rect(xx,185,180,115,'#eaf2ff')+tx(xx+35,215,label)+tx(xx+15,250,line1)+tx(xx+15,280,line2)
 b+=tx(24,345,'시험 자료를 보며 반복 선택하면 최종 평가의 독립성을 잃습니다')+tx(24,380,'시간·지역·단지 구조에 맞게 분할 · 박스 크기는 배분 비율이 아님')
 f4=fig('workflow','전체 자료에서 학습·검증·시험 역할 구분',b,'그림 4. 전체 원자료를 학습·검증·시험 역할로 구분한 개념도입니다. 학습 자료를 검증·시험 자료로 차례로 바꾼다는 뜻이 아닙니다. 비율은 고정하지 않으며 표준화·결측치 대체 기준은 학습 자료에서 계산합니다.')
 parts=[]
 page=ROOT/'supervised-unsupervised/index.html';old=page.read_text(encoding='utf-8')
 references=re.search(r'<details class="learn-more"><summary>참고자료(?:와 계산값)?</summary>.*?</details>',old,re.S)[0].replace('회귀 계산은 공통 학습 자료의 두 수치열을 단위 없는 X,Y로 사용했습니다.','회귀 계산은 공통 학습 자료의 면적(㎡)과 거래단가(만원/㎡)를 사용했습니다.')
 source=normalize_source((ROOT/'supervised-unsupervised/content.md').read_text(encoding='utf-8'))
 formulas={r'\hat y=\hat f(X)':'ŷ = f̂(X)',r'\frac1n\sum_{i=1}^{n}L(y_i,\hat f(x_i))':'(1/n) Σ L(yᵢ, f̂(xᵢ))',r'z=\frac{x-\bar x}{s}':'z = (x−x̄)/s'}
 source=re.sub(r'^\[\s*\n(.*?)\n\]$',lambda match:formulas[match[1].strip()],source,flags=re.M|re.S)
 ids=['quick-start','purposes','supervised','regression','baseline','classification-intro','classification','unsupervised','clusters','features','scaling','workflow','evaluation','macro','practice','recap']
 def inline(value):return escape(value)
 def render(block):
  out=[];lines=block.strip().split('\n');i=0
  while i<len(lines):
   line=lines[i].strip()
   if not line or line=='---':i+=1;continue
   if line.startswith('### '):out.append('<h3>'+inline(line[4:])+'</h3>');i+=1;continue
   if line.startswith('[그림 '):out.append({1:f1,2:f2,3:f3,4:f4}[int(re.search(r'그림 (\d)',line)[1])]);i+=1;continue
   if line=='[CH2 Macro 통계·데이터분석 열기 →]':out.append('<p><a href="https://macro.ch2data.com/">CH2 Macro 통계·데이터분석 열기 →</a></p>');i+=1;continue
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
    out.append('<div class="learn-data learn-data--full"><table><thead><tr>'+''.join('<th scope="col">'+inline(c)+'</th>' for c in table[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<th scope="row">'+inline(c)+'</th>' if j==0 else '<td>'+inline(c)+'</td>' for j,c in enumerate(row))+'</tr>' for row in table[1:])+'</tbody></table></div>');continue
   if line.startswith('- '):
    items=[]
    while i<len(lines) and lines[i].startswith('- '):items.append('<li>'+inline(lines[i][2:])+'</li>');i+=1
    out.append('<ul>'+''.join(items)+'</ul>');continue
   formula=line.startswith(('ŷ','(1/n)','z =','거래단가 =','정확도 =','예측값 ='))
   out.append('<p'+(' class="sl-formula"' if formula else '')+'>'+inline(line)+'</p>');i+=1
  return '\n'.join(out)
 for id,section in zip(ids,re.split(r'^## ',source,flags=re.M)[1:],strict=True):
  label,body=section.split('\n',1);heading=re.search(r'^### (.+)$',body,re.M)[1];body=re.sub(r'^### .+\n','',body,count=1,flags=re.M)
  if id=='practice':
   items=[]
   for q in re.split(r'^\d+\. ',body,flags=re.M)[1:]:
    question,answer=q.split('▶ 답과 해설',1);items.append('<li>'+inline(question.strip())+'<details><summary>답과 해설</summary><div class="learn-more__body">'+render(answer)+'</div></details></li>')
   html='<ol class="learn-exercises">'+''.join(items)+'</ol>'
  else:html=render(body)
  if id=='quick-start':html=html.replace('<ul>','<ul class="learn-objectives">',1)+'<p class="learn-source-note"><a href="/learn/stats/graphs/#data">공통 학습 자료 30건</a> · <a href="../learning-example.json">회귀 평가·가상 분류·군집 계산 자료</a>. 회귀는 면적(㎡)·거래단가(만원/㎡), 분류·군집은 별도 가상 자료입니다. 실제 거래의 대표성이 검증된 자료는 아닙니다.</p>'
  if id=='regression':html=html.replace('17장에서 배운 단순선형회귀','<a href="/learn/stats/regression/">17장에서 배운 단순선형회귀</a>')
  if id=='classification':html+='<p class="learn-source-note">정확도=(TP+TN)/100=90%, 양성 재현율=TP/(TP+FN)=0%, 정밀도=TP/(TP+FP)=0/0으로 정의되지 않습니다. 확률 보정 상태의 평가와 확률을 다시 보정하는 절차도 구분합니다.</p>'
  if id=='features':html+='<p class="learn-source-note">공시지가·건축물대장 등의 정보도 해당 예측 시점에 이용 가능했던 판본인지 확인해야 합니다. 최신 자료가 과거에도 알려져 있었다고 가정하지 않습니다.</p>'
  if id=='scaling':html+='<p class="learn-source-note">검증·시험 자료에는 학습 자료에서 정한 같은 평균과 표준편차를 적용합니다. 각각의 평균·표준편차를 다시 구해 별도로 표준화하지 않습니다.</p>'
  if id=='clusters':html+='<p><a href="/learn/stats/clustering/">31장 군집분석</a>에서 군집 수와 안정성을 더 자세히 살펴봅니다.</p>'
  if id=='evaluation':html='<span id="choice" aria-hidden="true"></span>'+html
  if id=='macro':html+=macro_notes()
  if id=='recap':html=html.replace('23장 「학습·검증·시험 자료와 데이터 누수」','<a href="/learn/stats/train-validation-test/">23장 「학습·검증·시험 자료와 데이터 누수」</a>')
  parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{heading}</h2>{html}</section>')
 html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="통계적 설명과 예측, 지도학습과 비지도학습">'+'\n'.join(parts)+'</article>',old,count=1,flags=re.S)
 html=html.replace('별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.','활용도는 CH2 Macro의 분석 결과를 이해하는 데 얼마나 도움이 되는지를 나타냅니다.')
 if 'supervised-unsupervised/chapter.css' not in html:html=html.replace('</head>','<link rel="stylesheet" href="/learn/stats/supervised-unsupervised/chapter.css?v=20261025-1" />\n</head>')
 data=json.dumps(result,ensure_ascii=False).replace('</','<\\/')
 html=html.replace('</body>','<script type="application/json" id="sl-data">'+data+'</script>\n</body>') if 'id="sl-data"' not in html else re.sub(r'<script type="application/json" id="sl-data">.*?</script>',lambda _: '<script type="application/json" id="sl-data">'+data+'</script>',html,flags=re.S)
 if 'supervised-unsupervised/experiment.js' not in html:html=html.replace('</body>','<script type="module" src="/learn/stats/supervised-unsupervised/experiment.js?v=20261025-1"></script>\n</body>')
 page.write_text(html,encoding='utf-8')

def normalize_source(raw):
 """Restore semantic headings/lists/tables from the user's plain-text paste."""
 raw=raw.replace('**','').replace('\\~','~')
 sections=['서두 · 학습목표','분석 목적의 차이','지도학습의 기본 구조','지도학습 ① 회귀','기준모형과 비교하기','지도학습 ② 분류','분류의 정확도와 오류','비지도학습의 기본 구조','군집분석의 예제','변수의 역할은 분석 목적에 따라 달라집니다','변수의 단위와 스케일','학습·검증·시험 자료','무엇을 기준으로 평가해야 할까요?','CH2 Macro에서 읽기','확인 문제','결론 · 학습 요약']
 tables=[
  [['분석 목적','주요 질문','중요하게 살펴볼 것'],['설명','어떤 관계가 관찰되는가?','관계의 크기·방향·안정성'],['인과','X를 바꾸면 Y가 달라지는가?','연구 설계·교란 요인·식별 가정'],['예측','아직 모르는 Y를 맞힐 수 있는가?','새로운 자료의 예측오차']],
  [['입력변수 X','목표변수 Y'],['면적, 층, 용도지역, 건축연도','거래단가']],
  [['예측 방법','평가 MAE'],['학습 자료의 평균만 사용','49.86만원/㎡'],['면적을 이용한 단순회귀','41.08만원/㎡']],
  [['실제 \\ 예측','양성','음성'],['실제 양성','0','10'],['실제 음성','0','90']],
  [['분석 방법','평가할 내용','대표적인 방법'],['수치 예측','실제값과 예측값의 차이','MAE, RMSE 등'],['분류','정확히 분류했는지와 오류의 종류','정확도, 재현율, 정밀도 등'],['확률 예측','예측확률의 품질','로그손실, 확률 보정 등'],['군집분석','군집 구조의 안정성과 해석 가능성','군집 분리도, 안정성, 분야 해석']]
 ]
 for table in tables:
  flat='\n\n'.join(cell for row in table for cell in row)
  assert flat in raw,table[0]
  markdown='| '+' | '.join(table[0])+' |\n| '+' | '.join(['---']*len(table[0]))+' |\n'+'\n'.join('| '+' | '.join(row)+' |' for row in table[1:])
  raw=raw.replace(flat,markdown,1)
 objectives={'통계적 설명, 인과 추론, 예측의 목적을 구별합니다.','지도학습에서 입력변수와 목표변수의 역할을 이해합니다.','회귀와 분류가 서로 다른 예측 문제임을 알아봅니다.','비지도학습에서 군집분석의 의미와 한계를 이해합니다.','학습 자료와 평가 자료의 차이를 이해합니다.','분석 목적에 따라 변수와 평가 기준을 선택하는 방법을 알아봅니다.'}
 out=[];heading=False
 for paragraph in re.split(r'\n\s*\n',raw.strip()):
  paragraph=paragraph.strip()
  if paragraph in sections:out.append('## '+paragraph);heading=True
  elif heading:out.append('### '+paragraph);heading=False
  elif paragraph in objectives or paragraph.startswith(('학습 자료:','평가 자료:','군집 A 중심:','군집 B 중심:','토지면적:','층:','설명:','인과:','예측:','지도학습:','회귀와 분류:','비지도학습:','데이터 누수:','모형 평가:','CH2 Macro:')):out.append('- '+paragraph)
  else:out.append(paragraph)
 # Join consecutive list items while preserving ordinary paragraph boundaries.
 return re.sub(r'\n\n(?=- )','\n','\n\n'.join(out))

def macro_notes():
 return '''<details class="learn-more"><summary>실제 Macro의 추천 목적·평가 자료·입력 범위 확인</summary><div class="learn-more__body">
<p>확인한 복합 모형추천과 집합 주거 지역회귀 추천 UI는 ‘예측형’과 ‘설명형’을 구분합니다. 목적에 따른 후보 정렬이며 통계적 통제가 인과효과를 보장하는 기능은 아닙니다. 계수의 p값·유의 변수 수를 별도 자료의 예측 기여도나 변수 중요도 순위로 읽지 않습니다.</p>
<p>복합 척도 비교의 확인한 경로는 예측형에서 원 단위 CV-MAPE를 우선하고, 없으면 학습 MAPE와 AIC를 참조합니다. 설명형은 로그 종속변수 후보끼리 AIC를 비교합니다. 롤링 시점 검증은 과거 연도로 학습해 이후 연도를 평가하며, 로그 역변환 보정계수는 각 학습 fold의 잔차에서만 구합니다. 그렇다고 모든 전처리·변수 선택 단계의 정보 누수까지 검증되었다는 뜻은 아닙니다.</p>
<p>집합 주거 지역회귀는 단지별 중앙단가를 목표로 하며, 예측형 후보 정렬에는 Holdout MAPE를 사용합니다. 없으면 학습 MAPE를 참조하고, 설명형은 원 단위 수정 R²를 우선합니다. 이 Holdout은 후보 선택에 쓰이므로 최종 선택과 독립적인 시험 성능이라고 부르면 안 됩니다. 복합의 거래별 금액·연도 검증과 집합의 단지별 단가·단지 분할을 같은 평가로 섞지 않습니다.</p>
<p>지역회귀는 후보별 선택 변수의 결측 조건으로 적격 표본을 정하고, 그 표본에서 분할합니다. 따라서 후보마다 같은 단지들이 평가된다고 단정할 수 없습니다. 또한 범주 구성에 전체 적격 자료를 사용하는 경로가 있어, 전처리가 모두 학습 자료 내부에서만 이루어진다고 설명하지 않습니다. 공정한 동일 표본 비교와 별도 최종 시험, 전처리 범위는 추가 점검 사항입니다.</p>
<p>같은 단지·지역의 반복 거래는 서로 독립적이지 않을 수 있습니다. 확인한 복합 연도 분할이 단지 단위의 완전한 분리까지 보장하지는 않습니다. 반대로 단지 한 행을 나누는 지역회귀도 미래 연도나 새로운 지역에 대한 검증을 자동 보장하지 않습니다. 적용하려는 대상에 맞춰 시간·지역·단지 구조를 함께 점검해야 합니다.</p>
<p>확인한 복합 설계는 거래금액을 목표로 하고, 지역회귀 설계는 단지 중앙단가를 목표로 합니다. 지역회귀의 선택 속성에는 세대수·최고층·연식·주차·대표 필지 공시지가·범주 등이 있습니다. 이 경로에서 실제 목표 거래금액을 입력해 단가를 복원하는 교재의 누수 예제를 그대로 사용한다고 보지는 않습니다. 다만 공시지가처럼 ‘최신 대표 필지’ 속성을 과거 예측에 쓸 때는 당시 이용 가능했던 판본인지 별도로 확인해야 합니다.</p>
<p>이 장의 가상 혼동행렬과 K-means 8점 실험은 독립된 학습 UI입니다. 이를 실제 Macro가 모든 거래에 제공하는 분류·군집 기능으로 소개하지 않습니다. 유사 지역·집단을 찾는 다른 서비스 기능도 이 교재의 K-means와 같은 알고리즘이라고 가정하지 않습니다. 실제 회귀·추천·자료 처리 로직은 이번 작업에서 변경하지 않습니다.</p>
</div></details>'''

if __name__=='__main__':build()
