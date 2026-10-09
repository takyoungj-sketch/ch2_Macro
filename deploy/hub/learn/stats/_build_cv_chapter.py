"""Chapter 26: fold-local fitting and honest selection."""
from pathlib import Path
from statistics import mean
from html import escape
import json,re,math
from _build_regression_chapter import fit
from _build_errors_chapter import metrics
ROOT=Path(__file__).resolve().parent

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];folds=[];all_y=[];all_p=[]
 for k in range(3):
  va=rows[k*10:(k+1)*10];tr=rows[:k*10]+rows[(k+1)*10:];m=fit([r['area'] for r in tr],[r['price'] for r in tr]);pred=[m['intercept']+m['slope']*r['area'] for r in va];y=[r['price'] for r in va];all_y+=y;all_p+=pred
  folds.append(dict(fold=k+1,train_ids=[r['id'] for r in tr],validation_ids=[r['id'] for r in va],intercept=m['intercept'],slope=m['slope'],predictions=pred,metrics=metrics(y,pred)))
 pooled=metrics(all_y,all_p);average_rmse=mean(f['metrics']['RMSE'] for f in folds)
 d=dict(description='공통 학습 자료의 번호 순 3폴드. 시간·집단 검증 또는 최종 운영 성능 추정이 아님.',folds=folds,pooled=pooled,mean_fold_RMSE=average_rmse,unequal_example=dict(sizes=[2,8],MAE=[10,2],unweighted=6,pooled=3.6))
 (ROOT/'cross-validation-example.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def box(x,y,w,h,c):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{c}"/>'
 def ln(x,y,a,b):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="#94a3b8"/>'
 def fig(id,title,b,cap):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 410" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=tx(24,28,'3폴드: 매번 20건으로 새로 학습하고 10건을 예측')
 for j,label in enumerate(['1~10번','11~20번','21~30번']):b+=tx(140+j*160,80,label)
 for k in range(3):
  yy=105+k*75;b+=tx(24,yy+32,f'{k+1}회')
  for j in range(3):b+=box(120+j*160,yy,145,55,'#ffedd5' if j==k else '#dbeafe')+tx(160+j*160,yy+32,'검증' if j==k else '학습')
 b+=tx(24,370,'파랑: 학습 / 주황: 검증 · 한 관측은 검증에 정확히 한 번 사용')
 g1=fig('folds','3폴드의 자료 배정',b,'그림 1. 번호 블록별 교재용 분할입니다. 세 모형의 학습 자료가 서로 겹치므로 폴드 점수들을 독립 반복 측정으로 간주하지 않습니다.')
 b=tx(24,28,'공통 자료: 폴드별 검증 MAE')+ln(70,320,575,320)
 for i,f in enumerate(folds):
  v=f['metrics']['MAE'];xx=140+i*170;b+=box(xx,320-v*3.5,70,v*3.5,'#2563eb')+tx(xx+10,307-v*3.5,f'{v:.2f}')+tx(xx+10,350,f'{i+1}폴드')
 for v in [0,20,40,60]:b+=tx(25,325-v*3.5,v)
 b+=tx(24,385,f'세로: 만원/㎡ · 동일 크기 폴드 평균 = 전체 OOF MAE {pooled["MAE"]:.2f}')
 g2=fig('scores','폴드별 오차의 차이',b,'그림 2. 각 폴드에서 회귀계수를 다시 추정했습니다. 폴드마다 검증 관측과 학습 구성이 달라 점수도 달라집니다. 세 값만으로 성능의 정밀한 신뢰구간을 만들지 않습니다.')
 b=tx(24,28,'가상 불균등 폴드: 2건 MAE 10 / 8건 MAE 2')+ln(80,320,570,320)
 for i,(label,v) in enumerate([('폴드 단순 평균',6),('관측별 통합',3.6)]):
  xx=180+i*220;b+=box(xx,320-v*32,80,v*32,'#2563eb' if i==0 else '#d97706')+tx(xx+25,307-v*32,v)+tx(xx-18,350,label)
 for v in [0,2,4,6]:b+=tx(35,325-v*32,v)
 b+=tx(24,385,'(10+2)/2 = 6 / (2×10+8×2)/10 = 3.6')
 g3=fig('aggregation','폴드와 관측 가중치',b,'그림 3. 별도 가상 예제입니다. 폴드에 같은 비중을 주는 것과 관측에 같은 비중을 주는 것은 다른 집계입니다. 어떤 대상을 평균하는지 밝혀야 합니다.')
 b=tx(24,28,'중첩 교차검증: 바깥은 평가, 안쪽은 선택')+box(55,65,370,250,'#f1f5f9')+tx(75,95,'바깥 학습 부분')+box(80,115,330,75,'#dbeafe')+tx(100,144,'안쪽 CV: 전처리·후보 비교')+tx(100,174,'선택 후 바깥 학습 전체로 재적합')+box(80,215,330,65,'#dcfce7')+tx(100,251,'이 바깥 반복의 선택된 모형')+box(435,115,125,165,'#ffedd5')+tx(453,160,'바깥 검증')+tx(450,196,'선택에 미사용')+tx(417,252,'→')+tx(24,370,'바깥 분할을 바꾸며 선택 절차 전체의 성능을 평가합니다')
 g4=fig('nested','선택과 평가의 중첩 구조',b,'그림 4. 한 번의 바깥 반복을 보여 주는 개념도입니다. 바깥 검증 자료는 안쪽 선택과 재적합에 쓰지 않습니다. 각 바깥 반복에서 선택되는 설정은 달라도 됩니다.')
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('cross-validation','K폴드의 원리','검증 역할을 바꾸면서 모형을 다시 학습합니다','<p>K폴드 교차검증은 개발 자료를 K개 부분으로 나누고, 한 부분을 검증에 남겨 나머지 K−1개로 학습하는 과정을 반복합니다. 이미 전체 자료로 적합한 모형을 그대로 가져와 각 부분의 점수만 계산하는 것이 아닙니다.</p>'+g1+'<p>일반적인 K폴드에서 각 관측은 검증에 한 번, 학습에 K−1번 들어갑니다. 다른 반복의 학습에 사용되었다고 누수는 아닙니다. 그 관측을 예측하는 해당 반복의 학습·선택에 그 검증 정보를 넣지 않는 것이 핵심입니다.</p><p>교차검증은 자료 활용을 높이지만 최종 모형 한 개의 정확한 미래 성능을 보장하지 않습니다. 각 반복은 전체보다 적은 자료로 학습하며, 최종 재적합 모형과 학습 크기도 다릅니다.</p>')
 sec('scores','공통 자료 예제','세 번의 직선과 검증 오차를 계산합니다',f'<p>공통 30건을 번호 1~10, 11~20, 21~30의 세 블록으로 나눕니다. 번호는 시간 정보가 아니며 이 예제는 실제 미래·새 지역 성능을 평가하는 설계가 아닙니다. 매번 나머지 20건으로 면적–단가 직선을 새로 적합합니다.</p>'+g2+'<p>'+ ' / '.join(f'{f["fold"]}폴드: ŷ={f["intercept"]:.3f} {f["slope"]:+.4f}×면적' for f in folds)+f'입니다. 동일한 회귀 방법도 학습 표본이 달라지면 계수가 달라집니다. 세 폴드의 MAE 평균은 {pooled["MAE"]:.2f}만원/㎡입니다.</p><p>모든 관측에 대해 그 관측을 학습에서 제외한 모형의 예측을 모으면 OOF(out-of-fold) 예측이 됩니다. <a href="../cross-validation-example.json">분할·계수·OOF 예측 자료</a>에서 계산을 확인할 수 있습니다.</p>')
 sec('aggregation','점수 집계','폴드 평균과 관측 평균을 구별합니다','<p>검증 건수가 같으면 폴드별 MAE의 단순 평균과 전체 OOF MAE가 같습니다. 크기가 다르면 각 폴드에 같은 비중을 줄지, 관측 수로 가중할지에 따라 결과가 달라집니다.</p>'+g3+f'<p>RMSE는 제곱근 때문에 동일 크기 폴드에서도 단순 평균과 전체 OOF 계산이 일반적으로 다릅니다. 공통 예제의 폴드 RMSE 평균은 {average_rmse:.2f}, 전체 OOF RMSE는 {pooled["RMSE"]:.2f}입니다. 관측별 통합은 √[Σnₖ RMSEₖ²/Σnₖ]로 계산합니다.</p><p>R²·AUC 같은 지표도 폴드별 계산을 평균한 값과 모든 OOF 예측을 합쳐 계산한 값이 같다고 전제하지 않습니다. 집단을 같은 비중으로 평가하려면 관측 수 가중과 다른 질문이라는 점을 적습니다.</p>')
 sec('cv-mape','CV-MAPE','교차검증은 MAPE의 한계를 없애지 않습니다',f'<p>이 장의 CV-MAPE는 각 관측의 OOF 예측으로 계산한 100×평균(|y−ŷ|/|y|)로 정의합니다. 공통 자료에서는 {pooled["MAPE"]:.2f}%입니다. 세 폴드의 크기가 같고 실제값이 모두 양수이므로 폴드별 MAPE 평균과도 같습니다.</p><p>실제값 0에서는 원래 MAPE가 정의되지 않고, 작은 실제값에 민감한 성질도 그대로 남습니다. 소프트웨어의 비율/백분율 표시와 0 처리 규칙을 확인하세요. 교차검증을 붙였다고 다른 자료의 CV-MAPE를 무조건 비교할 수 있는 것은 아닙니다.</p>')
 sec('pipeline','전처리의 위치','전체 파이프라인을 폴드 안에서 다시 적합합니다','<p>결측 대체·표준화·PCA·특징 선택을 전체 개발 자료에 먼저 적합한 뒤 교차검증하면 검증 부분의 정보가 학습에 들어갈 수 있습니다. 각 폴드의 학습 부분에서 기준을 추정하고, 해당 검증에는 그 기준을 적용합니다.</p><p>규제 강도·이웃 수·나무 깊이 등을 비교할 때 후보마다 같은 분할을 사용하면 표본 차이에 따른 변동을 줄여 비교하기 쉽습니다. 단, 같은 분할을 반복해서 들여다보며 후보를 무한히 늘리면 선택 편향은 커질 수 있습니다.</p>')
 sec('model-recommendation','모형 선택','가장 낮은 CV 점수는 선택에 쓰인 점수입니다','<p>후보와 주 지표를 먼저 정하고 같은 분할에서 비교합니다. 가장 좋은 평균 점수뿐 아니라 폴드별 편차·특정 집단의 실패·해석 가능성·비용도 살펴봅니다. 작은 점수 차이를 확정적인 우열로 읽지 않습니다.</p><p>여러 후보 중 최소값을 고르면 우연히 잘 나온 후보를 선택할 수 있습니다. 따라서 선택에 사용한 최저 CV 오차를 그대로 독립적인 최종 성능이라고 보고하면 낙관적일 수 있습니다. 최종 시험 자료를 남겨 두거나 중첩 교차검증으로 선택 절차 자체를 평가합니다.</p><p>선택이 끝나면 정한 설정과 전처리를 개발 자료 전체에 다시 적합합니다. OOF 예측을 만든 K개 모형이 곧 최종 모형은 아닙니다. 폴드 모형을 평균하는 앙상블을 쓰려면 그것도 별도의 절차로 정의하고 평가해야 합니다.</p>')
 sec('nested','중첩 교차검증','선택의 바깥에 평가를 한 겹 더 둡니다','<p>바깥 반복에서 평가 부분을 먼저 떼어 둡니다. 바깥 학습 부분 안에서만 안쪽 CV로 설정을 고르고, 선택된 설정을 바깥 학습 전체에 재적합한 뒤 바깥 검증에 적용합니다.</p>'+g4+'<p>바깥 점수는 특정 설정 하나가 아니라 ‘설정을 고르고 학습하는 절차’의 성능을 평가합니다. 바깥 점수를 보고 절차를 반복 변경하면 다시 선택에 사용한 것이므로 사용 이력을 밝혀야 합니다. 전체 개발 자료로 최종 설정을 고르고 재적합할 때도 평가 결과와 최종 모델을 구별합니다.</p>')
 sec('design','K와 분할 설계','시간·집단의 구조가 K보다 먼저입니다','<p>K가 커지면 각 학습 부분은 커지고 검증 부분은 작아집니다. 계산량과 점수 변동의 특성이 달라지므로 K가 클수록 항상 더 신뢰할 수 있는 것은 아닙니다. 한 관측씩 빼는 LOOCV도 만능은 아닙니다.</p><p>독립적인 분류 자료에서는 계층화로 범주 비율을 맞출 수 있고, 새 단지 평가에서는 집단 단위 분할을 사용합니다. 미래 예측은 앞 시점으로 학습하고 뒤 시점으로 평가하는 확장·이동 창을 설계합니다. 일반 K폴드처럼 미래를 학습해 과거를 예측하지 않도록 주의합니다.</p><p>시간 분할에서는 초반 관측이 검증에 들어가지 않을 수 있고, 반복 분할에서는 같은 관측이 여러 번 평가될 수도 있습니다. 모든 CV에서 OOF가 관측당 정확히 한 번이라고 가정하지 않습니다. 평가 대상과 집계 가중치를 명시하세요.</p>')
 sec('uncertainty','점수의 불확실성','폴드 표준편차를 곧바로 신뢰구간으로 바꾸지 않습니다','<p>폴드 점수의 표준편차는 분할 사이 변동을 요약하지만, 학습 부분이 겹치므로 점수들이 독립이 아닙니다. SD/√K를 기계적으로 표준오차로 해석하거나 단순 t구간을 붙이지 않습니다.</p><p>반복 CV는 분할 민감도를 살피는 데 도움이 되지만 반복 횟수가 늘었다고 새로운 독립 관측이 늘어난 것은 아닙니다. 시간·집단에 맞는 외부 검증과 자료 수집 설계가 중요합니다. 점수와 함께 분할 규칙·시드·기간·집단·건수·후보 탐색 범위를 보고하세요.</p>')
 sec('practice','확인 문제','반복마다 무엇을 다시 배워야 할까요?','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('전체 자료로 표준화한 뒤 K폴드를 하면 괜찮나요?','학습되는 전처리 기준도 각 폴드의 학습 부분에서 추정해야 합니다.'),('폴드 RMSE 평균은 전체 OOF RMSE와 같은가요?','일반적으로 다릅니다. 통합 RMSE는 폴드 MSE를 관측 수로 가중한 뒤 제곱근을 취합니다.'),('최저 CV 오차는 선택된 모형의 독립 최종 점수인가요?','선택에 사용됐으므로 낙관적일 수 있습니다. 별도 시험 또는 중첩 평가를 사용합니다.'),('CV 표준편차를 √K로 나누면 정확한 표준오차인가요?','겹치는 학습 자료 때문에 폴드 점수들이 의존하므로 자동으로 그렇게 해석할 수 없습니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','CV라는 이름보다 분할과 선택 절차를 확인합니다','<p>CV 점수의 산식·폴드 수·시간/집단 기준·전처리 위치·후보 선택 여부를 함께 확인하세요. 이 장의 번호 분할 예제가 실제 서비스의 평가 설계라고 전제하지 않습니다.</p><p>공통 자료는 출처 미확인 학습 예제입니다. 작은 CV 오차를 개별 적정가나 미래 시장 성능의 보장으로 해석하지 않습니다.</p>')
 sec('recap','정리와 참고자료','반복 평가에서도 정보의 경계를 지킵니다','<p>교차검증은 매번 학습을 다시 수행하는 절차입니다. 점수 집계를 명확히 하고, 선택에 사용한 결과와 최종 평가를 구별하세요.</p><p>다음 <a href="/learn/stats/regularization/">27장 「규제: 릿지와 라쏘」</a>로 이어집니다.</p><ul><li><a href="https://scikit-learn.org/stable/modules/cross_validation.html">scikit-learn: Cross-validation</a></li><li><a href="../cross-validation-example.json">공통 자료 3폴드 계산 자료</a></li></ul><p class="learn-source-note">본문·그림은 공통 학습 자료와 별도 가상 예제로 직접 작성했습니다. 참고자료 확인: 2026-10-09.</p>')
 p=ROOT/'cross-validation/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="교차검증과 모형 선택">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1K폴드·OOF·점수 집계와 중첩 교차검증, 시간·집단 분할 및 모형 선택의 한계를 학습합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
