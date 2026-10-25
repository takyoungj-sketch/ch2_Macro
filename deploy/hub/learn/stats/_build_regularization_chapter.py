"""Chapter 27: explicit penalty normalization and coefficient paths."""
from pathlib import Path
from statistics import mean,pstdev
from html import escape
import math,json,re
ROOT=Path(__file__).resolve().parent

def build():
 z=[3,1,-.5];path=[dict(lam=i/25,ridge=[v/(1+i/25) for v in z],lasso=[math.copysign(max(abs(v)-i/25,0),v) for v in z]) for i in range(101)]
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];cv=[]
 for lam in [0,.1,1,10]:
  folds=[]
  for k in range(3):
   va=rows[k*10:(k+1)*10];tr=rows[:k*10]+rows[(k+1)*10:];xm=mean(r['area'] for r in tr);xs=pstdev(r['area'] for r in tr);ym=mean(r['price'] for r in tr);cov=mean((r['area']-xm)/xs*(r['price']-ym) for r in tr);b=cov/(1+lam);pred=[ym+b*(r['area']-xm)/xs for r in va];mse=mean((r['price']-v)**2 for r,v in zip(va,pred));folds.append(dict(fold=k+1,xmean=xm,xscale=xs,ymean=ym,b=b,predictions=pred,MSE=mse))
  cv.append(dict(lam=lam,folds=folds,RMSE=math.sqrt(mean(f['MSE'] for f in folds))))
 best=min(cv,key=lambda v:v['RMSE'])
 d=dict(description='직교 가상 예제와 공통 자료의 X 단일 변수 릿지 3폴드. 최종 성능 평가 아님.',normalization='SSE/(2n)+lambda*L2_squared/2 or SSE/(2n)+lambda*L1; intercept excluded',orthogonal=dict(z=z,path=path),cv=cv,best_lambda=best['lam'])
 (ROOT/'regularization-example.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def ln(x,y,a,b):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="#94a3b8"/>'
 def fig(id,title,b,cap):return f'<figure class="learn-chart learn-chart--wide"><svg class="reg-chart-svg" viewBox="0 0 640 410" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 colors=['#2563eb','#d97706','#16a34a'];charts=[]
 for key,label in [('ridge','릿지'),('lasso','라쏘')]:
  b=tx(24,28,f'직교 가상 예제: {label} 계수 경로')+ln(70,290,570,290)+ln(70,55,70,335)
  for j,c in enumerate(colors):b+='<polyline data-index="'+str(j)+'" points="'+' '.join(f"{70+r['lam']*120},{290-r[key][j]*70}" for r in path)+'" fill="none" stroke="'+c+'" stroke-width="2"/>'
  for v in [0,1,2,3,4]:b+=tx(65+v*120,355,v)
  for v in [-.5,0,1,2,3]:b+=tx(25,295-v*70,v)
  b+=tx(24,390,'가로 λ / 세로 계수 · 파랑 z=3, 주황 z=1, 초록 z=−0.5')
  b+=f'<line data-lambda-guide="{key}" x1="190" x2="190" y1="55" y2="335" stroke="#94a3b8" stroke-dasharray="4 4"/>'
  for j,c in enumerate(colors):
   value=z[j]/2 if key=='ridge' else math.copysign(max(abs(z[j])-1,0),z[j]);b+=f'<circle data-current-method="{key}" data-current-index="{j}" cx="190" cy="{290-value*70}" r="6" fill="{c}"/>'
  b+=f'<text id="{key}-current-label" x="430" y="56">현재 λ=1</text>'
  charts.append(fig(key,label+' 계수 경로',b,'그림 '+('1' if key=='ridge' else '2')+'. ZᵀZ/n=I인 별도 가상 조건에서 계산한 경로입니다. 실제 상관된 변수의 계수 경로가 항상 이 모양이거나 각 계수 절댓값이 단조 감소하는 것은 아닙니다.'))
 b=tx(24,28,'두 계수의 제약 영역: 반지름·한계값을 1로 둔 개념도')
 for cx,label in [(180,'릿지: b₁²+b₂² ≤ 1'),(470,'라쏘: |b₁|+|b₂| ≤ 1')]:b+=ln(cx-110,205,cx+110,205)+ln(cx,95,cx,315)+tx(cx-105,365,label)+tx(cx+95,227,'b₁')+tx(cx+10,100,'b₂')
 b+='<circle cx="180" cy="205" r="85" fill="#dbeafe" fill-opacity=".6" stroke="#2563eb"/><polygon points="470,120 555,205 470,290 385,205" fill="#ffedd5" fill-opacity=".6" stroke="#d97706"/>'
 b+=tx(24,395,'제약 영역만 표시 · 손실 등고선 생략 · 특정 λ의 실제 해가 아님')
 charts.append(fig('geometry','L2와 L1 제약',b,'그림 3. 라쏘의 꼭짓점은 한 계수가 0인 축에 놓입니다. 손실 등고선과 만나는 위치에 따라 0인 계수가 생길 수 있음을 돕는 개념도이며 λ=1의 해를 그린 것은 아닙니다.'))
 ymax=max(v['RMSE'] for v in cv)*1.2;b=tx(24,28,'공통 자료: X 단일 변수 릿지의 3폴드 OOF RMSE')+ln(70,320,570,320)
 for i,v in enumerate(cv):
  h=v['RMSE']/ymax*240;xx=110+i*130;b+=f'<rect data-cv-lambda="{v["lam"]}" x="{xx}" y="{320-h}" width="65" height="{h}" fill="#2563eb"/>'+tx(xx+4,308-h,f'{v["RMSE"]:.2f}')+tx(xx+4,350,f'λ={v["lam"]}')
 for v in [0,40,80]:b+=tx(25,325-v/ymax*240,v)
 b+=tx(24,390,'세로: Y와 같은 단위 · 각 폴드의 학습 부분에서만 X 표준화')
 charts.append(fig('cv','규제 강도와 검증 오차',b,'그림 4. 번호 블록 3폴드의 교재용 비교입니다. 단일 변수 릿지이며 라쏘·다중공선성 성능 실험은 아닙니다. 선택에 사용한 점수를 독립 최종 성능으로 읽지 않습니다.'))
 charts[0]=charts[0].replace('<svg ','<div class="reg-controls" hidden=""><label for="reg-lambda">직교 가상 예제 λ — 그림 1·2 공통</label><input id="reg-lambda" type="range" min="0" max="4" step="0.01" value="1" /><div class="reg-shortcuts">'+''.join(f'<button type="button" data-orthogonal-lambda="{value}">λ={value}</button>' for value in [0,.5,1,3])+'</div><p id="reg-orthogonal-status" role="status" aria-live="polite"></p></div><svg ',1)
 charts[1]=charts[1].replace('<svg ','<p id="reg-lasso-status" role="status" aria-live="polite"></p><svg ',1)
 charts[3]=charts[3].replace('<svg ','<div class="reg-controls" hidden=""><label for="reg-cv-lambda">공통 자료 릿지 CV 후보 λ — 직교 예제와 별도</label><select id="reg-cv-lambda">'+''.join(f'<option value="{v["lam"]}">λ={v["lam"]}</option>' for v in cv)+'</select><p id="reg-cv-status" role="status" aria-live="polite"></p></div><svg ',1)
 charts[3]+='<details class="learn-more"><summary>선택 후보의 폴드별 표준화·원 단위 계수</summary><div id="reg-cv-table" class="learn-data learn-data--full"></div></details>'
 parts=render_content(charts)
 p=ROOT/'regularization/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="규제: 릿지와 라쏘">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1릿지·라쏘의 벌점과 계수 경로, 표준화·규제 강도 선택·해석의 한계를 학습합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);html=add_assets(html,d);p.write_text(html,encoding='utf-8')

def add_assets(html,data):
 html=html.replace('regularization/chapter.css?v=20261025-1','regularization/chapter.css?v=20261025-2')
 html=html.replace('Macro 활용도 1단계, 심화','Macro 활용도 3단계, 핵심').replace('<span aria-hidden="true">★☆☆</span>','<span aria-hidden="true">★★★</span>').replace('learn-stats-toc.js?v=20261025-2','learn-stats-toc.js?v=20261025-3')
 html=html.replace('별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.','활용도는 CH2 Macro의 분석 결과를 이해하는 데 얼마나 도움이 되는지를 나타냅니다.')
 if 'regularization/chapter.css' not in html:html=html.replace('</head>','<link rel="stylesheet" href="/learn/stats/regularization/chapter.css?v=20261025-2" /></head>')
 payload='<script type="application/json" id="reg-data">'+json.dumps(data,ensure_ascii=False)+'</script>'
 if 'id="reg-data"' in html:html=re.sub(r'<script type="application/json" id="reg-data">.*?</script>',lambda _:payload,html,flags=re.S)
 else:html=html.replace('</body>',payload+'</body>')
 if 'regularization/experiment.js' not in html:html=html.replace('</body>','<script type="module" src="/learn/stats/regularization/experiment.js?v=20261025-1"></script></body>')
 return html

def macro_notes():
 return '<details class="learn-more"><summary>확인한 Macro·랩의 규제 정의와 학습 경계'+'</summary><div class="learn-more__body"><p>이 학습 계산은 직접 정의한 목적함수와 직교 공식으로 수행합니다. 그림 4는 폴드별 학습 X 평균·모집단형 표준편차와 Y 평균을 새로 계산합니다. 절편은 벌점 밖이며 계수는 원 단위로 복원해도 같은 예측을 냅니다. 교재 λ를 다른 프로그램의 α 숫자와 그대로 비교하지 않습니다.</p><p>확인한 일반 복합·집합 주거 회귀 추천 경로를 릿지·라쏘·엘라스틱넷을 공통 지원하는 기능으로 소개하지 않습니다. 별도 scale_effect_lab에는 NumPy 직접 릿지 선형계 풀이와 라쏘 좌표하강 코드가 있습니다. 릿지는 SSE+αΣb², 라쏘는 SSE/2+αΣ|b|에 대응하는 기울기 갱신을 사용하므로, 중심화·절편 조건이 맞을 때 교재에서는 모두 α=nλ로 환산해야 합니다. 이는 같은 λ 숫자가 두 벌점의 동일한 실질 강도를 뜻한다는 주장은 아닙니다.</p><p>랩은 연속열을 바깥 학습 겹에서 표준화하고 더미는 0/1로 유지하며, 상수에 가까운 연속열의 표준편차는 1로 둡니다. 선택된 열의 벌점에는 더미도 포함됩니다. α 후보는 10⁻³~10²의 로그 간격 10개이고 내부 3겹 MSE로 고르는 경로가 있습니다. 하지만 내부 겹마다 표준화를 다시 적합하는 것은 아니며, 중심화되지 않은 열에도 절편을 Y평균으로 고정하는 경로가 확인됐습니다. 이를 절편을 자유롭게 최적화한 일반 규제회귀와 동일하다고 설명하지 않습니다. 재현 근거와 별도 점검 사항을 보류 문서에 기록했습니다.</p><p>랩의 규제 예측 비교와 별도로 표시하는 OLS 계수·p값을 구분합니다. 일반 OLS p값을 규제계수의 유의성으로 읽지 않습니다. 원 단위 복원·더미 정책·상관 변수의 선택 안정성도 따로 확인해야 합니다. 일반 서비스의 예측형 CV-MAPE/Holdout MAPE와 설명형 AIC·수정 R² 기준을 이번 교재의 OOF RMSE 선택과 혼동하지 않습니다.</p><p>이 장의 직교 예제와 공통 단일 변수 릿지는 실제 Macro 서비스의 성능이나 인과효과를 검증한 결과가 아닙니다. 실제 규제 알고리즘·변수 선택·추론·자료 처리 로직은 변경하지 않았습니다.</p></div></details>'

def render_content(graphs):
 page=ROOT/'regularization/index.html'
 old=page.read_text(encoding='utf8')
 refs=re.search(r'<details class="learn-references">.*?</details>',old,re.S)[0]
 source=(ROOT/'regularization/content.md').read_text(encoding='utf8').replace('**','').replace('<text color="secondary">그림에 표시할 핵심 계산값</text>','지표별 계산 비교')
 formulas=['SSE = Σ (yᵢ−ŷᵢ)²','min over b₀,b: SSE/(2n) + (λ/2) Σ bⱼ²','min over b₀,b: SSE/(2n) + λ Σ |bⱼ|','3²+1²+(−0.5)² = 10.25','ZᵀZ/n = I','bⱼ(λ) = zⱼ/(1+λ)','(3,1,−0.5)÷2 = (1.5,0.5,−0.25)','|3|+|1|+|−0.5| = 4.5','bⱼ(λ) = sign(zⱼ) max(|zⱼ|−λ,0)','b₁²+b₂² ≤ t','|b₁|+|b₂| ≤ t','Zⱼ = (Xⱼ−X̄ⱼ)/sⱼ','βⱼ = bⱼ/sⱼ','SSE/(2n) + λ[ρ Σ |bⱼ| + (1−ρ) Σ bⱼ²/2]']

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
   if line in formulas:out.append('<p class="reg-formula">'+inline(line)+'</p>');continue
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
   out.append('<p'+(' class="reg-formula"' if (any(line==formula for formula in formulas) or line.startswith(('ME =','MSE =','MAE =','RMSE =','MAPE ='))) else '')+'>'+inline(line)+'</p>')
  return '\n'.join(out)
 ids=['quick-start','purpose','objective','ridge','lasso','comparison','geometry','scale','collinearity','cv','elastic','interpretation','stability','practice','macro','recap']
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
  if id=='scale':content+='<p class="reg-formula">원 단위 절편: β₀ = b₀ − Σ (bⱼ μⱼ / sⱼ)</p><p class="learn-source-note">b₀는 표준화된 설명변수 모형의 절편입니다. 그림 4는 학습 X의 모집단형 표준편차(ddof=0)를 사용하고 절편을 규제하지 않습니다.</p>'
  if id=='quick-start':content=content.replace('<ul>','<ul class="learn-objectives">',1)
  content=content.replace('교차검증은 26장에서','교차검증은 <a href="/learn/stats/cross-validation/">26장</a>에서').replace('28장 「분류와 로지스틱 회귀」','<a href="/learn/stats/classification/">28장 「분류와 로지스틱 회귀」</a>')
  parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{heading}</h2>{content}</section>')
 return parts
if __name__=='__main__':build()
