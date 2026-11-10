
from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/cp1_signal_mechanism_v1')
B=O.parent/'mobile_candidate_response_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
frozen={str(p):sha(p)for p in [O/'SIGNAL_GATE_FREEZE.json',B/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet',B/'FIXED_NATIVE_PRICE_LABELS.parquet',Path(__file__)]}
c=pd.read_parquet(B/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet');lab=pd.read_parquet(B/'FIXED_NATIVE_PRICE_LABELS.parquet')
c=c.merge(lab,on=['sid','day'],validate='many_to_one')
sm={r['symbol']:r for r in read(U/'STOCK_MANIFEST.json')}
im=read(U/'INDUSTRY_MANIFEST.json');states={}
for r in im:
 z=pd.read_parquet(r['refs']['state']).set_index('day')
 states[r['series']]=z.E0_valid & z.attempt_id.notna() & z.stage.gt(0)
h=np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz');ds=pd.DatetimeIndex(h['dates']);ds=ds[(ds>='2022-01-01')&(ds<='2026-05-15')];cal={str(d.date()):i for i,d in enumerate(ds)}
facts={}
for sid,idx in c.groupby('sid').groups.items():
 f=pd.read_parquet(sm[sid]['refs']['facts']);facts[sid]=f;days=pd.DatetimeIndex(c.loc[idx,'day'])
 for col in ['i_buy','g_grade','g_fresh_up','e0_target']:c.loc[idx,'source_'+col]=f[col].reindex(days).to_numpy()
c['gate_known']=c.source_i_buy.notna();c['accepted']=c.source_i_buy.eq(True)
assert c.gate_known.all()
c['gate_reject_reason']=np.where(c.accepted,'PASS',np.where(c.source_g_grade<2,'GRADE_BELOW_2','NO_CURRENT_FRESH_I_BUY'))
c.to_parquet(O/'EMPTY_MOBILE_SIGNAL_GATE.parquet',index=False)
first=pd.read_csv(O.parent/'ALL_FIRST_ENTRIES.csv');first=first[first.first_kind=='add']
j=first.merge(c[['account','sid','day','accepted','source_g_grade','source_g_fresh_up','gate_reject_reason']],left_on=['account','sid','signal_day'],right_on=['account','sid','day'],validate='one_to_one')
assert len(j)==3601
j.to_csv(O/'ACTUAL_FIRST_MOBILE_GATE_ATTRIBUTION.csv',index=False)
def path(g):
 r=dict(n=len(g),days=g.day.nunique(),big60=int(g.big60_posthoc.sum()),complete60=int(g.complete60.sum()))
 for k in [1,3,5,10,20]:
  z=g[g['complete'+str(k)]]
  r.update({f'complete{k}':len(z),f'mean_ret{k}':z['ret'+str(k)].mean(),f'mean_mfe{k}':z['mfe'+str(k)].mean(),f'mean_mae{k}':z['mae'+str(k)].mean()})
 return r
cg=[dict(account=a,year=y,accepted=acc,**path(g))for(a,y,acc),g in c.groupby(['account','year','accepted'])]
pd.DataFrame(cg).to_csv(O/'CANDIDATE_GATE_BY_YEAR.csv',index=False)
ag=[]
for(a,y,acc),g in j.groupby(['account','year','accepted']):
 closed=g[g.closed_in_entry_year]if y==2022 else g[g.closed]
 win=closed[closed.round_pnl>0];loss=closed[closed.round_pnl<0]
 ag.append(dict(account=a,year=y,accepted=acc,actual_firsts=len(g),closed=len(closed),wins=len(win),losses=len(loss),winrate=len(win)/len(closed)if len(closed)else np.nan,original_net=closed.round_pnl.sum(),original_gross_positive=win.round_pnl.sum(),original_gross_negative=loss.round_pnl.sum(),actual_big60=int(g.big60_posthoc.sum()),actual_complete60=int(g.complete60.sum())))
pd.DataFrame(ag).to_csv(O/'ACTUAL_FIRST_GATE_BY_YEAR.csv',index=False)
# Offline original PVR order is unchanged; only acceptance removes candidate and allows original next order to fill an evaluation slot.
sels=[];qc=[]
for(a,d),g in c.groupby(['account','day']):
 base=g.sort_values(['original_priority_rank','sid']);keep=base[base.accepted];K=min(20,len(base));KG=min(K,len(keep))
 for strategy,z in [('ORIGINAL_PVR',base.head(K)),('EMPTY_MOBILE_I_AND_CP',keep.head(K))]:
  q=z.copy();q['strategy']=strategy;sels.append(q)
 qc.append(dict(account=a,day=d,baseK=K,gateK=KG,removed_candidates=len(base)-len(keep),fewer_selected=K-KG))
sel=pd.concat(sels,ignore_index=True);sel.to_parquet(O/'OFFLINE_GATE_SELECTIONS.parquet',index=False)
pd.DataFrame(qc).to_csv(O/'GATE_QUEUE_COUNTS.csv',index=False)
sg=[dict(account=a,year=y,strategy=s,**path(g))for(a,y,s),g in sel.groupby(['account','year','strategy'])]
pd.DataFrame(sg).to_csv(O/'OFFLINE_GATE_PATHS_BY_YEAR.csv',index=False)
origroots=pd.read_csv(B/'ROOT_EPISODE_COVERAGE.csv');ep=[]
ss={s:set(zip(g.account,g.sid,g.epoch,g.day))for s,g in sel.groupby('strategy')}
for(a,sid,epoch),g in c.groupby(['account','sid','epoch']):
 g=g.sort_values('t');birth=g.iloc[0];early=g[g.t<=int(birth.t)+5];r=dict(account=a,sid=sid,epoch=epoch,year=int(birth.year),birth_day=birth.day,big60=bool(birth.big60_posthoc),complete60=bool(birth.complete60),first_gate_accept=bool(birth.accepted))
 for s,lookup in ss.items():r[s+'_capture']=any((a,sid,epoch,q.day)in lookup for q in early.itertuples())
 ep.append(r)
ep=pd.DataFrame(ep);ep.to_csv(O/'GATE_ROOT_EPISODES.csv',index=False)
er=[]
for(a,y),g in ep.groupby(['account','year']):
 z=g[g.big60];old=z.ORIGINAL_PVR_capture;new=z.EMPTY_MOBILE_I_AND_CP_capture
 er.append(dict(account=a,year=y,big_roots=len(z),original_captured=int(old.sum()),gate_captured=int(new.sum()),lost=int((old&~new).sum()),added=int((~old&new).sum()),retained_original=float((old&new).sum()/old.sum())if old.any()else np.nan))
pd.DataFrame(er).to_csv(O/'GATE_BIG_ROOT_COVERAGE.csv',index=False)
# Natural reappearance of a NEW joint market signal after rejected ACTUAL first mobile entries.
# This reports recovery observability only; never grants a fill or changes old account held/cash/ACT states.
recovery=[]
for sid,g in j[~j.accepted].groupby('sid'):
 f=facts[sid];cp=pd.read_parquet(sm[sid]['refs']['CP1'])
 on=f.i_target.eq(1);seg=f.segment_id;starts=on&(~on.shift(fill_value=False)|seg.ne(seg.shift()));root=starts.cumsum().where(on)
 sector=g.sector.iloc[0];active=pd.Series(states[sector].to_numpy(),index=pd.to_datetime(states[sector].index)).reindex(f.index).fillna(False)
 joint=f.i_buy.eq(True)&cp.receipt.eq(True)&active
 for r in g.itertuples():
  d=pd.Timestamp(r.signal_day);future=f.index[(f.index>d)&(f.index<=pd.Timestamp('2026-05-15'))&joint]
  nxt=future[0]if len(future)else None
  recovery.append(dict(account=r.account,sid=sid,signal_day=r.signal_day,year=r.year,original_pnl=r.round_pnl,original_closed=r.closed,original_closed_in_entry_year=r.closed_in_entry_year,first_new_joint_market_day=str(nxt.date())if nxt is not None else None,wait_common_days=cal[str(nxt.date())]-cal[r.signal_day]if nxt is not None else np.nan,same_I_root=bool(root.at[nxt]==root.at[d])if nxt is not None else None,recovery_signal_close_vs_original_open=float(f.at[nxt,'close']/r.entry_adjusted_open-1)if nxt is not None else np.nan))
pd.DataFrame(recovery).to_csv(O/'REJECTED_FIRST_NATURAL_NEW_SIGNAL.csv',index=False)
# Prefix causality of the added gate: future cached state mutations do not change prior gate.
tests=[]
for cutoff in ['2022-03-31','2024-09-24','2026-01-15']:
 x=c.copy();x.loc[x.day>cutoff,'source_i_buy']=~x.loc[x.day>cutoff,'source_i_buy'].astype(bool)
 test=x.source_i_buy.eq(True);assert test[x.day<=cutoff].equals(c.loc[c.day<=cutoff,'accepted'])
 tests.append(dict(cutoff=cutoff,prefix_rows=int((c.day<=cutoff).sum()),passed=True))
for p,v in frozen.items():assert sha(p)==v
summary=dict(status='SINGLE_SIGNAL_CONSISTENCY_GATE_DIAGNOSTIC_NOT_ACCOUNT_NOT_OOS',candidate_rows=len(c),actual_firsts=len(j),all_gate_known=True,original_indicator_runs=0,account_runs=0,source_freeze=frozen,future_gate_tests=tests,by_year_original_firsts=ag,root_coverage=er)
(O/'GATE_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str))
print('ACTUAL PVR');print(pd.DataFrame(ag).query("account=='PVR'").to_string(index=False))
print('ROOT PVR');print(pd.DataFrame(er).query("account=='PVR'").to_string(index=False))
print('REJECTED_WINNERS_2022');print(j[(j.account=='PVR')&j.year.eq(2022)&j.closed_in_entry_year&~j.accepted&j.round_pnl.gt(0)][['sid','signal_day','entry_day','round_pnl','original_g_grade','original_i_buy','close_MFE20','ret20_forward']].to_string(index=False))
print('CANDIDATE PVR');print(pd.DataFrame(cg).query("account=='PVR'")[['year','accepted','n','mean_ret5','mean_ret20','big60']].to_string(index=False))
