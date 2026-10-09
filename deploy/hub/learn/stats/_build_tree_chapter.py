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
 b+=box(205,55,230,f'면적 ≤ {t1:g}㎡?', '루트: 학습 20건')+box(35,185,200,'예 → 잎 1',f'1건 · 예측 {av[0]:.1f}')+box(305,185,230,f'아니요 → 면적 ≤ {t2:g}㎡?', '남은 학습 19건')+box(230,315,180,'예 → 잎 2',f'7건 · 예측 {av[1]:.1f}')+box(430,315,180,'아니요 → 잎 3',f'12건 · 예측 {av[2]:.1f}')
 g1=fig('path','회귀나무의 분기와 잎',b,'그림 1. 단가는 만원/㎡입니다. 제곱오차 기준으로 첫 분할을 찾은 뒤 오른쪽 자식만 한 번 더 분할한 설명용 3잎 나무입니다. 모든 자식을 깊이 2까지 자란 나무와는 구별합니다.')
 b=tx(24,28,'첫 분할 후보마다 양쪽 잎의 오차 제곱합을 비교')+ln(65,325,590,325)+ln(65,65,65,325)
 pts=[(65+r['threshold']*1.7,325-r['sse']/700) for r in cand]
 b+='<polyline points="'+' '.join(f'{a},{v}' for a,v in pts)+'" fill="none" stroke="#2563eb" stroke-width="2"/>'
 for r,(a,v) in zip(cand,pts):b+=f'<circle cx="{a}" cy="{v}" r="4" fill="'+('#d97706' if r['threshold']==t1 else '#2563eb')+'"/>'
 for v in [0,100,200,300]:b+=tx(60+v*1.7,350,v)
 for v in [0,70000,140000]:b+=tx(8,330-v/700,f'{v/1000:g}k')
 b+=tx(95,70,f'최소 후보: {t1:g}㎡ · SSE {min(v["sse"] for v in cand):,.1f}')+tx(24,390,'가로: 면적 경계(㎡) / 세로: SSE · k는 1,000')
 g2=fig('split','회귀 분할 기준',b,'그림 2. 서로 다른 학습 면적 사이의 중점을 후보로 계산했습니다. 점이 실제 후보이며 연결선은 읽기를 돕습니다. 확인 10건은 경계 선택에 쓰지 않았습니다.')
 b=tx(24,28,'세 잎의 평균은 구간마다 일정한 예측이 됩니다')+ln(65,325,590,325)+ln(65,55,65,325)
 for a,z,v in [(0,t1,av[0]),(t1,t2,av[1]),(t2,310,av[2])]:b+=ln(65+a*1.65,325-v*.5,65+z*1.65,325-v*.5,'#d97706')
 for r in train:b+=f'<circle cx="{65+r["area"]*1.65}" cy="{325-r["price"]*.5}" r="4" fill="#2563eb"/>'
 for v in [0,100,200,300]:b+=tx(60+v*1.65,350,v)
 for v in [0,200,400]:b+=tx(20,330-v*.5,v)
 b+=tx(24,390,'가로: 면적(㎡) / 세로: 단가(만원/㎡) · 파랑 학습 / 주황 예측')
 g3=fig('prediction','구간별 평균 예측',b,'그림 3. 경계에서는 ≤인 왼쪽 잎을 선택합니다. 31㎡ 이하의 예측 480은 단 한 건에 의존하며, 자료 범위 밖에서도 해당 끝 잎의 값만 출력합니다.')
 b=tx(24,28,'별도 가상 분류 8건: 분할 뒤 혼합 정도 비교')+box(190,65,260,'부모: 양성 4 · 음성 4','Gini = 0.5')+ln(320,130,165,210)+ln(320,130,475,210)+box(35,210,270,'왼쪽: 양성 3 · 음성 1','Gini = 0.375 · 양성 비율 0.75')+box(335,210,270,'오른쪽: 양성 1 · 음성 3','Gini = 0.375 · 양성 비율 0.25')+tx(65,335,'가중 불순도 = (4/8)×0.375 + (4/8)×0.375 = 0.375')+tx(65,380,'불순도 감소 = 0.5 − 0.375 = 0.125')
 g4=fig('classification','분류나무의 지니 불순도',b,'그림 4. 분류 계산만 설명하는 별도 가상 자료입니다. 회귀 예제의 단가를 이진 라벨로 바꾼 결과가 아닙니다. 잎의 비율이 보정된 실제 확률임을 보장하지 않습니다.')
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('path','나무의 구조','질문을 따라 내려가고 잎에서 예측합니다','<p>의사결정나무는 입력 변수에 대한 질문을 반복해 관측을 여러 영역으로 나누는 지도학습 방법입니다. 맨 위는 루트, 질문이 있는 곳은 분기 노드, 더 나누지 않는 끝은 잎입니다. 새 관측은 학습 때 정한 규칙을 따라 하나의 잎에 도착합니다.</p>'+g1+'<p>이 장은 한 변수씩 임계값으로 둘로 나누는 CART 방식의 기본 원리를 다룹니다. 회귀에서는 수치형 목표를, 분류에서는 범주를 예측합니다. 여러 변수로 나누면 앞선 조건에 따라 다음 질문이 달라져 상호작용을 표현할 수 있습니다.</p><p>공통 30건의 번호 1~20을 학습, 21~30을 확인 자료로 사용합니다. 번호는 시간 순서가 아니며 실제 거래 출처도 확인되지 않은 학습 자료입니다.</p>')
 sec('split','회귀 분할 기준','각 잎 안의 오차 제곱합이 작아지는 경계를 찾습니다','<p>제곱오차 회귀나무의 잎 예측은 그 잎의 학습 목표 평균입니다. 후보 경계 s마다 왼쪽 L과 오른쪽 R을 만들고 SSE(s)=ΣL(yᵢ−ȳL)²+ΣR(yᵢ−ȳR)²를 계산합니다. 허용된 후보 중 가장 작은 값을 선택합니다.</p>'+g2+'<p>노드의 MSE로 표현하면 자식 불순도에 각각 nL/n과 nR/n을 곱해야 같은 기준이 됩니다. 두 자식의 MSE를 단순히 더하면 작은 집단과 큰 집단의 비중을 잘못 줄 수 있습니다. 평균이 제곱오차를 최소화하는 성질은 25장과 연결됩니다.</p><p>분할은 현재 노드에서의 탐욕적 선택입니다. 첫 질문을 고른 뒤 되돌아가 모든 나무를 비교하는 방법이 아니므로 전체 최적 나무를 보장하지 않습니다. 최소 잎 크기 등 제한이 있으면 후보 자체가 달라집니다.</p>')
 sec('prediction','회귀 예측과 오차','잎 안에서는 입력이 달라도 같은 평균을 받습니다',g3+f'<p>31㎡ 초과 80㎡ 이하 7건의 평균은 {av[1]:.2f}, 80㎡ 초과 12건의 평균은 {av[2]:.2f}만원/㎡입니다. 예를 들어 60㎡와 75㎡는 같은 잎에 들어가 같은 예측을 받습니다. 관측값이 경계에서 불연속적으로 뛰는 것이 아니라 모형의 예측 규칙이 계단 모양인 것입니다.</p><p>이 나무의 학습 MAE는 {metrics["train_mae"]:.2f}, 확인 MAE는 {metrics["test_mae"]:.2f}만원/㎡입니다. 같은 분할의 직선 회귀 확인 MAE 약 41.08과 비교할 수 있지만, 한 번의 작은 분할만으로 모형의 우열을 일반화할 수 없습니다. 반복해서 선택에 사용한 확인 자료는 최종 시험 자료가 아닙니다.</p><p>평균을 쓰는 잎은 해당 학습 목표의 범위를 벗어나 추세를 연장하지 않습니다. 관측 범위 밖에서도 출력이 나온다는 사실과 신뢰할 수 있는 외삽은 다릅니다.</p>')
 sec('classification','분류의 불순도','범주가 얼마나 섞였는지를 측정합니다','<p>범주 비율 pₖ에 대해 지니 불순도는 G=1−Σpₖ²입니다. 한 범주만 있으면 0이고 이진 범주가 반반이면 0.5입니다. 후보 분할은 부모 G에서 표본 수로 가중한 자식 G를 뺀 감소량으로 비교합니다.</p>'+g4+'<p>엔트로피 H=−Σpₖ log pₖ도 사용할 수 있으며 0 log 0은 0으로 정의합니다. 로그 밑은 단위를 바꾸고 같은 기준 내의 후보 순서는 바꾸지 않습니다. 회귀의 제곱오차와 분류의 불순도는 목표 유형에 맞춰 선택합니다.</p><p>균등 가중 분류나무는 잎의 범주 비율로 확률형 점수를 만들고 보통 최다 범주를 예측합니다. 표본·범주 가중치를 쓰면 가중 비율이 됩니다. 불균형 자료에서는 정확도만 보지 말고 28장의 재현율·정밀도·확률 품질과 오류 비용을 함께 확인합니다.</p>')
 sec('pruning','복잡도와 가지치기','잘게 나누는 능력에 제한을 둡니다','<p>깊이 제한, 최소 분할 표본 수, 최소 잎 표본 수, 최대 잎 수는 나무가 지나치게 세밀해지는 것을 막는 사전 제약입니다. 깊이를 하나 늘릴 때 잎 수는 최대 두 배가 될 수 있지만 실제 모양은 분할 가능 여부에 달려 있습니다. 한 건짜리 잎의 완벽한 적합은 새 자료에 대한 정확성의 증거가 아닙니다.</p><p>비용복잡도 가지치기는 먼저 자란 나무의 가지를 줄이며 Rα(T)=R(T)+α|T|를 비교합니다. |T|는 잎 수, R(T)는 학습 손실입니다. 여기서는 회귀의 전체 SSE/n을 R로 정의하므로 α의 단위도 목표값의 제곱입니다. 손실의 정규화 방식이 달라지면 α의 숫자도 달라집니다.</p>'+f'<p>이 예제에서 1·2·3잎의 R은 각각 {risks[0]["risk"]:.2f}·{risks[1]["risk"]:.2f}·{risks[2]["risk"]:.2f}입니다. 학습 손실 감소만 보면 세 잎이 유리하지만, α가 커지면 잎 수에 대한 비용이 커집니다. 이는 이 세 후보의 설명이며 전체 가지치기 경로를 계산한 결과는 아닙니다.</p>'+'<p>최대 깊이·최소 잎 수·α는 교차검증으로 선택합니다. 동일 단지나 미래 시점을 예측할 목적이라면 집단·시간 분할을 따르고, 전처리와 나무 학습을 폴드 안에서 다시 수행합니다. 시험 자료는 선택이 끝난 뒤에 평가합니다.</p>')
 sec('features','변수와 전처리','거리의 스케일보다는 순서와 표현 방식이 중요합니다','<p>수치형 변수의 순서로 분할하는 나무는 면적을 ㎡에서 다른 양의 비례 단위로 바꾸어도 후보 집단이 같습니다. 따라서 29장의 거리 기반 KNN과 달리 일반적으로 표준화가 필수는 아닙니다. 다만 반올림·수치 정밀도·근사 분할은 결과에 영향을 줄 수 있습니다.</p><p>범주형 변수에 임의의 번호를 붙이면 존재하지 않는 순서로 나눌 수 있습니다. 원핫 인코딩 또는 범주 분할을 지원하는 구현을 검토하세요. 결측값을 자동으로 처리하는지는 알고리즘·구현에 따라 다르므로 학습 자료에서 정한 대체 규칙이나 결측 분기 방식을 명시해야 합니다.</p>')
 sec('interpretation','안정성과 해석','읽기 쉬운 규칙도 인과 설명은 아닙니다','<p>표본이 조금 바뀌면 첫 분할과 이후 나무가 크게 달라질 수 있습니다. 분할 경계 31㎡를 시장의 보편적 기준으로 해석하지 마세요. 변수 중요도의 불순도 감소 합은 분할 후보가 많은 변수에 유리할 수 있고, 상관된 변수 사이에 중요도가 나뉠 수도 있습니다.</p><p>별도 평가 자료에서 변수를 섞어 보는 순열 중요도 역시 상관 구조와 평가 설계의 영향을 받습니다. 중요도가 높다는 것은 그 변수가 목표를 원인으로 변화시킨다는 뜻이 아닙니다.</p><p>랜덤 포레스트는 여러 나무의 결과를 모으고, 부스팅은 손실을 줄이는 방향으로 나무를 순차적으로 더합니다. 단일 나무의 불안정성을 보완하는 다음 학습 주제이며, 이 장의 수치는 앙상블 성능을 나타내지 않습니다.</p>')
 sec('practice','확인 문제','분할 기준과 예측을 직접 확인하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('75㎡의 예측은 어느 잎에서 나오나요?',f'31 초과 80 이하의 두 번째 잎입니다. 예측은 학습 7건 평균 {av[1]:.2f}만원/㎡입니다.'),('자식 노드의 불순도를 왜 가중하나요?','자식마다 관측 수가 다르므로 전체 관측에 대한 평균 손실로 비교하기 위해서입니다.'),('양성과 음성이 3:1이면 지니 불순도는?','1−(3/4)²−(1/4)²=0.375입니다.'),('학습 오차가 가장 작은 깊이를 바로 채택해도 될까요?','과적합할 수 있습니다. 목적에 맞는 검증 분할에서 복잡도를 선택하고 최종 시험은 분리합니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','모형의 종류와 적용 범위를 먼저 확인합니다','<p>회귀계수로 표현된 식과 구간별 잎 평균은 다른 예측 규칙입니다. 결과를 읽을 때 학습 변수·기간·잎의 관측 수·검증 오차를 함께 확인하세요. 여기의 나무가 CH2 Macro의 실제 서비스 알고리즘이라고 전제하지 않습니다.</p><p>학습 예제의 잎 평균은 개별 적정가격이나 인과효과를 뜻하지 않습니다. 소수 표본과 조건 차이를 고려해 집단 통계와 모형의 의미를 이해하는 데 사용합니다.</p>')
 sec('recap','정리와 참고자료','질문·손실·복잡도·검증을 함께 읽습니다','<p>나무는 입력 공간을 나누고 잎에서 예측합니다. 질문이 단순해도 분할 선택과 복잡도 조절에는 검증이 필요합니다. 다음 <a href="/learn/stats/clustering/">31장 「군집분석」</a>에서는 목표값 없이 관측을 묶는 방법을 배웁니다.</p><ul><li><a href="https://scikit-learn.org/stable/modules/tree.html">scikit-learn: Decision Trees — 분할 기준과 가지치기 참고</a></li><li><a href="../decision-tree-example.json">분할 후보·잎·오차 재현 자료</a></li></ul><p class="learn-source-note">그림과 계산은 공통 학습 자료 및 별도 가상 분류 예제로 직접 작성했습니다. 참고자료 확인: 2026-10-09.</p>')
 p=ROOT/'decision-tree/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="의사결정나무">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1의사결정나무의 분할·잎 예측, 회귀와 분류의 손실, 가지치기와 검증 방법을 학습합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
