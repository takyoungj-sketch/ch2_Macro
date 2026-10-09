"""Generate chapter 07 with reproducible fences and sensitivity figures."""
from pathlib import Path
from statistics import mean,median,pstdev
from html import escape
import json,re
from _build_quantiles_chapter import summary
ROOT=Path(__file__).resolve().parent

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];values=[r['price'] for r in rows]
 def t(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def line(x,y,xx,yy,extra=''):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="#64748b" {extra}/>'
 def fig(id,title,b,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=t(24,28,'울타리는 계산한 경계, 수염 끝은 실제 관측값입니다')
 x=lambda v:110+v*.95
 b+=line(x(62),90,x(268),90)+f'<rect x="{x(98)}" y="70" width="{70*.95}" height="40" fill="#bfdbfe"/>'+line(x(122),70,x(122),110)
 for v,label,y in [(-7,'하한 −7',55),(98,'Q1 98',140),(168,'Q3 168',160),(273,'상한 273',55)]:
  b+=line(x(v),65,x(v),115,'stroke-dasharray="4 3"')+t(x(v),y,label,'text-anchor="middle"')
 b+=line(x(62),83,x(62),97)+line(x(268),83,x(268),97)+t(x(62),190,'수염 62','text-anchor="middle"')+t(x(268),190,'수염 268','text-anchor="middle"')
 b+=f'<circle cx="{x(480)}" cy="90" r="6" fill="#d97706"/>'+t(x(480),65,'7번 480','text-anchor="middle"')
 b+=line(x(0),230,x(500),230)
 for v in [0,100,200,300,400,500]:b+=t(x(v),252,v,'text-anchor="middle"')
 b+=t(400,281,'단가(만원/㎡)')
 f1=fig('fences','IQR 울타리와 수염',b,'그림 1. 공통 30건의 IQR은 70, 1.5배 울타리는 −7과 273입니다. 수염은 경계 안의 실제 최솟값 62와 최댓값 268까지입니다. 별도 점 480은 검토 후보입니다.',305)
 b=t(24,28,'같은 Q1·Q3를 고정하고 배수만 바꿉니다')
 for i,k in enumerate([1.5,2,3]):
  y=85+i*75;lo=98-k*70;hi=168+k*70
  b+=t(24,y+5,f'k={k}')+line(105,y,600,y)+f'<rect x="{105+(lo+120)*.75}" y="{y-10}" width="{(hi-lo)*.75}" height="20" fill="#dbeafe" data-k="{k}" data-low="{lo}" data-high="{hi}"/>'
  b+=t(105+(lo+120)*.75,y-20,f'{lo:g}','text-anchor="middle"')+t(105+(hi+120)*.75,y-20,f'{hi:g}','text-anchor="middle"')+f'<circle cx="555" cy="{y}" r="5" fill="#d97706"/>'+t(568,y+5,'480')
 b+=t(24,285,'색칠한 구간: 하한~상한 / 주황 점: 7번')+t(370,311,'단가(만원/㎡), 동일 축척')
 f2=fig('multipliers','배수별 IQR 경계',b,'그림 2. 하한·상한은 k=1.5에서 −7·273, k=2에서 −42·308, k=3에서 −112·378입니다. 세 경우 모두 480 한 건만 경계 밖입니다.',336)
 b=t(24,28,'집단을 나누면 비교 기준도 달라집니다')
 for i,label in enumerate(['전체','주거','상업']):
  v=values if label=='전체' else [r['price'] for r in rows if r['group']==label];q1,q2,q3,lo,hi,out=summary(v);upper=q3+1.5*(q3-q1);y=90+i*100
  b+=t(24,y-28,f'{label} {len(v)}건 · Q1 {q1:g}, Q3 {q3:g}, 상한 {upper:g}')+line(90,y,590,y)
  b+=f'<rect x="{90+q1}" y="{y-10}" width="{q3-q1}" height="20" fill="#bfdbfe" data-group="{label}" data-upper="{upper}"/>'+line(90+q2,y-10,90+q2,y+10)+line(90+upper,y-17,90+upper,y+17,'stroke-dasharray="4 3"')
  for val in v:b+=f'<circle cx="{90+val}" cy="{y+25}" r="3" fill="{"#d97706" if val in out else "#2563eb"}"/>'
 for val in [0,100,200,300,400,500]:b+=t(90+val,355,val,'text-anchor="middle"')
 b+=t(420,382,'단가(만원/㎡)')
 f3=fig('group-fences','집단별 상한 비교',b,'그림 3. 공통 자료를 유형별로 나눠 다시 계산한 상한은 주거 168, 상업 401.5입니다. 전체와 상업에서는 480이 후보이고 주거에는 후보가 없습니다. 기준값 자체도 달라집니다. 점이 겹치면 여러 건이 하나로 보일 수 있습니다.',407)
 b=t(24,28,'포함·제외 비교는 결과의 민감도를 보여 줍니다')
 other=[r['price'] for r in rows if r['id']!=7]
 for i,(label,fn) in enumerate([('평균',mean),('중앙값',median),('표준편차',pstdev)]):
  y=78+i*90;b+=t(24,y+8,label)
  for offset,v,color,key in [(0,values,'#2563eb','all'),(31,other,'#d97706','without')]:
   value=fn(v);b+=f'<rect x="150" y="{y+offset-10}" width="{value*2.5}" height="18" fill="{color}" data-metric="{label}" data-series="{key}" data-value="{value}"/>'+t(158+value*2.5,y+offset+4,f'{value:.2f}')
 b+=t(24,345,'파랑: 전체 30건 / 주황: 7번 제외 29건')+t(24,373,'가로축은 모두 0에서 시작 · 단위: 만원/㎡')
 f4=fig('sensitivity','제외 전후 통계량',b,'그림 4. 표준편차는 각 집합의 건수 n으로 나눠 계산합니다. 자료가 바뀌므로 평균도 다시 구합니다. 제외 결과가 더 정확하다는 의미는 아닙니다.',398)
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','핵심 이해','이상치는 확인할 관측이지, 곧바로 버릴 관측은 아닙니다','''<p>주변 값에서 유난히 떨어진 관측을 발견하면 먼저 비교 기준을 묻습니다. 같은 지역이라도 용도·면적·시점이 다르면 가격 분포가 달라질 수 있습니다. <strong>이상치 후보</strong>는 정한 규칙에 따라 추가 확인 대상으로 표시한 관측입니다. 표시만으로 입력 오류나 부적정 거래가 입증되지는 않습니다.</p><p>이 장에서는 <a href="/learn/stats/quantiles/">05장의 사분위수</a>로 울타리를 계산하고, 배수·집단·계산 관례에 따라 판정이 달라질 수 있음을 살펴봅니다. 이어서 포함·제외 결과를 비교하고 처리 근거를 남기는 방법을 익힙니다.</p>'''+f1)
 sec('iqr-multiplier','울타리 계산','Q1과 Q3에서 IQR의 일정 배수만큼 넓힙니다','''<p><strong>IQR=Q3−Q1</strong>은 가운데 부분의 퍼짐입니다. 배수 k를 정하면 하한 L=Q1−k×IQR, 상한 U=Q3+k×IQR입니다. 이 장에서는 <strong>x&lt;L 또는 x&gt;U</strong>인 값을 후보로 표시하고, 경계와 같은 값은 포함합니다. 수염은 울타리 자체가 아니라 그 안에 있는 실제 관측값까지 그립니다.</p><p>공통 <a href="/learn/stats/graphs/#data">학습 예시 30건</a>은 Q1=98, Q3=168, IQR=70입니다. k=1.5이면 L=98−105=−7, U=168+105=273입니다. 최솟값 62는 하한보다 크고, 24번 268은 상한보다 5 작습니다. 따라서 7번 480만 후보입니다. 음수 하한은 계산 결과이며 음수 거래가 존재한다는 뜻이 아닙니다.</p><p>1.5배는 널리 쓰이는 탐색 규칙이며 3배 울타리도 함께 쓰입니다. k가 2여야 한다는 통계학적 의무는 없습니다. 배수는 민감도를 정하는 선택이고, 울타리가 95% 신뢰구간이거나 잘못된 거래를 확률 95%로 검출한다는 의미도 아닙니다.</p>'''+f2+'''<p>자료와 사분위수를 고정하면 k를 키울수록 경계가 바깥으로 이동합니다. 후보 수는 줄거나 그대로이며 늘지 않습니다. 이 예제에서는 273과 378 사이에 값이 없어 세 배수 모두 1건입니다. 필터 적용 후 사분위수를 다시 구하는 절차는 이 비교와 다릅니다.</p>''')
 sec('conventions','계산 관례와 예외','작은 표본과 같은 값이 많은 자료에서는 더 주의합니다','''<p>이 장은 정렬한 자료를 절반으로 나누어 각 절반의 중앙값을 Q1·Q3로 삼고, 홀수 건수에서는 전체 중앙값을 양쪽 절반에서 제외합니다. <a href="/learn/stats/quantiles/#methods">분위수 계산 관례</a>에 따라 경계는 달라질 수 있습니다. 공통 30건에 선형 보간 type 7을 쓰면 Q1=99, Q3=166, IQR=67이며 1.5배 울타리는 −1.5와 266.5입니다. 이때는 268과 480 두 건이 후보가 됩니다.</p><p>표본이 작으면 몇 개 관측이 사분위수 위치를 크게 바꿉니다. 반올림된 값이나 동일 값이 많아 IQR=0이면 두 울타리가 Q1=Q3로 겹칩니다. 예를 들어 100·100·100·100·100·100·120은 이 관례에서 IQR=0이고 120만 경계 밖입니다. 그것만으로 120이 오류라고 결론 내리지 않습니다.</p><p>제외 후 울타리를 다시 계산해 반복 적용하면 처음에는 포함되던 값도 나중에 빠질 수 있습니다. 한 번 계산한 경계를 쓰는지, 반복하는지 구분하고 기록해야 합니다. 결과가 원하는 모양이 될 때까지 배수를 바꾸지 않습니다.</p>''')
 sec('groups','집단과 분포','누구와 비교하느냐가 이상치 판단의 일부입니다','''<p>전체 거래에 하나의 기준을 적용하는 것과 용도별로 나누어 적용하는 것은 서로 다른 질문입니다. 전자는 전체에서 떨어진 값을 찾고, 후자는 같은 유형 안에서 떨어진 값을 찾습니다. 집단을 나누면 건수와 사분위수도 다시 구합니다.</p>'''+f3+'''<p>이 그림에서는 주거 15건의 IQR은 32, 상업 15건의 IQR은 111입니다. 전체 IQR 70을 두 집단에 그대로 적용하지 않습니다. 집단을 지나치게 잘게 나누면 표본이 작아져 기준이 불안정해질 수 있으므로, 분석 목적에 맞는 비교 집단을 먼저 정합니다.</p><p>IQR 울타리를 계산하는 데 정규분포 가정은 필요하지 않습니다. 다만 오른쪽 꼬리가 긴 자료에서 경계 밖의 값이 자연스럽게 나타날 수 있고, 여러 집단이 섞이면 구조적인 차이를 후보로 표시할 수 있습니다. 히스토그램과 산점도를 함께 읽으세요. 한 변수의 IQR 검사는 변수들의 관계에서만 드러나는 특이한 관측까지 모두 찾아내지는 못합니다.</p>''')
 sec('sensitivity','포함·제외 비교','숫자가 얼마나 바뀌는지와 그 이유를 함께 봅니다','''<p>공통 예제는 실제 거래 출처가 확인되지 않은 학습 자료입니다. 7번을 제외하면 평균은 146.33에서 134.83, 중앙값은 122에서 120으로 바뀝니다. <a href="/learn/stats/spread/">06장 표준편차</a>는 80.16에서 51.72로 줄어듭니다.</p>'''+f4+'''<p>평균과 표준편차가 더 크게 변하는 것은 큰 관측의 영향과 연결됩니다. 중앙값과 IQR은 꼬리의 일부 값에 상대적으로 덜 민감하지만, 어떤 변경에도 불변인 지표는 아닙니다. 전체 시장을 묻는 분석에서 유효한 고가 거래를 빼면 분석 대상 자체가 달라질 수 있습니다.</p>''')
 sec('workflow','확인과 처리','원자료를 확인하고 처리 근거를 남깁니다','''<ol><li><strong>대상을 정합니다.</strong> 지역·기간·유형, 관측 단위, 금액인지 단가인지와 단위를 확인합니다.</li><li><strong>후보를 표시합니다.</strong> 사분위수 산식, k, 경계 포함 여부, 기준 건수와 후보 목록을 남깁니다.</li><li><strong>원자료를 대조합니다.</strong> 단위 입력, 면적 분모, 중복, 정정 여부와 거래 조건을 확인합니다. 높은 단가만으로 원인을 추측하지 않습니다.</li><li><strong>처리 방식을 선택합니다.</strong> 확인된 오류는 근거에 따라 정정하고, 유효한 별도 집단은 구분해 분석할 수 있습니다. 근거가 부족하면 원자료를 유지한 결과와 민감도 비교를 함께 제시합니다.</li><li><strong>변경을 설명합니다.</strong> 제외 사유·건수와 전후 통계량을 보고합니다. 원자료는 보존합니다.</li></ol><p>절사(trimming)는 일부 관측을 분석에서 제외하고, 윈저화(winsorization)는 정한 경계값으로 극단의 값을 바꾸는 방식입니다. 둘은 건수와 분포에 미치는 효과가 다릅니다. 어느 방식도 자동으로 오류를 교정해 주는 것은 아니며, 적용했다면 규칙을 밝혀야 합니다.</p>''')
 sec('practice','확인 문제','판정 기준과 처리 결정을 구분해 보세요','''<ol class="learn-exercises"><li>Q1=98, Q3=168, k=1.5일 때 273은 후보인가요?<details><summary>답과 해설</summary><p>아니요. 상한은 273이며 이 장은 경계를 포함합니다. 273보다 큰 값이 위쪽 후보입니다. 실제 공통 자료에는 273이 없습니다.</p></details></li><li>k를 1.5에서 3으로 바꾸면 후보가 반드시 줄어드나요?<details><summary>답과 해설</summary><p>반드시 줄지는 않습니다. 같은 자료와 사분위수에서는 줄거나 그대로입니다. 공통 예제는 두 경우 모두 480 한 건입니다.</p></details></li><li>같은 30건인데 한 프로그램은 480만, 다른 프로그램은 268과 480을 표시합니다. 반드시 구현 오류인가요?<details><summary>답과 해설</summary><p>아니요. 절반의 중앙값 방식과 type 7은 상한이 각각 273과 266.5입니다. 먼저 분위수 산식과 경계 처리, 비교 집단을 확인해야 합니다.</p></details></li></ol>''')
 sec('macro','CH2 Macro에서 읽기','필터 전후의 건수와 기준을 함께 확인합니다','''<p>CH2 Macro에서 IQR 옵션을 사용할 때는 적용 변수와 비교 집단, 선택 배수, 적용 전후 건수를 함께 확인하세요. 이 장의 손계산 관례를 서비스의 모든 화면에 그대로 대입하지 말고 해당 화면의 산식 설명을 확인합니다. 필터로 제외했다는 것은 분석 대상에서 빠졌다는 뜻이며 원자료 오류가 확정되었다는 뜻은 아닙니다.</p><figure class="learn-capture"><img src="../assets/captures/land-heungdeok-iqr.png" alt="토지 필터의 IQR 이상치 제외와 배수 선택 화면" loading="lazy"/><figcaption class="learn-capture__caption">기존 토지 필터 캡처. 설정 위치를 보여 주며 공통 학습 자료 30건의 실행 결과는 아닙니다. 현재 화면은 서비스 변경에 따라 다를 수 있습니다.</figcaption></figure><p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지에서 확인하기 →</a></p>''')
 sec('recap','정리와 참고자료','표시 → 확인 → 비교 → 기록 순서로 읽습니다','''<p>IQR 울타리는 검토 대상을 찾는 탐색 도구입니다. 배수와 분위수 관례, 비교 집단을 명시하고 후보의 실제 맥락을 확인하세요. 제외 여부는 통계량을 작게 만드는 방향이 아니라 분석 목적과 자료 근거로 판단합니다.</p><p>다음 <a href="/learn/stats/probability/">08장 「확률의 기초와 조건부확률」</a>에서는 사건과 확률, 조건에 따른 분모의 변화를 배웁니다.</p><ul><li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/boxplot.htm">NIST/SEMATECH: Box Plot</a> — 상자그림과 IQR 울타리.</li><li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm">NIST/SEMATECH: Detection of Outliers</a> — 후보 표시와 확인, 처리의 구분.</li></ul><p class="learn-source-note">본문과 그림은 공통 학습 자료 및 별도 가상 예제를 바탕으로 직접 작성했습니다. 출처 미확인 자료를 실제 시장 통계로 해석하지 않습니다. 참고자료 확인: 2026-10-07.</p>''')
 p=ROOT/'iqr-outliers/index.html';s=p.read_text(encoding='utf-8');s=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="이상치와 IQR">\n'+'\n'.join(parts)+'\n</article>',s,count=1,flags=re.S)
 s=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1IQR 울타리의 계산, 배수와 분위수 관례, 집단별 비교와 이상치 처리 절차를 그림과 예제로 익힙니다.\2',s,count=1,flags=re.S);p.write_text(s,encoding='utf-8')
if __name__=='__main__':build()
