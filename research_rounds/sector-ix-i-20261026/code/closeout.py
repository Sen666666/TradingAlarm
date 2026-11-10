from sec_common import *
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote

def main():
 groups={}
 for name,refs in [('pair_freeze',read(HERE/'pair-freeze.json')['sha256']),('valid_economic_freeze',read(HERE/'account-freeze-v2.json')['sha256']),('previous_213_artifacts',read(PREV/'complete.json')['artifacts']),('budget_55_artifacts',read(BUDGET/'complete.json')['artifacts']),('E0_R_R1',read(ROOT/'research_rounds/algorithm-baselines-20261024/registry.json')['sha256'])]:
  for p,h in refs.items():assert sha(ROOT/p)==h,(name,p)
  groups[name]=len(refs)
 old={r['symbol']:r for r in read(IX/'signals/manifest.json')['series']}
 for r in read(HERE/'signals/manifest.json')['series']:
  assert r['source']['sha256']==old[r['symbol']]['output_sha256'];assert sha(ROOT/r['source']['path'])==r['source']['sha256'];assert sha(HERE/'signals'/f"{r['symbol']}.parquet")==r['output_sha256']
 assert sha(HERE/'sources/931152cons.xls')==read(HERE/'scope.json')['innovation_source']['sha256']
 class Links(HTMLParser):
  def __init__(self):super().__init__();self.links=[]
  def handle_starttag(self,t,a):
   for k,v in a:
    if k in ['src','href']:self.links.append(v)
 l=Links();l.feed((HERE/'report/index.html').read_text());links=[]
 for ref in l.links:
  u=urlsplit(ref)
  if u.scheme or not u.path:continue
  assert (HERE/'report'/unquote(u.path)).resolve().exists(),ref;links.append(ref)
 audit=read(HERE/'analysis-v2/accounting.json');prefix=read(HERE/'technical/prefix-identity-v2.json');assert audit['passed'] and prefix['passed'];assert audit['max_absolute_nav_error_cny']=='0'
 write(HERE/'source-identity.json',dict(passed=True,verified_groups=groups,unchanged_signal_sources=256,official_membership_sha_checked=True,local_report_links=len(links),recorded_at=now()))
 files={str(p.relative_to(ROOT)):sha(p) for p in sorted(HERE.rglob('*')) if p.is_file() and p.name not in ['server.log','complete.json']}
 write(HERE/'complete.json',dict(status='complete',recorded_at=now(),valid_economic_paths=8,invalid_capacity_paths_preserved=8,economic_reruns_for_capacity_repair=1,post_result_strategy_parameter_changes=0,stocks=256,pairs=11670,independent_economic_daily_rows=11200,nav_error_cny='0',same_candidate_list_checks=5600,physical_prefix_daily_rows=5816,physical_prefix_decision_rows=5816,old_model_and_results_preserved=True,old_IX_full_financial_controls=2,local_report='http://127.0.0.1:8797/report/',new_stock_price_downloads=0,new_public_membership_downloads=1,live_trading=False,adopted_as_default=False,artifacts=files,artifact_count=len(files)))
 print(dict(complete=True,artifacts=len(files),verified_groups=groups))
if __name__=='__main__':main()
