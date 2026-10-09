"""Validate the course manifest, every available page and local link/anchor."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit,unquote
import json,re,sys
ROOT=Path(__file__).resolve().parent
HUB=ROOT.parent.parent
class Page(HTMLParser):
 def __init__(self,text):
  super().__init__();self.ids=[];self.refs=[];self.feed(text)
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if 'id' in d:self.ids.append(d['id'])
  for name in ('href','src'):
   if name in d:self.refs.append(d[name])
def main():
 errors=[]
 groups=json.loads((ROOT/'course.json').read_text(encoding='utf-8'))
 items=[i for g in groups for i in g['items']]
 if [i['n'] for i in items]!=[f'{i:02}' for i in range(1,len(items)+1)]:errors.append('Invalid chapter numbering')
 if len({i['slug'] for i in items})!=len(items):errors.append('Duplicate chapter slug')
 available=[i for i in items if not i['soon']]
 toc=(ROOT/'learn-stats-toc.js').read_text(encoding='utf-8')
 embedded=re.search(r'const ROADMAP = (\[.*?\n\]);',toc,re.S)
 if not embedded or json.loads(embedded[1])!=groups:errors.append('Run _build_navigation.py: JS manifest differs')
 for item in items:
  p=ROOT/item['slug']/'index.html'
  if p.exists()==item['soon']:errors.append(f'{item["slug"]}: availability mismatch')
 pages=list(ROOT.rglob('index.html'))
 for p in pages:
  text=p.read_text(encoding='utf-8');parsed=Page(text)
  if '\ufffd' in text:errors.append(f'{p}: encoding corruption')
  if len(parsed.ids)!=len(set(parsed.ids)):errors.append(f'{p}: duplicate IDs')
  if 'learn-stats-toc.js' not in text:errors.append(f'{p}: missing navigation script')
  if p.parent!=ROOT:
   item=next((i for i in available if i['slug']==p.parent.name),None)
   if not item:errors.append(f'{p}: missing manifest entry')
   elif f'{item["n"]}. {item["title"]}' not in text:errors.append(f'{p}: incorrect heading')
  base='/'+p.relative_to(HUB).as_posix()
  for ref in parsed.refs:
   u=urlsplit(urljoin(base,ref))
   if u.scheme or u.netloc:continue
   target=HUB/unquote(u.path).lstrip('/')
   if target.is_dir():target=target/'index.html'
   if not target.exists():errors.append(f'{p.parent.name}: missing {ref}');continue
   if u.fragment and target.suffix=='.html' and unquote(u.fragment) not in Page(target.read_text(encoding='utf-8')).ids:errors.append(f'{p.parent.name}: missing anchor {ref}')
 required={'iqr-outliers':['iqr-multiplier'],'model-fit':['r-squared','adj-r-squared','mape'],'cross-validation':['cross-validation','cv-mape','model-recommendation']}
 for slug,ids in required.items():
  parsed=Page((ROOT/slug/'index.html').read_text(encoding='utf-8'))
  for id in ids:
   if id not in parsed.ids:errors.append(f'{slug}: legacy #{id} missing')
 data=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows']
 assert len(data)==30 and sum(r['group']=='주거' for r in data)==15
 assert sum(r['group']=='상업' for r in data)==15
 assert min(r['area'] for r in data)==22 and max(r['area'] for r in data)==310
 assert min(r['price'] for r in data)==62 and max(r['price'] for r in data)==480
 assert round((100+120+0)/3,1)==73.3
 ch=(ROOT/'data-and-variables/index.html').read_text(encoding='utf-8')
 assert ch.count('<svg ')==4 and ch.count('<circle ')==30

 sampling=json.loads((ROOT/'sampling-example.json').read_text(encoding='utf-8'))
 population=sampling['population'];by_id={r['id']:r for r in population}
 frame=[by_id[i] for i in sampling['frame_ids']];selected=[by_id[i] for i in sampling['selected_ids']]
 assert len(population)==100 and len(frame)==40 and len(selected)==20
 assert set(sampling['selected_ids']) <= set(sampling['frame_ids']) <= set(by_id)
 for rows,expected,key in [(population,120,'population_mean'),(frame,150,'frame_mean'),(selected,150,'sample_mean')]:
  assert sum(r['price'] for r in rows)/len(rows)==expected==sampling[key]
 from statistics import mean,pstdev
 import random,xml.etree.ElementTree as ET
 rng=random.Random(sampling['seed'])
 ch2=(ROOT/'population-and-sampling/index.html').read_text(encoding='utf-8')
 charts=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch2,re.S)]
 assert len(charts)==4
 composition=next(svg for svg in charts if svg.attrib['aria-labelledby'].startswith('composition'))
 labels=[t.text for t in composition.findall('text')]
 assert 'A 80%' in labels and 'B 20%' in labels and labels.count('B 50%')==2
 repeat=next(svg for svg in charts if svg.attrib['aria-labelledby'].startswith('sampling-repeat'))
 bars=[r for r in repeat.findall('rect')]
 expected_bars=[]
 for idx,t in enumerate(sampling['trials']):
  source=population if t['source']=='population' else frame
  values=[mean(r['price'] for r in rng.sample(source,t['n'])) for _ in range(t['repetitions'])]
  from collections import Counter
  assert dict(Counter(values))=={float(v):c for v,c in t['frequencies'].items()}
  assert abs(mean(values)-t['mean'])<1e-10 and abs(pstdev(values)-t['sd'])<1e-10
  for value,count in t['frequencies'].items():expected_bars.append((80+(float(value)-100)*5.15-3,75+idx*110+62-count*.25,count*.25))
 assert len(bars)==len(expected_bars)
 for bar,(x,y,h) in zip(bars,expected_bars):
  assert abs(float(bar.attrib['x'])-x)<1e-8 and abs(float(bar.attrib['y'])-y)<1e-8 and abs(float(bar.attrib['height'])-h)<1e-8
 print('Chapter 02 population, 2,000 repeated samples and plotted bar coordinates verified')

 ch3=(ROOT/'graphs/index.html').read_text(encoding='utf-8')
 charts3=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch3,re.S)]
 assert len(charts3)==5
 histogram=next(svg for svg in charts3 if svg.attrib['aria-labelledby'].startswith('histogram-widths'))
 for width in [60,120]:
  bars=[r for r in histogram.findall('rect') if r.attrib.get('data-bin-width')==str(width)]
  counts=[sum(low<=r['price']<low+width for r in data) for low in range(60,540,width)]
  assert len(bars)==len(counts) and sum(counts)==30
  for idx,(bar,count) in enumerate(zip(bars,counts)):
   assert int(bar.attrib['data-count'])==count
   assert abs(float(bar.attrib['height'])-count*5)<1e-8
   assert abs(float(bar.attrib['x'])-(70+idx*width*1.1))<1e-8
 scatter=next(svg for svg in charts3 if svg.attrib['aria-labelledby'].startswith('grouped-scatter'))
 points=[e for e in scatter if 'data-observation' in e.attrib]
 assert len(points)==30
 for point in points:
  row=next(r for r in data if r['id']==int(point.attrib['data-observation']))
  x=float(point.attrib.get('cx',point.attrib.get('x')))+(4.5 if point.tag=='rect' else 0)
  y=float(point.attrib.get('cy',point.attrib.get('y')))+(4.5 if point.tag=='rect' else 0)
  assert abs(x-(70+row['area']*1.6))<1e-8 and abs(y-(285-row['price']*.42))<1e-8
 ordered=sorted(r['price'] for r in data)
 from statistics import median
 q1,q2,q3=median(ordered[:15]),median(ordered),median(ordered[15:])
 assert (q1,q2,q3)==(98,122,168)
 within=[v for v in ordered if q1-1.5*(q3-q1)<=v<=q3+1.5*(q3-q1)]
 assert (min(within),max(within))==(62,268)
 box=next(svg for svg in charts3 if svg.attrib['aria-labelledby'].startswith('box-summary'))
 assert box.find('rect').attrib['width']=='70'
 assert box.find('circle').attrib['cx']=='540'
 print('Chapter 03 histogram counts, scatter coordinates and boxplot statistics verified')

 ch4=(ROOT/'mean-and-median/index.html').read_text(encoding='utf-8')
 charts4=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch4,re.S)]
 assert len(charts4)==5
 values=[r['price'] for r in data];other=[r['price'] for r in data if r['id']!=7]
 assert sum(values)==4390 and median(values)==122
 assert sum(v>mean(values) for v in values)==10
 assert round(mean(other),1)==134.8 and median(other)==120
 assert round(mean(other+[780]),1)==156.3 and median(other+[780])==122
 dot=next(svg for svg in charts4 if svg.attrib['aria-labelledby'].startswith('two-centers'))
 points=[e for e in dot.findall('circle') if 'data-observation' in e.attrib]
 assert len(points)==30
 for point in points:
  row=next(r for r in data if r['id']==int(point.attrib['data-observation']))
  assert float(point.attrib['cx'])==60+row['price']
 sensitivity=next(svg for svg in charts4 if svg.attrib['aria-labelledby'].startswith('sensitivity'))
 for point in sensitivity.findall('circle'):
  replacement=int(point.attrib['data-replacement']);key=point.attrib['data-series']
  actual=mean(other+[replacement]) if key=='mean' else median(other+[replacement])
  assert abs(float(point.attrib['data-value'])-actual)<1e-8
  assert abs(float(point.attrib['cx'])-(75+(replacement-268)*.75))<1e-8
  assert abs(float(point.attrib['cy'])-(265-(actual-100)*2.3))<1e-8
 assert (200+100)/2==150 and (10*200+90*100)/(10+90)==110
 assert (10*100+90*200)/(10+90)==190
 print('Chapter 04 means, medians, sensitivity coordinates and weighted examples verified')

 ch5=(ROOT/'quantiles/index.html').read_text(encoding='utf-8')
 charts5=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch5,re.S)]
 assert len(charts5)==5
 from _build_quantiles_chapter import summary,type7
 assert summary(values)==(98,122,168,62,268,[480])
 assert [type7(values,p) for p in [.25,.5,.75]]==[99,122,166]
 assert summary([r['price'] for r in data if r['group']=='주거'])[:3]==(88,105,120)
 assert summary([r['price'] for r in data if r['group']=='상업'])[:3]==(124,168,235)
 for svg in charts5:
  for box in svg.findall('rect'):
   label=box.attrib.get('data-box')
   if not label:continue
   group=[r['price'] for r in data if r['group']==label] if label in ['주거','상업'] else values
   q1,q2,q3,lo,hi,out=summary(group)
   if label=='range':lo,hi=min(group),max(group)
   assert [float(box.attrib[k]) for k in ['data-q1','data-q2','data-q3','data-low','data-high']]==[q1,q2,q3,lo,hi]
   assert float(box.attrib['x'])==60+q1 and float(box.attrib['width'])==q3-q1
 print('Chapter 05 quartiles, interpolation and group boxplot coordinates verified')

 from statistics import pvariance,variance,pstdev,stdev
 ch6=(ROOT/'spread/index.html').read_text(encoding='utf-8')
 charts6=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch6,re.S)]
 assert len(charts6)==4
 assert round(pvariance(values),2)==6425.36 and round(pstdev(values),2)==80.16
 assert round(variance(values),2)==6646.92 and round(stdev(values),2)==81.53
 assert round(pstdev(other),2)==51.72
 for svg in charts6:
  for bar in svg.findall('rect'):
   if 'data-denominator' in bar.attrib:
    expected=pstdev(values) if bar.attrib['data-denominator']=='n' else stdev(values)
    assert abs(float(bar.attrib['data-sd'])-expected)<1e-8 and abs(float(bar.attrib['width'])-expected*4.7)<1e-8
   if 'data-count' in bar.attrib:
    expected=pstdev(values if int(bar.attrib['data-count'])==30 else other)
    assert abs(float(bar.attrib['data-sd'])-expected)<1e-8 and abs(float(bar.attrib['width'])-expected*4.4)<1e-8
 small=[80,100,120]
 assert round(pvariance(small),2)==266.67 and round(pstdev(small),2)==16.33
 assert abs(pstdev([x+100 for x in small])-pstdev(small))<1e-8
 assert abs(pvariance([2*x for x in small])-4*pvariance(small))<1e-8
 print('Chapter 06 variance, standard deviation, bar lengths and transformations verified')
 ch7=(ROOT/'iqr-outliers/index.html').read_text(encoding='utf-8')
 charts7=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch7,re.S)]
 assert len(charts7)==4
 assert [x for x in values if x < -7 or x > 273]==[480]
 assert sorted(x for x in values if x < -1.5 or x > 266.5)==[268,480]
 assert summary([100]*6+[120])[:3]==(100,100,100)
 for svg in charts7:
  for bar in svg.findall('rect'):
   a=bar.attrib
   if 'data-k' in a:
    k=float(a['data-k']);lo=98-k*70;hi=168+k*70
    assert float(a['data-low'])==lo and float(a['data-high'])==hi
    assert abs(float(a['x'])-(105+(lo+120)*.75))<1e-8
    assert float(a['width'])==(hi-lo)*.75
    assert [v for v in values if v<lo or v>hi]==[480]
   if 'data-group' in a:
    expected={'전체':273,'주거':168,'상업':401.5}[a['data-group']]
    assert float(a['data-upper'])==expected
   if 'data-metric' in a:
    fn={'평균':mean,'중앙값':median,'표준편차':pstdev}[a['data-metric']]
    expected=fn(values if a['data-series']=='all' else other)
    assert abs(float(a['data-value'])-expected)<1e-8
    assert abs(float(a['width'])-2.5*expected)<1e-8
 print('Chapter 07 fences, quantile conventions, group thresholds and sensitivity verified')
 ch8=(ROOT/'probability/index.html').read_text(encoding='utf-8')
 charts8=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch8,re.S)]
 assert len(charts8)==4 and ch8.count('<summary>답과 해설</summary>')==4
 example=json.loads((ROOT/'probability-example.json').read_text(encoding='utf-8'))
 counts=example['table'];assert counts=={'A_B':18,'A_notB':22,'notA_B':12,'notA_notB':48}
 assert sum(counts.values())==100
 from collections import Counter
 assert dict(Counter(e.attrib['data-cell'] for e in charts8[0].findall('rect') if 'data-cell' in e.attrib))==counts
 for bar in charts8[1].findall('rect'):
  if 'data-numerator' in bar.attrib:
   a=bar.attrib;assert abs(float(a['width'])-340*int(a['data-numerator'])/int(a['data-denominator']))<1e-8
 assert 40+30-18==52 and 18/30==.6 and 18/40==.45
 assert abs(.4*.45+.6*.2-.3)<1e-12
 assert round(40/100*39/99*100,2)==15.76
 d=example['screening'];assert d['total']==1000 and d['errors']==20
 assert d['true_positive']/d['errors']==.9 and d['false_positive']/(d['total']-d['errors'])==.1
 assert round(d['true_positive']/(d['true_positive']+d['false_positive'])*100,2)==15.52
 for bar in charts8[3].findall('rect'):
  assert abs(float(bar.attrib['width'])-int(bar.attrib['data-flagged'])*2.6)<1e-8
 print('Chapter 08 frequency cells, conditional bars, probability rules and Bayes example verified')
 ch9=(ROOT/'probability-distributions/index.html').read_text(encoding='utf-8')
 charts9=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch9,re.S)]
 assert len(charts9)==4 and ch9.count('<summary>답과 해설</summary>')==4
 import math
 from _build_distributions_chapter import binomial,normal
 probs=binomial(3,.4)
 assert all(abs(a-b)<1e-12 for a,b in zip(probs,[.216,.432,.288,.064]))
 assert abs(sum(probs)-1)<1e-12
 mu=sum(k*p for k,p in enumerate(probs));var=sum((k-mu)**2*p for k,p in enumerate(probs))
 assert abs(mu-1.2)<1e-12 and abs(var-.72)<1e-12
 saved=json.loads((ROOT/'distributions-example.json').read_text(encoding='utf-8'));assert saved['binomial']['probabilities']==probs
 for bar in charts9[0].findall('rect'):
  a=bar.attrib;p=probs[int(a['data-k'])];assert abs(float(a['height'])-p*380)<1e-8
  assert abs(float(a['y'])-(245-p*380))<1e-8
 for dot in charts9[1].findall('circle'):
  a=dot.attrib
  if 'data-cdf' in a:
   expected=sum(probs[:int(a['data-k'])+1]);assert abs(float(a['data-cdf'])-expected)<1e-12
   assert abs(float(a['cy'])-(250-expected*180))<1e-8
 assert abs((.3-.1)*2-.4)<1e-12
 assert round(math.erf(1/math.sqrt(2))*100,2)==68.27
 curve=charts9[3].find('polyline');points=curve.attrib['points'].split();assert len(points)==321
 for i,pair in enumerate(points):
  x,y=map(float,pair.split(','));z=-4+i*.025
  assert abs(x-(320+z*65))<.0001 and abs(y-(245-normal(z)*430))<.0001
 print('Chapter 09 PMF, CDF, moments, density area and normal curve verified')
 ch10=(ROOT/'sampling-distributions/index.html').read_text(encoding='utf-8')
 charts10=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch10,re.S)]
 assert len(charts10)==4 and ch10.count('<summary>답과 해설</summary>')==4
 saved=json.loads((ROOT/'sampling-distributions-example.json').read_text(encoding='utf-8'))
 for d in saved['distributions']:
  n=d['n'];probs=binomial(n,.2);assert d['probabilities']==probs
  assert abs(sum(probs)-1)<1e-12
  assert abs(sum(k/n*p for k,p in enumerate(probs))-.2)<1e-12
  assert abs(sum((k/n-.2)**2*p for k,p in enumerate(probs))-.16/n)<1e-12
 bars=[e for e in charts10[1].findall('line') if 'data-n' in e.attrib]
 assert len(bars)==140
 for bar in bars:
  a=bar.attrib;n=int(a['data-n']);k=int(a['data-k']);p=binomial(n,.2)[k]
  assert abs(float(a['x1'])-(70+500*k/n))<1e-9
  assert abs(float(a['y1'])-float(a['y2'])-125*p)<1e-9
 for bar in charts10[2].findall('rect'):
  a=bar.attrib;se=.4/math.sqrt(int(a['data-n']));assert float(a['data-se'])==se and float(a['width'])==se*900
 exact=sum(binomial(100,.2)[15:26]);approx=math.erf(1.375/math.sqrt(2))
 assert abs(exact-approx)<.01
 assert f'{exact:.4f}' in ch10 and f'{approx:.4f}' in ch10
 print('Chapter 10 exact sampling probabilities, moments, coordinates and approximation verified')
 ch11=(ROOT/'sample-size/index.html').read_text(encoding='utf-8')
 charts11=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch11,re.S)]
 assert len(charts11)==4 and ch11.count('<summary>답과 해설</summary>')==4
 v=[r['price'] for r in data];sd=stdev(v);se=sd/math.sqrt(30)
 assert round(se,2)==14.89
 for i,svg in enumerate(charts11):
  for bar in svg.findall('rect'):
   a=bar.attrib
   if i==0:assert abs(float(a['width'])-float(a['data-value'])*4)<1e-9
   if i==1:
    expected=sd/math.sqrt(int(a['data-n']));assert abs(float(a['data-se'])-expected)<1e-9 and abs(float(a['width'])-14*expected)<1e-9
   if i==2:
    group=[r['price'] for r in data if r['group']==a['data-group']];expected=stdev(group)/math.sqrt(len(group));assert abs(float(a['data-se'])-expected)<1e-9 and abs(float(a['width'])-13*expected)<1e-9
   if i==3:
    target=float(a['data-target']);n=math.ceil((sd/target)**2);assert int(a['data-required'])==n and float(a['width'])==n*1.3
    assert sd/math.sqrt(n)<=target and sd/math.sqrt(n-1)>target
 assert math.ceil((1.96*80/10)**2)==246
 print('Chapter 11 SD, SE, group calculations and sample-size planning verified')
 ch12=(ROOT/'confidence-intervals/index.html').read_text(encoding='utf-8')
 charts12=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch12,re.S)]
 assert len(charts12)==4 and ch12.count('<summary>답과 해설</summary>')==4
 from scipy.stats import t as student_t,norm
 ci=json.loads((ROOT/'confidence-example.json').read_text(encoding='utf-8'))
 base=ci['base'];assert abs(base['mean']-mean(v))<1e-10 and abs(base['sd']-stdev(v))<1e-10
 for d in [base]+ci['levels']+ci['sizes']:
  critical=float(student_t.ppf((1+d['level'])/2,d['n']-1));margin=critical*d['sd']/math.sqrt(d['n'])
  assert abs(d['margin']-margin)<1e-10 and abs(d['low']-(d['mean']-margin))<1e-10
  assert abs(d['high']-(d['mean']+margin))<1e-10
 for svg in charts12:
  for bar in svg.findall('line'):
   a=bar.attrib
   if 'data-key' in a:
    scale=3.7 if a['data-key'].startswith('n-') else 4
    assert abs(float(a['x1'])-(90+(float(a['data-low'])-90)*scale))<1e-9
    assert abs(float(a['x2'])-(90+(float(a['data-high'])-90)*scale))<1e-9
 sim=ci['simulation'];rng=random.Random(sim['seed'])
 for d in sim['repeats']:
  sample=[rng.gauss(sim['mu'],sim['sigma']) for _ in range(sim['n'])];assert sample==d['sample']
  avg=mean(sample);margin=float(norm.ppf(.975))*20/5
  assert abs(d['mean']-avg)<1e-10 and abs(d['low']-(avg-margin))<1e-10
  assert d['covers']==(d['low']<=100<=d['high'])
 bars=[e for e in next(svg for svg in charts12 if svg.attrib['aria-labelledby'].startswith('coverage')).findall('line') if 'data-repeat' in e.attrib];assert len(bars)==20
 for bar,d in zip(bars,sim['repeats']):
  assert abs(float(bar.attrib['x1'])-(80+(d['low']-80)*12))<1e-9
  assert abs(float(bar.attrib['x2'])-(80+(d['high']-80)*12))<1e-9
 print('Chapter 12 t intervals, confidence levels, SVG endpoints and seeded coverage verified')
 ch13=(ROOT/'hypothesis-tests/index.html').read_text(encoding='utf-8')
 charts13=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch13,re.S)]
 assert len(charts13)==4 and ch13.count('<summary>답과 해설</summary>')==4
 from scipy.stats import ttest_1samp,nct
 h=json.loads((ROOT/'hypothesis-example.json').read_text(encoding='utf-8'))
 independent=ttest_1samp(v,130)
 assert abs(h['t']-independent.statistic)<1e-12 and abs(h['p']-independent.pvalue)<1e-12
 assert h['p']>.05 and h['ci'][0]<130<h['ci'][1]
 for svg in charts13[:2]:
  points=svg.find('polyline').attrib['points'].split();assert len(points)==361
  for i,pair in enumerate(points):
   x,y=map(float,pair.split(','));value=-4.5+i*.025
   assert abs(x-(320+value*60))<1e-4 and abs(y-(235-student_t.pdf(value,29)*400))<1e-4
 for bar,d in zip(charts13[3].findall('rect'),h['power']['values']):
  n=d['n'];c=student_t.ppf(.975,n-1);nc=.25*math.sqrt(n);power=nct.cdf(-c,n-1,nc)+nct.sf(c,n-1,nc)
  assert abs(d['power']-power)<1e-12 and abs(float(bar.attrib['width'])-power*390)<1e-9
 assert round((1-.95**20)*100,1)==64.2
 print('Chapter 13 independent t-test, null curves, CI agreement and power verified')
 ch14=(ROOT/'comparing-groups/index.html').read_text(encoding='utf-8')
 charts14=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch14,re.S)]
 assert len(charts14)==4 and ch14.count('<summary>답과 해설</summary>')==4
 from scipy.stats import ttest_ind,ttest_rel
 g=json.loads((ROOT/'group-comparison-example.json').read_text(encoding='utf-8'))
 a=[r['price'] for r in data if r['group']=='상업'];b=[r['price'] for r in data if r['group']=='주거']
 w=g['welch'];test=ttest_ind(a,b,equal_var=False);bounds=test.confidence_interval()
 assert abs(w['t']-test.statistic)<1e-10 and abs(w['p']-test.pvalue)<1e-10
 assert abs(w['low']-bounds.low)<1e-9 and abs(w['high']-bounds.high)<1e-9
 reduced=ttest_ind([r['price'] for r in data if r['group']=='상업' and r['id']!=7],b,equal_var=False)
 assert abs(g['without_id7']['p']-reduced.pvalue)<1e-10
 assert abs(w['d']-(mean(a)-mean(b))/math.sqrt((variance(a)+variance(b))/2))<1e-10
 pa=g['paired'];paired=ttest_rel(pa['after'],pa['before']);pci=paired.confidence_interval()
 assert abs(pa['low']-pci.low)<1e-10 and abs(pa['high']-pci.high)<1e-10
 assert pa['differences']==[6,4,7,5,8,6]
 dots=[dot for dot in charts14[0].findall('circle') if 'data-group' in dot.attrib];assert len(dots)==30
 for dot in dots:assert float(dot.attrib['cx'])==70+float(dot.attrib['data-value'])
 ci=next(e for e in charts14[1].findall('line') if 'data-diff-ci' in e.attrib)
 assert abs(float(ci.attrib['x1'])-(100+3.3*w['low']))<1e-9 and abs(float(ci.attrib['x2'])-(100+3.3*w['high']))<1e-9
 pairs=[e for e in charts14[2].findall('line') if 'data-pair' in e.attrib];assert len(pairs)==6
 for line,pv,av in zip(pairs,pa['before'],pa['after']):
  assert abs(float(line.attrib['y1'])-(300-(pv-60)*1.7))<1e-9 and abs(float(line.attrib['y2'])-(300-(av-60)*1.7))<1e-9
 print('Chapter 14 independent Welch/paired checks, effect sizes and SVG coordinates verified')
 ch15=(ROOT/'multiple-groups-and-categorical/index.html').read_text(encoding='utf-8')
 charts15=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch15,re.S)]
 assert len(charts15)==4 and ch15.count('<summary>답과 해설</summary>')==4
 from scipy.stats import f_oneway,chi2_contingency,studentized_range
 m15=json.loads((ROOT/'multiple-groups-example.json').read_text(encoding='utf-8'))
 groups=m15['groups'];an=m15['anova'];check=f_oneway(*groups)
 assert an['between_ss']==3200 and an['within_ss']==600 and an['F']==24
 assert abs(an['F']-check.statistic)<1e-12 and abs(an['p']-check.pvalue)<1e-12
 assert abs(an['eta_squared']-3200/3800)<1e-12
 for pair in m15['tukey']:
  delta=mean(groups[pair['i']])-mean(groups[pair['j']]);half=studentized_range.ppf(.95,3,9)*math.sqrt((600/9)/4)
  assert abs(pair['low']-(delta-half))<1e-8 and abs(pair['high']-(delta+half))<1e-8
 c=m15['categorical'];cc=chi2_contingency(c['observed'],correction=False)
 assert abs(cc.statistic-c['chi2'])<1e-12 and abs(cc.pvalue-c['p'])<1e-12 and cc.expected_freq.tolist()==c['expected']
 assert abs(c['V']-1/3)<1e-12
 dots=[e for e in charts15[0].findall('circle')];assert len(dots)==12
 for dot in dots:assert float(dot.attrib['cx'])==80+(float(dot.attrib['data-value'])-80)*6
 for bar in charts15[1].findall('rect'):assert abs(float(bar.attrib['width'])-float(bar.attrib['data-ss'])*.11)<1e-9
 intervals=[e for e in charts15[2].findall('line') if 'data-pair' in e.attrib]
 for bar,d in zip(intervals,m15['tukey']):
  assert abs(float(bar.attrib['x1'])-(115+d['low']*6))<1e-9 and abs(float(bar.attrib['x2'])-(115+d['high']*6))<1e-9
 for bar in charts15[3].findall('rect'):
  if 'data-row' in bar.attrib:
   row=c['observed'][int(bar.attrib['data-row'])];assert abs(float(bar.attrib['width'])-400*row[0]/sum(row))<1e-9
 print('Chapter 15 ANOVA, Tukey intervals, chi-square, effects and SVG coordinates verified')
 ch16=(ROOT/'correlation/index.html').read_text(encoding='utf-8')
 charts16=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch16,re.S)]
 assert len(charts16)==4 and ch16.count('<summary>답과 해설</summary>')==4
 from scipy.stats import pearsonr,spearmanr,rankdata
 c=json.loads((ROOT/'correlation-example.json').read_text(encoding='utf-8'))
 areas=[r['area'] for r in data];prices=[r['price'] for r in data]
 assert abs(c['pearson_area_price']-pearsonr(areas,prices).statistic)<1e-12
 assert abs(c['spearman_area_price']-pearsonr(rankdata(areas),rankdata(prices)).statistic)<1e-12
 otherrows=[r for r in data if r['id']!=7]
 assert abs(c['without_id7']-pearsonr([r['area'] for r in otherrows],[r['price'] for r in otherrows]).statistic)<1e-12
 assert abs(pearsonr(*zip(*c['curved'])).statistic)<1e-12
 mix=c['mixture'];assert abs(pearsonr(*zip(*mix['A'])).statistic-1)<1e-12
 assert abs(pearsonr(*zip(*mix['B'])).statistic-1)<1e-12
 assert abs(pearsonr(*zip(*(mix['A']+mix['B']))).statistic-mix['overall_r'])<1e-12 and mix['overall_r']<0
 dots=charts16[0].findall('circle');assert len(dots)==30
 for dot in dots:
  row=next(r for r in data if r['id']==int(dot.attrib['data-id']))
  assert float(dot.attrib['cx'])==70+row['area']*1.5 and float(dot.attrib['cy'])==320-row['price']*.5
 for dot in charts16[1].findall('circle'):
  a=dot.attrib;assert float(a['cx'])==320+int(a['data-x'])*65 and float(a['cy'])==285-int(a['data-y'])*22
 for dot in charts16[2].findall('circle'):
  a=dot.attrib;assert float(a['cx'])==70+int(a['data-x'])*48 and float(a['cy'])==320-int(a['data-y'])*23
 print('Chapter 16 Pearson/rank correlations, nonlinear/mixture examples and coordinates verified')
 ch17=(ROOT/'regression/index.html').read_text(encoding='utf-8')
 charts17=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch17,re.S)]
 assert len(charts17)==4 and ch17.count('<summary>답과 해설</summary>')==4
 from scipy.stats import linregress
 reg=json.loads((ROOT/'regression-example.json').read_text(encoding='utf-8'));fit=reg['fit'];check=linregress(areas,prices)
 assert abs(fit['slope']-check.slope)<1e-12 and abs(fit['intercept']-check.intercept)<1e-10
 assert abs(sum(fit['residuals']))<1e-8 and abs(fit['R2']-check.rvalue**2)<1e-12
 assert reg['small']['fit']['residuals']==[.5,-1,.5] and reg['small']['fit']['SSE']==1.5
 for key,value in reg['predictions'].items():assert abs(value-(check.intercept+check.slope*float(key)))<1e-10
 assert reg['predictions']['400']<0
 curve=charts17[2].find('polyline');points=curve.attrib['points'].split();assert len(points)==101
 for i,pair in enumerate(points):
  sx,sy=map(float,pair.split(','));slope=-1.2+i*.01;inter=mean(prices)-slope*mean(areas)
  sse=sum((y-inter-slope*x)**2 for x,y in zip(areas,prices))
  assert abs(sx-(80+(slope+1.2)*450))<1e-4 and abs(sy-(285-(sse-fit['SSE'])/500))<1e-4
 dots=[e for e in charts17[0].findall('circle')];assert len(dots)==30
 for dot in dots:
  row=next(r for r in data if r['id']==int(dot.attrib['data-id']))
  assert float(dot.attrib['cx'])==70+row['area']*1.5 and float(dot.attrib['cy'])==320-row['price']*.5
 print('Chapter 17 OLS, residuals, R-squared, predictions and objective curve verified')
 ch18=(ROOT/'residuals/index.html').read_text(encoding='utf-8')
 charts18=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch18,re.S)]
 assert len(charts18)==4 and ch18.count('<summary>답과 해설</summary>')==4
 diag=json.loads((ROOT/'residuals-example.json').read_text(encoding='utf-8'))
 import numpy as np
 from scipy.stats import norm
 X=np.column_stack([np.ones(len(areas)),areas]);yy=np.array(prices)
 beta=np.linalg.lstsq(X,yy,rcond=None)[0];ee=yy-X@beta;hat=X@np.linalg.inv(X.T@X)@X.T
 ss=float(ee@ee);sigma=math.sqrt(ss/28)
 assert abs(diag['s']-sigma)<1e-10 and abs(diag['RMSE']-math.sqrt(ss/30))<1e-10
 assert abs(diag['MAE']-float(np.abs(ee).mean()))<1e-10
 assert abs(sum(r['leverage'] for r in diag['rows'])-2)<1e-12
 for i,row in enumerate(diag['rows']):
  h=hat[i,i];r=ee[i]/(sigma*math.sqrt(1-h));keep=np.arange(30)!=i
  deleted=np.linalg.lstsq(X[keep],yy[keep],rcond=None)[0]
  cook=float(np.sum((X@beta-X@deleted)**2)/(2*sigma*sigma))
  assert abs(row['residual']-ee[i])<1e-9 and abs(row['leverage']-h)<1e-12
  assert abs(row['standardized']-r)<1e-10 and abs(row['cook']-cook)<1e-10
 for i,q in enumerate(diag['qq']):
  assert abs(q['z']-norm.ppf((i+.5)/30))<1e-12 and abs(q['residual']-sorted(ee)[i])<1e-9
 for chart,kind in [(charts18[0],'residual'),(charts18[3],'influence')]:
  dots=chart.findall('circle');assert len(dots)==30
  for dot,row in zip(dots,diag['rows']):
   cx=65+row['fitted']*2.2 if kind=='residual' else 65+row['leverage']*1800
   cy=255-row['residual']*.7 if kind=='residual' else 280-row['standardized']*45
   assert abs(float(dot.attrib['cx'])-cx)<1e-9 and abs(float(dot.attrib['cy'])-cy)<1e-9
 print('Chapter 18 independent matrix OLS, leverage, deletion Cook distances, Q-Q and plotted coordinates verified')
 ch19=(ROOT/'multiple-regression/index.html').read_text(encoding='utf-8')
 charts19=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch19,re.S)]
 assert len(charts19)==4 and ch19.count('<summary>답과 해설</summary>')==4
 from scipy.stats import t as student_t19
 m19=json.loads((ROOT/'multiple-regression-example.json').read_text(encoding='utf-8'))
 demo=m19['demo'];assert np.allclose(demo['model']['beta'],[7,1,-9])
 assert abs(demo['simple']['beta'][1]-linregress(demo['x'],demo['y']).slope)<1e-12
 rx=np.array(demo['residual_x']);ry=np.array(demo['residual_y']);assert abs(rx@ry/(rx@rx)-1)<1e-12
 for key,cols in [('simple',[np.ones(30),areas]),('multiple',[np.ones(30),areas,[r['floor'] for r in data]])]:
  mat=np.column_stack(cols);q,r=np.linalg.qr(mat);coef=np.linalg.solve(r,q.T@np.array(prices));err=np.array(prices)-mat@coef;df=30-mat.shape[1]
  invr=np.linalg.solve(r,np.eye(r.shape[0]));se=np.sqrt(np.diag(invr@invr.T)*(err@err)/df)
  assert np.allclose(coef,m19[key]['beta']) and np.allclose(se,m19[key]['se'])
  for j in range(len(coef)):assert np.allclose(m19[key]['ci'][j],[coef[j]-student_t19.ppf(.975,df)*se[j],coef[j]+student_t19.ppf(.975,df)*se[j]])
 assert m19['multiple']['SSE']<=m19['simple']['SSE'] and m19['multiple']['df']==27
 for dot,xx,yy in zip(charts19[0].findall('circle'),demo['x'],demo['y']):
  assert abs(float(dot.attrib['cx'])-(70+xx*75))<1e-9 and abs(float(dot.attrib['cy'])-(320-yy*23))<1e-9
 for dot,xx,yy in zip(charts19[1].findall('circle'),rx,ry):
  assert abs(float(dot.attrib['cx'])-(320+xx*130))<1e-9 and abs(float(dot.attrib['cy'])-(210-yy*104))<1e-9
 print('Chapter 19 QR coefficients, intervals, partial regression and graphic coordinates verified')
 ch20=(ROOT/'log-regression/index.html').read_text(encoding='utf-8')
 charts20=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch20,re.S)]
 assert len(charts20)==4 and ch20.count('<summary>답과 해설</summary>')==4
 log20=json.loads((ROOT/'log-regression-example.json').read_text(encoding='utf-8'))
 for key in ['level','log_y','log_x','log_log']:
  xx=np.log(areas) if key in ['log_x','log_log'] else np.array(areas)
  yy=np.log(prices) if key in ['log_y','log_log'] else np.array(prices)
  check=linregress(xx,yy);m=log20['models'][key]
  assert abs(m['slope']-check.slope)<1e-10 and abs(m['intercept']-check.intercept)<1e-10
  pred=check.intercept+check.slope*xx
  if key in ['log_y','log_log']:
   assert abs(m['smearing']-np.exp(yy-pred).mean())<1e-10
   pred=np.exp(pred)
  assert np.allclose(pred,m['predictions']) and abs(m['MAE']-np.abs(np.array(prices)-pred).mean())<1e-10
 for curve in charts20[1].findall('polyline'):
  key=curve.attrib['data-model'];m=log20['models'][key];pairs=curve.attrib['points'].split();assert len(pairs)==101
  for i,pair in enumerate(pairs):
   cx,cy=map(float,pair.split(','));xv=22+i*288/100;z=math.log(xv) if key=='log_log' else xv
   yv=m['intercept']+m['slope']*z;yv=math.exp(yv) if key!='level' else yv
   assert abs(cx-(65+xv*1.55))<1e-9 and abs(cy-(325-yv*.5))<1e-9
 for row in log20['percentages']:
  b=log20['models']['log_log']['slope'];c=row['change'];assert abs(row['exact']-100*math.expm1(b*math.log1p(c/100)))<1e-10
 assert abs(math.exp(mean([math.log(50),math.log(200)]))-100)<1e-10
 print('Chapter 20 log fits, smearing, MAE, exact percentages and curve coordinates verified')
 ch21=(ROOT/'model-fit/index.html').read_text(encoding='utf-8')
 charts21=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch21,re.S)]
 assert len(charts21)==4 and ch21.count('<summary>답과 해설</summary>')==4
 fit21=json.loads((ROOT/'model-fit-example.json').read_text(encoding='utf-8'))
 A=np.column_stack([np.ones(30),areas]);yy=np.array(prices);q,r=np.linalg.qr(A);beta=np.linalg.solve(r,q.T@yy);e=yy-A@beta
 invr=np.linalg.solve(r,np.eye(2));cov=invr@invr.T*float(e@e)/28;critical=student_t19.ppf(.975,28)
 assert abs(fit21['SST']-fit21['SSR']-fit21['SSE'])<1e-8
 assert abs(fit21['slope_se']-math.sqrt(cov[1,1]))<1e-10 and abs(fit21['F']-fit21['t']**2)<1e-10
 assert abs(fit21['p']-fit21['F_p'])<1e-12
 for row in fit21['grid']+[fit21['point100']]:
  v=np.array([1,row['x']]);center=float(v@beta);meanvar=float(v@cov@v)
  assert abs(row['fit']-center)<1e-9
  assert np.allclose(row['ci'],[center-critical*math.sqrt(meanvar),center+critical*math.sqrt(meanvar)])
  assert np.allclose(row['pi'],[center-critical*math.sqrt(meanvar+float(e@e)/28),center+critical*math.sqrt(meanvar+float(e@e)/28)])
  assert row['pi'][0]<row['ci'][0]<row['ci'][1]<row['pi'][1]
 for band in charts21[1].findall('polygon'):
  key=band.attrib['data-band'];points=[tuple(map(float,p.split(','))) for p in band.attrib['points'].split()]
  expected=[(65+v['x']*1.55,330-(v[key][1]+150)*.43) for v in fit21['grid']]+[(65+v['x']*1.55,330-(v[key][0]+150)*.43) for v in reversed(fit21['grid'])]
  assert np.allclose(points,expected)
 for curve in charts21[3].findall('polyline'):
  key=curve.attrib['data-width'];points=[tuple(map(float,p.split(','))) for p in curve.attrib['points'].split()]
  assert np.allclose(points,[(65+v['x']*1.55,320-(v[key][1]-v['fit'])*1.6) for v in fit21['grid']])
 print('Chapter 21 sum-of-squares, QR covariance, t/F agreement and interval coordinates verified')
 ch22=(ROOT/'supervised-unsupervised/index.html').read_text(encoding='utf-8')
 charts22=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch22,re.S)]
 assert len(charts22)==4 and ch22.count('<summary>답과 해설</summary>')==4
 learn=json.loads((ROOT/'learning-example.json').read_text(encoding='utf-8'))
 assert learn['train_ids']==list(range(1,21)) and [v['id'] for v in learn['test']]==list(range(21,31))
 lr=linregress([r['area'] for r in data[:20]],[r['price'] for r in data[:20]])
 pred=[lr.intercept+lr.slope*r['area'] for r in data[20:]]
 assert np.allclose(pred,[v['predicted'] for v in learn['test']])
 assert abs(learn['MAE']-mean(abs(v-r['price']) for v,r in zip(pred,data[20:])))<1e-10
 assert abs(learn['baseline_MAE']-mean(abs(mean(r['price'] for r in data[:20])-r['price']) for r in data[20:]))<1e-10
 for dot,row in zip(charts22[0].findall('circle'),learn['test']):
  assert abs(float(dot.attrib['cx'])-(65+row['actual']*1.5))<1e-9 and abs(float(dot.attrib['cy'])-(325-row['predicted']*.9))<1e-9
 cl=learn['clustering'];pts=np.array(cl['points']);cent=np.array(cl['centers']);dist=((pts[:,None,:]-cent[None,:,:])**2).sum(axis=2)
 assert np.array_equal(dist.argmin(axis=1),cl['labels']) and abs(dist.min(axis=1).sum()-4)<1e-12
 for j in range(2):assert np.allclose(pts[np.array(cl['labels'])==j].mean(axis=0),cent[j])
 cf=learn['classification'];assert (cf['TP']+cf['TN'])/100==cf['accuracy'] and cf['TP']/(cf['TP']+cf['FN'])==0
 print('Chapter 22 held-out predictions, baseline, confusion counts and clustering fixed point verified')
 ch23=(ROOT/'train-validation-test/index.html').read_text(encoding='utf-8')
 charts23=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch23,re.S)]
 assert len(charts23)==4 and ch23.count('<summary>답과 해설</summary>')==4
 split23=json.loads((ROOT/'split-example.json').read_text(encoding='utf-8'))
 tr=np.array(split23['train']);va=np.array(split23['validation']);te=np.array(split23['test'])
 assert tr.mean()==20 and np.median(tr)==10
 assert np.abs(va-tr.mean()).mean()==8 and np.abs(va-np.median(tr)).mean()==2
 assert split23['selected']=='median' and split23['refit_value']==np.median(np.concatenate([tr,va]))==11
 assert abs(split23['test_MAE']-np.abs(te-11).mean())<1e-12
 sc=split23['scaling'];a=np.array(sc['train']);b=np.append(a,sc['held_out'])
 assert abs(sc['train_z']-(140-a.mean())/a.std())<1e-12 and abs(sc['leaked_z']-(140-b.mean())/b.std())<1e-12
 bars=charts23[3].findall('rect');assert len(bars)==2
 assert [float(v.attrib['height']) for v in bars]==[200,50]
 assert [float(v.attrib['y']) for v in bars]==[120,270]
 print('Chapter 23 selection, refit, test MAE, scaling boundaries and chart heights verified')
 ch24=(ROOT/'overfitting/index.html').read_text(encoding='utf-8')
 charts24=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch24,re.S)]
 assert len(charts24)==4 and ch24.count('<summary>답과 해설</summary>')==4
 sim=json.loads((ROOT/'overfitting-example.json').read_text(encoding='utf-8'));xx=np.array(sim['x']);gg=np.array(sim['grid']);yy=np.array(sim['training_y']);true=1+gg+.7*gg**2
 expected=1+xx+.7*xx**2+np.random.default_rng(sim['seed']).normal(0,.15,(300,12));assert np.allclose(yy,expected)
 previous=float('inf')
 for m in sim['models']:
  # Independent monomial QR solution rather than generator Legendre SVD.
  deg=m['degree'];A=np.vander(xx,deg+1,increasing=True);G=np.vander(gg,deg+1,increasing=True);q,r=np.linalg.qr(A);coef=np.linalg.solve(r,q.T@yy.T);pred=(G@coef).T
  err=float(np.mean((pred-true)**2)+.15**2);trerr=float(np.mean((yy-(A@coef).T)**2))
  assert abs(err-m['expected_MSE'])<1e-8 and abs(trerr-m['train_MSE'])<1e-8
  assert abs(m['bias2']+m['variance']+m['noise']-err)<1e-8
  assert trerr<=previous+1e-10;previous=trerr
  assert np.allclose(pred[0],m['first_curve'],atol=1e-8)
  assert np.allclose((np.vander([.8],deg+1,increasing=True)@coef).ravel(),m['at08'],atol=1e-8)
 ymax=max(m['expected_MSE'] for m in sim['models'])*1.2
 for curve in charts24[1].findall('polyline'):
  key=curve.attrib['data-metric'];points=[tuple(map(float,p.split(','))) for p in curve.attrib['points'].split()]
  assert np.allclose(points,[(120+i*140,320-m[key]/ymax*240) for i,m in enumerate(sim['models'])])
 for bar in charts24[2].findall('rect'):
  m=next(m for m in sim['models'] if m['degree']==int(bar.attrib['data-degree']))
  assert abs(float(bar.attrib['height'])-m[bar.attrib['data-part']]/ymax*240)<1e-9
 print('Chapter 24 seeded simulation, independent polynomial QR, bias/variance identity and chart coordinates verified')
 ch25=(ROOT/'prediction-errors/index.html').read_text(encoding='utf-8')
 charts25=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch25,re.S)]
 assert len(charts25)==4 and ch25.count('<summary>답과 해설</summary>')==4
 er25=json.loads((ROOT/'prediction-errors-example.json').read_text(encoding='utf-8'))
 for key in ['A','B']:
  d=er25['ranking'];e=np.array(d['actual'])-np.array(d[key+'_predictions']);m=d[key]
  assert abs(m['MAE']-np.abs(e).mean())<1e-12 and abs(m['RMSE']-np.sqrt(np.mean(e*e)))<1e-12
 assert er25['ranking']['A']['MAE']==2 and er25['ranking']['A']['RMSE']==4
 assert er25['ranking']['B']['MAE']==er25['ranking']['B']['RMSE']==3
 assert er25['small_values']['metrics']['MAPE']==37
 for row in er25['loss']['grid']:
  e=np.array([1,2,9])-row['value'];assert abs(row['MAE']-np.abs(e).mean())<1e-12 and abs(row['MSE']-np.mean(e*e))<1e-12
 assert min(er25['loss']['grid'],key=lambda v:v['MAE'])['value']==2
 assert min(er25['loss']['grid'],key=lambda v:v['MSE'])['value']==4
 co=er25['common'];lr=linregress([r['area'] for r in data[:20]],[r['price'] for r in data[:20]]);pred=np.array([lr.intercept+lr.slope*r['area'] for r in data[20:]]);actual=np.array([r['price'] for r in data[20:]]);e=actual-pred
 assert np.allclose(pred,co['predictions']) and abs(co['metrics']['MAPE']-100*np.mean(np.abs(e/actual)))<1e-10
 for j,curve in enumerate(charts25[3].findall('polyline')):
  key=curve.attrib['data-loss'];maxv=10 if key=='MAE' else 60;left=65+j*300
  points=[tuple(map(float,p.split(','))) for p in curve.attrib['points'].split()]
  assert np.allclose(points,[(left+v['value']*23,315-v[key]/maxv*220) for v in er25['loss']['grid']])
 assert np.allclose([float(b.attrib['height']) for b in charts25[2].findall('rect')],[220,22,2.2])
 print('Chapter 25 metric ranking, MAPE, loss optima, held-out predictions and graphic coordinates verified')
 ch26=(ROOT/'cross-validation/index.html').read_text(encoding='utf-8')
 charts26=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch26,re.S)]
 assert len(charts26)==4 and ch26.count('<summary>답과 해설</summary>')==4
 cv26=json.loads((ROOT/'cross-validation-example.json').read_text(encoding='utf-8'));errors26=[];apes26=[];seen=[]
 for fold in cv26['folds']:
  tr=[r for r in data if r['id'] in fold['train_ids']];va=[r for r in data if r['id'] in fold['validation_ids']]
  assert not set(fold['train_ids'])&set(fold['validation_ids']) and len(tr)==20 and len(va)==10;seen+=fold['validation_ids']
  lr=linregress([r['area'] for r in tr],[r['price'] for r in tr]);pred=np.array([lr.intercept+lr.slope*r['area'] for r in va]);actual=np.array([r['price'] for r in va]);e=actual-pred
  assert np.allclose(pred,fold['predictions']) and abs(np.abs(e).mean()-fold['metrics']['MAE'])<1e-10
  errors26.extend(e);apes26.extend(np.abs(e/actual))
 assert sorted(seen)==list(range(1,31))
 assert abs(np.abs(errors26).mean()-cv26['pooled']['MAE'])<1e-10 and abs(100*np.mean(apes26)-cv26['pooled']['MAPE'])<1e-10
 assert abs(np.sqrt(np.mean(np.array(errors26)**2))-cv26['pooled']['RMSE'])<1e-10
 assert abs(mean(f['metrics']['RMSE'] for f in cv26['folds'])-cv26['mean_fold_RMSE'])<1e-10
 for bar,fold in zip(charts26[1].findall('rect'),cv26['folds']):assert abs(float(bar.attrib['height'])-fold['metrics']['MAE']*3.5)<1e-9
 assert np.allclose([float(v.attrib['height']) for v in charts26[2].findall('rect')],[192,115.2])
 print('Chapter 26 disjoint folds, independent regressions, pooled metrics and bar coordinates verified')
 ch27=(ROOT/'regularization/index.html').read_text(encoding='utf-8')
 charts27=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch27,re.S)]
 assert len(charts27)==4 and ch27.count('<summary>답과 해설</summary>')==4
 reg27=json.loads((ROOT/'regularization-example.json').read_text(encoding='utf-8'));z=np.array(reg27['orthogonal']['z'])
 for row in reg27['orthogonal']['path']:
  lam=row['lam'];ridge=np.array(row['ridge']);lasso=np.array(row['lasso'])
  assert np.allclose((1+lam)*ridge,z)
  for b,zi in zip(lasso,z):
   assert abs(b-zi+lam*np.sign(b))<1e-10 if b!=0 else abs(zi)<=lam+1e-10
 for item in reg27['cv']:
  errs=[]
  for fold in item['folds']:
   k=fold['fold']-1;tr=data[:k*10]+data[(k+1)*10:];va=data[k*10:(k+1)*10];xx=np.array([r['area'] for r in tr]);yy=np.array([r['price'] for r in tr]);zz=(xx-xx.mean())/xx.std()
   A=np.column_stack([np.ones(20),zz]);pen=np.diag([0,20*item['lam']]);b=np.linalg.solve(A.T@A+pen,A.T@yy)
   pred=b[0]+b[1]*(np.array([r['area'] for r in va])-xx.mean())/xx.std();assert np.allclose(pred,fold['predictions'])
   errs.extend(np.array([r['price'] for r in va])-pred)
  assert abs(np.sqrt(np.mean(np.array(errs)**2))-item['RMSE'])<1e-10
 assert reg27['best_lambda']==min(reg27['cv'],key=lambda v:v['RMSE'])['lam']
 for chart,key in [(charts27[0],'ridge'),(charts27[1],'lasso')]:
  for curve in chart.findall('polyline'):
   j=int(curve.attrib['data-index']);points=[tuple(map(float,p.split(','))) for p in curve.attrib['points'].split()]
   assert np.allclose(points,[(70+r['lam']*120,290-r[key][j]*70) for r in reg27['orthogonal']['path']])
 print('Chapter 27 ridge equations, lasso optimality, fold-local scaling and coefficient paths verified')
 ch28=(ROOT/'classification/index.html').read_text(encoding='utf-8')
 charts28=[ET.fromstring(svg) for svg in re.findall(r'<svg .*?</svg>',ch28,re.S)]
 assert len(charts28)==4 and ch28.count('<summary>답과 해설</summary>')==4
 cls=json.loads((ROOT/'classification-example.json').read_text(encoding='utf-8'));pp=np.array(cls['probabilities']);yy=np.array(cls['labels'])
 from scipy.special import expit,logit
 for v in cls['curve']:assert abs(v['p']-expit(-2+.8*v['x']))<1e-12
 for v in cls['odds']:assert abs(logit(v['after'])-logit(v['before'])-math.log(2))<1e-12
 for c in cls['confusions']:
  pr=pp>=c['threshold'];tp=int(np.sum(pr&(yy==1)));fp=int(np.sum(pr&(yy==0)));fn=int(np.sum(~pr&(yy==1)));tn=int(np.sum(~pr&(yy==0)))
  assert [tp,fp,fn,tn]==[c['TP'],c['FP'],c['FN'],c['TN']]
  assert abs(c['precision']-tp/(tp+fp))<1e-12 and abs(c['F1']-2*tp/(2*tp+fp+fn))<1e-12
 assert abs(cls['log_loss']-np.mean(np.logaddexp(0,logit(pp))-yy*logit(pp)))<1e-12
 assert abs(cls['brier']-np.mean((pp-yy)**2))<1e-12
 from scipy.stats import rankdata
 auc=(rankdata(pp)[yy==1].sum()-4*5/2)/16
 assert cls['AUC']==auc==13/16
 points=[tuple(map(float,v.split(','))) for v in charts28[0].find('polyline').attrib['points'].split()]
 assert np.allclose(points,[(70+r['x']*100,320-r['p']*250) for r in cls['curve']])
 for curve in charts28[3].findall('polyline'):
  key=curve.attrib['data-label'];points=[tuple(map(float,v.split(','))) for v in curve.attrib['points'].split()]
  assert np.allclose(points,[(70+r['p']*500,320-r[key]*50) for r in cls['loss']])
 print('Chapter 28 sigmoid, odds ratios, confusion metrics, log loss, rank AUC and chart coordinates verified')
 knn=json.loads((Path(__file__).resolve().parent/'knn-example.json').read_text(encoding='utf-8'))
 kx=np.array(knn['x']);ky=np.array(knn['y'])
 for row in knn['grid']+[dict(x=knn['query'],k1=knn['k1'],k3=knn['k3'])]:
  order=np.argsort(abs(kx-row['x']),kind='stable')
  for k in [1,3]:assert abs(row[f'k{k}']-ky[order[:k]].mean())<1e-12
 ks=knn['scaling'];kp=np.array(ks['points']);kq=np.array(ks['query']);std=kp.std(axis=0)
 assert np.allclose(std,ks['scales'])
 assert np.allclose(np.linalg.norm(kp-kq,axis=1),ks['raw'])
 assert np.allclose(np.linalg.norm((kp-kq)/std,axis=1),ks['scaled'])
 assert np.argmin(ks['raw'])==1 and np.argmin(ks['scaled'])==0
 assert knn['vote']['probability']==np.mean(knn['vote']['labels'])
 print('Chapter 29 neighbor predictions, stable ties, scaling distances and voting verified')
 tree30=json.loads((Path(__file__).resolve().parent/'decision-tree-example.json').read_text(encoding='utf-8'))
 raw30=json.loads((Path(__file__).resolve().parent/'example-data.json').read_text(encoding='utf-8'))['rows']
 x30=np.array([r['area'] for r in raw30[:20]]);y30=np.array([r['price'] for r in raw30[:20]])
 for candidate in tree30['candidates']:
  mask=x30<=candidate['threshold'];loss=sum(np.sum((v-v.mean())**2) for v in [y30[mask],y30[~mask]])
  assert abs(loss-candidate['sse'])<1e-8
 assert tree30['thresholds']==[31,80]
 assert min(tree30['candidates'],key=lambda r:r['sse'])['threshold']==31
 for leaf in tree30['leaves']:
  assert abs(leaf['mean']-np.mean([r['price'] for r in raw30 if r['id'] in leaf['ids']]))<1e-12
 for key,rr in [('train_mae',raw30[:20]),('test_mae',raw30[20:])]:
  pp=[tree30['leaves'][0 if r['area']<=31 else 1 if r['area']<=80 else 2]['mean'] for r in rr]
  assert abs(np.mean(np.abs(np.array(pp)-[r['price'] for r in rr]))-tree30['metrics'][key])<1e-12
 cc=tree30['classification'];gini=lambda counts:1-np.sum((np.array(counts)/sum(counts))**2)
 assert gini(cc['parent'])==cc['parent_gini'] and gini(cc['left'])==cc['weighted_gini']
 assert cc['parent_gini']-cc['weighted_gini']==cc['gain']
 print('Chapter 30 split losses, leaf means, held-out errors and Gini impurity verified')
 cluster31=json.loads((Path(__file__).resolve().parent/'clustering-example.json').read_text(encoding='utf-8'))
 xp31=np.array(cluster31['points'],dtype=float)
 for model31 in cluster31['models']:
  centers31=np.array(model31['centers']);labels31=np.array(model31['labels'])
  assert np.array_equal(np.argmin(((xp31[:,None]-centers31)**2).sum(axis=2),axis=1),labels31)
  for j in range(len(centers31)):assert np.allclose(centers31[j],xp31[labels31==j].mean(axis=0))
  assert abs(np.sum((xp31-centers31[labels31])**2)-model31['inertia'])<1e-10
 from scipy.spatial.distance import cdist
 from scipy.cluster.hierarchy import linkage
 dd31=cdist(xp31,xp31);ll31=np.array(cluster31['models'][1]['labels'])
 for i,ss31 in enumerate(cluster31['silhouette']):
  aa31=np.mean(dd31[i,(ll31==ll31[i])&(np.arange(6)!=i)]);bb31=np.mean(dd31[i,ll31!=ll31[i]])
  assert abs((bb31-aa31)/max(aa31,bb31)-ss31['s'])<1e-12
 assert np.allclose(linkage(np.array(cluster31['hierarchy']['x'])[:,None],method='complete'),cluster31['hierarchy']['merges'])
 print('Chapter 31 centers, assignments, inertia, silhouette distances and complete linkage verified')
 read32=json.loads((ROOT/'reading-results-example.json').read_text(encoding='utf-8'))
 raw32=json.loads((ROOT/'example-data.json').read_text(encoding='utf-8'))['rows'];xx32=np.array([r['area'] for r in raw32]);yy32=np.array([r['price'] for r in raw32])
 assert abs(read32['mean']-yy32.mean())<1e-12 and read32['median']==np.median(yy32)
 from scipy.stats import t as t32
 assert np.allclose(read32['mean_ci'],t32.interval(.95,29,loc=yy32.mean(),scale=yy32.std(ddof=1)/np.sqrt(30)))
 def mae32(tr,te):
  design=np.column_stack([np.ones(len(tr)),xx32[tr]]);beta=np.linalg.lstsq(design,yy32[tr],rcond=None)[0]
  return np.mean(abs(yy32[te]-(beta[0]+beta[1]*xx32[te])))
 ids32=np.arange(30);folds32=np.array_split(ids32,3)
 expected32=[mae32(ids32,ids32),mae32(ids32[:20],ids32[20:]),np.mean([mae32(np.setdiff1d(ids32,f),f) for f in folds32])]
 assert np.allclose(expected32,read32['mae'])
 print('Chapter 32 summary statistics, t interval and independent least-squares evaluation errors verified')
 print(f'{len(items)} chapters: {len(available)} available, {len(items)-len(available)} planned; {len(pages)} pages checked')
 print('Chapter 01 example counts, ranges, missing-value example and scatter count verified')
 for error in errors:print('ERROR:',error)
 if not errors:print('All checks passed')
 return bool(errors)
if __name__=='__main__':sys.exit(main())

