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
 g1=fig('sigmoid','로지스틱 확률곡선',b,'그림 1. 설명용으로 계수 −2와 0.8을 직접 정했습니다. 실제 자료에 적합한 곡선이나 시장 예측 결과가 아닙니다.')
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
 sec('sigmoid','확률을 예측하는 모형','0과 1의 답에서 양성 확률을 학습합니다','<p>이진 분류는 사전에 정의한 두 범주 중 하나를 예측합니다. Y=1을 양성, Y=0을 음성으로 두되 무엇이 양성인지 먼저 명시합니다. 로지스틱 회귀는 이름에 회귀가 있어도 대표적인 분류 확률 모형입니다.</p><p><strong>p(X)=P(Y=1|X)=1/[1+exp(−η)]</strong>, η=β₀+β₁X₁+⋯+βₖXₖ로 씁니다. 선형 예측값 η를 시그모이드로 변환해 0~1의 확률을 얻습니다. 유한한 η에서는 정확히 0이나 1이 되지 않습니다.</p>'+g1+'<p>확률을 출력하는 단계와 임계값으로 범주를 정하는 단계는 다릅니다. 같은 확률 모형도 누락과 오탐의 비용에 따라 다른 판정 규칙을 사용할 수 있습니다.</p>')
 sec('odds','오즈와 계수','exp(β)는 확률비가 아니라 오즈비입니다','<p>오즈는 p/(1−p), 로그오즈는 logit(p)=ln[p/(1−p)]입니다. p=0.5이면 오즈 1, p=0.8이면 오즈 4입니다. 로지스틱 모형은 확률 자체가 아니라 로그오즈를 설명변수의 선형식으로 표현합니다.</p><p>다른 포함 변수를 고정하고 상호작용이 없을 때 Xⱼ가 1 증가하면 로그오즈는 βⱼ만큼, 오즈는 exp(βⱼ)배가 됩니다. 확률이 βⱼ만큼 증가하거나 exp(βⱼ)배가 된다는 뜻은 아닙니다.</p>'+g2+'<p>그림 1의 기울기 0.8은 오즈비 exp(0.8)≈2.23입니다. 확률의 기울기는 βⱼp(1−p)로 현재 확률에 따라 달라집니다. 조건부 오즈비는 인과효과나 전체 집단의 단순 오즈비와 자동으로 같지 않습니다.</p>')
 sec('fit','추정과 가정','관측된 0·1의 우도를 크게 만드는 계수를 찾습니다','<p>조건부 베르누이 모형에서 관측별 우도는 pᵢʸⁱ(1−pᵢ)¹⁻ʸⁱ입니다. 독립 관측의 우도를 곱하거나 로그우도를 더해 최대화합니다. 이는 평균 음의 로그우도, 즉 로그손실을 최소화하는 것과 같습니다.</p><p>일반적으로 OLS처럼 한 번의 닫힌 식으로 계수를 구하지 않고 수치 최적화를 사용합니다. 로지스틱 모형은 Y나 잔차가 정규분포일 것을 요구하지 않습니다. 조건부 분산은 p(1−p)이며, 로그오즈 함수의 형태와 관측 의존성·표집 구조를 점검해야 합니다.</p><p>설명변수로 두 범주가 완전히 분리되면 비규제 최대우도 계수가 무한대로 발산할 수 있습니다. 희소 범주·공선성·수렴 상태를 확인하고 필요하면 규제나 적절한 추정 방법을 사용합니다. 규제 강도와 전처리는 학습 자료 안에서 선택합니다.</p>')
 sec('threshold','분류 임계값','0.5는 모든 목적에 최적인 기준이 아닙니다','<p>가상 예측 확률을 0.10·0.20·0.35·0.45·0.55·0.65·0.80·0.90, 실제 라벨을 0·0·1·0·1·0·1·1로 둡니다. 이 확률들은 설명을 위해 직접 정했으며 그림 1을 적합해 얻은 결과가 아닙니다.</p>'+g3+'<p>TP는 맞힌 양성, FP는 잘못 양성이라 한 관측, FN은 놓친 양성, TN은 맞힌 음성입니다. 임계값 0.5에서는 TP=3, FP=1, FN=1, TN=3이고, 0.3에서는 TP=4, FP=2, FN=0, TN=2입니다.</p><p>누락 비용이 크면 낮은 임계값을 검토할 수 있지만 오탐 부담도 함께 봅니다. 임계값은 검증 자료와 목적을 이용해 정하고 시험 결과에 반복 맞추지 않습니다. 잘 보정된 확률과 일정한 비용을 가정하면 비용에 따른 결정 규칙을 만들 수 있지만 실제 비용·유병률·업무 용량을 확인해야 합니다.</p>')
 sec('metrics','분류 평가','정확도와 재현율은 다른 질문에 답합니다','<p>정확도=(TP+TN)/n, 정밀도=TP/(TP+FP), 재현율=TP/(TP+FN), 특이도=TN/(TN+FP)입니다. F1=2TP/(2TP+FP+FN)은 정밀도와 재현율의 조화평균이며 TN을 직접 반영하지 않습니다. 분모가 0인 경우의 처리 규칙도 밝혀야 합니다.</p><p>위 예제의 0.5 기준 정확도·정밀도·재현율은 모두 0.75입니다. 0.3 기준 정확도는 여전히 0.75지만 정밀도는 2/3, 재현율은 1로 달라집니다. 같은 정확도라도 오류의 구성은 다를 수 있습니다.</p><p>양성이 드물면 모두 음성이라 해도 정확도가 높을 수 있습니다. 혼동행렬과 범주 비율을 함께 보고, 집단·시점별 성능과 표본 수를 확인합니다.</p>')
 sec('loss','확률 평가','정답 범주뿐 아니라 확률의 품질도 봅니다',f'<p><strong>로그손실=−(1/n)Σ[yᵢln pᵢ+(1−yᵢ)ln(1−pᵢ)]</strong>는 확신하며 틀린 예측에 큰 비용을 줍니다. <strong>브라이어 점수=(1/n)Σ(yᵢ−pᵢ)²</strong>는 이진 확률의 제곱오차입니다. 둘 다 낮을수록 좋습니다.</p>'+g4+f'<p>가상 8건의 로그손실은 {d["log_loss"]:.4f}, 브라이어 점수는 {d["brier"]:.4f}입니다. 임계값만 바꾸고 확률은 그대로 두면 이 두 값은 바뀌지 않습니다. 수치 계산에서 확률을 작은 값으로 잘라 쓰는 구현은 그 규칙을 확인해야 합니다.</p>')
 sec('ranking','순위와 보정','AUC가 높아도 확률이 잘 맞는다는 뜻은 아닙니다',f'<p>ROC는 임계값에 따른 위양성률 FP/(FP+TN)과 재현율을 그립니다. ROC-AUC는 양성의 점수가 음성보다 높을 확률로 해석할 수 있으며 동점에는 절반을 부여합니다. 이 가상 자료는 양성·음성 16쌍 중 13쌍에서 순서가 맞아 AUC={auc:.4f}입니다.</p><p>PR 곡선은 정밀도와 재현율을 비교하며 양성이 드문 문제에서 유용합니다. 정밀도와 PR 요약은 범주 비율에 영향을 받습니다. AUC는 특정 임계값의 업무 성과나 확률 보정을 대신하지 않습니다.</p><p>보정은 0.7이라고 예측한 관측들을 충분히 모았을 때 실제 양성 비율이 약 0.7인지 보는 성질입니다. 작은 구간별 표본에서는 불확실성이 크며, 이 8건만으로 보정을 입증할 수 없습니다. 보정 방법을 학습하거나 선택할 때도 독립 평가 경계를 유지합니다.</p>')
 sec('extensions','다중 변수와 다중 범주','기준·스케일·표집을 함께 확인합니다','<p>연속변수·더미변수·상호작용을 넣을 수 있습니다. 상호작용이 있으면 한 변수의 오즈비는 다른 변수 값에 따라 달라집니다. 세 개 이상 상호 배타적인 범주에는 다항 로지스틱·소프트맥스 모형 등을 사용하며, 여러 라벨이 동시에 가능한 문제와 구별합니다.</p><p>재표집이나 클래스 가중치는 학습 목표와 출력 확률의 해석을 바꿀 수 있습니다. 평가 자료를 인위적으로 균형화한 점수를 실제 범주 비율의 운영 성능으로 곧바로 읽지 않습니다. 지역·단지·시간 의존성과 라벨 오류도 점검합니다.</p>')
 sec('practice','확인 문제','확률·오즈·판정을 구별하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('오즈비 2이면 확률도 2배인가요?','아니요. p′=2p/(1+p)이므로 시작 확률에 따라 달라집니다.'),('임계값을 낮추면 로그손실도 바뀌나요?','확률이 같다면 바뀌지 않습니다. 판정과 확률 평가는 다른 단계입니다.'),('AUC가 높으면 0.8 확률이 정확한가요?','AUC는 순위 성능입니다. 확률 보정은 별도로 확인합니다.'),('완전 분리일 때 비규제 추정은 항상 안정적인가요?','계수가 발산할 수 있습니다. 수렴과 자료 구조를 확인하고 규제 등 적절한 방법을 검토합니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','양성 정의와 확률의 대상을 먼저 확인합니다','<p>분류 결과를 읽을 때 무엇을 양성으로 정의했는지, 예측 시점의 입력과 라벨 기준, 임계값 선택과 평가 설계를 확인하세요. 이 장의 가상 확률과 성능은 실제 서비스 결과가 아닙니다.</p><p>확률은 특정 조건의 사건에 관한 모형 출력이며 개별 물건의 적정가나 투자 판단의 보장이 아닙니다. 순위·보정·오류 비용을 함께 읽습니다.</p>')
 sec('recap','정리와 참고자료','확률 추정과 의사결정의 기준을 분리합니다','<p>로지스틱 회귀는 로그오즈를 선형식으로 표현합니다. 오즈비를 확률비로 읽지 말고, 판정 지표·확률 손실·순위·보정을 목적에 맞춰 함께 확인하세요.</p><p>다음 <a href="/learn/stats/knn/">29장 「최근접 이웃과 변수의 스케일」</a>로 이어집니다.</p><ul><li><a href="https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression">scikit-learn: Logistic regression</a></li><li><a href="../classification-example.json">가상 확률·혼동행렬·손실 계산 자료</a></li></ul><p class="learn-source-note">모든 그림과 숫자는 별도 가상 예제입니다. 참고자료 확인: 2026-10-09.</p>')
 p=ROOT/'classification/index.html';p.parent.mkdir(exist_ok=True);html=p.read_text(encoding='utf-8') if p.exists() else (ROOT/'regularization/index.html').read_text(encoding='utf-8').replace('https://ch2data.com/learn/stats/regularization/','https://ch2data.com/learn/stats/classification/')
 html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="분류와 로지스틱 회귀">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1로지스틱 확률·오즈비·임계값과 혼동행렬, 로그손실·AUC·확률 보정을 예제로 학습합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
