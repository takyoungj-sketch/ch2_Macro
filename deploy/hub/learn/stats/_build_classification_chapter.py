"""Chapter 28: illustrative logistic probabilities and classification metrics."""
from pathlib import Path
from html import escape
import math,json,re
ROOT=Path(__file__).resolve().parent

def build():
 probs=[.1,.2,.35,.45,.55,.65,.8,.9];ys=[0,0,1,0,1,0,1,1]
 def conf(th):
  tp=sum(y==1 and p>=th for y,p in zip(ys,probs));fp=sum(y==0 and p>=th for y,p in zip(ys,probs));fn=4-tp;tn=4-fp
  return dict(threshold=th,TP=tp,FP=fp,FN=fn,TN=tn,accuracy=(tp+tn)/8,precision=tp/(tp+fp),recall=tp/4,specificity=tn/4,F1=2*tp/(2*tp+fp+fn))
 curve=[dict(x=i/20,p=1/(1+math.exp(-(-2+.8*i/20)))) for i in range(101)]
 odds=[dict(before=p,after=2*p/(1+p)) for p in [.1,.5,.8]]
 loss=[dict(p=i/100,positive=-math.log(i/100),negative=-math.log1p(-i/100)) for i in range(1,100)]
 auc=sum(a>b for a,y in zip(probs,ys) if y==1 for b,z in zip(probs,ys) if z==0)/16
 d=dict(description='모든 자료는 별도 가상 예제. 시그모이드 계수는 사전 지정이며 학습으로 추정한 값이 아님.',curve=curve,odds=odds,probabilities=probs,labels=ys,confusions=[conf(.5),conf(.3)],loss=loss,log_loss=-sum(y*math.log(p)+(1-y)*math.log1p(-p) for y,p in zip(ys,probs))/8,brier=sum((y-p)**2 for y,p in zip(ys,probs))/8,AUC=auc)
 (ROOT/'classification-example.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def ln(x,y,a,b):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="#94a3b8"/>'
 def fig(id,title,b,cap):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 410" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=tx(24,28,'가상 식: logit(p)=−2+0.8x')+ln(70,320,570,320)+ln(70,65,70,320)+ln(70,195,570,195)
 b+='<polyline points="'+' '.join(f"{70+r['x']*100},{320-r['p']*250}" for r in curve)+'" fill="none" stroke="#2563eb" stroke-width="3"/>'
 for v in range(6):b+=tx(65+v*100,350,v)
 for v in [0,.25,.5,.75,1]:b+=tx(25,325-v*250,v)
 b+=tx(24,385,'가로: 가상 점수 x / 세로: 양성 확률 p · x=2.5에서 p=0.5')
 g1=fig('sigmoid','로지스틱 확률곡선',b,'그림 1. 설명용으로 계수 −2와 0.8을 직접 정했습니다. 실제 자료에서 계수를 추정한 곡선은 아닙니다.')
 b=tx(24,28,'오즈가 2배가 되어도 확률이 2배가 되지는 않습니다')+ln(70,320,570,320)
 for i,r in enumerate(odds):
  for j,(key,c) in enumerate([('before','#94a3b8'),('after','#2563eb')]):
   xx=120+i*170+j*35;v=r[key];b+=f'<rect x="{xx}" y="{320-v*240}" width="30" height="{v*240}" fill="{c}"/>'+tx(xx-5,308-v*240,f'{v*100:.1f}')
  b+=tx(115+i*170,350,f'시작 {r["before"]*100:.0f}%')
 for v in [0,.5,1]:b+=tx(25,325-v*240,f'{v*100:.0f}%')
 b+=tx(24,385,'회색: 변화 전 / 파랑: 오즈 2배 후 · 숫자는 확률(%)')
 g2=fig('odds','오즈비와 확률 변화',b,'그림 2. p′=2p/(1+p)로 계산한 별도 예제입니다. 오즈비가 같아도 시작 확률에 따라 퍼센트포인트 변화가 다릅니다.')
 b=tx(24,28,'같은 가상 8건: 임계값만 바꾸어 비교')
 for j,c in enumerate(d['confusions']):
  left=60+j*300;b+=tx(left,80,f'임계값 {c["threshold"]}')+tx(left+70,110,'예측 0 / 예측 1')
  for i,(name,a,v) in enumerate([('실제 0',c['TN'],c['FP']),('실제 1',c['FN'],c['TP'])]):
   yy=135+i*80;b+=tx(left,yy+35,name)
   for k,val in enumerate([a,v]):b+=f'<rect x="{left+75+k*80}" y="{yy}" width="70" height="60" fill="#dbeafe"/>'+tx(left+102+k*80,yy+35,val)
  b+=tx(left,330,f'정밀도 {c["precision"]:.2f} / 재현율 {c["recall"]:.2f}')
 b+=tx(24,385,'양성 판정: p ≥ 임계값 · 행은 실제, 열은 예측')
 g3=fig('threshold','임계값과 혼동행렬',b,'그림 3. 임계값을 내리면 이 예제에서 놓친 양성은 줄지만 오탐은 늘어납니다. 이 8건으로 최적 임계값이나 운영 성능을 확정하지 않습니다.')
 b=tx(24,28,'한 관측의 로그손실: 확신하며 틀리면 큰 비용')+ln(70,320,570,320)+ln(70,65,70,320)
 for key,col in [('positive','#2563eb'),('negative','#d97706')]:b+='<polyline data-label="'+key+'" points="'+' '.join(f"{70+r['p']*500},{320-r[key]*50}" for r in loss)+'" fill="none" stroke="'+col+'" stroke-width="2"/>'
 for v in [0,.25,.5,.75,1]:b+=tx(65+v*500,350,v)
 for v in [0,2,4]:b+=tx(30,325-v*50,v)
 b+=tx(24,385,'가로: 양성 예측 확률 / 파랑 실제 1 / 주황 실제 0')
 g4=fig('loss','로그손실 곡선',b,'그림 4. 자연로그를 사용하고 p=0.01~0.99만 그렸습니다. 실제 1에 p→0 또는 실제 0에 p→1이면 손실은 무한히 커집니다.')
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','학습 목표','확률을 구하는 것과 범주를 정하는 것은 다릅니다','<p>메일이 스팸일 확률을 0.7로 예측했다고 해 봅시다. 이 숫자만으로 메일을 차단할지 정해지는 것은 아닙니다. 일반 메일을 잘못 차단하는 비용과 스팸을 놓치는 비용에 따라 판정 기준이 달라질 수 있습니다.</p><p>이 장에서는 두 범주를 예측하는 로지스틱 회귀를 살펴봅니다. 예측 확률을 범주로 바꾸는 과정과 함께, 분류가 맞았는지·확률이 적절한지·순서가 잘 매겨졌는지를 구별해 평가합니다.</p><ul class="learn-objectives"><li>로지스틱 회귀가 확률을 만드는 방식과 오즈비의 의미를 설명합니다.</li><li>임계값에 따라 혼동행렬과 정밀도·재현율이 어떻게 달라지는지 계산합니다.</li><li>범주 판정, 확률 평가, 순위 성능과 확률 보정을 구별합니다.</li><li>범주 비율과 오류 비용을 고려하고 검증으로 판정 기준을 정합니다.</li></ul>')
 sec('sigmoid','핵심 이해','로지스틱 회귀는 양성일 확률을 예측합니다','<p><strong>이진 분류</strong>는 미리 정한 두 범주 중 하나를 예측하는 문제입니다. 스팸을 1, 일반 메일을 0으로 둘 수 있습니다. 1을 ‘양성’, 0을 ‘음성’이라고 부르지만 좋은 결과와 나쁜 결과를 뜻하는 것은 아닙니다. 무엇을 1로 정했는지 먼저 밝혀야 합니다.</p><p>로지스틱 회귀는 입력을 선형식으로 묶은 점수 η(에타)를 <strong>시그모이드 함수</strong>에 넣어 양성 확률 p로 바꿉니다. 이름에 회귀가 들어가지만 대표적인 분류 확률 모형입니다.</p>'+g1+'<p>그림의 식은 η=−2+0.8x입니다. x가 커지면 확률이 올라가지만 같은 폭으로 계속 증가하지는 않습니다. x=2.5에서는 η=0이 되어 p=0.5입니다. 이 계수는 원리를 보여 주기 위해 직접 정했습니다.</p><p>확률을 구한 뒤 별도의 임계값으로 범주를 정합니다. 같은 확률 모형에도 서로 다른 판정 기준을 적용할 수 있습니다.</p><details><summary>확률식 자세히 보기</summary><p>p(X)=P(Y=1|X)=1/[1+exp(−η)]이며 η=β₀+β₁X₁+⋯+βₖXₖ입니다. 유한한 η에서 p는 0과 1 사이에 있고 정확히 0이나 1은 되지 않습니다.</p></details>')
 sec('odds','오즈와 계수','오즈가 2배라고 확률도 2배는 아닙니다','<p><strong>오즈</strong>는 양성 확률과 음성 확률의 비인 p/(1−p)입니다. p=0.5이면 오즈는 1, p=0.8이면 오즈는 4입니다. <strong>로그오즈</strong>는 이 값에 자연로그를 취한 것으로, 로지스틱 회귀는 로그오즈를 입력의 선형식으로 표현합니다.</p><p>상호작용이 없는 모형에서 다른 포함 변수를 고정하고 Xⱼ가 1 증가하면, 로그오즈는 βⱼ만큼 증가하고 오즈는 exp(βⱼ)배가 됩니다. 이를 오즈비라고 합니다. 확률이 βⱼ만큼 증가하거나 exp(βⱼ)배가 된다는 뜻은 아닙니다.</p>'+g2+'<p>오즈비가 2여도 시작 확률이 10%면 약 18.2%, 50%면 약 66.7%, 80%면 약 88.9%가 됩니다. 같은 오즈비라도 확률이 얼마나 변하는지는 출발점에 달려 있습니다.</p><details><summary>계수와 확률 변화의 식</summary><p>logit(p)=ln[p/(1−p)]입니다. 그림 1의 계수 0.8은 오즈비 exp(0.8)≈2.23에 해당합니다. 상호작용이 없을 때 Xⱼ에 대한 확률의 기울기는 βⱼp(1−p)입니다. 조건부 오즈비를 인과효과나 전체 집단에서 단순 계산한 오즈비와 같다고 해석하지 않습니다.</p></details>')
 sec('fit','학습 방법','관측된 답에 높은 확률을 주는 계수를 찾습니다','<p>실제가 1이면 높은 p를, 실제가 0이면 낮은 p를 주는 모형이 관측된 답을 더 잘 설명합니다. 로지스틱 회귀는 이 원리에 따라 우도를 크게 하는 계수를 찾습니다. 뒤에서 살펴볼 로그손실을 작게 만드는 것과 같은 학습입니다.</p><p>일반적으로 수치 최적화를 반복해 계수를 구합니다. Y나 잔차가 정규분포여야 한다는 가정은 없습니다. 대신 로그오즈를 표현하는 식이 적절한지, 반복 관측처럼 서로 의존하는 자료가 있는지, 자료를 어떻게 모았는지 살펴야 합니다.</p><p>입력만으로 두 범주가 완전히 나뉘면 규제 없는 추정에서 계수가 무한히 커질 수 있습니다. 이를 완전 분리라고 합니다. 드문 범주, 비슷한 입력 변수, 수렴 여부를 확인하고 필요하면 규제 등 적절한 추정 방법을 사용합니다. 전처리와 규제 강도 선택도 학습 자료 안에서 수행합니다.</p><details><summary>우도와 분산</summary><p>Y가 0 또는 1인 조건부 베르누이 모형에서 관측별 우도는 pᵢʸⁱ(1−pᵢ)¹⁻ʸⁱ입니다. 독립 관측의 우도를 곱하거나 로그우도를 더해 최대화합니다. 조건부 분산은 p(1−p)입니다.</p></details>')
 sec('threshold','분류 임계값','0.5는 모든 목적에 맞는 기준이 아닙니다','<p>가상 관측 8개의 예측 확률을 0.10·0.20·0.35·0.45·0.55·0.65·0.80·0.90, 실제 답을 0·0·1·0·1·0·1·1로 둡니다. 확률이 임계값 이상이면 양성으로 판정합니다. 이 확률들은 직접 정한 값으로 그림 1에서 얻은 예측은 아닙니다.</p>'+g3+'<p><strong>TP</strong>는 맞힌 양성, <strong>FP</strong>는 실제 음성을 양성으로 잘못 판정한 오탐, <strong>FN</strong>은 놓친 양성, <strong>TN</strong>은 맞힌 음성입니다. 임계값 0.5에서는 TP=3, FP=1, FN=1, TN=3입니다. 0.3으로 낮추면 TP=4, FP=2, FN=0, TN=2가 됩니다.</p><p>스팸을 놓치는 일을 줄이려 임계값을 낮추면 일반 메일까지 차단할 수 있습니다. 누락과 오탐의 비용을 함께 보고 검증 자료로 기준을 정해야 합니다. 시험 결과가 좋아질 때까지 반복해서 바꾸지는 않습니다.</p><p>판정 기준에는 확률이 실제 비율과 잘 맞는지, 양성이 얼마나 흔한지, 사람이 검토할 수 있는 양은 어느 정도인지도 영향을 줍니다. 이 8개의 관측만으로 최적 임계값을 정할 수는 없습니다.</p>')
 sec('metrics','분류 평가','정확도·정밀도·재현율은 서로 다른 비율입니다','<ul><li><strong>정확도 = (TP+TN)/n:</strong> 전체 중 맞힌 비율입니다.</li><li><strong>정밀도 = TP/(TP+FP):</strong> 양성이라고 판정한 것 중 실제 양성의 비율입니다.</li><li><strong>재현율 = TP/(TP+FN):</strong> 실제 양성 중 찾아낸 비율입니다.</li><li><strong>특이도 = TN/(TN+FP):</strong> 실제 음성 중 음성으로 맞힌 비율입니다.</li></ul><p>위 예제에서 임계값 0.5의 정확도·정밀도·재현율은 모두 0.75입니다. 0.3으로 낮춰도 정확도는 0.75이지만 정밀도는 2/3, 재현율은 1이 됩니다. 같은 정확도라도 어떤 오류를 내는지는 다릅니다.</p><p>양성이 드물면 모두 음성이라고 해도 정확도가 높을 수 있습니다. 혼동행렬, 범주 비율, 집단·시점별 성능과 관측 수를 함께 봅니다.</p><details><summary>F1과 분모가 0인 경우</summary><p>F1=2TP/(2TP+FP+FN)은 정밀도와 재현율의 조화평균이며 TN을 직접 반영하지 않습니다. 정밀도나 재현율 등의 분모가 0이면 원래 비율을 계산할 수 없습니다. 제외하거나 특정 값으로 표시하는 경우 그 처리 규칙을 밝혀야 합니다.</p></details>')
 sec('loss','확률 평가','같은 판정이라도 확신의 정도는 다릅니다',f'<p>실제 답이 1일 때 0.6과 0.99는 임계값 0.5에서 모두 맞는 판정입니다. 하지만 확률 예측으로는 다릅니다. 반대로 실제가 0이라면 0.99라는 확신은 크게 빗나간 것입니다. <strong>로그손실</strong>은 이렇게 확신하면서 틀린 예측에 큰 비용을 줍니다.</p>'+g4+f'<p>확률의 제곱오차를 평균한 <strong>브라이어 점수</strong>도 사용할 수 있습니다. 가상 8건의 로그손실은 {d["log_loss"]:.4f}, 브라이어 점수는 {d["brier"]:.4f}이며 둘 다 낮을수록 좋습니다.</p><p>확률은 그대로 두고 임계값만 바꾸면 두 값은 변하지 않습니다. 범주 판정의 성능과 확률의 품질을 나누어 평가하는 이유입니다.</p><details><summary>확률 평가의 산식</summary><p>로그손실 = −(1/n)Σ[yᵢln pᵢ+(1−yᵢ)ln(1−pᵢ)], 브라이어 점수 = (1/n)Σ(yᵢ−pᵢ)²입니다. 로그손실에는 자연로그를 사용합니다. 구현에서 0이나 1 근처의 확률을 잘라 계산한다면 그 규칙도 확인합니다.</p></details>')
 sec('ranking','순위와 보정','순서를 잘 매기는 것과 확률이 잘 맞는 것은 다릅니다',f'<p><strong>ROC 곡선</strong>은 임계값을 바꿀 때 위양성률과 재현율이 어떻게 변하는지 보여 줍니다. ROC-AUC는 임의로 고른 양성의 점수가 음성보다 높을 확률로 해석할 수 있습니다. 동점은 절반으로 셉니다. 가상 자료에서는 양성·음성 16쌍 중 13쌍의 순서가 맞아 AUC={auc:.4f}입니다.</p><p><strong>PR 곡선</strong>은 정밀도와 재현율을 비교합니다. 양성이 드문 문제에서 유용하지만 정밀도와 PR 요약은 범주 비율에 영향을 받습니다. AUC가 높다고 특정 임계값에서 오류 비용이 작거나 예측 확률까지 정확한 것은 아닙니다.</p><p><strong>확률 보정</strong>은 예를 들어 0.7로 예측한 관측을 충분히 모았을 때 실제 양성 비율이 약 70%인지 보는 성질입니다. 순위는 잘 매기면서 확률은 과장할 수도 있습니다. 작은 구간별 표본에서는 불확실성이 크므로 이 8건으로 보정을 입증할 수 없습니다.</p><p>보정 방법을 학습하거나 고를 때도 평가 자료를 선택에 사용하지 않도록 구분합니다.</p>')
 sec('extensions','변수와 범주의 확장','입력과 범주가 늘어나면 해석 조건도 확인합니다','<p>연속변수, 더미변수, 상호작용을 입력에 넣을 수 있습니다. 상호작용이 있으면 한 변수의 오즈비는 다른 변수 값에 따라 달라집니다. 서로 겹치지 않는 범주가 세 개 이상이면 다항 로지스틱·소프트맥스 모형 등을 사용합니다. 한 메일에 여러 주제 라벨을 붙이는 것처럼 여러 답이 동시에 가능한 문제와는 구별합니다.</p><p>특정 범주의 관측을 더 뽑거나 클래스 가중치를 주면 학습 목표와 출력 확률의 해석이 달라질 수 있습니다. 인위적으로 범주 비율을 맞춘 평가 결과를 실제 사용 환경의 성능으로 바로 옮겨 읽지 않습니다. 같은 사람의 반복 관측, 시간에 따른 변화, 잘못 붙은 라벨도 점검해야 합니다.</p>')
 sec('practice','확인 문제','확률·오즈·판정을 구별하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('오즈비 2이면 확률도 2배인가요?','아니요. p′=2p/(1+p)이므로 시작 확률에 따라 달라집니다.'),('임계값을 낮추면 로그손실도 바뀌나요?','확률이 같다면 바뀌지 않습니다. 판정과 확률 평가는 다른 단계입니다.'),('AUC가 높으면 0.8 확률이 정확한가요?','AUC는 순위 성능입니다. 확률 보정은 별도로 확인합니다.'),('완전 분리일 때 비규제 추정은 항상 안정적인가요?','계수가 발산할 수 있습니다. 수렴과 자료 구조를 확인하고 규제 등 적절한 방법을 검토합니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','양성 정의와 확률의 대상을 먼저 확인합니다','<p>분류 결과를 읽을 때 무엇을 양성으로 정의했는지, 예측 시점의 입력과 라벨 기준, 임계값 선택과 평가 설계를 확인하세요. 이 장의 가상 확률과 성능은 실제 서비스 결과가 아닙니다.</p><p>확률은 특정 조건의 사건에 관한 모형 출력이며 개별 물건의 적정가나 투자 판단의 보장이 아닙니다. 순위·보정·오류 비용을 함께 읽습니다.</p>')
 sec('recap','학습 요약','확률·판정·순위·보정을 나누어 확인합니다','<ul class="learn-recap-list"><li><strong>로지스틱 회귀</strong>는 로그오즈를 선형식으로 표현하고 시그모이드로 양성 확률을 구합니다.</li><li>계수의 지수 exp(β)는 조건 아래에서 <strong>오즈비</strong>이며 확률비가 아닙니다.</li><li><strong>임계값</strong>을 바꾸면 혼동행렬과 정밀도·재현율이 달라집니다. 목적과 오류 비용에 맞춰 검증으로 정합니다.</li><li>로그손실과 브라이어 점수는 확률을 평가하므로 확률이 같다면 임계값만 바꾸어도 변하지 않습니다.</li><li>AUC의 순위 성능과 확률 보정은 다릅니다. 범주 비율과 관측 수를 함께 확인합니다.</li></ul><p>다음 <a href="/learn/stats/knn/">29장 「최근접 이웃과 변수의 스케일」</a>에서는 비슷한 관측을 찾아 예측하는 방법을 살펴봅니다.</p><details class="learn-references"><summary>참고자료와 예제 데이터</summary><ul><li><a href="https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression">scikit-learn: Logistic regression</a></li><li><a href="../classification-example.json">가상 확률·혼동행렬·손실 계산 자료</a></li></ul><p class="learn-source-note">모든 그림과 숫자는 별도 가상 예제입니다. 참고자료 기존 확인일: 2026-10-09.</p></details>')
 p=ROOT/'classification/index.html';p.parent.mkdir(exist_ok=True);html=p.read_text(encoding='utf-8') if p.exists() else (ROOT/'regularization/index.html').read_text(encoding='utf-8').replace('https://ch2data.com/learn/stats/regularization/','https://ch2data.com/learn/stats/classification/')
 html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="분류와 로지스틱 회귀">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1로지스틱 확률·오즈비·임계값과 혼동행렬, 로그손실·AUC·확률 보정을 예제로 학습합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
