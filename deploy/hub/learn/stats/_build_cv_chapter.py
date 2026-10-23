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
 b+=tx(24,385,f'세로: Y와 같은 단위 · 동일 크기 폴드 평균 = 전체 OOF MAE {pooled["MAE"]:.2f}')
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
 sec('quick-start','학습 목표','한 번 나눈 결과만으로 모형을 골라도 될까요?','<p>자료를 한 번 나누어 평가하면 어떤 관측이 검증 쪽에 들어갔는지에 따라 점수가 달라질 수 있습니다. 교차검증은 검증에 남길 부분을 바꾸어 가며 모형을 다시 학습하고 비교하는 방법입니다.</p><p>이 장에서는 3폴드 예제로 반복 과정을 따라갑니다. 이어서 여러 점수를 모으는 방법, 전처리를 수행할 위치, 후보를 고르는 평가와 최종 성능을 확인하는 평가의 차이를 살펴봅니다.</p><ul class="learn-objectives"><li>K폴드 교차검증에서 매번 어떤 자료로 학습하고 검증하는지 설명합니다.</li><li>각 관측을 학습에서 제외해 만든 OOF 예측과 점수 집계를 이해합니다.</li><li>전처리와 모형 선택에서 검증 정보가 섞이지 않도록 구분합니다.</li><li>중첩 교차검증의 역할과 교차검증 점수의 한계를 설명합니다.</li></ul>')
 sec('cross-validation','핵심 이해','검증할 부분을 바꿀 때마다 모형을 다시 배웁니다','<p><strong>K폴드 교차검증</strong>은 모형 개발에 사용할 자료를 K개 묶음(폴드)으로 나눕니다. 한 묶음을 검증에 남기고 나머지 K−1개로 학습합니다. 검증할 묶음을 바꾸면서 K번 반복합니다. 그림은 30개 관측을 10개씩 나눈 3폴드 예제입니다.</p>'+g1+'<p>첫 번째에는 11~30번으로 학습해 1~10번을 예측합니다. 두 번째에는 1~10번과 21~30번으로 새로 학습해 11~20번을 예측합니다. 세 번째에도 같은 방식으로 다시 학습합니다. 전체 자료로 만든 모형 하나의 점수만 나누어 계산하는 것이 아닙니다.</p><p>일반적인 K폴드에서 각 관측은 검증에 한 번, 학습에 K−1번 들어갑니다. 다른 반복의 학습에 쓰였다는 사실 자체가 누수는 아닙니다. <strong>그 관측을 예측하는 반복에서는 그 관측의 검증 정보가 학습에 들어가지 않아야 합니다.</strong></p><p>교차검증은 자료를 번갈아 활용하는 방법입니다. 각 모형은 전체보다 적은 자료로 학습하므로, 전체 자료로 다시 학습한 최종 모형의 정확한 미래 점수를 알려 주는 것은 아닙니다.</p>')
 sec('scores','예제 계산','같은 방법으로 학습해도 직선과 오차가 달라집니다',f'<p>공통 학습 자료의 두 수치 열을 단위 없는 X와 Y로 놓습니다. 30개 관측을 번호 1~10, 11~20, 21~30의 세 묶음으로 나누고, 매번 나머지 20개로 X에서 Y를 예측하는 직선을 새로 적합합니다. 번호는 시간 순서를 뜻하지 않으며 이 분할은 계산 연습을 위한 것입니다.</p>'+g2+'<p>반복마다 얻은 식은 '+ ' / '.join(f'{f["fold"]}폴드: ŷ={f["intercept"]:.3f} {f["slope"]:+.4f}×X' for f in folds)+f'입니다. 학습 자료가 바뀌면 계수가 달라지고, 검증 관측도 달라져 점수가 변합니다. 세 폴드의 MAE 평균은 {pooled["MAE"]:.2f}로 Y와 같은 단위입니다.</p><p>각 관측에는 자신을 학습에서 제외한 모형의 예측이 하나씩 생깁니다. 이를 모은 것이 <strong>OOF(out-of-fold) 예측</strong>입니다. <a href="../cross-validation-example.json">분할·계수·OOF 예측 자료</a>에서 계산을 확인할 수 있습니다. 원자료는 출처가 확인되지 않은 학습용 자료입니다.</p>')
 sec('aggregation','점수 집계','폴드를 평균할지 관측을 평균할지 구별합니다','<p>검증 관측 수가 같으면 폴드별 MAE의 단순 평균과 전체 OOF 예측의 MAE가 같습니다. 관측 수가 다르면 결과가 달라질 수 있습니다. 예를 들어 2개 관측인 폴드의 MAE가 10이고 8개 관측인 폴드의 MAE가 2라면, 폴드 평균은 (10+2)/2 = 6입니다. 관측을 같은 비중으로 모으면 (2×10+8×2)/10 = 3.6입니다.</p>'+g3+f'<p><strong>RMSE는 폴드 크기가 같아도 단순 평균과 전체 계산값이 다를 수 있습니다.</strong> 공통 예제의 폴드 RMSE 평균은 {average_rmse:.2f}, 전체 OOF RMSE는 {pooled["RMSE"]:.2f}입니다. 제곱근을 취하는 시점이 다르기 때문입니다.</p><details><summary>전체 RMSE를 구하는 방법</summary><p>폴드 k의 관측 수를 nₖ라고 하면 전체 RMSE는 √[Σnₖ RMSEₖ²/Σnₖ]입니다. 폴드별 MSE를 관측 수로 가중해 합친 뒤 마지막에 제곱근을 취합니다. R²나 AUC도 폴드별 평균과 전체 OOF 예측으로 계산한 값이 같다고 가정해서는 안 됩니다.</p></details><p>관측마다 같은 비중을 줄지 집단마다 같은 비중을 줄지는 평가 목적에 따라 정합니다. 점수와 함께 어떤 대상을 평균했는지 적어야 합니다.</p>')
 sec('cv-mape','CV-MAPE','교차검증을 해도 지표의 성질은 그대로입니다',f'<p>이 장에서 <strong>CV-MAPE</strong>는 각 관측의 OOF 예측으로 구한 MAPE를 뜻합니다. 산식은 100×평균(|y−ŷ|/|y|)이며 공통 자료의 결과는 {pooled["MAPE"]:.2f}%입니다. 세 폴드의 크기가 같고 실제값이 모두 양수이므로 폴드별 MAPE의 평균과도 같습니다.</p><p>25장에서 살펴본 한계도 남습니다. 실제값이 0이면 원래 MAPE는 정의되지 않고 작은 실제값에 민감합니다. 비율과 백분율 중 어떤 단위로 표시하는지, 0을 어떻게 처리하는지도 확인합니다. 서로 다른 자료의 CV-MAPE는 교차검증을 했다는 이유만으로 바로 비교할 수 없습니다.</p>')
 sec('pipeline','전처리의 위치','전처리 기준도 각 학습 부분에서 다시 구합니다','<p>전체 자료로 평균과 표준편차를 구해 표준화한 뒤 교차검증을 하면 검증 부분의 정보가 학습 기준에 섞입니다. 결측값 대체, 표준화, 주성분 분석(PCA), 변수 선택처럼 자료에서 기준을 배우는 과정은 <strong>각 반복의 학습 부분 안에서</strong> 수행해야 합니다. 검증 부분에는 그 기준을 적용합니다.</p><p>전처리와 모형을 하나의 파이프라인으로 묶어 매번 다시 적합하면 이 순서를 지키기 쉽습니다. 규제 강도, 이웃 수, 나무 깊이 같은 후보 설정도 같은 분할에서 비교하면 자료 구성 차이의 영향을 줄일 수 있습니다.</p><p>다만 같은 검증 결과를 계속 보면서 후보를 늘리면 우연히 그 자료에 잘 맞는 설정을 고를 수 있습니다. 전처리의 누수를 막는 일과 반복 선택의 영향을 줄이는 일은 모두 필요합니다.</p>')
 sec('model-recommendation','모형 선택','후보를 고른 점수와 최종 평가를 구별합니다','<p>후보와 주 평가 지표를 먼저 정하고 같은 분할에서 비교합니다. 평균 점수뿐 아니라 폴드별 차이, 특정 집단의 큰 오차, 설명하기 쉬운지, 계산 비용도 살펴봅니다. 작은 점수 차이만으로 우열을 단정하지 않습니다.</p><p>많은 후보 중 가장 좋은 점수를 고르면 우연히 잘 나온 결과를 선택할 수도 있습니다. 따라서 <strong>선택에 쓴 최저 CV 오차를 그대로 독립적인 최종 성능으로 보고하면 낙관적일 수 있습니다.</strong> 별도 시험 자료를 남기거나, 다음 절의 중첩 교차검증으로 선택 과정 전체를 평가합니다.</p><p>선택을 마치면 정한 설정으로 전처리와 모형을 개발 자료 전체에 다시 적합합니다. OOF 예측을 만든 K개 모형 자체가 최종 모형 하나는 아닙니다. 여러 폴드 모형의 예측을 평균해 사용할 수도 있지만, 그 경우에는 평균하는 절차까지 정해 평가해야 합니다.</p>')
 sec('nested','중첩 교차검증','안쪽에서 고르고 바깥쪽에서 평가합니다','<p><strong>중첩 교차검증</strong>은 선택과 평가를 두 겹으로 나눕니다. 먼저 바깥 분할에서 평가할 부분을 남깁니다. 바깥 학습 부분 안에서만 안쪽 교차검증을 수행해 설정을 고릅니다. 고른 설정으로 바깥 학습 부분 전체를 다시 학습한 뒤, 남겨 둔 바깥 검증 부분을 예측합니다.</p>'+g4+'<p>이 과정을 바깥 분할을 바꾸며 반복합니다. 바깥 점수는 특정 설정 하나보다는 <strong>설정을 고르고 학습하는 절차</strong>가 새 자료에서 얼마나 잘 작동하는지 평가합니다. 안쪽 학습 자료가 달라지므로 반복마다 선택되는 설정도 달라질 수 있습니다.</p><p>바깥 점수를 본 뒤 절차를 여러 번 바꾸면 그 점수도 선택에 사용한 셈입니다. 무엇을 보고 바꾸었는지 기록해야 합니다. 평가가 끝나 개발 자료 전체로 설정을 고르고 재적합할 때도 최종 모형과 평가에 사용한 모형들을 구별합니다.</p>')
 sec('design','K와 분할 설계','폴드 수보다 예측 상황을 먼저 정합니다','<p>K가 커지면 한 번에 학습하는 자료는 많아지고 검증 자료는 적어집니다. 반복 학습의 계산량도 늘어납니다. 점수 변동의 성질도 달라지므로 K가 클수록 항상 더 믿을 만하다고 할 수는 없습니다. 한 관측씩 남기는 방법(LOOCV)도 모든 상황의 정답은 아닙니다.</p><p>23장에서처럼 새 대상을 무엇으로 볼지 먼저 정합니다. 독립적인 분류 자료에서는 범주 비율을 비슷하게 맞추는 계층화를 고려할 수 있습니다. 처음 보는 학교에 적용하려면 학교를 묶어서 나눕니다. 미래 결과를 예측한다면 과거로 학습해 이후를 평가하고, 평가 시점을 뒤로 옮기며 반복합니다. 미래 자료로 학습해 과거를 예측하는 분할은 이 목적에 맞지 않습니다.</p><p>시간 분할에서는 초반 관측이 검증에 쓰이지 않을 수 있고, 반복 교차검증에서는 같은 관측에 여러 예측이 생길 수도 있습니다. 모든 교차검증에서 관측당 OOF 예측이 정확히 하나라고 생각해서는 안 됩니다. 평가 대상과 집계 규칙을 함께 정합니다.</p>')
 sec('uncertainty','점수의 불확실성','폴드 사이의 차이가 곧 신뢰구간은 아닙니다','<p>폴드 점수의 표준편차는 분할에 따라 점수가 얼마나 달랐는지 요약합니다. 하지만 학습 자료가 서로 겹치므로 폴드 점수들은 독립적인 반복 측정이 아닙니다. 표준편차를 √K로 나누어 곧바로 표준오차라고 하거나 단순한 t 신뢰구간을 붙일 수는 없습니다.</p><p>여러 분할로 교차검증을 반복하면 결과의 민감도를 살펴볼 수 있습니다. 반복 횟수를 늘려도 독립적인 새 관측이 늘어나는 것은 아닙니다. 필요한 경우 시간·집단 구조에 맞는 별도 자료에서 평가하고 자료 수집 방법도 검토합니다.</p><p>결과에는 분할 규칙, K, 난수 시드, 기간, 집단, 관측 수와 후보 탐색 범위를 함께 적습니다. 점수를 재현하고 적용 범위를 판단하는 데 필요한 정보입니다.</p>')
 sec('practice','확인 문제','반복마다 무엇을 다시 배워야 할까요?','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('전체 자료로 표준화한 뒤 K폴드를 하면 괜찮나요?','학습되는 전처리 기준도 각 폴드의 학습 부분에서 추정해야 합니다.'),('폴드 RMSE 평균은 전체 OOF RMSE와 같은가요?','일반적으로 다릅니다. 통합 RMSE는 폴드 MSE를 관측 수로 가중한 뒤 제곱근을 취합니다.'),('최저 CV 오차는 선택된 모형의 독립 최종 점수인가요?','선택에 사용됐으므로 낙관적일 수 있습니다. 별도 시험 또는 중첩 평가를 사용합니다.'),('CV 표준편차를 √K로 나누면 정확한 표준오차인가요?','겹치는 학습 자료 때문에 폴드 점수들이 의존하므로 자동으로 그렇게 해석할 수 없습니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','CV라는 이름보다 분할과 선택 절차를 확인합니다','<p>CV 점수의 산식·폴드 수·시간/집단 기준·전처리 위치·후보 선택 여부를 함께 확인하세요. 이 장의 번호 분할 예제가 실제 서비스의 평가 설계라고 전제하지 않습니다.</p><p>공통 자료는 출처 미확인 학습 예제입니다. 작은 CV 오차를 개별 적정가나 미래 시장 성능의 보장으로 해석하지 않습니다.</p>')
 sec('recap','학습 요약','역할을 바꾸어 반복하되 매번 학습의 경계를 지킵니다','<ul class="learn-recap-list"><li><strong>K폴드 교차검증</strong>은 검증 부분을 바꾸며 K번 새로 학습하는 절차입니다.</li><li><strong>OOF 예측</strong>은 각 관측을 해당 학습에서 제외해 얻습니다. 폴드 평균과 관측별 통합 점수는 지표와 폴드 크기에 따라 다를 수 있습니다.</li><li>전처리와 변수 선택도 매 반복의 학습 부분에서 다시 수행합니다.</li><li>후보 선택에 사용한 점수와 독립적인 최종 평가를 구별합니다. 중첩 교차검증은 안쪽에서 선택하고 바깥쪽에서 절차를 평가합니다.</li><li>시간·집단 구조에 맞게 분할하고, 폴드 점수의 표준편차를 곧바로 신뢰구간으로 해석하지 않습니다.</li></ul><p>다음 <a href="/learn/stats/regularization/">27장 「규제: 릿지와 라쏘」</a>에서는 계수의 크기를 제한해 모형의 복잡도를 조절하는 방법을 살펴봅니다.</p><details class="learn-references"><summary>참고자료와 예제 데이터</summary><ul><li><a href="https://scikit-learn.org/stable/modules/cross_validation.html">scikit-learn: Cross-validation</a></li><li><a href="../cross-validation-example.json">공통 자료 3폴드 계산 자료</a></li></ul><p class="learn-source-note">본문·그림은 공통 학습 자료와 별도 가상 예제로 직접 작성했습니다. 참고자료 기존 확인일: 2026-10-09.</p></details>')
 p=ROOT/'cross-validation/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="교차검증과 모형 선택">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1K폴드·OOF·점수 집계와 중첩 교차검증, 시간·집단 분할 및 모형 선택의 한계를 학습합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
