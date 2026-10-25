"""Chapter 23: splitting, selection and leakage."""
from pathlib import Path
from statistics import mean,median,pstdev
from html import escape
import json,re
ROOT=Path(__file__).resolve().parent

def build():
 train=[10,10,10,10,20,60];valid=[11,12,13];test=[9,11,16]
 candidates={name:dict(value=fn(train),validation_MAE=mean(abs(y-fn(train)) for y in valid)) for name,fn in [('mean',mean),('median',median)]}
 selected=min(candidates,key=lambda k:candidates[k]['validation_MAE']);final=median(train+valid);test_mae=mean(abs(y-final) for y in test)
 scale_train=[40,60,80];held=140;mu=mean(scale_train);sd=pstdev(scale_train);all_mu=mean(scale_train+[held]);all_sd=pstdev(scale_train+[held])
 d=dict(description='자료 분할과 전처리를 설명하기 위한 가상 자료.',train=train,validation=valid,test=test,candidates=candidates,selected=selected,refit_value=final,test_MAE=test_mae,scaling=dict(train=scale_train,held_out=held,train_mean=mu,train_sd=sd,train_z=(held-mu)/sd,all_mean=all_mu,all_sd=all_sd,leaked_z=(held-all_mu)/all_sd))
 (ROOT/'split-example.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 def tx(x,y,s):return f'<text x="{x}" y="{y}">{escape(str(s))}</text>'
 def box(x,y,w,h,c):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{c}"/>'
 def line(x,y,a,b):return f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="#94a3b8"/>'
 def fig(id,title,b,cap,h=410):return f'<figure class="learn-chart learn-chart--wide"><svg class="split-chart-svg" viewBox="0 0 640 {h}" role="img" aria-labelledby="{id}-title {id}-desc"><title id="{id}-title">{title}</title><desc id="{id}-desc">{cap}</desc>{b}</svg><figcaption class="learn-chart__caption">{cap}</figcaption></figure>'
 b=tx(24,28,'자료의 역할: 학습 → 선택 → 마지막 평가')
 for y,title,desc in [(70,'학습','전처리와 계수를 학습'),(165,'검증','후보·설정·임계값을 선택'),(260,'시험','선택한 절차의 성능을 마지막에 평가')]:b+=box(90,y,455,65,'#eaf2ff')+tx(112,y+25,title)+tx(112,y+49,desc)
 b+=tx(305,154,'↓')+tx(305,249,'↓')+tx(24,380,'시험 성적에 맞춰 다시 선택하면 독립 평가의 역할을 잃습니다')
 g1=fig('roles','세 자료의 역할',b,'그림 1. 역할을 구분한 개념도입니다. 세 개의 고정 파일만이 유일한 구현은 아니며 교차검증으로 학습·검증 역할을 반복할 수 있습니다.')
 b=tx(24,28,'활용 상황에 맞춘 분할: 두 가지 별도 예시')+tx(24,80,'미래 결과 예측: 시간 순서')
 for x,w,label,c in [(65,230,'과거 학습','#dbeafe'),(305,115,'검증','#dcfce7'),(430,140,'미래 시험','#ffedd5')]:b+=box(x,100,w,55,c)+tx(x+14,133,label)
 b+=tx(65,190,'시간 → · 계약일≠공개일: 당시 이용 가능한 입력만 사용')+tx(24,245,'새 단지 적용: 단지 전체를 한쪽에 배정')
 for i,(label,c) in enumerate([('단지 A','#dbeafe'),('단지 B','#dbeafe'),('단지 C','#dcfce7'),('단지 D','#ffedd5')]):b+=box(65+i*130,267,115,55,c)+tx(80+i*130,300,label)
 for i,label in enumerate(['학습','학습','검증','시험']):b+=tx(80+i*130,344,label)
 b+=tx(24,385,'시간과 새 집단이 모두 중요하면 두 조건을 함께 설계합니다')
 g2=fig('design','시간과 집단을 반영한 분할',b,'그림 2. 가상 시간·단지 개념도입니다. 위는 시간 순서, 아래는 집단 격리의 원리이며 특정 배정 비율을 권장하는 그림이 아닙니다.')
 b=tx(24,28,'같은 평가 면적 140㎡의 표준화 좌표 비교')
 for key,y,label,center,spread,z,color in [('train',80,'학습 40·60·80㎡만 사용',mu,sd,d['scaling']['train_z'],'#2563eb'),('all',230,'평가 140㎡까지 포함한 누수',all_mu,all_sd,d['scaling']['leaked_z'],'#d97706')]:
  b+=f'<g data-scale="{key}">'+tx(30,y,label)+tx(30,y+28,f'평균 {center:.0f}㎡ · 모집단형 SD {spread:.2f}㎡ · z={z:.2f}')+line(90,y+80,565,y+80)
  for tick in range(6):b+=tx(86+tick*90,y+105,tick)
  b+=f'<circle data-z="{key}" cx="{90+90*z}" cy="{y+80}" r="7" fill="{color}"/>'+tx(570,y+85,'z')+'</g>'
 g3=fig('scaling','평가 면적 140㎡: 표준화 기준과 좌표',b,'그림 3. 별도 가상 면적 자료입니다. 두 축은 같은 z 배율이며 SD는 n으로 나눕니다. 좌표 변화가 모든 모형의 예측 성능 변화를 뜻하지는 않습니다.',380)
 g3=g3.replace('<svg ', '<div class="split-controls" hidden=""><label for="split-scale">표준화 기준 선택</label><select id="split-scale"><option value="train">학습 자료로 표준화</option><option value="all">전체 자료로 표준화 — 누수 사례</option></select><p id="split-scale-status" role="status" aria-live="polite"></p></div><svg ',1)
 b=tx(24,28,'가상 목표값: 검증 MAE로 상수 예측 규칙 선택')+line(110,320,560,320)
 for i,(label,v,c) in enumerate([('학습 평균',candidates['mean']['validation_MAE'],'#94a3b8'),('학습 중앙값',candidates['median']['validation_MAE'],'#2563eb')]):
  xx=210+i*210;b+=box(xx-40,320-v*25,80,v*25,c)+tx(xx-10,305-v*25,f'{v:.1f}')+tx(xx-40,350,label)
 for v in [0,2,4,6,8]:b+=tx(65,325-v*25,v)
 b+=tx(24,390,f'중앙값 규칙 선택 → 학습+검증 재적합 → 시험 MAE {test_mae:.2f}')
 g4=fig('selection','선택과 최종 평가의 분리',b,'그림 4. 막대는 검증 오차만 비교합니다. 시험 오차는 선택과 재적합을 끝낸 뒤 한 번 계산했습니다. 작은 가상 예제로 성능 우열의 일반적 근거가 아닙니다.',420)
 parts=render_content([g1,g2,g3,g4])
 p=ROOT/'train-validation-test/index.html';p.parent.mkdir(exist_ok=True);html=p.read_text(encoding='utf-8') if p.exists() else (ROOT/'supervised-unsupervised/index.html').read_text(encoding='utf-8').replace('https://ch2data.com/learn/stats/supervised-unsupervised/','https://ch2data.com/learn/stats/train-validation-test/')
 html=re.sub(r'<article.*?</article>','<article class="learn-chapter learn-chapter--expanded learn-chapter--edited" aria-label="학습·검증·시험 자료와 데이터 누수">'+'\n'.join(parts)+'</article>',html,count=1,flags=re.S);html=re.sub(r'(name="description"\s+content=").*?("\s*/>)',r'\1학습·검증·시험 역할, 시간·집단 분할과 전처리·변수 선택의 데이터 누수를 예제로 학습합니다.\2',html,count=1,flags=re.S);html=re.sub(r'learn-stats\.css\?v=[^"\s]+','learn-stats.css?v=20261023-1',html);html=add_assets(html,d);p.write_text(html,encoding='utf-8')

def add_assets(html,data):
 html=html.replace('별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.','활용도는 CH2 Macro의 분석 결과를 이해하는 데 얼마나 도움이 되는지를 나타냅니다.')
 if 'train-validation-test/chapter.css' not in html:html=html.replace('</head>','<link rel="stylesheet" href="/learn/stats/train-validation-test/chapter.css?v=20261025-1" /></head>')
 payload='<script type="application/json" id="split-data">'+json.dumps(data,ensure_ascii=False)+'</script>'
 if 'id="split-data"' in html:html=re.sub(r'<script type="application/json" id="split-data">.*?</script>',lambda _:payload,html,flags=re.S)
 else:html=html.replace('</body>',payload+'</body>')
 if 'train-validation-test/experiment.js' not in html:html=html.replace('</body>','<script type="module" src="/learn/stats/train-validation-test/experiment.js?v=20261025-1"></script></body>')
 return html

def render_content(graphs):
 page=ROOT/'train-validation-test/index.html'
 old=page.read_text(encoding='utf8')
 refs=re.search(r'<details class="learn-references">.*?</details>',old,re.S)[0]
 source=(ROOT/'train-validation-test/content.md').read_text(encoding='utf8').replace('**','')
 formulas={r'z=\frac{x-\bar x}{s}':'z = (x−x̄)/s',r'z=\frac{140-60}{16.33}\approx4.90':'z = (140−60)/16.33 ≈ 4.90',r'z=\frac{140-80}{37.42}\approx1.60':'z = (140−80)/37.42 ≈ 1.60',r'MAE=\frac{2+0+5}{3}\approx2.33':'MAE = (2+0+5)/3 ≈ 2.33'}
 source=re.sub(r'\\\[\s*\n(.*?)\n\\\]',lambda m:formulas[m[1].strip()],source,flags=re.S)
 def inline(t):
  return re.sub(r'`([^`]+)`',r'<code>\1</code>',escape(t))
 def render(block):
  lines=block.strip().splitlines();i=0;out=[]
  while i<len(lines):
   line=lines[i].strip();i+=1
   if not line or line=='---':continue
   if line.startswith('### '):out.append('<h3>'+inline(line[4:])+'</h3>');continue
   if line.startswith('[그림 '):out.append(graphs[int(re.search(r'그림 (\d)',line)[1])-1]);continue
   if line=='[CH2 Macro 통계·데이터분석 열기 →]':out.append('<p><a href="https://macro.ch2data.com/">CH2 Macro 통계·데이터분석 열기 →</a></p>');continue
   if line=='▶ 참고자료':out.append(refs);continue
   if line.startswith('▶ '):
    rest=[]
    while i<len(lines) and lines[i].strip()!='---':rest.append(lines[i]);i+=1
    out.append('<details class="learn-more"><summary>'+inline(line[2:])+'</summary><div class="learn-more__body">'+render('\n'.join(rest))+'</div></details>');continue
   if line.startswith('|'):
    rows=[line]
    while i<len(lines) and lines[i].strip().startswith('|'):rows.append(lines[i].strip());i+=1
    cells=[[c.strip() for c in row.strip('|').split('|')] for row in rows]
    cells=[row for row in cells if not all(re.fullmatch(r'[:\- ]+',c) for c in row)]
    out.append('<div class="learn-data learn-data--full"><table><thead><tr>'+''.join('<th scope="col">'+inline(c)+'</th>' for c in cells[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join(('<th scope="row">'+inline(c)+'</th>') if j==0 else '<td>'+inline(c)+'</td>' for j,c in enumerate(row))+'</tr>' for row in cells[1:])+'</tbody></table></div>');continue
   if line.startswith('- '):
    items=[line[2:]]
    while i<len(lines) and lines[i].startswith('- '):items.append(lines[i][2:]);i+=1
    out.append('<ul>'+''.join('<li>'+inline(item)+'</li>' for item in items)+'</ul>');continue
   out.append('<p'+(' class="split-formula"' if line.startswith(('z =','MAE =')) else '')+'>'+inline(line)+'</p>')
  return '\n'.join(out)
 ids=['quick-start','roles','evaluation','target','design','availability','ratio','leakage','scaling','preprocessing','selection','test-use','macro','practice','recap']
 parts=[]
 for id,section in zip(ids,re.split(r'^## ',source,flags=re.M)[1:],strict=True):
  label,body=section.split('\n',1);heading=re.search(r'^### (.+)$',body,re.M)[1];body=re.sub(r'^### .+\n','',body,count=1,flags=re.M)
  if id=='practice':
   qs=[]
   for q in re.split(r'^\d+\. ',body,flags=re.M)[1:]:
    question,answer=q.split('▶ 답과 해설',1)
    qs.append('<li>'+inline(question.strip())+'<details><summary>답과 해설</summary><div class="learn-more__body">'+render(answer)+'</div></details></li>')
   content='<ol class="learn-exercises">'+''.join(qs)+'</ol>'
  else:content=render(body)
  if id=='macro':content+=macro_notes()
  if id=='leakage':content+='<p class="learn-source-note">동일 거래의 중복 행이나 같은 사건에서 파생된 자료가 학습·평가 양쪽에 배정되는지도 확인합니다.</p>'
  if id=='quick-start':content=content.replace('<ul>','<ul class="learn-objectives">',1)
  if id=='test-use':content+='<span id="audit" aria-hidden="true"></span>'
  content=content.replace('교차검증은 26장에서','교차검증은 <a href="/learn/stats/cross-validation/">26장</a>에서').replace('24장 「과적합과 편향–분산의 균형」','<a href="/learn/stats/overfitting/">24장 「과적합과 편향–분산의 균형」</a>')
  parts.append(f'<section class="learn-chapter__step" id="{id}" data-toc-label="{label}"><p class="learn-chapter__label">{label}</p><h2>{heading}</h2>{content}</section>')
 return parts

def macro_notes():
 return '<details class="learn-more"><summary>현재 구현에서 확인한 평가 방식과 정보 시점의 한계</summary><div class="learn-more__body"><p>확인한 복합 회귀의 롤링 CV는 계약연도 기준으로 과거를 학습하고 이후 연도를 평가합니다. 로그 역변환 보정과 시점 보정은 각 학습 fold에서 구합니다. 다만 설계행렬은 전체 표본에서 만든 뒤 연도로 나누는 경로가 있어, 범주 구성까지 모두 학습 fold 내부에서 정한다고 설명할 수는 없습니다. 화면의 탐색 CV·확인 CV와 교재의 독립 시험 개념은 실제 후보 선택에 사용된 이력을 함께 확인해야 합니다.</p><p>집합 주거 지역회귀는 후보별 선택 변수의 결측 조건으로 적격 단지를 정한 뒤 무작위 Holdout을 나눕니다. 그 오차를 후보 선택에 사용하므로 최종 독립 시험 점수와 구별합니다. 후보별 평가 단지가 달라질 수 있고 범주 구성에도 전체 적격 자료를 참조하는 경로가 있습니다. 동일 표본 비교와 전처리 경계는 별도 점검 사항입니다.</p><p>계약연도 분할이 신고·공개 당시의 정보 가용성이나 새 단지·지역 분리를 자동 보장하지는 않습니다. 확인한 토지 거래 ORM에는 contract_date와 updated_at이 있지만 updated_at을 원천 공개일로 간주할 수 없습니다. 속성 원장에는 판본 연도·스냅샷·원천 파일을 기록하는 경로가 있으나, 이 정보만으로 거래별 최초 공개·접수·취득 시점 전체를 확인한 것은 아닙니다. 확인되지 않은 시점을 새 필드처럼 가정하지 않습니다.</p><p>이 장의 표준화·선택 실험은 별도 가상 자료입니다. 실제 회귀·변수 선택·데이터 파이프라인은 변경하지 않았으며, 시점 이력과 검증 정책은 별도 검토 대상으로 기록했습니다.</p></div></details>'

if __name__=='__main__':build()
