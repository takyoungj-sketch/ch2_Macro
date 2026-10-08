"""Generate chapter 17 using exact ordinary least squares from shared data."""
from pathlib import Path
from statistics import mean
from html import escape
import math,json,re
ROOT=Path(__file__).resolve().parent

def fit(x,y):
 xm,ym=mean(x),mean(y);sxx=sum((v-xm)**2 for v in x);sxy=sum((a-xm)*(b-ym) for a,b in zip(x,y));b=sxy/sxx;a=ym-b*xm;res=[v-(a+b*u) for u,v in zip(x,y)];sse=sum(e*e for e in res);sst=sum((v-ym)**2 for v in y)
 return {'intercept':a,'slope':b,'xmean':xm,'ymean':ym,'Sxx':sxx,'Sxy':sxy,'residuals':res,'SSE':sse,'R2':1-sse/sst}

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];x=[r['area'] for r in rows];y=[r['price'] for r in rows];d=fit(x,y);a,b=d['intercept'],d['slope'];pred=lambda v:a+b*v
 smallx=[1,2,3];smally=[2,2,5];small=fit(smallx,smally);other=[r for r in rows if r['id']!=7];reduced=fit([r['area'] for r in other],[r['price'] for r in other]);result={'description':'공통 학습자료 OLS와 별도 가상 세 점. 실제 시장 가격모형이 아님.','fit':d,'without_id7':reduced,'small':{'x':smallx,'y':smally,'fit':small},'predictions':{str(v):pred(v) for v in [100,200,400]}}
 (ROOT/'regression-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def t(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def line(x,y,xx,yy,c='#64748b',extra=''):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{c}" {extra}/>'
 def fig(id,title,body,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{body}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 body=t(24,28,f'ŷ={a:.3f} {b:+.4f}×면적')+line(70,320,580,320)+line(70,55,70,320)
 for row in rows:body+=f'<circle cx="{70+row["area"]*1.5}" cy="{320-row["price"]*.5}" r="4" fill="#2563eb" data-id="{row["id"]}"/>'
 body+=line(70+min(x)*1.5,320-pred(min(x))*.5,70+max(x)*1.5,320-pred(max(x))*.5,'#d97706','stroke-width="3" data-fit="true"')
 for v in [0,100,200,300]:body+=t(70+v*1.5,345,v,'text-anchor="middle"')
 for v in [0,100,200,300,400,500]:body+=t(58,325-v*.5,v,'text-anchor="end"')
 body+=t(24,52,'단가(만원/㎡)')+t(430,380,'면적(㎡)')
 f1=fig('fit','공통 자료의 최소제곱 직선',body,'그림 1. 공통 학습 자료 30건의 면적을 X, 단가를 Y로 둔 절편 포함 OLS입니다. 선은 관측된 면적 22~310㎡ 범위에만 표시했습니다.',407)
 body=t(24,28,'세로 잔차를 제곱해 더합니다: 가상 세 점')+line(70,290,550,290)+line(70,45,70,290)
 px=lambda v:70+v*140;py=lambda v:290-v*43
 body+=line(px(.5),py(-.0+1.5*.5),px(3.2),py(1.5*3.2),'#d97706','stroke-width="2"')
 for xx,yy,e in zip(smallx,smally,small['residuals']):
  hat=small['intercept']+small['slope']*xx;body+=line(px(xx),py(yy),px(xx),py(hat),'#2563eb',f'stroke-width="3" data-residual="{e}"')+f'<circle cx="{px(xx)}" cy="{py(yy)}" r="5" fill="#2563eb"/>'+t(px(xx)+12,py(yy),f'e={e:+.1f}')
 for v in [1,2,3]:body+=t(px(v),316,v,'text-anchor="middle"')
 body+=t(24,350,'ŷ=1.5x · 잔차 0.5, −1, 0.5 · SSE=1.5')
 f2=fig('residuals','관측값과 적합값의 차이',body,'그림 2. 별도 가상 (1,2)·(2,2)·(3,5) 예제입니다. 잔차는 같은 X에서의 세로 차이이며 점에서 직선까지의 최단거리가 아닙니다. 축은 단위 없는 가상 변수입니다.',378)
 body=t(24,28,'각 기울기에서 절편을 최적으로 맞춘 제곱합')
 pts=[]
 for i in range(101):
  slope=-1.2+i*.01;inter=mean(y)-slope*mean(x);sse=sum((v-inter-slope*u)**2 for u,v in zip(x,y));cx=80+(slope+1.2)*450;cy=285-(sse-d['SSE'])/500;pts.append((cx,cy))
 body+=line(70,285,560,285)+ '<polyline points="'+' '.join(f'{xx:.5f},{yy:.5f}' for xx,yy in pts)+'" fill="none" stroke="#2563eb" stroke-width="2"/>'
 body+=f'<circle cx="{80+(b+1.2)*450}" cy="285" r="5" fill="#d97706"/>'
 for val in [-1.2,-1,-.8,-.6,-.4,-.2]:body+=t(80+(val+1.2)*450,312,f'{val:.1f}','text-anchor="middle"')
 body+=t(24,345,f'최소 기울기 {b:.4f} · 최소 SSE {d["SSE"]:,.2f}')+t(24,374,'세로축: 최소 SSE보다 늘어난 양(제곱 단위), 아래가 0')
 f3=fig('objective','기울기에 따른 잔차제곱합',body,'그림 3. 기울기마다 절편을 ȳ−b×x̄로 맞췄습니다. 공통 자료의 최소제곱 목적함수이며 확률곡선이나 신뢰구간이 아닙니다.',401)
 body=t(24,28,'관측 범위 밖의 직선 연장은 별도 가정입니다');xx=lambda v:70+v*1.2;yy=lambda v:280-v*.7
 body+=line(70,280,580,280)+line(xx(22),yy(pred(22)),xx(310),yy(pred(310)),'#2563eb','stroke-width="3"')+line(xx(310),yy(pred(310)),xx(400),yy(pred(400)),'#d97706','stroke-width="3" stroke-dasharray="5 4"')
 for val in [100,200,400]:body+=f'<circle cx="{xx(val)}" cy="{yy(pred(val))}" r="5" fill="#2563eb"/>'+t(xx(val)-5,yy(pred(val))-14,f'{pred(val):.2f}','text-anchor="middle"')
 for val in [0,100,200,300,400]:body+=t(xx(val),350,val,'text-anchor="middle"')
 body+=t(24,385,'파랑: 관측 범위의 적합선 / 주황 점선: 외삽 · 가로축: 면적(㎡)')
 f4=fig('extrapolation','내삽과 외삽',body,'그림 4. 세로 위치는 예측 단가(만원/㎡)이며 가로선은 단가 0입니다. 400㎡에서 음수로 내려가는 결과는 직선 연장의 한계를 보여 줍니다.',414)
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','핵심 이해','평균적 관계를 기울기와 절편으로 표현합니다','''<p>단순선형회귀는 설명변수 X 하나와 결과변수 Y 사이의 관계를 직선으로 요약합니다. 모집단 모형은 Y=β₀+β₁X+ε, 자료로 적합한 식은 <strong>ŷ=b₀+b₁x</strong>로 구분합니다. β는 미지의 모수, b는 추정 계수, ε는 모형의 오차입니다.</p><p>면적을 X, 단가를 Y로 정해 보겠습니다. 같은 면적에서도 거래 조건에 따라 단가가 다르므로 모든 점이 직선에 놓일 필요는 없습니다. E[ε|X]=0이라는 조건이 맞으면 직선은 조건부 평균 E[Y|X]을 나타냅니다. 이 조건을 확인하지 않은 적합선은 관측 관계의 기술적 요약으로 읽어야 합니다.</p>'''+f1)
 sec('coefficients','기울기와 절편','계수에는 단위와 적용 범위가 있습니다',f'''<p>공통 30건을 적합하면 b₀={a:.5f}…, b₁={b:.5f}…입니다. 면적이 1㎡ 큰 거래의 적합 단가는 평균적으로 약 {abs(b):.3f}만원/㎡ 낮게 나타납니다. 이는 다른 조건을 통제한 면적의 인과효과가 아닙니다.</p><p>기울기의 단위는 ‘Y 단위/X 단위’이므로 여기서는 (만원/㎡)/㎡입니다. 10㎡ 차이에 대한 적합값의 차이는 10b₁≈{10*b:.2f}만원/㎡입니다. 상관계수와 달리 단위 변환에 따라 계수의 숫자가 바뀝니다.</p><p>절편은 X=0일 때의 적합값입니다. 관측 면적은 22~310㎡이므로 면적 0의 절편을 실제 0㎡ 물건의 단가로 해석하지 않습니다. X를 평균에서 뺀 X−x̄로 중심화하면 절편이 ȳ가 되어 해석하기 쉬워지고, 같은 직선의 적합값과 기울기는 유지됩니다.</p>''')
 sec('residuals','잔차','오차와 잔차, 적합값과 관측값을 구분합니다','''<p>잔차 eᵢ=yᵢ−ŷᵢ는 관측값에서 적합값을 뺀 값입니다. 양수면 점이 직선 위, 음수면 아래에 있습니다. 진짜 조건부 평균에서의 오차 εᵢ는 모르는 값이고, 표본으로 맞춘 직선에서의 잔차는 계산 가능한 값입니다.</p>'''+f2+'''<p>가상 세 점의 직선 ŷ=1.5x에서 잔차 합은 0이지만 모든 점이 직선에 맞는 것은 아닙니다. 양수·음수의 상쇄를 피하려고 제곱합니다. 잔차제곱합 SSE=0.5²+(−1)²+0.5²=1.5입니다.</p><p>OLS는 Y방향의 세로 잔차를 최소화합니다. X와 Y를 뒤집어 적합하면 다른 문제를 풀기 때문에 원래 기울기의 역수가 되는 것은 일반적이지 않습니다.</p>''')
 sec('ols','최소제곱법','잔차제곱합이 가장 작은 계수를 찾습니다','''<p>최소제곱법(OLS)은 <strong>SSE=Σ[yᵢ−(b₀+b₁xᵢ)]²</strong>를 최소화합니다. X에 퍼짐이 있을 때 Sxx=Σ(xᵢ−x̄)², Sxy=Σ(xᵢ−x̄)(yᵢ−ȳ)로 놓으면 <strong>b₁=Sxy/Sxx, b₀=ȳ−b₁x̄</strong>입니다.</p>'''+f3+f'''<p>공통 자료의 x̄={d['xmean']:.5f}…, ȳ={d['ymean']:.5f}…, Sxx={d['Sxx']:,.5f}…, Sxy={d['Sxy']:,.5f}…입니다. 이를 대입한 SSE는 {d['SSE']:,.2f}입니다. 중간값은 반올림하지 않았습니다. <a href="../regression-example.json">계수·잔차·예제 JSON</a>을 확인할 수 있습니다.</p><p>절편을 포함한 같은 자료의 OLS 직선은 (x̄,ȳ)를 지나고 잔차 합은 0입니다. 모든 X가 같으면 Sxx=0이어서 기울기를 고유하게 정할 수 없습니다. 두 개의 서로 다른 X만 있으면 직선을 계산할 수 있어도 오차 변동을 추정할 잔차 자유도가 없어집니다.</p>''')
 sec('prediction','적합값과 예측','계산한 한 점은 개별 거래의 보장값이 아닙니다',f'''<p>면적 100㎡의 적합 단가는 {pred(100):.2f}, 200㎡는 {pred(200):.2f}만원/㎡입니다. 반올림한 식으로 다시 계산하면 마지막 자릿수가 달라질 수 있으므로 내부 계산에는 원래 계수를 사용합니다.</p><p>같은 X의 평균적 수준을 추정하는 것과 새 거래 한 건을 예측하는 것은 다릅니다. 평균 반응의 신뢰구간은 회귀선의 추정 불확실성을, 개별 예측구간은 그 위에 개별 오차 변동까지 반영합니다. 적합값 한 개만으로 정확성을 판단하지 않습니다.</p><p>학습 자료에 맞춘 오차가 작다는 것이 새로운 지역·시점에서도 잘 맞는다는 뜻은 아닙니다. 실제 예측 성능은 별도 검증 자료와 적절한 시간·집단 분할로 확인해야 합니다.</p>''')
 sec('extrapolation','내삽과 외삽','자료가 없는 영역에서는 모형 가정이 더 중요해집니다','''<p>관측 X 범위 안에서 계산하는 것을 내삽, 밖으로 연장하는 것을 외삽이라고 합니다. 범위 안에서도 관측이 드문 구간이나 다른 거래 유형에는 주의가 필요합니다.</p>'''+f4+f'''<p>400㎡에서 식은 {pred(400):.2f}만원/㎡를 냅니다. 단가가 음수가 되는 이 값은 시장의 타당한 가격 전망이 아니라 직선을 범위 밖까지 연장한 산술 결과입니다. 외삽 결과를 단순히 0으로 잘라내기보다 모형의 범위와 함수 형태를 재검토해야 합니다.</p>''')
 sec('correlation','상관과 설명력','기울기·상관·R²는 서로 다른 정보를 담습니다',f'''<p>절편을 포함한 단순 OLS에서 두 변수의 분산이 양수이면 b₁=r×s_y/s_x입니다. r은 단위 없는 선형 결합의 정도, 기울기는 단위가 있는 변화량입니다. 이 특별한 모형에서는 <strong>R²=r²=1−SSE/SST</strong>이며 SST=Σ(yᵢ−ȳ)²입니다.</p><p>공통 자료의 R²는 {d['R2']:.3f}입니다. 같은 표본의 Y 제곱변동 중 평균만 사용하는 것보다 직선이 줄인 비율을 뜻합니다. 인과적으로 설명된 비율이나 미래 예측의 정확도, ‘정답률’이 아닙니다. 절편 없는 회귀나 다른 평가 상황에는 r² 관계를 그대로 적용하지 않습니다.</p><p>R²가 같아도 잔차의 곡선 패턴·이상치·예측 위험은 다를 수 있습니다. 더 자세한 적합도는 21장에서 다룹니다.</p>''')
 sec('assumptions','계산과 추론의 조건','직선을 계산할 수 있다는 것과 타당한 모형은 다릅니다','''<p>OLS 계수 계산 자체에 정규성 가정이 필요한 것은 아닙니다. 하지만 계수의 불편성이나 표준오차·검정·신뢰구간의 타당성을 주장하려면 조건을 구별해야 합니다. 조건부 평균의 선형성, E[ε|X]=0, 적절한 표집과 독립성, 일정한 오차분산 등이 기본 점검 대상입니다. 고전적 작은 표본 t·F 추론에는 정규 오차 가정도 사용합니다.</p><p>이분산이 있으면 계수 계산과 별개로 일반적인 표준오차가 부적절할 수 있습니다. 군집·시간 의존성도 그 구조에 맞춰 다뤄야 합니다. 강건한 표준오차를 쓴다고 누락변수나 잘못된 평균 함수가 해결되지는 않습니다.</p><p>면적과 단가에는 분모의 공유 구조가 있고, 유형·위치·연식이 섞여 있습니다. 계수의 인과 해석에는 별도 설계와 가정이 필요합니다. 단순회귀가 다른 조건을 자동으로 고정해 주지 않습니다.</p>''')
 sec('sensitivity','큰 관측과 모형 점검','한 점이 직선에 미치는 영향을 확인합니다',f'''<p>공통 자료의 7번을 제외해 다시 적합하면 절편은 {reduced['intercept']:.3f}, 기울기는 {reduced['slope']:.4f}입니다. 원래 기울기 {b:.4f}와 비교하면 민감도를 볼 수 있습니다. 더 보기 좋은 직선을 얻기 위한 삭제가 아니라 원자료·조건·영향력을 확인하는 과정입니다.</p><p>X방향에서 멀리 있는 점은 높은 레버리지를 가질 수 있고, 큰 잔차와 레버리지가 결합하면 계수에 강한 영향을 줄 수 있습니다. 잔차가 크다는 사실만으로 영향력을 모두 판단하지 않습니다. 다음 장에서 잔차 패턴과 진단을 자세히 다룹니다.</p><p>공통 자료는 출처 미확인 학습 예제이며 적합한 식을 실제 시장의 가격모형이나 개별 적정가로 사용하지 않습니다.</p>''')
 sec('practice','확인 문제','계수의 단위와 예측의 대상을 확인하세요','''<ol class="learn-exercises"><li>잔차 합이 0이면 모든 점이 직선 위에 있나요?<details><summary>답과 해설</summary><p>아니요. 양수·음수가 상쇄될 수 있습니다. SSE와 잔차 패턴을 봐야 합니다.</p></details></li><li>절편은 항상 실제로 관측 가능한 X=0의 의미인가요?<details><summary>답과 해설</summary><p>아니요. X=0이 관측 범위 밖이면 물리적 해석이 부적절할 수 있습니다.</p></details></li><li>X와 Y를 바꾸면 OLS 기울기는 원래의 역수인가요?<details><summary>답과 해설</summary><p>일반적으로 아닙니다. 최소화하는 잔차 방향이 바뀝니다.</p></details></li><li>학습 자료의 R²가 높으면 인과효과와 미래 정확성이 보장되나요?<details><summary>답과 해설</summary><p>아니요. 적합도·인과 식별·외부 예측 성능은 별도로 확인해야 합니다.</p></details></li></ol>''')
 sec('macro','CH2 Macro에서 읽기','변수·단위·범위를 확인하고 회귀선을 읽습니다','''<p>CH2 Macro의 회귀 결과를 읽을 때는 X와 Y의 정의, 로그 등 변환 여부, 관측 단위·기간·유형과 건수, 적용 범위를 먼저 확인하세요. 이 장의 단순선형식이 모든 서비스 모형의 산식이라고 전제하지 않습니다.</p><p>회귀선을 시장 관계를 이해하는 요약으로 읽고, 개별 물건의 적정가나 조건 변경의 확정적 효과로 바꾸어 해석하지 않습니다.</p><p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 통계 열기 →</a></p>''')
 sec('recap','정리와 참고자료','식·잔차·가정을 함께 읽습니다','''<p>단순 OLS는 세로 잔차제곱합을 최소화하는 직선을 찾습니다. 계수의 단위, 절편의 범위, 개별 예측의 불확실성, 외삽과 영향 관측을 함께 확인합니다.</p><p>다음 <a href="/learn/stats/residuals/">18장 「잔차와 회귀모형의 가정」</a>으로 이어집니다.</p><ul><li><a href="https://www.itl.nist.gov/div898/handbook/pmd/section1/pmd141.htm">NIST: Linear Least Squares Regression</a> — 최소제곱의 원리와 적용 한계.</li></ul><p class="learn-source-note">본문과 그림은 공통 학습 자료 및 별도 가상 예제로 직접 작성했습니다. 실제 시장의 가격모형이 아닙니다. 참고자료 확인: 2026-10-08.</p>''')
 p=ROOT/'regression/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="단순선형회귀와 최소제곱법">\n'+'\n'.join(parts)+'\n</article>',html,count=1,flags=re.S)
 html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1단순선형회귀의 기울기·절편·잔차와 최소제곱 계산, 예측·외삽의 한계를 설명합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
