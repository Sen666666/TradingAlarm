"""Final data-corrected package; preserve interrupted v1 and exact model states."""
from pathlib import Path
from build_inputs import HERE,read,write,ref,sha256,now
from current_pool_bridge import load_bundle,load_prepared_states

def main():
 out=HERE/'inputs-v2';b=load_bundle(out/'input-manifest.json');load_prepared_states(b,HERE/'prepared-v2');assert b.signal_ready
 qualified=[x for x in b.lines if x.company_cap_cny is not None]
 assert len(qualified)==1709 and all(x.sector_id in b.sector_series for x in qualified)
 proof=read(out/'state-reuse-proof.json');assert proof['all_series_records_exactly_equal'] and proof['no_E0_RS_input_or_formula_changes']
 assert read(HERE/'audit/industry-repair-v2/report.json')['qualified_industry_unknown']==0
 tests=(HERE/'audit/execution-partition-regression-01.log').read_text();assert '\nOK\n' in tests
 old=read(HERE/'inputs-v1/economic-protocol.json');protocol=dict(old)
 for name,h in old['code_sha256'].items():assert sha256(HERE/'code'/name)==h,'Frozen v1 source was altered: '+name
 protocol.update(status='frozen',recorded_at=now(),account_runs_before_this_freeze=13,completed_accounts_before_this_freeze=0,
  prior_invalid_run=ref(HERE/'accounts-v1/aborted.json'),data_mapping_repair=ref(HERE/'audit/industry-repair-v2/report.json'),
  data_limit='Corrected nonempty22-Oct industry tree gives5575 unique raw classifications;1709 qualified all have a same-source industry. Current cap000016/002731 unknown retained;000016 industry unknown;002731 source origin unknown. Prices/actions remain same audited sources.',
  dispatch='Two independent process groups T0/T1/B0 and S0/S1; same frozen HistoryRunner, each account once, no shared portfolio state; exact synthetic scheduling equivalence checked.',
  code_sha256={**old['code_sha256'],'dispatch_accounts.py':sha256(HERE/'code/dispatch_accounts.py')})
 p=out/'economic-protocol.json';assert not p.exists();write(p,protocol)
 files=[p,out/'input-manifest.json',HERE/'prepared-v2/manifest.json',out/'market-rules.json',out/'fx-quotes.json',
  HERE/'audit/data-closeout-v2.json',out/'state-reuse-proof.json',HERE/'audit/industry-repair-v2/report.json',
  HERE/'audit/execution-partition-regression-01.log',HERE/'code/dispatch_accounts.py',HERE/'code/test_dispatch_accounts.py',
  *[HERE/'code'/name for name in old['code_sha256']]]
 receipt=out/'economic-protocol-frozen.json'
 write(receipt,dict(kind='economic_protocol_frozen',round_id=HERE.name,status='frozen',recorded_at=now(),scope_sha256=sha256(HERE/'scope.json'),
  artifacts={str(p.resolve()):sha256(p) for p in files},main_accounts=13,prior_invalid_accounts_started=13,prior_completed_accounts=0,algorithm_changes=0))
 package=dict(schema_version=1,mode='frozen_A13_historical',scope=ref(HERE/'scope.json'),data_closeout=ref(HERE/'audit/data-closeout-v2.json'),
  economic_protocol_frozen=ref(receipt),economic_protocol=ref(p),bridge_manifest=ref(out/'input-manifest.json'),
  prepared_manifest=ref(HERE/'prepared-v2/manifest.json'),market_rules=ref(out/'market-rules.json'),fx_quotes=ref(out/'fx-quotes.json'),
  start=protocol['account_start'],end=protocol['account_end'])
 write(out/'package.json',package);print({'frozen_at':protocol['recorded_at'],'qualified':1709,'industry_missing':0,'main_accounts':13},flush=True)

if __name__=='__main__':main()
