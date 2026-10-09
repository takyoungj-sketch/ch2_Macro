"""Build chapter 08 with explicitly fictional frequency examples."""
from pathlib import Path
from html import escape
import json,re
ROOT=Path(__file__).resolve().parent
EXAMPLE={'description':'08장 전용 가상 학습 자료. 실제 거래 및 서비스 성능이 아님.','table':{'A_B':18,'A_notB':22,'notA_B':12,'notA_notB':48},'screening':{'total':1000,'errors':20,'true_positive':18,'false_positive':98}}

def build():
 (ROOT/'probability-example.json').write_text(json.dumps(EXAMPLE,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def t(x,y,s,extra=''):return f'<text x="{x}" y="{y}" {extra}>{escape(str(s))}</text>'
 def line(x,y,xx,yy):return f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="#94a3b8"/>'
 def box(x,y,w,h,c,extra=''):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}" {extra}/>'
 def fig(id,title,b,cap,h):return f'<figure class="learn-chart learn-chart--wide"><svg viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=t(24,27,'100건을 겹치지 않는 네 묶음으로 나눕니다')
 for i,(key,n,c,label) in enumerate([('A_B',18,'#2563eb','A와 B 18'),('A_notB',22,'#93c5fd','A만 22'),('notA_B',12,'#f59e0b','B만 12'),('notA_notB',48,'#cbd5e1','둘 다 아님 48')]):
  start=sum(list(EXAMPLE['table'].values())[:i])
  for j in range(start,start+n):b+=box(40+(j%10)*26,55+(j//10)*26,22,22,c,f'data-cell="{key}"')
  b+=box(335,70+i*58,18,18,c)+t(365,85+i*58,label)
 b+=t(24,340,'한 칸 = 1건 / A: 주거, B: 면적 100㎡ 이상')
 f1=fig('events','사건의 교집합과 합집합',b,'그림 1. 08장 전용 가상 100건. A는 40건, B는 30건, 둘 다 해당하는 교집합은 18건입니다. 칸의 위치는 지리나 가격을 뜻하지 않습니다.',365)
 b=t(24,28,'조건이 바뀌면 분모가 바뀝니다')
 for i,(label,num,den) in enumerate([('P(A)',40,100),('P(A|B)',18,30),('P(B|A)',18,40)]):
  y=75+i*78;v=num/den;b+=t(24,y+18,label)+box(160,y,340,26,'#e2e8f0')+box(160,y,340*v,26,'#2563eb',f'data-numerator="{num}" data-denominator="{den}"')+t(510,y+19,f'{v:.0%}')+t(160,y+49,f'{num} / {den}건')
 b+=t(24,334,'各 막대의 전체 길이 = 해당 분모의 100%'.replace('各','각'))
 f2=fig('conditioning','조건부확률의 분모',b,'그림 2. 전체 중 주거는 40%, 큰 면적 중 주거는 60%, 주거 중 큰 면적은 45%입니다. 같은 교집합 18건도 분모에 따라 다른 비율이 됩니다.',361)
 b=t(24,28,'가지에서는 곱하고, 서로 겹치지 않는 경로는 더합니다')
 for x,y,xx,yy in [(60,175,250,100),(60,175,250,265),(285,100,490,65),(285,100,490,150),(285,265,490,230),(285,265,490,315)]:b+=line(x,y,xx,yy)
 for x,y,s in [(24,160,'전체'),(105,100,'P(A)=0.40'),(95,270,'P(Aᶜ)=0.60'),(225,83,'A'),(222,290,'Aᶜ'),(330,59,'P(B|A)=0.45'),(310,155,'P(Bᶜ|A)=0.55'),(320,215,'P(B|Aᶜ)=0.20'),(310,340,'P(Bᶜ|Aᶜ)=0.80'),(505,70,'B: 0.18'),(505,155,'Bᶜ: 0.22'),(505,235,'B: 0.12'),(505,320,'Bᶜ: 0.48')]:b+=t(x,y,s)
 b+=t(24,383,'P(B) = 0.40×0.45 + 0.60×0.20 = 0.30')
 f3=fig('tree','곱셈법칙과 전확률',b,'그림 3. 가상 100건의 분류를 확률나무로 표현했습니다. 끝의 값은 전체에 대한 결합확률이며 합계는 1입니다. 나무의 선 길이는 확률 크기를 뜻하지 않습니다.',410)
 d=EXAMPLE['screening'];b=t(24,28,'탐지율이 높아도 표시된 건이 모두 오류인 것은 아닙니다')
 for i,(label,total,flag,color) in enumerate([('실제 오류',20,18,'#2563eb'),('오류 아님',980,98,'#f59e0b')]):
  y=80+i*100;b+=t(24,y,label)+t(24,y+26,f'{total}건 중 {flag}건 표시')+box(240,y-15,flag*2.6,28,color,f'data-flagged="{flag}"')+t(250+flag*2.6,y+5,f'{flag}건')
 b+=t(24,289,'표시된 116건 = 실제 오류 18건 + 오류 아닌 98건')+t(24,324,'P(오류 | 표시) = 18 / 116 ≈ 15.52%')
 f4=fig('base-rate','기초 비율과 베이즈 정리',b,'그림 4. 별도 가상 1,000건의 탐지 예제. 실제 오류 비율 2%, 오류 탐지율 90%, 오탐률 10%를 가정했습니다. 막대 길이는 표시된 건수에 비례하며 서비스 성능이 아닙니다.',355)
 parts=[]
 def sec(id,label,title,body):parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{title}</h2>{body}</section>')
 sec('quick-start','핵심 이해','확률을 읽기 전에 어떤 경우를 세는지 정합니다','''<p>‘주거 거래일 확률’과 ‘면적이 큰 거래 중 주거일 확률’은 다릅니다. 앞 문장은 전체를, 뒤 문장은 조건에 맞는 일부를 기준으로 삼습니다. 확률을 이해하는 첫 단계는 <strong>대상과 조건, 분모</strong>를 정확히 정하는 것입니다.</p><p>이 장에서는 사건의 연산, 조건부확률, 독립, 곱셈법칙과 베이즈 정리를 배웁니다. <a href="/learn/stats/population-and-sampling/">모집단과 표본</a>을 먼저 익히면 관측 비율과 모집단 확률을 구별하는 데 도움이 됩니다. 여기의 100건·1,000건은 설명을 위해 별도로 만든 가상 자료이며 앞 장의 공통 30건과 다릅니다.</p>''')
 sec('events','표본공간과 사건','한 번의 결과와 결과의 묶음을 구별합니다','''<p>우연에 따라 결과가 정해지는 시행에서 가능한 결과 전체를 <strong>표본공간 Ω</strong>, 관심 있는 결과의 집합을 <strong>사건</strong>이라고 합니다. 예를 들어 고정된 목록 100건에서 각 건이 같은 확률로 뽑히도록 한 건을 추출하면, 결과는 선택된 거래의 ID이고 Ω는 100개 ID의 집합입니다.</p><p>A를 ‘주거’, B를 ‘면적 100㎡ 이상’으로 정하겠습니다. A∩B는 둘 다 해당하는 교집합, A∪B는 적어도 하나에 해당하는 합집합, Aᶜ는 주거가 아닌 여사건입니다. 합집합의 ‘또는’에는 둘 다 해당하는 경우도 포함합니다.</p>'''+f1+'''<div class="learn-data learn-data--full"><table><caption>08장 전용 가상 목록의 분할표 · 단위: 건</caption><thead><tr><th scope="col">유형</th><th scope="col">B: 100㎡ 이상</th><th scope="col">Bᶜ: 100㎡ 미만</th><th scope="col">합계</th></tr></thead><tbody><tr><th scope="row">A: 주거</th><td>18</td><td>22</td><td>40</td></tr><tr><th scope="row">Aᶜ: 비주거</th><td>12</td><td>48</td><td>60</td></tr><tr><th scope="row">합계</th><td>30</td><td>70</td><td>100</td></tr></tbody></table></div><p>이 예제는 유형과 면적의 결측이 없고 두 분류가 각각 전체를 빠짐없이 나눈다고 가정합니다. 실제 자료에서는 결측을 어느 분모에서 제외했는지도 밝혀야 합니다. <a href="../probability-example.json">예제의 집계값 JSON</a>을 확인할 수 있습니다.</p>''')
 sec('rules','확률의 기본 규칙','겹치는 경우를 두 번 더하지 않습니다','''<p>확률은 0 이상 1 이하이며 P(Ω)=1입니다. 여사건은 P(Aᶜ)=1−P(A), 합집합은 <strong>P(A∪B)=P(A)+P(B)−P(A∩B)</strong>로 계산합니다. 겹치는 부분을 한 번 빼야 중복 계산하지 않습니다.</p><p>각 ID를 같은 확률로 선택하는 이 목록에서는 P(A)=40/100=0.40, P(B)=30/100=0.30, P(A∩B)=18/100=0.18입니다. 따라서 P(A∪B)=0.40+0.30−0.18=0.52이고, 둘 다 아닌 확률은 0.48입니다.</p><p>‘해당 건수÷전체 건수’는 가능한 개별 결과들이 같은 확률일 때 바로 적용할 수 있습니다. 선택 확률이 다르면 각 결과의 확률을 더해야 합니다. 실제 표본의 관측 비율을 더 큰 모집단의 확률로 추정하려면 대표성과 표집 설계도 검토해야 합니다.</p><p>확률 0.4라고 해서 독립적인 10회 시행에서 반드시 4회 발생하는 것은 아닙니다. 같은 조건에서 반복한 상대도수는 흔들릴 수 있습니다. 확률 모형과 한 번 관측한 빈도를 구별하세요.</p>''')
 sec('conditional','조건부확률','조건 뒤의 사건이 새로운 분모가 됩니다','''<p><strong>P(A|B)</strong>는 ‘B라는 조건에서 A일 확률’입니다. P(B)&gt;0일 때 P(A|B)=P(A∩B)/P(B)입니다. 세로선 오른쪽이 조건입니다. 조건이 시간상 먼저 발생해야 한다는 뜻은 아닙니다.</p>'''+f2+'''<p>B인 30건만 놓고 보면 그중 A는 18건이므로 P(A|B)=18/30=0.60입니다. 반대로 A인 40건 중 B는 18건이므로 P(B|A)=18/40=0.45입니다. <strong>조건의 방향을 뒤집으면 같은 값이 된다고 보장할 수 없습니다.</strong></p><p>조건에 해당하는 건이 0건이면 이 빈도 방식으로 조건부확률을 계산할 수 없습니다. 0%라고 쓰는 대신 ‘해당 자료 없음’으로 구분해야 합니다. 또한 조건부 비율의 차이만으로 면적이 유형을 ‘원인으로서 바꾼다’고 말할 수 없습니다.</p>''')
 sec('independence','독립과 배반','서로 영향을 주지 않는 것과 함께 일어날 수 없는 것은 다릅니다','''<p>사건 A와 B가 <strong>독립</strong>이면 P(A∩B)=P(A)P(B)입니다. P(B)&gt;0일 때는 P(A|B)=P(A)와 같습니다. B를 안다고 A의 확률이 달라지지 않는다는 뜻입니다. 가상 목록은 0.18≠0.40×0.30이므로 이 추출 실험에서 A와 B는 독립이 아닙니다.</p><p><strong>배반</strong>은 두 사건이 동시에 일어날 수 없어 A∩B가 공집합인 경우입니다. 한 번 뽑은 거래가 주거이면서 비주거일 수 없다는 설정이 그 예입니다. 두 사건의 확률이 모두 양수라면 배반인 사건들은 독립이 아닙니다. 하나가 일어나면 다른 하나의 가능성이 0이 되기 때문입니다.</p><p>공정한 동전을 두 번 독립적으로 던지는 모형에서 첫째 앞면과 둘째 앞면의 교집합 확률은 1/2×1/2=1/4입니다. 반면 목록에서 비복원으로 두 건을 추출하면 앞의 선택이 뒤의 구성에 영향을 줍니다. 가상 100건에서 주거 두 건을 뽑을 확률은 (40/100)×(39/99)≈15.76%이며, 복원해 독립적으로 뽑는 경우의 16%와 다릅니다.</p><p>표본 비율이 우연히 비슷하다는 사실만으로 모집단의 독립을 입증할 수는 없습니다. 여기서는 고정된 가상 목록의 추출 확률을 계산하고 있습니다.</p>''')
 sec('tree','곱셈법칙과 전확률','경로의 확률을 계산해 전체로 합칩니다','''<p>일반적인 곱셈법칙은 <strong>P(A∩B)=P(A)P(B|A)</strong>입니다. 독립일 때만 조건부확률을 P(B)로 바꿀 수 있습니다. A와 Aᶜ는 전체를 겹치지 않게 나누므로 B로 가는 두 경로를 더하면 P(B)가 됩니다.</p>'''+f3+'''<p>이를 전확률법칙이라고 합니다. <strong>P(B)=P(A)P(B|A)+P(Aᶜ)P(B|Aᶜ)</strong>이며, 여기서는 0.4×0.45+0.6×0.2=0.3입니다. 집단별 비율 45%와 20%를 단순 평균한 32.5%는 전체 비율이 아닙니다. 집단 크기 40%와 60%를 가중치로 사용해야 합니다.</p>''')
 sec('bayes','베이즈 정리','조건의 방향을 바꿀 때 기초 비율을 반영합니다','''<p>곱셈법칙을 두 방향으로 쓰면 P(A∩B)=P(A)P(B|A)=P(B)P(A|B)입니다. 따라서 P(B)&gt;0에서 <strong>P(A|B)=P(B|A)P(A)/P(B)</strong>입니다. 이것이 베이즈 정리입니다. 가상 목록에서는 0.45×0.40/0.30=0.60입니다.</p><p>증거를 보기 전의 P(A)를 사전확률, A일 때 증거 B를 볼 확률 P(B|A)를 우도, 증거를 반영한 P(A|B)를 사후확률이라고 부릅니다. 우도는 이 경우 사건 B의 조건부확률이지만, 이를 A에 대한 확률분포처럼 읽으면 안 됩니다.</p>'''+f4+'''<p>이번에는 오류 여부를 확인한 별도 가상 목록 1,000건을 생각해 봅시다. 오류 20건 중 18건을 표시하고, 오류가 아닌 980건 중 98건도 표시하는 탐지 규칙을 가정합니다. 탐지율 P(표시|오류)=90%이지만, 우리가 알고 싶은 P(오류|표시)는 18/(18+98)≈15.52%입니다.</p><p>계산식은 (0.90×0.02)/(0.90×0.02+0.10×0.98)입니다. 사전확률 2%를 무시하면 결과를 크게 오해할 수 있습니다. 이 예제의 오탐률 10%는 ‘오류 아닌 건 중 표시된 비율’이며 ‘표시된 건 중 오류 아닌 비율’과 다릅니다. 탐지 규칙과 비율은 모두 가정이며 CH2 Macro의 성능 평가가 아닙니다.</p>''')
 sec('practice','확인 문제','먼저 분모와 조건의 방향을 말해 보세요','''<ol class="learn-exercises"><li>A 또는 B에 해당하는 거래는 몇 건인가요?<details><summary>답과 해설</summary><p>40+30−18=52건입니다. 둘 다 해당하는 18건을 두 번 세지 않도록 한 번 뺍니다.</p></details></li><li>‘주거 중 큰 면적’과 ‘큰 면적 중 주거’의 비율은 각각 얼마인가요?<details><summary>답과 해설</summary><p>각각 18/40=45%, 18/30=60%입니다. 조건에 따라 분모가 달라집니다.</p></details></li><li>배반인 두 사건의 확률이 모두 양수일 때 독립일 수 있나요?<details><summary>답과 해설</summary><p>아니요. 교집합 확률은 0이지만 두 확률의 곱은 양수이므로 독립 조건이 성립하지 않습니다.</p></details></li><li>오류 탐지율이 90%이면 표시된 거래의 90%가 오류인가요?<details><summary>답과 해설</summary><p>아니요. 조건의 방향이 반대입니다. 예제에서는 실제 오류의 기초 비율과 오탐을 반영하면 18/116≈15.52%입니다.</p></details></li></ol>''')
 sec('macro','CH2 Macro에서 읽기','필터를 적용하면 통계의 기준 집단도 바뀝니다','''<p>CH2 Macro에서 지역·기간·유형·면적 필터를 적용하면 결과를 읽는 분모가 달라집니다. ‘선택한 거래 중 주거의 비율’과 ‘전체 지역 거래 중 주거의 비율’을 혼동하지 마세요. 결측·정정·제외 규칙과 기준 건수도 함께 확인해야 합니다.</p><p>필터 결과의 비율을 미래 거래의 발생 확률이나 개별 물건의 가격 상승 확률로 그대로 바꿔 읽을 수는 없습니다. 그런 추론에는 모집단·표집·시간 변화에 관한 별도의 모형과 검증이 필요합니다. 이 장은 확률 계산의 기초를 설명하며 별도의 서비스 예측 기능을 전제하지 않습니다.</p><p class="learn-macro-cta"><a href="https://macro.ch2data.com/land/">CH2 Macro 토지 통계 열기 →</a></p>''')
 sec('recap','정리와 참고자료','같은 숫자도 무엇을 조건으로 삼느냐에 따라 뜻이 달라집니다','''<p>확률은 정한 실험과 사건에 대해 계산합니다. 합집합에서는 중복을 빼고, 조건부확률에서는 분모를 좁히며, 경로에서는 조건부확률을 곱합니다. 독립과 배반을 구별하고 조건을 뒤집을 때는 기초 비율을 반영하세요.</p><p>다음 <a href="/learn/stats/probability-distributions/">09장 「확률변수와 확률분포」</a>에서는 우연한 결과를 숫자로 나타내고 그 분포를 읽습니다.</p><ul><li><a href="https://openstax.org/books/introductory-statistics-2e/pages/3-1-terminology">OpenStax, Introductory Statistics 2e §3.1</a> — 표본공간·사건·조건부확률의 용어.</li><li><a href="https://openstax.org/books/introductory-statistics-2e/pages/3-3-two-basic-rules-of-probability">OpenStax §3.3</a> — 확률의 덧셈·곱셈법칙.</li></ul><p class="learn-source-note">설명과 그림은 별도 가상 집계값으로 직접 작성했습니다. 실제 거래 통계나 서비스 성능이 아닙니다. 참고자료 확인: 2026-10-07.</p>''')
 p=ROOT/'probability/index.html';p.parent.mkdir(exist_ok=True)
 s=p.read_text(encoding='utf-8') if p.exists() else (ROOT/'iqr-outliers/index.html').read_text(encoding='utf-8')
 s=s.replace('https://ch2data.com/learn/stats/iqr-outliers/','https://ch2data.com/learn/stats/probability/')
 s=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded" aria-label="확률의 기초와 조건부확률">\n'+'\n'.join(parts)+'\n</article>',s,count=1,flags=re.S)
 s=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1사건과 확률, 조건부확률·독립·베이즈 정리를 가상 거래 예제와 그림으로 익힙니다.\2',s,count=1,flags=re.S);p.write_text(s,encoding='utf-8')
if __name__=='__main__':build()
