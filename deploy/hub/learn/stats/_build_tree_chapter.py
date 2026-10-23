"""Reproducible chapter 30 regression splits and classification impurity."""
from pathlib import Path
from statistics import mean
from html import escape
import json,re
ROOT=Path(__file__).resolve().parent

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];train=rows[:20];test=rows[20:]
 def sse(rr):return sum((r['price']-mean(v['price'] for v in rr))**2 for r in rr)
 def candidates(rr):
  xx=sorted(set(r['area'] for r in rr));out=[]
  for a,b in zip(xx,xx[1:]):
   t=(a+b)/2;l=[r for r in rr if r['area']<=t];h=[r for r in rr if r['area']>t];out.append(dict(threshold=t,sse=sse(l)+sse(h)))
  return out
 cand=candidates(train);t1=min(cand,key=lambda r:r['sse'])['threshold'];right=[r for r in train if r['area']>t1];t2=min(candidates(right),key=lambda r:r['sse'])['threshold']
 groups=[[r for r in train if r['area']<=t1],[r for r in train if t1<r['area']<=t2],[r for r in train if r['area']>t2]];av=[mean(r['price'] for r in g) for g in groups]
 def pred(r):return av[0 if r['area']<=t1 else 1 if r['area']<=t2 else 2]
 metrics={name:mean(abs(r['price']-pred(r)) for r in rr) for name,rr in [('train_mae',train),('test_mae',test)]}
 risks=[dict(leaves=1,risk=sse(train)/20),dict(leaves=2,risk=min(v['sse'] for v in cand)/20),dict(leaves=3,risk=sum(sse(g) for g in groups)/20)]
 d=dict(source='공통 30건: 출처 미확인 학습 예시. 번호 1~20 학습, 21~30 확인.',thresholds=[t1,t2],candidates=cand,leaves=[dict(ids=[r['id'] for r in g],mean=m) for g,m in zip(groups,av)],metrics=metrics,risks=risks,classification=dict(parent=[4,4],left=[3,1],right=[1,3],parent_gini=.5,weighted_gini=.375,gain=.125))
 (ROOT/'decision-tree-example.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def ln(x,y,a,b,c='#94a3b8'):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="{c}"/>'
 def fig(id,title,b,cap):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 410" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 def box(x,y,w,title,sub):return f'<rect x="{x}" y="{y}" width="{w}" height="65" rx="6" fill="#eaf2ff"/>'+tx(x+12,y+25,title)+tx(x+12,y+50,sub)
 b=tx(24,28,'공통 학습 20건: 질문을 따라 잎에 도착합니다')+ln(320,120,135,185)+ln(320,120,420,185)+ln(420,250,330,315)+ln(420,250,530,315)
 b+=box(205,55,230,f'X ≤ {t1:g}?', '루트: 학습 20건')+box(35,185,200,'예 → 잎 1',f'1건 · 예측 {av[0]:.1f}')+box(305,185,230,f'아니요 → X ≤ {t2:g}?', '남은 학습 19건')+box(230,315,180,'예 → 잎 2',f'7건 · 예측 {av[1]:.1f}')+box(430,315,180,'아니요 → 잎 3',f'12건 · 예측 {av[2]:.1f}')
 g1=fig('path','회귀나무의 분기와 잎',b,'그림 1. X·Y는 단위 없는 변수입니다. 제곱오차 기준으로 첫 분할을 찾은 뒤 오른쪽 자식만 한 번 더 분할한 설명용 3잎 나무입니다. 모든 자식을 깊이 2까지 자란 나무와는 구별합니다.')
 b=tx(24,28,'첫 분할 후보마다 양쪽 잎의 오차 제곱합을 비교')+ln(65,325,590,325)+ln(65,65,65,325)
 pts=[(65+r['threshold']*1.7,325-r['sse']/700) for r in cand]
 b+='<polyline points="'+' '.join(f'{a},{v}' for a,v in pts)+'" fill="none" stroke="#2563eb" stroke-width="2"/>'
 for r,(a,v) in zip(cand,pts):b+=f'<circle cx="{a}" cy="{v}" r="4" fill="'+('#d97706' if r['threshold']==t1 else '#2563eb')+'"/>'
 for v in [0,100,200,300]:b+=tx(60+v*1.7,350,v)
 for v in [0,70000,140000]:b+=tx(8,330-v/700,f'{v/1000:g}k')
 b+=tx(95,70,f'최소 후보: {t1:g} · SSE {min(v["sse"] for v in cand):,.1f}')+tx(24,390,'가로: X의 경계 / 세로: SSE · k는 1,000')
 g2=fig('split','회귀 분할 기준',b,'그림 2. 서로 다른 학습 X 사이의 중점을 후보로 계산했습니다. 점이 실제 후보이며 연결선은 읽기를 돕습니다. 확인 10건은 경계 선택에 쓰지 않았습니다.')
 b=tx(24,28,'세 잎의 평균은 구간마다 일정한 예측이 됩니다')+ln(65,325,590,325)+ln(65,55,65,325)
 for a,z,v in [(0,t1,av[0]),(t1,t2,av[1]),(t2,310,av[2])]:b+=ln(65+a*1.65,325-v*.5,65+z*1.65,325-v*.5,'#d97706')
 for r in train:b+=f'<circle cx="{65+r["area"]*1.65}" cy="{325-r["price"]*.5}" r="4" fill="#2563eb"/>'
 for v in [0,100,200,300]:b+=tx(60+v*1.65,350,v)
 for v in [0,200,400]:b+=tx(20,330-v*.5,v)
 b+=tx(24,390,'가로: X / 세로: Y · 파랑 학습 / 주황 예측')
 g3=fig('prediction','구간별 평균 예측',b,'그림 3. 경계에서는 ≤인 왼쪽 잎을 선택합니다. X가 31 이하의 예측 480은 단 한 건에 의존하며, 자료 범위 밖에서도 해당 끝 잎의 값만 출력합니다.')
 b=tx(24,28,'별도 가상 분류 8건: 분할 뒤 혼합 정도 비교')+box(190,65,260,'부모: 양성 4 · 음성 4','Gini = 0.5')+ln(320,130,165,210)+ln(320,130,475,210)+box(35,210,270,'왼쪽: 양성 3 · 음성 1','Gini = 0.375 · 양성 비율 0.75')+box(335,210,270,'오른쪽: 양성 1 · 음성 3','Gini = 0.375 · 양성 비율 0.25')+tx(65,335,'가중 불순도 = (4/8)×0.375 + (4/8)×0.375 = 0.375')+tx(65,380,'불순도 감소 = 0.5 − 0.375 = 0.125')
 g4=fig('classification','분류나무의 지니 불순도',b,'그림 4. 분류 계산만 설명하는 별도 가상 자료입니다. 회귀 예제의 Y를 이진 라벨로 바꾼 결과가 아닙니다. 잎의 비율이 보정된 실제 확률임을 보장하지 않습니다.')
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','학습 목표','조건을 하나씩 따라가면 예측이 나옵니다','<p>‘학습 시간이 이 값 이하인가?’, ‘연습 횟수가 이 값보다 많은가?’처럼 질문을 이어 가며 대상을 나눌 수 있습니다. 의사결정나무는 이런 조건을 자료에서 찾고, 마지막에 도착한 집단의 정보를 이용해 예측하는 방법입니다.</p><p>이 장에서는 나무가 질문을 고르는 과정과 잎에서 예측하는 방식을 살펴봅니다. 회귀와 분류의 분할 기준을 비교하고, 나무를 너무 잘게 나누지 않도록 복잡도를 조절하는 이유도 알아봅니다.</p><ul class="learn-objectives"><li>루트·분기·잎의 역할을 설명하고 조건에 따라 예측을 찾습니다.</li><li>회귀의 제곱오차와 분류의 지니 불순도로 분할을 비교합니다.</li><li>깊이·잎 크기·가지치기로 복잡도를 조절하는 이유를 이해합니다.</li><li>검증과 해석에서 소수 표본·불안정성·인과관계의 한계를 구별합니다.</li></ul>')
 sec('path','핵심 이해','질문을 따라 내려가 마지막 잎에서 예측합니다','<p><strong>의사결정나무</strong>는 입력에 대한 질문을 반복해 자료를 나누는 지도학습 방법입니다. 맨 위의 시작점이 <strong>루트</strong>, 질문으로 갈라지는 곳이 <strong>분기 노드</strong>, 더 나누지 않는 끝이 <strong>잎</strong>입니다. 새 관측은 학습 때 정한 조건을 따라 하나의 잎에 도착합니다.</p>'+g1+'<p>그림에서는 먼저 X가 31 이하인지 묻습니다. 그렇다면 잎 1로 갑니다. 아니라면 X가 80 이하인지 한 번 더 물어 잎 2와 잎 3으로 나눕니다. 수치형 Y를 예측하는 회귀나무이며 각 잎의 학습 Y 평균을 예측값으로 씁니다.</p><p>예제는 공통 학습 자료의 두 수치 열을 단위 없는 X와 Y로 놓고, 1~20번으로 학습한 뒤 21~30번에서 확인합니다. 번호는 시간 순서가 아니며 원자료는 출처가 확인되지 않은 학습용 자료입니다.</p><p>이 장은 한 변수의 경계값으로 두 갈래씩 나누는 CART 방식의 기본 원리를 다룹니다. 변수가 여러 개이면 앞선 답에 따라 다음에 물을 변수가 달라질 수 있어 상호작용도 표현할 수 있습니다.</p>')
 sec('split','회귀 분할 기준','양쪽 잎의 제곱오차 합이 작아지는 경계를 찾습니다','<p>후보 경계마다 자료를 왼쪽과 오른쪽으로 나눕니다. 각 쪽의 Y 평균을 예측값으로 놓고, 실제 Y와의 차이를 제곱해 모두 더합니다. 허용된 후보 중 이 <strong>잔차제곱합(SSE)</strong>이 가장 작은 경계를 고릅니다.</p>'+g2+'<p>그림의 주황 점이 선택한 첫 경계 X=31입니다. 후보는 서로 다른 학습 X 사이의 중점으로 정했습니다. 확인 자료 10개는 경계를 고르는 데 쓰지 않았습니다.</p><p>이 선택은 현재 노드에서 가장 유리한 분할을 찾는 <strong>탐욕적 선택</strong>입니다. 가능한 모든 나무를 비교해 전체 최적의 나무를 찾았다는 뜻은 아닙니다. 잎에 최소 몇 개의 관측이 있어야 한다는 제한을 두면 허용되는 경계도 달라집니다.</p><details><summary>제곱오차와 가중 불순도의 관계</summary><p>SSE(s)=ΣL(yᵢ−ȳL)²+ΣR(yᵢ−ȳR)²입니다. 이를 자식 노드의 MSE로 비교하려면 각각 nL/n과 nR/n을 곱해야 같은 기준이 됩니다. 두 MSE를 단순히 더하면 작은 집단과 큰 집단을 같은 비중으로 취급하게 됩니다. 잎의 평균이 제곱오차를 최소화하는 성질은 25장과 연결됩니다.</p></details>')
 sec('prediction','회귀 예측과 오차','같은 잎에 들어가면 같은 평균을 예측합니다',g3+f'<p>X가 31 초과 80 이하인 7개 관측의 Y 평균은 {av[1]:.2f}, 80 초과인 12개의 평균은 {av[2]:.2f}입니다. X=60과 X=75는 같은 잎에 들어가므로 같은 값을 예측합니다. 실제 관계가 경계에서 갑자기 뛴다는 뜻이 아니라 모형이 구간별로 일정하게 예측한다는 뜻입니다.</p><p>특히 X가 31 이하인 잎은 관측 하나에만 의존합니다. 그 관측에서 정확하게 맞더라도 새 자료에서 안정적이라고 판단하기는 어렵습니다.</p><p>이 나무의 학습 MAE는 {metrics["train_mae"]:.2f}, 확인 MAE는 {metrics["test_mae"]:.2f}로 Y와 같은 단위입니다. 같은 분할의 직선 회귀 확인 MAE 약 41.08과 비교할 수 있지만 작은 분할 한 번으로 우열을 일반화할 수는 없습니다. 확인 결과를 보고 반복해서 후보를 고르면 그 자료는 최종 시험 역할을 하지 못합니다.</p><p>입력이 학습 범위를 벗어나도 나무는 끝 잎의 평균을 출력합니다. 직선처럼 추세를 연장하는 것은 아니므로 출력이 나온다는 사실만으로 외삽을 신뢰해서는 안 됩니다.</p>')
 sec('classification','분류의 불순도','한 범주끼리 모이도록 나눕니다','<p>분류나무는 수치의 차이 대신 범주가 얼마나 섞였는지 살펴봅니다. <strong>지니 불순도</strong>는 G=1−Σpₖ²로, pₖ는 노드 안에서 범주 k의 비율입니다. 한 범주만 있으면 0이고, 두 범주가 반반이면 0.5입니다.</p>'+g4+'<p>부모의 양성·음성이 4:4이면 G=0.5입니다. 두 자식이 각각 3:1과 1:3으로 나뉘면 각 G는 0.375입니다. 관측 수로 가중한 자식 불순도도 0.375이므로 감소량은 0.125입니다. 다른 후보들과 이런 감소량을 비교합니다.</p><p>분류나무는 보통 잎에서 가장 많은 범주를 예측하고 범주별 비율을 확률형 점수로 냅니다. 가중치를 쓰면 비율도 가중해 계산합니다. 작은 잎의 비율이 잘 보정된 확률이라는 보장은 없으며, 불균형 자료에서는 28장의 정밀도·재현율과 오류 비용도 살펴야 합니다.</p><details><summary>다른 분할 기준: 엔트로피</summary><p>엔트로피 H=−Σpₖ log pₖ도 범주의 혼합 정도를 나타냅니다. 0 log 0은 0으로 정의합니다. 로그의 밑은 단위를 바꾸지만 같은 기준에서 후보의 순서는 바꾸지 않습니다. 회귀의 제곱오차와 분류의 불순도는 목표 유형에 맞춰 구별합니다.</p></details>')
 sec('pruning','복잡도와 가지치기','질문을 늘리는 데도 제한이 필요합니다','<p>나무를 깊게 만들면 학습 자료를 세밀하게 나눌 수 있지만 우연한 흔들림까지 따라갈 수 있습니다. 최대 깊이, 분할에 필요한 최소 관측 수, 잎의 최소 관측 수, 최대 잎 수로 복잡도를 제한할 수 있습니다. 한 관측만 있는 잎의 완벽한 적합은 새 자료의 정확성을 보장하지 않습니다.</p><p><strong>가지치기</strong>는 먼저 자란 나무에서 일부 가지를 줄이는 방법입니다. 비용복잡도 가지치기는 학습 손실과 잎 수의 비용을 더해 비교합니다. 잎 수의 비용을 높이면 더 단순한 나무가 유리해질 수 있습니다.</p><details><summary>비용복잡도 산식과 예제</summary><p>Rα(T)=R(T)+α|T|에서 |T|는 잎 수입니다. 이 장에서는 R(T)를 전체 학습 SSE/n으로 정하므로 α의 단위도 Y의 제곱입니다. 손실의 정규화가 다르면 α의 숫자도 달라집니다.</p>'+f'<p>예제의 1·2·3잎 나무에서 R은 각각 {risks[0]["risk"]:.2f}·{risks[1]["risk"]:.2f}·{risks[2]["risk"]:.2f}입니다. 학습 손실만 보면 세 잎이 유리하지만 α가 커지면 추가 잎의 비용도 커집니다. 이는 이 세 후보를 설명한 계산으로 전체 가지치기 경로를 구한 것은 아닙니다.</p>'+'<p>이진 나무는 깊이를 한 단계 늘릴 때 잎 수가 최대 두 배가 될 수 있습니다. 실제 잎 수는 자료와 분할 제한에 따라 달라집니다.</p></details><p>깊이·잎 크기·α는 목적에 맞는 교차검증으로 고릅니다. 새로운 학교나 미래 시점에 적용하려면 집단·시간 구조를 반영해 나누고 매 폴드에서 전처리와 학습을 다시 수행합니다. 시험 자료는 선택을 마친 뒤 평가에 사용합니다.</p>')
 sec('features','변수와 전처리','거리보다 값의 순서와 분할 방식이 중요합니다','<p>학습 시간을 분에서 시간으로 바꾸어도 값의 순서는 같습니다. 수치형 변수의 순서로 나누는 나무에서는 같은 학습 관측끼리 분할할 수 있습니다. 따라서 29장의 거리 기반 KNN과 달리 일반적으로 표준화가 필수는 아닙니다. 다만 반올림이나 수치 정밀도, 근사 분할은 결과에 영향을 줄 수 있습니다.</p><p>범주에 임의의 번호를 붙이면 원래 없던 순서로 나눌 수 있습니다. 원핫 인코딩이나 범주 분할을 지원하는 구현을 검토합니다. 결측값을 자동 처리하는지도 구현에 따라 다르므로 대체 규칙이나 결측 분기 방식을 확인해야 합니다.</p>')
 sec('interpretation','안정성과 해석','읽기 쉬운 조건도 보편적인 법칙은 아닙니다','<p>학습 자료를 조금 바꾸면 첫 질문부터 달라지고 뒤의 나무도 크게 달라질 수 있습니다. 예제의 경계 X=31은 이 자료에서 고른 값으로, 모든 자료에 적용되는 기준은 아닙니다.</p><p>불순도 감소를 모은 변수 중요도는 분할 후보가 많은 변수에 유리할 수 있고 비슷한 정보를 가진 변수들 사이에 중요도가 나뉠 수도 있습니다. 별도 평가 자료에서 한 변수를 섞어 성능 변화를 보는 순열 중요도 역시 변수 간 상관과 평가 설계의 영향을 받습니다. 중요도가 높다는 사실은 인과관계를 뜻하지 않습니다.</p><p>랜덤 포레스트는 여러 나무의 결과를 모으고, 부스팅은 손실을 줄이는 방향으로 나무를 순차적으로 더합니다. 단일 나무의 한계를 보완하는 확장 방법입니다. 이 장의 계산은 이런 앙상블의 성능을 평가한 결과는 아닙니다.</p>')
 sec('practice','확인 문제','분할 기준과 예측을 직접 확인하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('X=75의 예측은 어느 잎에서 나오나요?',f'31 초과 80 이하의 두 번째 잎입니다. 예측은 학습 7개 관측의 Y 평균 {av[1]:.2f}입니다.'),('자식 노드의 불순도를 왜 가중하나요?','자식마다 관측 수가 다르므로 전체 관측에 대한 평균 손실로 비교하기 위해서입니다.'),('양성과 음성이 3:1이면 지니 불순도는?','1−(3/4)²−(1/4)²=0.375입니다.'),('학습 오차가 가장 작은 깊이를 바로 채택해도 될까요?','과적합할 수 있습니다. 목적에 맞는 검증 분할에서 복잡도를 선택하고 최종 시험은 분리합니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','모형의 종류와 적용 범위를 먼저 확인합니다','<p>회귀계수로 표현된 식과 구간별 잎 평균은 다른 예측 규칙입니다. 결과를 읽을 때 학습 변수·기간·잎의 관측 수·검증 오차를 함께 확인하세요. 여기의 나무가 CH2 Macro의 실제 서비스 알고리즘이라고 전제하지 않습니다.</p><p>학습 예제의 잎 평균은 개별 적정가격이나 인과효과를 뜻하지 않습니다. 소수 표본과 조건 차이를 고려해 집단 통계와 모형의 의미를 이해하는 데 사용합니다.</p>')
 sec('recap','학습 요약','조건을 고르는 과정과 잎의 근거를 함께 봅니다','<ul class="learn-recap-list"><li><strong>의사결정나무</strong>는 입력 조건으로 자료를 나누고 마지막 잎에서 예측합니다.</li><li>제곱오차 회귀나무는 잎의 학습 Y 평균을 사용합니다. 분할은 양쪽 잎의 SSE가 작아지도록 고릅니다.</li><li>분류나무는 지니 불순도 등 범주의 혼합 정도를 비교하고 관측 수로 자식 노드를 가중합니다.</li><li>깊이·최소 잎 크기·가지치기로 복잡도를 조절하고 검증으로 선택합니다.</li><li>작은 잎과 경계의 불안정성을 살핍니다. 읽기 쉬운 조건이나 높은 변수 중요도가 인과관계를 뜻하지는 않습니다.</li></ul><p>다음 <a href="/learn/stats/clustering/">31장 「군집분석」</a>에서는 목표값 없이 관측을 묶는 방법을 배웁니다.</p><details class="learn-references"><summary>참고자료와 예제 데이터</summary><ul><li><a href="https://scikit-learn.org/stable/modules/tree.html">scikit-learn: Decision Trees — 분할 기준과 가지치기</a></li><li><a href="../decision-tree-example.json">분할 후보·잎·오차 재현 자료</a></li></ul><p class="learn-source-note">그림과 계산은 공통 학습 자료 및 별도 가상 분류 예제로 직접 작성했습니다. 참고자료 기존 확인일: 2026-10-09.</p></details>')
 p=ROOT/'decision-tree/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="의사결정나무">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1의사결정나무의 분할·잎 예측, 회귀와 분류의 손실, 가지치기와 검증 방법을 학습합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
