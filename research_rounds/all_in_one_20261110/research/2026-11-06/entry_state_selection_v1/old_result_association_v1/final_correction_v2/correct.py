from pathlib import Path
import pandas as pd,json,hashlib
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');P=R/'old_result_association_v1';D=P/'final_correction_v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,o):(D/n).write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False))
sources=[P/'ALL_ASSOCIATED_ROUNDS.csv',P/'FROZEN_GATE_KEYS.json',P/'OUTPUT_HASHES.json']+[R/f'independent_channel_joint_economic_v1/economic_{y}/COMPARISON_REPORT_RECOVERED.json' for y in [2022,2024]]
h={str(p):sha(p) for p in sources};save('SOURCE_HASHES_BEFORE.json',h)
protocol='''# Final correction protocol\nAppend-only correction. Retain initial and coverage_v1 artifacts unchanged. Exact original report round_coverage arm=joint,lane=PRICE supplies financial coverage. Original report core_independent_dated_fee_diagnostics supplies independent CORE with EACH_ACTUAL_CORE_FILL_INDEPENDENT_DATED_FEE. The audit verified original report_adapter derives PROBE actual-fill independent dated fees and recognized core cash income; no fee recalculation or economics here. Initial claim CORE unavailable was incorrect because the report nested diagnostics were overlooked, not absent. Unknown financial coverage is never a known total even if conditional closed net is saved. Keep every gate identity unchanged; independent CORE not allocated PROBE_realized. Static original-path associations cannot support OR reject the dynamic gate, whose later generation/reentry and costs are not tested here. No promotion/nonpromotion conclusion is drawn; any earlier phrasing implying a decision is superseded.\n'''
(D/'PROTOCOL.md').write_text(protocol)
x=pd.read_csv(P/'ALL_ASSOCIATED_ROUNDS.csv',low_memory=False);cs=[];ks=[]
for p in sources[3:]:
 j=json.loads(p.read_text());cs+=j['round_coverage'];ks+=j['core_independent_dated_fee_diagnostics']
c=pd.DataFrame(cs);c=c[c.arm.eq('joint')&c.lane.eq('PRICE')];k=pd.DataFrame(ks);k=k[k.arm.eq('joint')&k.lane.eq('PRICE')]
assert len(c)==len(k)==3621 and k.fee_basis.eq('EACH_ACTUAL_CORE_FILL_INDEPENDENT_DATED_FEE').all()
x=x.merge(c[['round_id','financial_covered','reason']],on='round_id',validate='one_to_one',how='left').merge(k[['round_id','closed_net','independent_dated_fees','core_registered_net80','fee_basis']],on='round_id',validate='one_to_one',how='left');assert x.financial_covered.notna().all()
x['original_saved_FULL_closed_net']=x.old_FULL_net;x['financial_FULL_known']=x.known_old_full&x.financial_covered;x['financial_CORE_known']=x.actual_buy&x.closed_net.notna()&x.financial_covered&x.known_old_full;x['financial_FULL_net']=x.old_FULL_net.where(x.financial_FULL_known);x['financial_CORE_net']=x.closed_net.where(x.financial_CORE_known);x['closed_but_uncovered']=x.known_old_full&~x.financial_covered
assert list(x[x.closed_but_uncovered].groupby('window').size())==[30,14];assert x.loc[x.common&x.actual_buy,'financial_FULL_known'].all();assert x.loc[x.common&x.actual_buy,'financial_CORE_known'].all()
x.to_csv(D/'ALL_FULL_CORE_ASSOCIATIONS.csv',index=False);x[x.closed_but_uncovered].to_csv(D/'CLOSED_BUT_FINANCIALLY_UNCOVERED.csv',index=False);x[x.common&x.actual_buy&x.gate_group.eq('DENY')].to_csv(D/'COMMON_167_DENY_FULL_CORE.csv',index=False)
def stats(z,role):
 known=z[f'financial_{role}_known'];v=z.loc[known,f'financial_{role}_net'];fee='fees' if role=='FULL' else 'independent_dated_fees'
 return dict(registered=len(z),actual_proxy_buy=int(z.actual_buy.sum()),known=int(known.sum()),UNKNOWN_buy=int((z.actual_buy&~known).sum()),no_buy=int((~z.actual_buy).sum()),closed_but_uncovered=int(z.closed_but_uncovered.sum()),old_net=float(v.sum()) if len(v) else None,winners=int((v>0).sum()),losers=int((v<0).sum()),zeros=int((v==0).sum()),gross_winning_net_sum=float(v[v>0].sum()) if len(v) else None,gross_losing_net_sum=float(v[v<0].sum()) if len(v) else None,included_known_fees=float(z.loc[known,fee].sum()) if len(v) else None)
s=[];st=[]
for w,t in x.groupby('window'):
 for scope,u in [('ALL',t),('COMMON',t[t.common])]:
  for gate,z in [('TOTAL',u)]+list(u.groupby('gate_group')):
   for role in ['FULL','CORE']:
    s.append(dict(window=w,scope=scope,gate=gate,role=role,**stats(z,role)))
    for sid,a in z.groupby('sid'):st.append(dict(window=w,scope=scope,gate=gate,role=role,sid=sid,**stats(a,role)))
pd.DataFrame(s).to_csv(D/'SUMMARY.csv',index=False);save('SUMMARY.json',s);pd.DataFrame(st).to_csv(D/'PER_STOCK_RESULTS.csv',index=False)
# Preserve original case identities. Add both financially covered outcomes and UNKNOWN status; no case/exemption changes.
cases=pd.read_csv(P/'TOP_CASES.csv');cases=cases.merge(x[['round_id','financial_covered','financial_FULL_net','financial_CORE_net','independent_dated_fees']],on='round_id',how='left',validate='many_to_one');cases.to_csv(D/'ORIGINAL_CASES_WITH_FULL_CORE.csv',index=False)
assert h=={str(p):sha(p) for p in sources};old=json.loads((P/'OUTPUT_HASHES.json').read_text());assert all(sha(P/n)==v for n,v in old.items());old1=json.loads((P/'coverage_supplement_v1/OUTPUT_HASHES.json').read_text());assert all(sha(P/'coverage_supplement_v1'/n)==v for n,v in old1.items())
save('QA.json',dict(original_and_v1_artifacts_unchanged=True,sources_unchanged=True,exact_all3621_join=True,common167_preserved=True,source_CORE_fee_basis_verified=True,economic_runs=0,fee_recalculations=0,gate_changes=0));save('SOURCE_HASHES_AFTER.json',h)
lines=['# Corrected original-path FULL and independent CORE associations','This is the controlling financial-coverage and CORE clarification; initial artifacts remain intact for audit.','Initial known_old_full meant saved conditional closed-net, not financially covered FULL. Financially uncovered closed rounds: 2022 30, 2024 14. Total financial FULL/CORE for them is UNKNOWN. COMMON167 is unchanged.','Correction: initial CORE unavailable claim was wrong. Original COMPARISON_REPORT_RECOVERED.json already contains independently dated-fee initial-layer CORE. We join these saved values only, not allocated PROBE_realized; no calculation of a new economic path.','Static positive/negative associations cannot support or reject the gate. Later entry-generation rebirth, participation and opportunity costs require separately authorized dynamic evaluation. Any earlier wording implying promotion/nonpromotion is superseded.','Source model remains static NON-PIT conditional next-common OPEN full-fill proxy. Real ACK/fill unknown; no-buy is not zero-fill. No new gate, threshold, exception or formula change.','mtime note: earlier audit observed a file during final report generation; current initial OUTPUT_HASHES matches all files. This correction does not overwrite any earlier artifact.','']
for z in s:lines.append(str(z))
lines+=['','See ../READOUT.md and original tables for complete cases, same-stock old rounds, receipt generation overlap and left-boundary strata; financial amounts and CORE availability use this correction.']
(D/'READOUT.md').write_text('\n'.join(lines)+'\n');save('OUTPUT_HASHES.json',{p.name:sha(p) for p in D.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'});print(pd.DataFrame(s).query("gate == 'DENY'").to_string(index=False))
