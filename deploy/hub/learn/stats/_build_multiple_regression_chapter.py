"""Chapter 19: multiple regression, exact reproducible examples."""
from pathlib import Path
from html import escape
import numpy as np
import json,re
from scipy.stats import t
ROOT=Path(__file__).resolve().parent

def model(X,y):
 X=np.asarray(X,float);y=np.asarray(y,float);b=np.linalg.lstsq(X,y,rcond=None)[0];e=y-X@b;n,p=X.shape;sse=float(e@e);s2=sse/(n-p);se=np.sqrt(np.diag(np.linalg.inv(X.T@X))*s2);r2=1-sse/float(((y-y.mean())**2).sum());crit=t.ppf(.975,n-p)
 return dict(beta=b.tolist(),residuals=e.tolist(),SSE=sse,df=n-p,R2=r2,adjusted_R2=1-(1-r2)*(n-1)/(n-p),se=se.tolist(),ci=[[float(v-crit*w),float(v+crit*w)] for v,w in zip(b,se)])


def macro_case():
 return '''<p>아래는 사용자가 제공한 복합부동산 회귀 화면입니다. 남평읍의 적합 표본 112건을 사용한 캡처로, 공통 학습 자료 30건과 다른 사례입니다. 조회 거래 134건에서 숫자 결측 22건을 제외한 최종 표본 112건이 표시됩니다. ‘지분 4건 제외’도 별도 조건으로 보이지만, 전체 필터 처리 순서를 이미지 하나로 재구성할 수는 없습니다.</p>
<figure class="mr-macro-case"><a href="macro-built-regression.png" target="_blank" rel="noopener"><img src="macro-built-regression.png" width="1174" height="900" loading="lazy" alt="남평읍 복합 회귀 화면. n=112, 설계 열 25개·독립 계수 22개로 계수가 고유하지 않다는 경고. R² 0.62322, 수정 R² 0.53531, 학습 MAPE 56.73%, CV-MAPE 111.29%. 기준 범주와 계수별 SE·t·p가 표시됩니다."></a><figcaption>실제 복합 회귀 화면 캡처 · 숫자는 캡처 당시 값입니다. 이미지를 선택하면 원본 크기로 볼 수 있습니다. 기간·전체 변수 설정과 원자료가 없어 이 숫자를 현재 값이나 독립 검산 결과로 제시하지 않습니다.</figcaption></figure>
<p>이 화면의 종속변수는 ‘금액’입니다. 교재의 ‘단가’를 설명하는 식과 구별해야 합니다. 연면적·대지면적·연식·범주 더미와 log(개별공시지가) 등이 식에 포함되어 있습니다. 연면적계수 +53만원이라는 표시는 포함한 다른 변수와 함수 형태를 조건으로 한 표현이며, 누락된 모든 부동산 조건을 같게 만든 인과효과가 아닙니다.</p>
<p>이 캡처에서는 계수보다 먼저 노란 ‘모형 식별’ 경고를 읽어야 합니다. 설계 열은 25개지만 독립 계수는 22개이므로, 같은 적합값을 만드는 계수 조합이 여러 개 존재합니다. 유한한 계수·표준오차·t값·p값이 출력되더라도 개별 계수가 고유하게 식별되었다는 뜻은 아닙니다. 숫자만으로 변수별 가격 기여를 나누어 해석해서는 안 됩니다.</p>
<p>‘미상’ 범주는 기준 범주와 다릅니다. 캡처에는 용도지역 제1종일반주거, 구조 벽돌, 도로조건 8m미만, 유형 상업이 기준으로 표시됩니다. ‘미상’의 계수가 0만원, SE가 0.00으로 보이는 것은 표시 반올림과 식별 경고를 함께 확인해야 하는 상황입니다. 이 값만으로 관계가 정확히 0이라고 결론 내리지 않습니다.</p>
<p>R²=0.62322와 수정 R²=0.53531은 표본 내 적합도입니다. 학습 MAPE=56.73%와 CV-MAPE=111.29%도 서로 다른 평가입니다. 오차율이므로 111.29%는 정답률이 아니며, 별도 시점 평가가 학습 적합보다 나쁠 수 있음을 보여 줍니다. ‘마지막 연도 확인 50.50%’도 전체 CV와 같은 숫자가 아닙니다.</p>
<details class="learn-more"><summary>실제 복합·지역 회귀의 변수와 계산·표시 방식</summary><div class="learn-more__body">
<p>확인한 복합 모형은 연면적·대지면적·연식·공시지가와 선택한 지역 지표 등을 수치형 변수로, 용도지역·건축물용도·구조·도로조건·지역 등을 기준 범주가 있는 더미로 구성합니다. ‘미상 유지’와 ‘결측 행 제외’ 정책이 있으며 켜진 숫자 변수의 결측, 로그변환의 양수 조건에 따라 표본이 달라집니다. 모형·앱별 제공 변수는 같다고 전제하지 않습니다.</p>
<p>확인한 복합 설계행렬은 선택한 수치형 변수와 범주 더미를 더하는 구조입니다. 로그 변환 옵션과 별개로 이 장의 X×D 상호작용항을 자동으로 추가하지는 않습니다. 화면에 없는 상호작용이나 95% 계수 신뢰구간을 이미 제공하는 것처럼 읽지 마세요.</p>
<p>절편을 포함한 statsmodels OLS에서 계수와 일반 표준오차·t·p를 구합니다. 현재 계수 상세 표에는 SE·t·p가 표시되며 95% 계수 구간 열은 없습니다. SE와 t는 소수 둘째 자리, p는 다섯째 자리로 표시하므로 0.00000은 확률이 정확히 0이라는 뜻이 아닙니다. 식의 기본 축약 표시는 p&lt;0.1인 항을 중심으로 하고, ‘유의 변수’ 개수는 백엔드의 p&lt;0.05 기준이므로 두 표시의 기준이 다릅니다.</p>
<p>이 경로는 열 수와 행렬 rank를 따로 확인합니다. rank가 줄어도 잔차 자유도가 남으면 계산 결과와 식별 경고를 함께 제공할 수 있습니다. 자유도가 없으면 계산 불가로, 유효 표본 30건 미만 또는 독립 계수당 관측 5건 미만이면 참고용으로 안내합니다. 이는 서비스 제공 기준이지 통계적 타당성의 보증은 아닙니다.</p>
<p>서비스 VIF 경고는 선택한 연속변수 열로 계산하며 기준 범주 더미와 상수항을 제외합니다. 특히 현재 보조회귀 입력에 상수항을 추가하지 않으므로 교재의 절편 포함 보조회귀 Rⱼ²로 계산한 통상적 VIF와 수치가 다를 수 있습니다. 캡처의 VIF 경고를 교재 공식의 독립 검산값으로 취급하지 않습니다. VIF나 드문 미상 범주의 경고는 자동 삭제 명령이 아닙니다.</p>
<p>모형 탐색에는 후보 변수 블록을 구성하고 비교하는 절차와 AIC 기준 순차 추가 경로 등이 있습니다. 학습 R²만으로 변수를 고르거나 모든 변수를 p값 순으로 자동 삭제하는 단일 정책은 아닙니다. CV-MAPE는 연도 순서를 고려한 롤링 평가와 마지막 연도 확인으로 구분됩니다. 추천·선택 후의 p값과 구간에도 선택 과정의 불확실성이 남습니다.</p>
<p>공시지가·면적·건물 특성은 서로 관련될 수 있습니다. 변수의 실무적 의미·유효 표본수·기준 범주·식별 경고와 검증 성능을 함께 보고, 한 변수를 무조건 제거하거나 개별 물건의 적정가격 효과로 해석하지 마세요.</p></div></details>
<p class="learn-macro-cta"><a href="https://macro.ch2data.com/built/">CH2 Macro 복합 통계·데이터분석 열기 →</a></p>'''

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];x=np.array([r['area'] for r in rows]);y=np.array([r['price'] for r in rows]);floor=np.array([r['floor'] for r in rows]);n=len(x)
 simple=model(np.column_stack([np.ones(n),x]),y);multi=model(np.column_stack([np.ones(n),x,floor]),y)
 sx=np.arange(1,7,dtype=float);g=np.array([0,0,0,1,1,1]);sy=7+sx-9*g+np.array([.2,-.4,.2,.2,-.4,.2]);demo=model(np.column_stack([np.ones(6),sx,g]),sy);unadjusted=model(np.column_stack([np.ones(6),sx]),sy)
 rx=sx-np.where(g==0,2,5);ry=sy-np.where(g==0,9,3)
 result=dict(description='공통 학습 자료 30건의 면적(㎡)·층(층)·단가(만원/㎡) 다중회귀와 별도 가상 6점. 인과효과가 아님.',simple=simple,multiple=multi,demo=dict(x=sx.tolist(),group=g.tolist(),y=sy.tolist(),model=demo,simple=unadjusted,residual_x=rx.tolist(),residual_y=ry.tolist()))
 (ROOT/'multiple-regression-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def ln(x,y,a,b,c='#94a3b8',extra=''):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="{c}" {extra}/>'
 def dot(x,y,c='#2563eb'):return f'<circle cx="{x}" cy="{y}" r="5" fill="{c}"/>'
 def fig(id,title,b,cap):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 400" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=tx(24,28,'가상 자료: 파랑 A집단 / 주황 B집단','id="mr-group-heading"')+ln(70,320,580,320)+ln(70,55,70,320)
 for xx,yy,gg in zip(sx,sy,g):b+=dot(70+xx*75,320-yy*23,'#2563eb' if gg==0 else '#d97706').replace('/>',f' data-group="{int(gg)}"><title>{"AB"[gg]}: ({xx:g}, {yy:g})</title></circle>')
 for gg,lo,hi,c in [(0,1,3,'#2563eb'),(1,4,6,'#d97706')]:b+=ln(70+lo*75,320-(7+lo-9*gg)*23,70+hi*75,320-(7+hi-9*gg)*23,c,f'stroke-width="2" data-trend="{"AB"[gg]}"')
 a,k=unadjusted['beta'];b+=ln(145,320-(a+k)*23,520,320-(a+6*k)*23,'#64748b','stroke-dasharray="5 4" stroke-width="2" data-trend="overall"')
 for v in [1,2,3,4,5,6]:b+=tx(65+v*75,345,v)
 for v in [0,4,8,10]:b+=tx(35,325-v*23,v)
 b+=tx(24,380,'X·Y: 가상 변수 · 파랑 A / 주황 B / 회색 점선: 전체','id="mr-group-legend"')
 f1=fig('groups','집단 조정 전후의 관계',b,'그림 1. 별도 가상 6점입니다. 집단 내 기울기는 양수지만 전체 기울기는 음수입니다. 집단 간 X범위가 겹치지 않아 같은 X에서의 집단 차이는 모형 가정에 의존합니다.')
 controls='<div class="mr-controls" hidden><label for="mr-group-mode">집단 통제 전후 보기</label><select id="mr-group-mode"><option value="both">통제 전후 비교</option><option value="overall">집단을 구분하지 않은 회귀</option><option value="adjusted">집단을 구분한 회귀</option></select><p id="mr-group-status" role="status" aria-live="polite"></p><p class="learn-source-note">A의 X범위는 1~3, B는 4~6으로 겹치지 않습니다. 집단별 선은 관측 범위에만 표시합니다. 동일한 X에서의 집단 차이는 공통 기울기·가산성 가정에 의존하며 인과효과가 아닙니다.</p></div>'
 f1=f1.replace('<figure class="learn-chart learn-chart--wide">','<figure class="learn-chart learn-chart--wide" id="mr-groups">').replace('<svg',controls+'<script type="application/json" id="mr-demo">'+json.dumps(result['demo'],ensure_ascii=False)+'</script><svg',1).replace('<svg ','<svg class="mr-group-svg" ',1)
 b=tx(24,28,'집단 평균을 각각 뺀 X와 Y')+ln(100,210,540,210)+ln(320,65,320,330)+ln(160,338,480,82,'#2563eb')
 for xx,yy in zip(rx,ry):b+=dot(320+xx*130,210-yy*104)
 for xx,yy in sorted(set(zip(np.round(rx,10),np.round(ry,10)))):
  b+=f'<ellipse cx="{320+xx*130}" cy="{210-yy*104}" rx="8" ry="8" fill="none" stroke="#2563eb"/>'+tx(332+xx*130,214-yy*104,'×2')
 for v in [-1,0,1]:b+=tx(315+v*130,355,v)
 for v in [-1,0,1]:b+=tx(65,215-v*104,v)
 b+=tx(24,383,'가로: X의 집단 내 편차 / 세로: Y의 집단 내 편차')
 f2=fig('partial','집단을 조정한 기울기',b,'그림 2. 그림 1의 각 집단 평균을 제거했습니다. 같은 좌표마다 A·B 각 1개씩 두 관측값이 겹치며, 고리와 ×2로 표시합니다. 이 편차들의 원점 통과 회귀 기울기는 다중회귀 X계수 1과 같습니다.')
 b=tx(24,28,'같은 30건의 면적계수와 고전적 95% 신뢰구간')
 vals=[v for m in [simple,multi] for v in m['ci'][1]];lo=min(vals)-.1;hi=max(vals)+.1;px=lambda v:170+(v-lo)/(hi-lo)*380
 for yy,m,label in [(140,simple,'면적만'),(240,multi,'면적+층')]:
  l,u=m['ci'][1];b+=tx(24,yy+5,label)+ln(px(l),yy,px(u),yy,'#2563eb','stroke-width="3"')+dot(px(m['beta'][1]),yy)+tx(170,yy+32,f"{m['beta'][1]:.3f} [{l:.3f}, {u:.3f}]")
 b+=ln(170,320,550,320)
 for v in np.linspace(lo,hi,4):b+=tx(px(v)-15,345,f'{v:.2f}')
 b+=tx(24,382,'면적계수 단위: (만원/㎡)/㎡ · 층 포함 여부만 다릅니다')
 f3=fig('coefficients','층 추가 전후의 면적계수와 95% 신뢰구간',b,'그림 3. 같은 학습 자료 30건에서 층을 추가했을 때의 면적계수입니다. 구간은 등분산·독립·정규 오차 등 고전적 가정에 근거하며, 이 자료에서 가정이 충족되었다는 뜻은 아닙니다.')
 b=tx(24,28,'완전 공선성: X₂=2X₁')+ln(70,320,570,320)+ln(70,55,70,320)
 for v in range(1,6):b+=dot(70+v*85,320-v*44)
 b+=ln(155,276,495,100,'#2563eb')
 for v in range(6):b+=tx(65+v*85,345,v)
 for v in [0,4,8,10]:b+=tx(35,325-v*22,v)
 b+=tx(24,365,'예: (b₁,b₂)=(2,0) 또는 (0,1) → 같은 2X₁')
 b+=tx(24,392,'가로 X₁ / 세로 X₂ · b₁+2b₂만 구별할 수 있습니다')
 f4=fig('collinear','완전 공선성',b,'그림 4. 별도 가상 설명변수입니다. 두 열이 정확히 비례하면 개별 계수의 유일한 OLS 해가 없습니다. 단위만 바꿔 추가한 변수는 새로운 정보를 더하지 않습니다.')
 page=ROOT/'multiple-regression/index.html';old=page.read_text(encoding='utf-8')
 references=re.search(r'<details class="learn-more"><summary>참고자료</summary>.*?</details>',old,re.S)[0].replace('30개 관측의 계산은 공통 학습 자료의 세 수치열을 단위 없는 X₁,X₂,Y로 사용했습니다.','30건의 계산은 공통 학습 자료의 면적(㎡)·층(층)·단가(만원/㎡)를 사용했습니다.')
 parts=[];source=(ROOT/'multiple-regression/content.md').read_text(encoding='utf-8').replace('\\*','*').replace('**','').replace('\\~','~')
 formulas={r'Y=\beta_0+\beta_1X_1+\beta_2X_2+\cdots+\beta_kX_k+\varepsilon':'Y = β₀ + β₁X₁ + β₂X₂ + … + βₖXₖ + ε',r'\hat y=b_0+b_1x_1+b_2x_2+\cdots+b_kx_k':'ŷ = b₀ + b₁x₁ + b₂x₂ + … + bₖxₖ',r'SSE=\sum(y_i-\hat y_i)^2':'SSE = Σ(yᵢ−ŷᵢ)²',r'\mathbf b=(X^TX)^{-1}X^T\mathbf y':'b = (XᵀX)⁻¹Xᵀy',r'\hat y=b_0+b_1X+b_2D+b_3(XD)':'ŷ = b₀ + b₁X + b₂D + b₃XD',r'\hat y=b_0+b_1X':'ŷ = b₀ + b₁X',r'\hat y=(b_0+b_2)+(b_1+b_3)X':'ŷ = (b₀+b₂) + (b₁+b₃)X',r'b_1X_1+b_2X_2=(b_1+2b_2)X_1':'b₁X₁ + b₂X₂ = (b₁+2b₂)X₁',r'VIF_j=\frac{1}{1-R_j^2}':'VIFⱼ = 1/(1−Rⱼ²)',r'R^2\_{\mathrm{adj}}=' + '\n' + r'1-\frac{SSE/(n-p)}{SST/(n-1)}':'R²_adj = 1 − [SSE/(n−p)] / [SST/(n−1)]',r't=\frac{b_j-0}{SE(b_j)}':'t = (bⱼ−0) / SE(bⱼ)',r'F=' + '\n' + r'\frac{(SSE_R-SSE_U)/q}{SSE_U/(n-p_U)}':'F = [(SSE_R−SSE_U)/q] / [SSE_U/(n−p_U)]'}
 source=re.sub(r'^\[\s*\n(.*?)\n\]$',lambda m:formulas[m[1].strip()],source,flags=re.M|re.S)
 ids=['quick-start','core','groups','partial','example','coding','interaction','collinearity','fit','tests','causality','practice','macro','recap']
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
   if re.match(r'^\d+\. ',line):out.append('<h3>'+inline(line)+'</h3>');i+=1;continue
   if line.startswith('- ') or re.match(r'\d+\. ',line):
    ordered=not line.startswith('- ');tag='ol' if ordered else 'ul';items=[]
    while i<len(lines) and (re.match(r'\d+\. ',lines[i]) if ordered else lines[i].startswith('- ')):
     items.append('<li>'+inline(re.sub(r'^(?:- |\d+\. )','',lines[i]))+'</li>');i+=1
    out.append('<'+tag+'>'+''.join(items)+'</'+tag+'>');continue
   formula=line.startswith(('Y =','ŷ','SSE =','b =','b₁','b₂','R²','t =','F =','VIF','X₂ =','H₀:','상업지역 −'))
   out.append('<p'+(' class="mr-formula"' if formula else '')+'>'+inline(line)+'</p>');i+=1
  return '\n'.join(out)
 for id,section in zip(ids,re.split(r'^## ',source,flags=re.M)[1:],strict=True):
  label,body=section.split('\n',1);heading=re.search(r'^### (.+)$',body,re.M)[1];body=re.sub(r'^### .+\n','',body,count=1,flags=re.M)
  if id=='practice':
   items=[]
   for q in re.split(r'^\d+\. ',body,flags=re.M)[1:]:
    question,answer=q.split('▶ 답과 해설',1);items.append('<li>'+inline(question.strip())+'<details><summary>답과 해설</summary><div class="learn-more__body">'+render(answer)+'</div></details></li>')
   html='<ol class="learn-exercises">'+''.join(items)+'</ol>'
  else:html=render(body)
  if id=='quick-start':html=html.replace('<ul>','<ul class="learn-objectives">',1)+'<p class="learn-source-note"><a href="/learn/stats/graphs/#data">공통 학습 자료 30건</a> · <a href="../multiple-regression-example.json">계수·구간·가상 예제 JSON</a>. 실제 거래 출처와 대표성이 검증되지 않은 학습 자료입니다.</p>'
  if id=='example':
   table='<details class="learn-more"><summary>두 모형의 전체 계수·고전적 표준오차·95% 구간</summary><div class="learn-more__body"><div class="learn-data learn-data--full"><table><thead><tr><th>모형·계수</th><th>추정값</th><th>표준오차</th><th>95% 구간</th></tr></thead><tbody>'
   for name,m in [('면적만',simple),('면적+층',multi)]:
    for j,label19 in enumerate(['절편','면적','층'][:len(m['beta'])]):table+=f'<tr><th scope="row">{name} · {label19}</th><td>{m["beta"][j]:.4f}</td><td>{m["se"][j]:.4f}</td><td>{m["ci"][j][0]:.4f}~{m["ci"][j][1]:.4f}</td></tr>'
   html+=table+'</tbody></table></div><p>면적만 모형 자유도 28, 면적+층 자유도 27의 양측 t 임계값을 각각 사용했습니다. 계수와 표준오차의 단위는 절편: 만원/㎡, 면적: (만원/㎡)/㎡, 층: (만원/㎡)/층입니다. 이분산·의존성이 있으면 이 고전적 구간이 자동으로 타당해지지는 않습니다.</p></div></details>'
  if id=='fit':
   html=html.replace('<td>—</td>',f'<td>{simple["adjusted_R2"]:.3f}</td>',1)+'<p class="learn-source-note">면적만 모형의 수정 R²는 0.4006745736…입니다. 표에서는 소수 셋째 자리까지 반올림해 표시합니다.</p>'
  if id=='macro':html=macro_case()
  if id=='recap':html=html.replace('20장 「로그변환과 비선형 관계」','<a href="/learn/stats/log-regression/">20장 「로그변환과 비선형 관계」</a>')
  parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{heading if id!="macro" else "실제 회귀 화면의 계수·기준·식별 경고를 함께 읽으세요"}</h2>{html}</section>')
 p=ROOT/'multiple-regression/index.html';p.parent.mkdir(exist_ok=True);html=p.read_text(encoding='utf-8') if p.exists() else (ROOT/'regression/index.html').read_text(encoding='utf-8').replace('https://ch2data.com/learn/stats/regression/','https://ch2data.com/learn/stats/multiple-regression/')
 html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="다중회귀와 변수의 해석">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1다중회귀의 조건부 계수, 더미변수·상호작용·공선성과 통제변수의 한계를 학습합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);
 html=html.replace('별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.','활용도는 CH2 Macro의 분석 결과를 이해하는 데 얼마나 도움이 되는지를 나타냅니다.')
 if 'multiple-regression/chapter.css' not in html:html=html.replace('</head>','<link rel="stylesheet" href="/learn/stats/multiple-regression/chapter.css?v=20261024-1" />\n</head>')
 if 'multiple-regression/experiment.js' not in html:html=html.replace('</body>','<script type="module" src="/learn/stats/multiple-regression/experiment.js?v=20261024-1"></script>\n</body>')
 p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
