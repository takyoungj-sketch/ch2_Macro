"""Chapter 22: purposes, supervised tasks and unsupervised structure."""
from pathlib import Path
from statistics import mean
from html import escape
import json,re,math
from _build_regression_chapter import fit
ROOT=Path(__file__).resolve().parent

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];train=rows[:20];test=rows[20:];m=fit([r['area'] for r in train],[r['price'] for r in train]);baseline=mean(r['price'] for r in train)
 predictions=[dict(id=r['id'],actual=r['price'],predicted=m['intercept']+m['slope']*r['area']) for r in test];mae=mean(abs(r['actual']-r['predicted']) for r in predictions);base_mae=mean(abs(r['price']-baseline) for r in test)
 points=[[1,1],[1,2],[2,1],[2,2],[6,6],[6,7],[7,6],[7,7]];centers=[[1.5,1.5],[6.5,6.5]];labels=[min(range(2),key=lambda j:sum((v-c)**2 for v,c in zip(p,centers[j]))) for p in points]
 result=dict(description='공통 자료의 번호 순서 분할은 학습용이며 시간 검증이 아님. 분류·군집 예제는 별도 가상 자료.',train_ids=[r['id'] for r in train],test=predictions,fit=m,MAE=mae,baseline_mean=baseline,baseline_MAE=base_mae,classification=dict(TN=90,FP=0,FN=10,TP=0,accuracy=.9,recall=0),clustering=dict(points=points,centers=centers,labels=labels,inertia=sum(sum((v-c)**2 for v,c in zip(p,centers[j])) for p,j in zip(points,labels))))
 (ROOT/'learning-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def ln(x,y,a,b,c='#94a3b8'):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="{c}"/>'
 def rect(x,y,w,h,c):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{c}"/>'
 def fig(id,title,b,cap,h=410):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=tx(24,28,'공통 자료: 학습에 쓰지 않은 번호 21~30의 예측')+ln(65,325,570,325)+ln(65,55,65,325)+ln(65,325,515,55,'#94a3b8')
 for r in predictions:b+=f'<circle data-id="{r["id"]}" cx="{65+r["actual"]*1.5}" cy="{325-r["predicted"]*.9}" r="5" fill="#2563eb"/>'
 for v in [0,100,200,300]:b+=tx(60+v*1.5,350,v)+tx(24,330-v*.9,v)
 b+=tx(24,385,'가로: 실제 단가 / 세로: 예측 단가 (만원/㎡)')
 f1=fig('regression','관측값과 예측값',b,'그림 1. 1~20번으로 학습하고 21~30번에서 평가한 교재용 분할입니다. 회색선은 예측=관측입니다. 번호는 시간순이 아니며 운영 성능을 추정하기 위한 검증 설계가 아닙니다.')
 b=tx(24,28,'가상 분류: 100건 모두 음성으로 예측')+tx(220,75,'예측 음성')+tx(420,75,'예측 양성')
 for x,y,c in [(190,100,'#dbeafe'),(390,100,'#f1f5f9'),(190,210,'#ffedd5'),(390,210,'#f1f5f9')]:b+=rect(x,y,170,85,c)
 b+=tx(35,148,'실제 음성')+tx(35,258,'실제 양성')+tx(250,148,'90')+tx(450,148,'0')+tx(250,258,'10')+tx(450,258,'0')+tx(24,350,'정확도 90% · 양성 재현율 0%')+tx(24,385,'높은 정확도가 드문 양성의 탐지를 보장하지 않습니다')
 f2=fig('classification','불균형 분류의 혼동행렬',b,'그림 2. 실제 양성 10건을 모두 놓친 별도 가상 예제입니다. 행은 실제, 열은 예측입니다. 양성 예측이 없어 정밀도는 분모가 0이며 정의되지 않습니다.')
 b=tx(24,28,'가상 두 특징의 K=2 군집 예제')+ln(65,325,570,325)+ln(65,55,65,325)
 for p,j in zip(points,labels):b+=f'<circle cx="{65+p[0]*60}" cy="{325-p[1]*35}" r="5" fill="'+('#2563eb' if j==0 else '#d97706')+'"/>'
 for a,v in centers:
  cx=65+a*60;cy=325-v*35;b+=ln(cx-8,cy-8,cx+8,cy+8,'#111827')+ln(cx-8,cy+8,cx+8,cy-8,'#111827')
 for v in [0,2,4,6,8]:b+=tx(60+v*60,350,v)+tx(30,330-v*35,v)
 b+=tx(24,385,'가로: 특징 1 / 세로: 특징 2 · ×는 군집 중심')
 f3=fig('clusters','정답 범주 없이 만든 군집',b,'그림 3. 단위 없는 가상 8점입니다. 색은 정답 유형이 아니라 거리로 정한 군집 번호입니다. 중심은 (1.5,1.5), (6.5,6.5)이며 번호를 바꾸어도 같은 분할입니다.')
 b=tx(24,28,'예측 성능 평가의 개념 흐름')
 for y,label,desc in [(75,'학습 자료','전처리 기준과 모형 계수 학습'),(170,'검증 자료','변수·모형·설정 비교와 선택'),(265,'시험 자료','선택을 끝낸 뒤 최종 성능 평가')]:
  b+=rect(90,y,450,65,'#eaf2ff')+tx(115,y+25,label)+tx(115,y+50,desc)
 b+=tx(300,160,'↓')+tx(300,255,'↓')+tx(24,385,'시험 결과를 보고 반복 선택하면 시험도 검증 자료가 됩니다')
 f4=fig('workflow','학습과 평가 역할',b,'그림 4. 역할을 구분한 개념도입니다. 비율은 고정하지 않으며 시간·단지 구조와 활용 상황에 맞춰 자료를 나눕니다. 전처리는 학습 자료에서 적합합니다.')
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','질문부터 정하기','설명·인과·예측은 서로 다른 질문입니다','<p><strong>기술적 설명</strong>은 관측 자료의 분포와 관계를 요약합니다. 예를 들어 면적과 단가의 관계를 그리거나 유형을 조건으로 한 계수를 읽습니다. <strong>인과 추론</strong>은 특정 조건을 바꾸었을 때 결과가 어떻게 달라지는지 묻습니다. 관측 관계만으로 답할 수 없으며 설계와 식별 가정이 필요합니다.</p><p><strong>예측</strong>은 아직 모르는 결과를, 예측 시점에 알 수 있는 정보로 추정합니다. 계수의 유의성보다 새로운 자료에서의 오차·확률의 신뢰성·활용 목적이 중요합니다. 같은 회귀식도 설명이나 예측에 쓰일 수 있지만 평가 기준은 달라집니다.</p><p>따라서 ‘통계는 설명, 머신러닝은 예측’으로 나누지 않습니다. 방법 이름보다 질문, 자료 수집 과정, 검증 설계를 먼저 정합니다. 예측 변수의 중요도가 크다고 인과효과가 큰 것도 아닙니다.</p>')
 sec('supervised','지도학습의 구조','입력 X와 목표 Y의 대응을 학습합니다','<p>지도학습은 관측된 입력 특징 X와 목표값 Y의 쌍으로 f̂를 학습해 새 입력의 Y를 예측합니다. 부동산 예제에서는 면적·층·지역이 입력, 거래 단가가 목표가 될 수 있습니다. 학습 당시 목표값이 있다는 뜻이지, 실제 예측 시점에도 목표를 알고 있다는 뜻은 아닙니다.</p><p>‘정답’은 기록된 목표 열을 가리키는 편의적 표현입니다. 측정오차·신고오류·라벨 기준의 모호함이 있을 수 있으며 현실의 완전한 진실이라는 뜻은 아닙니다. 입력과 목표의 정의·관측 단위·예측 시점을 명시해야 합니다.</p><p>경험위험 최소화는 학습 손실 (1/n)ΣL(yᵢ,f(xᵢ))을 줄이는 방식입니다. 제곱손실·절대손실·로그손실처럼 목적에 맞는 손실을 선택하며, 학습 손실을 낮추는 것만으로 새 자료 성능이 보장되지 않습니다.</p>')
 sec('regression','회귀 예제','숫자 목표에는 원 단위의 오차를 확인합니다',f'<p>수치형 목표를 예측하는 회귀를 살펴보겠습니다. 공통 자료 1~20번으로 적합한 식은 ŷ={m["intercept"]:.3f} {m["slope"]:+.4f}×면적입니다. 나머지 10건의 MAE는 {mae:.2f}만원/㎡입니다.</p>'+f1+f'<p>같은 평가 10건에서 학습 평균 {baseline:.2f}만 항상 예측하는 기준모형의 MAE는 {base_mae:.2f}입니다. 기준모형은 평가 자료의 단가를 보고 다시 정하지 않았습니다. 평균 기준은 간단한 비교용이며 MAE를 최소화하는 상수는 학습 중앙값이라는 점도 구별합니다.</p><p>단 한 번의 작은 번호 순 분할로 우수한 모형을 확정할 수 없습니다. 공통 자료의 번호는 거래 시점이 아니므로 미래 예측 검증도 아닙니다. 같은 목표·평가 표본·지표에서 비교했다는 계산 원리를 배우는 예제입니다.</p>')
 sec('classification','분류 예제','범주 목표는 확률과 오류의 종류를 읽습니다','<p>분류는 범주형 목표를 예측합니다. 예를 들어 별도로 정의하고 라벨링한 거래 유형을 추정할 수 있습니다. 주거·상업을 숫자 0·1로 저장해도 연속값 회귀와 같은 목표가 되는 것은 아닙니다. 로지스틱 회귀는 이름에 회귀가 있지만 대표적인 분류 확률 모형입니다.</p>'+f2+'<p>정확도=(TP+TN)/전체, 양성 재현율=TP/(TP+FN), 정밀도=TP/(TP+FP)입니다. TP는 맞힌 양성, FN은 놓친 양성, FP는 잘못 양성으로 분류한 관측입니다. 이 예제의 정밀도는 분모가 0입니다. 소프트웨어가 편의상 0을 출력하더라도 정의와 출력 규칙을 구별합니다.</p><p>확률을 범주로 바꾸는 임계값은 오탐과 누락의 균형을 바꿉니다. 확률 예측에는 로그손실·보정 상태도 중요합니다. 양성이 드물 때 정확도만으로 판단하지 말고 어떤 오류가 더 중요한지 목적에 맞춰 평가합니다.</p>')
 sec('unsupervised','비지도학습의 구조','목표 라벨 없이 입력 자료의 구조를 찾습니다','<p>비지도학습은 지정된 목표 Y와 맞추도록 학습하지 않고 X의 구조를 찾습니다. 군집은 비슷한 관측을 묶고, 차원축소는 여러 특징을 더 적은 좌표로 요약합니다. 밀도 추정이나 일부 이상 탐지도 이 범주에 속합니다. 비지도학습이 모두 군집분석이라는 뜻은 아닙니다.</p><p>‘라벨을 사용하지 않는다’와 ‘사람의 선택이 없다’는 다릅니다. 특징·거리·표준화·군집 수를 사람이 정하며 이 선택이 결과를 바꿉니다. 알고리즘은 분석 목적을 대신 정해 주지 않습니다.</p>')
 sec('clusters','군집 예제','군집 번호는 원래의 정답 범주가 아닙니다','<p>K-means는 정한 K개의 중심과 각 점 사이의 제곱거리 합을 작게 만드는 군집을 찾습니다. 그림은 구조를 보기 쉬운 별도 가상 8점과 두 중심입니다. 각 점을 가까운 중심에 배정하고, 각 군집의 평균을 다시 구하면 같은 중심을 얻습니다.</p>'+f3+'<p>이 예제의 군집 내 제곱거리 합은 4입니다. 이 숫자만으로 두 군집이 현실의 두 유형을 발견했다고 결론낼 수 없습니다. K를 늘리면 같은 자료의 최적 제곱거리 합은 줄거나 같아지므로 작은 값만 추구하면 안 됩니다.</p><p>군집 번호에는 순서나 좋고 나쁨이 없습니다. 임의로 주거·상업이라는 이름을 붙이는 것과 해당 범주를 예측하도록 학습하는 것은 다릅니다. 사후 라벨 일치율을 계산하더라도 그것은 외부 비교이며, 독립 평가 자료의 분류 정확도와 같지 않습니다.</p>')
 sec('features','특징·스케일·시점','같은 열도 분석 목적에 따라 역할이 달라집니다','<p>기존 거래의 면적·단가로 시장 구성을 탐색한다면 단가를 군집 특징에 사용할 수 있습니다. 반면 아직 모르는 단가를 예측하려는 시점에는 그 단가나 거래금액÷면적으로 복원한 값을 입력으로 넣을 수 없습니다. 이는 정답을 입력에 섞는 데이터 누수입니다.</p><p>거리 기반 방법에서 ㎡·원·층은 숫자의 규모가 달라 거리의 비중을 바꿉니다. 표준화는 한 방법이지만, 모든 변수의 중요도가 같다는 선택이 될 수 있으므로 목적과 단위를 함께 고려합니다. 예측 파이프라인의 평균·표준편차는 학습 자료로만 추정합니다.</p><p>중복 거래·같은 단지의 반복 관측·인접 시점의 유사 자료를 무작위로 나누면 실제 새 지역이나 미래에 적용하는 상황보다 쉬운 평가가 될 수 있습니다. 어느 단위까지 새로운 대상인지 먼저 정하세요.</p>')
 sec('workflow','학습과 평가','선택에 사용한 자료와 마지막 평가를 구분합니다','<p>학습 자료는 계수와 전처리 기준을 정하는 데, 검증 자료는 모형·변수·설정을 비교하는 데, 시험 자료는 선택이 끝난 뒤 성능을 평가하는 데 사용합니다. 자료가 작으면 교차검증 등으로 역할을 구현할 수 있지만 시험 결과를 반복 선택에 이용하면 더 이상 독립적인 최종 평가가 아닙니다.</p>'+f4+'<p>회귀는 같은 목표 단위의 오차, 분류는 오류 유형과 확률, 군집은 안정성·분리 정도·분야 해석을 함께 봅니다. 비지도학습도 평가가 필요하며 표본을 바꾸거나 스케일을 바꿀 때 구조가 유지되는지 확인합니다. 내부 지표가 좋아도 유용한 시장 구분이라는 보장은 없습니다.</p>')
 sec('choice','문제 정의 연습','알고 싶은 것과 사용할 정보를 먼저 적습니다','<ol><li>분석 대상과 관측 단위를 정합니다. 거래 한 건인지, 단지인지, 지역·월인지 구별합니다.</li><li>설명·인과·예측·구조 탐색 중 주된 질문을 적습니다.</li><li>지도학습이면 목표와 예측 시점, 그 시점의 입력 정보를 정의합니다.</li><li>활용할 지역·시점·집단에 맞춰 검증 설계와 기준모형을 정합니다.</li><li>결과의 오차·불확실성·적용 범위를 함께 보고합니다.</li></ol><p>좋은 예측이 좋은 인과 설명을 보장하지 않고, 해석하기 쉬운 모형이 자동으로 좋은 예측을 보장하지도 않습니다. 목적에 맞게 확인할 증거를 선택합니다.</p>')
 sec('practice','확인 문제','목표와 평가 대상을 구별하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('회귀분석은 통계이므로 지도학습이 아닌가요?','입력과 수치형 목표의 대응을 학습한다면 지도학습입니다. 방법의 전통과 학습 구조는 다른 구분입니다.'),('군집 색이 실제 유형과 비슷하면 분류 정확도인가요?','군집을 만든 뒤의 외부 비교입니다. 같은 자료에서 사후 대응시킨 일치율을 새 관측의 분류 정확도로 읽지 않습니다.'),('정확도 90%면 드문 양성도 잘 찾나요?','아니요. 양성 10%를 모두 놓쳐도 정확도 90%일 수 있습니다. 재현율 등도 확인합니다.'),('단가로 기존 시장을 군집화하는 것도 늘 누수인가요?','아니요. 이미 알려진 거래의 구조 탐색에는 쓸 수 있습니다. 미지의 단가를 예측하는 입력에 넣으면 목적상 누수가 됩니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','기능 이름보다 분석 질문을 확인합니다','<p>CH2 Macro에서 관계를 요약한 통계, 미래·미지 결과의 예측, 유사한 시장 집단의 탐색을 구별해 읽으세요. 실제 제공되는 입력·출력과 평가 설명을 확인하고 이 장의 예제가 서비스에 구현된 알고리즘이라고 전제하지 않습니다.</p><p>공통 자료는 출처 미확인 학습 예제이며 분류·군집 그림은 별도 가상 자료입니다. 군집이나 예측값을 개별 적정가·투자 권고로 바꾸어 해석하지 않습니다.</p>')
 sec('recap','정리와 참고자료','목표·정보·평가가 학습 문제를 정합니다','<p>지도학습은 목표값과의 대응을, 비지도학습은 입력의 구조를 학습합니다. 설명·인과·예측의 목적을 먼저 구별하고 새 자료에서 무엇을 확인해야 하는지 정하세요.</p><p>다음 <a href="/learn/stats/train-validation-test/">23장 「학습·검증·시험 자료와 데이터 누수」</a>에서 평가 설계를 자세히 살펴봅니다.</p><ul><li><a href="https://scikit-learn.org/stable/supervised_learning.html">scikit-learn: 지도학습</a></li><li><a href="https://scikit-learn.org/stable/unsupervised_learning.html">scikit-learn: 비지도학습</a></li><li><a href="../learning-example.json">분할·예측·가상 분류·군집 예제 자료</a></li></ul><p class="learn-source-note">본문과 그림은 직접 작성한 학습 예제입니다. 참고자료 확인: 2026-10-09.</p>')
 p=ROOT/'supervised-unsupervised/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="통계적 설명과 예측, 지도학습과 비지도학습">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1설명·인과·예측의 목적과 회귀·분류·군집의 차이, 입력과 목표·학습과 평가를 구별합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
