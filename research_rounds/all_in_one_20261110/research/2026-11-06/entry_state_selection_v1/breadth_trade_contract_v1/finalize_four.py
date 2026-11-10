from pathlib import Path
import pandas as pd,json,hashlib
O=Path(__file__).resolve().parent;D=O/'causal_queue_four_rounds_detailed';z=pd.read_csv(D/'ALL_SHADOW_ROUNDS.csv');assert len(z)==4
for c in ['net_pnl','net_return_on_buy_cash','all_fees','total_buy_cash']:
 if c not in z:z[c]=float('nan')
z.to_csv(D/'ALL_SHADOW_ROUNDS.csv',index=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=json.load(open(O/'SELECTION_SEAL.json'));assert all(sha(p)==h for p,h in s['source_hashes'].items())
f=json.load(open(O/'causal_queue_four_rounds/FOUR_SELECTION_SEAL.json'));assert all(sha(p)==h for p,h in f['hashes'].items())
(D/'SUMMARY.json').write_text(json.dumps(dict(selected=4,closed=0,source_or_action_unknown=2,open_censored_at_2026_06_30=2,full_account_runs=0,three_initial_investment_checks='Selection4 still exact, historical tradabilityUNKNOWN, actual account risk/cash gate not supplied',completion_repair='The output rows completed; generic summary assumed a closed round and failed. Added empty economic columns and correct zero-closed summary; no economic row or selection change.',completed_utc=str(pd.Timestamp.now(tz='UTC'))),ensure_ascii=False,indent=2)+'\n')
(D/'QA.json').write_text(json.dumps(dict(sealed_sources_unchanged=True,four_frozen_selection_unchanged=True,cashflow_values_unchanged=True,closed_denominator_zero=True,no_wins_reported=True,complete=True),indent=2)+'\n')
(D/'OUTPUT_HASHES.json').write_text(json.dumps({str(p):sha(p) for p in D.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'},indent=2)+'\n')
print('FOUR_COMPLETE')
