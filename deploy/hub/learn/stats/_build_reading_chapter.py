"""Chapter 32: interpretation workflow and reproducible course recap."""
from pathlib import Path
from statistics import mean,median,stdev
from html import escape
import json,re,math
from scipy.stats import t,linregress
ROOT=Path(__file__).resolve().parent

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];y=[r['price'] for r in rows];x=[r['area'] for r in rows]
 fit=linregress(x,y);mu=mean(y);half=float(t.ppf(.975,29))*stdev(y)/math.sqrt(30)
 def evaluate(train,test):
  m=linregress([r['area'] for r in train],[r['price'] for r in train]);return mean(abs(r['price']-(m.intercept+m.slope*r['area'])) for r in test)
 errs=[evaluate(rows,rows),evaluate(rows[:20],rows[20:]),mean(evaluate(rows[:i]+rows[i+10:],rows[i:i+10]) for i in [0,10,20])]
 effects=[dict(label='A: 작은 효과·좁은 구간',estimate=.2,low=.1,high=.3),dict(label='B: 큰 추정·넓은 구간',estimate=2,low=-1,high=5),dict(label='C: 작고 불확실',estimate=0,low=-.5,high=.5)]
 d=dict(source='공통 30건: 실제 거래 출처 미확인 학습 자료. 효과 크기 패널은 별도 가상 예제.',mean=mu,median=median(y),mean_ci=[mu-half,mu+half],slope=fit.slope,intercept=fit.intercept,r_squared=fit.rvalue**2,mae=errs,area_range=[min(x),max(x)],effects=effects)
 (ROOT/'reading-results-example.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def ln(x,y,a,b,c='#94a3b8'):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="{c}"/>'
 def fig(id,title,b,cap):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 410" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=tx(24,28,'결과를 읽는 다섯 단계')
 for i,(a,c) in enumerate([('1. 질문','무엇을 알고 싶은가?'),('2. 자료','누구·언제·어떤 단위인가?'),('3. 방법','가정과 비교 기준은 무엇인가?'),('4. 결과','크기·불확실성·오차는?'),('5. 적용','어디까지 말할 수 있는가?')]):
  yy=55+i*64;b+=f'<rect x="65" y="{yy}" width="510" height="49" rx="5" fill="#eaf2ff"/>'+tx(80,yy+29,a)+tx(245,yy+29,c)
  if i<4:b+=ln(320,yy+49,320,yy+64)
 g1=fig('workflow','결과 읽기 순서',b,'그림 1. 숫자를 평가하기 전에 질문과 자료 범위를 확인합니다. 필요한 조건이 확인되지 않으면 결론을 좁히거나 추가 자료를 요청합니다.')
 b=tx(24,28,'별도 가상 효과 추정: 0과 비교하고 크기도 봅니다')+ln(160,330,590,330)+ln(160+70,55,160+70,330)
 for i,v in enumerate(effects):
  yy=115+i*80;lo=160+(v['low']+1)*70;hi=160+(v['high']+1)*70;xx=160+(v['estimate']+1)*70
  b+=tx(20,yy-25,v['label'])+ln(lo,yy,hi,yy,'#2563eb')+ln(lo,yy-6,lo,yy+6,'#2563eb')+ln(hi,yy-6,hi,yy+6,'#2563eb')+f'<circle cx="{xx}" cy="{yy}" r="5" fill="#2563eb"/>'
 for v in [-1,0,1,2,3,4,5]:b+=tx(155+(v+1)*70,355,v)
 b+=tx(24,390,'가로: 효과 크기(가상 단위) · 점 추정 / 선 95% 신뢰구간')
 g2=fig('uncertainty','효과 크기와 신뢰구간',b,'그림 2. 실제 분석에서 산출한 값이 아닌 설명용 추정·구간입니다. 같은 검정과 대응하는 구간을 가정하면 A는 0을 제외하지만 효과는 작고, B는 큰 효과도 0도 포함합니다.')
 b=tx(24,28,'같은 공통 자료·같은 직선 모형, 다른 평가 설계')+ln(185,335,555,335)
 for i,(name,v) in enumerate(zip(['30건 재대입','20건 학습→10건 확인','번호 블록 3폴드'],errs)):
  yy=90+i*80;w=v*7;b+=tx(20,yy+22,name)+f'<rect x="185" y="{yy}" width="{w}" height="32" fill="#2563eb"/>'+tx(195+w,yy+22,f'{v:.2f}')
 for v in [0,20,40,50]:b+=tx(180+v*7,360,v)
 b+=tx(24,390,'가로: MAE(만원/㎡) · 낮을수록 해당 평가의 절대오차가 작음')
 g3=fig('prediction','평가 자료가 다른 오차',b,'그림 3. 세 값은 서로 다른 알고리즘 순위가 아닙니다. 같은 직선 적합 절차라도 사용한 학습·평가 자료가 다릅니다. 번호 블록은 시간 분할이 아닙니다.')
 b=tx(24,28,'적용 범위: 면적 안쪽이라도 다른 조건을 확인합니다')+ln(65,220,590,220)+f'<rect x="{65+22*1.45}" y="180" width="{(310-22)*1.45}" height="40" fill="#dbeafe"/>'+tx(190,205,'학습 자료 면적 22~310㎡')
 for v in [0,22,100,200,310,350]:b+=ln(65+v*1.45,220,65+v*1.45,230)+tx(55+v*1.45,250,v)
 b+=tx(65,110,'0㎡: 절편의 위치, 자료 범위 밖')+tx(65,300,'범위 안: 지역·용도·시점·변수 조합이 다를 수 있음')+tx(65,345,'범위 밖: 직선을 연장한 계산과 신뢰할 만한 예측은 다름')+tx(24,390,'가로: 면적(㎡) · 파란 영역은 관측된 최소~최대 범위')
 g4=fig('scope','관측 범위와 적용 범위',b,'그림 4. 최소·최대 사이를 칠한 것은 모든 면적에서 충분한 자료가 있다는 뜻이 아닙니다. 다른 지역·미래 시점으로 옮길 때는 분포 변화도 확인해야 합니다.')
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('workflow','결과 읽기의 순서','숫자를 질문·자료·방법에 연결합니다','<p>이 장은 새로운 모형을 추가하기보다 앞의 31개 장에서 배운 개념을 하나의 읽기 절차로 묶습니다. 전체 과정을 마친 뒤 종합 점검에 쓰거나, 결과를 해석하다 막힌 부분의 연결 장으로 돌아가는 안내로 사용할 수 있습니다.</p>'+g1+'<p>기술통계는 관측 자료를 요약하고, 추론은 가정 아래 모집단의 특성을 추정하며, 예측은 아직 보지 않은 관측의 목표를 맞추려 합니다. 인과 질문은 어떤 조건을 바꾸었을 때 결과가 어떻게 달라질지를 묻습니다. 같은 숫자를 이 네 질문의 답으로 바꾸어 읽지 마세요.</p>')
 sec('data','대상·단위·자료','누가 포함되고 누가 빠졌는지 확인합니다','<p>지역·기간·용도·관측 단위·표본 수를 먼저 확인합니다. 거래 100건, 건물 100개, 단지 100개는 다른 자료입니다. 같은 단지의 반복 거래는 서로 독립적이지 않을 수 있으며, 관측 수가 많아도 대표성과 독립성이 자동으로 확보되지는 않습니다.</p><p>총액과 단가, 건수 가중과 면적 가중, 명목값과 물가를 조정한 값도 구별해야 합니다. 결측·중복·이상치 필터로 빠진 관측을 확인하고 필터 전후 건수와 요약치 변화를 비교하세요. IQR 기준으로 제외되었다는 사실만으로 입력 오류라고 단정할 수 없습니다.</p><p>기간별 평균 차이는 같은 유형의 값이 달라져서 생길 수도 있고 거래 구성비가 바뀌어서 생길 수도 있습니다. 자료 정의와 구성 변화를 함께 살펴야 합니다. 복습: <a href="/learn/stats/population-and-sampling/">02장 표본과 편향</a>, <a href="/learn/stats/iqr-outliers/">07장 이상치</a>.</p>')
 sec('summary','공통 자료 종합','평균·기울기·설명력은 다른 질문의 답입니다',f'<p>공통 예제 30건의 평균 단가는 {mu:.2f}, 중앙값은 {median(y):g}만원/㎡입니다. 평균은 합계를 건수로 나눈 중심, 중앙값은 정렬했을 때 가운데 위치입니다. 둘의 차이는 분포를 더 살펴보라는 단서이지 어느 하나가 항상 옳다는 뜻은 아닙니다.</p><p>독립 표본과 평균 추론 가정을 적용한 t 방식의 평균 95% 신뢰구간은 {mu-half:.2f}~{mu+half:.2f}만원/㎡입니다. 이 자료는 실제 거래 출처와 표집 설계가 확인되지 않은 학습 예제이므로 이 계산을 특정 지역 모집단의 검증된 구간으로 제시할 수 없습니다.</p><p>30건에 면적 하나를 넣은 직선의 기울기는 {fit.slope:.3f}, R²는 {fit.rvalue**2:.3f}입니다. 기울기는 이 모형에서 면적 1㎡ 차이에 대응하는 예측 단가 차이(만원/㎡)이며, 면적을 바꾸었을 때 생기는 인과효과가 아닙니다. R²는 같은 자료에서 평균만 쓸 때보다 제곱오차를 줄인 비율이지 정확도나 인과 설명 비율이 아닙니다.</p>')
 sec('uncertainty','효과와 불확실성','0과 다른지와 실질적으로 큰지를 나누어 봅니다',g2+'<p>p값은 귀무가설과 검정 모형이 맞는다는 조건에서 관측값만큼 또는 더 극단적인 통계량을 얻을 확률입니다. 귀무가설이 참일 확률이나 효과가 클 확률이 아닙니다. 작은 효과도 표본이 크면 작은 p값을 가질 수 있습니다.</p><p>신뢰구간은 추정의 정밀도와 자료가 허용하는 효과 범위를 보여 줍니다. 0을 포함한다고 효과가 없다고 입증한 것은 아니며, 0을 제외한다고 실무적으로 중요하다고 입증한 것도 아닙니다. 중요하다고 볼 최소 크기는 목적과 단위를 고려해 정하고, 동등성을 주장하려면 그에 맞는 검정·구간을 사용해야 합니다.</p><p>95% 신뢰수준은 같은 절차를 반복할 때 참값을 포함하는 구간의 비율을 뜻합니다. 평균의 신뢰구간을 개별 거래의 95% 범위로 읽지 마세요. 개별 관측의 변동까지 포함하는 예측구간과 구별합니다. 복습: <a href="/learn/stats/confidence-intervals/">12장</a>, <a href="/learn/stats/hypothesis-tests/">13장</a>.</p>')
 sec('prediction','예측 성능','무엇으로 학습하고 어디에서 평가했는지 묻습니다',g3+'<p>재대입 오차는 학습에 사용한 관측으로 다시 평가한 값이고, 홀드아웃과 교차검증은 학습에서 빠진 관측을 예측합니다. 모형을 비교할 때는 평가 관측·척도·전처리·분할 설계가 같아야 합니다. 평균이나 중앙값만 쓰는 기준 모형과 비교하면 복잡한 모형이 실제로 도움이 되는지도 볼 수 있습니다.</p><p>MAE는 목표와 같은 단위의 평균 절대오차, RMSE는 큰 오차에 더 민감한 지표입니다. MAPE는 실제값이 작거나 0일 때 문제가 생길 수 있습니다. 평균 오차와 함께 표본 수·오차 분포·큰 오차·집단별 성능도 확인하세요. 평균 오차가 모든 관측의 오차 한도는 아닙니다.</p><p>교차검증으로 모형을 선택했다면 그 최소 점수를 독립적인 최종 성능으로 간주하지 않습니다. 반복 단지·시간 순서를 고려하고, 시험 자료를 선택에 사용하지 않았는지 확인합니다. 미래 환경이 달라지면 과거 평가가 유지된다는 보장도 없습니다. 복습: <a href="/learn/stats/train-validation-test/">23장</a>, <a href="/learn/stats/prediction-errors/">25장</a>, <a href="/learn/stats/cross-validation/">26장</a>.</p>')
 sec('scope','적용과 외삽','계산 가능한 범위와 근거 있는 범위를 구별합니다',g4+f'<p>공통 직선의 절편 {fit.intercept:.2f}는 면적 0㎡에서의 모형 값이며 관측 범위 밖입니다. 310㎡의 예측도 {fit.intercept+fit.slope*310:.2f}만원/㎡로 관측 최소 단가 62보다 낮습니다. 범위 안이라는 이유만으로 모든 예측이 타당한 것은 아니므로 잔차·자료 밀도·모형 형태를 함께 점검합니다.</p><p>지역·용도·기간·수집 방식이 달라지면 같은 계수나 오차를 그대로 옮길 수 없습니다. 회귀에서 다른 변수를 통제했다는 말도 측정하지 못한 교란이나 선택 편향을 없앴다는 뜻은 아닙니다. 인과효과를 말하려면 연구 설계와 식별 가정이 추가로 필요합니다.</p>')
 sec('selection','분석 선택과 재현','유리한 결과만 남지 않았는지 확인합니다','<p>많은 지역·기간·변수를 시험한 뒤 가장 작은 p값만 보고하면 우연한 발견이 늘어납니다. 사전에 정한 분석과 사후 탐색을 구별하고 비교 횟수·다중검정 처리·선택 과정을 기록하세요. 같은 자료로 가설을 만들고 검증한 결과는 독립 재현과 다릅니다.</p><p>필터·집계·변수 변환·모형·평가 분할을 기록해야 같은 결과를 다시 만들 수 있습니다. 다른 합리적인 선택을 했을 때 결론이 유지되는지 민감도 분석을 하고, 누락 자료나 대표성 부족처럼 계산으로 해결되지 않는 한계도 남겨 둡니다.</p>')
 sec('report','해석 문장 작성','대상·수치·근거·한계를 한 문장씩 적습니다','<p><strong>피해야 할 문장:</strong> “면적이 커지면 단가가 반드시 하락하고, R² 0.42이므로 42% 정확하다.”</p><p><strong>고쳐 쓴 문장:</strong> “출처가 확인되지 않은 학습 예제 30건에서 면적만 사용한 직선은 음의 기울기를 보였다. 이는 해당 자료의 연관성을 요약하며 인과효과를 뜻하지 않는다. 학습 R²는 약 0.42이고, 번호 1~20으로 학습한 모형의 21~30번 확인 MAE는 약 41.08만원/㎡였다. 이 평가를 다른 지역이나 개별 물건에 그대로 적용할 수는 없다.”</p><p>실제 보고서는 먼저 대상·기간·단위·필터를 밝히고, 추정치와 불확실성 또는 평가 오차를 제시한 뒤 결론의 범위를 적습니다. 아직 모르는 부분과 다음에 확인할 자료를 구체적으로 남기면 판단의 근거가 명확해집니다.</p>')
 sec('practice','종합 확인 문제','숫자를 적절한 질문에 연결하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('평균의 95% 신뢰구간에 거래 95%가 들어가나요?','아닙니다. 모집단 평균의 추정 구간이며 개별 거래의 분포 구간과 다릅니다.'),('R²가 더 높으면 미래 예측도 더 정확한가요?','학습 적합도만으로 알 수 없습니다. 같은 독립 평가 자료에서 목적에 맞는 오차를 비교해야 합니다.'),('p값이 0.05보다 크면 효과가 없나요?','효과가 없다고 입증한 것이 아닙니다. 추정치·구간 폭·검정력과 의미 있는 효과 범위를 함께 봅니다.'),('군집 2를 군집 1보다 우수한 시장이라고 부를 수 있나요?','번호는 임의의 라벨입니다. 군집 특성과 분석 목적을 설명하되 우열이나 인과적 유형으로 단정하지 않습니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 활용','결과 화면에서 여섯 가지를 확인합니다','<ol><li><strong>범위:</strong> 지역·기간·용도와 관심 대상이 맞는가?</li><li><strong>단위:</strong> 거래·건물·단지 중 무엇이며 총액·단가·가중 방식은 무엇인가?</li><li><strong>포함:</strong> 표본 수와 필터 전후 제외 건은 어떻게 달라지는가?</li><li><strong>방법:</strong> 단순 요약·회귀·검정·예측 중 무엇이며 가정은 무엇인가?</li><li><strong>불확실성:</strong> 구간·잔차·평가 오차와 비교 기준이 제시되어 있는가?</li><li><strong>한계:</strong> 인과·외삽·개별 적정가로 확대 해석하지 않았는가?</li></ol><p>화면에 없는 구간이나 검증 방식을 있다고 가정하지 말고 설명과 산출 조건을 확인하세요. 이 과정은 시장과 집단 통계를 읽기 위한 기초이며 개별 감정평가나 투자 판단을 대신하지 않습니다.</p><p class="learn-macro-cta"><a href="https://macro.ch2data.com/">CH2 Macro에서 확인하기 →</a></p>')
 sec('recap','과정 마무리','필요한 개념으로 돌아갈 수 있으면 충분합니다','<p>모든 공식을 외우기보다 지금 보고 있는 숫자가 어떤 질문의 답인지 설명할 수 있는지를 점검하세요. 기술통계는 분포, 추론은 가정과 불확실성, 회귀는 관계와 진단, 머신러닝은 평가 설계와 일반화에 초점을 맞춥니다.</p><p><a href="/learn/stats/">전체 32장 목차로 돌아가기</a> · <a href="../reading-results-example.json">이 장의 요약 수치와 가상 효과 구간</a></p><p class="learn-source-note">공통 자료의 출처·표집 설계는 확인되지 않았으며 학습 계산에만 사용했습니다. 그림 2의 효과 추정과 구간은 별도 가상 예제입니다.</p>')
 p=ROOT/'reading-results/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="통계 결과를 읽고 판단하는 법">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1자료 범위, 효과 크기와 불확실성, 예측 오차와 적용 한계를 종합해 통계 결과를 읽는 방법을 학습합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
