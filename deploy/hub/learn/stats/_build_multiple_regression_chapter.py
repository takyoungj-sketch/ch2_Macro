"""Chapter 19: multiple regression, exact reproducible examples."""
from pathlib import Path
import numpy as np
import json,re
from scipy.stats import t
ROOT=Path(__file__).resolve().parent

def model(X,y):
 X=np.asarray(X,float);y=np.asarray(y,float);b=np.linalg.lstsq(X,y,rcond=None)[0];e=y-X@b;n,p=X.shape;sse=float(e@e);s2=sse/(n-p);se=np.sqrt(np.diag(np.linalg.inv(X.T@X))*s2);r2=1-sse/float(((y-y.mean())**2).sum());crit=t.ppf(.975,n-p)
 return dict(beta=b.tolist(),residuals=e.tolist(),SSE=sse,df=n-p,R2=r2,adjusted_R2=1-(1-r2)*(n-1)/(n-p),se=se.tolist(),ci=[[float(v-crit*w),float(v+crit*w)] for v,w in zip(b,se)])

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];x=np.array([r['area'] for r in rows]);y=np.array([r['price'] for r in rows]);floor=np.array([r['floor'] for r in rows]);n=len(x)
 simple=model(np.column_stack([np.ones(n),x]),y);multi=model(np.column_stack([np.ones(n),x,floor]),y)
 sx=np.arange(1,7,dtype=float);g=np.array([0,0,0,1,1,1]);sy=7+sx-9*g+np.array([.2,-.4,.2,.2,-.4,.2]);demo=model(np.column_stack([np.ones(6),sx,g]),sy);unadjusted=model(np.column_stack([np.ones(6),sx]),sy)
 rx=sx-np.where(g==0,2,5);ry=sy-np.where(g==0,9,3)
 result=dict(description='공통 학습 자료 및 별도 가상 6점. 인과효과·실제 시장 모형이 아님.',simple=simple,multiple=multi,demo=dict(x=sx.tolist(),group=g.tolist(),y=sy.tolist(),model=demo,simple=unadjusted,residual_x=rx.tolist(),residual_y=ry.tolist()))
 (ROOT/'multiple-regression-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{s}</text>'
 def ln(x,y,a,b,c='#94a3b8',extra=''):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="{c}" {extra}/>'
 def dot(x,y,c='#2563eb'):return f'<circle cx="{x}" cy="{y}" r="5" fill="{c}"/>'
 def fig(id,title,b,cap):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 400" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=tx(24,28,'가상 자료: 파랑 A집단 / 주황 B집단')+ln(70,320,580,320)+ln(70,55,70,320)
 for xx,yy,gg in zip(sx,sy,g):b+=dot(70+xx*75,320-yy*23,'#2563eb' if gg==0 else '#d97706')
 for gg,lo,hi,c in [(0,1,3,'#2563eb'),(1,4,6,'#d97706')]:b+=ln(70+lo*75,320-(7+lo-9*gg)*23,70+hi*75,320-(7+hi-9*gg)*23,c,'stroke-width="2"')
 a,k=unadjusted['beta'];b+=ln(145,320-(a+k)*23,520,320-(a+6*k)*23,'#64748b','stroke-dasharray="5 4"')
 for v in [1,2,3,4,5,6]:b+=tx(65+v*75,345,v)
 for v in [0,4,8,10]:b+=tx(35,325-v*23,v)
 b+=tx(24,380,'가로 X / 세로 Y · 회색 점선: 집단을 구분하지 않은 회귀')
 f1=fig('groups','집단 조정 전후의 관계',b,'그림 1. 별도 가상 6점입니다. 집단 내 기울기는 양수지만 전체 기울기는 음수입니다. 집단 간 X범위가 겹치지 않아 같은 X에서의 집단 차이는 모형 가정에 의존합니다.')
 b=tx(24,28,'집단 평균을 각각 뺀 X와 Y')+ln(100,210,540,210)+ln(320,65,320,330)+ln(160,338,480,82,'#2563eb')
 for xx,yy in zip(rx,ry):b+=dot(320+xx*130,210-yy*104)
 for v in [-1,0,1]:b+=tx(315+v*130,355,v)
 for v in [-1,0,1]:b+=tx(65,215-v*104,v)
 b+=tx(24,383,'가로: X의 집단 내 편차 / 세로: Y의 집단 내 편차')
 f2=fig('partial','집단을 조정한 기울기',b,'그림 2. 그림 1의 각 집단 평균을 제거했습니다. 같은 좌표의 점은 겹칩니다. 이 편차들의 원점 통과 회귀 기울기는 다중회귀 X계수 1과 같습니다.')
 b=tx(24,28,'공통 자료: 면적 계수와 고전적 95% 신뢰구간')
 vals=[v for m in [simple,multi] for v in m['ci'][1]];lo=min(vals)-.1;hi=max(vals)+.1;px=lambda v:170+(v-lo)/(hi-lo)*380
 for yy,m,label in [(140,simple,'면적만'),(240,multi,'면적 + 층')]:
  l,u=m['ci'][1];b+=tx(24,yy+5,label)+ln(px(l),yy,px(u),yy,'#2563eb','stroke-width="3"')+dot(px(m['beta'][1]),yy)+tx(170,yy+32,f"{m['beta'][1]:.3f} [{l:.3f}, {u:.3f}]")
 b+=ln(170,320,550,320)
 for v in np.linspace(lo,hi,4):b+=tx(px(v)-15,345,f'{v:.2f}')
 b+=tx(24,382,'계수 단위: (만원/㎡)/㎡ · 가정이 맞을 때의 구간')
 f3=fig('coefficients','면적 계수 비교',b,'그림 3. 같은 30건에서 층을 추가했을 때의 면적 계수입니다. 구간은 등분산·독립·정규 오차 등 고전적 가정에 근거하며, 이 자료에서 가정이 충족되었다는 뜻은 아닙니다.')
 b=tx(24,28,'완전 공선성: X₂=2X₁')+ln(70,320,570,320)+ln(70,55,70,320)
 for v in range(1,6):b+=dot(70+v*85,320-v*44)
 b+=ln(155,276,495,100,'#2563eb')
 for v in range(6):b+=tx(65+v*85,345,v)
 for v in [0,4,8,10]:b+=tx(35,325-v*22,v)
 b+=tx(24,382,'가로 X₁ / 세로 X₂ · b₁+2b₂만 구별할 수 있습니다')
 f4=fig('collinear','완전 공선성',b,'그림 4. 별도 가상 설명변수입니다. 두 열이 정확히 비례하면 개별 계수의 유일한 OLS 해가 없습니다. 단위를 바꾸는 것만으로 중복 정보가 생기지는 않습니다.')
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','핵심 이해','여러 설명변수의 관계를 한 식에서 읽습니다','<p>단순회귀가 면적 하나로 단가를 요약했다면, 다중회귀는 면적·층·유형처럼 여러 설명변수를 함께 사용합니다. 모집단 모형은 <strong>Y=β₀+β₁X₁+⋯+βₖXₖ+ε</strong>, 표본 적합식은 ŷ=b₀+b₁x₁+⋯+bₖxₖ입니다. 결과변수 하나에 설명변수 여러 개를 쓰는 모형이며, 결과변수 여러 개를 다루는 다변량 회귀와 구별합니다.</p><p>다른 포함 변수를 고정했을 때 Xⱼ가 1단위 다른 관측의 적합값 차이가 bⱼ입니다. 이는 가산 모형의 조건부 비교이며, 실제 물건의 한 속성을 바꾸었을 때의 인과효과를 자동으로 뜻하지 않습니다. 상호작용이나 제곱항이 있으면 변화량 해석도 달라집니다.</p>')
 sec('groups','조정 전후','집단 구성 때문에 전체 관계가 달라질 수 있습니다',f'<p>별도 가상 자료에서 A집단의 X는 1·2·3, Y는 8.2·8.6·10.2이고, B집단의 X는 4·5·6, Y는 2.2·2.6·4.2입니다. X가 큰 관측이 수준이 낮은 B에 몰려 있습니다.</p>'+f1+f'<p>집단을 무시한 기울기는 {unadjusted["beta"][1]:.3f}이지만 B이면 D=1, A이면 D=0인 더미변수를 넣으면 <strong>ŷ=7+1×X−9×D</strong>입니다. 집단별 절편을 허용하니 X계수는 +1이 됩니다. 부호 변화가 어느 모형의 인과적 정답을 증명하는 것은 아닙니다.</p>')
 sec('partial','통제의 의미','다른 변수로 설명되는 부분을 제거해 볼 수 있습니다','<p>이 예제에서 X와 Y 각각에서 집단 평균을 빼면 집단 사이의 평균 차이가 제거됩니다. 남은 편차 사이의 기울기가 더미변수를 포함한 다중회귀의 X계수와 같습니다.</p>'+f2+'<p>일반적으로도 Xⱼ와 Y를 나머지 설명변수·절편에 각각 회귀한 잔차끼리 회귀하면 같은 Xⱼ계수를 얻습니다. 이는 같은 관측·가중치와 충분한 열 독립성이 있는 OLS의 부분회귀 성질입니다. 다만 이 보조회귀의 기본 출력 표준오차를 원래 다중회귀와 그대로 같다고 볼 수는 없습니다. 원래 모형의 잔차 자유도를 사용해야 합니다.</p><p>실제 자료에 없는 변수 조합을 ‘다른 조건이 같은 비교’라고 부르면 외삽이 됩니다. 위 가상 자료처럼 두 집단의 X범위가 겹치지 않는 경우에는 공통 기울기·가산성 가정에 특히 의존합니다.</p>')
 b0,b1,b2=multi['beta']
 sec('example','공통 자료 계산','면적과 층을 함께 넣고 계수를 읽습니다',f'<p>공통 30건의 단가를 Y, 면적과 층을 X로 넣으면 <strong>ŷ={b0:.3f} {b1:+.4f}×면적 {b2:+.4f}×층</strong>입니다. 면적 계수는 같은 층에서 면적 1㎡ 차이, 층 계수는 같은 면적에서 1층 차이에 대한 적합값 차이입니다. ‘같은 층’은 이 식의 비교 조건이며 위치·유형·연식까지 같다는 뜻이 아닙니다.</p>'+f3+f'<p>계수는 Σ(yᵢ−ŷᵢ)²를 최소화해 구합니다. 설계행렬 X에 절편 열을 포함하고 열들이 독립이면 b=(XᵀX)⁻¹Xᵀy로 표현할 수 있습니다. 실제 계산은 역행렬을 직접 만들기보다 QR·SVD 같은 수치해법을 사용합니다.</p><p>절편 포함 모수 수 p=3, 잔차 자유도 n−p=27입니다. 잔차분산 추정은 SSE/(n−p), 고전적 계수 구간은 bⱼ±t×SE(bⱼ)입니다. 이분산·군집 의존성이 있으면 그 구조에 맞는 표준오차를 검토합니다. <a href="../multiple-regression-example.json">계수·구간·예제 자료</a>는 반올림 전 값입니다.</p><p>공통 자료는 출처 미확인 학습 예제입니다. 유형을 섞은 단순한 연습 모형을 실제 시장 모형이나 개별 적정가로 사용하지 않습니다.</p>')
 sec('coding','범주와 상호작용','기준집단과 조건부 차이를 명시합니다','<p>범주가 K개라면 절편과 함께 보통 K−1개의 더미변수를 넣습니다. 기준집단을 A로 두면 B더미의 계수는 같은 다른 변수 값에서 B−A의 적합값 차이입니다. 기준을 바꾸면 계수 표현은 달라져도 같은 모형의 적합값은 유지됩니다.</p><p>모든 범주 더미와 절편을 동시에 넣으면 열이 중복됩니다. 범주에 단순히 1·2·3을 부여해 수치형 변수로 넣으면 같은 간격의 직선적 변화라는 별도 가정이 생깁니다.</p><p>집단별 기울기가 다를 수 있다면 X×D 상호작용을 검토합니다. ŷ=b₀+b₁X+b₂D+b₃XD에서 A의 기울기는 b₁, B는 b₁+b₃, 같은 X에서 B−A 차이는 b₂+b₃X입니다. 이때 b₂만을 모든 X에서의 집단 차이로 읽으면 안 됩니다. X 중심화는 기준 X의 해석을 바꾸지만 같은 항을 유지하면 적합값은 같습니다.</p>')
 sec('collinearity','다중공선성','정보가 겹치면 개별 계수의 구분이 어려워집니다','<p>설명변수끼리 강하게 겹치면 작은 자료 변화에도 개별 계수가 크게 움직이고 표준오차가 커질 수 있습니다. 다중공선성 자체가 OLS 계수의 편향을 뜻하지는 않지만, 조건부 효과를 정밀하게 구분하기 어려워집니다.</p>'+f4+'<p>완전 공선성에서는 계수를 고유하게 정할 수 없습니다. 예컨대 X₂=2X₁이면 b₁X₁+b₂X₂=(b₁+2b₂)X₁이므로 b₁과 b₂의 여러 조합이 같은 적합값을 만듭니다.</p><p>VIFⱼ=1/(1−Rⱼ²)는 Xⱼ를 나머지 설명변수에 회귀한 Rⱼ²로 계산합니다. 높은 값은 점검 단서이며 특정 임계값만으로 변수를 자동 삭제하지 않습니다. 단위 변환만으로 정보 중복이 사라지지도 않습니다. 계수 해석과 예측 중 무엇이 목적인지에 따라 변수 통합·자료 보강·규제 등을 검토합니다.</p>')
 sec('fit','적합도와 검정','변수를 추가하면 R²가 올라가는 것은 당연할 수 있습니다',f'<p>같은 관측·결과변수·절편을 사용하는 중첩 OLS 모형에서는 변수를 추가해도 학습 SSE가 늘지 않고 R²가 줄지 않습니다. 공통 자료의 면적만 사용한 R²={simple["R2"]:.3f}, 면적·층 R²={multi["R2"]:.3f}입니다. 이 증가만으로 추가 변수가 유용하다고 결론내리지 않습니다.</p><p>수정 R²=1−[SSE/(n−p)]/[SST/(n−1)]는 모수 수를 반영합니다. 여기서는 {multi["adjusted_R2"]:.3f}이며 변수를 추가하면 내려갈 수도 있습니다. 수정 R²도 새 자료 성능이나 인과 타당성의 보장은 아닙니다.</p><p>계수별 t검정은 다른 포함 변수를 조건으로 해당 계수가 0인지 봅니다. 여러 계수를 함께 검정하는 부분 F검정은 F=[(SSE축소−SSE전체)/q]/[SSE전체/(n−p전체)]로, 같은 자료·중첩 모형과 고전적 가정이 필요합니다. q는 추가 계수 수입니다. 결과변수 변환이나 결측 처리로 표본이 달라진 모형을 이 공식으로 바로 비교하지 않습니다.</p>')
 sec('causality','변수 선택과 인과','통제변수는 많을수록 좋은 것이 아닙니다','<p>누락된 변수가 Y와 관련되고 포함된 X와도 관련되면 단순회귀 계수는 그 관계를 함께 담을 수 있습니다. 그러나 관련 변수를 모두 넣는다고 인과효과가 보장되는 것은 아닙니다. 측정오차·선택편향·빠진 교란 등이 남을 수 있습니다.</p><p>무엇을 통제할지는 시간 순서와 인과 질문에 따라 정합니다. 총효과를 알고 싶은데 원인 이후의 매개변수를 통제하면 질문 자체가 달라질 수 있고, 두 변수의 공통 결과인 충돌변수를 조건으로 삼으면 없던 연관이 생길 수 있습니다. 유의확률만으로 변수를 넣고 빼는 방식은 이러한 문제를 해결하지 못합니다.</p><p>예측 목적이라면 예측 시점에 실제로 알 수 있는 변수만 사용하고 새 지역·시점에서 검증합니다. 사후에 알게 된 결과 관련 변수를 넣는 데이터 누출을 피해야 합니다.</p>')
 sec('practice','확인 문제','계수의 조건과 모형의 한계를 읽으세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('층을 통제한 면적 계수는 모든 조건이 같은 인과효과인가요?','아니요. 포함된 층만 고정한 모형상 비교이며 위치·유형 등은 통제되지 않았습니다.'),('절편과 모든 범주 더미를 넣어도 되나요?','열이 중복되어 계수가 고유하지 않습니다. 보통 기준 범주 하나를 제외합니다.'),('상호작용이 있으면 집단 차이는 항상 b₂인가요?','아니요. b₂+b₃X로 X에 따라 달라집니다.'),('변수를 추가해 R²가 오르면 모형이 좋아졌나요?','학습 R²의 비감소는 중첩 OLS의 성질입니다. 진단·불확실성·새 자료 성능을 따로 확인합니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','계수의 조건을 결과와 함께 기록합니다','<p>결과를 읽을 때 결과변수의 단위·변환, 포함 변수, 기준 범주, 상호작용, 표본과 결측 처리, 표준오차 계산 방법을 확인하세요. 이 장의 연습식이 서비스의 실제 산식이라고 전제하지 않습니다.</p><p>‘다른 조건이 같다’는 표현에는 어떤 변수를 조건으로 삼았는지 적습니다. 모형에 포함되지 않은 조건까지 같다고 확대하거나 개별 물건의 적정가로 해석하지 않습니다.</p>')
 sec('recap','정리와 참고자료','조건부 비교와 인과효과를 구별합니다','<p>다중회귀는 여러 변수의 관계를 함께 요약합니다. 계수는 포함 변수와 함수 형태에 따라 달라지므로 기준·공선성·자료 범위·추론 가정을 함께 읽어야 합니다.</p><p>다음 <a href="/learn/stats/log-regression/">20장 「로그변환과 비선형 관계」</a>에서 변수 변환에 따른 해석을 살펴봅니다.</p><ul><li><a href="https://www.itl.nist.gov/div898/handbook/pmd/section1/pmd141.htm">NIST: Linear Least Squares Regression</a> — 모형과 최소제곱의 정의.</li></ul><p class="learn-source-note">본문·그림은 공통 학습 자료와 별도 가상 예제로 직접 작성했습니다. 참고자료 확인: 2026-10-08.</p>')
 p=ROOT/'multiple-regression/index.html';p.parent.mkdir(exist_ok=True);html=p.read_text(encoding='utf-8') if p.exists() else (ROOT/'regression/index.html').read_text(encoding='utf-8').replace('https://ch2data.com/learn/stats/regression/','https://ch2data.com/learn/stats/multiple-regression/')
 html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="다중회귀와 변수의 해석">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1다중회귀의 조건부 계수, 더미변수·상호작용·공선성과 통제변수의 한계를 학습합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
