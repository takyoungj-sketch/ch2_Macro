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
 result=dict(description='공통 학습 자료의 고전적 단순 OLS. 가정 검증 완료를 뜻하지 않음.',n=n,df=df,SST=sst,SSR=ssr,SSE=sse,R2=m['R2'],adjusted_R2=1-(sse/df)/(sst/(n-1)),s=s,RMSE=math.sqrt(sse/n),MAE=mean(abs(e) for e in m['residuals']),slope=m['slope'],slope_se=se_b,slope_ci=[m['slope']-crit*se_b,m['slope']+crit*se_b],t=tv,p=pv,F=F,F_p=float(fdist.sf(F,1,df)),critical=crit,point100=p100,grid=grid)
 (ROOT/'model-fit-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,v):return f'<text x="{x}" y="{y}">{escape(str(v))}</text>'
 def ln(x,y,a,b,c='#94a3b8',extra=''):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="{c}" {extra}/>'
 def fig(id,title,b,cap,h=400):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 w=500*m['R2'];b=tx(24,30,'평균만 사용할 때의 제곱합을 나누어 봅니다')
 b+=f'<rect x="65" y="105" width="{w}" height="80" fill="#2563eb"/><rect x="{65+w}" y="105" width="{500-w}" height="80" fill="#d97706"/>'
 b+=tx(65,220,f'적합으로 줄어든 부분: {100*m["R2"]:.1f}%')+tx(65,255,f'남은 잔차 부분: {100*(1-m["R2"]):.1f}%')+tx(65,300,f'SST {sst:,.2f} = SSR {ssr:,.2f} + SSE {sse:,.2f}')+tx(24,365,'파랑: SSR / 주황: SSE · 단위: (만원/㎡)²')
 g1=fig('variance','총제곱합의 분해',b,'그림 1. 공통 자료의 절편 포함 OLS 분해입니다. 막대 전체는 SST이며 길이는 제곱합의 비율을 나타냅니다. 거래의 일정 비율을 정확히 맞혔다는 뜻이 아닙니다.')
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
 b+=tx(24,380,'가로: 면적(㎡) / 세로: 단가(만원/㎡)')+tx(24,408,'파랑 띠: 평균 / 주황 띠: 새 관측 · 각 X별 점별 구간')
 g2=fig('bands','신뢰구간과 예측구간',b,'그림 2. 고전적 가정 아래의 점별 95% 구간입니다. 전체 곡선을 동시에 95%로 덮는 띠가 아닙니다. 음수 하한도 숨기지 않았으며, 이는 이 모형의 적용 한계를 점검할 단서입니다.',435)
 b=tx(24,28,'면적 100㎡에서 같은 중심, 다른 불확실성')
 axis=lambda v:90+v*1.4
 for yy,key,label,c in [(130,'ci','평균 반응','#2563eb'),(240,'pi','새 거래 한 건','#d97706')]:
  low,high=p100[key];b+=tx(24,yy-32,label)+ln(axis(low),yy,axis(high),yy,c,'stroke-width="4"')+f'<circle cx="{axis(p100["fit"])}" cy="{yy}" r="5" fill="{c}"/>'+tx(axis(low),yy+28,f'{low:.2f} ~ {high:.2f}')
 b+=ln(90,320,560,320)
 for v in [0,100,200,300]:b+=tx(axis(v)-5,345,v)
 b+=tx(24,382,f'중심 {p100["fit"]:.2f}만원/㎡ · 점은 두 구간에서 같은 적합값')
 g3=fig('at100','100제곱미터의 두 구간',b,'그림 3. 평균 반응 구간은 모형 평균의 추정 오차를, 개별 예측구간은 여기에 새 관측 자체의 오차까지 반영합니다. 실제 거래의 보장 범위가 아닙니다.')
 b=tx(24,28,'X 위치에 따른 구간의 반폭')+ln(65,320,580,320)+ln(65,55,65,320)
 for key,c in [('ci','#2563eb'),('pi','#d97706')]:b+='<polyline data-width="'+key+'" points="'+' '.join(f"{px(r['x'])},{320-(r[key][1]-r['fit'])*1.6}" for r in grid)+'" fill="none" stroke="'+c+'" stroke-width="3"/>'
 b+=ln(px(mean(x)),60,px(mean(x)),320,'#64748b','stroke-dasharray="4 4"')
 for v in [0,100,200,300]:b+=tx(px(v)-5,345,v)
 for v in [0,50,100,150]:b+=tx(25,325-v*1.6,v)
 b+=tx(24,380,f'파랑: 평균 / 주황: 새 관측 · 점선 x̄={mean(x):.2f}㎡')
 g4=fig('width','구간 폭과 자료의 중심',b,'그림 4. 가로축은 면적(㎡), 세로축은 95% 구간의 반폭(만원/㎡)입니다. 이 단순 등분산 모형에서는 평균 면적에서 가장 좁고 멀어질수록 넓어집니다.')
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('r-squared','R²와 제곱합','평균만 사용할 때보다 얼마나 줄었는지 봅니다',f'<p>R²는 관측된 Y의 변동 가운데 적합식이 설명하는 비율입니다. 절편을 포함한 같은 표본의 OLS에서는 <strong>SST=Σ(yᵢ−ȳ)², SSE=Σ(yᵢ−ŷᵢ)², SSR=Σ(ŷᵢ−ȳ)²</strong>이며 SST=SSR+SSE입니다. 따라서 R²=1−SSE/SST입니다.</p>'+g1+f'<p>공통 30건의 면적–단가 회귀는 R²={m["R2"]:.4f}입니다. 평균만 사용한 기준보다 학습 제곱오차를 약 {100*m["R2"]:.1f}% 줄였다는 뜻이지, 거래 {100*m["R2"]:.1f}%를 정확히 맞혔다거나 인과관계의 비율이라는 뜻이 아닙니다.</p><p>절편 포함 OLS의 학습 R²는 SST&gt;0이면 0~1입니다. 결과값이 전부 같으면 이 정의의 분모가 0입니다. 절편이 없는 모형이나 별도 검증 자료에서는 이러한 범위·분해가 그대로 적용되지 않을 수 있습니다. 검증 R²는 사용한 기준 평균을 명시해야 하며 음수가 될 수 있습니다.</p>')
 sec('adj-r-squared','수정 R²','변수 수를 반영해도 검증 성능은 따로 확인합니다',f'<p>같은 자료·결과변수에서 중첩 OLS에 설명변수를 추가하면 R²는 감소하지 않습니다. 절편을 포함한 모수 수를 p라 할 때 <strong>수정 R²=1−[SSE/(n−p)]/[SST/(n−1)]</strong>는 자유도 손실을 반영합니다.</p><p>이 단순회귀는 p=2, n−p=28이고 수정 R²={result["adjusted_R2"]:.4f}입니다. 수정 R²는 내려가거나 음수가 될 수 있으며, 이를 최대화했다고 새 자료의 성능이나 인과 타당성이 보장되지는 않습니다. 표본·결측 처리·결과변수 변환이 다른 모형을 숫자만으로 비교하지 않습니다.</p>')
 sec('error-scale','원 단위의 오차','R² 옆에 잔차의 크기와 단위를 적습니다',f'<p>R²는 단위가 없지만 실제 오차의 크기는 말해 주지 않습니다. 이 자료의 학습 MAE={result["MAE"]:.2f}, 학습 RMSE=√(SSE/n)={result["RMSE"]:.2f}, 잔차 표준오차 <strong>s=√(SSE/(n−p))={s:.2f}</strong>만원/㎡입니다. RMSE와 s는 분모가 다릅니다.</p><p>같은 R²라도 결과변수의 퍼짐이 큰 자료에서는 원 단위 오차가 클 수 있습니다. 반대로 범위를 좁힌 동질적 표본에서는 작은 오차에도 R²가 낮을 수 있습니다. R²에 보편적인 합격선을 두기보다 목적·표본·원 단위 오차를 함께 봅니다.</p><p id="mape">MAPE는 평균 절대 백분율 오차입니다. 실제값이 0이면 정의할 수 없고 0 근처에서는 불안정하며, 작은 값에 큰 비중을 줄 수 있습니다. 단위 없는 지표라는 이유만으로 자료·목표가 다른 결과를 무조건 비교하지 않습니다. 예측오차 지표는 뒤 장에서 자세히 다룹니다.</p>')
 sec('coefficients','계수의 불확실성','계수의 크기·구간·검정을 함께 읽습니다',f'<p>고전적 단순회귀에서 기울기의 표준오차는 SE(b₁)=s/√Sxx입니다. 이 자료의 b₁={m["slope"]:.4f}, SE={se_b:.4f}, 95% 신뢰구간은 {result["slope_ci"][0]:.4f}~{result["slope_ci"][1]:.4f}입니다. 단위는 (만원/㎡)/㎡입니다.</p><p>H₀:β₁=0의 t=b₁/SE(b₁)={tv:.3f}, 자유도 28, 양측 p={pv:.5f}입니다. 절편 포함 단순회귀의 전체 F검정은 F(1,28)={F:.3f}=t²이며 같은 p값을 냅니다. 다중회귀의 전체 F검정은 모든 기울기가 함께 0인지 검정하므로 개별 t검정과 질문이 다릅니다.</p><p>작은 p값이 큰 실질적 차이·높은 예측력·인과효과를 뜻하지는 않습니다. 위 구간과 p값은 올바른 선형 평균, 독립·등분산 정규 오차 등 고전적 가정 아래의 계산 예제입니다. 공통 자료가 그 가정을 충족한다고 검증된 것은 아닙니다.</p>')
 sec('bands','두 종류의 구간','평균을 추정하는 것과 새 관측을 예측하는 것은 다릅니다','<p>같은 면적 x₀에서 평균 반응 E[Y|X=x₀]을 추정할 수도 있고, 새 거래 한 건 Y새를 예측할 수도 있습니다. 중심 적합값 ŷ₀는 같아도 불확실성의 대상이 다릅니다.</p>'+g2+'<p>h₀=1/n+(x₀−x̄)²/Sxx로 두면, 평균 반응의 신뢰구간은 <strong>ŷ₀±t₀.₉₇₅,ₙ₋₂·s√h₀</strong>, 새 관측 한 건의 예측구간은 <strong>ŷ₀±t₀.₉₇₅,ₙ₋₂·s√(1+h₀)</strong>입니다. 두 번째의 1은 새 관측 자체의 오차분산을 반영합니다. 새 오차가 학습 자료와 독립이고 같은 분산을 가진다는 가정도 필요합니다.</p><p>그림의 각 X별 95% 구간을 연결해도 전체 회귀곡선을 동시에 95%로 덮는 구간은 아닙니다. 여러 지점을 동시에 추론하려면 동시 신뢰대역 등 별도 방법이 필요합니다.</p>')
 sec('point-example','100㎡ 예제','같은 적합값에서 구간 폭이 크게 달라집니다',f'<p>100㎡의 적합 단가는 {p100["fit"]:.2f}만원/㎡입니다. 평균 반응의 95% 신뢰구간은 {p100["ci"][0]:.2f}~{p100["ci"][1]:.2f}, 새 관측의 95% 예측구간은 {p100["pi"][0]:.2f}~{p100["pi"][1]:.2f}입니다. 반올림 전 회귀계수와 t값으로 계산했습니다.</p>'+g3+'<p>신뢰수준 95%는 가정 아래 표본추출·구간 계산을 반복했을 때 고정된 모평균을 포함하는 절차의 장기 비율입니다. 이미 얻은 구간 안에 고정 모평균이 95% 확률로 놓인다는 빈도주의 해석은 하지 않습니다. 예측구간은 새 관측도 변동하는 반복 과정의 포함률을 대상으로 합니다.</p>')
 sec('width','구간 폭을 결정하는 것','자료의 중심에서 멀어질수록 평균 추정이 불안정합니다','<p>구간 폭은 잔차 변동 s, 신뢰수준, 표본 수, 설명변수의 퍼짐과 예측 위치에 달려 있습니다. 신뢰수준을 높이면 넓어지고, 같은 조건에서 자료가 더 풍부하면 평균 추정은 정밀해질 수 있습니다.</p>'+g4+'<p>평균 주변에서 h₀가 작아지므로 평균 신뢰구간이 좁습니다. 그러나 표본이 커져도 새 관측 자체의 오차까지 사라지는 것은 아닙니다. 개별 예측구간을 평균 신뢰구간처럼 좁아질 것으로 기대하면 안 됩니다.</p><p>공식은 관측 범위 밖에서도 값을 내지만 함수 형태가 틀릴 위험은 담지 않습니다. 음수 단가 하한은 실제 음수 거래를 주장하는 것이 아니라, 가산 정규 오차 모형이 양수 자료에 부적절할 가능성을 점검할 단서입니다. 하한을 임의로 0에 잘라 같은 명목 포함률이라고 주장하지 않습니다.</p>')
 sec('limits','진단과 외부 검증','좁은 구간이 모든 불확실성을 포함하지는 않습니다','<p>위 구간은 선택한 모형·가정에 조건부입니다. 변수 선택·변환 탐색을 거친 불확실성, 표본 편향, 측정오차, 시점 변화, 빠진 변수의 영향까지 모두 포함한 것이 아닙니다. 이분산·군집·시계열 의존성이 있으면 추론 방식을 조정해야 합니다.</p><p>계수에 강건 표준오차를 적용했다고 새 관측의 예측구간까지 자동으로 올바르게 구성되는 것은 아닙니다. 조건부 오차분포와 예측 대상을 별도로 고려해야 합니다.</p><p>적합도는 학습 자료의 요약, 계수·평균 구간은 추정의 불확실성, 별도 자료 오차는 일반화 성능입니다. 세 질문을 구별하고 18장의 잔차 진단과 함께 읽으세요.</p>')
 sec('practice','확인 문제','숫자가 답하는 질문을 구별하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('R²=0.42이면 거래 42%를 정확히 맞혔나요?','아니요. 같은 학습 표본에서 평균만 쓰는 기준 대비 제곱오차가 줄어든 비율입니다.'),('새 거래를 예측할 때 평균 신뢰구간을 사용해도 되나요?','새 관측의 오차가 빠져 너무 좁습니다. 목적에 맞는 예측구간이 필요합니다.'),('그림 전체가 동시에 95% 신뢰구간인가요?','각 X의 점별 구간입니다. 동시에 전체 곡선을 덮는 보장과 다릅니다.'),('p값이 작으면 미래 예측도 정확한가요?','아니요. 계수에 관한 추론과 별도 자료의 예측 성능은 다른 질문입니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','적합도·단위·구간의 대상을 함께 확인합니다','<p>R²와 표본 수만 보지 말고 결과변수의 정의·변환, 원 단위 오차, 자유도, 구간의 대상과 계산 가정을 확인하세요. 화면의 구간이 평균 신뢰구간인지 개별 예측구간인지 확인한 후 해석합니다. 이 장의 공식이 모든 서비스 결과의 실제 산식이라고 전제하지 않습니다.</p><p>공통 자료는 출처 미확인 학습 예제입니다. 계산된 구간을 실제 시장의 보장 범위나 개별 물건의 적정가 범위로 사용하지 않습니다.</p>')
 sec('recap','정리와 참고자료','적합이 좋은지와 얼마나 확실한지는 다른 질문입니다','<p>R²·수정 R²·잔차 표준오차를 함께 읽고, 계수·평균 반응·새 관측 중 구간이 무엇을 대상으로 하는지 확인하세요.</p><p>다음 <a href="/learn/stats/supervised-unsupervised/">22장 「통계적 설명과 예측, 지도학습과 비지도학습」</a>으로 이어집니다.</p><ul><li><a href="https://www.itl.nist.gov/div898/handbook/pmd/section5/pmd511.htm">NIST: 평균 반응의 추정과 신뢰구간</a></li><li><a href="https://www.itl.nist.gov/div898/handbook/pmd/section5/pmd512.htm">NIST: 새 관측의 예측과 불확실성</a></li><li><a href="../model-fit-example.json">제곱합·검정·구간·그림 좌표</a></li></ul><p class="learn-source-note">본문·그림은 공통 학습 자료로 직접 작성했습니다. 참고자료 확인: 2026-10-09.</p>')
 p=ROOT/'model-fit/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="회귀모형의 적합도와 추정의 불확실성">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1R²·수정 R²·잔차 표준오차와 계수의 추론, 평균 신뢰구간·개별 예측구간을 비교합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
