"""Reproducible chapter 18 residual diagnostics."""
from pathlib import Path
from statistics import mean,NormalDist
from html import escape
import json,math,re,random
from _build_regression_chapter import fit
ROOT=Path(__file__).resolve().parent


def macro_case():
 return '''<p>아래는 사용자가 제공한 CH2 Macro 복합 다항회귀의 「잔차 진단」 화면입니다. 교재의 면적·단가 단순회귀 30건과 다른 실제 서비스 사례입니다. 캡처에는 n=112, 중위 오차 −3.6%, 평균 오차 −32.3%가 표시되어 있습니다. 지역·분석 기간·모형 전체 설정은 이미지에 포함되어 있지 않아 현재 조회값이나 원자료 재계산 결과로 제시하지 않습니다.</p>
<figure class="rd-macro-case"><a href="macro-built-residuals.png" target="_blank" rel="noopener"><img src="macro-built-residuals.png" width="823" height="663" loading="lazy" alt="복합 다항회귀 잔차 진단 화면. n=112, 중위 오차 −3.6%, 평균 −32.3%. 가로축 예측금액, 세로축 실제금액 대비 오차율. 표시범위 ±120%, 경계 밖 점은 붉게 표시됩니다. BP p=0.383과 금액 분위별 오차 산포 표가 있습니다."></a><figcaption>실제 복합 다항회귀 화면 캡처 · 숫자는 캡처 당시 값입니다. 이미지를 선택하면 원본 크기로 볼 수 있습니다. 그림 1~4의 학습 자료와 별개입니다.</figcaption></figure>
<p>교재 그림 1의 세로축은 단가의 잔차(만원/㎡)입니다. 이 서비스 화면의 가로축은 예측 거래금액이고 세로축은 원척도 금액의 백분율 오차입니다. 계산 척도가 다르므로 두 그림의 숫자나 퍼짐을 직접 비교하면 안 됩니다.</p>
<p class="rd-formula">화면의 오차율(%) = (실제금액 − 예측금액) / 실제금액 × 100</p>
<p>양수는 해당 모형의 예측금액이 실제 거래금액보다 낮았다는 뜻입니다. 화면의 ‘과소평가’는 이 예측 차이를 가리키며, 감정평가상 저평가·고평가를 판정하는 말이 아닙니다. 평균 −32.3%와 중위수 −3.6%의 차이도 구별해서 읽어야 합니다. 작은 실제금액이 분모에 놓이면 큰 음의 오차율이 평균에 강하게 반영될 수 있습니다. 적합 척도의 OLS 잔차 합이 0이어도 원척도 백분율 오차의 평균은 0일 필요가 없습니다. 중위수 역시 모형의 타당성을 보장하지 않습니다.</p>
<p>붉은 점은 자동 삭제 대상으로 판정된 점이 아닙니다. 이 캡처의 표시범위 ±120%를 벗어나 위·아래 경계에 붙여 표시한 점입니다. 따라서 경계의 점이 모두 정확히 +120% 또는 −120%라는 뜻도 아닙니다.</p>
<p>오차율의 상한도 예측값에 따라 달라집니다. 실제금액이 양수이고 예측금액이 0 이상일 때만 오차율이 +100% 이하입니다. 캡처에는 예측금액 최솟값 −1,400만이 표시되어 있습니다. 음수 예측이 가능한 다항·선형 모형에서는 +100%를 넘는 오차율도 가능하므로, 이미지의 ‘+300%는 불가’ 설명을 모든 모형에 적용할 수는 없습니다.</p>
<p>표의 ‘오차 산포’는 각 예측금액 분위에서 오차율의 표본표준편차입니다. 1분위 68.2%, 5분위 129.4%이지만 2분위는 293.5%입니다. 금액이 커질수록 산포가 계속 커진다는 단조 관계로 단정할 수 없습니다. ‘중위 절대오차’도 MAE·학습 RMSE·RSE와 다른 지표입니다.</p>
<p>화면에는 Breusch–Pagan p=0.383과 ‘등분산 유지’라는 문구가 있습니다. 이는 5% 기준에서 등분산 귀무가설을 기각하지 못했다는 뜻으로 읽어야 합니다. 등분산이 입증되었거나 잔차 그림의 문제가 모두 사라졌다는 뜻은 아닙니다. 금액대별 오차율 산포와 모형 척도의 이분산 검정은 같은 통계가 아닙니다.</p>
<details class="learn-more"><summary>실제 복합 잔차 진단의 계산과 제공 범위</summary><div class="learn-more__body">
<p>이 화면은 적합에 사용한 거래의 표본 내 예측값을 사용합니다. 금액을 로그로 적합한 모형에서는 exp(적합값)에 Duan 보정을 곱해 원척도 금액으로 되돌립니다. 화면 상단 MAPE와 잔차 진단이 같은 원척도 예측값을 사용합니다. 새 거래의 검증 오차나 교차검증 결과와는 구별합니다.</p>
<p>실제 구현은 유한한 실제·예측금액과 0이 아닌 실제금액에서 오차율을 계산하며, 분모는 |실제금액|입니다. 양수인 거래금액에서는 본문의 식과 같습니다. 금액 분위는 예측금액으로 나누고, 각 분위의 중위 예측금액·중위 절대오차율·오차율 표본표준편차를 제공합니다. 집단 요약에는 최소 건수 조건이 있습니다.</p>
<p>지역·용도지역·건축물용도·연식·연면적 분위·계약연도 등의 집단별 요약이 자료와 최소 건수 조건에 따라 제공됩니다. 집단의 ‘전체 대비’는 해당 집단의 중위 오차율에서 나머지 표본의 중위 오차율을 뺀 값입니다. 그림이 보여주는 차이만으로 그 원인을 확정하지 않습니다.</p>
<p>Cook 거리와 레버리지, 영향 상위 거래 및 제외 재적합에 따른 계수 변화도 조건에 따라 제공합니다. 이는 사용자가 원자료와 민감도를 점검하기 위한 진단이며 자동 삭제 규칙이 아닙니다. 확인한 카드에는 정규 Q–Q 그림이나 교재와 같은 MAE·RMSE·RSE가 표시되지 않습니다. 다른 모형 비교 화면의 RMSE와도 평가 표본·척도를 맞춘 뒤 비교해야 합니다.</p>
<p>BP 검정은 화면 오차율이 아니라 적합된 모형의 원래 잔차와 설계행렬을 사용합니다. 로그 종속모형이면 로그 척도 잔차입니다. 확인한 OLS 경로는 일반 표준오차를 사용하며, 이 진단이 이분산 강건 또는 군집 표준오차를 자동 적용하는 것은 아닙니다. 거래 시점·지역·동일 건물의 의존성도 별도로 검토해야 합니다.</p>
<p>회귀에 앞서 선택한 지역·기간·유형·이상치 정책과 변수별 결측 처리가 적용됩니다. 화면의 n은 이 진단에 사용 가능한 오차율의 수입니다. 캡처의 전체 설정과 원자료가 없으므로 n=112나 p=0.383을 이 교재에서 독립적으로 재계산하지는 않았습니다.</p></div></details>
<p>잔차 진단은 시장의 평균적 관계를 점검하는 도구입니다. 개별 물건의 적정가격이나 조건 변경의 인과효과를 확정하지 않습니다.</p><p class="learn-macro-cta"><a href="https://macro.ch2data.com/built/">CH2 Macro 복합 통계·데이터분석 열기 →</a></p>'''

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];x=[r['area'] for r in rows];y=[r['price'] for r in rows];f=fit(x,y);n=len(x);s=math.sqrt(f['SSE']/(n-2))
 ds=[]
 for row,e in zip(rows,f['residuals']):
  h=1/n+(row['area']-mean(x))**2/f['Sxx'];r=e/(s*math.sqrt(1-h));cook=r*r*h/(2*(1-h))
  ds.append(dict(id=row['id'],fitted=row['price']-e,residual=e,leverage=h,standardized=r,cook=cook))
 qq=[dict(z=NormalDist().inv_cdf((i+.5)/n),residual=e) for i,e in enumerate(sorted(f['residuals']))]
 d=dict(description='공통 학습 자료 30건의 면적(㎡)·단가(만원/㎡)에 대한 절편 포함 단순 OLS 진단',n=n,df=n-2,SSE=f['SSE'],s=s,RMSE=math.sqrt(f['SSE']/n),MAE=mean(abs(e) for e in f['residuals']),rows=ds,qq=qq)
 (ROOT/'residuals-example.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def text(x,y,v,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(v))}</text>'
 def line(x,y,xx,yy):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="#94a3b8"/>'
 def dot(x,y,id='',color='#2563eb'):return f'<circle cx="{x}" cy="{y}" r="{6 if id==7 else 4}" fill="{"#d97706" if id==7 else color}" data-id="{id}"><title>{str(id)+"번 관측값" if id else "학습용 점"}</title></circle>'
 def fig(id,title,b,cap,h=390):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=text(24,28,'잔차(만원/㎡)')+line(65,255,580,255).replace('/>',' stroke-width="2" data-zero="true"/>')+line(65,55,65,335)
 for v in [-100,0,100,200]:b+=text(24,260-v*.7,v)
 for v in [0,50,100,150,200]:b+=text(65+v*2.2,355,v)
 for row in ds:
  cx=65+row['fitted']*2.2;cy=255-row['residual']*.7;b+=dot(cx,cy,row['id'])
  if row['id']==7:b+=text(cx-42,cy-12,'7번')
 b+=text(330,382,'적합 단가(만원/㎡)');g1=fig('resplot','적합값과 잔차',b,'그림 1. 17장과 같은 면적·단가 학습 자료 30건의 적합값과 잔차입니다. 주황 점은 id=7이며 번호는 시간 순서가 아닙니다. 0선 주변의 모양과 큰 잔차를 함께 봅니다. 가로축은 관측 Y가 아닌 적합값 ŷ입니다.',410)
 raw_rows=[dict(**row,**{k:v for k,v in diagnostic.items() if k!='id'}) for row,diagnostic in zip(rows,ds)]
 def observation_controls(kind):
  return '<div class="rd-controls" hidden><label for="rd-select-'+kind+'">관측값 확인</label><select id="rd-select-'+kind+'">'+''.join(f'<option value="{r["id"]}"'+(' selected' if r['id']==7 else '')+f'>{r["id"]}번 · {r["group"]}</option>' for r in rows)+'</select><p class="rd-observation-status" role="status" aria-live="polite"></p></div>'
 g1=g1.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide rd-observations" id="rd-fit">').replace('<svg',observation_controls('fit')+'<script type="application/json" id="rd-data">'+json.dumps(raw_rows,ensure_ascii=False)+'</script><svg',1).replace('<svg ','<svg class="rd-observation-svg" ',1)
 rng=random.Random(180);noise=[rng.uniform(-32,32) for _ in range(30)];center=mean(noise)
 patterns={'none':{'title':'특별한 패턴 없음','note':'중심과 폭에 뚜렷한 문제를 시사하는 패턴이 보이지 않는 예시입니다. 모든 가정이 확인된 것은 아닙니다.','points':[[i//2,noise[i]-center] for i in range(30)]},'curve':{'title':'곡선형 · 평균 관계 점검','note':'잔차 중심이 U자형입니다. 평균 함수·변환·집단 차이 등을 검토할 단서이며 원인을 확정하지 않습니다.','points':[[i,((i-7)/7)**2*100-38+sign*7] for i in range(15) for sign in [-1,1]]},'fan':{'title':'부채꼴 · 오차분산 점검','note':'중심은 0 부근이고 폭이 넓어집니다. 이분산 가능성을 시사하며 평균 관계의 곡선과 구별합니다.','points':[[i,sign*(8+i*4)] for i in range(15) for sign in [-1,1]]}}
 b=''
 for j,(key,pattern) in enumerate(patterns.items()):
  b+=f'<g data-pattern="{key}" data-panel="{j}" transform="translate(0 {j*255})">'+text(24,28,pattern['title'])+text(24,53,'잔차(임의 단위)')+line(90,140,580,140).replace('/>',' stroke-width="2"/>')+line(90,65,90,205)
  for tick in [-80,0,80]:b+=text(70,145-tick*.75,tick,'text-anchor="end"')
  for tick in [0,7,14]:b+=text(100+tick*32,226,tick,'text-anchor="middle"')
  for xx,ee in pattern['points']:b+=f'<circle cx="{100+xx*32}" cy="{140-ee*.75}" r="3.5" fill="#2563eb" data-x="{xx}" data-e="{ee}"/>'
  b+=text(300,250,'가상 적합값(임의 단위) · 공통 잔차 축 −80~80')+'</g>'
 g2=fig('patterns','잔차 패턴 비교 · 특별한 패턴 없음 / 곡선형 / 부채꼴',b,'그림 2. 패턴을 설명하기 위해 구성한 가상 개념도입니다. 세 패널은 같은 축 범위와 배율입니다. 곡선은 평균 함수, 부채꼴은 오차분산을 점검하는 단서이며 원인을 확정하지 않습니다.',785)
 controls='''<div class="rd-controls" hidden><div class="rd-actions" role="group" aria-label="잔차 패턴 보기"><button type="button" data-mode="all" aria-pressed="true">세 패턴 비교</button><button type="button" data-mode="none" aria-pressed="false">특별한 패턴 없음</button><button type="button" data-mode="curve" aria-pressed="false">곡선형</button><button type="button" data-mode="fan" aria-pressed="false">부채꼴</button></div><p id="rd-pattern-status" role="status" aria-live="polite">세 패턴을 같은 축으로 비교합니다.</p><p class="learn-source-note">공통 학습 자료 30건에서 나온 잔차가 아닙니다. 화면 전환은 가상 점과 축 배율을 바꾸지 않습니다.</p></div>'''
 g2=g2.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="rd-patterns">').replace('<svg',controls+'<script type="application/json" id="rd-pattern-data">'+json.dumps(patterns,ensure_ascii=False)+'</script><svg',1).replace('<svg ','<svg class="rd-pattern-svg" ',1)
 b=text(24,28,'정규 Q–Q: 정규 이론 분위수와 정렬한 잔차')+line(65,325,580,325)+line(65,55,65,325)
 for v in [-100,0,100,200]:b+=text(24,260-v*.7,v)
 for q in qq:b+=dot(320+q['z']*100,255-q['residual']*.7)
 b+=f'<line x1="{320-10000/s}" y1="325" x2="540" y2="{255-2.2*s*.7}" stroke="#d97706" stroke-dasharray="5 4"/>'
 for z in [-2,-1,0,1,2]:b+=text(315+z*100,350,z)
 b+=text(24,378,'세로: 잔차(만원/㎡) · 주황 점선: e = s×z, s≈63.1163')
 g3=fig('qq','잔차의 정규 Q–Q 그림',b,'그림 3. 가로축은 Φ⁻¹((i−0.5)/30), i=1,…,30입니다. 세로축은 정렬한 원 잔차(만원/㎡)입니다. 참고선은 e=s×z, s=√(SSE/28)이며 검정 경계나 신뢰구간이 아닙니다. 위쪽 꼬리의 최대 잔차는 id=7에서 나옵니다.',405)
 b=text(24,28,'레버리지와 내부 표준화 잔차')+line(65,280,580,280)+line(65,55,65,335)
 for v in [-1,0,1,2,3,4]:b+=text(35,285-v*45,v)
 for row in ds:
  cx=65+row['leverage']*1800;cy=280-row['standardized']*45;b+=dot(cx,cy,row['id'])
  if row['id'] in [7,max(ds,key=lambda v:v['leverage'])['id']]:b+=text(cx+7,cy-8,str(row['id'])+'번')
 for h in [0,.1,.2]:b+=text(65+h*1800,355,h)
 b+=text(350,382,'가로: 레버리지 hᵢ (단위 없음)')
 g4=fig('influence','잔차와 레버리지',b,'그림 4. 세로축은 eᵢ/[s√(1−hᵢ)]입니다. X방향의 극단성과 Y방향의 어긋남은 다른 개념입니다. 영향력은 계수 변화나 Cook 거리로 추가 확인합니다.',410)
 g4=g4.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide rd-observations" id="rd-influence">').replace('<svg',observation_controls('influence')+'<svg',1).replace('<svg ','<svg class="rd-observation-svg" ',1)
 page=ROOT/'residuals/index.html';old=page.read_text(encoding='utf-8')
 references=re.search(r'<details class="learn-more"><summary>참고자료와 계산값</summary>.*?</details>',old,re.S)[0].replace('계산은 17장과 같이 공통 학습 자료의 두 수치열을 단위 없는 X,Y로 사용했습니다. 곡선·부채꼴 그림은 설명을 위한 개념도입니다.','계산은 17장과 같은 면적(㎡)·단가(만원/㎡) 자료를 사용했습니다. 그림 2의 세 패턴은 가상 개념도입니다.')
 parts=[];source=(ROOT/'residuals/content.md').read_text(encoding='utf-8').replace('\\*','*').replace('**','').replace('\\~','~')
 formulas={r'e_i=y_i-\hat y_i':'eᵢ = yᵢ − ŷᵢ',r'MAE=\frac{1}{n}\sum |e_i|':'MAE = Σ|eᵢ| / n',r'RMSE=\sqrt{\frac{SSE}{n}}':'RMSE = √(SSE/n)',r'RSE=\sqrt{\frac{SSE}{n-2}}':'RSE = √[SSE/(n−2)]',r'Var(\varepsilon\mid X)=\sigma^2':'Var(ε|X) = σ²',r'h_i=\frac{1}{n}+\frac{(x_i-\bar{x})^2}{S\_{xx}}':'hᵢ = 1/n + (xᵢ−x̄)²/Sxx',r'r_i=\frac{e_i}{s\sqrt{1-h_i}}':'rᵢ = eᵢ/[s√(1−hᵢ)]',r'D_i=\frac{r_i^2}{2}\frac{h_i}{1-h_i}':'Dᵢ = (rᵢ²/2) × hᵢ/(1−hᵢ)'}
 source=re.sub(r'^\[\s*\n(.*?)\n\]$',lambda m:formulas[m[1].strip()],source,flags=re.M|re.S)
 ids=['quick-start','reading','scale','patterns','homoscedasticity','independence','normality','influence','workflow','practice','macro','recap']
 def inline(value):return re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',escape(value))
 def render(block):
  out=[];lines=block.strip().split('\n');i=0
  while i<len(lines):
   line=lines[i].strip()
   if not line or line=='---':i+=1;continue
   if line.startswith('### '):out.append('<h3>'+inline(line[4:])+'</h3>');i+=1;continue
   if line.startswith('[그림 '):out.append({1:g1,2:g2,3:g3,4:g4}[int(re.search(r'그림 (\d)',line)[1])]);i+=1;continue
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
   if re.match(r'^\d+\. ',line):out.append('<h3>'+inline(line)+'</h3>');i+=1;continue
   if line.startswith('- ') or re.match(r'\d+\. ',line):
    ordered=not line.startswith('- ');tag='ol' if ordered else 'ul';items=[]
    while i<len(lines) and (re.match(r'\d+\. ',lines[i]) if ordered else lines[i].startswith('- ')):
     items.append('<li>'+inline(re.sub(r'^(?:- |\d+\. )','',lines[i]))+'</li>');i+=1
    out.append('<'+tag+'>'+''.join(items)+'</'+tag+'>');continue
   formula=line.startswith(('ŷ','eᵢ','MAE =','RMSE =','RSE =','Var(','hᵢ','rᵢ','Dᵢ','잔차 ='))
   out.append('<p'+(' class="rd-formula"' if formula else '')+'>'+inline(line)+'</p>');i+=1
  return '\n'.join(out)
 for id,section in zip(ids,re.split(r'^## ',source,flags=re.M)[1:],strict=True):
  label,body=section.split('\n',1);heading=re.search(r'^### (.+)$',body,re.M)[1];body=re.sub(r'^### .+\n','',body,count=1,flags=re.M)
  if id=='practice':
   items=[]
   for q in re.split(r'^\d+\. ',body,flags=re.M)[1:]:
    question,answer=q.split('▶ 답과 해설',1);items.append('<li>'+inline(question.strip())+'<details><summary>답과 해설</summary><div class="learn-more__body">'+render(answer)+'</div></details></li>')
   html='<ol class="learn-exercises">'+''.join(items)+'</ol>'
  else:html=render(body)
  if id=='quick-start':html=html.replace('<ul>','<ul class="learn-objectives">',1).replace('17장에서는','<a href="/learn/stats/regression/">17장</a>에서는')+'<p class="learn-source-note"><a href="/learn/stats/graphs/#data">공통 학습 자료 30건</a> · <a href="../residuals-example.json">잔차·지표·Q–Q 좌표 JSON</a>. 실제 거래의 출처와 대표성이 확인되지 않은 학습 자료입니다.</p>'
  if id=='scale':html+='<p class="learn-source-note">n=30, 추정 모수 p=2, 잔차 자유도 28입니다. SSE의 단위는 (만원/㎡)²이고 MAE·RMSE·RSE의 단위는 만원/㎡입니다.</p>'
  if id=='macro':html=macro_case()
  if id=='recap':html=html.replace('19장 「다중회귀와 변수의 해석」','<a href="/learn/stats/multiple-regression/">19장 「다중회귀와 변수의 해석」</a>')
  parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{heading if id!="macro" else "복합 다항회귀의 잔차 진단 화면을 읽어 보세요"}</h2>{html}</section>')
 p=ROOT/'residuals/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="잔차와 회귀모형의 가정">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1잔차 그림으로 선형성·등분산·독립성·정규성과 영향력을 점검하는 방법을 학습합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);
 html=re.sub(r'(<p class="learn-chapter-relevance">).*?(</p>)',r'\1Macro 활용도 <span class="learn-relevance" aria-label="Macro 활용도 3단계, 핵심"><span aria-hidden="true">★★★</span></span>\2',html,count=1)
 html=html.replace('별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.','활용도는 CH2 Macro의 분석 결과를 이해하는 데 얼마나 도움이 되는지를 나타냅니다.')
 if 'residuals/chapter.css' not in html:html=html.replace('</head>','<link rel="stylesheet" href="/learn/stats/residuals/chapter.css?v=20261024-1" />\n</head>')
 if 'residuals/experiment.js' not in html:html=html.replace('</body>','<script type="module" src="/learn/stats/residuals/experiment.js?v=20261024-1"></script>\n</body>')
 p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
