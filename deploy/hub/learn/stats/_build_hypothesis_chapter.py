"""Generate chapter 13: fixed-reference one-sample inference and power."""
from pathlib import Path
from statistics import mean,stdev
from html import escape
import math,json,re
from scipy.stats import t as student_t,nct
ROOT=Path(__file__).resolve().parent

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];v=[r['price'] for r in rows];m=mean(v);s=stdev(v);n=len(v);df=n-1;se=s/math.sqrt(n);mu0=130;obs=(m-mu0)/se;p=float(2*student_t.sf(abs(obs),df));critical=float(student_t.ppf(.975,df));lo=m-critical*se;hi=m+critical*se
 power=[]
 for nn in [20,50,100,200]:
  c=float(student_t.ppf(.975,nn-1));nc=20/80*math.sqrt(nn);power.append({'n':nn,'power':float(nct.cdf(-c,nn-1,nc)+nct.sf(c,nn-1,nc))})
 result={'description':'공통 학습자료의 가상 사전 기준 130에 대한 양측 t 검정. 실제 시장 검정이 아님.','mu0':mu0,'n':n,'mean':m,'sd':s,'se':se,'t':obs,'df':df,'p':p,'critical':critical,'ci':[lo,hi],'power':{'sigma':80,'difference':20,'alpha':.05,'values':power}}
 (ROOT/'hypothesis-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def text(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def line(x,y,xx,yy,c='#64748b',extra=''):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{c}" {extra}/>'
 def fig(id,title,b,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 def curve(cut,label):
  point=lambda x:(320+x*60,235-float(student_t.pdf(x,df))*400)
  b=text(24,28,label)+line(50,235,590,235)
  for a,z in [(-4.5,-cut),(cut,4.5)]:
   pts=[point(a+(z-a)*i/100) for i in range(101)];b+='<polygon points="'+f'{point(a)[0]},235 '+' '.join(f'{x:.5f},{y:.5f}' for x,y in pts)+f' {point(z)[0]},235" fill="#bfdbfe"/>'
  pts=[point(-4.5+i*.025) for i in range(361)];b+='<polyline points="'+' '.join(f'{x:.5f},{y:.5f}' for x,y in pts)+'" fill="none" stroke="#2563eb" stroke-width="2"/>'
  for x in [-4,-2,0,2,4]:b+=text(320+x*60,264,x,'text-anchor="middle"')
  for x in [-cut,cut]:b+=line(320+x*60,point(x)[1],320+x*60,235,'#d97706')+text(320+x*60,295,f'{x:.3f}','text-anchor="middle"')
  return b+text(510,320,'t 값')
 f1=fig('p-tails','관측값보다 극단적인 양쪽 꼬리',curve(abs(obs),f'관측 |t|={abs(obs):.3f} 바깥 면적: p={p:.4f}'),'그림 1. H₀와 가정이 맞을 때의 자유도 29 t분포입니다. 양측 p값은 양쪽 꼬리 확률의 합입니다. 곡선은 −4.5~4.5만 표시하지만 계산은 무한 꼬리까지 포함합니다.',345)
 f2=fig('rejection','유의수준 5%의 기각역',curve(critical,f'사전에 정한 α=0.05: 양쪽 꼬리 0.025씩'),'그림 2. 자유도 29, 양측 5% 기각역은 ±2.045 바깥입니다. 그림 1의 관측값 기준 p값 영역과 그림 2의 사전 기준 기각역을 구별하세요.',345)
 x=lambda a:90+(a-90)*4
 b=text(24,28,'같은 양측 t 검정과 95% t 신뢰구간을 연결합니다')+line(x(lo),115,x(hi),115,'#2563eb','stroke-width="4" data-ci="mean"')+text(x(lo),147,f'{lo:.2f}','text-anchor="middle"')+text(x(hi),147,f'{hi:.2f}','text-anchor="middle"')+line(x(mu0),65,x(mu0),180,'#d97706','stroke-dasharray="4 3"')+text(x(mu0),55,'기준 130','text-anchor="middle"')+f'<circle cx="{x(m)}" cy="115" r="5" fill="#2563eb"/>'+text(x(m)+10,93,f'평균 {m:.2f}')+text(24,225,'130이 구간 안에 있음 → 5% 양측 검정에서 기각하지 않음')+text(360,260,'단위: 만원/㎡')
 f3=fig('ci-link','신뢰구간과 검정의 관계',b,'그림 3. 동일한 자료·가정·양측 t 방법에서의 연결입니다. 기준값을 기각하지 않는 것이 그 값이 참임을 입증하는 것은 아닙니다.',285)
 b=text(24,28,'같은 실제 차이와 퍼짐을 가정한 사전 검정력 비교')
 for i,d in enumerate(power):
  y=70+i*65;b+=text(24,y+19,f'n={d["n"]}')+f'<rect x="145" y="{y}" width="{d["power"]*390}" height="25" fill="#2563eb" data-n="{d["n"]}" data-power="{d["power"]}"/>'+text(155+d['power']*390,y+19,f'{d["power"]:.1%}')
 b+=text(24,345,'가로축: 검정력(0~100%) / α=0.05, 차이 20, σ=80')
 f4=fig('power','표본수와 검정력',b,'그림 4. 독립 정규표본의 양측 단일표본 t 검정을 가정한 이론값입니다. 실제 차이 20만원/㎡와 σ=80만원/㎡를 사전에 설정한 가상 계획 예제이며 관측 p값에서 계산한 사후 검정력이 아닙니다.',375)
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','핵심 이해','기준 가정 아래 관측 결과가 얼마나 극단적인지 봅니다','''<p>가설검정은 자료와 특정 가설의 양립 가능성을 정해진 절차로 살펴봅니다. 예를 들어 모평균 μ가 사전에 정한 기준 μ₀와 같은지 묻습니다. 여기서 검정 대상은 개별 거래 가격이나 표본평균 자체가 아니라 <strong>모집단의 평균</strong>입니다.</p><p>핵심 흐름은 질문과 가설 설정 → 표집·모형 확인 → 통계량·p값 계산 → 불확실성과 효과크기를 함께 보고하는 순서입니다. <a href="/learn/stats/confidence-intervals/">12장의 신뢰구간</a>과 연결해 읽으면 단순한 ‘통과·실패’ 판정을 피할 수 있습니다.</p>''')
 sec('hypotheses','가설과 방향','자료를 보기 전에 기준값과 검정 방향을 정합니다','''<p><strong>귀무가설 H₀: μ=130</strong>, <strong>대립가설 H₁: μ≠130</strong>으로 정하겠습니다. 130만원/㎡는 분석 전에 외부에서 정했다고 가정한 교육용 기준이며 실제 공인 기준이 아닙니다. 큰 쪽과 작은 쪽 모두 관심 있으므로 양측 검정입니다.</p><p>기존 설명처럼 같은 표본의 중앙값 122를 보고 모평균의 검정 기준으로 고르면, 기준 자체가 자료에 따라 변합니다. 이를 고정된 μ₀로 취급한 일반 단일표본 t 검정과 같은 추론으로 해석할 수 없습니다. 이 장은 이 혼동을 피하기 위해 사전 고정 기준을 사용합니다.</p><p>증가만을 사전에 검정하려면 H₀: μ≤130, H₁: μ&gt;130처럼 단측 가설을 정할 수 있습니다. 결과가 나온 뒤 유리한 방향으로 바꾸거나 양측 p값을 무조건 절반으로 나누지 않습니다. 이 장의 계산은 모두 사전에 정한 양측 검정입니다.</p>''')
 sec('statistic','검정통계량','차이를 평균의 표준오차로 나누어 비교합니다',f'''<p>정규모집단의 독립·동일분포 표본에서 σ를 모르는 단일표본 t 검정은 <strong>T=(x̄−μ₀)/(s/√n)</strong>을 사용합니다. H₀가 참이면 자유도 n−1의 t분포를 따릅니다. 비정규 자료에서는 근사 적용의 적절성을 따로 검토해야 합니다.</p><p>공통 학습 자료는 n=30, x̄={m:.5f}…, s={s:.5f}…, SE={se:.5f}…입니다. 기준 130과의 차이는 {m-mu0:.5f}…이고 <strong>t={obs:.5f}…</strong>입니다. 즉 관측된 차이는 추정 표준오차의 약 {obs:.2f}배입니다.</p><p>공통 30건은 실제 출처와 무작위 표집 설계가 확인되지 않은 교육용 자료입니다. 분포도 치우쳐 있으므로 산식 계산을 실제 시장의 유효한 가설검정으로 오인하지 않습니다. <a href="../hypothesis-example.json">계산값 JSON</a>에 중간값을 보존했습니다.</p>''')
 sec('p-value','p값의 의미','가설이 참일 확률을 계산하는 것이 아닙니다',f'''<p>p값은 <strong>귀무가설과 검정의 다른 가정이 맞을 때, 정한 검정통계량이 관측값만큼 또는 더 극단적일 확률</strong>입니다. 양측 t 검정에서는 p=P(|T|≥|t관측|)=2P(T≥|t관측|)입니다.</p>'''+f1+f'''<p>이 예제의 양측 p값은 <strong>{p:.4f}</strong>입니다. 이는 H₀가 참일 확률, 결과가 우연일 확률, 분석자가 틀렸을 확률이 아닙니다. 연속분포에서 관측한 평균과 정확히 같은 값이 나올 확률을 계산한 것도 아닙니다.</p><p>p값이 작으면 H₀와 모형 가정 아래에서 관측 결과가 드물다는 뜻입니다. 원인이 반드시 H₀의 거짓 하나뿐이라는 보장은 없습니다. 표집 편향·의존성·잘못된 모형도 결과에 영향을 줄 수 있습니다.</p>''')
 sec('decision','유의수준과 결정','기각하지 못했다는 말은 같음을 증명했다는 뜻이 아닙니다','''<p>유의수준 α는 H₀가 참일 때 잘못 기각하는 비율을 통제하도록 사전에 정한 기준입니다. 여기서는 α=0.05이고 p&lt;α이면 기각하는 규칙을 사용합니다. 경계의 등호 처리까지 일관되게 정해 두는 것이 좋습니다.</p>'''+f2+f'''<p>p={p:.4f}&gt;0.05이므로 이 계산에서는 H₀를 기각하지 않습니다. ‘μ=130이 입증됐다’거나 ‘차이가 없다’고 쓰지 않습니다. 자료의 퍼짐과 표본수 때문에 차이를 구분할 정보가 부족할 수도 있습니다.</p><p>0.049와 0.051 사이에 실질적인 진실의 경계가 있는 것은 아닙니다. 임계값 판정만 보고 결론을 급격히 바꾸기보다 정확한 p값, 추정 차이와 구간을 함께 보고합니다.</p>''')
 sec('ci','신뢰구간과 연결','같은 양측 방법에서는 구간과 기각 여부가 일치합니다',f'''<p>같은 자료와 가정의 양측 5% t 검정에서 μ₀가 95% t 구간 바깥이면 기각합니다. 공통 자료의 구간은 {lo:.2f}~{hi:.2f}이고, 기준 130은 안에 있습니다. 차이 μ−130의 구간은 {lo-130:.2f}~{hi-130:.2f}로 0을 포함합니다.</p>'''+f3+'''<p>이 대응은 같은 방법·신뢰수준·양측 가설을 사용할 때의 관계입니다. 다른 추정법이나 단측 검정 결과와 임의로 섞지 않습니다. 두 집단 각각의 구간이 겹치는지만 보는 것은 두 집단 차이의 검정을 대신하지 못합니다.</p>''')
 sec('errors','두 오류와 검정력','놓치는 오류도 함께 생각해야 합니다','''<div class="learn-data learn-data--full"><table><caption>가설검정의 가능한 결정</caption><thead><tr><th scope="col">실제 상태</th><th scope="col">H₀ 기각</th><th scope="col">H₀ 기각하지 않음</th></tr></thead><tbody><tr><th scope="row">H₀ 참</th><td>제1종 오류 · α로 통제</td><td>올바른 결정</td></tr><tr><th scope="row">특정 대립가설 참</th><td>탐지 · 검정력 1−β</td><td>제2종 오류 · β</td></tr></tbody></table></div><p>β와 검정력은 실제 차이가 얼마인지에 따라 달라집니다. 모든 대립가설에 공통인 검정력 하나가 있는 것이 아닙니다. 실제 차이·표본수·퍼짐·유의수준·검정 방향을 정해야 계산할 수 있습니다.</p>'''+f4+'''<p>같은 조건에서 n이 커지거나 실제 차이가 커지면 검정력은 대체로 높아집니다. α를 더 엄격하게 낮추면 제1종 오류를 줄이는 대신 같은 n에서 차이를 놓치기 쉬워질 수 있습니다. 자료를 모으기 전에 중요하게 볼 최소 차이와 목표 검정력을 정해 표본수를 계획합니다.</p>''')
 sec('effect','통계적 유의성과 실질적 의미','p값은 차이의 크기를 대신하지 않습니다',f'''<p>이 예제의 추정 차이는 {m-mu0:.2f}만원/㎡입니다. 단위를 가진 차이와 구간을 보고해야 실제 의미를 평가할 수 있습니다. 큰 표본에서는 아주 작은 차이도 유의할 수 있고, 작은 표본에서는 큰 차이도 넓은 불확실성 때문에 유의하지 않을 수 있습니다.</p><p>효과크기는 차이의 크기를 나타내고 p값은 특정 가정 아래 증거의 정도를 요약합니다. 다음 장에서 집단 간 차이와 표준화 효과크기를 다룹니다. ‘유의하지 않음’으로 두 값이 실질적으로 같다고 주장하려면 충분하지 않습니다. 동등성에는 사전에 정한 허용 차이와 별도의 검정 설계가 필요합니다.</p>''')
 sec('multiplicity','반복 검정과 보고','유리한 결과만 선택하면 오류율이 달라집니다',f'''<p>서로 독립이며 모두 H₀가 참인 검정을 α=0.05로 20번 하면 적어도 한 번 잘못 기각할 확률은 1−0.95²⁰≈{(1-.95**20)*100:.1f}%입니다. 각 검정의 5%와 전체 탐색의 오류율은 다릅니다. 의존성이 있으면 이 단순 계산도 달라집니다.</p><p>변수·지역·기간을 계속 바꾸다 p&lt;0.05인 결과만 보고하거나, 유의할 때까지 표본을 추가하면서 일반 p값을 그대로 해석하면 사전에 정한 오류 통제가 깨질 수 있습니다. 계획한 분석과 탐색을 구분하고 전체 비교 수를 밝히며, 필요하면 다중비교 보정이나 순차검정 방법을 사용합니다.</p><p>가설·기준값·방향·유의수준·표집 방법·유효 n·추정 차이·신뢰구간·정확한 p값을 함께 보고하세요. 반올림된 표시가 0.000이라고 해서 p=0이라고 쓰지 않습니다.</p>''')
 sec('practice','확인 문제','기준과 확률의 방향을 점검하세요','''<ol class="learn-exercises"><li>p=0.03이면 H₀가 참일 확률이 3%인가요?<details><summary>답과 해설</summary><p>아니요. H₀와 가정 아래 관측 통계량만큼 또는 더 극단적인 결과의 확률입니다.</p></details></li><li>p&gt;0.05이면 두 값이 같다는 증거인가요?<details><summary>답과 해설</summary><p>기각하지 못했다는 뜻이며 같음을 입증하지 않습니다. 구간과 검정력을 함께 봐야 합니다.</p></details></li><li>결과를 본 뒤 단측으로 바꿔도 되나요?<details><summary>답과 해설</summary><p>유리한 방향을 사후 선택하면 사전에 설계한 오류율 해석이 성립하지 않습니다.</p></details></li><li>매우 작은 p값이면 차이도 반드시 큰가요?<details><summary>답과 해설</summary><p>아니요. 표본수와 퍼짐도 영향을 줍니다. 차이의 크기와 신뢰구간을 별도로 보고합니다.</p></details></li></ol>''')
 sec('macro','CH2 Macro에서 읽기','유의성을 시장의 중요성과 혼동하지 않습니다','''<p>CH2 Macro에서 통계 결과를 읽을 때는 계수·차이의 크기, 단위, 건수, 표집 범위와 가정을 먼저 확인합니다. p값이 제공된다면 무엇을 귀무가설로 검정한 값인지 설명을 함께 읽으세요. 이 장의 계산이 모든 화면의 기능이라고 전제하지 않습니다.</p><p>유의한 관계도 인과관계나 미래 예측의 정확성을 보장하지 않습니다. 지역·기간을 반복 탐색한 결과는 탐색 과정과 함께 보고해야 합니다.</p><p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 통계 열기 →</a></p>''')
 sec('recap','정리와 참고자료','판정 한 단어보다 추정치와 맥락을 남깁니다','''<p>가설검정은 정한 기준과 자료의 관계를 표집 모형 아래 판단합니다. p값은 H₀의 확률이 아니며, 기각하지 않음은 같음의 증명이 아닙니다. 오류·검정력·효과크기·다중비교를 함께 고려합니다.</p><p>다음 <a href="/learn/stats/comparing-groups/">14장 「두 집단 비교와 효과크기」</a>로 이어집니다.</p><ul><li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm">NIST/SEMATECH: Confidence Limits for the Mean</a> — 단일표본 t 검정과 신뢰구간의 연결.</li></ul><p class="learn-source-note">공통 학습 자료와 별도 가상 기준으로 직접 계산했습니다. 검정력은 SciPy 비중심 t분포로 계산했습니다. 실제 시장 검정 결과가 아닙니다. 참고자료 확인: 2026-10-07.</p>''')
 pth=ROOT/'hypothesis-tests/index.html';html=pth.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="가설검정과 p값">\n'+'\n'.join(parts)+'\n</article>',html,count=1,flags=re.S)
 html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1가설검정과 p값, 유의수준·오류·검정력·효과크기를 그림과 예제로 구분해 설명합니다.\2',html,count=1,flags=re.S);pth.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
