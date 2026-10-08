"""Chapter 20: log transformations and retransformation."""
from pathlib import Path
from statistics import mean
from html import escape
import math,json,re
from _build_regression_chapter import fit
ROOT=Path(__file__).resolve().parent

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];x=[r['area'] for r in rows];y=[r['price'] for r in rows];lx=list(map(math.log,x));ly=list(map(math.log,y))
 models={}
 for key,xx,yy,logy in [('level',x,y,False),('log_y',x,ly,True),('log_x',lx,y,False),('log_log',lx,ly,True)]:
  m=fit(xx,yy);m['predictions']=[math.exp(m['intercept']+m['slope']*v) if logy else m['intercept']+m['slope']*v for v in xx];m['MAE']=mean(abs(a-b) for a,b in zip(y,m['predictions']));m['smearing']=mean(math.exp(e) for e in m['residuals']) if logy else None;models[key]=m
 def pred(key,v):
  m=models[key];z=math.log(v) if key in ['log_x','log_log'] else v;value=m['intercept']+m['slope']*z;return math.exp(value) if key in ['log_y','log_log'] else value
 curve=[dict(x=22+i*288/100,**{k:pred(k,22+i*288/100) for k in ['level','log_y','log_log']}) for i in range(101)]
 percentages=[dict(change=c,exact=100*((1+c/100)**models['log_log']['slope']-1),approx=models['log_log']['slope']*c) for c in [1,10,50]]
 (ROOT/'log-regression-example.json').write_text(json.dumps(dict(description='공통 학습 자료의 자연로그 OLS. 단순 지수변환은 산술평균 예측이 아님.',models=models,curves=curve,percentages=percentages,retransform=dict(values=[50,200],geometric=100,arithmetic=125)),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def ln(x,y,a,b,c='#94a3b8'):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="{c}"/>'
 def dot(x,y,c='#2563eb'):return f'<circle cx="{x}" cy="{y}" r="4" fill="{c}"/>'
 def fig(id,title,b,cap,h=400):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=tx(24,28,'같은 배수는 로그 축에서 같은 간격')
 b+=tx(24,85,'원래 값')+ln(110,110,590,110)+tx(24,225,'자연로그')+ln(110,250,590,250)
 for v in [25,50,100,200,400]:
  a=110+v*1.1;z=110+(math.log(v)-math.log(25))*170;b+=dot(a,110)+tx(a-10,145,v)+dot(z,250)+tx(z-12,285,v)
 b+=tx(24,340,'아래 점의 위치 = ln(값), 숫자는 원래 값을 표시')+tx(24,373,'25 → 50 → 100 → 200 → 400: 매번 ×2, 로그 차이는 ln 2')
 f1=fig('scale','원래 축과 로그 축',b,'그림 1. 별도 양수 예제입니다. 로그는 순서를 유지하면서 곱셈 관계를 덧셈 관계로 바꿉니다. 아래 축은 자연로그 위치에 원래 값으로 눈금을 붙였습니다.')
 b=tx(24,28,'단가(만원/㎡) · 공통 학습 자료 30건')+ln(65,325,580,325)+ln(65,55,65,325)
 for xx,yy in zip(x,y):b+=dot(65+xx*1.55,325-yy*.5,'#94a3b8')
 for key,c in [('level','#2563eb'),('log_y','#d97706'),('log_log','#16a34a')]:b+='<polyline data-model="'+key+'" points="'+' '.join(f"{65+r['x']*1.55},{325-r[key]*.5}" for r in curve)+'" fill="none" stroke="'+c+'" stroke-width="2"/>'
 for v in [0,100,200,300]:b+=tx(60+v*1.55,348,v)
 for v in [0,100,200,300,400,500]:b+=tx(25,330-v*.5,v)
 b+=tx(24,380,'파랑: 원래 척도 / 주황: ln Y / 초록: ln Y ~ ln X')+tx(420,405,'면적(㎡)')
 f2=fig('curves','변환에 따른 적합곡선',b,'그림 2. 관측 면적 22~310㎡에서만 그렸습니다. 주황·초록은 로그 적합값을 단순 지수변환한 곡선이며, 산술평균을 위한 재변환 보정은 적용하지 않았습니다.',430)
 b=tx(24,28,'로그–로그: 면적 증가율에 따른 적합값 변화율')+ln(120,95,570,95)
 for i,r in enumerate(percentages):
  xx=190+i*155;b+=f'<rect x="{xx-28}" y="95" width="24" height="{-r["exact"]*7}" fill="#2563eb"/><rect x="{xx+3}" y="95" width="24" height="{-r["approx"]*7}" fill="#d97706"/>'+tx(xx-35,320,f'+{r["change"]}%')+tx(xx-42,350,f'{r["exact"]:.2f} / {r["approx"]:.2f}')
 for v in [0,-10,-20,-30]:b+=tx(65,100-v*7,v)
 b+=tx(24,385,'세로: 변화율(%) · 파랑: 정확식 / 주황: b × 증가율 근사')
 f3=fig('percent','정확한 비율 변화와 근사',b,'그림 3. 공통 자료의 로그–로그 기울기를 사용했습니다. X 증가율이 커질수록 100[(1+c/100)^b−1]과 b×c의 차이가 커집니다.')
 b=tx(24,28,'가상 두 값 50과 200을 같은 비중으로 평균')+ln(120,320,570,320)
 for i,(label,v) in enumerate([('기하평균',100),('산술평균',125)]):
  xx=210+i*210;b+=f'<rect x="{xx-40}" y="{320-v*1.6}" width="80" height="{v*1.6}" fill="'+('#2563eb' if i==0 else '#d97706')+'"/>'+tx(xx-12,305-v*1.6,v)+tx(xx-35,350,label)
 for v in [0,50,100,150]:b+=tx(65,325-v*1.6,v)
 b+=tx(24,385,'exp[(ln 50 + ln 200)/2] = 100 ≠ (50 + 200)/2 = 125')
 f4=fig('retransform','지수변환과 산술평균',b,'그림 4. 로그 평균을 지수변환한 값과 원래 값의 산술평균은 다릅니다. 단위 없는 가상 예제로, 공통 자료의 예측오차 비교가 아닙니다.')
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','로그의 의미','일정한 차이와 일정한 비율을 구별합니다','<p>면적 50→100㎡와 200→250㎡는 모두 50㎡ 증가지만 비율은 다릅니다. 반대로 50→100㎡와 200→400㎡는 차이는 달라도 모두 두 배입니다. 로그변환은 이러한 비율 관계를 다루기 편하게 만듭니다.</p><p>이 장은 밑이 e인 자연로그 ln을 씁니다. ln(ab)=ln a+ln b, ln(b/a)=ln b−ln a이며 역변환은 exp입니다. ln 값 자체를 백분율로 읽지 말고 로그의 차이를 비율과 연결하세요.</p>'+f1)
 sec('forms','네 가지 모형','어느 변수에 로그를 취했는지 먼저 확인합니다','<p><strong>원래 척도: ŷ=a+bX.</strong> X가 Δ만큼 다를 때 적합값 차이는 bΔ입니다. b의 단위는 Y단위/X단위입니다.</p><p><strong>Y만 로그: m(X)=a+bX, m은 ln Y의 적합값.</strong> X가 Δ만큼 다를 때 exp(m)의 비는 exp(bΔ), 변화율은 100[exp(bΔ)−1]%입니다. bΔ가 작으면 약 100bΔ%입니다.</p><p><strong>X만 로그: ŷ=a+b ln X.</strong> X가 c% 증가하면 적합값 차이는 b ln(1+c/100)입니다. 작은 c에서는 약 bc/100이며 Y의 원래 단위로 읽습니다. Y의 c% 변화라는 뜻이 아닙니다.</p><p><strong>둘 다 로그: m(X)=a+b ln X.</strong> exp(m)=exp(a)Xᵇ이며 b는 이 곡선의 탄력성입니다. X가 c% 증가할 때 정확한 변화율은 100[(1+c/100)ᵇ−1]%, 작은 c에서는 약 bc%입니다. 두 배가 되면 100(2ᵇ−1)%입니다.</p><p>Y가 로그인 두 모형에서 위 비율은 우선 지수변환한 로그 적합값에 관한 것입니다. 산술평균의 비율로 읽으려면 재변환 보정이 X에 따라 어떻게 달라지는지까지 고려해야 합니다.</p>')
 ly_m=models['log_y'];ll=models['log_log'];lx_m=models['log_x']
 sec('example','공통 자료 계산','같은 자료를 서로 다른 척도에서 적합합니다',f'<p>면적 X와 단가 Y의 공통 30건은 모두 양수입니다. ln Y 모형은 m={ly_m["intercept"]:.5f} {ly_m["slope"]:+.6f}X, ln–ln 모형은 m={ll["intercept"]:.5f} {ll["slope"]:+.5f} ln X입니다. X만 로그인 식은 ŷ={lx_m["intercept"]:.3f} {lx_m["slope"]:+.3f} ln X입니다.</p>'+f2+f'<p>100㎡에서 ln Y 모형의 단순 역변환값은 {pred("log_y",100):.2f}, ln–ln은 {pred("log_log",100):.2f}만원/㎡입니다. 반올림 전 계수로 계산했습니다. ln Y 모형에서 10㎡ 차이의 비율 변화는 {100*math.expm1(ly_m["slope"]*10):.2f}%입니다.</p><p>로그 OLS는 로그 잔차의 제곱합을 최소화합니다. 원래 단가의 제곱오차나 절대오차를 최소화하는 것과 목적이 다릅니다. 로그를 취하면 큰 단가의 절대적 차이가 상대적으로 압축되지만, 이상치나 영향력 문제가 자동으로 사라지는 것은 아닙니다.</p>')
 sec('percent','탄력성과 근사','1% 근사를 큰 변화에 그대로 적용하지 않습니다',f'<p>공통 자료의 로그–로그 기울기는 {ll["slope"]:.4f}입니다. 면적 1% 증가에 대해 지수변환 적합값은 약 {abs(ll["slope"]):.2f}% 감소합니다. 이는 모형상 연관이며 면적을 실제로 늘리는 인과효과가 아닙니다.</p>'+f3+'<p>백분율과 퍼센트포인트도 구별합니다. ln Y 모형에서 exp(b)−1을 계산한 비율은 Y의 상대 변화이지 비율 변수의 퍼센트포인트 차이가 아닙니다. 다른 변수를 함께 넣었다면 해당 변수를 고정한 비교이며 상호작용이 있으면 변화율도 조건에 따라 달라집니다.</p>')
 sec('retransform','원래 단위로 복원','지수변환만으로 산술평균이 되지는 않습니다','<p>ln Y=m(X)+ε에서 E[ε|X]=0이라면 exp(m(X))는 조건부 기하평균입니다. ε의 조건부 중앙값까지 0이면 Y의 조건부 중앙값이기도 합니다. 평균 0만으로 중앙값 0이 따라오는 것은 아닙니다.</p>'+f4+'<p><strong>E[Y|X]=exp(m(X))×E[exp(ε)|X]</strong>이므로 산술평균에는 추가 요인이 필요합니다. 조건부 오차가 N(0,σ²)이면 exp(m+σ²/2)입니다. 추정한 계수와 분산을 대입하는 데도 추정 불확실성이 남습니다.</p><p>정규성을 가정하지 않는 방법으로 잔차의 exp를 평균한 스미어링 계수 S=(1/n)Σexp(eᵢ)를 곱할 수 있습니다. 하나의 공통 S가 적절하려면 E[exp(ε)|X]가 일정하다는 조건 등이 필요합니다. 이분산으로 이 요인이 달라지면 조건부 보정이 필요할 수 있습니다. 보정계수는 학습 자료에서만 추정해 검증 자료의 결과값 누출을 피합니다.</p><p>로그 척도의 구간 양 끝을 지수변환하면 원래 척도에서 비대칭 구간이 됩니다. 로그 평균의 신뢰구간을 변환한 것을 산술평균의 신뢰구간이라고 부르면 안 됩니다. 개별 관측의 로그 예측구간은 그 가정 아래 단조변환으로 Y 예측구간에 옮길 수 있습니다.</p>')
 sec('compare','모형 비교','같은 평가 자료와 같은 목표 단위에서 비교합니다',f'<p>같은 30건에 적합하고 같은 30건에서 측정한 원 단위 MAE는 원래 척도 {models["level"]["MAE"]:.2f}, ln Y 단순 역변환 {ly_m["MAE"]:.2f}, ln–ln 단순 역변환 {ll["MAE"]:.2f}만원/㎡입니다. 이것은 학습 오차이며 미래 성능 순위가 아닙니다. 산술평균 보정은 적용하지 않았습니다.</p><p>Y와 ln Y의 R²는 서로 다른 결과변수의 변동을 기준으로 하므로 숫자를 직접 비교해 승자를 정하지 않습니다. 같은 검증 표본에서, 원 단위인지 상대 오차인지 목적에 맞춘 지표로 평가하세요. MAE와 RMSE도 선호하는 점예측 대상이 다릅니다.</p><p>변환 후 잔차 대 적합값·시간·집단 패턴과 영향 관측을 다시 점검해야 합니다. 로그가 정규성·등분산·선형성을 모두 해결한다는 보장은 없습니다.</p>')
 sec('domain','0·음수와 단위','로그의 정의역을 먼저 확인합니다','<p>실수 범위에서 ln X는 X&gt;0에서만 정의됩니다. 0이나 음수를 조용히 제외하면 분석 대상이 바뀔 수 있습니다. 누락·오류인지, 실제 0인지, 음수가 의미 있는 변수인지 먼저 확인하세요.</p><p>ln(1+X)는 다른 모형입니다. 작은 값에서는 단위에 민감하고 일반 로그의 탄력성 해석을 그대로 쓸 수 없습니다. 임의 상수를 더하기보다 자료의 생성 과정과 목적에 맞는 변환·모형을 선택하고 처리 규칙을 기록합니다.</p><p>로그에는 선택한 단위로 표시한 수치를 넣습니다. X의 단위를 일정 배수로 바꾸면 ln X에 상수가 더해져 절편이 이동합니다. 같은 표본·절편·모형을 유지한 로그–로그 기울기는 변하지 않지만, 원 단위 X를 쓰는 ln Y 모형의 기울기 숫자는 X 단위에 따라 바뀝니다.</p>')
 sec('nonlinear','비선형 관계','곡선이어도 계수에 선형이면 선형회귀입니다','<p>Y=a+b ln X+ε와 Y=a+bX+cX²+ε는 원래 X축에서 곡선이지만 미지의 계수에는 선형입니다. 변환한 열을 설명변수로 넣어 선형 최소제곱으로 적합할 수 있습니다. 제곱항 모형의 기울기는 b+2cX이므로 일정하지 않습니다.</p><p>반면 Y=A exp(bX)+u를 원 단위의 가산 오차로 적합하는 것과 ln Y=a+bX+ε를 적합하는 것은 오차 구조와 최소화 대상이 다릅니다. 둘이 지수 모양이라는 이유로 같은 모형이라고 부르지 않습니다. 곡선 형태를 바꾸어도 관측 범위 밖 외삽의 불확실성은 남습니다.</p>')
 sec('practice','확인 문제','변화량과 복원 대상을 구별하세요','<ol class="learn-exercises">'+''.join(f'<li>{q}<details><summary>답과 해설</summary><p>{a}</p></details></li>' for q,a in [('ln Y=a+0.1X에서 X가 1 증가하면 정확히 10% 증가하나요?','정확한 비율은 100(exp(0.1)−1)≈10.52%입니다. 지수변환한 로그 적합값에 관한 비교입니다.'),('Y=a+b ln X에서 X가 1% 증가하면 Y가 b% 바뀌나요?','아니요. 정확한 변화는 b ln(1.01), 약 b/100이며 Y의 원래 단위입니다.'),('로그 평균을 지수변환하면 산술평균인가요?','아니요. 기하평균이며 산술평균에는 조건부 오차의 지수 평균을 반영해야 합니다.'),('ln(1+X)에서도 b를 그대로 탄력성으로 읽나요?','아니요. 변환한 함수가 달라졌으므로 변화율을 그 식에서 다시 계산해야 합니다.')])+'</ol>')
 sec('macro','CH2 Macro에서 읽기','변환·복원·평가 방식을 함께 확인합니다','<p>서비스 결과를 읽을 때 어떤 변수에 어떤 로그를 썼는지, 0·음수 처리와 단위, 단순 역변환인지 산술평균 보정인지, 검증 오차의 척도를 확인하세요. 이 장의 연습 모형이 실제 서비스의 산식이라고 전제하지 않습니다.</p><p>공통 자료는 출처 미확인 학습 예제입니다. 로그 곡선과 계수는 관계를 이해하는 연습이며 개별 적정가나 확정적인 인과효과를 제시하지 않습니다.</p>')
 sec('recap','정리와 참고자료','로그의 위치가 계수의 의미를 바꿉니다','<p>차이·비율·탄력성을 구별하고, 작은 변화의 근사와 정확식을 나누어 읽으세요. 원래 단위로 돌아갈 때는 기하평균·중앙값·산술평균 중 무엇을 추정하는지 확인합니다.</p><p>다음 <a href="/learn/stats/model-fit/">21장 「회귀모형의 적합도와 추정의 불확실성」</a>으로 이어집니다.</p><ul><li><a href="https://stats.oarc.ucla.edu/other/mult-pkg/faq/general/faqhow-do-i-interpret-a-regression-model-when-some-variables-are-log-transformed/">UCLA OARC: 로그변환 회귀의 해석</a></li><li><a href="https://www.itl.nist.gov/div898/handbook/pmd/section1/pmd141.htm">NIST: Linear Least Squares Regression</a></li><li><a href="../log-regression-example.json">계수·적합곡선·변화율 계산 자료</a></li></ul><p class="learn-source-note">본문과 그림은 공통 학습 자료 및 별도 가상 예제로 직접 작성했습니다. 참고자료 확인: 2026-10-08.</p>')
 p=ROOT/'log-regression/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="로그변환과 비선형 관계">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1로그변환의 계수·탄력성·정확한 변화율과 원 단위 재변환, 모형 비교의 주의점을 학습합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
