"""Chapter 31: deterministic clustering examples and figures."""
from pathlib import Path
from statistics import mean
from itertools import combinations
from html import escape
import json,math,re
ROOT=Path(__file__).resolve().parent

def build():
 points=[[1,1],[1,2],[2,1],[7,7],[7,8],[8,7]]
 def dist(a,b):return sum((x-y)**2 for x,y in zip(a,b))
 def fit(initial):
  centers=[points[i][:] for i in initial]
  for _ in range(100):
   labels=[min(range(len(centers)),key=lambda j:dist(p,centers[j])) for p in points]
   if len(set(labels))!=len(centers):return None
   new=[[mean(points[i][a] for i in range(6) if labels[i]==j) for a in range(2)] for j in range(len(centers))]
   if new==centers:break
   centers=new
  return dict(centers=centers,labels=labels,inertia=sum(dist(p,centers[j]) for p,j in zip(points,labels)))
 models=[]
 for k in range(1,6):models.append(min((v for ini in combinations(range(6),k) if (v:=fit(ini)) is not None),key=lambda v:v['inertia']))
 model=models[1];sil=[]
 for i,p in enumerate(points):
  a=mean(math.sqrt(dist(p,q)) for j,q in enumerate(points) if i!=j and model['labels'][j]==model['labels'][i]);b=mean(math.sqrt(dist(p,q)) for j,q in enumerate(points) if model['labels'][j]!=model['labels'][i]);sil.append(dict(a=a,b=b,s=(b-a)/max(a,b)))
 d=dict(description='군집 계산을 설명하는 단위 없는 가상 6점. 모든 관측점 조합을 초기 중심으로 반복한 결과 중 최소 목적값.',points=points,models=models,silhouette=sil,hierarchy=dict(x=[1,2,6,9],linkage='complete',merges=[[0,1,1,2],[2,3,3,2],[4,5,8,4]]))
 (ROOT/'clustering-example.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def ln(x,y,a,b,c='#94a3b8'):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="{c}"/>'
 def fig(id,title,b,cap):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 410" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=tx(24,28,'가상 6점 · K=2 · 원은 관측, 십자는 군집 중심')+ln(70,325,580,325)+ln(70,55,70,325)
 for i,(p,j) in enumerate(zip(points,model['labels'])):
  x,y=70+p[0]*55,325-p[1]*30;b+=f'<circle cx="{x}" cy="{y}" r="6" fill="'+['#2563eb','#d97706'][j]+'"/>'+tx(x-18,y-8,'ABCDEF'[i])
 for p in model['centers']:
  x,y=70+p[0]*55,325-p[1]*30;b+=ln(x-8,y,x+8,y,'#111827')+ln(x,y-8,x,y+8,'#111827')
 for v in [0,2,4,6,8]:b+=tx(65+v*55,350,v)+tx(30,330-v*30,v)
 b+=tx(24,390,'가로 X₁ / 세로 X₂ · 두 변수는 같은 무단위 척도')
 g1=fig('kmeans','K-means의 군집과 중심',b,'그림 1. A·B·C와 D·E·F를 묶었을 때 중심은 (4/3,4/3), (22/3,22/3)입니다. 그림의 가로·세로 픽셀 척도는 다르며 거리는 표시 좌표가 아닌 원자료로 계산합니다.')
 b=tx(24,28,'군집 수를 늘리면 관측을 더 잘게 나눌 수 있습니다')+ln(80,325,570,325)+ln(80,55,80,325)
 pp=[(100+i*105,325-m['inertia']*2.2) for i,m in enumerate(models)];b+='<polyline points="'+' '.join(f'{x},{y}' for x,y in pp)+'" stroke="#2563eb" stroke-width="2" fill="none"/>'
 for i,((x,y),m) in enumerate(zip(pp,models)):b+=f'<circle cx="{x}" cy="{y}" r="5" fill="#2563eb"/>'+tx(x+8,y-9,f'{m["inertia"]:.2f}')+tx(x-4,350,i+1)
 for v in [0,50,100]:b+=tx(25,330-v*2.2,v)
 b+=tx(24,390,'가로: 군집 수 K / 세로: 군집 내 제곱거리 합 W')
 g2=fig('number','군집 수와 목적값',b,'그림 2. 동일 자료·동일 척도에서 초기 관측점 조합을 모두 시도한 결과입니다. 이 예제의 꺾임은 뚜렷하지만 모든 자료에 자연스러운 K가 있는 것은 아닙니다.')
 b=tx(24,28,'K=2의 관측별 실루엣: 같은 군집과 다른 군집 비교')+ln(100,335,565,335)
 for i,v in enumerate(sil):
  yy=75+i*38;w=v['s']*440;b+=tx(65,yy+17,'ABCDEF'[i])+f'<rect x="100" y="{yy}" width="{w}" height="23" fill="#2563eb"/>'+tx(110+w,yy+17,f'{v["s"]:.3f}')
 b+=tx(95,360,'0')+tx(535,360,'1')+tx(24,390,f'가로: 실루엣 s · 평균 {mean(v["s"] for v in sil):.3f}')
 g3=fig('silhouette','관측별 실루엣',b,'그림 3. 유클리드 거리로 계산했습니다. 이 예제는 모든 실루엣이 양수여서 0~1만 표시했지만 지표 자체의 범위는 −1~1입니다.')
 b=tx(24,28,'별도 1차원 가상 자료 · 완전연결 덴드로그램')+ln(65,325,580,325)+ln(65,55,65,325)
 xs={0:125,1:245,2:385,3:505};hs={i:0 for i in range(4)}
 for i,(a,c,h,n) in enumerate(d['hierarchy']['merges']):
  yy=325-h*30;b+=ln(xs[a],325-hs[a]*30,xs[a],yy,'#2563eb')+ln(xs[c],325-hs[c]*30,xs[c],yy,'#2563eb')+ln(xs[a],yy,xs[c],yy,'#2563eb');xs[4+i]=(xs[a]+xs[c])/2;hs[4+i]=h
 b+=f'<line x1="70" y1="145" x2="575" y2="145" stroke="#d97706" stroke-dasharray="5 4"/>'+tx(400,135,'높이 6에서 자르면 2군집')
 for i,v in enumerate([1,2,6,9]):b+=tx(xs[i]-18,350,f'x={v}')
 for v in [0,2,4,6,8]:b+=tx(35,330-v*30,v)
 b+=tx(24,390,'세로: 병합 거리 / 가로: 관측의 배치 순서')
 g4=fig('hierarchy','완전연결 계층적 군집',b,'그림 4. 1과 2가 거리 1에서, 6과 9가 거리 3에서 합쳐집니다. 두 군집 사이 최대 거리 8에서 마지막 병합이 일어납니다. 가로 간격은 원자료의 거리를 뜻하지 않습니다.')
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','학습 목표','정답 이름표가 없어도 비슷한 관측을 묶을 수 있습니다','<p>학습 시간과 연습 횟수가 비슷한 학생들을 묶어 보면 어떤 모습의 집단이 나타날까요? 미리 ‘집단 A’나 ‘집단 B’라는 답을 주지 않고 자료에서 비슷한 묶음을 찾는 것이 군집분석입니다.</p><p>이 장에서는 K평균으로 관측을 배정하고 중심을 옮기는 과정을 따라갑니다. 군집 수와 묶음의 분리 정도를 살펴보고, 계층적으로 합친 결과를 덴드로그램에서 읽는 방법도 익힙니다.</p><ul class="learn-objectives"><li>정답 범주를 예측하는 분류와 군집분석을 구별합니다.</li><li>K평균의 배정·중심 갱신과 군집 내 제곱거리 합을 계산합니다.</li><li>군집 수, 스케일, 초기값에 따라 결과가 달라지는 이유를 설명합니다.</li><li>실루엣과 덴드로그램을 읽고 군집의 안정성과 해석 범위를 확인합니다.</li></ul>')
 sec('purpose','핵심 이해','분류는 주어진 이름을 예측하고 군집은 묶음을 찾습니다','<p><strong>군집분석</strong>은 정답 라벨 없이 선택한 변수와 유사성 기준으로 관측을 묶는 비지도학습입니다. 28장의 분류는 이미 주어진 범주를 예측하지만 군집분석은 묶음 자체를 찾습니다. 군집 번호 0·1·2는 이름표일 뿐 순서나 우열이 아닙니다.</p><p>학생을 학습 시간과 연습 횟수로 묶을 때와 관심 과목으로 묶을 때는 다른 결과가 나올 수 있습니다. 무엇을 입력으로 정하는지가 ‘비슷함’의 뜻을 정합니다. 미리 정한 학년·학급별 집단과 알고리즘이 찾아낸 군집도 구별해야 합니다.</p>')
 sec('kmeans','K평균의 원리','가까운 중심에 배정하고 평균으로 중심을 옮깁니다','<p><strong>K평균(K-means)</strong>은 군집 수 K를 먼저 정합니다. 각 관측을 가까운 중심에 배정하고 그 군집의 평균으로 중심을 갱신하며, 관측과 중심 사이의 제곱거리 합을 줄입니다.</p>'+g1+'<ol><li>초기 중심 K개를 정합니다.</li><li>각 관측을 가장 가까운 중심에 배정합니다.</li><li>배정된 관측의 평균으로 각 중심을 옮깁니다.</li><li>배정이나 중심이 충분히 안정될 때까지 반복합니다.</li></ol><p>가상 자료는 A=(1, 1), B=(1, 2), C=(2, 1), D=(7, 7), E=(7, 8), F=(8, 7)입니다. 앞의 세 점과 뒤의 세 점을 묶으면 중심은 각각 (4/3, 4/3), (22/3, 22/3)입니다. 중심은 평균이므로 실제 관측 중 하나일 필요가 없습니다.</p><p>이 배정과 평균 갱신은 목적값을 늘리지 않지만 가장 좋은 전체 해를 보장하지는 않습니다. 초기 중심을 달리해 여러 번 실행하거나 K-means++ 같은 초기화 방법을 사용합니다.</p><details><summary>목적함수와 예제의 초기화</summary><p>군집 Cₖ의 중심을 μₖ라고 하면 W=ΣₖΣᵢ∈Cₖ‖xᵢ−μₖ‖²를 줄입니다. W는 inertia 또는 군집 내 제곱합이라고 합니다. 이 예제에서 K=2의 W는 8/3≈2.67입니다.</p><p>교재의 작은 자료에서는 관측점으로 고를 수 있는 초기 중심 조합을 모두 시도하고 그중 목적값이 가장 작은 결과를 사용했습니다. 거리가 같으면 앞 번호 중심을 우선하고 빈 군집이 생기는 초기화는 제외했습니다. 동점과 빈 군집 처리도 재현에 필요한 규칙입니다.</p></details>')
 sec('scale','변수·거리·표준화','어떤 차이에 비중을 둘지 먼저 정합니다','<p>표준 K평균은 수치형 입력의 제곱 유클리드 거리를 사용합니다. 학습 시간과 연습 횟수처럼 숫자 범위가 다른 변수를 그대로 넣으면 변동 폭이 큰 쪽이 거리를 좌우할 수 있습니다. 29장의 표준화는 각 변수를 표준편차 단위로 바꿉니다. 다만 통계적 스케일을 맞추는 것이 목적에 맞는 중요도를 정해 주는 것은 아닙니다.</p><p>시험 점수를 넣어 군집을 만든 뒤 군집 간 점수 차이를 발견했다고 하면, 묶음의 기준으로 쓴 차이를 다시 확인한 셈입니다. 무엇으로 묶고 무엇으로 결과를 설명할지 적어야 합니다. 범주를 임의의 숫자로 바꾸면 원래 없던 거리와 평균이 생길 수도 있습니다.</p><p>이상치·중복·결측값과 변수 간 강한 상관도 결과를 바꿉니다. 새 자료에 적용하거나 평가 자료를 분리할 때는 표준화·대체값·차원축소 기준을 학습 부분에서 정해 고정합니다. 위치를 입력으로 쓴다면 지도상의 거리와 속성의 유사도도 구별해야 합니다.</p>')
 sec('number','군집 수 선택','더 잘게 나누면 목적값은 작아질 수밖에 없습니다',g2+'<p>군집 수 K를 늘리면 각 관측을 더 가까운 중심에 둘 수 있습니다. 같은 자료에서 전역 최소 W는 K가 커져도 증가하지 않습니다. 여섯 점을 각각 하나의 군집으로 두면 W=0입니다. 따라서 가장 작은 W만으로 유용한 군집 수를 고를 수는 없습니다.</p><p><strong>엘보 방법</strong>은 W가 빠르게 줄다가 감소 폭이 완만해지는 꺾임을 찾습니다. 이 예제에서는 K=2 부근의 꺾임이 뚜렷하지만 실제 자료에는 꺾임이 없거나 모호할 수 있습니다.</p><p>실루엣, 표본을 다시 뽑았을 때의 안정성, 군집 크기, 설명하기 쉬운지와 사용 목적을 함께 봅니다. 모든 자료에 유일한 ‘정답 K’가 있다고 가정하지 않습니다. 반복 알고리즘의 W가 K에 따라 오르내린다면 초기화와 수렴도 확인해야 합니다.</p>')
 sec('silhouette','실루엣','자기 군집에 가깝고 다른 군집에서는 먼지 봅니다','<p><strong>실루엣</strong>은 한 관측이 자기 군집에 얼마나 잘 어울리는지 요약합니다. 같은 군집의 다른 관측까지의 평균 거리 a와, 가장 가까운 다른 군집까지의 평균 거리 b를 비교합니다. 여기서는 W와 달리 제곱하지 않은 유클리드 거리를 사용합니다.</p>'+g3+'<p>1에 가까우면 자기 군집 쪽에 잘 모여 있고, 0 근처면 두 군집까지의 평균 거리가 비슷합니다. 음수면 다른 군집까지의 평균 거리가 더 짧아 배정을 살펴볼 필요가 있습니다. 평균 하나와 함께 개별 음수 값이나 작은 군집도 확인합니다.</p><p>높은 실루엣은 선택한 거리에서 잘 분리되었다는 뜻입니다. 실제로 독립된 유형이 존재한다는 증명은 아닙니다. 길게 휘어진 모양이나 밀도가 서로 다른 자료에서는 지표가 선호하는 묶음이 목적에 맞지 않을 수 있습니다.</p><details><summary>실루엣의 산식과 계산 조건</summary><p>s(i)=[b(i)−a(i)]/max[a(i),b(i)]이며 범위는 −1~1입니다. b(i)는 다른 각 군집까지의 평균 거리를 구한 뒤 그중 가장 작은 값입니다. 단독 관측 군집의 실루엣은 보통 0으로 처리합니다. 전체 지표는 보통 2≤군집 수≤n−1에서 계산합니다.</p></details>')
 sec('hierarchy','계층적 군집','가까운 묶음을 차례로 합쳐 나갑니다','<p><strong>응집형 계층적 군집</strong>은 각 관측을 하나의 군집으로 시작해 가까운 두 군집을 반복해서 합칩니다. 이 과정을 나무 모양으로 그린 것이 덴드로그램입니다. 두 군집 사이의 거리를 어떻게 정하는지가 중요합니다.</p><ul><li><strong>단일연결:</strong> 두 군집에서 가장 가까운 관측 쌍의 거리입니다. 연결 고리처럼 길게 이어질 수 있습니다.</li><li><strong>완전연결:</strong> 가장 먼 관측 쌍의 거리입니다.</li><li><strong>평균연결:</strong> 두 군집 사이 모든 관측 쌍 거리의 평균입니다.</li><li><strong>Ward:</strong> 합칠 때 군집 내 제곱합이 가장 적게 늘어나는 쌍을 고릅니다.</li></ul>'+g4+'<p>이 예제는 1·2·6·9를 완전연결로 묶습니다. 1과 2는 높이 1, 6과 9는 높이 3에서 합쳐집니다. 두 묶음의 가장 먼 쌍은 1과 9이므로 마지막 병합 높이는 8입니다. 높이 6에서 자르면 {1, 2}와 {6, 9}의 두 군집이 됩니다.</p><p><strong>세로축은 병합 수준</strong>이고 가로 간격 자체는 원자료의 거리가 아닙니다. 가지를 뒤집어도 같은 병합을 나타낼 수 있습니다. 연결 기준과 구현에 따라 높이의 정의가 다르므로 특히 Ward의 높이를 원래 두 점 사이 거리처럼 읽지 않습니다.</p><p>한번 합친 군집은 뒤에서 다시 나누지 않으므로 초기 병합의 영향이 남습니다. 관측이 많으면 거리 계산과 그림 표시 비용도 커집니다.</p>')
 sec('alternatives','다른 군집 방법','자료의 모양에 맞는 방법을 살펴봅니다','<p>K평균은 중심 주변으로 모인 군집에 잘 맞습니다. 크기나 밀도가 크게 다르거나 길게 휘어진 묶음에서는 원하는 구조를 놓칠 수 있습니다. <strong>K-medoids</strong>는 평균 대신 실제 관측을 대표점으로 사용합니다.</p><p><strong>DBSCAN</strong>은 이웃 반경과 최소 관측 수로 밀집 영역을 찾으며 일부 점을 어느 군집에도 넣지 않고 잡음으로 남길 수 있습니다. 이 역시 설정에 민감하고 잡음으로 분류됐다는 사실이 데이터 오류라는 뜻은 아닙니다.</p><p>가우시안 혼합모형처럼 소속을 확률적으로 표현하는 방법도 있습니다. 이 장의 K평균 결과가 다른 군집 방법에서도 그대로 나온다고 생각해서는 안 됩니다.</p>')
 sec('validation','안정성과 활용','설정을 바꾸어도 비슷한 묶음이 나오는지 확인합니다','<p>초기값, 표본, 변수 구성, 표준화 방법과 K를 바꿔 결과가 얼마나 유지되는지 살펴봅니다. 군집 번호는 실행마다 뒤바뀔 수 있습니다. 번호 자체의 일치율보다 같은 관측들이 함께 묶이는지 보거나 라벨 순서에 영향을 받지 않는 지표로 비교합니다.</p><p>새 관측은 학습한 K평균 중심 중 가까운 곳에 배정할 수 있습니다. 다만 모든 중심에서 멀다면 적용 범위를 벗어났는지 확인해야 합니다. 계층적 군집에는 보통 새 관측을 배정하는 기본 규칙이 없으므로 별도 규칙이나 재학습이 필요합니다.</p><p>군집을 만드는 데 쓴 변수로 차이 검정을 반복하면 묶음을 고른 영향을 무시할 수 있습니다. 탐색에서 보인 차이와 독립 자료에서 미리 정한 가설을 확인하는 일을 구별합니다. 군집은 인과적인 처치 집단이나 확정된 자연적 경계를 뜻하지 않습니다.</p>')
 sec('practice','확인 문제','묶음의 기준과 해석을 확인하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('A·B·C의 중심은 실제 관측인가요?','평균 (4/3,4/3)은 세 관측 중 어느 것과도 같지 않습니다.'),('W가 가장 작다는 이유로 K=6을 선택해도 되나요?','6점을 각각 묶으면 W=0입니다. 목적값 감소만으로 유용한 묶음을 정할 수 없습니다.'),('덴드로그램의 가로 간격은 거리인가요?','아닙니다. 병합 수준은 세로축에서 읽고 연결 기준도 함께 확인합니다.'),('군집 번호 2는 번호 1보다 우수한 집단인가요?','번호는 임의의 라벨입니다. 군집의 특성은 실제 변수 요약과 분포로 설명해야 합니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','미리 정한 집단과 발견한 군집을 구별합니다','<p>행정구역·용도별 통계표는 기준이 미리 정해진 집단 요약이며 자동 군집 결과와 다릅니다. 군집 결과를 접하면 포함 변수·거리·척도·알고리즘·군집 수와 각 군집의 표본 수를 먼저 확인하세요. 이 장은 서비스의 실제 군집 기능을 전제하지 않는 학습 예제입니다.</p><p>대표 중심과 함께 분포·겹침·이상치를 읽어야 합니다. 군집 이름은 관측된 특성을 요약하는 설명으로 사용하고 개별 적정가격·투자 우열을 뜻하는 이름은 붙이지 않습니다.</p>')
 sec('recap','학습 요약','묶음은 변수·거리·분석 방법을 선택한 결과입니다','<ul class="learn-recap-list"><li><strong>군집분석</strong>은 정답 라벨 없이 유사한 관측의 묶음을 찾습니다. 군집 번호는 순서나 우열이 아닙니다.</li><li><strong>K평균</strong>은 가까운 중심에 배정하고 평균으로 중심을 갱신해 군집 내 제곱거리 합을 줄입니다.</li><li>K를 늘리면 목적값을 줄일 수 있으므로 작은 W만으로 군집 수를 고르지 않습니다.</li><li><strong>실루엣</strong>은 같은 군집의 응집과 다른 군집과의 분리를 봅니다. 덴드로그램의 세로축은 연결 기준에 따른 병합 수준입니다.</li><li>변수·스케일·초기값·표본에 대한 안정성을 확인하고, 찾은 묶음을 확정된 유형이나 인과관계로 해석하지 않습니다.</li></ul><p>다음 <a href="/learn/stats/reading-results/">32장 「통계 결과를 읽고 판단하는 법」</a>에서 학습한 내용을 연결해 결과를 읽는 과정을 정리합니다.</p><details class="learn-references"><summary>참고자료와 예제 데이터</summary><ul><li><a href="https://scikit-learn.org/stable/modules/clustering.html">scikit-learn: Clustering — 알고리즘과 평가 지표</a></li><li><a href="../clustering-example.json">가상 관측·중심·목적값·실루엣·병합 자료</a></li></ul><p class="learn-source-note">그림과 수치는 별도 가상 자료로 직접 작성했습니다. 참고자료 기존 확인일: 2026-10-09.</p></details>')
 p=ROOT/'clustering/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="군집분석">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1K-means, 군집 수와 실루엣, 계층적 군집과 덴드로그램을 예제로 학습합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
