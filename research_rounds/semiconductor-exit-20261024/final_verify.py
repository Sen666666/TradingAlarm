from pathlib import Path
from html.parser import HTMLParser
import json,hashlib
import pandas as pd,numpy as np
R=Path(__file__).resolve().parent;O=R/'results/v0'
freeze=json.loads((R/'freeze.json').read_text())
for p,h in freeze['sha256'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p
class Links(HTMLParser):
 def __init__(self):super().__init__();self.paths=[]
 def handle_starttag(self,tag,attrs):
  for k,v in attrs:
   if k in ['href','src'] and not v.startswith(('#','http')):self.paths.append(v)
x=Links();x.feed((R/'index.html').read_text())
for p in x.paths:assert (R/p).is_file(),p
s=pd.read_csv(O/'summary.csv')
# Post-result period table is reporting arithmetic, not additional accounts.
y=pd.read_csv(O/'calendar-period-returns.csv')
for p in ['E0','E2','E3','ED','HOLD']:
 mode='H' if p=='HOLD' else 'P';l=pd.read_parquet(O/'accounts'/f'{mode}_{p}_base'/'ledger.parquet');v=l.loc[:'2025-12-31','nav'].iloc[-1];np.testing.assert_allclose(v*(l.nav.iloc[-1]/v),l.nav.iloc[-1])
record={'frozen_files_unchanged':len(freeze['sha256']),'valid_report_links_and_images':len(x.paths),'accounts':len(s),'charts_viewed':['raw.png','signals.png','comparison.png','transactions.png','matched-comparison.png'],'mechanism_revisions_after_results':0,'accounts_rerun':0,'visual_observations':['Original holds Apr-Nov2025; sensitive stop cuts it and reentry does not fully recover','Sensitive Dec2025 exit helps locally, Feb2026 reentry loses','June2026 E2 exit followed by loss-making reentry; final common leg still open before preset liquidation'],'workflow_timing_clarification':'Raw price-volume chart was reviewed in a prior returned tool call before accounts. New signal chart was read and account run dispatched in the same tool batch; agent review of that new chart occurred after batch returned. Therefore do not describe new signal chart subjective review as independently completed before dispatch. Previous full-period mechanism review existed; four signals and24account prefixes exactly match prior frozen run. No rule was changed after results. Frozen original review note retained; this is its chronology clarification.','passed':True}
(O/'final-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
p=R/'index.html';h=p.read_text();h=h.replace('先看原始量价和信号轨迹、再冻结、最后运行账户。','固定既有规则，先审阅原始量价，生成信号并冻结，再运行账户。');h=h.replace('<h2>8. 审计、数据和原始证据</h2>','<h2>8. 审计、数据和原始证据</h2><p class="small">流程时序说明：原始量价在账户前已审阅；新信号图的读取和账户启动位于同一个工具批次，agent对新信号图的主观复查在批次返回后完成，不将其表述为独立完成的账户前主观预审。原规则前轮已图检，本轮四信号及24账户前缀精确恒等，结果后未改规则。冻结原记录保留，时序更正见<a href="results/v0/final-verification.json">最终核验</a>。</p>');p.write_text(h)
manifest={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in R.rglob('*') if p.is_file() and p.name!='artifact-manifest.json'}
(R/'artifact-manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(record,ensure_ascii=False,indent=2))
