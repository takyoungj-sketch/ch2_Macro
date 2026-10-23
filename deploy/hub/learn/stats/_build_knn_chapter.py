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
 d=dict(description='최근접 이웃의 계산을 설명하기 위한 별도 가상 자료.',x=x,y=y,query=query,neighbors=neighbors(query,3),k1=predict(query,1),k3=predict(query,3),grid=grid,scaling=dict(points=points,query=q,scales=scales,raw=raw,scaled=scaled),vote=dict(labels=[1,0,1],probability=2/3))
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
 b=tx(24,28,'두 입력 변수의 가상 4건: 표준화가 이웃 순서를 바꿉니다')
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
 sec('quick-start','학습 목표','비슷한 관측의 답을 모아 예측할 수 있을까요?','<p>새 학생의 결과를 예측할 때 학습 시간과 연습 횟수가 비슷한 학생들의 결과를 참고할 수 있습니다. 최근접 이웃은 이처럼 입력이 가까운 관측을 찾아 그 답을 모으는 방법입니다. 무엇을 비슷하다고 볼지 정하는 일이 예측의 중요한 부분입니다.</p><p>이 장에서는 가까운 이웃을 직접 찾고 회귀와 분류에 사용하는 과정을 따라갑니다. 변수의 단위와 이웃 수를 바꾸면 예측이 어떻게 달라지는지도 살펴봅니다.</p><ul class="learn-objectives"><li>입력의 거리로 이웃을 찾고 목표값을 집계해 예측합니다.</li><li>변수 스케일과 거리의 정의가 이웃 순서를 바꾸는 이유를 설명합니다.</li><li>이웃 수 K와 예측의 민감도·복잡도를 연결합니다.</li><li>동점·중복·고차원의 한계를 알고 전체 절차를 검증합니다.</li></ul>')
 sec('neighbors','핵심 이해','입력이 가까운 학습 관측에서 답을 모읍니다','<p><strong>K최근접 이웃(KNN)</strong>은 새 입력과 가까운 학습 관측 K개를 찾아 그 목표값을 모아 예측합니다. 회귀계수 하나로 관계를 요약하기보다 학습 관측을 저장하고 거리 규칙을 이용합니다. 이웃을 찾는 과정에 목표값의 집계를 더하면 회귀나 분류에 사용할 수 있습니다.</p>'+g1+'<p>학습 자료의 X는 [1, 2, 4, 6, 8], Y는 [2, 3, 5, 4, 8]입니다. 새 입력 x=3.2까지의 거리는 순서대로 2.2·1.2·0.8·2.8·4.8입니다. 가까운 세 입력은 X=4, 2, 1이며 그 Y는 5, 3, 2입니다. 이웃 하나만 쓰면 예측은 5, 세 개를 평균하면 (5+3+2)/3≈3.33입니다.</p><p><strong>거리는 입력 X로 계산합니다.</strong> 아직 모르는 목표 Y를 이웃 선택에 쓰면 답을 미리 사용하는 누수입니다. 또한 학습 시간 하나가 비슷하다고 다른 조건까지 비슷한 것은 아니므로, 어떤 입력을 포함할지 먼저 정해야 합니다.</p>')
 sec('distance','거리의 정의','여러 입력의 차이를 어떻게 합칠지 정합니다','<p>변수가 하나라면 두 값의 절대 차이로 거리를 잴 수 있습니다. 변수가 여러 개면 각 차이를 합치는 규칙이 필요합니다. <strong>유클리드 거리</strong>는 차이의 제곱합에 제곱근을 취하고, <strong>맨해튼 거리</strong>는 절대 차이를 합합니다. 어떤 변수와 거리를 쓰는지에 따라 이웃이 달라집니다.</p><p>범주 이름을 임의로 1·2·3으로 바꾸면 원래 없던 순서와 간격이 생길 수 있습니다. 원핫 인코딩처럼 범주를 구분하는 표현이나 수치·범주를 함께 다루는 거리를 검토합니다. 지도상의 거리와 여러 입력의 유사도를 나타내는 거리는 구별해야 합니다.</p><details><summary>거리의 산식</summary><p>두 입력 x와 z의 유클리드 거리는 √Σ(xⱼ−zⱼ)², 맨해튼 거리는 Σ|xⱼ−zⱼ|입니다. 위치를 사용한다면 위도·경도의 도 단위를 평면의 미터 단위처럼 취급하지 않도록 주의합니다.</p></details>')
 sec('scale','변수 스케일','숫자 범위가 큰 변수가 거리를 좌우할 수 있습니다',f'<p>입력이 두 개인 가상 자료 A=(50, 1), B=(60, 10), C=(100, 5), D=(110, 6)을 보겠습니다. 새 입력은 (62, 2)입니다. 원래 숫자로 거리를 구하면 B가 가장 가깝습니다. 반면 각 열을 학습 표준편차로 나누면 A가 가장 가까워집니다.</p>'+g2+f'<p>학습 자료 네 개의 표준편차는 첫 번째 입력이 {scales[0]:.4f}, 두 번째가 {scales[1]:.4f}입니다. 원 숫자에서는 첫 번째 입력의 차이가 상대적으로 크게 작용합니다. 표준화는 각 변수의 차이를 그 변수의 퍼짐에 비추어 비교하도록 비중을 바꿉니다.</p><p>평균과 표준편차는 학습 부분에서 구하고 검증·시험에는 그 기준을 적용합니다. 교차검증이라면 반복마다 다시 구합니다. 상수 열, 이상치, 결측값의 처리도 같은 학습 절차 안에 둡니다.</p><p>표준화가 모든 문제에서 최적의 거리를 만드는 것은 아닙니다. 변수의 중요도와 측정 오류, 예측 목적도 고려해야 합니다.</p><details><summary>표준화 거리의 계산</summary><p>각 학습 열의 표준편차 sⱼ로 나눈 거리는 √Σ[(xⱼ−zⱼ)/sⱼ]²입니다. 같은 학습 평균을 빼는 효과는 두 점의 차이에서 상쇄되지만 표준편차로 나누는 효과는 남습니다. 이 예제의 표준편차는 분모로 4를 사용했습니다.</p></details>')
 sec('complexity','K와 복잡도','작은 K는 가까이 보고 큰 K는 넓게 평균합니다','<p>K가 작으면 가까운 몇 관측의 영향을 크게 받으므로 세부적인 관계뿐 아니라 잡음에도 민감할 수 있습니다. K가 커지면 더 넓은 영역을 평균해 예측이 덜 흔들릴 수 있지만 중요한 국소적 관계를 놓칠 수도 있습니다.</p>'+g3+'<p>모든 이웃에 같은 비중을 줄 때 K가 학습 관측 수와 같으면, 어디서 예측하든 학습 Y의 평균이 됩니다. 반대로 입력이 중복되지 않은 학습 자료에서 자기 자신을 이웃으로 넣은 K=1은 학습 오차가 0일 수 있습니다. 이미 아는 답을 돌려준 결과이므로 새 자료에서도 정확하다는 증거는 아닙니다.</p><p>균등 가중 KNN 회귀는 고른 이웃의 Y를 평균하므로 그 값들의 범위 안에서 예측합니다. 학습 입력 범위 밖에서도 결과를 낼 수 있지만 직선처럼 추세를 연장하는 방법은 아닙니다. 새 입력이 학습 관측에서 얼마나 떨어져 있는지도 확인해야 합니다.</p>')
 sec('tasks','회귀·분류·가중치','회귀는 값을 평균하고 분류는 범주별 표를 셉니다','<p>회귀에서는 이웃의 Y를 평균할 수 있습니다. 분류에서는 가장 많은 이웃이 속한 범주를 고릅니다. 이진 분류라면 이웃 중 양성의 비율을 확률형 점수로 사용할 수도 있습니다.</p>'+g4+'<p>가까운 이웃에 더 큰 비중을 주는 거리 가중 방식도 있습니다. 가중 회귀의 예측은 Σwᵢyᵢ/Σwᵢ입니다. 예를 들어 거리의 역수 1/dᵢ를 쓰면 거리가 0일 때 별도 규칙이 필요합니다. 같은 입력의 관측만 모아 집계하는 등 구현의 처리 방식을 확인합니다.</p><p>이웃 수가 작으면 양성 비율은 거친 간격으로 달라집니다. 비율을 출력한다고 곧바로 잘 보정된 확률이 되는 것은 아닙니다. 28장에서처럼 확률 보정과 판정 임계값을 평가해야 합니다. 홀수 K도 다중 범주나 가중 투표의 모든 동점을 없애지는 못합니다.</p>')
 sec('ties','동점과 재현성','같은 거리의 관측을 어떻게 고를지도 정합니다','<p>K번째와 K+1번째 관측의 거리가 같으면 어떤 관측을 포함하느냐에 따라 예측이 달라질 수 있습니다. 이 장은 같은 거리일 때 학습 자료에서 앞 번호인 관측을 우선합니다. 실제 분석에서도 순서, 동점, 중복 처리 규칙을 기록해야 결과를 재현할 수 있습니다.</p><p>이웃 수 대신 반경을 정하고 일정 거리 안의 점을 모두 쓰는 방법도 있습니다. 관측이 드문 곳에서는 이웃이 없을 수도 있으므로 그때의 처리 규칙이 필요합니다. KNN에서도 가장 가까운 점까지의 거리와 실제 집계에 기여한 이웃 수를 함께 보면 도움이 됩니다.</p>')
 sec('dimension','차원과 계산량','변수를 많이 넣는다고 이웃을 더 잘 찾는 것은 아닙니다','<p>변수가 늘면 같은 수의 관측으로 채워야 할 공간이 넓어집니다. 관련 없는 변수의 차이가 거리에 섞이면 유용한 이웃을 구별하기도 어려워집니다. 변수 선택이나 차원축소를 검토할 수 있지만 그 기준도 학습 자료 안에서 정해야 합니다.</p><p>KNN은 학습 관측을 저장하고 새 입력마다 이웃을 찾으므로 메모리와 예측 시간도 고려합니다. 탐색용 트리나 근사 검색으로 계산을 줄일 수 있지만 가까운 점을 얼마나 정확하게 찾는지 확인해야 합니다. 이웃 검색의 정확성과 새 자료에 대한 예측 성능은 서로 다른 평가입니다.</p>')
 sec('validation','선택과 검증','K와 거리와 전처리를 묶어서 비교합니다','<p>후보 K는 각 폴드의 학습 관측 수보다 클 수 없습니다. 거리의 종류, 표준화, 가중 방식까지 하나의 절차로 묶어 같은 분할에서 비교합니다. 회귀는 목적에 맞는 MAE·RMSE를, 분류는 오류 비용과 확률의 품질을 살펴봅니다.</p><p>같은 학생의 반복 관측이나 중복 자료가 학습과 평가에 섞이면 지나치게 쉬운 이웃을 찾을 수 있습니다. 기존 학생의 미래 결과를 예측할지 처음 보는 학교에 적용할지 정하고, 23·26장의 시간·집단 분할을 맞춰 사용합니다. 자신을 이웃에서 빼는 것만으로 이런 의존성이 해결되지는 않습니다.</p><p>가장 좋은 CV 점수로 설정을 골랐다면 그 점수는 선택에 사용한 결과입니다. 독립적인 최종 평가와 구별해야 합니다.</p>')
 sec('practice','확인 문제','가까움과 예측의 의미를 확인하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('K=1의 학습 오차 0이면 좋은 모형인가요?','자기 자신을 이웃으로 사용한 결과일 수 있습니다. 독립적인 검증이 필요합니다.'),('표준화하면 원래 이웃 순서가 유지되나요?','변수별 비중이 달라져 순서가 바뀔 수 있습니다.'),('실제 Y가 비슷한 관측을 골라 새 Y를 예측해도 되나요?','예측할 목표를 이웃 선택에 사용하면 누수입니다. 예측 시점에 아는 입력만 사용해야 합니다.'),('K가 홀수면 모든 동점이 사라지나요?','아니요. 거리 경계·다중 범주·가중 투표 등의 동점은 남을 수 있습니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','유사성의 기준과 적용 범위를 확인합니다','<p>유사 사례나 이웃 기반 결과를 읽을 때 포함 변수·단위·스케일·거리·K·가중치와 검색 범위를 확인하세요. 가장 가까운 사례도 절대적으로는 멀 수 있습니다. 이 장의 가상 예제가 서비스의 실제 알고리즘이라고 전제하지 않습니다.</p><p>비슷한 입력의 평균은 개별 적정가나 인과적 비교가 아닙니다. 자료 밀도·조건 차이·평가 설계와 함께 해석합니다.</p>')
 sec('recap','학습 요약','가까움의 정의도 예측 모형의 일부입니다','<ul class="learn-recap-list"><li><strong>KNN</strong>은 입력이 가까운 학습 관측 K개를 찾아 회귀에서는 값을, 분류에서는 범주별 표를 집계합니다.</li><li>거리에는 예측 시점에 아는 입력만 사용합니다. 목표값을 이웃 선택에 넣으면 누수입니다.</li><li>변수 스케일을 바꾸면 이웃 순서도 달라질 수 있습니다. 표준화 기준은 학습 부분에서 구합니다.</li><li>작은 K는 개별 관측에 민감하고 큰 K는 넓게 평균합니다. K=1의 학습 오차 0은 새 자료의 성능을 보장하지 않습니다.</li><li>K·거리·가중치·전처리와 동점 처리까지 정하고 목적에 맞는 분할로 검증합니다.</li></ul><p>다음 <a href="/learn/stats/decision-tree/">30장 「의사결정나무」</a>에서는 입력 조건으로 자료를 나누어 예측하는 방법을 살펴봅니다.</p><details class="learn-references"><summary>참고자료와 예제 데이터</summary><ul><li><a href="https://scikit-learn.org/stable/modules/neighbors.html">scikit-learn: Nearest Neighbors</a></li><li><a href="../knn-example.json">가상 이웃·거리·예측 계산 자료</a></li></ul><p class="learn-source-note">본문과 그림은 별도 가상 예제로 직접 작성했습니다. 참고자료 기존 확인일: 2026-10-09.</p></details>')
 p=ROOT/'knn/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="최근접 이웃과 변수의 스케일">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1최근접 이웃의 거리·K·표준화와 회귀·분류 집계, 동점·고차원·검증의 한계를 학습합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
