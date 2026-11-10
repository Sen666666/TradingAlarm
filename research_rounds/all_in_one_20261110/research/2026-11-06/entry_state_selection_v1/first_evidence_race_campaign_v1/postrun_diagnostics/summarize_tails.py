from pathlib import Path
import pandas as pd,json,hashlib
O=Path(__file__).resolve().parent;F=O.parent/'full';z=pd.read_csv(F/'report/ALL108_OLD_TAIL_CAMPAIGNS.csv');a=z[z.arm.eq('A')].set_index('baseline_round_id');z['A_close_days']=z.baseline_round_id.map(a.holding_close_days)
rows=[]
for scope,df in [('ALL_108_OLD_TAILS',z),('DOWN_FIRST_19',z[z.race.eq('DOWN_FIRST')])]:
 for (window,arm),g in df.groupby(['window','arm']):
  c=g[g.evidence_usable_closed]
  rows.append(dict(scope=scope,window=window,arm=arm,old_tail_count=len(g),complete_known=len(c),unknown_or_incomplete=len(g)-len(c),complete_known_net=c.net.sum(),same_known_old_A_net=c.old_initial_net.sum(),known_net_retention=c.net.sum()/c.old_initial_net.sum(),known_close_holding_days=c.holding_close_days.sum(),same_known_A_close_days=c.A_close_days.sum(),known_close_coverage=c.holding_close_days.sum()/c.A_close_days.sum(),all_attempts=g.attempts.sum(),actual_reentered=int(g.filled_attempts.gt(1).sum()),complete_known_winners=int(c.net.gt(0).sum())))
pd.DataFrame(rows).to_csv(O/'TAIL_COVERAGE_SUMMARY.csv',index=False)
r=pd.read_csv(F/'INITIAL_RECONCILIATION.csv');r['window']=r.round_id.str.split('|').str[0]
qa={}
for window,g in r[r.old_usable].groupby('window'):
 expected=2616 if window=='2022' else 1312;assert len(g)==expected
 boolcols=[c for c in g if c.endswith('_match')];assert g[boolcols].all().all();assert g.net_delta.abs().max()<=1e-7
 qa[window]=dict(old_usable_rows=len(g),all_components_match=True,max_abs_net_delta=g.net_delta.abs().max())
zz=pd.read_csv(F/'CAMPAIGNS.csv');assert len(zz)==16344
assert not zz[zz.evidence_usable_closed].duplicated(['arm','campaign_key']).any()
assert not zz[zz.all_arm_common_known].duplicated(['arm','campaign_key']).any()
qa['all_permits']=4086;qa['arm_rows']=len(zz);qa['closed_known_campaigns_unique']=True;qa['common_known_campaigns_unique']=True
(O/'FINAL_SELF_RECONCILIATION.json').write_text(json.dumps(qa,indent=2)+'\n')
paths=list(F.glob('*.csv'))+list(F.glob('*.json'))+list((F/'report').glob('*'))+list(O.glob('*'))
(O/'POSTRUN_SOURCE_OUTPUT_HASHES.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file() and p.name!='POSTRUN_SOURCE_OUTPUT_HASHES.json'},indent=2)+'\n')
print(json.dumps(qa,indent=2));print(pd.DataFrame(rows).to_string(index=False))
