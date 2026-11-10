"""Close only after all fixed accounts, audits, comparisons, and prefixes pass."""
from pathlib import Path
import hashlib,json
from build_inputs import HERE,read,write,now,ref

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def main():
 assert not (HERE/'complete.json').exists()
 freeze=read(HERE/'freeze.json')
 for p,h in freeze['inputs'].items():assert sha(p)==h,p
 for p,h in freeze['code'].items():assert sha(HERE/'code'/p)==h,p
 for p in ['audit/h1-verification.json','audit/preflight.json','audit/order-lifecycle.json','technical-prefix-v2/summary.json']:assert read(HERE/p)['passed'],p
 assert read(HERE/'analysis-v2/independent-accounting.json')['all_passed']
 acc=read(HERE/'accounts-v2/summary.json');assert acc['completed_accounts']==acc['historical_account_runs']==12 and acc['daily_rows']==34392
 assert read(HERE/'funnel-v2/summary.json')['decision_rows']==34392
 assert len(read(HERE/'comparison/paired-metrics.json'))==12
 old=read(HERE.parent/'algorithm-baselines-20261024/registry.json')
 for p,h in old['sha256'].items():assert sha(HERE.parents[1]/p)==h,p
 assert (HERE/'report/index.html').exists() and (HERE/'CONCLUSION.md').exists()
 artifacts={str(p.relative_to(HERE)):sha(p) for folder in ['audit','analysis-v2','comparison','misses-v2','report','code','diagnosis','entry-profiles','technical-prefix-v2'] for p in sorted((HERE/folder).rglob('*')) if p.is_file() and '__pycache__' not in str(p) and not p.is_symlink() and not p.name.endswith('.gz')}
 for p in sorted((HERE/'accounts-v2').iterdir()):
  if p.is_file():artifacts[str(p.relative_to(HERE))]=sha(p)
 write(HERE/'complete.json',dict(status='complete',recorded_at=now(),model='E0 unchanged + RS-H1 + daily buy lease / fresh competition',economic_accounts=12,technical_prefix_accounts=12,daily_account_rows=34392,core_registry_files_unchanged=len(old['sha256']),frozen_code_and_inputs_unchanged=True,formula_or_trading_rule_revisions_after_results=0,old_results_unchanged_by_frozen_hash=True,rotation_added=False,network_quote_queries=0,scope='A-only current survivor/current cap/current classification historical development, 2015-01-01—2026-10-22',freeze=ref(HERE/'freeze.json'),artifacts=artifacts,known_failures_preserved=['h1-attempt0','audit/prepare-h1.log','audit/preflight-attempt0.log','audit/ledger-tests.log']))
 print({'status':'complete','economic_accounts':12,'technical_prefix_accounts':12},flush=True)
if __name__=='__main__':main()
