"""Chapter 20: log transformations and retransformation."""
from pathlib import Path
from statistics import mean
from html import escape
import math,json,re
from _build_regression_chapter import fit
ROOT=Path(__file__).resolve().parent

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];x=[r['area'] for r in rows];y=[r['price'] for r in rows];lx=list(map(math.log,x));ly=list(map(math.log,y))
 models={}
 for key,xx,yy,logy in [('level',x,y,False),('log_y',x,ly,True),('log_x',lx,y,False),('log_log',lx,ly,True)]:
  m=fit(xx,yy);m['predictions']=[math.exp(m['intercept']+m['slope']*v) if logy else m['intercept']+m['slope']*v for v in xx];m['MAE']=mean(abs(a-b) for a,b in zip(y,m['predictions']));m['smearing']=mean(math.exp(e) for e in m['residuals']) if logy else None;models[key]=m
 def pred(key,v):
  m=models[key];z=math.log(v) if key in ['log_x','log_log'] else v;value=m['intercept']+m['slope']*z;return math.exp(value) if key in ['log_y','log_log'] else value
 curve=[dict(x=22+i*288/100,**{k:pred(k,22+i*288/100) for k in models}) for i in range(101)]
 percentages=[dict(change=c,exact=100*((1+c/100)**models['log_log']['slope']-1),approx=models['log_log']['slope']*c) for c in [1,10,50,100]]
 (ROOT/'log-regression-example.json').write_text(json.dumps(dict(description='공통 학습 자료 30건의 면적 X(㎡)와 단가 Y(만원/㎡)를 사용한 자연로그 OLS. 단순 지수변환은 산술평균 예측이 아님.',models=models,curves=curve,percentages=percentages,retransform=dict(values=[1,2,8],geometric=16**(1/3),arithmetic=11/3)),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def ln(x,y,a,b,c='#94a3b8'):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="{c}"/>'
 def dot(x,y,c='#2563eb'):return f'<circle cx="{x}" cy="{y}" r="4" fill="{c}"/>'
 def fig(id,title,b,cap,h=400):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=tx(24,28,'같은 배수는 로그 축에서 같은 간격')
 b+=tx(24,85,'원래 값')+ln(110,110,590,110)+tx(24,225,'자연로그')+ln(110,250,590,250)
 for v in [10,20,40,80]:
  a=110+v*5.5;z=110+(math.log(v)-math.log(10))*210;b+=dot(a,110)+tx(a-10,145,v)+dot(z,250)+tx(z-12,285,v)
 b+=tx(24,340,'아래 점의 위치 = ln(값), 숫자는 원래 값을 표시')+tx(24,373,'10 → 20 → 40 → 80: 매번 ×2, 로그 차이는 ln 2')
 f1=fig('scale','원래 축과 로그 축',b,'그림 1. 별도 양수 예제입니다. 로그는 순서를 유지하면서 곱셈 관계를 덧셈 관계로 바꿉니다. 아래 축은 자연로그 위치에 원래 값으로 눈금을 붙였습니다.')
 b=tx(24,28,'거래단가 (만원/㎡) · 공통 학습 자료 30건')+ln(65,325,580,325)+ln(65,55,65,325)
 for xx,yy in zip(x,y):b+=dot(65+xx*1.55,325-yy*.5,'#94a3b8')
 for key,c in [('level','#2563eb'),('log_y','#d97706'),('log_x','#9333ea'),('log_log','#16a34a')]:b+='<polyline data-model="'+key+'" points="'+' '.join(f"{65+r['x']*1.55},{325-r[key]*.5}" for r in curve)+'" fill="none" stroke="'+c+'" stroke-width="2"/>'
 for v in [0,100,200,300]:b+=tx(60+v*1.55,348,v)
 for v in [0,100,200,300,400,500]:b+=tx(25,330-v*.5,v)
 b+=tx(24,380,'파랑: 원래 척도 / 주황: Y만 로그')+tx(24,405,'보라: X만 로그 / 초록: 둘 다 로그')+tx(420,430,'면적 (㎡)')
 f2=fig('curves','변환에 따른 네 가지 적합곡선',b,'그림 2. 공통 학습 자료 30건의 면적(㎡)과 단가(만원/㎡)입니다. 관측 면적 범위 22~310㎡에서만 그렸습니다. 주황·초록은 로그 적합값을 단순 지수변환한 곡선이며, 산술평균을 위한 재변환 보정은 적용하지 않았습니다.',455)
 controls='<div class="lg-controls" hidden><label for="lg-model">비교할 회귀모형</label><select id="lg-model"><option value="all">전체 비교</option><option value="level">원래 척도</option><option value="log_y">로그-선형</option><option value="log_x">선형-로그</option><option value="log_log">로그-로그</option></select><div id="lg-model-status" role="status" aria-live="polite"></div><p class="learn-source-note">모든 관측점은 같은 위치에 유지됩니다. 로그-선형·로그-로그 곡선은 산술평균 보정 없는 단순 역변환입니다.</p></div>'
 f2=f2.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="lg-curves">').replace('<svg ',controls+'<svg class="lg-curves-svg" ',1)
 b=tx(24,28,'면적 +10% · 정확한 변화율과 근사 변화율')+ln(120,70,570,70)
 exact=100*math.expm1(models['log_log']['slope']*math.log1p(.1));approx=models['log_log']['slope']*10
 for key,xx,value,color,label in [('exact',250,exact,'#2563eb','정확식'),('approx',430,approx,'#d97706','근삿값')]:
  b+=f'<rect data-percent="{key}" x="{xx-30}" y="70" width="60" height="{-value*4.5}" fill="{color}"/>'+tx(xx-35,365,label)+f'<text data-percent-label="{key}" x="{xx-40}" y="{-value*4.5+92}">{value:.2f}%</text>'
 for v in [0,-10,-20,-30,-40,-50,-60]:b+=tx(65,75-v*4.5,v)
 b+=tx(24,395,'세로'+': 지수변환 적합값 변화율(%) · 동일한 축 범위')
 f3=fig('percent','면적 증가율에 따른 정확식과 근삿값',b,'그림 3. 공통 자료의 로그-로그 기울기를 사용한 가상 변화율 비교입니다. 근사 bc%와 정확식 100[(1+c/100)^b−1]%는 큰 변화에서 달라집니다.',415)
 controls='<div class="lg-controls" hidden><label for="lg-change">면적 증가율 <output id="lg-change-value" for="lg-change">10%</output></label><input id="lg-change" aria-label="면적 증가율" type="range" min="0" max="100" step="1" value="10"><div class="lg-quick">'+''.join(f'<button type="button" data-change="{v}">+{v}%</button>' for v in [1,10,50,100])+'</div><p id="lg-percent-status" role="status" aria-live="polite"></p></div>'
 f3=f3.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="lg-percent">').replace('<svg ',controls+'<svg ',1)
 b=tx(24,28,'가상 세 값 1, 2, 8을 같은 비중으로 평균')+ln(120,320,570,320)
 for i,(label,v) in enumerate([('기하평균',16**(1/3)),('산술평균',11/3)]):
  xx=210+i*210;b+=f'<rect x="{xx-40}" y="{320-v*60}" width="80" height="{v*60}" fill="'+('#2563eb' if i==0 else '#d97706')+'"/>'+tx(xx-18,305-v*60,f'{v:.2f}')+tx(xx-35,350,label)
 for v in [0,1,2,3,4]:b+=tx(65,325-v*60,v)
 b+=tx(24,385,'exp[(ln 1 + ln 2 + ln 8)/3] ≈ 2.52 ≠ 11/3 ≈ 3.67')
 f4=fig('retransform','로그'+' 평균의 지수변환과 산술평균',b,'그림 4. 가상 자료 1, 2, 8의 기하평균과 산술평균입니다. 공통 학습 자료의 예측오차 비교가 아닙니다. 로그 평균의 지수변환은 산술평균과 다릅니다.')
 # Each panel shows residuals on the scale actually used for its OLS fit.
 # Different vertical units must not be compared as error magnitudes.
 b=''
 for panel,(key,label) in enumerate([('level','원래 척도'),('log_y','Y만 로그')]):
  top=panel*285; model=models[key]
  fitted=[model['intercept']+model['slope']*v for v in x]
  lo,hi=min(fitted),max(fitted);bound=max(abs(e) for e in model['residuals'])*1.12
  px=lambda v:85+(v-lo)/(hi-lo)*475
  py=lambda v:top+145-v/bound*90
  b+=tx(24,top+25,label+' · '+('잔차(Y 단위)' if key=='level' else '로그 잔차(자연로그 단위)'))
  b+=ln(85,top+50,85,top+240)+ln(85,py(0),560,py(0))
  for value in [-bound,0,bound]:b+=tx(24,py(value)+5,f'{value:.1f}' if key=='level' else f'{value:.2f}')
  for value in [lo,(lo+hi)/2,hi]:b+=tx(px(value)-18,top+260,f'{value:.1f}')
  for value,e in zip(fitted,model['residuals']):b+=dot(px(value),py(e),'#2563eb' if key=='level' else '#d97706')
  b+=tx(360,top+280,'적합값' if key=='level' else '로그 적합값')
 f5=fig('residual-check','원래 척도와 로그 척도의 잔차',b,'그림 5. 같은 교육용 자료 30건을 각각 원래 Y와 ln Y에 적합했습니다. 위는 원 단위 잔차, 아래는 로그 잔차입니다. 축의 단위와 범위가 다르므로 점의 높이로 오차 크기를 직접 비교하지 않습니다. 두 그림 모두 0선 주변의 굽음·퍼짐·떨어진 점을 살펴보세요.',590)
 parts=[]
 page=ROOT/'log-regression/index.html';old=page.read_text(encoding='utf-8')
 references=re.search(r'<details class="learn-more"><summary>참고자료(?:와 계산 자료)?</summary>.*?</details>',old,re.S)[0].replace('공통 학습 자료의 두 수치열을 단위 없는 X,Y로 사용했습니다.','공통 학습 자료의 면적(㎡)과 거래단가(만원/㎡)를 사용했습니다.')
 source=(ROOT/'log-regression/content.md').read_text(encoding='utf-8').replace('**','').replace('\\~','~')
 formulas={r'100[\exp(b\Delta)-1]\%':'100[exp(bΔ)−1]%',r'b\ln(1+c/100)':'b ln(1+c/100)',r'100[(1+c/100)^b-1]\%':'100[(1+c/100)ᵇ−1]%',r'100(2^{-0.53136}-1)\%':'100[2^(−0.53136)−1]%',r'E[Y\mid X]=\exp(m(X))E[\exp(\varepsilon)\mid X]':'E[Y|X] = exp(m(X)) E[exp(ε)|X]',r'E[Y\mid X]=\exp(m(X)+\sigma^2/2)':'E[Y|X] = exp(m(X)+σ²/2)',r'S=\frac{1}{n}\sum_{i=1}^n\exp(e_i)':'S = (1/n) Σ exp(eᵢ)',r'Y=a+b\ln X+\varepsilon':'Y = a+b ln X+ε',r'Y=a+bX+cX^2+\varepsilon':'Y = a+bX+cX²+ε',r'\frac{d\hat Y}{dX}=b+2cX':'dŶ/dX = b+2cX'}
 source=re.sub(r'\\\[\s*\n(.*?)\n\\\]',lambda m:formulas[m[1].strip()],source,flags=re.S)
 ids=['introduction','quick-start','forms','log-linear','linear-log','percent','example','retransform','intervals','compare','domain','units','nonlinear','practice','macro','recap']
 def inline(value):return escape(value)
 def render(block):
  out=[];lines=block.strip().split('\n');i=0
  while i<len(lines):
   line=lines[i].strip()
   if not line or line=='---':i+=1;continue
   if line.startswith('### '):out.append('<h3>'+inline(line[4:])+'</h3>');i+=1;continue
   if line.startswith('[그림 '):out.append({1:f1,2:f2,3:f3,4:f4}[int(re.search(r'그림 (\d)',line)[1])]);i+=1;continue
   if line=='[CH2 Macro 통계·데이터분석 열기 →]':out.append('<p><a href="https://macro.ch2data.com/built/">CH2 Macro 복합 통계·데이터분석 열기 →</a></p>');i+=1;continue
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
   formula=line.startswith(('ln ','ŷ','Y =','X>','exp(','100[','100(','b ×','b ln','S =','E[','비율 =','(1+','(1×','dŶ'))
   out.append('<p'+(' class="lg-formula"' if formula else '')+'>'+inline(line)+'</p>');i+=1
  return '\n'.join(out)
 for id,section in zip(ids,re.split(r'^## ',source,flags=re.M)[1:],strict=True):
  label,body=section.split('\n',1);heading=re.search(r'^### (.+)$',body,re.M)[1];body=re.sub(r'^### .+\n','',body,count=1,flags=re.M)
  if id=='practice':
   items=[]
   for q in re.split(r'^\d+\. ',body,flags=re.M)[1:]:
    question,answer=q.split('▶ 답과 해설',1);items.append('<li>'+inline(question.strip())+'<details><summary>답과 해설</summary><div class="learn-more__body">'+render(answer)+'</div></details></li>')
   html='<ol class="learn-exercises">'+''.join(items)+'</ol>'
  else:html=render(body)
  if id=='introduction':html=html.replace('<ul>','<ul class="learn-objectives">',1)+'<p class="learn-source-note"><a href="/learn/stats/graphs/#data">공통 학습 자료 30건</a> · <a href="../log-regression-example.json">네 모형의 계산 자료 JSON</a>. 실제 거래의 출처·대표성이 검증되지 않은 학습 자료이며, 별도 가상 예제와 구별합니다.</p>'
  if id=='percent':html+='<p class="learn-source-note">이 탄력성은 로그 적합값을 지수변환한 곡선에 관한 것입니다. 원 단위 산술평균의 탄력성에는 E[exp(ε)|X]의 변화도 반영해야 합니다.</p>'
  if id=='compare':html+='<details class="learn-more" id="residual-patterns"><summary>보충 그림: 원래 척도와 로그 척도의 잔차</summary><div class="learn-more__body">'+f5+'</div></details>'
  if id=='forms':html='<span id="why-log" aria-hidden="true"></span>'+html
  if id=='macro':html=macro_case();heading='실제 로그-로그 회귀 화면에서 변환·보정·검증 범위를 읽으세요'
  if id=='recap':html=html.replace('21장 「회귀모형의 적합도와 추정의 불확실성」','<a href="/learn/stats/model-fit/">21장 「회귀모형의 적합도와 추정의 불확실성」</a>')
  parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{heading}</h2>{html}</section>')
 html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="로그변환과 비선형 관계">'+'\n'.join(parts)+'</article>',old,count=1,flags=re.S)
 html=html.replace('별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.','활용도는 CH2 Macro의 분석 결과를 이해하는 데 얼마나 도움이 되는지를 나타냅니다.')
 if 'log-regression/chapter.css' not in html:html=html.replace('</head>','<link rel="stylesheet" href="/learn/stats/log-regression/chapter.css?v=20261024-1" />\n</head>')
 data=json.dumps(models,ensure_ascii=False).replace('</','<\\/')
 html=html.replace('</body>','<script type="application/json" id="lg-model-data">'+data+'</script>\n</body>') if 'id="lg-model-data"' not in html else re.sub(r'<script type="application/json" id="lg-model-data">.*?</script>',lambda _: '<script type="application/json" id="lg-model-data">'+data+'</script>',html,flags=re.S)
 if 'log-regression/experiment.js' not in html:html=html.replace('</body>','<script type="module" src="/learn/stats/log-regression/experiment.js?v=20261024-1"></script>\n</body>')
 page.write_text(html,encoding='utf-8')

def macro_case():
 return '''<p>아래는 구로동 복합부동산 로그-로그 회귀 화면입니다. 조회 거래 217건에서 숫자 결측 12건을 제외한 적합 표본 205건이 표시됩니다. ‘지분 64건 제외’는 별도 조건이며, 이 캡처만으로 전체 필터 처리 순서를 재구성하지 않습니다. 공통 학습 자료 30건과 다른 사례입니다.</p>
<figure class="lg-macro-case"><a href="macro-loglog-regression.png" target="_blank" rel="noopener"><img src="macro-loglog-regression.png" width="1186" height="798" loading="lazy" alt="구로동 복합 로그-로그 회귀. 표본 205건, 설계 열 13개·독립 계수 11개로 식별 경고. R² 0.83564, 수정 R² 0.82717, 학습 MAPE 23.11%, CV-MAPE 미산출. log(금액)에 log(연면적) 0.2995, log(대지면적) 0.6794 등이 표시됩니다."></a><figcaption>실제 Macro 화면 캡처 · 선택하면 원본 크기로 볼 수 있습니다. 수치는 캡처 당시 값이며, 원자료와 전체 설정이 없어 독립 검산한 시장 통계로 제시하지 않습니다.</figcaption></figure>
<p>이 식의 종속변수는 log(금액)입니다. 학습 예제의 log(단가)와 구별하세요. 복합의 log-log 설정은 금액과 선택된 연면적·대지면적에 자연로그를 적용합니다. 연식과 범주 더미까지 모두 로그로 바꾸는 모형은 아닙니다. 개별공시지가는 선택되면 별도로 자연로그를 사용합니다.</p>
<p>화면의 연면적계수 0.2995는 식별된 가산적 로그-로그 모형이라면, 다른 포함 변수를 고정하고 연면적이 1% 다를 때 단순 역변환 적합값이 약 0.30% 다르다는 식으로 읽습니다. 하지만 이 캡처는 설계 열 13개에 독립 계수 11개로 계수가 고유하지 않다는 경고가 있습니다. 따라서 0.2995나 0.6794를 안정적으로 식별된 개별 탄력성 또는 인과효과로 확정해서는 안 됩니다.</p>
<p>학습 R²=0.83564와 수정 R²=0.82717은 로그 금액 척도의 표본 내 적합도입니다. 원 단위 모형의 R²와 직접 순위를 매기지 마세요. 학습 MAPE=23.11%는 원래 금액으로 복원한 값에 대한 학습 오차입니다. ‘CV-MAPE —’는 0% 오차가 아니라 검증값을 산출하지 못했다는 뜻입니다. 화면에는 고유 계약연도가 3년 미만이거나 마지막 연도 fold를 적합할 수 없다는 안내가 있습니다. 이 이미지로 어느 조건이 원인인지 더 좁혀 판단할 수는 없습니다.</p>
<p>본문의 로그 곡선은 보정 없는 단순 지수변환입니다. 반면 현재 복합 구현은 로그모형의 원 단위 적합값·MAPE와 점추정에 학습 잔차로 구한 Duan 스미어링 계수를 곱합니다. 같은 로그식이라도 두 계산 대상을 섞어 비교하면 안 됩니다. 공통 보정이 조건부 산술평균을 적절히 추정하는지는 오차 구조에 따라 다시 점검해야 합니다.</p>
<details class="learn-more"><summary>실제 서비스의 변환·재변환·모형 비교 방식</summary><div class="learn-more__body">
<p>확인한 복합 경로는 원래 금액, 로그 금액, 금액·면적 로그 모형을 지원하며 np.log와 np.exp, 즉 자연로그와 지수함수를 사용합니다. 로그를 취할 열의 0·음수와 선택된 수치열의 결측은 적합 마스크에서 제외됩니다. 모든 앱이 같은 규칙이라고 가정하지 말고 최종 표본수와 제외 사유를 확인하세요.</p>
<p>복합의 롤링 시점 검증에서는 각 학습 fold의 잔차만으로 스미어링 계수를 구해 검증 금액을 복원합니다. 검증 거래의 실제 금액은 오차 평가에 사용하며 보정계수 계산에는 사용하지 않습니다. 다만 이것만으로 변수 선택·범주 구성 등 전처리 전체의 누출 가능성까지 검증되었다는 뜻은 아닙니다.</p>
<p>복합의 점추정과 평균 구간 양 끝에는 학습 스미어링 계수를 곱하고, 개별 예측구간 양 끝에는 단순 지수변환을 적용합니다. 평균 구간에 추정된 보정계수의 불확실성까지 전파하는 계산은 확인한 경로에 포함되지 않습니다. 화면의 평균 구간을 재변환 불확실성이 모두 반영된 구간으로 해석하지 않습니다.</p>
<p>집합 주거 회귀의 확인한 경로도 로그 종속변수와 스미어링 보정, 학습 fold 잔차에 의한 교차검증 복원을 사용합니다. 다만 이 사실을 집합 비주거·층지수·모든 지역 분석이 같은 종속변수와 표본 규칙을 사용한다는 뜻으로 확대하지 않습니다. 금액·단가·지수 중 분석 대상을 먼저 확인하세요.</p>
<p>확인한 복합 척도 비교 경로는 같은 변수 블록에 대해 양수 금액·선택된 면적 조건을 공통 적용한 뒤 원래 금액·로그 금액·금액과 면적 로그 후보를 적합합니다. 예측형은 원 단위 CV-MAPE를 우선하며, 없으면 학습 MAPE, 이후 AIC를 참조합니다. 설명형은 로그 종속변수 후보끼리 AIC를 비교합니다. 모든 앱·서로 다른 변수 블록의 표본까지 같다는 뜻은 아니므로 유효 표본수와 제외 조건을 함께 확인하세요.</p>
<p>이 캡처의 VIF는 연면적 118.79, 대지면적 142.89, 연식 5.37입니다. 현재 복합 VIF는 선택한 연속변수에서 상수항 없는 보조회귀로 계산하므로 교재의 통상적인 절편 포함 VIF와 다를 수 있습니다. 로그변환이 공선성이나 모형 식별 문제를 자동 해결하지 않는다는 점을 기억하세요. ‘미상’도 기준 범주와 다릅니다.</p>
<p>이 장의 제곱항·상호작용 설명은 학습 원리입니다. 확인한 복합 기본 설계 경로에서는 이 항을 자동 생성하지 않으므로, 첨부 로그-로그 화면을 다항회귀 화면이라고 설명하지 않습니다. 관측 범위 밖의 적용과 개별 물건의 적정가격 해석도 별도 검토가 필요합니다.</p>
</div></details><p class="learn-macro-cta"><a href="https://macro.ch2data.com/built/">CH2 Macro 복합 통계·데이터분석 열기 →</a></p>'''

if __name__=='__main__':build()
