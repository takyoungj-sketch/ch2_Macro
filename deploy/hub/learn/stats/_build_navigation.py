"""Generate navigation from course.json. Run after changing the course order."""
from pathlib import Path
import json,re,html
ROOT=Path(__file__).resolve().parent
LEVELS={3:('★★★','핵심'),2:('★★☆','권장'),1:('★☆☆','심화')}

def badge(item):
 stars,label=LEVELS[item['macro_relevance']]
 return f'<span class="learn-relevance" aria-label="Macro 활용도 {item["macro_relevance"]}단계, {label}"><span aria-hidden="true">{stars}</span></span>'

def guide():
 return '<p class="learn-relevance-guide">Macro 활용도: ★★★ 핵심 · ★★☆ 권장 · ★☆☆ 심화<br>별은 Macro 결과 이해에 도움이 되는 정도이며, 학습 순서나 선수 지식을 대신하지 않습니다.</p>'

def generate():
 groups=json.loads((ROOT/'course.json').read_text(encoding='utf-8'))
 items=[i for g in groups for i in g['items']]
 live=[i for i in items if not i['soon']]
 assert all(i.get('macro_relevance') in LEVELS for i in items)
 toc=ROOT/'learn-stats-toc.js'
 s=toc.read_text(encoding='utf-8')
 s=re.sub(r'  const ROADMAP = \[.*?\n\];','  const ROADMAP = '+json.dumps(groups,ensure_ascii=False,indent=2)+';',s,count=1,flags=re.S)
 toc.write_text(s,encoding='utf-8')
 home=ROOT/'index.html';s=home.read_text(encoding='utf-8')
 blocks=[]
 for g in groups:
  entries=[]
  for i in g['items']:
   label=html.escape(i['n']+'. '+i['title'])
   entries.append(f'<li data-macro-relevance="{i["macro_relevance"]}">'+ (f'<span class="is-soon">{label} · 작성 예정</span>' if i['soon'] else f'<a href="/learn/stats/{i["slug"]}/">{label} {badge(i)}</a>')+'</li>')
  blocks.append(f'<section class="learn-roadmap__group"><h2>{html.escape(g["group"])}</h2><ul class="learn-roadmap__list">'+''.join(entries)+'</ul></section>')
 s=re.sub(r'<main class="learn-roadmap".*?</main>','<main class="learn-roadmap" aria-label="학습 로드맵">'+''.join(blocks)+'</main>',s,flags=re.S)
 controls='<div class="learn-relevance-controls">'+guide()+'<button class="learn-core-filter" type="button" aria-pressed="false" hidden>★★★ 핵심 장만 보기</button><p class="learn-filter-status" role="status">전체 32개 장</p></div>'
 s=re.sub(r'<div class="learn-relevance-controls">.*?</div>\s*','',s,flags=re.S)
 s=s.replace('<main class="learn-roadmap"',controls+'\n<main class="learn-roadmap"',1)
 home.write_text(s,encoding='utf-8')
 for g in groups:
  for i in g['items']:
   if i['soon']:continue
   p=ROOT/i['slug']/'index.html';s=p.read_text(encoding='utf-8');label=html.escape(i['n']+'. '+i['title'])
   s=re.sub(r'<title>.*?</title>',f'<title>{label} | 통계학 &amp; 데이터 분석</title>',s,count=1)
   s=re.sub(r'(<h1 class="hero__title">).*?(</h1>)',lambda m:m[1]+label+m[2],s,count=1,flags=re.S)
   s=re.sub(r'<p class="learn-chapter-relevance">.*?</p>\s*','',s,flags=re.S)
   s=re.sub(r'<p class="learn-relevance-guide">.*?</p>\s*','',s,flags=re.S)
   s=re.sub(r'(</h1>)',lambda m:m[1]+'\n<p class="learn-chapter-relevance">Macro 활용도 '+badge(i)+'</p>\n'+guide(),s,count=1)
   s=re.sub(r'(<p class="hero__eyebrow">).*?(</p>)',lambda m:m[1]+html.escape(g['group'])+m[2],s,count=1,flags=re.S)
   idx=live.index(i);prev=live[idx-1] if idx else None;nxt=live[idx+1] if idx+1<len(live) else None
   nav=['<nav class="learn-chapter-nav" aria-label="장 이동">']
   nav.append(f'<a href="/learn/stats/{prev["slug"]}/">← {html.escape(prev["n"]+". "+prev["title"])}</a>' if prev else '<a href="/learn/stats/">← 전체 과정</a>')
   if nxt:nav.append(f'<a href="/learn/stats/{nxt["slug"]}/">{html.escape(nxt["n"]+". "+nxt["title"])} →</a>')
   nav.append('</nav>')
   skipped=[x['n'] for x in items if i['n']<x['n']<(nxt['n'] if nxt else '33') and x['soon']]
   if skipped:nav.append('<p class="learn-nav-note">'+', '.join(skipped)+'장은 작성 중입니다. 다음 링크는 현재 읽을 수 있는 장으로 연결됩니다.</p>')
   s=re.sub(r'<nav class="learn-chapter-nav".*?</nav>(?:\s*<p class="learn-nav-note">.*?</p>)?','\n'.join(nav),s,count=1,flags=re.S)
   p.write_text(s,encoding='utf-8')
 for p in ROOT.rglob('index.html'):
  s=p.read_text(encoding='utf-8');s=re.sub(r'(learn-stats(?:-toc\.js|\.css))\?v=[^"\s]+',r'\1?v=20261023-1',s)
  p.write_text(s,encoding='utf-8')
if __name__=='__main__':generate()
