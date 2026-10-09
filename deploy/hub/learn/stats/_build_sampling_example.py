"""Reproducible, fictional sampling example for chapter 02 (no market data)."""
from pathlib import Path
import json, random
from collections import Counter
from statistics import mean, pstdev
ROOT=Path(__file__).resolve().parent

def build():
 population=[{'id':i+1,'group':'A' if i<80 else 'B','price':100 if i<80 else 200} for i in range(100)]
 frame=population[:20]+population[80:]
 selected=frame[:10]+frame[20:30]
 rng=random.Random(20261007)
 trials=[]
 for label,source in [('population',population),('frame',frame)]:
  for n in (5,20):
   values=[mean(r['price'] for r in rng.sample(source,n)) for _ in range(500)]
   trials.append({'source':label,'n':n,'repetitions':500,'mean':mean(values),'sd':pstdev(values),'frequencies':dict(sorted(Counter(values).items()))})
 result={'kind':'fictional teaching example','seed':20261007,'unit':'만원/㎡','population':population,'frame_ids':[r['id'] for r in frame],'selected_ids':[r['id'] for r in selected],'population_mean':mean(r['price'] for r in population),'frame_mean':mean(r['price'] for r in frame),'sample_mean':mean(r['price'] for r in selected),'trials':trials}
 (ROOT/'sampling-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 return result
if __name__=='__main__':
 d=build()
 print('Population/frame/sample means:',d['population_mean'],d['frame_mean'],d['sample_mean'])
 for t in d['trials']:print(t['source'],t['n'],round(t['mean'],2),round(t['sd'],2))
