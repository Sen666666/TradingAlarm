from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,csv,re
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
 return h.hexdigest()
def main():
 checks={}
 def verify(label,mapping,base=ROOT):
  for name,expected in mapping.items():
   p=Path(name);p=p if p.is_absolute() else base/p
   assert sha(p)==expected,(label,name)
  checks[label]=len(mapping)
 prep=read(HERE/'preparation.json');verify('new_sources',prep['sources']);verify('new_EMA_outputs',prep['files'],HERE)
 verify('account_freeze',read(HERE/'account-freeze.json')['sha256'])
 verify('old_LER_evidence',read(ROOT/'research_rounds/a-share-local-entry-reentry-20261026/complete.json')['artifacts'])
 verify('old_sector_evidence',read(ROOT/'research_rounds/sector-ix-i-20261026/complete.json')['artifacts'])
 verify('old_video_preparation',read(ROOT/'research_rounds/video-ema-a-share-20261026/PREPARATION_MANIFEST.json')['artifacts'])
 verify('E0_R_R1_registry',read(ROOT/'research_rounds/algorithm-baselines-20261024/registry.json')['sha256'])
 audit=read(HERE/'analysis/accounting.json');prefix=read(HERE/'technical/prefix-identity.json');control=read(HERE/'I-controls.json')
 assert audit['passed'] and audit['daily_rows']==33600 and audit['maximum_NAV_difference_cny']=='0'
 assert audit['actual_buy_checks']==4365 and audit['native_exit_checks']==4274
 assert prefix['passed'] and prefix['rows']==dict(daily=11632,decisions=11632) and prefix['paths']==16
 assert control['passed'] and len(control['controls'])==4
 with (HERE/'analysis/summary.csv').open() as f:rows=list(csv.DictReader(f))
 assert len(rows)==24 and len({r['account'] for r in rows})==24
 assert all(float(r['max_drawdown'])>.2 for r in rows)
 for r in rows:
  assert abs(sum(float(r[k]) for k in ['tail_pnl','ordinary_pnl','open_pnl'])-(float(r['final_nav'])-1e6))<1e-6
 page=(HERE/'review/index.html').read_text();links=re.findall(r'(?:href|src)="([^"]+)"',page)
 for link in links:
  if not link.startswith(('http:','https:')):assert (HERE/'review'/link).exists(),link
 checks['local_report_links']=len(links)
 outputs={str(p.relative_to(ROOT)):sha(p) for p in sorted(HERE.rglob('*')) if p.is_file() and p.name!='complete.json' and '__pycache__' not in p.parts}
 result=dict(status='complete',recorded_at=datetime.now(timezone.utc).isoformat(),adopted_as_default=False,
   candidate='EMA9>21>50 and all three rising; individual-stock entry gate only',
   paths=24,new_economic_paths=20,old_I_controls=4,economic_runs=1,economic_reruns=0,post_result_rule_changes=0,
   daily_rows=33600,independent_NAV_error_cny='0',native_exit_checks=4274,buy_checks=4365,
   real_financial_prefix_paths=16,prefix_daily_rows=11632,prefix_decision_rows=11632,
   old_trade_diagnosis_only=True,old_I_cycles=738,old_I_blocked_cycles=374,old_I_tail_count=72,old_I_blocked_tails=39,
   chart_windows=12,posthoc_actual_stock_cases=8,source_and_preservation_checks=checks,
   new_market_downloads=0,live_trading=False,local_report='http://127.0.0.1:8800/review/',
   separate_video_daily_adaptation='research_rounds/video-ema-a-share-20261026/DAILY_ADAPTATION_FOR_REVIEW.md',
   video_daily_adaptation_financial_accounts=0,artifacts=outputs,artifact_count=len(outputs))
 with (HERE/'complete.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps({k:v for k,v in result.items() if k!='artifacts'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
