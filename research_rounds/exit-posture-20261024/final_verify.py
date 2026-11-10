from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
from html.parser import HTMLParser
R=Path(__file__).resolve().parent;O=R/'results/v0';f=json.loads((R/'freeze.json').read_text())
for p,h in f['sha256'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p
s=pd.read_csv(O/'summary.csv');a=pd.read_csv(O/'aggregates.csv');cache={x.key:pd.read_parquet(O/'accounts'/x.key/'ledger.parquet').nav for x in s.itertuples()}
for row in a.to_dict('records'):
 mode='P' if row['mode']=='M' and row['policy']=='E0' else row['mode']
 z=s.loc[(s.window==row['window'])&(s.scenario==row['scenario'])&(s['mode']==mode)&(s.policy==row['policy'])]
 if row['group']=='exAU0_12':z=z.loc[z.symbol!='AU0']
 nav=pd.concat([cache[k] for k in z.key],axis=1,sort=True).ffill().fillna(1.).mean(axis=1)
 drawdown=1-nav/np.maximum.accumulate(np.r_[1.,nav])[1:]
 np.testing.assert_allclose([nav.iloc[-1]-1,drawdown.max()],[row['net_return'],row['max_drawdown']],atol=1e-12)
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  for key,value in attrs:
   if key in ['src','href'] and not value.startswith(('#','http')):self.links.append(value)
x=Links();x.feed((R/'index.html').read_text())
for link in x.links:assert (R/link).is_file(),link
record={'frozen_files_unchanged':len(f['sha256']),'independent_aggregate_checks':len(a),'report_local_links_and_images_valid':len(x.links),'visual_review':'Both13-asset price/NAV/actual-exit contact sheets, aggregate, all-asset return/drawdown comparison and full gold trajectory viewed; no causal or display anomaly found','observations':['Gold sensitive exit wins primary, fails2024 and goldETF; do not extrapolate','Semiconductor and bank extended advances cut; rebound retries remain in declining HK assets','2024 September fast start retained by both but later paths and retry costs differ'],'result_after_rule_changes':0,'accounts_rerun':0,'passed':True}
(O/'final-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
# Post-result review pages; no simulation rerun.
p=R/'index.html';html=p.read_text();html=html.replace('<h2>8. 审计与复核</h2>','<details><summary>两个窗口全部13样本轨迹复盘</summary><img loading="lazy" src="charts/review-primary.png"><img loading="lazy" src="charts/review-history2024.png"></details><h2>8. 审计与复核</h2>');html=html.replace('独立核账见audit.json；','独立核账通过：507账户、9624条成交、最大净值误差2.89e-15；84个分仓汇总也独立复核。详见<a href="results/v0/final-verification.json">最终核验</a>及audit.json；');p.write_text(html)
manifest={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in R.rglob('*') if p.is_file() and p.name!='artifact-manifest.json'}
(R/'artifact-manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(record,ensure_ascii=False,indent=2))
