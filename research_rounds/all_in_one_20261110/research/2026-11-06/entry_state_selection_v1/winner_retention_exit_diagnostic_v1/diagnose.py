from pathlib import Path
import pandas as pd,numpy as np,json,sys,hashlib,time
from decimal import Decimal as D
O=Path(__file__).resolve().parent;R=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on
from sector_account import QuantityRule,FeeComponent,FeeSchedule
SLIP=D('.0005');START=time.monotonic()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
protocol=dict(mechanism='Core-only frozen initial-risk activation, cost floor, first intervention diagnostic. No account or threshold grid.',formula='K0=q0*entry_fill+entry_fee; R0=max(K0-q0*S0*(1-slip)+sell_fee_at_entry(q0,S0*(1-slip)),0); U_t=q0*C_t*(1-slip)-sell_fee_t(q0,C_t*(1-slip))-K0; activate first U_t>=R0; on a later observed held close U_t<=0 request q0 core shares at immediately next common OPEN, original I exit has priority. Original native I remains in force before/after activation, no extra trailing ratchet.',scope='All baseline PVR-selected M3 FALSE_TO_TRUE, closed original 2022 and Sep-Dec2024 cohorts plus 2026H1 semi descriptive. Complete/unknown original paths not silently mixed. One original-core unit only, additive future behavior ends at first intervention.',fees='Independent core liquidation cost. Not original pro-rata layer fee. Same-day core/add exits require one security-level execution and fees; separate calculation is explicitly a conservative layer diagnostic, not entire-round PnL.',execution='Signal close then next common open minus5bp. T+1 and dated sell quantity checked. Original pending add at that next open would be cancelled. Existing add quantity remains under own original contract; no new simulation or mechanical PnL retention after intervention. All historical orderability remains unknown; open-down-near-limit and flat day are warnings, never signal filters.',reentry='Not permanently excluded. After actual exit must use a fresh intent first observed after execution plus existing I/M3/CP, cash/risk/order rules; stale pending buys cannot revive. Diagnostic reports future fresh CP only as opportunity not an assumed fill.',known_history='Historical data already consumed. Protocol fixed before this output, but not OOS/pre-registration.',old_work=['account_comparison_continuous_v1/analysis/one_r_giveback_audit_v1','risk_pyramid_bounded_v1','2026-11-04/task-4/trend_hold_v1'],account_runs=0,threshold_grid=0)
save('PROTOCOL.json',protocol)
bp=R/'entry_protection_migration_mechanism_v1/BASELINE_PATH_DIAGNOSTICS.csv';zp=R/'breadth_pvr3_priority_v1/rounds/ALL_SHADOW_ROUNDS.csv'
base=pd.read_csv(bp,parse_dates=['day','entry_day','exit_day'],dtype={'window':str})
z=pd.read_csv(zp,usecols=['ranking_strategy','event_id','sid','actions'],dtype=str);z=z[z.ranking_strategy.eq('ALL_FEASIBLE_DIAGNOSTIC')]
base=base.merge(z[['event_id','sid','actions']],on=['event_id','sid'],validate='one_to_one')
base=base[base.label.isin(['W','L'])].copy()
sm={x['symbol']:x for x in json.load(open(U/'STOCK_MANIFEST.json'))}
im=json.load(open(U/'INDUSTRY_MANIFEST.json'))
cal=pd.DatetimeIndex(sorted(set().union(*[set(pd.read_parquet(x['refs']['CP1_input']).index) for x in im])))
cal=cal[cal<=pd.Timestamp('2026-06-30')]
rules=json.load(open(B/'inputs-v2/market-rules.json'));proxies=json.load(open(B/'inputs-v2/economic-protocol.json'))['approved_proxy_ids'];names=rules['security_metadata'];meta={}
hashes={str(p):sha(p) for p in [bp,zp,U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json',B/'code/market_rules.py',B/'code/sector_account.py',Path(__file__)]}
def getmeta(sid,d):
 key=(sid,str(d.date()))
 if key not in meta:
  s=key[1];ident=market_identity_on(rules,sid,s,proxies);v=version_on(rules['fee_versions'][ident['venue']],s,proxies)['schedule']
  meta[key]=(QuantityRule(**version_on(rules['quantity_versions'][sid],s,proxies)['rule']),FeeSchedule(v['schedule_id'],tuple(FeeComponent(**x) for x in v['components'])),D(str(names[sid]['par_value'])))
 return meta[key]
def fee(sid,q,price,d):
 _,fs,par=getmeta(sid,d);return sum(fs.incremental('sell',D(q)*price,{}, {},1,shares=q,par_value=par).values(),D(0))
def pnl(sid,q,price,d,K):return D(q)*price-fee(sid,q,price,d)-K
rows=[];casepaths=[]
for j,(sid,g) in enumerate(base.groupby('sid',sort=True)):
 m=sm[sid];sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
 p=pd.read_parquet(sp).reindex(cal);f=pd.read_parquet(m['refs']['facts']).reindex(cal);cp=pd.read_parquet(m['refs']['CP1']).reindex(cal)
 for path in [sp,m['refs']['facts'],m['refs']['CP1']]:hashes[str(path)]=sha(path)
 for _,r in g.iterrows():
  e=cal.get_loc(r.entry_day);x=cal.get_loc(r.exit_day);q=int(r.entry_q);K=D(q)*D(str(r.entry_price))+D(str(r.entry_fee))
  RR=max(D(0),K-D(q)*D(str(r.floor_raw))*(1-SLIP)+fee(sid,q,D(str(r.floor_raw))*(1-SLIP),r.entry_day))
  actions=json.loads(r.actions)
  orig=pnl(sid,q,D(str(r.exit_price)),r.exit_day,K)
  row=dict(event_id=r.event_id,window=r.window,sid=sid,name=r['name'],signal_day=r.day,entry_day=r.entry_day,original_exit_day=r.exit_day,q=q,K=float(K),R0=float(RR),R0_old=float(r.entry_risk),original_core_net=float(orig),original_allocated_core_net=r.core_net,original_round_net=r.net_pnl,original_round_tail30=bool(r.tail30),original_core_tail30=orig/K>=D('.3'),MFE=r.held_close_MFE,giveback10=r.core_net<0 and r.held_close_MFE>=.1,activation_day=None,activation_U=None,activation_I_floor=None,activation_on_entry=False,trigger_day=None,intervention=False,same_as_original=False,core_proxy_net=None,delta_core_proxy=None,post_trigger_original_add_count=0,add_inventory_at_trigger=0,next_open_original_add_cancelled=0,core_sell_lot_valid=None,tplus1_valid=None,open_gap=None,near_limit_down_proxy=None,flat_next_day=None,first_later_CP=None,first_later_CP_nextopen=None,first_later_CP_same_I=None)
  a=None;t=None;daily=[]
  for k in range(e,x):
   d=cal[k];z=p.iloc[k]
   assert z.observed_bar and z.price_eligible and z.volume_eligible and not z.source_invalid and not z.synthetic_event_bar and np.isfinite(z.raw_close)
   v=pnl(sid,q,D(str(z.raw_close))*(1-SLIP),d,K)
   if a is None and v>=RR:
    a=k;row.update(activation_day=d,activation_U=float(v),activation_I_floor=float(f.i_floor.iloc[k]/z.adjustment_factor),activation_on_entry=(k==e))
   if a is not None and k>a and v<=0:
    t=k;row.update(trigger_day=d,trigger_U=float(v),trigger_close=float(z.raw_close),trigger_I_valid=bool(f.i_target.iloc[k]),same_as_original=k==x-1,intervention=k<x-1);break
  if t is not None:
   nd=cal[t+1];zn=p.iloc[t+1];zc=p.iloc[t];px=D(str(zn.raw_open))*(1-SLIP);pv=pnl(sid,q,px,nd,K)
   inv=0
   for act in actions:
    ad=pd.Timestamp(act['day'])
    if ad>cal[t]:continue
    if act['side']=='buy_add':inv+=int(act['q'])
    elif act['side']=='sell_add':inv-=int(act['q'])
   qr,_,_=getmeta(sid,nd);sq=qr.sell_floor(q,q+inv)
   # Warning uses board nominal amplitude only; not a PIT trading limit.
   limit=.3 if sid.endswith('.BJ') else (.2 if sid.startswith(('300','301','688','689')) else .1)
   gap=float(zn.raw_open/zc.raw_close-1)
   row.update(proxy_exit_day=nd,proxy_exit_raw_open=float(zn.raw_open),core_proxy_net=float(pv),delta_core_proxy=float(pv-orig),add_inventory_at_trigger=inv,core_sell_lot_valid=sq==q,tplus1_valid=nd>r.entry_day,core_sell_qty_proxy=sq,open_gap=gap,near_limit_down_proxy=gap<=-limit+.005,flat_next_day=bool(zn.raw_high==zn.raw_low),post_trigger_original_add_count=sum(act['side']=='buy_add' and pd.Timestamp(act['day'])>cal[t] for act in actions),next_open_original_add_cancelled=sum(act['side']=='buy_add' and pd.Timestamp(act['day'])==nd for act in actions),trigger_I_floor=float(f.i_floor.iloc[t]/zc.adjustment_factor))
   later=cp.iloc[t+1:x]
   cc=later.index[later.receipt.fillna(False).astype(bool)]
   if len(cc):
    fc=cc[0];fk=cal.get_loc(fc)
    row.update(first_later_CP=fc,first_later_CP_nextopen=cal[fk+1] if fk+1<len(cal) else None,first_later_CP_same_I=bool(f.i_target.loc[fc]),first_later_CP_close=float(p.raw_close.loc[fc]))
  rows.append(row)
 if (j+1)%200==0:print('DONE_STOCKS',j+1,'SECONDS',round(time.monotonic()-START,2),flush=True)
out=pd.DataFrame(rows);out.to_csv(O/'ALL_CORE_DIAGNOSTICS.csv',index=False)
changed=out[out.intervention].copy();changed.to_csv(O/'FIRST_INTERVENTIONS.csv',index=False)
out[out.giveback10].to_csv(O/'GIVEBACK10_DIAGNOSTICS.csv',index=False)
out[out.original_round_tail30].to_csv(O/'ORIGINAL_ROUND_TAILS.csv',index=False)
summ=[]
for win,g in out.groupby('window'):
 for label,gg in [('all_closed',g),('original_core_loss',g[g.original_allocated_core_net<0]),('giveback10',g[g.giveback10]),('original_round_tail30',g[g.original_round_tail30]),('original_core_tail30',g[g.original_core_tail30])]:
  ch=gg[gg.intervention];up=ch[ch.core_proxy_net>0];dn=ch[ch.delta_core_proxy<0]
  summ.append(dict(window=win,cohort=label,N=len(gg),activated=int(gg.activation_day.notna().sum()),activation_entry_day=int(gg.activation_on_entry.sum()),triggered=int(gg.trigger_day.notna().sum()),same_as_original=int(gg.same_as_original.sum()),new_interventions=len(ch),core_positive_at_cutoff=len(up),core_negative_at_cutoff=int((ch.core_proxy_net<=0).sum()),static_core_delta_sum=ch.delta_core_proxy.sum(),delta_negative_N=len(dn),delta_negative_sum=dn.delta_core_proxy.sum(),original_core_net_sum=gg.original_core_net.sum(),original_core_before_cutoff_sum=ch.original_core_net.sum(),cutoff_core_net_sum=ch.core_proxy_net.sum(),changed_core_positive_to_negative=int(((ch.original_core_net>0)&(ch.core_proxy_net<=0)).sum()),changed_core_negative_to_positive=int(((ch.original_core_net<=0)&(ch.core_proxy_net>0)).sum()),has_existing_add=int((ch.add_inventory_at_trigger>0).sum()),cancel_next_open_add=int((ch.next_open_original_add_cancelled>0).sum()),original_future_add=int((ch.post_trigger_original_add_count>0).sum()),lot_invalid=int(ch.core_sell_lot_valid.eq(False).sum()),t1_invalid=int(ch.tplus1_valid.eq(False).sum()),near_limitdown_warning=int(ch.near_limit_down_proxy.eq(True).sum()),flat_nextday_warning=int(ch.flat_next_day.eq(True).sum()),new_CP_before_original_exit=int(ch.first_later_CP.notna().sum())))
summary=pd.DataFrame(summ);summary.to_csv(O/'SUMMARY.csv',index=False)
qa=dict(closed_rows=len(out),all_R0_matches=float(abs(out.R0-out.R0_old).max()),independent_minus_allocated_max=float(abs(out.original_core_net-out.original_allocated_core_net).max()),independent_loss_count=int((out.original_core_net<0).sum()),source_hashes_match=all(sha(p)==h for p,h in hashes.items()),seconds=time.monotonic()-START,full_account_runs=0)
save('SOURCE_HASHES.json',hashes);save('QA.json',qa)
print('SUMMARY\n'+summary.to_string(index=False));print('QA',json.dumps(qa))
cols=['window','name','sid','signal_day','entry_day','original_exit_day','R0','MFE','original_core_net','original_round_net','activation_day','trigger_day','proxy_exit_day','core_proxy_net','delta_core_proxy','add_inventory_at_trigger','first_later_CP','near_limit_down_proxy']
print('LARGEST_HARMS\n'+changed.nsmallest(12,'delta_core_proxy')[cols].to_string(index=False))
print('LARGEST_IMPROVEMENTS\n'+changed.nlargest(12,'delta_core_proxy')[cols].to_string(index=False))
print('NAMED\n'+out[out.sid.isin(['300085.SZ','000921.SZ','600702.SH','603938.SH','002456.SZ','002583.SZ','003021.SZ'])][[c for c in cols if c in out]].to_string(index=False))

