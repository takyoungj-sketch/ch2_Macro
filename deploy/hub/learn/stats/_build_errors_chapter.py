"""Chapter 25: error metrics with explicit evaluation targets."""
from pathlib import Path
from statistics import mean,median
from html import escape
import math,json,re
from _build_regression_chapter import fit
ROOT=Path(__file__).resolve().parent

def metrics(y,p):
 e=[a-b for a,b in zip(y,p)]
 return dict(errors=e,ME=mean(e),MAE=mean(abs(v) for v in e),MSE=mean(v*v for v in e),RMSE=math.sqrt(mean(v*v for v in e)),MAPE=100*mean(abs(v/a) for v,a in zip(e,y)) if all(a!=0 for a in y) else None)

def build():
 actual=[10,10,10,10];ap=[10,10,10,2];bp=[7,7,7,7];A=metrics(actual,ap);B=metrics(actual,bp);small=metrics([1,10,100],[0,9,99]);target=[1,2,9];grid=[i/20 for i in range(201)];loss=[dict(value=v,MAE=mean(abs(a-v) for a in target),MSE=mean((a-v)**2 for a in target)) for v in grid]
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];tr=rows[:20];te=rows[20:];f=fit([r['area'] for r in tr],[r['price'] for r in tr]);pred=[f['intercept']+f['slope']*r['area'] for r in te];common=metrics([r['price'] for r in te],pred)
 d=dict(description='A/B·MAPE·손실 곡선은 별도 가상 자료. 공통 30건 번호 분할은 시간 검증이 아님.',ranking=dict(actual=actual,A_predictions=ap,B_predictions=bp,A=A,B=B),small_values=dict(actual=[1,10,100],predictions=[0,9,99],metrics=small),loss=dict(actual=target,grid=loss),common=dict(train_ids=[r['id'] for r in tr],test_ids=[r['id'] for r in te],predictions=pred,metrics=common))
 (ROOT/'prediction-errors-example.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def ln(x,y,a,b):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="#94a3b8"/>'
 def fig(id,title,b,cap,h=410):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=tx(24,28,'가상 4건: A는 한 번 큰 오차, B는 매번 작은 오차')+ln(65,320,580,320)
 for i in range(4):
  for j,(m,c) in enumerate([(A,'#2563eb'),(B,'#d97706')]):
   v=abs(m['errors'][i]);xx=110+i*130+j*28;b+=f'<rect x="{xx}" y="{320-v*27}" width="24" height="{v*27}" fill="{c}"/>'+tx(xx,308-v*27,v)
  b+=tx(110+i*130,350,f'{i+1}번')
 for v in [0,2,4,6,8]:b+=tx(25,325-v*27,v)
 b+=tx(24,385,'세로: 절대오차 · 파랑 A / 주황 B · 단위 없는 가상 값')
 g1=fig('errors','관측별 절대오차',b,'그림 1. 실제값은 모두 10, A 예측은 10·10·10·2, B 예측은 7·7·7·7입니다. 평가 표본을 바꾸지 않고 오차 분포만 비교합니다.')
 b=tx(24,28,'같은 예측도 지표에 따라 순위가 달라집니다')+ln(65,320,580,320)
 for i,key in enumerate(['MAE','RMSE']):
  for j,(m,c) in enumerate([(A,'#2563eb'),(B,'#d97706')]):
   xx=170+i*240+j*65;v=m[key];b+=f'<rect x="{xx}" y="{320-v*50}" width="50" height="{v*50}" fill="{c}"/>'+tx(xx+15,308-v*50,f'{v:.1f}')
  b+=tx(195+i*240,350,key)
 for v in [0,1,2,3,4]:b+=tx(25,325-v*50,v)
 b+=tx(24,385,'파랑 A / 주황 B · 낮을수록 좋음 · 두 지표 모두 Y와 같은 단위')
 g2=fig('ranking','MAE와 RMSE의 순위 역전',b,'그림 2. A는 MAE 2로 B의 3보다 작지만 RMSE 4로 B의 3보다 큽니다. 큰 오차에 더 큰 비중을 주면 선택이 달라질 수 있습니다.')
 b=tx(24,28,'절대오차가 모두 1이어도 상대오차는 다릅니다')+ln(65,320,580,320)
 for i,v in enumerate([1,10,100]):
  ape=100/v;xx=140+i*170;b+=f'<rect x="{xx}" y="{320-ape*2.2}" width="70" height="{ape*2.2}" fill="#2563eb"/>'+tx(xx+15,308-ape*2.2,f'{ape:.0f}%')+tx(xx-5,350,f'실제값 {v}')
 for v in [0,50,100]:b+=tx(25,325-v*2.2,v)
 b+=tx(24,385,'세로: 절대 백분율 오차(%) · 예측은 각각 실제값보다 1 작음')
 g3=fig('mape','MAPE와 작은 분모',b,'그림 3. 별도 가상 값 1·10·100의 APE는 100%·10%·1%, MAPE는 37%입니다. MAPE는 작은 실제값의 같은 절대오차에 더 큰 비중을 줍니다.')
 b=tx(24,28,'가상 실제값 1·2·9에 상수 c를 예측한다면')
 for j,(key,maxv) in enumerate([('MAE',10),('MSE',60)]):
  left=65+j*300;b+=ln(left,315,left+235,315)+tx(left,65,key)
  pts=' '.join(f"{left+r['value']*23},{315-r[key]/maxv*220}" for r in loss);b+='<polyline data-loss="'+key+'" points="'+pts+'" fill="none" stroke="#2563eb" stroke-width="2"/>'
  optimum=2 if key=='MAE' else 4;val=mean(abs(a-optimum) for a in target) if key=='MAE' else mean((a-optimum)**2 for a in target)
  b+=f'<circle cx="{left+optimum*23}" cy="{315-val/maxv*220}" r="5" fill="#d97706"/>'+tx(left,380,f'최소점 c={optimum}: '+('중앙값' if key=='MAE' else '평균'))
  for v in [0,5,10]:b+=tx(left+v*23-3,342,v)
  for v in [0,maxv/2,maxv]:b+=tx(left-32,320-v/maxv*220,f'{v:g}')
 g4=fig('target','손실과 예측 대상',b,'그림 4. 가로축은 상수 예측 c입니다. 왼쪽은 MAE, 오른쪽은 MSE이며 세로 척도·단위가 다릅니다. 같은 곡선의 높이를 직접 비교하는 그림이 아닙니다.')
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','학습 목표','예측이 얼마나 틀렸는지 어떻게 비교할까요?','<p>대부분 잘 맞히지만 가끔 크게 틀리는 모형과 매번 조금씩 틀리는 모형이 있습니다. 어느 쪽이 더 나은지는 오차를 어떻게 모아 비교하느냐에 따라 달라집니다. 예측 지표는 이런 차이를 하나의 숫자로 요약하는 방법입니다.</p><p>이 장에서는 같은 예측에 MAE·RMSE·MAPE를 적용해 보고, 지표마다 무엇을 중요하게 보는지 살펴봅니다. 계산값뿐 아니라 단위, 작은 실제값의 영향, 평가에 포함한 관측도 함께 확인합니다.</p><ul class="learn-objectives"><li>실제값과 예측값으로 MAE·MSE·RMSE·MAPE를 계산합니다.</li><li>큰 오차와 작은 실제값이 각 지표에 미치는 영향을 설명합니다.</li><li>손실의 선택이 평균·중앙값 예측과 어떻게 연결되는지 이해합니다.</li><li>같은 평가 자료와 기준으로 모형을 비교하고 결과를 보고합니다.</li></ul>')
 sec('errors','오차의 정의','실제값에서 예측값을 빼 봅니다','<p>이 장에서는 <strong>오차 eᵢ = 실제값 yᵢ − 예측값 ŷᵢ</strong>로 정합니다. 실제값이 10인데 7로 예측했다면 오차는 +3입니다. 양수는 실제보다 낮게, 음수는 실제보다 높게 예측했다는 뜻입니다.</p>'+g1+'<p>오차를 그대로 평균한 <strong>평균오차(ME)</strong>는 예측이 어느 방향으로 치우치는지 보여 줍니다. 다만 −10과 +10을 평균하면 0이 됩니다. 두 예측이 모두 틀려도 상쇄될 수 있으므로 정확성을 평가할 때는 절댓값이나 제곱을 이용합니다.</p><p>학습 자료에서 구한 잔차와 새 자료에서 구한 예측 오차는 계산 모양이 같아도 의미가 다릅니다. 어떤 자료에서 평가한 결과인지 먼저 밝혀야 합니다.</p>')
 sec('definitions','MAE·MSE·RMSE','절댓값으로 평균할지, 제곱해서 평균할지 정합니다','<p><strong>MAE(평균절대오차)</strong>는 오차의 절댓값을 평균한 값입니다. MAE = Σ|eᵢ|/n입니다. 절대오차가 2배가 되면 그 관측이 합계에 더하는 값도 2배가 됩니다. 예를 들어 절대오차가 1·2·3이면 MAE는 2입니다.</p><p><strong>MSE(평균제곱오차)</strong>는 오차를 제곱한 뒤 평균한 값이고, <strong>RMSE(평균제곱근오차)</strong>는 MSE의 제곱근입니다. MSE = Σeᵢ²/n, RMSE = √MSE입니다. 오차가 2배면 제곱 항은 4배가 되므로 큰 오차에 더 민감합니다.</p><p>MAE와 RMSE는 Y와 같은 단위입니다. 점수를 예측했다면 둘 다 ‘점’으로 읽습니다. MSE의 단위는 그 제곱인 ‘점²’입니다. RMSE는 절대오차의 평균에 제곱근을 씌운 값이 아니며, 잔차 표준오차처럼 n−p로 나누지도 않습니다.</p><p>같은 관측에 같은 비음수 가중치를 적용하면 RMSE는 MAE보다 작지 않습니다. 모든 절대오차가 같으면 두 값도 같습니다. MAE가 큰 오차에 덜 민감하더라도 그 영향을 전혀 받지 않는 것은 아닙니다.</p>')
 sec('ranking','지표에 따른 선택','한 번의 큰 오차와 여러 번의 작은 오차를 비교합니다','<p>그림 1의 A는 절대오차가 0·0·0·8이고 B는 3·3·3·3입니다. A는 네 번 중 세 번 정확하지만 한 번 크게 틀립니다. B는 네 번 모두 같은 크기로 틀립니다.</p>'+g2+'<p>A의 MAE는 (0+0+0+8)/4 = 2입니다. MSE는 64/4 = 16이고 RMSE는 4입니다. B는 MAE와 RMSE가 모두 3입니다. 따라서 MAE로는 A가, RMSE로는 B가 더 좋습니다. 큰 실패에 어느 정도의 비용을 두는지에 따라 선택이 달라집니다.</p><p>같은 평가 자료에서 하나로 집계한 MSE와 RMSE는 후보 순위가 같습니다. 제곱근을 취해도 값의 순서는 바뀌지 않기 때문입니다. 다만 자료를 여러 묶음으로 나누어 구한 RMSE의 평균과 전체 오차를 합쳐 구한 RMSE는 다를 수 있습니다. 집계 방식도 함께 적어야 합니다.</p>')
 sec('target','손실과 목표값','평균을 예측할지 중앙값을 예측할지도 연결됩니다','<p>실제값이 1·2·9일 때 세 값 모두에 같은 숫자 c를 예측한다고 해 봅시다. 절대오차의 평균을 가장 작게 만드는 c는 중앙값 2입니다. 제곱오차의 평균을 가장 작게 만드는 c는 평균 4입니다.</p>'+g4+'<p>이 원리는 입력 X가 주어진 예측에도 이어집니다. 필요한 기대값이 존재할 때, 기대 제곱오차를 최소화하는 예측은 <strong>조건부 평균</strong>이고 기대 절대오차를 최소화하는 예측은 <strong>조건부 중앙값</strong>입니다. 평균과 중앙값이 다른 분포에서는 좋은 예측값도 손실에 따라 달라질 수 있습니다.</p><p>일반 MAE와 제곱오차는 같은 실제값을 기준으로 +오차와 −오차를 대칭으로 취급합니다. 과소예측과 과대예측의 비용이 다르다면 분위수 손실처럼 비대칭적인 기준도 고려할 수 있습니다.</p>')
 sec('mape','MAPE의 정의와 한계','같은 오차도 실제값이 작으면 비율이 커집니다','<p><strong>MAPE(평균절대백분율오차)</strong>는 각 절대오차를 실제값의 절댓값으로 나눈 뒤 평균해 %로 표시합니다. MAPE = (100/n)Σ|(yᵢ−ŷᵢ)/yᵢ|입니다. 실제값 10을 9로 예측하면 절대오차는 1이고 절대백분율오차(APE)는 10%입니다.</p>'+g3+'<p>실제값 1·10·100을 각각 0·9·99로 예측하면 절대오차는 모두 1입니다. 하지만 APE는 100%·10%·1%이고 MAPE는 (100+10+1)/3 = 37%입니다. 같은 절대오차라도 작은 실제값에서 더 큰 영향을 줍니다.</p><p><strong>실제값이 0이면 원래 산식으로 계산할 수 없습니다.</strong> 0 근처에서도 값이 매우 커질 수 있습니다. 분모에 작은 상수를 넣거나 0인 관측을 빼는 것은 계산 규칙이나 평가 대상을 바꾸는 일입니다. 처리 방법과 관측 수를 밝히고 다른 지표도 함께 살펴야 합니다.</p><p>백분율이 의미 있는 척도인지도 확인합니다. 음수가 있거나 섭씨온도처럼 0이 임의의 기준인 척도에서는 해석이 부적절할 수 있습니다. 소프트웨어에 따라 37%를 37 또는 0.37로 반환하므로 표시 단위도 확인해야 합니다.</p><details><summary>MAPE의 가중치와 비교 방향</summary><p>양수인 실제값에서는 절대오차에 1/yᵢ의 가중치를 주는 셈입니다. 따라서 일반적인 평균이나 중앙값 예측과 다른 값을 선호할 수 있습니다. 같은 실제값에서 같은 크기의 ±오차는 같게 평가하지만, 실제값과 예측값을 뒤집으면 분모가 달라집니다. 실제 100·예측 200의 오차율은 100%, 실제 200·예측 100은 50%입니다.</p></details>')
 sec('alternatives','대안과 가중치','비율 지표도 산식과 가중치를 확인합니다','<p><strong>WAPE</strong>는 개별 오차율의 평균 대신 전체 실제값 규모에 대한 절대오차의 비율을 구합니다. WAPE = 100Σ|eᵢ|/Σ|yᵢ|이며 전체 분모가 양수여야 합니다. MAPE와 다른 지표이고, 같은 평가 표본에서는 분모가 고정되어 MAE와 후보 순위가 같습니다.</p><p><strong>가중 지표</strong>는 관측마다 다른 비중을 줍니다. 모든 학생을 같은 비중으로 볼지, 학교별 비중을 같게 맞출지에 따라 묻는 질문이 달라집니다. 가중 MAE = Σwᵢ|eᵢ|/Σwᵢ, 가중 RMSE = √[Σwᵢeᵢ²/Σwᵢ]로 계산합니다. 가중치는 비음수이고 합은 양수여야 합니다.</p><details><summary>sMAPE를 사용할 때</summary><p>sMAPE의 한 정의는 (100/n)Σ[2|yᵢ−ŷᵢ|/(|yᵢ|+|ŷᵢ|)]입니다. 실제값과 예측값이 모두 0일 때의 처리나 상수 배율이 구현마다 다를 수 있고 0 근처의 민감성도 남습니다. 이름만 보고 문제가 해결된다고 생각하기보다 산식과 처리 규칙을 확인합니다.</p></details>')
 sec('example','예제 계산','같은 예측을 세 지표로 요약해 봅니다',f'<p>22장에서 사용한 공통 학습 자료의 두 수치 열을 단위 없는 X와 Y로 놓습니다. 1~20번 관측으로 X에서 Y를 예측하는 직선을 학습하고, 남겨 둔 21~30번 관측에서 평가합니다. 같은 10개 예측으로 계산한 결과는 <strong>MAE={common["MAE"]:.2f}, RMSE={common["RMSE"]:.2f}, MAPE={common["MAPE"]:.2f}%</strong>입니다.</p><p>평가 자료의 Y가 모두 양수이므로 이 예제의 MAPE를 계산할 수 있습니다. MAE와 RMSE는 Y와 같은 단위이고 MAPE는 %입니다. RMSE가 MAE보다 큰 것은 오차의 크기가 관측마다 다르기 때문입니다.</p><p>이 예제는 작은 자료를 번호순으로 한 번 나눈 계산 연습입니다. 번호가 시간 순서를 뜻하지 않으며, 앞으로의 성능을 확인한 결과로 해석하지 않습니다. 원자료는 출처가 확인되지 않은 학습용 자료입니다.</p><p>모형을 비교할 때는 학습 오차와 평가 오차를 섞거나 서로 다른 관측을 제외한 점수를 나란히 놓지 않습니다. 로그로 학습한 모형을 원래 단위에서 평가하려면 20장에서 살펴본 역변환과 예측 대상도 먼저 정해야 합니다.</p>')
 sec('report','보고와 비교','평균 점수 옆에 평가 조건과 오차 분포를 적습니다','<p>평가 표본, 기간, 관측 수, 단위, 가중치, 결측값과 0의 처리 방법을 함께 보고합니다. 학습 평균·중앙값이나 이전 시점 값처럼 단순한 기준모형도 같은 자료에서 비교하면 개선 정도를 이해하기 쉽습니다. 기준모형의 예측 기준을 평가 정답으로 다시 맞추지는 않습니다.</p><p>전체 평균만으로는 특정 집단의 큰 실패가 가려질 수 있습니다. 학년·학교별 오차, 큰 오차의 분위수와 관측 수, 과소·과대예측의 방향도 살펴봅니다. 집단의 관측 수가 작으면 그 요약값도 불안정할 수 있습니다.</p><p>작은 점수 차이는 평가 표본이 바뀌면 뒤집힐 수 있습니다. 같은 관측에 대한 두 모형의 오차를 짝지어 비교하고, 반복 평가나 재표집을 할 때는 시간·집단의 의존성도 반영합니다. 시험 점수를 반복 확인하며 후보를 고르면 독립적인 최종 평가가 되지 않는다는 점도 기억해야 합니다.</p>')
 sec('practice','확인 문제','산식과 단위, 평가 대상을 확인하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('오차 −10과 +10의 평균이 0이면 정확한가요?','방향이 상쇄된 것입니다. MAE와 RMSE는 둘 다 10입니다.'),('같은 표본에서 MSE와 RMSE의 모형 순위가 다를 수 있나요?','단일 동일 집계라면 제곱근은 단조여서 순위가 같습니다. 폴드별 집계를 다르게 하면 별도 문제입니다.'),('MAPE 계산에서 실제값 0을 빼도 되나요?','평가 대상이 달라집니다. 처리 이유·건수를 밝히고 목적에 적절한 다른 지표를 함께 사용해야 합니다.'),('MAE가 가장 작으면 조건부 평균을 가장 잘 예측하나요?','일반적으로 그렇지 않습니다. 절대손실은 중앙값, 제곱손실은 평균을 목표로 합니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','지표 이름과 함께 산식을 읽습니다','<p>CH2 Macro의 평가 수치를 읽을 때 단가·총액·로그값 중 무엇의 오차인지, 학습·검증·시험 중 어디서 계산했는지 확인하세요. 이 장의 계산을 실제 서비스 성능이라고 전제하지 않습니다.</p><p>낮은 평균 오차는 개별 거래의 정확성이나 적정가를 보장하지 않습니다. 지표·오차 분포·적용 범위를 함께 해석합니다.</p>')
 sec('recap','학습 요약','지표는 어떤 오차를 중요하게 볼지 정하는 기준입니다','<ul class="learn-recap-list"><li><strong>MAE</strong>는 절대오차의 평균입니다. <strong>RMSE</strong>는 제곱을 이용하므로 큰 오차에 더 민감합니다. 두 지표는 Y와 같은 단위입니다.</li><li><strong>MSE</strong>는 제곱 단위이고 같은 평가 자료에서 RMSE와 후보 순위가 같습니다.</li><li><strong>MAPE</strong>는 실제값 대비 백분율 오차입니다. 실제값이 0이면 정의되지 않고 작은 값에 민감합니다.</li><li>절대손실은 중앙값, 제곱손실은 평균 예측과 연결됩니다. 목적과 실패 비용에 맞춰 지표를 정합니다.</li><li>같은 자료와 계산 규칙으로 비교하고, 집단별 오차와 평가 조건도 함께 보고합니다.</li></ul><p>다음 <a href="/learn/stats/cross-validation/">26장 「교차검증과 모형 선택」</a>에서는 자료를 여러 번 나누어 후보를 비교하는 방법을 살펴봅니다.</p><details class="learn-references"><summary>참고자료와 예제 데이터</summary><ul><li><a href="https://scikit-learn.org/stable/modules/model_evaluation.html#regression-metrics">scikit-learn: 회귀 평가 지표</a></li><li><a href="../prediction-errors-example.json">예측값·지표·손실 곡선 계산 자료</a></li></ul><p class="learn-source-note">본문·그림은 직접 구성한 가상 예제와 공통 학습 자료로 작성했습니다. 참고자료 기존 확인일: 2026-10-09.</p></details>')
 target_section=next(v for v in parts if 'id="target"' in v);parts.remove(target_section);parts.insert(next(i for i,v in enumerate(parts) if 'id="mape"' in v)+1,target_section)
 p=ROOT/'prediction-errors/index.html';p.parent.mkdir(exist_ok=True);html=p.read_text(encoding='utf-8') if p.exists() else (ROOT/'overfitting/index.html').read_text(encoding='utf-8').replace('https://ch2data.com/learn/stats/overfitting/','https://ch2data.com/learn/stats/prediction-errors/')
 html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="예측오차: MAE·RMSE·MAPE">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1MAE·RMSE·MAPE의 산식과 단위, 순위 차이와 0 근처 문제, 예측 대상과 평가 기준을 학습합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
