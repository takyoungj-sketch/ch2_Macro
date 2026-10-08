"""Generate independent/paired comparisons and explicitly defined effect sizes."""
from pathlib import Path
from statistics import mean,stdev,variance
from html import escape
import math,json,re
from scipy.stats import t as student_t
ROOT=Path(__file__).resolve().parent

def welch(a,b):
 na,nb=len(a),len(b);va,vb=variance(a),variance(b);aa,bb=va/na,vb/nb;se=math.sqrt(aa+bb);df=(aa+bb)**2/(aa*aa/(na-1)+bb*bb/(nb-1));delta=mean(a)-mean(b);t=delta/se;crit=float(student_t.ppf(.975,df));pooled=math.sqrt(((na-1)*va+(nb-1)*vb)/(na+nb-2));d=delta/pooled
 return {'difference':delta,'se':se,'df':df,'t':t,'p':float(2*student_t.sf(abs(t),df)),'low':delta-crit*se,'high':delta+crit*se,'pooled_sd':pooled,'d':d,'g_approx':(1-3/(4*(na+nb-2)-1))*d}

def build():
 rows=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];a=[r['price'] for r in rows if r['group']=='상업'];b=[r['price'] for r in rows if r['group']=='주거'];w=welch(a,b);sensitivity=welch([r['price'] for r in rows if r['group']=='상업' and r['id']!=7],b)
 before=[80,100,120,140,160,180];after=[86,104,127,145,168,186];diff=[y-x for x,y in zip(before,after)];dm=mean(diff);ds=stdev(diff);dse=ds/math.sqrt(len(diff));crit=float(student_t.ppf(.975,len(diff)-1));paired={'before':before,'after':after,'differences':diff,'mean':dm,'sd':ds,'se':dse,'low':dm-crit*dse,'high':dm+crit*dse}
 result={'description':'공통 학습 자료 및 별도 가상 대응표본. 실제 인과효과가 아님.','welch':w,'without_id7':sensitivity,'paired':paired};(ROOT/'group-comparison-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def t(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def line(x,y,xx,yy,c='#64748b',extra=''):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{c}" {extra}/>'
 def fig(id,title,body,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{body}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 body=t(24,28,'평균 차이와 각 집단의 분포를 함께 봅니다')
 for i,(label,values) in enumerate([('주거',b),('상업',a)]):
  y=100+i*120;body+=t(24,y-40,f'{label} · n={len(values)} · 평균 {mean(values):.2f} · s={stdev(values):.2f}')+line(70,y,570,y)
  for j,value in enumerate(sorted(values)):body+=f'<circle cx="{70+value}" cy="{y-(j%3)*8}" r="4" fill="#2563eb" data-group="{label}" data-value="{value}"/>'
  body+=line(70+mean(values),y-28,70+mean(values),y+15,'#d97706','stroke-width="2"')
 for v in [0,100,200,300,400,500]:body+=t(70+v,265,v,'text-anchor="middle"')
 body+=t(24,300,'주황선: 평균 / 점의 세로 위치는 겹침을 줄이기 위한 표시')+t(410,330,'단가(만원/㎡)')
 f1=fig('groups','두 집단의 관측값과 평균',body,'그림 1. 공통 학습 자료 각 15건. 상업의 큰 관측 480도 표시했습니다. 서로 다른 유형이라는 사실만으로 무작위 표집이나 관측 간 독립성이 확인되는 것은 아닙니다.',355)
 body=t(24,28,'상업 − 주거: 차이 자체의 구간을 계산합니다');x=lambda value:100+value*3.3
 body+=line(x(0),65,x(0),185,'#d97706','stroke-dasharray="4 3"')+line(x(w['low']),120,x(w['high']),120,'#2563eb',f'stroke-width="4" data-diff-ci="true"')+f'<circle cx="{x(w["difference"])}" cy="120" r="5" fill="#2563eb"/>'
 body+=t(x(w['low']),153,f'{w["low"]:.2f}','text-anchor="middle"')+t(x(w['high']),153,f'{w["high"]:.2f}','text-anchor="middle"')+t(x(w['difference']),95,f'차이 {w["difference"]:.2f}','text-anchor="middle"')+t(x(0),210,'0','text-anchor="middle"')+t(24,250,f'Welch 95% 구간 / p={w["p"]:.4f} / 단위: 만원/㎡')
 f2=fig('difference','Welch 평균 차이의 구간',body,'그림 2. 독립 정규표본 모형을 적용한 교재 계산입니다. 표집 가정이 확인되지 않은 이 자료로 실제 시장의 유의성이나 용도의 인과효과를 주장하지 않습니다.',280)
 body=t(24,28,'같은 대상의 전후 값을 연결하면 짝을 볼 수 있습니다')
 for i,(v1,v2) in enumerate(zip(before,after)):
  yy=lambda value:300-(value-60)*1.7;body+=line(180,yy(v1),440,yy(v2),'#94a3b8',f'data-pair="{i+1}"')+f'<circle cx="180" cy="{yy(v1)}" r="4" fill="#2563eb"/><circle cx="440" cy="{yy(v2)}" r="4" fill="#d97706"/>'+t(165,yy(v1)+4,v1,'text-anchor="end"')+t(455,yy(v2)+4,v2)
 body+=t(180,324,'이전','text-anchor="middle"')+t(440,324,'이후','text-anchor="middle"')+t(24,360,'차이: 6 · 4 · 7 · 5 · 8 · 6 / 단위: 만원/㎡')
 f3=fig('pairs','가상 대응표본의 연결선',body,'그림 3. 같은 대상 6개의 전후 값을 가정한 별도 예제입니다. 공통 거래 자료와 무관하며 전후 변화만으로 처치의 인과효과를 알 수는 없습니다.',385)
 body=t(24,28,'원 단위 차이와 표준화 차이는 다른 척도입니다')
 for i,(label,value,scale,unit) in enumerate([('평균 차이',w['difference'],4,'만원/㎡'),('Cohen의 d',w['d'],280,'표준편차 단위')]):
  y=90+i*110;body+=t(24,y+17,label)+f'<rect x="160" y="{y}" width="{value*scale}" height="26" fill="#2563eb" data-effect="{i}"/>'+t(170+value*scale,y+19,f'{value:.2f}')+t(160,y+55,unit)
 body+=t(24,310,'각 행의 축척이 다릅니다. 막대 길이를 서로 비교하지 않습니다.')
 f4=fig('effect','효과크기의 두 표현',body,'그림 4. d=(상업 평균−주거 평균)/합동 표준편차입니다. 원 단위 차이를 표준화한 기술적 요약이며, 분산이 크게 다른 이 예제에서는 분모 선택에 민감함을 함께 밝혀야 합니다.',338)
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','핵심 이해','비교 대상과 차이의 방향을 먼저 정합니다','''<p>두 집단 비교의 출발점은 ‘무엇이 얼마나 다른가’입니다. 모평균의 차이 Δ=μ상업−μ주거를 관심 대상으로 정하면 양수는 상업이 높은 방향, 음수는 주거가 높은 방향입니다. 집단 순서를 바꾸면 부호도 바뀝니다.</p><p>평균·표본수·퍼짐과 분포를 확인한 뒤 차이, 신뢰구간, 필요하면 p값을 제시합니다. <a href="/learn/stats/hypothesis-tests/">13장의 유의성</a> 하나로 실질적 중요성을 대신하지 않습니다.</p>'''+f1)
 sec('design','독립표본과 대응표본','같은 건수보다 관측의 관계가 중요합니다','''<p><strong>독립표본</strong>은 두 집단의 관측이 서로 연결되지 않고, 집단 안에서도 분석에 필요한 독립성 가정이 성립하는 설계입니다. 주거·상업이라는 이름만으로 독립성이 보장되지는 않습니다. 같은 건물·지역·시점의 군집을 확인해야 합니다.</p><p><strong>대응표본</strong>은 같은 대상의 전후 측정이나 사전에 정한 짝이 있는 설계입니다. 이때는 짝 안의 차이를 계산합니다. 두 집단의 건수가 같거나 행 순서가 같다고 임의로 짝지으면 안 됩니다.</p><p>비교할 단위·기간·대상 범위도 맞춥니다. 거래 유형과 면적·위치·시점이 함께 다르면 단순 평균 차이는 여러 구성 차이가 섞인 결과입니다. 관찰 자료의 집단 차이를 원인과 결과로 바로 해석하지 않습니다.</p>''')
 sec('welch','독립표본의 Welch 방법','각 집단의 분산을 별도로 반영합니다','''<p>두 독립표본에서 평균 차이는 Δ̂=x̄₁−x̄₂, 표준오차는 <strong>SE(Δ̂)=√(s₁²/n₁+s₂²/n₂)</strong>입니다. 귀무가설 H₀:Δ=0의 통계량은 t=Δ̂/SE입니다. 두 집단의 SE를 그냥 더하지 않고 제곱을 더한 뒤 제곱근을 구합니다.</p><p>Welch 방법의 근사 자유도는 ν=(a+b)²/[a²/(n₁−1)+b²/(n₂−1)]이며 a=s₁²/n₁, b=s₂²/n₂입니다. 95% 구간은 Δ̂±t₀.₉₇₅,ν×SE입니다. 이 자유도는 보통 정수가 아니며 반올림하지 않은 값으로 계산할 수 있습니다.</p><p>Welch는 두 모집단 분산이 같다고 요구하지 않습니다. 반면 합동분산 t 검정은 공통 분산 가정을 사용합니다. Welch도 독립성과 적절한 분포·표본수 조건이 필요하며 심한 이상치·작은 표본의 치우침·군집 문제를 자동으로 해결하지 않습니다.</p>''')
 sec('example','공통 30건 계산','평균 차이의 구간을 직접 읽습니다',f'''<p>공통 학습 자료에서 상업 평균은 {mean(a):.2f}, 주거 평균은 {mean(b):.2f}만원/㎡이고 각각 15건입니다. 표본표준편차는 {stdev(a):.2f}와 {stdev(b):.2f}로 차이가 큽니다.</p><p>상업−주거 차이는 <strong>{w['difference']:.2f}</strong>, SE는 {w['se']:.2f}, 자유도는 {w['df']:.3f}, t는 {w['t']:.3f}, 양측 p는 {w['p']:.4f}입니다. 95% 구간은 <strong>{w['low']:.2f}~{w['high']:.2f}만원/㎡</strong>입니다.</p>'''+f2+'''<p>이 계산에서는 구간이 0을 포함하지 않으며 양측 p&lt;0.05입니다. 그러나 자료의 출처·무작위 표집·독립성이 확인되지 않아 실제 시장에 대한 유효한 추론으로 제시하지 않습니다. 상업으로 바꾸면 단가가 그만큼 오른다는 인과 해석도 할 수 없습니다.</p><p><a href="/learn/stats/graphs/#data">공통 원자료</a>와 <a href="../group-comparison-example.json">계산 JSON</a>을 확인할 수 있습니다. 개별 집단 평균의 두 구간이 겹치는지만 보고 평균 차이의 검정을 대신하지 않습니다.</p>''')
 sec('paired','대응표본의 계산','각 짝의 차이를 하나의 자료로 만듭니다','''<p>같은 대상의 이전·이후 값이라면 dᵢ=이후ᵢ−이전ᵢ를 먼저 계산합니다. 완전한 짝의 수를 n으로 놓고 차이의 평균 d̄와 표준편차 s_d를 구합니다. 표준오차는 s_d/√n, 통계량은 t=d̄/(s_d/√n)이며 자유도는 n−1입니다.</p>'''+f3+f'''<p>차이 6·4·7·5·8·6의 평균은 {dm:.2f}, s_d={ds:.3f}, SE={dse:.3f}입니다. 차이의 95% t 구간은 {paired['low']:.2f}~{paired['high']:.2f}만원/㎡입니다. 대상 간 원래 수준 차이가 크더라도 짝 안에서의 변화는 작고 일정할 수 있습니다.</p><p>대응표본 검정의 정규성 가정은 이전값·이후값 각각보다 ‘차이의 분포’에 관한 것입니다. 짝들 사이의 독립성도 필요합니다. 전후 모두 있는 완전한 짝을 사용했다면 제외된 짝과 결측 이유를 보고해야 합니다. 이 여섯 쌍은 작은 가상 예제이므로 실제 효과 증거가 아닙니다.</p>''')
 sec('effect','효과크기','차이를 원 단위와 표준화 단위로 함께 설명합니다',f'''<p>가장 직접적인 효과크기는 평균 차이 {w['difference']:.2f}만원/㎡입니다. 단위가 있으므로 분석 목적에 비추어 크기를 판단할 수 있습니다. 서로 다른 척도를 비교하려면 표준화한 차이를 보조적으로 사용할 수 있습니다.</p><p>독립집단 Cohen의 d를 <strong>d=(x̄₁−x̄₂)/s_p</strong>, s_p=√[((n₁−1)s₁²+(n₂−1)s₂²)/(n₁+n₂−2)]로 정의하겠습니다. 공통 자료에서는 s_p={w['pooled_sd']:.2f}, d={w['d']:.3f}입니다. 이 정의를 쓰는 것과 Welch 검정에서 등분산을 가정하는 것은 별개입니다.</p>'''+f4+f'''<p>합동 표준편차를 사용한 d는 공통 척도를 요약하지만, 분산 차이가 큰 경우 해석이 분모 선택에 민감합니다. 어떤 표준편차로 나누었는지 밝히고 원 단위 차이·구간·집단별 s를 우선 제시합니다.</p><p>작은 표본의 편향을 줄이는 Hedges의 g는 보정계수 J를 곱합니다. ν=n₁+n₂−2일 때 J≈1−3/(4ν−1) 근사를 쓰면 이 자료의 g≈{w['g_approx']:.3f}입니다. 이 장은 근사 보정을 표시했으며 정확 보정식과 마지막 자릿수가 다를 수 있습니다. 대응표본의 d_z=d̄/s_d는 다른 분모를 사용하므로 독립집단 d와 같은 크기 척도로 무심코 비교하지 않습니다.</p><p>작음·중간·큼이라는 관행적 경계는 분야의 실질적 중요성을 보장하지 않습니다. 효과크기도 표본에서 추정한 값이므로 불확실성이 있으며, 점추정 하나를 확정적 효과로 읽지 않습니다.</p>''')
 sec('sensitivity','민감도와 대안','큰 관측의 영향은 삭제보다 먼저 확인합니다',f'''<p>상업의 7번 480을 제외하는 민감도 비교에서는 상업 14건·주거 15건이고 차이는 {sensitivity['difference']:.2f}, Welch 구간은 {sensitivity['low']:.2f}~{sensitivity['high']:.2f}입니다. 원래 결과와 무엇이 달라지는지 확인할 수 있지만 더 작은 p값이나 좁은 구간을 얻으려고 삭제해서는 안 됩니다.</p><p>오류 여부와 조건 차이를 확인하고 포함·제외 결과와 이유를 함께 보고합니다. 치우침이나 큰 관측이 문제라면 비교 질문에 맞는 변환·강건한 방법·재표집을 검토할 수 있지만 이들도 가정이 있습니다.</p><p>Mann–Whitney 같은 순위 검정은 일반적으로 평균 차이의 검정이 아닙니다. 추가적인 같은 모양·위치 이동 가정 없이 무조건 ‘중앙값 검정’이라고 부르지 않습니다. 분석 방법을 바꾸면 어떤 모수를 비교하는지도 다시 밝혀야 합니다.</p>''')
 sec('report','해석과 보고','관측 차이와 인과효과를 분리합니다','''<p>보고에는 집단 정의와 순서, 독립·대응 설계, 각 n·평균·s, 차이와 구간, 방법과 p값, 효과크기의 분모, 누락·제외 기준을 포함합니다. 원 단위 차이에 대한 실질적 기준은 가능하면 결과를 보기 전에 정합니다.</p><p>시간·위치·면적·품질 등이 다르면 단순 집단 차이에 교란이 섞입니다. 대응 설계도 시간에 따른 공통 변화나 선택 편향을 자동으로 제거하지 않습니다. 인과 해석에는 연구 설계와 추가 가정이 필요합니다.</p><p>여러 유형을 모두 쌍별 비교하면 다중비교 문제가 생깁니다. 두 집단 방법을 반복 적용하기 전에 전체 질문과 비교 수를 정해야 합니다. 다음 장에서 여러 집단과 범주형 자료로 확장합니다.</p>''')
 sec('practice','확인 문제','검정 이름보다 비교 구조를 먼저 확인하세요','''<ol class="learn-exercises"><li>두 집단이 각각 15건이면 대응표본인가요?<details><summary>답과 해설</summary><p>아니요. 같은 대상이나 설계상 정한 짝이 있어야 합니다. 같은 건수나 행 순서는 근거가 아닙니다.</p></details></li><li>독립표본 평균 차이의 SE는 두 SE의 합인가요?<details><summary>답과 해설</summary><p>아니요. 독립일 때 √(SE₁²+SE₂²)입니다.</p></details></li><li>Welch 결과가 유의하면 집단 유형이 가격 차이의 원인인가요?<details><summary>답과 해설</summary><p>아니요. 유의성은 검정 가정 아래의 결과이며 교란이나 선택 편향을 배제하지 않습니다.</p></details></li><li>Cohen의 d가 같으면 원 단위 차이도 같나요?<details><summary>답과 해설</summary><p>아니요. 분모인 표준편차가 다르면 같은 d라도 원 단위 차이는 달라집니다.</p></details></li></ol>''')
 sec('macro','CH2 Macro에서 읽기','비교 조건과 구성 차이를 함께 봅니다','''<p>CH2 Macro에서 지역·유형·기간을 비교할 때 관측 단위와 단가 단위를 맞추고, 건수·분포·면적과 시점 구성을 함께 확인하세요. 이 장의 Welch·대응 t·효과크기 계산이 모든 화면에서 제공된다고 전제하지 않습니다.</p><p>큰 차이가 특정 물건의 저평가·고평가나 정책·용도의 인과효과를 입증하지는 않습니다. 시장 집단의 구조를 이해하는 근거로 읽습니다.</p><p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 통계 열기 →</a></p>''')
 sec('recap','정리와 참고자료','차이·구간·설계·효과크기를 함께 보고합니다','''<p>독립표본은 집단별 변동을, 대응표본은 짝 안의 차이를 반영합니다. 차이의 구간과 효과크기로 크기·불확실성을 설명하고, 유의성과 인과성을 혼동하지 않습니다.</p><p>다음 <a href="/learn/stats/multiple-groups-and-categorical/">15장 「여러 집단과 범주형 자료의 비교」</a>에서 여러 평균과 구성비의 비교로 확장합니다.</p><ul><li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/eda353.htm">NIST/SEMATECH: Two-Sample t-Test for Equal Means</a> — 독립·대응 설계와 Welch 산식.</li></ul><p class="learn-source-note">본문과 그림은 공통 학습 자료와 별도 가상 대응표본으로 직접 작성했습니다. 실제 시장 추론이 아닙니다. 참고자료 확인: 2026-10-07.</p>''')
 p=ROOT/'comparing-groups/index.html';html=p.read_text(encoding='utf-8');html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="두 집단 비교와 효과크기">\n'+'\n'.join(parts)+'\n</article>',html,count=1,flags=re.S)
 html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1독립표본과 대응표본, Welch 평균 차이와 신뢰구간, 효과크기를 예제와 그림으로 설명합니다.\2',html,count=1,flags=re.S);p.write_text(html,encoding='utf-8')
if __name__=='__main__':build()
