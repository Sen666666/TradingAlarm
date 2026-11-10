"""Freeze the finite13-account package only after data and signal review."""
from build_inputs import HERE,OLD,read,write,ref,sha256,now
from current_pool_bridge import load_bundle,load_prepared_states
from run_first10 import first10_specs
from dataclasses import asdict

def main():
 out=HERE/'inputs-v1';prepared=HERE/'prepared-v1/manifest.json';checks=read(HERE/'audit/signal-review-v1/prefix-checks.json')
 assert checks['exact_state_identity_vs_parallel_writer'] and all(x['exact'] for x in checks['checks'])
 assert read(prepared)['signal_ready'] and len(read(prepared)['series'])==1801
 assert read(HERE/'audit/signal-visual-review.json')['reviewed_before_accounts'] is True
 b=load_bundle(out/'input-manifest.json');load_prepared_states(b,prepared.parent);assert b.signal_ready
 protocol=read(out/'economic-protocol-draft.json');protocol.update(status='frozen',recorded_at=now(),
  code_sha256={p.name:sha256(p) for p in (HERE/'code').glob('*.py')},
  accounts=[asdict(x) for x in first10_specs()],
  ordinary_loss_rationale='continuous ordinary net loss and tail contribution disclosure; no added hard percentage promotion threshold',
  fixed_stages=['2015-2017','2018-2020','2021-2023','2024-2026-10-22'],
  technical_prefixes=['2017-12-31','2020-12-31','2023-12-31'],
  economic_comparison_accounts=13,account_runs_before_this_freeze=0,
  data_limit='5576 raw stocks audited,200 BSE source conflicts resolved;002731 source origin unresolved,000016/002731 cap unknown retained; qualified1709 plus2unknown and90indices produce1801shared series.',
  same_date_ordinary_actions='6038832024-06-27 two explicit per10-old-share distributions summed: cash0.66,split1.3; both source texts retained.',
  B0_fractional_target_mapping='floor explicit share-unit targets without increasing frozen gross caps; no cash invented')
 p=out/'economic-protocol.json';assert not p.exists();write(p,protocol)
 files=[p,out/'input-manifest.json',prepared,out/'market-rules.json',out/'fx-quotes.json',
  HERE/'audit/data-closeout.json',HERE/'audit/signal-visual-review.json',HERE/'audit/signal-review-v1/prefix-checks.json',
  HERE/'audit/execution-regression-final-04.log',OLD/'audit-fees/fees.json',OLD/'audit-execution/ECONOMIC_READING_DECISION.md',
  *list((HERE/'code').glob('*.py'))]
 receipt=out/'economic-protocol-frozen.json'
 write(receipt,dict(kind='economic_protocol_frozen',round_id=HERE.name,status='frozen',recorded_at=now(),scope_sha256=sha256(HERE/'scope.json'),
  artifacts={str(p) if not p.is_relative_to(out) else str(p.relative_to(out)):sha256(p) for p in files},
  historical_economic_accounts_before_freeze=0,main_accounts=13,algorithm_changes=0))
 package=dict(schema_version=1,mode='frozen_A13_historical',scope=ref(HERE/'scope.json'),
  data_closeout=ref(HERE/'audit/data-closeout.json'),economic_protocol_frozen=ref(receipt),economic_protocol=ref(p),
  bridge_manifest=ref(out/'input-manifest.json'),prepared_manifest=ref(prepared),market_rules=ref(out/'market-rules.json'),fx_quotes=ref(out/'fx-quotes.json'),
  start=protocol['account_start'],end=protocol['account_end'])
 write(out/'package.json',package)
 print({'frozen_at':protocol['recorded_at'],'main_accounts':13,'algorithm_changes':0},flush=True)

if __name__=='__main__':main()
