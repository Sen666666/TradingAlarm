"""Existing event/fact inspection only. No indicators, policies, or orders run."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
from datetime import datetime,timezone
import json,csv,gzip,hashlib,time,math,importlib.util
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O.parent;RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');PRIOR=W/'partial-action-ledger-attribution-20261030';Z=D(0);START=time.monotonic()
def read(p):return json.loads(Path(p).read_text())
def cr(p):
 with Path(p).open() as f:return list(csv.DictReader(f))
def gz(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False))
def clean(x):
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(D,Path,pd.Timestamp)):return str(x)
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
 return x

def write(n,rs):
 if not rs:return
 rs=[clean(r) for r in rs]
 with (O/n).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rs for k in r)));w.writeheader();w.writerows(rs)
sp=importlib.util.spec_from_file_location('restore_review_arithmetic',RR/'pv-strength-b5-20261025/code/arithmetic.py');AR=importlib.util.module_from_spec(sp);sp.loader.exec_module(AR)
def cmp(a,b):
 return None if a is None or b is None or not np.isfinite(float(a)) or not np.isfinite(float(b)) else AR.compare(float(a),float(b))
PROOF=read(RR/'ph1-cross-sector-20261028/event-validation.json');proof={(r['sector'],r['symbol']):r for r in PROOF['records']};files={};CACHE={};cachechecks=[]
def bundle(sec,sid):
 if (sec,sid) in CACHE:return CACHE[sec,sid]
 prep=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261027-153013-2ffe04/prepared') if sec=='TECH' else RR/'innovative-drug-sfw3-20261028/prepared';fp=prep/'facts'/f'{sid}.parquet';ep=RR/'ph1-cross-sector-20261028/events'/sec/f'{sid}.parquet';gp=RR/'ix-a-share-entry-20261025/signals'/f'{sid}.parquet';f=pd.read_parquet(fp);e=pd.read_parquet(ep);pr=proof[sec,sid]
 for p,h in [(fp,pr['inputs'][str(fp)]),(ep,pr['output_sha256'])]:actual=hashlib.sha256(p.read_bytes()).hexdigest();assert actual==h;files[str(p)]=actual
 assert f.index.equals(e.index) and f.close.equals(e.close) and f.segment_id.equals(e.segment_id)
 known=f.e0_ready.astype(bool)&f.e0_target.notna();on=f.e0_target.astype('boolean').where(known).groupby(f.segment_id).ffill().fillna(False).astype(bool);beg=on&~on.groupby(f.segment_id).shift(fill_value=False);labels=pd.Series(None,index=f.index,dtype=object)
 for day in f.index[beg]:labels.loc[day]=f'{sid}|source={int(f.loc[day,"segment_id"])}|E0={day.date()}'
 labels=labels.groupby(f.segment_id).ffill().where(on,None)
 g=None;ok=False;error=None
 if gp.exists():
  g=pd.read_parquet(gp);common=f.index.intersection(g.index)
  try:
   for old,new in [('close','close'),('grade','g_grade'),('fresh_up','g_fresh_up'),('strength_ready','g_ready')]:np.testing.assert_array_equal(g.loc[common,old].to_numpy(float),f.loc[common,new].to_numpy(float))
   signal_volume=pd.read_parquet(prep/'signals'/f'{sid}.parquet',columns=['volume']).reindex(common).volume;np.testing.assert_array_equal(g.loc[common,'volume'].to_numpy(float),signal_volume.to_numpy(float))
   bit=g.loc[common,'up_reasons'].fillna('').str.contains('new_E0_price_volume_up_event');np.testing.assert_array_equal(bit.to_numpy(bool),(e.loc[common,'event'].eq(1)&f.loc[common,'g_ready'].astype(bool)).to_numpy(bool))
   ok=True;files[str(gp)]=hashlib.sha256(gp.read_bytes()).hexdigest()
  except AssertionError as ex:error=str(ex)[:500];g=None
 cachechecks.append(dict(sector=sec,symbol=sid,archive_exists=gp.exists(),archive_verified=ok,archive_end=str(g.index[-1].date()) if g is not None else None,error=error));CACHE[sec,sid]=(f,e,g,labels,beg);return CACHE[sec,sid]

def snap(sec,sid,at,oldB=None,reference_floor=None):
 f,e,g,epoch,beg=bundle(sec,sid);day=pd.Timestamp(at[:10]);isopen=at[11:16]<'15:05';j=f.index.searchsorted(day,side='left' if isopen else 'right')-1
 if j<0:return dict(state_unknown=True)
 dt=f.index[j];r=f.iloc[j];seg=r.segment_id;past=e.loc[:dt];past=past[past.segment_id.eq(seg)];pos=past[past.event.eq(1)];neg=past[past.event.eq(-1)];pp=pos.iloc[-1] if len(pos) else None;pn=neg.iloc[-1] if len(neg) else None;gr=g.loc[dt] if g is not None and dt in g.index else None;fl=float(r.e0_floor) if np.isfinite(r.e0_floor) else None;co=float(r.close);new=bool(beg.loc[dt]);fresh=bool(r.g_fresh_up);warm=bool(r.g_ready and np.isfinite(r.g_grade) and r.g_grade>=2);reconstructed=bool(r.i_target and r.e0_target and warm and(new or fresh));assert reconstructed==bool(r.i_buy),(sec,sid,str(dt),'I identity')
 z=dict(state_asof=str(dt.date())+' 15:05:00+08:00',uses_previous_close_at_execution=isopen,source_segment=int(seg),epoch=epoch.loc[dt],e0_valid=bool(r.e0_target),i_valid=bool(r.i_target),i_buy=bool(r.i_buy),g_ready=bool(r.g_ready),g_grade=r.g_grade,g_fresh_up=fresh,e0_open_today=new,I_source='E0_start_and_G1_fresh' if new and fresh else 'E0_start' if new else 'G1_fresh' if fresh else 'no_new_I_evidence',g_up_reasons=gr.up_reasons if gr is not None else None,g_phase=gr.phase if gr is not None else None,z5=gr.z5 if gr is not None else None,z21=gr.z21 if gr is not None else None,g_acute_up=gr.acute_up if gr is not None else None,economic_close=co,raw_close=float(r.raw_close),factor=float(r.factor),e0_floor=fl,i_floor=float(r.i_floor) if np.isfinite(r.i_floor) else None,floor_ge_old_B=None if cmp(fl,oldB) is None else cmp(fl,oldB)>=0,floor_raised_since_exit=None if cmp(fl,reference_floor) is None else cmp(fl,reference_floor)>0,native_event=int(e.loc[dt,'event']),native_pivot=float(e.loc[dt,'pivot']) if np.isfinite(e.loc[dt,'pivot']) else None,native_pivot_date=e.loc[dt,'pivot_date'],last_low_confirmed_at=str(pos.index[-1].date()) if len(pos) else None,last_low_pivot=pp['pivot'] if pp is not None else None,last_low_date=pp['pivot_date'] if pp is not None else None,last_high_confirmed_at=str(neg.index[-1].date()) if len(neg) else None,last_high_pivot=pn['pivot'] if pn is not None else None,last_high_date=pn['pivot_date'] if pn is not None else None,prior_low=pos.iloc[-2]['pivot'] if len(pos)>1 else None,prior_high=neg.iloc[-2]['pivot'] if len(neg)>1 else None)
 z['low_higher_than_previous']=None if len(pos)<2 else cmp(pp['pivot'],pos.iloc[-2]['pivot'])>0;z['high_higher_than_previous']=None if len(neg)<2 else cmp(pn['pivot'],neg.iloc[-2]['pivot'])>0;z['close_reclaimed_last_confirmed_high']=None if pn is None else cmp(co,pn['pivot'])>=0;z['close_vs_last_confirmed_high']=None if pn is None else co/float(pn['pivot'])-1;prev=f.iloc[j-1].e0_floor if j and f.iloc[j-1].segment_id==seg else None;z['floor_raised_today']=None if cmp(fl,prev) is None else cmp(fl,prev)>0
 return clean(z)

EPLIST=cr(PRIOR/'RISK_TRIM_RECOVERY_EPISODES.csv');case_data={};observations=[];ALL=[];EPGATE=[];PL=[];examples=[];snapshotrows=[];summary=[]
for sec,mode in [('TECH','I'),('DRUG','ACT')]:
 for stress in ['base','delay1']:
  root=W/'partial-action-full-account-20261030'/sec/'on' if stress=='base' else W/'partial-action-delay-repair-20261030'/sec/'full';aid=f'{mode}__B_S0_{stress}';accountp=root/'accounts-v2'/f'{aid}.json';a=read(accountp);files[str(accountp)]=hashlib.sha256(accountp.read_bytes()).hexdigest();logs=a['audit_log'];ds=[r for r in gz(root/'accounts-v2/daily.jsonl.gz') if r['account']==aid];ep=[r for r in EPLIST if r['sector']==sec and r['stress']==stress];bysell={r['order_id']:r for r in ep};byrestore={oid:r for r in ep for oid in r['all_order_ids'].split('|') if oid};afills={r['receipt']['receipt_id']:r for r in logs if r['kind']=='fill'};reserves={r['order_id']:r for r in logs if r['kind']=='reserve'};pi={(r['at'],r['sid']):r for r in logs if r['kind']=='partial_input'};pa={r['at']:r for r in logs if r['kind']=='partial_admission'};act={r['at']:r for r in logs if r['kind']=='risk_checkpoint'};trimfills=defaultdict(list);restorefills=[];state={};pnl=defaultdict(D);cost=defaultdict(D);buys=Counter();sellqty=Counter()
  for r in logs:
   if r['kind'] in ['split','split_fraction_floor_proxy']:
    sid=r['sid']
    if sid in state:
     z=state[sid];rat=D(r['ratio']);total=int(D(z['K']+z['R'])*rat);z['R']=int(D(z['R'])*rat);z['K']=total-z['R']
   elif r['kind']=='partial_event':
    e=r['detail'];sid=e.get('sid');kind=e['kind']
    if kind=='actual_role_buy':
     f=e['receipt'];oid=afills[f['receipt_id']]['order_id']
     if e['action']=='risk_restore':
      old=byrestore[oid];key=old['order_id'];assert state[sid]['R']==0 or state[sid]['ep']==key;state[sid]['ep']=key;pnl[key]-=D(f['gross_cny'])+D(f['fees_cny']);cost[key]+=D(f['fees_cny']);buys[key]+=f['shares'];restorefills.append((e,old,reserves[oid]));state[sid].update(K=e['K'],R=e['R'])
     else:state[sid]=dict(K=e['K'],R=e['R'],ep=None)
    elif kind=='actual_role_sell':
     f=e['receipt'];z=state[sid];dr=z['R']-e['R'];key=z['ep']
     if key and dr:ratio=D(dr)/f['shares'];pnl[key]+=(D(f['gross_cny'])-D(f['fees_cny']))*ratio;cost[key]+=D(f['fees_cny'])*ratio;sellqty[key]+=dr
     if e['action']=='risk_trim':trimfills[afills[f['receipt_id']]['order_id']].append(f)
     z.update(K=e['K'],R=e['R'])
     if e['K']+e['R']==0:state.pop(sid)
    elif kind=='role_dividend' and state[sid]['ep']:pnl[state[sid]['ep']]+=D(e['risk'])
  last=ds[-1];con={(r['date'],r['symbol']):r for r in cr(root/'analysis/contributions.csv') if r['account']==aid}
  for sid,z in state.items():
   if z['ep']:pnl[z['ep']]+=D(con[last['at'][:10],sid]['market_value'])*z['R']/(z['K']+z['R'])
  expected=next(r for r in read(PRIOR/'RECOVERY_SUMMARY.json') if r['sector']==sec and r['stress']==stress)['role_profit']['risk_restored'];assert abs(sum(pnl.values(),Z)-D(expected))<D('1e-8')
  for old in ep:
   sid=old['symbol'];rp=pi.get((old['request_at'],sid));B=rp['diagnostic'].get('boundary') if rp else None;exitstate=snap(sec,sid,old['request_at'],B);floor0=exitstate.get('e0_floor');sell=trimfills[old['order_id']];flatat=old['flat_at'];future=[];missing=[]
   if flatat:
    for d in ds:
     at=d['at']
     if not flatat<at<old['window_end']:continue
     f,ev,g,epoch,beg=bundle(sec,sid);day=pd.Timestamp(at[:10]);el=next((q for q in pa[at]['decisions'][-1]['eligibility'] if q['security_id']==sid),None)
     if day not in f.index:missing.append(at);continue
     if not bool(f.loc[day,'i_buy']):continue
     if el is None or el['q'] is None:missing.append(at);continue
     if el['q'] is not True or not act[at]['on']:continue
     z=snap(sec,sid,at,B,floor0);same=z['epoch']==old['group'];gate=z['floor_ge_old_B'] if same else None;future.append(dict(at=at,gate=gate,same_epoch=same,e0_floor=z['e0_floor'],up_reasons=z['g_up_reasons']))
   first=future[0] if future else None;firstpass=next((r for r in future if r['gate'] is True),None);cat='not_applicable_not_flat' if not flatat else 'no_fresh_I_Q_observed' if not first and not missing else 'unknown_before_eligibility' if not first else 'first_IQ_pass' if first['gate'] is True else 'first_IQ_fail' if first['gate'] is False else 'first_IQ_unknown'
   row=dict(old,old_B=B,exit_decision_floor=floor0,first_fresh_IQ=first['at'] if first else None,gate_at_first_IQ=first['gate'] if first else None,first_gated_fresh_IQ=firstpass['at'] if firstpass else None,gate_workflow=cat,missing_observations='|'.join(missing),actual_restored_profit=pnl[old['order_id']],actual_restored_all_fees=cost[old['order_id']],later_market_date_is_not_counterfactual_fill=True);EPGATE.append(row);case_data[sec,stress,old['order_id']]=dict(old=old,B=B,floor0=floor0,sells=sell,exitstate=exitstate,logs=logs,pi=pi,ds=ds)
   if old['restore_fill_count']!='0':PL.append(dict(sector=sec,stress=stress,symbol=sid,name=old['name'],episode_id=old['order_id'],first_restore_at=old['first_restore_at'],end_at=old['cycle_end'] or ds[-1]['at'],actual_restored_profit=pnl[old['order_id']],actual_restored_all_fees=cost[old['order_id']],buy_shares=buys[old['order_id']],sell_shares=sellqty[old['order_id']]))
  for e,old,reserve in restorefills:
   sid=e['sid'];key=old['order_id'];info=case_data[sec,stress,key];B=info['B'];floor0=info['floor0'];sig=reserve['decision_at'];fill=e['receipt'];sell=info['sells'][-1];f,ev,g,epoch,beg=bundle(sec,sid);sd=snap(sec,sid,sig,B,floor0);assert sd['i_buy'] and sd['g_ready'] and sd['g_grade']>=2;di=pi.get((sig,sid));q=next(x for x in pa[sig]['decisions'][-1]['eligibility'] if x['security_id']==sid);assert q['q'] is True
   if pd.Timestamp(sell['at'][:10]) in f.index:exitfactor=float(f.loc[pd.Timestamp(sell['at'][:10]),'factor']);exit_economic=float(D(sell['gross_cny'])/sell['shares'])*exitfactor
   else:exit_economic=None
   fday=pd.Timestamp(fill['at'][:10]);factor=float(f.loc[fday,'factor']) if fday in f.index else None;execution_economic=float(D(fill['gross_cny'])/fill['shares'])*factor if factor else None
   z=dict(sector=sec,stress=stress,symbol=sid,name=old['name'],episode_id=key,restore_receipt=fill['receipt_id'],exit_decision=old['request_at'],exit_first_fill=old['first_trim_at'],exit_flat_at=old['flat_at'],exit_flat_price_raw=D(sell['gross_cny'])/sell['shares'],exit_flat_price_economic=exit_economic,restore_signal=sig,restore_fill=fill['at'],restore_shares=fill['shares'],restore_price_raw=D(fill['gross_cny'])/fill['shares'],restore_price_economic=execution_economic,restore_buy_fees=fill['fees_cny'],old_B=B,gate_pass=sd['floor_ge_old_B'],same_original_epoch=sd['epoch']==old['group'],old_controller_handover='not_applicable_old_risk_already_sold',actual_episode_restored_profit=pnl[key],signal_close_vs_exit=None if not exit_economic else sd['economic_close']/exit_economic-1,restore_execution_vs_exit=None if not exit_economic or not execution_economic else execution_economic/exit_economic-1,**sd);ALL.append(z)
   for phase,at in [('exit_decision',old['request_at']),('exit_execution',sell['at']),('restore_signal',sig),('restore_execution',fill['at'])]:snapshotrows.append(dict(sector=sec,stress=stress,symbol=sid,episode_id=key,restore_receipt=fill['receipt_id'],phase=phase,at=at,**snap(sec,sid,at,B,floor0)))
  actual=[r for r in ALL if r['sector']==sec and r['stress']==stress];epg=[r for r in EPGATE if r['sector']==sec and r['stress']==stress];counts=Counter('pass' if r['gate_pass'] is True else 'fail' if r['gate_pass'] is False else 'unknown' for r in actual);reasons=Counter(r['g_up_reasons'] or 'archive_unknown' for r in actual);s=dict(sector=sec,stress=stress,requests=len(ep),actual_restore_fills=len(actual),actual_gate=dict(counts),all_request_workflow=dict(Counter(r['gate_workflow'] for r in epg)),reason_combinations=dict(reasons),new_E0_starts=sum(r['e0_open_today'] for r in actual),same_epoch=sum(r['same_original_epoch'] for r in actual),old_B_available=sum(r['old_B'] is not None for r in epg));summary.append(s);print('SUMMARY',s,flush=True)
write('ALL_57_RESTORES.csv',ALL);write('FOUR_TIMEPOINTS.csv',snapshotrows);write('ALL_115_REQUEST_GATE_TIMES.csv',EPGATE);write('ACTUAL_RECOVERY_EPISODE_MONEY.csv',PL);save('SUMMARY.json',summary);save('ARCHIVE_JOIN_CHECKS.json',cachechecks);save('INPUT_IDENTITY.json',dict(source_sha256=files,unchanged_formulas=True,new_indicators_computed=0,new_account_paths=0))
# Fixed requested drug cases and actual tech exposure examples; never a trading selection.
tech=[r for r in PL if r['sector']=='TECH'];selected=[('drug_whipsaw','DRUG','delay1','603259.SH'),('drug_profitable_recovery_less_than_hold','DRUG','delay1','688331.SH')]
for label,row in [('tech_losing',min(tech,key=lambda r:r['actual_restored_profit'])),('tech_profitable',max(tech,key=lambda r:r['actual_restored_profit']))]:selected.append((label,row['sector'],row['stress'],row['symbol']))
DAILY=[]
for label,sec,st,sid in selected:
 relevant=[r for r in PL if r['sector']==sec and r['stress']==st and r['symbol']==sid];example=next((r for r in relevant if r['first_restore_at'][:4]=='2024'),relevant[0]) if label=='drug_whipsaw' else next((r for r in relevant if r['first_restore_at'][:4]=='2025'),relevant[0]) if label=='drug_profitable_recovery_less_than_hold' else (min(relevant,key=lambda r:r['actual_restored_profit']) if label=='tech_losing' else max(relevant,key=lambda r:r['actual_restored_profit']));info=case_data[sec,st,example['episode_id']];cycle=info['old']['cycle'];events=[r['detail'] for r in info['logs'] if r['kind']=='partial_event' and r['detail'].get('sid')==sid];initial=next(e for e in events if e['kind']=='actual_role_buy' and e['receipt']['receipt_id']==cycle);lo=initial['at'][:10];hi=(info['old']['cycle_end'] or info['ds'][-1]['at'])[:10];trans=[e for e in events if e['kind'] in ['risk_trim_request','actual_role_buy','actual_role_sell'] and lo<=e['at'][:10]<=hi];examples.append(dict(label=label,selected=example,cycle=cycle,start=lo,end=hi,transactions=trans,read_only_gate_rows=[r for r in ALL if r['sector']==sec and r['stress']==st and r['symbol']==sid and lo<=r['restore_fill'][:10]<=hi]))
 for d in info['ds']:
  if lo<=d['at'][:10]<=hi:DAILY.append(dict(case=label,sector=sec,stress=st,symbol=sid,date=d['at'][:10],actual_held=d['positions'].get(sid,0),**snap(sec,sid,d['at'],info['B'],info['floor0'])))
write('EXAMPLE_DAILY_STATES.csv',DAILY);save('EXAMPLES.json',examples);save('COMPUTATION.json',dict(seconds=time.monotonic()-START,restores=len(ALL),requests=len(EPGATE),snapshots=len(snapshotrows),cached_symbols=len(CACHE),new_indicators=0,new_orders=0,new_policy_PnL=0));print('DONE',time.monotonic()-START,'examples',[(x['label'],x['selected']['symbol']) for x in examples],flush=True)
