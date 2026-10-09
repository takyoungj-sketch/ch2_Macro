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
 sec('errors','오차의 정의','평가 관측마다 실제값과 예측값을 비교합니다','<p>평가 오차를 eᵢ=yᵢ−ŷᵢ로 정의하겠습니다. 양수는 낮게 예측, 음수는 높게 예측했다는 뜻입니다. 학습 자료의 잔차와 새 평가 자료의 오차는 계산 모양이 같아도 해석이 다릅니다. 어떤 자료에서 계산했는지 먼저 적어야 합니다.</p>'+g1+'<p>평균오차 ME=(1/n)Σeᵢ는 방향을 보여 주지만 양수·음수가 상쇄됩니다. 오차 −10과 +10이면 ME는 0이지만 두 예측 모두 정확하지 않습니다. ME를 단독으로 정확성 지표로 사용하지 않습니다.</p>')
 sec('definitions','MAE·MSE·RMSE','절댓값과 제곱은 큰 오차를 다르게 취급합니다','<p><strong>MAE=(1/n)Σ|eᵢ|</strong>는 절대오차의 평균입니다. 오차가 2배면 해당 항도 2배가 됩니다. 관측 하나의 큰 오차에 RMSE보다 덜 민감하지만 극단 오차의 영향이 없다는 뜻은 아닙니다.</p><p><strong>MSE=(1/n)Σeᵢ²</strong>는 제곱오차의 평균, <strong>RMSE=√MSE</strong>는 그 제곱근입니다. 오차가 2배면 제곱 항은 4배입니다. MSE의 단위는 Y단위의 제곱이고, MAE·RMSE는 원래 Y와 같은 단위입니다.</p><p>같은 관측·같은 비음수 가중치라면 RMSE≥MAE이며 모든 절대오차가 같을 때 같습니다. RMSE는 절대오차를 평균한 뒤 제곱근을 취하는 값이 아니고, 잔차 표준오차처럼 n−p로 나누는 값도 아닙니다.</p>')
 sec('ranking','지표에 따른 선택','큰 실패를 얼마나 중요하게 볼지 정합니다','<p>A의 절대오차는 0·0·0·8, B는 3·3·3·3입니다. A는 대부분 정확하지만 한 번 크게 틀리고, B는 모든 관측에서 일정하게 틀립니다.</p>'+g2+'<p>A의 MAE=(0+0+0+8)/4=2, MSE=64/4=16, RMSE=4입니다. B는 MAE=3, MSE=9, RMSE=3입니다. 어느 지표가 정답인지보다 큰 오차의 비용과 분석 목적이 무엇인지가 중요합니다.</p><p>동일 평가 표본에서 MSE와 RMSE는 단조 관계여서 후보 순위가 같습니다. 여러 폴드의 RMSE를 따로 계산해 평균한 값은 전체 오차를 합쳐 계산한 RMSE와 다를 수 있으므로 집계 방법을 밝혀야 합니다.</p>')
 sec('target','손실과 목표값','평균을 원하는지 중앙값을 원하는지도 연결됩니다','<p>기대 제곱오차를 최소화하는 점예측은 조건부 평균이며, 기대 절대오차를 최소화하는 점예측은 조건부 중앙값입니다. 필요한 모멘트가 존재한다는 조건 아래의 결과입니다. 같은 분포도 어떤 값을 대표 예측으로 내놓을지는 손실에 따라 달라집니다.</p>'+g4+'<p>비대칭 분포에서는 평균과 중앙값이 다를 수 있습니다. MAE에서 유리한 예측이 반드시 평균을 잘 추정하는 것은 아닙니다. 과소예측과 과대예측의 비용이 다르면 분위수 손실 같은 비대칭 기준을 검토할 수 있습니다. 일반 MAE·제곱오차는 같은 실제값에서 ±오차를 대칭으로 취급합니다.</p>')
 sec('mape','MAPE의 정의와 한계','백분율 오차는 실제값으로 나눕니다','<p><strong>MAPE=(100/n)Σ|(yᵢ−ŷᵢ)/yᵢ|</strong>로 정의하며 이 장은 %로 표시합니다. 일부 소프트웨어는 37%를 37 대신 0.37로 반환하므로 표시 단위를 확인하세요.</p>'+g3+'<p>실제값이 0이면 원래 정의로 계산할 수 없습니다. 분모에 작은 상수를 넣는 구현은 다른 수치 규칙이며 큰 유한값을 출력해도 문제가 사라지는 것은 아닙니다. 0을 임의로 제외하면 평가 대상이 바뀌므로 제외 규칙·건수·다른 지표를 함께 보고합니다.</p><p>0 근처 값은 상대오차를 크게 만들고, 음수나 임의 원점을 가진 척도에서는 백분율 의미가 부적절할 수 있습니다. 양수 실제값에서 MAPE는 절대오차에 1/yᵢ 가중치를 주므로 일반적인 평균·중앙값 예측과 다른 대상을 선호할 수 있습니다.</p><p>고정된 실제값에 같은 ±오차를 주면 MAPE는 같지만, 실제와 예측을 뒤집으면 분모가 바뀝니다. 예컨대 실제 100·예측 200은 100%, 실제 200·예측 100은 50%입니다. 상대 변화의 해석을 명확히 해야 합니다.</p>')
 sec('alternatives','대안과 가중치','비율 지표의 이름만으로 문제 해결을 가정하지 않습니다','<p>WAPE=100Σ|eᵢ|/Σ|yᵢ|는 총 실제 규모 대비 절대오차입니다. 전체 분모가 양수여야 하며 개별 MAPE의 단순 평균과 다릅니다. 같은 표본에서 분모가 고정이면 MAE와 순위가 같고, 큰 규모의 관측이 더 큰 영향을 줄 수 있습니다.</p><p>sMAPE의 한 정의는 (100/n)Σ[2|yᵢ−ŷᵢ|/(|yᵢ|+|ŷᵢ|)]입니다. 둘 다 0인 경우의 처리와 정의가 구현마다 다를 수 있고 0 근처 문제도 남습니다. 지표 이름만 적지 말고 산식·0 처리 규칙을 확인합니다.</p><p>관측 가중치가 있으면 가중 MAE=Σwᵢ|eᵢ|/Σwᵢ, 가중 RMSE=√[Σwᵢeᵢ²/Σwᵢ]처럼 계산합니다. 거래 한 건을 같은 비중으로 보는지, 거래금액·지역 등에 가중하는지에 따라 질문이 달라집니다. 가중치는 비음수이고 합이 양수여야 합니다.</p>')
 sec('example','공통 자료 계산','같은 평가 10건에서 세 지표를 함께 봅니다',f'<p>22장과 같이 공통 자료 1~20번으로 면적–단가 직선을 학습하고 21~30번에서 계산합니다. <strong>MAE={common["MAE"]:.2f}, RMSE={common["RMSE"]:.2f}만원/㎡, MAPE={common["MAPE"]:.2f}%</strong>입니다. 평가 자료의 실제 단가는 모두 양수이므로 이 예제의 MAPE는 정의됩니다.</p><p>한 번의 작은 번호 순 분할이며 번호는 거래 시점이 아닙니다. 실제 운영의 미래 성능 추정이 아니라 동일 예측을 서로 다른 지표로 요약하는 연습입니다. 공통 자료는 출처 미확인 학습 자료입니다.</p><p>학습 오차와 평가 오차를 섞거나 모형별로 다른 관측을 제외한 뒤 점수만 비교하지 않습니다. 로그 모형도 원 단위가 평가 목적이면 20장의 역변환·예측 대상 문제를 먼저 정리해야 합니다.</p>')
 sec('report','보고와 비교','전체 평균이 감추는 집단별 실패도 확인합니다','<p>지표에는 평가 표본·기간·지역·건수·단위·가중치·결측 및 0 처리 규칙을 붙입니다. 학습 평균·중앙값 또는 이전 시점 값 같은 기준모형도 같은 평가 자료에서 비교하되, 기준을 평가 정답으로 다시 맞추지 않습니다.</p><p>지역·유형·면적대별 오차, 큰 오차의 분위수·건수, 과소·과대예측 방향을 함께 확인합니다. 전체 MAE가 작아도 소수 집단에서 큰 오류가 날 수 있습니다. 집단별 건수가 작으면 그 요약도 불확실합니다.</p><p>모형 간 작은 점수 차이는 표본에 따라 뒤집힐 수 있습니다. 동일 관측의 오차를 짝지어 비교하고 시간·집단 의존성을 반영한 재표집이나 반복 평가를 검토합니다. 시험 점수를 반복 확인하며 모형을 선택하면 평가가 오염됩니다.</p>')
 sec('practice','확인 문제','산식과 단위, 평가 대상을 확인하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('오차 −10과 +10의 평균이 0이면 정확한가요?','방향이 상쇄된 것입니다. MAE와 RMSE는 둘 다 10입니다.'),('같은 표본에서 MSE와 RMSE의 모형 순위가 다를 수 있나요?','단일 동일 집계라면 제곱근은 단조여서 순위가 같습니다. 폴드별 집계를 다르게 하면 별도 문제입니다.'),('MAPE 계산에서 실제값 0을 빼도 되나요?','평가 대상이 달라집니다. 처리 이유·건수를 밝히고 목적에 적절한 다른 지표를 함께 사용해야 합니다.'),('MAE가 가장 작으면 조건부 평균을 가장 잘 예측하나요?','일반적으로 그렇지 않습니다. 절대손실은 중앙값, 제곱손실은 평균을 목표로 합니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','지표 이름과 함께 산식을 읽습니다','<p>CH2 Macro의 평가 수치를 읽을 때 단가·총액·로그값 중 무엇의 오차인지, 학습·검증·시험 중 어디서 계산했는지 확인하세요. 이 장의 계산을 실제 서비스 성능이라고 전제하지 않습니다.</p><p>낮은 평균 오차는 개별 거래의 정확성이나 적정가를 보장하지 않습니다. 지표·오차 분포·적용 범위를 함께 해석합니다.</p>')
 sec('recap','정리와 참고자료','목적에 맞는 지표를 미리 정합니다','<p>MAE는 절대 차이, RMSE는 큰 차이에 더 민감한 제곱 기반 요약, MAPE는 실제값 대비 상대 차이입니다. 지표를 고르기 전에 예측 대상·오류 비용·자료의 정의역을 확인하세요.</p><p>다음 <a href="/learn/stats/cross-validation/">26장 「교차검증과 모형 선택」</a>으로 이어집니다.</p><ul><li><a href="https://scikit-learn.org/stable/modules/model_evaluation.html#regression-metrics">scikit-learn: 회귀 평가 지표</a></li><li><a href="../prediction-errors-example.json">예측값·지표·손실 곡선 계산 자료</a></li></ul><p class="learn-source-note">본문·그림은 직접 구성한 가상 예제와 공통 학습 자료로 작성했습니다. 참고자료 확인: 2026-10-09.</p>')
 target_section=next(v for v in parts if 'id="target"' in v);parts.remove(target_section);parts.insert(next(i for i,v in enumerate(parts) if 'id="mape"' in v)+1,target_section)
 p=ROOT/'prediction-errors/index.html';p.parent.mkdir(exist_ok=True);html=p.read_text(encoding='utf-8') if p.exists() else (ROOT/'overfitting/index.html').read_text(encoding='utf-8').replace('https://ch2data.com/learn/stats/overfitting/','https://ch2data.com/learn/stats/prediction-errors/')
 html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="예측오차: MAE·RMSE·MAPE">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1MAE·RMSE·MAPE의 산식과 단위, 순위 차이와 0 근처 문제, 예측 대상과 평가 기준을 학습합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
