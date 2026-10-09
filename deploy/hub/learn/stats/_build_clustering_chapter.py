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
 d=dict(description='실제 거래가 아닌 무단위 가상 6점. 모든 관측점 조합을 초기 중심으로 반복한 결과 중 최소 목적값.',points=points,models=models,silhouette=sil,hierarchy=dict(x=[1,2,6,9],linkage='complete',merges=[[0,1,1,2],[2,3,3,2],[4,5,8,4]]))
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
 sec('purpose','군집과 분류','정답 범주 없이 관측을 묶습니다','<p>군집분석은 선택한 변수와 유사성 기준으로 관측을 묶는 비지도학습입니다. 28장의 분류는 이미 주어진 라벨을 예측하지만, 군집은 묶음 자체를 자료에서 찾습니다. 군집 번호 0·1·2는 이름표일 뿐 크기나 우열의 순서가 아닙니다.</p><p>부동산 자료에서 면적·층·노후도 등으로 관측을 묶을 수 있습니다. 다만 입력을 무엇으로 정하는지에 따라 “비슷함”의 뜻이 달라집니다. 행정구역이나 용도처럼 미리 정한 집단과 알고리즘으로 얻은 군집도 구별해야 합니다.</p>')
 sec('kmeans','K-means의 원리','가까운 중심에 배정하고 중심을 평균으로 갱신합니다','<p>K-means는 군집 수 K를 정한 뒤 W=ΣₖΣᵢ∈Cₖ‖xᵢ−μₖ‖²를 줄입니다. Cₖ는 군집, μₖ는 그 군집의 평균 벡터입니다. 목적값 W는 inertia 또는 군집 내 제곱합이라고 부릅니다.</p>'+g1+'<ol><li>초기 중심 K개를 정합니다.</li><li>각 관측을 가장 가까운 중심에 배정합니다.</li><li>배정된 관측의 평균으로 각 중심을 옮깁니다.</li><li>배정이나 중심이 충분히 안정될 때까지 반복합니다.</li></ol><p>이 예제는 A=(1,1), B=(1,2), C=(2,1), D=(7,7), E=(7,8), F=(8,7)입니다. 첫 세 점의 평균은 (4/3,4/3), 뒤 세 점은 (22/3,22/3)이고 W=8/3≈2.67입니다. 중심은 실제 관측 중 하나일 필요가 없습니다.</p><p>배정과 평균 갱신은 목적값을 증가시키지 않지만 전역 최적해를 보장하지 않습니다. 초기값을 바꾸어 반복하고 K-means++ 같은 초기화 방식을 검토합니다. 같은 거리의 동점과 빈 군집 처리 규칙도 재현에 영향을 줍니다. 이 예제는 앞 번호 중심을 동점에서 우선하고 빈 군집이 생긴 초기화는 제외했습니다.</p>')
 sec('scale','변수·거리·표준화','무엇을 비슷하다고 볼지 먼저 정합니다','<p>표준 K-means는 수치형 공간의 제곱 유클리드 거리를 사용합니다. 면적과 층을 원 숫자로 넣으면 변동 폭이 큰 변수가 목적값을 지배할 수 있습니다. 29장에서 배운 표준화는 각 변수를 표준편차 단위로 바꾸지만 모든 변수에 같은 중요도를 주는 것이 적절한지는 별도로 판단해야 합니다.</p><p>단가로 군집을 만든 뒤 군집 간 단가 차이를 발견했다고 하면, 입력에 넣은 차이를 다시 확인하는 셈입니다. 어떤 속성으로 묶고 어떤 속성으로 해석할지 기록하세요. 범주를 임의의 숫자로 바꾸면 잘못된 거리와 평균이 생길 수 있으므로 혼합 자료에 맞는 거리·알고리즘이 필요합니다.</p><p>이상치·중복·결측과 변수 간 강한 상관도 결과에 영향을 줍니다. 새 자료에 적용하거나 평가 자료를 분리한다면 스케일·대체값·차원축소는 학습 부분에서 추정하고 고정합니다. 위도·경도는 도 단위이며 지리적 거리와 속성 거리는 같은 개념이 아닙니다.</p>')
 sec('number','군집 수 선택','작은 목적값만으로 K를 고를 수 없습니다',g2+'<p>전역 최소 W는 K를 늘려도 커지지 않습니다. 모든 관측을 각각 군집으로 두면 W=0이므로 가장 작은 W만 고르면 과도하게 잘게 나눕니다. 실제 반복 알고리즘의 결과가 단조롭지 않다면 초기화나 수렴도 점검해야 합니다.</p><p>엘보 방법은 W의 감소가 완만해지는 지점을 찾지만 판단이 모호하거나 꺾임이 없을 수 있습니다. 실루엣·표본 재추출 안정성·군집 크기·설명 가능성과 사용 목적을 함께 보세요. 자료에 반드시 “정답 K”가 존재한다고 가정하지 않습니다.</p>')
 sec('silhouette','실루엣','응집도와 다른 군집과의 분리를 함께 봅니다','<p>관측 i에 대해 a(i)는 같은 군집의 다른 관측까지 평균 거리이고, b(i)는 다른 군집 각각에 대한 평균 거리 중 가장 작은 값입니다. s(i)=[b(i)−a(i)]/max[a(i),b(i)]로 계산합니다. K-means의 W와 달리 여기서는 제곱하지 않은 유클리드 거리를 씁니다.</p>'+g3+'<p>1에 가까우면 자기 군집에 더 가깝고, 0 근처면 경계에 있으며, 음수면 다른 군집에 더 가까울 수 있습니다. 단독 관측 군집의 실루엣은 보통 0으로 처리합니다. 전체 지표는 보통 2≤군집 수≤n−1인 경우 계산합니다.</p><p>평균 하나만 보지 말고 음수 관측과 작은 군집도 살펴야 합니다. 높은 실루엣은 선택한 거리에서 잘 분리되었다는 뜻이지 실제 시장의 독립 유형임을 증명하지 않습니다. 길게 휘어진 군집이나 밀도가 다른 자료에는 지표의 선호가 맞지 않을 수 있습니다.</p>')
 sec('hierarchy','계층적 군집','가까운 묶음부터 차례로 합칩니다','<p>응집형 계층적 군집은 각 관측을 하나의 군집으로 시작해 가까운 두 군집을 반복해서 합칩니다. 어느 군집끼리 가까운지 정하는 연결 기준이 결과를 바꿉니다.</p><ul><li>단일연결: 두 군집 사이 가장 가까운 관측 쌍의 거리. 연결 고리처럼 길게 이어질 수 있습니다.</li><li>완전연결: 가장 먼 관측 쌍의 거리. 군집 전체의 최대 간격을 고려합니다.</li><li>평균연결: 두 군집 사이 모든 관측 쌍 거리의 평균.</li><li>Ward: 합칠 때 증가하는 군집 내 제곱합을 최소화합니다. 유클리드 공간의 분산 기준입니다.</li></ul>'+g4+'<p>덴드로그램의 세로축은 병합 수준입니다. 연결 기준·구현에 따라 높이의 정의가 달라지므로 특히 Ward 높이를 원래의 두 점 거리처럼 읽지 마세요. 가로 순서는 가지를 뒤집으면 바뀌며 간격 자체에는 거리 의미가 없습니다.</p><p>높이 6에서 가로로 자르면 이 예제는 {1,2}와 {6,9}의 두 군집입니다. 한번 합친 군집을 뒤 단계에서 다시 분리하지 않으므로 초기 병합의 영향이 남습니다. 관측이 많으면 거리 계산과 덴드로그램 표시 비용도 커집니다.</p>')
 sec('alternatives','다른 모양의 군집','알고리즘의 가정과 자료 형태를 맞춥니다','<p>K-means는 중심 주변에 모인 군집에 잘 맞지만 크기·밀도가 크게 다르거나 휘어진 모양에는 부적절할 수 있습니다. K-medoids는 실제 관측을 대표점으로 삼고, 밀도 기반 DBSCAN은 이웃 반경과 최소 관측 수로 연결된 밀집 영역을 찾으며 일부 점을 잡음으로 남길 수 있습니다.</p><p>DBSCAN도 반경·밀도 설정에 민감하고 잡음 판정이 곧 데이터 오류는 아닙니다. 가우시안 혼합모형은 확률적으로 소속을 표현하는 다른 접근입니다. 이 장의 K-means 결과를 모든 군집 방법의 결과로 일반화하지 않습니다.</p>')
 sec('validation','안정성과 활용','다시 뽑아도 비슷한 묶음인지 확인합니다','<p>초기값, 표본 재추출, 변수 구성, 표준화 방식과 K를 바꿔 결과가 유지되는지 살펴봅니다. 군집 번호는 실행마다 바뀔 수 있으므로 번호 일치율을 그대로 비교하지 말고 같은 관측 쌍이 함께 묶이는지 또는 라벨 순서에 무관한 지표로 비교합니다.</p><p>새 관측은 고정한 K-means 중심 중 가까운 곳에 배정할 수 있지만, 기존 모든 중심에서 매우 멀면 적용 범위를 점검해야 합니다. 계층적 군집은 기본적으로 새 관측 배정 규칙을 제공하지 않으므로 재학습이나 별도 규칙이 필요합니다.</p><p>군집 생성에 쓴 변수로 사후 검정을 반복하면 선택 효과를 무시할 수 있습니다. 군집 간 차이의 탐색과 독립 자료에서 미리 정한 가설을 검증하는 일을 구별하세요. 군집은 인과적 처치 집단이나 확정된 시장 경계를 뜻하지 않습니다.</p>')
 sec('practice','확인 문제','묶음의 기준과 해석을 확인하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('A·B·C의 중심은 실제 관측인가요?','평균 (4/3,4/3)은 세 관측 중 어느 것과도 같지 않습니다.'),('W가 가장 작다는 이유로 K=6을 선택해도 되나요?','6점을 각각 묶으면 W=0입니다. 목적값 감소만으로 유용한 묶음을 정할 수 없습니다.'),('덴드로그램의 가로 간격은 거리인가요?','아닙니다. 병합 수준은 세로축에서 읽고 연결 기준도 함께 확인합니다.'),('군집 번호 2는 번호 1보다 우수한 집단인가요?','번호는 임의의 라벨입니다. 군집의 특성은 실제 변수 요약과 분포로 설명해야 합니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','미리 정한 집단과 발견한 군집을 구별합니다','<p>행정구역·용도별 통계표는 기준이 미리 정해진 집단 요약이며 자동 군집 결과와 다릅니다. 군집 결과를 접하면 포함 변수·거리·척도·알고리즘·군집 수와 각 군집의 표본 수를 먼저 확인하세요. 이 장은 서비스의 실제 군집 기능을 전제하지 않는 학습 예제입니다.</p><p>대표 중심과 함께 분포·겹침·이상치를 읽어야 합니다. 군집 이름은 관측된 특성을 요약하는 설명으로 사용하고 개별 적정가격·투자 우열을 뜻하는 이름은 붙이지 않습니다.</p>')
 sec('recap','정리와 참고자료','묶음은 자료와 분석 선택의 결과입니다','<p>군집분석은 선택한 변수와 거리에서 구조를 탐색합니다. K-means의 중심·목적값, 실루엣, 계층적 병합 높이는 서로 다른 질문에 답하므로 함께 해석하세요. 다음 <a href="/learn/stats/reading-results/">32장 「통계 결과를 읽고 판단하는 법」</a>에서 과정 전체를 정리합니다.</p><ul><li><a href="https://scikit-learn.org/stable/modules/clustering.html">scikit-learn: Clustering — 알고리즘과 평가 지표 참고</a></li><li><a href="../clustering-example.json">가상 관측·중심·목적값·실루엣·병합 자료</a></li></ul><p class="learn-source-note">그림과 수치는 별도 가상 자료로 직접 작성했습니다. 실제 거래 자료가 아닙니다. 참고자료 확인: 2026-10-09.</p>')
 p=ROOT/'clustering/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="군집분석">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1K-means, 군집 수와 실루엣, 계층적 군집과 덴드로그램을 예제로 학습합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
