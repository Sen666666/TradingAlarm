from pathlib import Path
import json,hashlib,datetime
R=Path(__file__).resolve().parent;P=R/'../exit-posture-20261024';paths=[R/x for x in ['PROTOCOL.md','prepare.py','preflight.py','model.py','engine.py','run.py','freeze.py','inputs.json','review-before-accounts.json','charts/raw.png','charts/signals.png']]+list((R/'prepared').glob('*'))+list((R/'inputs').glob('*'))
paths += [R/'../pv-participation-response-20261020/code'/x for x in ['numeric.py','participation.py']]
paths += [P/'freeze.json']
for scenario in ['base','cost2','delay1']:
 for mode,policies in [('P',['E0','E2','E3','ED']),('M',['E2','E3','ED']),('H',['HOLD'])]:
  for p in policies:paths.append(P/'results/v0/accounts'/f'USHJ512480__primary__{scenario}__{mode}__{p}'/'ledger.parquet')
payload={'frozen_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'new_window_account_results_seen':False,'existing_history_and_previous_round_seen':True,'accounts':24,'parameter_search':False,'sha256':{str(p.relative_to(R)) if p.is_relative_to(R) else str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
with (R/'freeze.json').open('x') as f:json.dump(payload,f,indent=2)
print('Frozen',len(paths),'files before new-window accounts')
