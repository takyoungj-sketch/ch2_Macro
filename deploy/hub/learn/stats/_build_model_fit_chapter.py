"""Chapter 21: fit, coefficient inference and pointwise intervals."""
from pathlib import Path
from statistics import mean
from html import escape
import math,json,re
from scipy.stats import t,f as fdist
from _build_regression_chapter import fit
ROOT=Path(__file__).resolve().parent

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];x=[r['area'] for r in rows];y=[r['price'] for r in rows];m=fit(x,y);n=len(x);df=n-2;sse=m['SSE'];sst=sum((v-mean(y))**2 for v in y);ssr=sst-sse;s=math.sqrt(sse/df);crit=float(t.ppf(.975,df));se_b=s/math.sqrt(m['Sxx']);tv=m['slope']/se_b;pv=float(2*t.sf(abs(tv),df));F=(ssr)/(sse/df)
 def point(v):
  hat=m['intercept']+m['slope']*v;h=1/n+(v-mean(x))**2/m['Sxx'];c=crit*s*math.sqrt(h);p=crit*s*math.sqrt(1+h)
  return dict(x=v,fit=hat,h=h,ci=[hat-c,hat+c],pi=[hat-p,hat+p])
 grid=[point(22+i*288/100) for i in range(101)];p100=point(100)
 result=dict(description='공통 학습 자료 30건의 면적 X(㎡)와 거래단가 Y(만원/㎡)를 사용한 고전적 단순 OLS. 가정 검증 완료를 뜻하지 않음.',n=n,df=df,SST=sst,SSR=ssr,SSE=sse,R2=m['R2'],adjusted_R2=1-(sse/df)/(sst/(n-1)),s=s,RMSE=math.sqrt(sse/n),MAE=mean(abs(e) for e in m['residuals']),slope=m['slope'],slope_se=se_b,slope_ci=[m['slope']-crit*se_b,m['slope']+crit*se_b],t=tv,p=pv,F=F,F_p=float(fdist.sf(F,1,df)),critical=crit,point100=p100,grid=grid,parameters=dict(n=n,df=df,intercept=m['intercept'],slope=m['slope'],xmean=mean(x),Sxx=m['Sxx'],s=s,critical=crit))
 (ROOT/'model-fit-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,v):return f'<text x="{x}" y="{y}">{escape(str(v))}</text>'
 def ln(x,y,a,b,c='#94a3b8',extra=''):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="{c}" {extra}/>'
 def fig(id,title,b,cap,h=400):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 w=500*m['R2'];b=tx(24,30,'평균만 사용할 때의 제곱합을 나누어 봅니다')
 b+=f'<rect x="65" y="105" width="{w}" height="80" fill="#2563eb"/><rect x="{65+w}" y="105" width="{500-w}" height="80" fill="#d97706"/>'
 b+=tx(65,220,f'적합으로 줄어든 부분: {100*m["R2"]:.1f}%')+tx(65,255,f'남은 잔차 부분: {100*(1-m["R2"]):.1f}%')+tx(65,300,f'SST {sst:,.2f} = SSR {ssr:,.2f} + SSE {sse:,.2f}')+tx(24,365,'파랑: SSR / 주황: SSE · 단위: (만원/㎡)²')
 g1=fig('variance','총제곱합의 분해',b,'그림 1. 공통 자료의 절편 포함 OLS 분해입니다. 막대 전체는 SST이며 길이는 제곱합의 비율을 나타냅니다. 관측값의 일정 비율을 정확히 맞혔다는 뜻이 아닙니다.')
 px=lambda v:65+v*1.55;py=lambda v:330-(v+150)*.43
 b=tx(24,28,'평균의 95% 신뢰구간과 새 관측의 95% 예측구간')
 for key,color in [('pi','#ffedd5'),('ci','#bfdbfe')]:
  pts=[(px(r['x']),py(r[key][1])) for r in grid]+[(px(r['x']),py(r[key][0])) for r in reversed(grid)]
  b+='<polygon data-band="'+key+'" points="'+' '.join(f'{a},{v}' for a,v in pts)+'" fill="'+color+'"/>'
 b+=ln(65,py(0),580,py(0))+ln(65,55,65,330)
 b+='<polyline points="'+' '.join(f"{px(r['x'])},{py(r['fit'])}" for r in grid)+'" fill="none" stroke="#2563eb" stroke-width="2"/>'
 for xx,yy in zip(x,y):b+=f'<circle cx="{px(xx)}" cy="{py(yy)}" r="3" fill="#64748b"/>'
 for v in [0,100,200,300]:b+=tx(px(v)-5,350,v)
 for v in [-100,0,100,200,300,400,500]:b+=tx(24,py(v)+5,v)
 b+=tx(24,380,'가로: 면적 (㎡) / 세로: 거래단가 (만원/㎡)')+tx(24,408,'파랑 띠: 평균 / 주황 띠: 새 관측 · 각 X별 점별 구간')
 b+=ln(px(100),55,px(100),330,'#0f766e','stroke-dasharray="7 5" data-selected-area="bands"')
 g2=fig('bands','신뢰구간과 예측구간',b,'그림 2. 고전적 가정 아래의 점별 95% 구간입니다. 전체 곡선을 동시에 95%로 덮는 띠가 아닙니다. 음수 하한도 표시했습니다. 관측 면적은 22~310㎡이며 음수 단가가 타당하다는 뜻은 아닙니다.',435)
 g2=g2.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="mf-bands">').replace('<svg ','<p class="mf-position" id="mf-bands-position">선택 면적 100.00㎡ · 청록 점선</p><svg ',1)
 b=tx(24,28,'면적 100.00㎡에서 같은 중심, 다른 불확실성').replace('<text ','<text id="mf-point-heading" ',1)
 axis=lambda v:90+(v+150)*.85
 for yy,key,label,c in [(130,'ci','평균 반응의 95% 신뢰구간','#2563eb'),(240,'pi','새 거래 한 건의 95% 예측구간','#d97706')]:
  low,high=p100[key];b+=tx(24,yy-32,label)+ln(axis(low),yy,axis(high),yy,c,f'stroke-width="4" data-point-interval="{key}"')+f'<circle data-point-center="{key}" cx="{axis(p100["fit"])}" cy="{yy}" r="5" fill="{c}"/>'+f'<text data-point-label="{key}" x="90" y="{yy+28}">{low:.2f} ~ {high:.2f}</text>'
 b+=ln(90,320,560,320)
 for v in [-100,0,100,200,300,400]:b+=tx(axis(v)-7,345,v)
 b+=tx(24,382,'가로: 거래단가 (만원/㎡) · 두 점은 같은 적합값')
 g3=fig('at100','선택한 면적에서 평균 신뢰구간과 개별 예측구간',b,'그림 3. 면적 100㎡의 적합 단가는 164.08만원/㎡입니다. 평균 95% 구간은 139.14~189.02, 개별 95% 구간은 32.41~295.75만원/㎡입니다. 선택한 면적의 점별 구간이며 실제 거래가격의 보장 범위가 아닙니다.')
 controls='<div class="mf-controls" hidden><label for="mf-area">면적 <output for="mf-area" id="mf-area-value">100.00㎡</output></label><input type="range" id="mf-area" aria-label="비교할 면적" min="22" max="310" step="0.01" value="100"><div class="mf-quick"><button type="button" data-area="100">100㎡로 복원</button><button type="button" data-area="125.93">평균 면적 약 125.93㎡</button></div><div id="mf-point-status" role="status" aria-live="polite"></div><p class="learn-source-note">학습 자료 30건과 회귀계수는 고정합니다. 면적 22~310㎡에서 그림 2의 선택선, 그림 3의 구간과 그림 4의 선택선이 함께 바뀝니다.</p></div>'
 g3=g3.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="mf-point">').replace('<svg ',controls+'<svg ',1)
 b=tx(24,28,'면적 위치에 따른 95% 구간의 반폭 (만원/㎡)')+ln(65,320,580,320)+ln(65,55,65,320)
 for key,c in [('ci','#2563eb'),('pi','#d97706')]:b+='<polyline data-width="'+key+'" points="'+' '.join(f"{px(r['x'])},{320-(r[key][1]-r['fit'])*1.6}" for r in grid)+'" fill="none" stroke="'+c+'" stroke-width="3"/>'
 b+=ln(px(mean(x)),60,px(mean(x)),320,'#64748b','stroke-dasharray="4 4"')
 for v in [0,100,200,300]:b+=tx(px(v)-5,345,v)
 for v in [0,50,100,150]:b+=tx(25,325-v*1.6,v)
 b+=ln(px(100),60,px(100),320,'#0f766e','stroke-dasharray="7 5" data-selected-area="width"')
 b+=tx(24,380,f'면적 (㎡) · 파랑: 평균 / 주황: 새 거래')+tx(24,408,f'회색 점선: 평균 면적 {mean(x):.4f}㎡ / 청록: 선택 면적')
 g4=fig('width','구간 폭과 자료의 중심',b,'그림 4. 가로축은 면적(㎡), 세로축은 95% 구간의 반폭(만원/㎡)입니다. 이 단순 등분산 모형에서는 X의 평균에서 가장 좁고 멀어질수록 넓어집니다. 관측 범위 22~310㎡에서 비교합니다.',435)
 parts=[]
 page=ROOT/'model-fit/index.html';old=page.read_text(encoding='utf-8')
 references=re.search(r'<details class="learn-more"><summary>참고자료(?:와 계산값)?</summary>.*?</details>',old,re.S)[0].replace('공통 학습 자료의 두 수치열을 단위 없는 X,Y로 사용한 30쌍에 고전적 단순 OLS 가정을 적용한 예제입니다.','공통 학습 자료 30건의 면적(㎡)과 거래단가(만원/㎡)에 고전적 단순 OLS 가정을 적용한 예제입니다.')
 source=(ROOT/'model-fit/content.md').read_text(encoding='utf-8').replace('**','').replace('\\~','~')
 formulas={r'R^2=1-\frac{SSE}{SST}':'R² = 1−SSE/SST',r'SST=SSR+SSE':'SST = SSR+SSE',r'R^2_{\mathrm{adj}}'+'\n'+r'=1-\frac{SSE/(n-p)}{SST/(n-1)}':'수정 R² = 1−[SSE/(n−p)]/[SST/(n−1)]',r'SE(b_1)=\frac{s}{\sqrt{S_{xx}}}':'SE(b₁) = s/√Sxx',r't=\frac{b_1}{SE(b_1)}':'t = b₁/SE(b₁)',r'h_0=\frac1n+\frac{(x_0-\bar x)^2}{S_{xx}}':'h₀ = 1/n+(x₀−x̄)²/Sxx',r'\hat y_0\pm t_{0.975,n-2}s\sqrt{h_0}':'ŷ₀ ± t₀.₉₇₅,ₙ₋₂ s√h₀',r'\hat y_0\pm t_{0.975,n-2}s\sqrt{1+h_0}':'ŷ₀ ± t₀.₉₇₅,ₙ₋₂ s√(1+h₀)'}
 formulas.update({r'RMSE=\sqrt{\frac{SSE}{n}}':'RMSE = √(SSE/n)',r'RSE=\sqrt{\frac{SSE}{n-p}}':'RSE = √(SSE/(n−p))'})
 source=re.sub(r'\\\[\s*\n(.*?)\n\\\]',lambda m:formulas[m[1].strip()],source,flags=re.S)
 ids=['quick-start','r-squared','adj-r-squared','error-scale','coefficients','tests','bands','point-example','width','negative','limits','practice','macro','recap']
 def inline(value):return escape(value)
 def render(block):
  out=[];lines=block.strip().split('\n');i=0
  while i<len(lines):
   line=lines[i].strip()
   if not line or line=='---':i+=1;continue
   if line.startswith('### '):out.append('<h3>'+inline(line[4:])+'</h3>');i+=1;continue
   if line.startswith('[그림 '):out.append({1:g1,2:g2,3:g3,4:g4}[int(re.search(r'그림 (\d)',line)[1])]);i+=1;continue
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
   formula=line.startswith(('ŷ','R²','RMSE =','RSE =','수정 R² =','SST =','SE(','t =','F =','h₀','H₀:'))
   out.append('<p'+(' class="mf-formula"' if formula else '')+'>'+inline(line)+'</p>');i+=1
  return '\n'.join(out)
 for id,section in zip(ids,re.split(r'^## ',source,flags=re.M)[1:],strict=True):
  label,body=section.split('\n',1);heading=re.search(r'^### (.+)$',body,re.M)[1];body=re.sub(r'^### .+\n','',body,count=1,flags=re.M)
  if id=='practice':
   items=[]
   for q in re.split(r'^\d+\. ',body,flags=re.M)[1:]:
    question,answer=q.split('▶ 답과 해설',1);items.append('<li>'+inline(question.strip())+'<details><summary>답과 해설</summary><div class="learn-more__body">'+render(answer)+'</div></details></li>')
   html='<ol class="learn-exercises">'+''.join(items)+'</ol>'
  else:html=render(body)
  if id=='quick-start':html=html.replace('<ul>','<ul class="learn-objectives">',1)+'<p class="learn-source-note"><a href="/learn/stats/graphs/#data">공통 학습 자료 30건</a> · <a href="../model-fit-example.json">제곱합·계수 검정·구간 계산 자료</a>. 실제 거래 출처·대표성과 고전적 가정이 검증된 자료는 아닙니다.</p>'
  if id=='bands':html+='<p class="learn-source-note">새 관측의 오차가 학습 자료와 독립이고, 올바른 선형 평균·등분산 정규오차 등 고전적 가정이 적절해야 합니다. 그림은 면적 22~310㎡의 점별 구간입니다.</p>'
  if id=='point-example':html=html.replace('두 구간의 중심은 모두 164.08만원/㎡입니다.','기본값 100㎡에서 두 구간의 중심은 모두 164.08만원/㎡입니다. 위 조절기로 면적을 바꾸면 선택 면적의 적합값과 구간을 확인할 수 있습니다.')
  if id=='width':html+='<p class="learn-source-note">공통 자료의 평균 면적은 125.9333…㎡입니다. 회색 점선은 이 위치를, 청록 점선은 선택한 면적을 나타냅니다.</p>'
  if id=='error-scale':html=html.replace('18장에서 배운 잔차 지표','<a href="/learn/stats/residuals/">18장에서 배운 잔차 지표</a>')+'<span id="mape" aria-hidden="true"></span>'
  if id=='macro':html=macro_case();heading='실제 집합 지역회귀에서 학습 성능과 두 종류의 구간을 구별하세요'
  if id=='recap':html=html.replace('22장 「통계적 설명과 예측, 지도학습과 비지도학습」','<a href="/learn/stats/supervised-unsupervised/">22장 「통계적 설명과 예측, 지도학습과 비지도학습」</a>')
  parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{heading}</h2>{html}</section>')
 html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="회귀모형의 적합도와 추정의 불확실성">'+'\n'.join(parts)+'</article>',old,count=1,flags=re.S)
 html=html.replace('별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.','활용도는 CH2 Macro의 분석 결과를 이해하는 데 얼마나 도움이 되는지를 나타냅니다.')
 if 'model-fit/chapter.css' not in html:html=html.replace('</head>','<link rel="stylesheet" href="/learn/stats/model-fit/chapter.css?v=20261025-1" />\n</head>')
 data=json.dumps(result['parameters'],ensure_ascii=False).replace('</','<\\/')
 html=html.replace('</body>','<script type="application/json" id="mf-model-data">'+data+'</script>\n</body>') if 'id="mf-model-data"' not in html else re.sub(r'<script type="application/json" id="mf-model-data">.*?</script>',lambda _: '<script type="application/json" id="mf-model-data">'+data+'</script>',html,flags=re.S)
 if 'model-fit/experiment.js' not in html:html=html.replace('</body>','<script type="module" src="/learn/stats/model-fit/experiment.js?v=20261025-1"></script>\n</body>')
 page.write_text(html,encoding='utf-8')

def macro_case():
 return '''<p>아래 두 화면은 집합 주거 지역회귀 사례입니다. 위쪽은 학습 성능과 계수표, 아래쪽은 선택 단지의 추정값과 구간을 보여줍니다. 공통 학습 자료 30건의 단순회귀와는 자료의 단위·가중치·모형이 다릅니다.</p>
<figure class="mf-macro-case"><a href="macro-regional-fit.png" target="_blank" rel="noopener"><img src="macro-regional-fit.png" width="996" height="838" loading="lazy" alt="집합 지역회귀 성능. 학습 단지 38개, 유효 단지 24.6, R² 0.69870, 수정 R² 0.62355, 학습 MAPE 21.1%, Holdout 없음. 거래수 가중·로그 단가 적합 안내와 계수별 p값이 표시됩니다."></a><figcaption>실제 화면 1 · 학습 성능과 계수. 이미지를 선택하면 원본 크기로 볼 수 있습니다. 숫자는 캡처 당시 값이며 원자료가 없어 독립 검산한 결과로 제시하지 않습니다.</figcaption></figure>
<p>학습 n=38은 거래 38건이 아니라 학습에 사용한 단지 38개입니다. 이 지역회귀의 결과변수는 단지별 중앙 거래단가이며, 화면에는 ‘거래수 가중 · log 단가’가 표시됩니다. ‘유효 단지 24.6’은 현재 구현에서 거래 건수 t에 따른 가중치 w=t/(t+10)의 합입니다. 독립적인 단지가 정확히 24.6개라거나, 이 값을 그대로 잔차 자유도에 넣는다는 뜻은 아닙니다.</p>
<p>학습 MAPE 21.1%는 학습 단지의 가중 절대 백분율 오차입니다. Holdout n과 Holdout MAPE의 ‘—’는 검증 오차가 0이라는 뜻이 아닙니다. 표본이 작아 별도 Holdout을 만들지 않았다는 안내를 함께 읽으세요. 선택 단지의 중앙값과 적합값 차이 1.4%도 외부 예측 성능의 증거로 볼 수 없습니다.</p>
<p>이 화면의 표기에는 확인할 차이가 있습니다. 공통 회귀식 표시 컴포넌트는 ‘log(금액)’이라고 쓰지만, 지역회귀 엔진은 단지 중앙단가의 자연로그를 적합합니다. 따라서 이 사례의 회귀식을 거래총액 모형으로 읽으면 안 됩니다. 또 로그모형의 R²는 로그 척도의 가중 적합도인 반면, 수정 R²는 스미어링으로 원 단위로 복원한 값의 가중 제곱오차에서 계산됩니다. 표시된 0.69870과 0.62355를 동일 척도의 R²와 수정 R² 한 쌍처럼 해석하지 않습니다.</p>
<figure class="mf-macro-case"><a href="macro-regional-intervals.png" target="_blank" rel="noopener"><img src="macro-regional-intervals.png" width="972" height="722" loading="lazy" alt="개포우성3차 아파트의 단지 예측 사례. 중앙값 2210, 적합값 2241만원/㎡. 평균 95% 추정범위 1911~2630, 개별 단지 95% 예측범위 1320~3552만원/㎡. 감정평가액이나 실제 가격 보장 범위가 아니라는 안내가 있습니다."></a><figcaption>실제 화면 2 · 선택 조건의 평균 추정과 개별 단지 예측. 학습 예제의 새 거래 한 건과 이 화면의 새 단지 한 개는 서로 다른 관측 단위입니다.</figcaption></figure>
<p>선택된 개포우성3차 사례의 추정값은 2,241만원/㎡입니다. 평균 95% 추정범위는 1,911~2,630만원/㎡, 개별 단지 95% 예측범위는 1,320~3,552만원/㎡로 표시됩니다. 평균 관계를 추정하는 구간보다 단지 자체의 변동까지 고려하는 예측범위가 넓습니다. 로그 척도에서 역변환한 구간이므로 원래 단위에서는 중심을 기준으로 대칭일 필요가 없습니다.</p>
<p>이 값은 선택 자료와 모형에서 추정한 통계적 참고값입니다. 특정 단지나 개별 호의 감정평가액·적정가격·실제 거래가격의 보장 범위가 아닙니다. 화면 제목의 ‘평균단가 예측’과 구별해, 실제 학습 목표가 단지 중앙단가라는 점도 함께 확인하세요.</p>
<details class="learn-more"><summary>실제 지역회귀의 적합·검정·구간 계산 방식</summary><div class="learn-more__body">
<p>확인한 집합 주거 지역회귀는 단지 한 개를 한 행으로 구성합니다. 선택 지역·기간·유형과 거래 건수 조건을 적용하고, 중앙단가가 양수이며 선택한 수치 속성이 있는 단지를 사용합니다. 범주 결측은 선택한 미상 유지·제외 정책을 따릅니다. 학습 유효 표본과 원래 조회 표본은 다를 수 있습니다.</p>
<p>단지 균등 설정은 OLS, 거래수 가중 설정은 WLS를 사용합니다. 현재 적합 호출은 고전적 기본 공분산을 사용하며, 이 경로에 이분산 강건 또는 군집 보정 옵션은 확인되지 않습니다. 계수별 SE·t·p와 모형 전체 F검정은 적합 결과에서 가져옵니다. 자유도는 설계행렬의 독립 열 수에 따르며 ‘유효 단지’ 가중치 합으로 대체하지 않습니다.</p>
<p>첨부 계수표는 변수·해석·p를 표시합니다. 백엔드에 SE와 t가 있어도 이 표에 계수의 표준오차·95% 신뢰구간을 이미 제공하는 것처럼 설명하지 않습니다. p값은 표에서 최대 소수 넷째 자리, 전체 F의 p값은 다섯째 자리로 반올림되어 0으로 보일 수 있으며, 확률이 정확히 0이라는 뜻은 아닙니다. RSE·MAE는 이 성능 카드에 없고, 백엔드의 원 단위 가중 RMSE도 첨부 카드에는 표시되지 않습니다.</p>
<p>현재 Holdout 분할은 적격 단지가 40개 미만이면 생략합니다. 그 이상이면 고정 난수로 약 25%를 따로 두며 최소 8개를 사용합니다. 이는 별도 단지에 대한 분할이며 미래 연도나 다른 지역의 성능까지 보장하지 않습니다. 모형 후보 탐색 후의 불확실성도 통상적인 계수 검정에 모두 포함되지는 않습니다.</p>
<p>평균 구간과 개별 예측구간은 적합 모형의 get_prediction(...).summary_frame(alpha=0.05)에서 계산합니다. 로그모형은 학습 잔차의 가중 스미어링 계수로 점추정과 평균 구간 양 끝을 보정합니다. 개별 예측구간은 로그 구간 양 끝을 지수변환합니다. 보정계수 자체의 추정 불확실성을 별도로 전파하는 계산은 확인한 경로에 포함되지 않습니다.</p>
<p>WLS 예측 호출에는 새 단지의 별도 가중치를 전달하지 않습니다. 따라서 거래 건수 가중 적합과 새 단지의 오차분산 가정이 어떻게 연결되는지 추가 검토가 필요합니다. 계산된 ‘95%’를 실제 단지 자료에서 검증된 95% 포함률로 받아들이지 마세요. 지역·시점 의존성과 가중치의 통계적 의미도 따로 확인해야 합니다.</p>
<p>이 확인 범위는 첨부한 집합 주거 지역회귀 경로입니다. 거래별 회귀, 비주거 도로명 집계, 복합 회귀 등 다른 모형에도 같은 관측 단위와 구간 계산이 적용된다고 확대하지 않습니다. 이 장에서는 표기·계산의 차이를 설명하며 실제 분석 및 모형추천 코드를 변경하지 않습니다.</p>
</div></details><p class="learn-macro-cta"><a href="https://macro.ch2data.com/collective/">CH2 Macro 집합 통계·데이터분석 열기 →</a></p>'''

if __name__=='__main__':build()
