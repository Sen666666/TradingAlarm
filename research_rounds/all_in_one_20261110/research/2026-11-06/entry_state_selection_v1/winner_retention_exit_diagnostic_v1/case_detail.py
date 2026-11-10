from pathlib import Path
import pandas as pd,numpy as np,json,sys,hashlib
from decimal import Decimal as D
O=Path(__file__).resolve().parent;R=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on
from sector_account import QuantityRule,FeeComponent,FeeSchedule
d=pd.read_csv(O/'ALL_CORE_DIAGNOSTICS.csv',parse_dates=['entry_day','signal_day','original_exit_day','activation_day','trigger_day','proxy_exit_day','first_later_CP'])
sm={x['symbol']:x for x in json.load(open(U/'STOCK_MANIFEST.json'))}
im=json.load(open(U/'INDUSTRY_MANIFEST.json'))
cal=pd.DatetimeIndex(sorted(set().union(*[set(pd.read_parquet(x['refs']['CP1_input']).index) for x in im])))
cal=cal[cal<=pd.Timestamp('2026-06-30')]
rules=json.load(open(B/'inputs-v2/market-rules.json'));proxies=json.load(open(B/'inputs-v2/economic-protocol.json'))['approved_proxy_ids'];names=rules['security_metadata'];meta={}
def getmeta(sid,day):
 key=(sid,str(day.date()))
 if key not in meta:
  s=key[1];ident=market_identity_on(rules,sid,s,proxies);v=version_on(rules['fee_versions'][ident['venue']],s,proxies)['schedule']
  meta[key]=(QuantityRule(**version_on(rules['quantity_versions'][sid],s,proxies)['rule']),FeeSchedule(v['schedule_id'],tuple(FeeComponent(**x) for x in v['components'])),D(str(names[sid]['par_value'])))
 return meta[key]
def fee(sid,q,price,day):
 _,fs,par=getmeta(sid,day);return sum(fs.incremental('sell',D(q)*price,{}, {},1,shares=q,par_value=par).values(),D(0))
def pnl(sid,q,raw,day,K):
 p=D(str(raw))*D('.9995');return float(D(q)*p-fee(sid,q,p,day)-D(str(K)))
def be(sid,q,day,K):
 lo=0.;hi=float(K/q)*1.1+10
 for _ in range(70):
  mi=(lo+hi)/2
  if pnl(sid,q,mi,day,K)>0:hi=mi
  else:lo=mi
 return (lo+hi)/2
specified=[('603938.SH','2022-03-21'),('600702.SH','2024-11-05'),('300085.SZ','2024-09-12'),('003021.SZ','2024-10-22'),('003021.SZ','2024-12-03'),('002603.SZ','2022-03-31'),('000921.SZ','2022-11-03'),('300657.SZ','2022-06-27')]
choose=d[d.original_round_tail30 & d.intervention].copy()
choose=pd.concat([choose,*[d[d.sid.eq(sid)&d.signal_day.eq(day)] for sid,day in specified]]).drop_duplicates(['event_id','sid'])
rows=[];case_summary=[]
panel=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet')
case_summary=[]
for _,r in choose.iterrows():
 sid=r.sid;q=int(r.q);m=sm[sid];p=pd.read_parquet(next(x for x in m['source_sha256'] if x.endswith('/signal.parquet'))).reindex(cal);f=pd.read_parquet(m['refs']['facts']).reindex(cal);cp=pd.read_parquet(m['refs']['CP1']).reindex(cal);e=cal.get_loc(r.entry_day);x=cal.get_loc(r.original_exit_day)
 row=r.to_dict()
 for k in range(e,x+1):
  dt=cal[k];zz=p.iloc[k];fr=f.iloc[k];cr=cp.iloc[k]
  phase='ORIGINAL_HELD'
  if dt==r.entry_day:phase='ENTRY'
  if dt==r.activation_day:phase+='|ACTIVATE'
  if dt==r.trigger_day:phase+='|NEW_EXIT_SIGNAL'
  if dt==r.proxy_exit_day:phase+='|NEW_EXIT_OPEN'
  if dt==r.first_later_CP:phase+='|LATER_CP'
  if dt==r.original_exit_day:phase='ORIGINAL_EXIT_OPEN_CLOSE_NOT_HELD'
  rows.append(dict(event_id=r.event_id,sid=sid,name=r['name'],day=dt,phase=phase,raw_open=zz.raw_open,raw_high=zz.raw_high,raw_low=zz.raw_low,raw_close=zz.raw_close,core_net_at_close=pnl(sid,q,zz.raw_close,dt,r.K),cost_floor_raw=be(sid,q,dt,r.K),R0=r.R0,I_target=fr.i_target,I_floor=fr.i_floor/zz.adjustment_factor,CP_receipt=cr.receipt,CP_candidate=cr.candidate/zz.adjustment_factor))
 if pd.notna(r.trigger_day):row['cost_floor_at_trigger']=be(sid,q,r.trigger_day,r.K)
 if pd.notna(r.first_later_CP):
  dt=r.first_later_CP;ix=cal.get_loc(dt);xx=p.iloc[ix+1];sec=r.event_id.split('|')[-1];ss=panel[panel.sector.eq(sec)&panel.day.eq(dt)]
  floor=max(f.i_floor.loc[dt],cp.candidate.loc[dt])/p.adjustment_factor.loc[dt]
  row.update(reentry_evidence_M3=int(ss.M3_candidate.iloc[0]) if len(ss) else None,reentry_evidence_CP_floor=floor,reentry_evidence_nextopen=xx.raw_open,reentry_evidence_nextopen_above_floor=bool(xx.raw_open>floor),reentry_evidence_not_an_order=True)
 case_summary.append(row)
pd.DataFrame(rows).to_csv(O/'CASE_DAILY.csv',index=False);pd.DataFrame(case_summary).to_csv(O/'CASE_SUMMARY.csv',index=False)
extra={str(Path(__file__)):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
for a in im:
 p=Path(a['refs']['CP1_input']);extra[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
p=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet';extra[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
(O/'SUPPLEMENT_CURRENT_SOURCE_HASHES.json').write_text(json.dumps(dict(note='Current capture after primary result; not a retrospective pre-outcome seal. Calendar sources were not separately hashed in the primary file.',hashes=extra),indent=2))
cols=['name','signal_day','q','K','R0','activation_day','activation_U','activation_I_floor','trigger_day','cost_floor_at_trigger','trigger_close','trigger_U','proxy_exit_day','proxy_exit_raw_open','core_proxy_net','original_exit_day','original_core_net','first_later_CP','reentry_evidence_M3','reentry_evidence_nextopen','reentry_evidence_CP_floor','reentry_evidence_nextopen_above_floor']
print(pd.DataFrame(case_summary)[cols].to_string(index=False))

