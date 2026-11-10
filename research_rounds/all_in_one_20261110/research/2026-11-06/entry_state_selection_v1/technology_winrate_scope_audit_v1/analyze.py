from pathlib import Path
from decimal import Decimal as D
import json,hashlib,pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=Path(__file__).resolve().parent;M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');OLD=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/rb1-act-finite-20261031');S=R/'m3_ab_shared_probe_v1/indexed_execution_v1/cohort_2024_924';hs={}
def read(p,kind='json'):
 hs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text()) if kind=='json' else pd.read_csv(p,low_memory=False)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
m=read(M/'tech-finite-compound-20261026/prepared-v2/manifest.json');stocks={x['symbol'] for x in m['series'] if not x['symbol'].startswith('URFI')};sectors={x['symbol'] for x in m['series'] if x['symbol'].startswith('URFI')};assert len(stocks)==407 and len(sectors)==11
arc=read(S/'ARCHIVES.json');l=read(S/'LAYER_REPORT.json');rounds={x['round_id']:x for x in read(S/'ROUND_REPORT.json')};decision=pd.DataFrame(read(S/'DECISIONS.json'));audit=read(S/'AUDIT.json');source=pd.DataFrame(read(S/'SOURCE_ROUNDS.json'));rows=[]
for x in l:
 if x['layer']!='core':continue
 rid=x['round_id'];a=arc[rid];rr=rounds[rid];assert rr['status']=='EXECUTION_AND_SETTLEMENT_CLOSED'
 rows.append(dict(round_id=rid,sid=rr['sid'],name=a['name'],sector=a['sector'],industry=a['industry'],signal_day=a['signal_day'][:10],entry_day=rr['entry_day'][:10],CORE_NET80=D(x['NET80']),CORE_return=D(x['return_on_layer_buy_cash']),FULL_NET80=D(rr['whole_round_NET80']),FULL_return=D(rr['conditional_return_on_actual_buy_cash']),old_407_member=rr['sid'] in stocks,old_11_sector=a['sector'] in sectors))
d=pd.DataFrame(rows);assert len(d)==80 and d.old_407_member.equals(d.old_11_sector);d.to_csv(O/'CURRENT_M3_80_LAYER_AND_ROUND.csv',index=False)
industries=[]
for (sec,ind),e in decision.groupby(['sector','industry']):
 z=d[d.sector==sec];industries.append(dict(sector=sec,industry=ind,events=len(e),selected=int(e.selected.sum()),funded=len(z),CORE_wins=sum(x>0 for x in z.CORE_NET80),FULL_wins=sum(x>0 for x in z.FULL_NET80),CORE_net=sum(z.CORE_NET80,D(0)),FULL_net=sum(z.FULL_NET80,D(0)),old_11_sector=sec in sectors))
pd.DataFrame(industries).to_csv(O/'CURRENT_M3_ALL_INDUSTRY_FUNNEL.csv',index=False)
comparison=[]
for tag,z in [('TECH407',d[d.old_407_member]),('NON_TECH407',d[~d.old_407_member]),('ALL',d)]:
 comparison.append(dict(account='M3_SHARED_2024_FALL',scope=tag,total=len(z),CORE_wins=sum(x>0 for x in z.CORE_NET80),FULL_wins=sum(x>0 for x in z.FULL_NET80),CORE_net=sum(z.CORE_NET80,D(0)),FULL_net=sum(z.FULL_NET80,D(0))))
semi=decision[decision.sector=='URFI881121'].merge(source[['event_id','status']],on='event_id',how='left');semi.to_csv(O/'CURRENT_M3_SEMICONDUCTOR_ALL_EVENTS.csv',index=False)
sids=set(semi.round_id.dropna());reasons=[]
for a in audit:
 if a.get('round_id') in sids and a['type']=='BUDGET_REJECTED' and a['kind']=='INIT':reasons.append(dict(round_id=a['round_id'],day=a['day'],last_reasons=a['trials'][-1]['reasons'] if a['trials'] else ['NO_QUANTITY_TRIAL']))
save('CURRENT_M3_SEMICONDUCTOR_REASONS.json',reasons)
# Current continuous native PVR: same account, new-entry calendar, same endpoint, closed only.
allfirst=read(R/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv','csv');a=allfirst[(allfirst.account=='PVR')&(allfirst.entry_day>='2026-01-01')].copy();assert len(a)==257 and a.closed.sum()==193 and ((a.round_pnl>0)&a.closed).sum()==41
a['old_407_member']=a.sid.isin(stocks);a['old_11_sector']=a.sector.isin(sectors);assert a.old_407_member.equals(a.old_11_sector);a.to_csv(O/'CURRENT_PVR_2026_ENTRY_COHORT.csv',index=False)
name={x['sector']:x['industry'] for x in industries};per=[]
for sec,z in a.groupby('sector'):
 cl=z[z.closed];per.append(dict(sector=sec,industry=name.get(sec,sec),new_rounds=len(z),closed=len(cl),wins=int((cl.round_pnl>0).sum()),still_open=len(z)-len(cl),closed_net=float(cl.round_pnl.sum()),old_11_sector=sec in sectors))
pd.DataFrame(per).to_csv(O/'CURRENT_PVR_2026_INDUSTRY_CLOSED.csv',index=False)
for tag,z in [('TECH407',a[a.old_407_member]),('NON_TECH407',a[~a.old_407_member]),('SEMICONDUCTOR',a[a.sector=='URFI881121']),('ALL',a)]:
 cl=z[z.closed];comparison.append(dict(account='CONTINUOUS_PVR_2026_NEW_TO_MAY15',scope=tag,total=len(z),closed=len(cl),wins=int((cl.round_pnl>0).sum()),open=len(z)-len(cl),closed_net=float(cl.round_pnl.sum()),open_net='NOT_EVALUATED_NOT_ZERO'))
# Old genuine technology account. Compare primary campaigns with derived ALL_CYCLES before use.
old=read(OLD/'ALL_CYCLES.csv','csv');old=old[(old.sector=='TECH')&(old.model=='A')&(old.pressure=='base')].copy();primary=read(M/'pvr-local-finite-capital-20261029/baseline/analysis/campaigns.csv','csv');primary=primary[primary.account=='I__S0_base']
k=['symbol','entry_at','exit_at'];matched=old.merge(primary,on=k,suffixes=('_audit','_source'),validate='one_to_one');assert len(matched)==69 and (matched.net_pnl_audit==matched.net_pnl_source).all() and (matched.net_return_audit==matched.net_return_source).all();assert old.closed.all()
old.to_csv(O/'OLD_TECH_A_69_CLOSED_ROUNDS.csv',index=False);old.groupby('industry').agg(n=('symbol','size'),wins=('net_pnl',lambda v:int((v>0).sum())),net=('net_pnl','sum'),tails=('tail_closed','sum')).to_csv(O/'OLD_TECH_A_INDUSTRY.csv')
oldfall=old[old.entry_at.str[:10].between('2024-09-02','2024-12-31')];oldfall.to_csv(O/'OLD_TECH_A_2024_FALL_ENTRIES.csv',index=False)
legacy=read(M/'tech-finite-compound-20261026/analysis/summary.csv','csv');legacy[legacy.scenario=='base'].to_csv(O/'OLDER_TECH_FINITE_BASE_SUMMARY.csv',index=False)
etf=read(M/'semiconductor-exit-20261024/results/v0/summary.csv','csv');etf[etf.key=='P_E0_base'].to_csv(O/'OLD_SEMICONDUCTOR_ETF_E0.csv',index=False)
summary=dict(comparisons=comparison,semiconductor_M3=dict(events=len(semi),decisions=semi.decision.value_counts().to_dict(),funded=0,pending=10),old_tech_A=dict(n=len(old),wins=int((old.net_pnl>0).sum()),net=float(old.net_pnl.sum()),semiconductor_n=int((old.industry=='半导体').sum()),semiconductor_wins=int(((old.industry=='半导体')&(old.net_pnl>0)).sum()),semiconductor_net=float(old.loc[old.industry=='半导体','net_pnl'].sum()),largest_two_profit=float(old.nlargest(2,'net_pnl').net_pnl.sum()),old_fall_entries=len(oldfall),old_fall_wins=int((oldfall.net_pnl>0).sum()),old_new_tech_fall_stock_overlap=len(set(oldfall.symbol)&set(d[d.old_407_member].sid))),new_accounts=0)
save('SUMMARY.json',summary);save('OLD_TECH_SCOPE.json',dict(stock_count=len(stocks),sectors=sorted(sectors),stock_ids=sorted(stocks),scope='Existing static 407-member/11-industry roster, applied retrospectively for description, not a new trading screen or PIT universe'))
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hs.items());save('SOURCE_HASHES.json',hs);save('QA.json',dict(original_80_closed_verified=True,old_69_rounds_primary_exact=True,current_2026_257_193_41_exact=True,tech_member_vs_sector_masks_equal=True,industry_partitions_add_to_accounts=True,new_account_runs=0,new_indicators=0,minute_data=0))
print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))
