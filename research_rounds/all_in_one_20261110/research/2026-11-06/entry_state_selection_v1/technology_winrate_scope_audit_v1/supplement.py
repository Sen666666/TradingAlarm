from pathlib import Path
import pandas as pd,json,hashlib
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=Path(__file__).resolve().parent;hs={}
def read(p,csv=False):
 hs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return pd.read_csv(p,low_memory=False) if csv else json.loads(p.read_text())
old=pd.read_csv(O/'OLD_TECH_A_2024_FALL_ENTRIES.csv');e=read(R/'shared_ab_entry_selection_attribution_v1/ALL_EVENT_FUNNEL.csv',True);out=[]
for x in old.to_dict('records'):
 z=e[e.sid==x['symbol']];ds=x['decision_at'][:10]
 out.append(dict(sid=x['symbol'],name=x['name'],old_signal_day=ds,old_entry_day=x['entry_at'][:10],old_exit_day=x['exit_at'][:10],old_actual_net=x['net_pnl'],new_same_signal_day_event_count=int(z.day.str.startswith(ds).sum()),new_actual_fills=int(z.filled.sum()),new_event_history=z[['day','event_type','PVR_score','decision','status']].where(pd.notna(z),None).to_dict('records'),warning='Old money is not an achievable profit credit in the new account'))
assert all(x['new_same_signal_day_event_count']==0 and x['new_actual_fills']==0 for x in out)
(O/'OLD_8_VS_CURRENT_EVENT_CHAINS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str))
hp=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/rb1-act-history-pressure-2019-2023-20261031');h=read(hp/'ALL_CYCLES.csv',True);z=h[(h.sector=='TECH')&(h.model=='A')&(h.pressure=='base')];cl=z[z.closed];assert len(cl)==136 and (cl.net_pnl>0).sum()==41 and len(z)-len(cl)==6;z.to_csv(O/'OLD_TECH_A_HISTORY_2019_2023.csv',index=False)
summary=read(hp/'SUMMARY.json');rr=next(x for x in summary['matrix'] if x['sector']=='TECH' and x['model']=='A' and x['pressure']=='base');(O/'OLD_TECH_A_HISTORY_SUMMARY.json').write_text(json.dumps(rr,ensure_ascii=False,indent=2))
p=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-local-finite-capital-20261029/baseline/accounts-v2/I__S0_base.json');obj=read(p);fills=[x for x in obj['fills'] if x['security_id'] in ['688498.SH','688048.SH']];assert all(x['at'].startswith('2025-10-21') for x in fills if x['side']=='buy');(O/'OLD_TECH_TWO_MAJOR_WINNER_FILLS.json').write_text(json.dumps(fills,ensure_ascii=False,indent=2));(O/'SUPPLEMENT_SOURCE_HASHES.json').write_text(json.dumps(hs,ensure_ascii=False,indent=2));print('old_8_no_same_date_event_verified',len(out),'history',len(cl),int((cl.net_pnl>0).sum()),len(z)-len(cl))
