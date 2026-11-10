from pathlib import Path
from html.parser import HTMLParser
import json,hashlib
import numpy as np,pandas as pd
R=Path(__file__).resolve().parent;O=R/'results/v0'
frozen=json.loads((R/'freeze.json').read_text())
for p,h in frozen['sha256'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p
class Links(HTMLParser):
 def __init__(self):super().__init__();self.paths=[]
 def handle_starttag(self,tag,attrs):
  for k,v in attrs:
   if k in ['href','src'] and not v.startswith(('#','http')):self.paths.append(v)
x=Links();x.feed((R/'index.html').read_text())
for p in x.paths:assert (R/p).is_file(),p
old=pd.read_parquet(R/'../three-layer-prototype-20261024/inputs/USHJ512480.parquet')[['open','high','low','close','volume']];new=pd.read_parquet(R/'inputs/USHJ512480.parquet');pd.testing.assert_frame_equal(old,new.loc[old.index],check_exact=True)
a=json.loads((O/'audit.json').read_text());assert a['passed'] and a['accounts']==240
s=pd.read_csv(O/'summary.csv');readable=pd.read_csv(O/'readable-returns.csv');assert len(readable)==10
# Validate every displayed return against stored numeric results, independent of plotting code.
labels={'E0':'原结构退出','E2':'＋2倍波幅退出','E3':'＋3倍波幅退出','ED':'＋向下量价事件','HOLD':'买入持有'}
cases=json.loads((R/'cases.json').read_text());count=0
for i,c in enumerate(cases):
 for p,label in labels.items():
  v=s.loc[s.case.eq(c['id'])&s.scenario.eq('base')&s.policy.eq(p)&s['mode'].eq('H' if p=='HOLD' else 'P')].iloc[0].net_return
  assert readable.iloc[i][label]==f'{v*100:+.2f}%';count+=1
record={'frozen_files_unchanged':len(frozen['sha256']),'report_local_links_and_images_valid':len(x.paths),'displayed_return_cells_checked':count,'original_1781_rows_unchanged':len(old),'added_days':len(new)-len(old),'visual_review':'all10price/NAV/DD charts in5contact sheets plus fullYTDmatched and matrix viewed; successful and failed policies retained','account_reruns':0,'policy_changes':0,'passed':True}
(O/'final-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
manifest={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in R.rglob('*') if p.is_file() and p.name!='artifact-manifest.json'}
(R/'artifact-manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(record,ensure_ascii=False,indent=2))
