"""Chapter 25: error metrics with explicit evaluation targets."""
from pathlib import Path
from statistics import mean,median
from html import escape
import math,json,re
from _build_regression_chapter import fit
ROOT=Path(__file__).resolve().parent

def metrics(y,p):
 e=[a-b for a,b in zip(y,p)]
 return dict(errors=e,ME=mean(e),MAE=mean(abs(v) for v in e),MSE=mean(v*v for v in e),RMSE=math.sqrt(mean(v*v for v in e)),MAPE=100*mean(abs(v/a) for v,a in zip(e,y)) if all(a!=0 for a in y) else None)

def build():
 actual=[10,10,10,10];ap=[10,10,10,2];bp=[7,7,7,7];A=metrics(actual,ap);B=metrics(actual,bp);small=metrics([1,10,100],[0,9,99]);target=[1,2,9];grid=[i/20 for i in range(201)];loss=[dict(value=v,MAE=mean(abs(a-v) for a in target),MSE=mean((a-v)**2 for a in target)) for v in grid]
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];tr=rows[:20];te=rows[20:];f=fit([r['area'] for r in tr],[r['price'] for r in tr]);pred=[f['intercept']+f['slope']*r['area'] for r in te];common=metrics([r['price'] for r in te],pred)
 d=dict(description='A/B·MAPE·손실 곡선은 별도 가상 자료. 공통 30건 번호 분할은 시간 검증이 아님.',ranking=dict(actual=actual,A_predictions=ap,B_predictions=bp,A=A,B=B),small_values=dict(actual=[1,10,100],predictions=[0,9,99],metrics=small),loss=dict(actual=target,grid=loss),common=dict(train_ids=[r['id'] for r in tr],test_ids=[r['id'] for r in te],predictions=pred,metrics=common))
 (ROOT/'prediction-errors-example.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def ln(x,y,a,b):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="#94a3b8"/>'
 def fig(id,title,b,cap,h=410):return f'<figure class="learn-chart learn-chart--wide"><svg class="errors-chart-svg" viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=tx(24,28,'가상 4건: A는 한 번 큰 오차, B는 매번 작은 오차')+ln(65,320,580,320)
 for i in range(4):
  for j,(m,c) in enumerate([(A,'#2563eb'),(B,'#d97706')]):
   v=abs(m['errors'][i]);xx=110+i*130+j*28;b+=f'<g data-error-model="{chr(65+j)}"><rect data-observation="{i}" x="{xx}" y="{320-v*27}" width="24" height="{v*27}" fill="{c}"/>'+tx(xx,308-v*27,v)+'</g>'
  b+=tx(110+i*130,350,f'{i+1}번')
 for v in [0,2,4,6,8]:b+=tx(25,325-v*27,v)
 b+=tx(24,385,'세로: 절대오차 · 파랑 A / 주황 B · 단위 없는 가상 값')
 g1=fig('errors','관측별 절대오차',b,'그림 1. 실제값은 모두 10, A 예측은 10·10·10·2, B 예측은 7·7·7·7입니다. 평가 표본을 바꾸지 않고 오차 분포만 비교합니다.')
 b=tx(24,28,'같은 예측도 지표에 따라 순위가 달라집니다')+ln(65,320,580,320)
 for i,key in enumerate(['MAE','RMSE']):
  for j,(m,c) in enumerate([(A,'#2563eb'),(B,'#d97706')]):
   xx=170+i*240+j*65;v=m[key];b+=f'<rect data-rank-metric="{key}" data-model="{chr(65+j)}" x="{xx}" y="{320-v*50}" width="50" height="{v*50}" fill="{c}"/>'+tx(xx+15,308-v*50,f'{v:.1f}')
  b+=tx(195+i*240,350,key)
 for v in [0,1,2,3,4]:b+=tx(25,325-v*50,v)
 b+=tx(24,385,'파랑 A / 주황 B · 낮을수록 좋음 · 두 지표 모두 Y와 같은 단위')
 g2=fig('ranking','MAE와 RMSE의 순위 역전',b,'그림 2. A는 MAE 2로 B의 3보다 작지만 RMSE 4로 B의 3보다 큽니다. 큰 오차에 더 큰 비중을 주면 선택이 달라질 수 있습니다.')
 b=tx(24,28,'절대오차가 모두 1이어도 상대오차는 다릅니다')+ln(65,320,580,320)
 for i,v in enumerate([1,10,100]):
  ape=100/v;xx=140+i*170;b+=f'<rect x="{xx}" y="{320-ape*2.2}" width="70" height="{ape*2.2}" fill="#2563eb"/>'+tx(xx+15,308-ape*2.2,f'{ape:.0f}%')+tx(xx-5,350,f'실제값 {v}')
 for v in [0,50,100]:b+=tx(25,325-v*2.2,v)
 b+=tx(24,385,'세로: 절대 백분율 오차(%) · 예측은 각각 실제값보다 1 작음')
 g3=fig('mape','MAPE와 작은 분모',b,'그림 3. 별도 가상 값 1·10·100의 APE는 100%·10%·1%, MAPE는 37%입니다. MAPE는 작은 실제값의 같은 절대오차에 더 큰 비중을 줍니다.')
 b=tx(24,28,'가상 실제값 1·2·9에 상수 c를 예측한다면')
 for j,(key,maxv) in enumerate([('MAE',10),('MSE',60)]):
  left=65+j*300;b+=ln(left,315,left+235,315)+tx(left,65,key+(' · Y 단위' if key=='MAE' else ' · Y² 단위'))
  pts=' '.join(f"{left+r['value']*23},{315-r[key]/maxv*220}" for r in loss);b+='<polyline data-loss="'+key+'" points="'+pts+'" fill="none" stroke="#2563eb" stroke-width="2"/>'
  optimum=2 if key=='MAE' else 4;val=mean(abs(a-optimum) for a in target) if key=='MAE' else mean((a-optimum)**2 for a in target)
  b+=f'<circle data-optimum="{key}" cx="{left+optimum*23}" cy="{315-val/maxv*220}" r="5" fill="#d97706"/>'+tx(left,380,f'최소점 c={optimum}: '+('중앙값' if key=='MAE' else '평균'))+f'<circle data-current-loss="{key}" cx="{left+4*23}" cy="{315-(mean(abs(a-4) for a in target) if key=="MAE" else mean((a-4)**2 for a in target))/maxv*220}" r="6" fill="#0f766e"/>'
  for v in [0,5,10]:b+=tx(left+v*23-3,342,v)
  for v in [0,maxv/2,maxv]:b+=tx(left-32,320-v/maxv*220,f'{v:g}')
 g4=fig('target','손실과 예측 대상',b,'그림 4. 가로축은 상수 예측 c입니다. 왼쪽은 MAE, 오른쪽은 MSE이며 세로 척도·단위가 다릅니다. 같은 곡선의 높이를 직접 비교하는 그림이 아닙니다.')
 g1=g1.replace('<svg ','<div class="errors-controls" hidden=""><label for="errors-model">관측별 모형 보기</label><select id="errors-model"><option value="all">함께 비교</option><option value="A">모형 A</option><option value="B">모형 B</option></select><p id="errors-model-status" role="status" aria-live="polite"></p><div id="errors-observations" class="learn-data learn-data--full"></div></div><svg ',1)
 g2=g2.replace('<svg ','<div class="errors-controls" hidden=""><label for="errors-metric">평가 지표 선택</label><select id="errors-metric"><option value="MAE">MAE 기준</option><option value="RMSE">RMSE 기준</option></select><p id="errors-ranking-status" role="status" aria-live="polite"></p></div><svg ',1)
 g4=g4.replace('<svg ','<div class="errors-controls" hidden=""><label for="errors-constant">상수 예측 c</label><input id="errors-constant" type="range" min="0" max="10" step="0.05" value="4" /><div class="errors-shortcuts"><button type="button" data-constant="2">중앙값 2로 이동</button><button type="button" data-constant="4">평균 4로 이동</button></div><p id="errors-loss-status" role="status" aria-live="polite"></p><p>초록 점은 현재 c, 주황 점은 각 손실의 최소점입니다. 두 세로축의 단위와 척도는 다릅니다.</p></div><svg ',1)
 parts=render_content([g1,g2,g3,g4])
 p=ROOT/'prediction-errors/index.html';p.parent.mkdir(exist_ok=True);html=p.read_text(encoding='utf-8') if p.exists() else (ROOT/'overfitting/index.html').read_text(encoding='utf-8').replace('https://ch2data.com/learn/stats/overfitting/','https://ch2data.com/learn/stats/prediction-errors/')
 html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="예측오차: MAE·RMSE·MAPE">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1MAE·RMSE·MAPE의 산식과 단위, 순위 차이와 0 근처 문제, 예측 대상과 평가 기준을 학습합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);html=add_assets(html,d);p.write_text(html,encoding='utf-8')

def add_assets(html,data):
 html=html.replace('prediction-errors/experiment.js?v=20261025-1','prediction-errors/experiment.js?v=20261025-2')
 html=html.replace('별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.','활용도는 CH2 Macro의 분석 결과를 이해하는 데 얼마나 도움이 되는지를 나타냅니다.')
 if 'prediction-errors/chapter.css' not in html:html=html.replace('</head>','<link rel="stylesheet" href="/learn/stats/prediction-errors/chapter.css?v=20261025-1" /></head>')
 payload='<script type="application/json" id="errors-data">'+json.dumps(data,ensure_ascii=False)+'</script>'
 if 'id="errors-data"' in html:html=re.sub(r'<script type="application/json" id="errors-data">.*?</script>',lambda _:payload,html,flags=re.S)
 else:html=html.replace('</body>',payload+'</body>')
 if 'prediction-errors/experiment.js' not in html:html=html.replace('</body>','<script type="module" src="/learn/stats/prediction-errors/experiment.js?v=20261025-2"></script></body>')
 return html

def macro_notes():
 return '<details class="learn-more"><summary>실제 Macro의 평가 단위·가중치·0 처리 확인</summary><div class="learn-more__body"><p>복합의 확인한 학습 MAPE는 거래금액(만원)의 원척도에서 계산하며, 유한한 실제값·예측값 중 실제값 0을 제외하고 관측별 APE를 단순 평균해 백분율로 표시합니다. 롤링 CV도 로그 모형의 예측을 각 학습 fold 잔차로 보정해 원금액으로 돌린 뒤 평가합니다. 확인한 경로는 평가 관측의 APE를 모아 평균하며, 폴드별 RMSE 평균과 같은 계산이 아닙니다.</p><p>집합 주거 지역회귀는 단지별 중앙단가를 목표로 하며 동일 가중(equal)이 기본입니다. 거래수 가중(tx)을 선택하는 경로는 n_tx/(n_tx+10) 형태의 가중치를 사용하고, 원 단위 RMSE와 MAPE에도 같은 가중 모드를 적용합니다. 이는 거래 한 건씩의 동일 가중 평가와 다릅니다. MAPE는 실제값 0을 제외한 분모 가중치 합으로 나누고 RMSE는 포함 관측의 가중 제곱오차 평균의 제곱근입니다. 양수 가격 영역을 전제로 분모에 실제값을 쓰는 구현이며 음수 일반 자료의 MAPE 함수와 같다고 확대하지 않습니다.</p><p>복합 예측형 척도 비교는 CV-MAPE를 우선하고 없으면 학습 MAPE 등을 참조합니다. 설명형은 같은 로그 종속변수의 AIC를 비교합니다. 집합 주거 추천은 예측형 Holdout MAPE, 설명형 원 단위 수정 R²를 사용합니다. 이 장의 MAE/RMSE 전환이 실제 추천의 기본 지표를 변경하는 기능은 아닙니다. 랩의 릿지·라쏘·제곱항 실험과 일반 서비스도 구별합니다.</p><p>후보별 결측 조건 때문에 평가 표본이 달라질 수 있고, 선택에 사용한 Holdout은 최종 독립 시험이 아닙니다. 표시 반올림 전의 선택 기준과 작은 점수 차이의 불확실성을 별도로 검토해야 합니다. 이 장에서는 실제 서비스의 지표나 추천 정책을 바꾸지 않습니다.</p><p>복합 잔차 진단에는 금액·면적·연도·범주 등에 따른 오차 요약과 영향 관측 경로가 있습니다. 이를 모든 서비스가 공통된 지역·유형별 MAE/RMSE, 최대오차·상위 분위수를 제공한다는 뜻으로 확대하지 않습니다. 최신 구현에서의 노출 항목과 0 제외 건수 안내, 후보 간 동일 표본 비교는 별도 점검 대상으로 기록했습니다.</p><p>본 장 공통 자료의 MAE·RMSE는 문안대로 Y와 같은 단위로 읽습니다. 공통 예시의 실제 거래 출처와 대표성은 검증되지 않았으며 여기의 세 지표를 현재 Macro 서비스 성능으로 해석하지 않습니다.</p></div></details>'

def render_content(graphs):
 page=ROOT/'prediction-errors/index.html'
 old=page.read_text(encoding='utf8')
 refs=re.search(r'<details class="learn-references">.*?</details>',old,re.S)[0]
 source=(ROOT/'prediction-errors/content.md').read_text(encoding='utf8').replace('**','').replace('<text color="secondary">그림에 표시할 핵심 계산값</text>','지표별 계산 비교')
 formulas=['eᵢ = yᵢ−ŷᵢ','(10+(−10))/2 = 0','MAE = (1/n) Σ |yᵢ−ŷᵢ|','MAE = (10+20+30)/3 = 20','MSE = (1/n) Σ (yᵢ−ŷᵢ)²','RMSE = √[(1/n) Σ (yᵢ−ŷᵢ)²]','RMSE = √[(10²+20²+30²)/3]','RMSE ≥ MAE','(0+0+0+8)/4 = 2','(3+3+3+3)/4 = 3','√[(0+0+0+64)/4] = 4','√[(9+9+9+9)/4] = 3','MAPE = (100/n) Σ |(yᵢ−ŷᵢ)/yᵢ|','APE = (10/100)×100 = 10%','MAPE = (100+10+1)/3 = 37%','WAPE = 100 Σ |yᵢ−ŷᵢ| / Σ |yᵢ|','sMAPE = (100/n) Σ [2|yᵢ−ŷᵢ|/(|yᵢ|+|ŷᵢ|)]','MAEw = Σ wᵢ|eᵢ| / Σ wᵢ','RMSEw = √[Σ wᵢeᵢ² / Σ wᵢ]']

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
   out.append('<p'+(' class="errors-formula"' if (any(line==formula for formula in formulas) or line.startswith(('ME =','MSE =','MAE =','RMSE =','MAPE ='))) else '')+'>'+inline(line)+'</p>')
  return '\n'.join(out)
 ids=['quick-start','errors','mae','rmse','ranking','mape-definition','mape','mape-limits','target','common','weights','distribution','comparison','practice','macro','recap']
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
  if id in {'mae','mape-limits','common','distribution'}:content='<span id="'+{'mae':'definitions','mape-limits':'alternatives','common':'example','distribution':'report'}[id]+'" aria-hidden="true"></span>'+content
  if id=='quick-start':content=content.replace('<ul>','<ul class="learn-objectives">',1)
  content=content.replace('교차검증은 26장에서','교차검증은 <a href="/learn/stats/cross-validation/">26장</a>에서').replace('26장 「교차검증과 모형 선택」','<a href="/learn/stats/cross-validation/">26장 「교차검증과 모형 선택」</a>')
  parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{heading}</h2>{content}</section>')
 return parts
if __name__=='__main__':build()
