from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent
c=pd.read_csv(O/'ALL_M3_RESULTS.csv',dtype={'window':str},low_memory=False)
rows=[]
for key,g in c.groupby(['window','event_type']):
 k=g[g.feature_known];a=g[g.baseline_selected&~g.new_selected];b=g[~g.baseline_selected&g.new_selected]
 rows.append(dict(window=key[0],event_type=key[1],N=len(g),known=len(k),unknown=len(g)-len(k),spearman_PVR_robust=k[['PVR_score','robust_score']].corr(method='spearman').iloc[0,1],original_fresh=int((g.baseline_selected&g.member_state.eq('FRESH')).sum()),new_fresh=int((g.new_selected&g.member_state.eq('FRESH')).sum()),removed=len(a),added=len(b),removed_fresh=int(a.member_state.eq('FRESH').sum()),added_fresh=int(b.member_state.eq('FRESH').sum()),removed_fresh_tails=int((a.tail30&a.member_state.eq('FRESH')).sum()),added_fresh_tails=int((b.tail30&b.member_state.eq('FRESH')).sum())))
pd.DataFrame(rows).to_csv(O/'MECHANISM_SUMMARY.csv',index=False)
w=.9**np.arange(20,-1,-1);w/=w.sum()
def q(e):
 d=w*np.array(e);return d.sum()-max(0,d.max())
e=np.zeros(21);e[-1]=1.5;assert q(e)==0
e[-2]=1;assert q(e)>0
e[-3]=-1;assert abs(q(e)-w[-2]+w[-3])<1e-12
assert max(w)*1.5<.169
mu=0;mus=[]
for r in [np.log(1.1),-.01,-.01]:mu=r/3+2*mu/3;mus.append(mu)
assert min(mus)>0
# Counterexample: concentration fractions virtually equal, yet absolute stress debit differs.
p=pd.read_csv(O/'PAIRED_RESULTS.csv',dtype={'window':str},low_memory=False)
ex=p[p.removed_name.eq('兆威机电')];assert len(ex)==1
report=dict(method='Post-selection algebra and descriptive mechanism audit only. No alternative ranking or rerun.',single_positive_credit_Q=0,positive_credit_with_full_negatives=True,maximum_possible_M=float(1.5*w.max()),mu5_single_jump_then_two_declines=mus,mu5_three_positive_despite_two_negative_returns=True,score_exact_source_inherits_old_scale=True,not_a_raw_day_deletion_counterfactual=True,concentration_counterexample=ex[['removed_M','added_M','removed_dependency_fraction','added_dependency_fraction','removed_Q','added_Q']].to_dict('records'),csv_reading='Explicit window string dtype. Initial ad-hoc preview read of larger result file split2022 into int/string groups; it did not change original sealed selections or evaluated SUMMARY, and is not used for final numbers.')
(O/'MECHANISM_QA.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(pd.DataFrame(rows).query("event_type=='FALSE_TO_TRUE'").to_string(index=False));print(json.dumps(report,ensure_ascii=False,indent=2))
