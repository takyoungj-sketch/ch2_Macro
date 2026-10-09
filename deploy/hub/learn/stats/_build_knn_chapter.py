"""Chapter 29: deterministic nearest neighbors and scale examples."""
from pathlib import Path
from statistics import mean,pstdev
from html import escape
import json,re,math
ROOT=Path(__file__).resolve().parent

def build():
 x=[1,2,4,6,8];y=[2,3,5,4,8];query=3.2
 def neighbors(v,k):return sorted(range(5),key=lambda i:(abs(x[i]-v),i))[:k]
 def predict(v,k):return mean(y[i] for i in neighbors(v,k))
 points=[[50,1],[60,10],[100,5],[110,6]];q=[62,2];scales=[pstdev(p[j] for p in points) for j in range(2)];raw=[math.dist(p,q) for p in points];scaled=[math.sqrt(sum(((p[j]-q[j])/scales[j])**2 for j in range(2))) for p in points]
 grid=[dict(x=i/20,k1=predict(i/20,1),k3=predict(i/20,3)) for i in range(201)]
 d=dict(description='별도 가상 자료이며 실제 시장 성능이나 서비스 알고리즘이 아님.',x=x,y=y,query=query,neighbors=neighbors(query,3),k1=predict(query,1),k3=predict(query,3),grid=grid,scaling=dict(points=points,query=q,scales=scales,raw=raw,scaled=scaled),vote=dict(labels=[1,0,1],probability=2/3))
 (ROOT/'knn-example.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def ln(x,y,a,b,c='#94a3b8'):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="{c}"/>'
 def fig(id,title,b,cap):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 410" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=tx(24,28,'가상 입력 x=3.2에서 가까운 세 점을 고릅니다')+ln(70,310,570,310)+ln(70,55,70,310)
 for i,(a,v) in enumerate(zip(x,y)):b+=f'<circle cx="{70+a*55}" cy="{310-v*28}" r="6" fill="'+('#2563eb' if i in neighbors(query,3) else '#94a3b8')+'"/>'+tx(75+a*55,300-v*28,f'({a},{v})')
 b+=ln(70+query*55,65,70+query*55,310,'#d97706')
 for v in [0,2,4,6,8]:b+=tx(65+v*55,340,v)+tx(30,315-v*28,v)
 b+=tx(24,385,'가로 입력 X / 세로 목표 Y · 주황선 x=3.2 · 파랑: 이웃 3개')
 g1=fig('neighbors','K개의 가까운 관측',b,'그림 1. 거리는 입력 X만으로 계산합니다. 목표 Y를 거리 계산에 넣지 않습니다. 가장 가까운 순서는 X=4, 2, 1입니다.')
 b=tx(24,28,'면적·층 가상 4건: 표준화가 이웃 순서를 바꿉니다')
 for j,(name,dist,maxv) in enumerate([('원 단위 거리',raw,60),('표준화 거리',scaled,3)]):
  left=65+j*300;b+=tx(left,75,name)+ln(left,320,left+235,320)
  for i,v in enumerate(dist):
   h=v/maxv*205;xx=left+i*57;b+=f'<rect x="{xx}" y="{320-h}" width="35" height="{h}" fill="#2563eb"/>'+tx(xx,308-h,f'{v:.2f}')+tx(xx+8,345,'ABCD'[i])
  b+=tx(left,382,'최단: '+('B' if j==0 else 'A'))
 g2=fig('scale','표준화 전후의 거리',b,'그림 2. A=(50,1), B=(60,10), C=(100,5), D=(110,6), 질의=(62,2)입니다. 학습 4건의 각 열 표준편차로 나눈 거리입니다. 좌우 세로 척도가 달라 막대 높이를 직접 비교하지 않습니다.')
 b=tx(24,28,'같은 가상 5점으로 만든 K=1·K=3 예측')+ln(70,320,570,320)+ln(70,55,70,320)
 for key,col in [('k1','#2563eb'),('k3','#d97706')]:
  # Draw horizontal/vertical steps rather than implying interpolation.
  pts=[]
  for i,r in enumerate(grid):
   if i:pts.append((70+r['x']*50,320-grid[i-1][key]*28))
   pts.append((70+r['x']*50,320-r[key]*28))
  b+='<polyline data-k="'+key+'" points="'+' '.join(f'{a},{v}' for a,v in pts)+'" fill="none" stroke="'+col+'" stroke-width="2"/>'
 for a,v in zip(x,y):b+=f'<circle cx="{70+a*50}" cy="{320-v*28}" r="4" fill="#111827"/>'
 for v in [0,2,4,6,8,10]:b+=tx(65+v*50,350,v)
 for v in [0,4,8]:b+=tx(30,325-v*28,v)
 b+=tx(24,385,'가로 X / 세로 예측 Y · 파랑 K=1 / 주황 K=3')
 g3=fig('complexity','이웃 수와 예측 모양',b,'그림 3. 0.05 간격으로 평가한 계단 표시입니다. 경계 위치에는 격자 오차가 있습니다. 같은 거리면 앞 번호를 우선하며 이 그림만으로 최적 K를 정하지 않습니다.')
 b=tx(24,28,'동일한 이웃 탐색 뒤, 목표 유형에 따라 집계')
 for yy,title,desc in [(90,'회귀: 수치형 목표','이웃 Y가 5·3·2 → 평균 10/3 ≈ 3.33'),(230,'분류: 별도 가상 이진 라벨','이웃 라벨 1·0·1 → 양성 비율 2/3')]:b+=f'<rect x="65" y="{yy}" width="510" height="95" rx="6" fill="#eaf2ff"/>'+tx(85,yy+32,title)+tx(85,yy+67,desc)
 b+=tx(24,385,'이웃의 양성 비율이 잘 보정된 확률이라는 보장은 없습니다')
 g4=fig('tasks','회귀와 분류의 집계',b,'그림 4. 회귀 예제와 분류 라벨 예제는 별개입니다. 균등 가중을 사용했으며 거리 가중을 쓰면 집계가 달라집니다.')
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('neighbors','최근접 이웃의 원리','비슷한 입력을 가진 학습 관측에서 답을 모읍니다','<p>K최근접 이웃(KNN)은 새 입력과 가까운 학습 관측 K개를 찾고 그 목표값을 집계하는 방법입니다. 고정된 회귀계수 하나로 관계를 표현하기보다 저장된 관측과 거리 규칙을 이용합니다. 이웃 탐색 자체와 목표를 예측하는 지도학습은 구별합니다.</p>'+g1+'<p>가상 학습 자료는 X=[1,2,4,6,8], Y=[2,3,5,4,8]입니다. x=3.2까지의 거리는 2.2·1.2·0.8·2.8·4.8이므로 가까운 세 입력은 4·2·1입니다. K=1의 회귀 예측은 5, K=3은 (5+3+2)/3≈3.33입니다.</p><p>여기서 가까움은 입력 공간의 개념입니다. 아직 모르는 목표값을 거리 계산에 넣으면 답을 미리 쓰는 누수가 됩니다. 실제 부동산에서는 면적이 비슷하다는 이유만으로 위치·용도까지 비슷하다고 볼 수 없습니다.</p>')
 sec('distance','거리의 정의','숫자의 차이를 어떤 방식으로 합칠지 정합니다','<p>유클리드 거리는 d(x,z)=√Σ(xⱼ−zⱼ)², 맨해튼 거리는 Σ|xⱼ−zⱼ|입니다. 거리 종류와 포함 변수가 바뀌면 이웃도 바뀝니다. 좌표상의 지리적 거리와 여러 속성의 특징 공간 거리는 같은 개념이 아닙니다.</p><p>범주를 임의로 1·2·3으로 바꾸면 순서와 간격을 부여하게 됩니다. 원핫 인코딩·혼합형 거리 등 목적에 맞는 표현을 검토해야 합니다. 위도·경도의 도 단위를 그대로 평면 미터처럼 취급하지 않도록 주의합니다.</p>')
 sc1,sc2=scales
 sec('scale','변수 스케일','단위가 큰 변수가 거리를 지배할 수 있습니다',f'<p>면적과 층을 함께 쓰는 가상 예제를 봅시다. 원 숫자의 거리에서는 질의 (62㎡,2층)에 B=(60㎡,10층)가 가장 가깝습니다. 학습 자료의 표준편차로 나누면 A=(50㎡,1층)가 가장 가까워집니다.</p>'+g2+f'<p>학습 4건의 면적 표준편차는 {sc1:.4f}, 층은 {sc2:.4f}이며 분모는 4를 사용했습니다. 표준화 거리는 √Σ[(xⱼ−zⱼ)/sⱼ]²입니다. 같은 학습 평균을 빼는 것은 두 점의 차이에서 상쇄되지만, 각 열을 표준편차로 나누는 것은 비중을 바꿉니다.</p><p>평균·표준편차는 학습 부분에서만 추정하고 검증·시험에 적용합니다. 교차검증이라면 폴드마다 다시 적합합니다. 상수 열·이상치·결측을 처리하는 규칙도 그 안에 포함합니다.</p><p>표준화가 항상 최적 거리라는 뜻은 아닙니다. 각 변수에 비슷한 통계적 스케일을 부여하는 선택이므로, 중요도·측정오차·목적을 함께 고려하세요.</p>')
 sec('complexity','K와 복잡도','작은 이웃은 국소적이고 큰 이웃은 더 넓게 평균합니다','<p>K가 작으면 개별 관측·잡음에 민감할 수 있고, K가 커지면 더 넓은 영역을 평균해 국소 구조를 놓칠 수 있습니다. 균등 가중에서 K가 학습 건수와 같으면 회귀 예측은 모든 입력에서 학습 Y 평균이 됩니다.</p>'+g3+'<p>중복 없는 학습 입력에서 자기 자신을 이웃에 포함한 K=1의 학습 오차는 0이 될 수 있습니다. 이는 이미 본 답을 돌려주는 결과이지 새 관측에 정확하다는 증거가 아닙니다. 학습에서 자신을 제외한 평가도 중복·집단 의존성이 있으면 충분하지 않을 수 있습니다.</p><p>균등 가중 KNN 회귀는 선택한 이웃의 목표 범위 안에서 평균을 냅니다. 관측 범위 밖에서도 값을 출력하지만 추세를 연장하는 방식은 아니므로 멀리 떨어진 질의의 신뢰성을 별도로 판단해야 합니다.</p>')
 sec('tasks','회귀·분류·가중치','이웃을 찾은 다음 무엇을 집계할지 정합니다','<p>균등 가중 회귀는 ŷ=(1/K)Σ이웃 yᵢ입니다. 분류는 범주별 표를 세고 가장 많은 범주를 선택하며, 이진 문제에서는 이웃의 양성 비율을 확률형 점수로 사용할 수 있습니다.</p>'+g4+'<p>거리 가중 회귀는 ŷ=Σwᵢyᵢ/Σwᵢ로 계산하며 가까운 이웃에 더 큰 비중을 줄 수 있습니다. 예를 들어 wᵢ=1/dᵢ는 d=0에서 별도 규칙이 필요합니다. 동일 입력이 있으면 그 점들만 집계하는 등 구현의 처리 방식을 명시하세요.</p><p>분류의 양성 비율은 이웃 수가 작으면 거칠게 변합니다. 확률 보정과 임계값은 28장에서 배운 방식으로 별도 평가합니다. 홀수 K를 써도 다중 범주나 거리 가중에서 모든 동점 문제가 사라지는 것은 아닙니다.</p>')
 sec('ties','동점과 재현성','경계의 같은 거리도 규칙이 필요합니다','<p>K번째와 K+1번째 거리가 같으면 어떤 관측을 포함하는지에 따라 예측이 달라질 수 있습니다. 이 장에서는 같은 거리일 때 학습 자료의 앞 번호를 우선합니다. 실제 분석도 순서·동점·중복 처리 규칙을 기록해야 재현할 수 있습니다.</p><p>반경 기반 이웃은 K를 고정하는 대신 일정 거리 안의 점을 사용합니다. 밀도에 따라 이웃 수가 달라지고 아무 이웃도 없는 질의가 생길 수 있으므로 처리 규칙이 필요합니다. KNN 역시 가장 가까운 점까지의 거리와 유효 이웃 수를 함께 살피는 것이 유용합니다.</p>')
 sec('dimension','차원과 계산량','특징을 많이 넣으면 가까운 점을 찾기 어려워질 수 있습니다','<p>차원이 커지면 같은 표본 수로 채워야 하는 공간이 넓어집니다. 무관한 변수가 거리에 섞이면 유용한 이웃을 구별하기 어려워질 수 있습니다. 변수 선택·차원축소를 검토하되 해당 변환도 학습 경계 안에서 적합합니다.</p><p>관측을 저장하고 질의마다 거리를 찾으므로 예측 시간과 메모리도 중요합니다. 트리 기반 탐색이나 근사 탐색을 쓰면 계산 방식·정확성의 절충이 달라질 수 있습니다. 근사 이웃 검색과 통계 모형의 일반화 성능을 구별합니다.</p>')
 sec('validation','선택과 검증','K·거리·전처리를 하나의 절차로 평가합니다','<p>후보 K는 각 폴드의 학습 건수를 넘지 않아야 합니다. 거리 종류·표준화·가중 방식까지 묶어 같은 분할에서 비교하고, 회귀는 목적에 맞는 MAE/RMSE, 분류는 오류 비용·확률 품질을 평가합니다.</p><p>같은 단지의 반복 거래나 중복 관측이 학습과 평가 양쪽에 있으면 지나치게 쉬운 이웃을 찾을 수 있습니다. 새 단지·미래 시점 중 무엇에 적용할지에 맞춰 23·26장의 집단·시간 분할을 사용합니다. 최저 CV 점수를 선택에 사용했다면 독립 최종 평가와 구별합니다.</p>')
 sec('practice','확인 문제','가까움과 예측의 의미를 확인하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('K=1의 학습 오차 0이면 좋은 모형인가요?','자기 자신을 이웃으로 사용한 결과일 수 있습니다. 독립적인 검증이 필요합니다.'),('표준화하면 원래 이웃 순서가 유지되나요?','변수별 비중이 달라져 순서가 바뀔 수 있습니다.'),('가까운 단가를 가진 관측을 골라 단가를 예측해도 되나요?','예측할 목표를 이웃 선택에 사용하면 누수입니다. 예측 시점에 아는 입력만 사용해야 합니다.'),('K가 홀수면 모든 동점이 사라지나요?','아니요. 거리 경계·다중 범주·가중 투표 등의 동점은 남을 수 있습니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','유사성의 기준과 적용 범위를 확인합니다','<p>유사 사례나 이웃 기반 결과를 읽을 때 포함 변수·단위·스케일·거리·K·가중치와 검색 범위를 확인하세요. 가장 가까운 사례도 절대적으로는 멀 수 있습니다. 이 장의 가상 예제가 서비스의 실제 알고리즘이라고 전제하지 않습니다.</p><p>비슷한 입력의 평균은 개별 적정가나 인과적 비교가 아닙니다. 자료 밀도·조건 차이·평가 설계와 함께 해석합니다.</p>')
 sec('recap','정리와 참고자료','거리 설계가 모형의 일부입니다','<p>KNN은 이웃을 찾는 거리와 답을 집계하는 규칙으로 구성됩니다. K뿐 아니라 스케일·변수·동점·평가 경계를 함께 정해야 합니다.</p><p>다음 <a href="/learn/stats/decision-tree/">30장 「의사결정나무」</a>로 이어집니다.</p><ul><li><a href="https://scikit-learn.org/stable/modules/neighbors.html">scikit-learn: Nearest Neighbors</a></li><li><a href="../knn-example.json">가상 이웃·거리·예측 계산 자료</a></li></ul><p class="learn-source-note">본문과 그림은 별도 가상 예제로 직접 작성했습니다. 참고자료 확인: 2026-10-09.</p>')
 p=ROOT/'knn/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="최근접 이웃과 변수의 스케일">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1최근접 이웃의 거리·K·표준화와 회귀·분류 집계, 동점·고차원·검증의 한계를 학습합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
