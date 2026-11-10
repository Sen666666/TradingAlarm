"""Fixed-permit NET80 cash-dividend scenarios, not actual tax, PIT or a shared account.
Modes prepare -> unit -> independent approval -> full once. Never modify old artifacts.
"""
from pathlib import Path
from decimal import Decimal as D
import ast,sys,json,hashlib,time,datetime
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;E=O.parent;R=E.parent;OLD=E/'lifecycle_v1';PUB=E/'cash_dividend_source_feasibility_v1';BR=E/'corporate_action_path_audit_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
NAV=D('1200000');INIT=D('24000');SLOT=D('48000');RISK=D('3000');SLIP=D('.0005');END=pd.Timestamp('2026-06-30');NET=D('.8')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')};rules=read(B/'inputs-v2/market-rules.json');proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids']
panel_path=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet';panel=pd.read_parquet(panel_path).sort_values(['sector','day']);cal=pd.DatetimeIndex(sorted(panel.day.unique()));cal=cal[cal<=END]
sector={s:g.set_index('day').M3_candidate.to_dict() for s,g in panel.groupby('sector')}
raw={};facts={};cp={};capacity={};meta={};load_count=0;hashes={};closecache={};rounds=[];actions=[];divs=[];bridges=[];marks=[];prefix=[]
source=(OLD/'simulate.py').read_text();tree=ast.parse(source)
names={'finite','true','false','lineage','flags','DayFrame','load','getmeta','fee','size','checkclose','act','record','freeze_unknown','mark','entry_open','held_open','held_close'}
for node in tree.body:
 if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names:
  exec(compile(ast.get_source_segment(source,node),str(OLD/'simulate.py')+':unchanged_definition','exec'),globals())
native_record=record;native_mark=mark;native_act=act
MODE='UNSET'
def mark(st,px,d):return native_mark(st,px,d)+st.get('receivable',D(0))
def act(st,d,side,q,px,fee_,reason,**extra):
 native_act(st,d,side,q,px,fee_,reason,**extra);actions[-1].update(mode=MODE,original_round_id=st['original_round_id'])
def record(st,status,d=None,**extra):
 native_record(st,status,d,**extra)
 row=rounds[-1];st['_output_index']=len(rounds)-1
 row.update(mode=MODE,original_round_id=st['original_round_id'],cash_at_stock_termination=float(st.get('cash',D(0))),receivable_at_stock_termination=float(st.get('receivable',D(0))),dividend_recognized_at_stock_termination=float(st.get('dividend_total',D(0))),scenario_not_actual_tax=True)
 if status=='COMPLETE_CONDITIONAL_STOCK_ROUND':
  row.update(net_pnl=float(st['cash']+st.get('receivable',D(0))),net_return_on_buy_cash=float((st['cash']+st.get('receivable',D(0)))/st['spent']))

def accrue(st,q,cash,day):
 assert q>=0 and not st.get('dividend_applied',False)
 before=(st['cash'],st['spent'],st['core'],st['add']);inc=D(q)*cash*NET
 st['receivable']=st.get('receivable',D(0))+inc;st['dividend_total']=inc;st['dividend_applied']=True
 assert before==(st['cash'],st['spent'],st['core'],st['add'])
 return inc

def settle(st,day):
 before=st['cash']+st['receivable'];inc=st['receivable'];st['cash']+=inc;st['receivable']=D(0);st['dividend_paid']=st.get('dividend_paid',D(0))+inc
 assert before==st['cash']+st['receivable']
 st['last_payout_day']=day
 return inc

def rebase(st,new_factor):
 old=st['fac'];out={}
 for key in ['addfloor','addpending']:
  if st.get(key) is not None:
   before=st[key];st[key]=before*old/new_factor;out[key]={'before':str(before),'after':str(st[key])}
 st['fac']=new_factor;st['factor']=float(new_factor)
 return out

all_old=pd.read_csv(OLD/'ROUNDS.csv',low_memory=False);oldact=pd.read_csv(OLD/'ACTIONS.csv',low_memory=False)
old=all_old[all_old.window.eq('2022')&all_old.arm.eq('A_UNION_B')].copy();assert len(old)==2432
public_table=pd.read_csv(PUB/'EVENT_FACTS_WITH_DOCUMENTED_COMPOSITES.csv')
target=public_table[public_table.coverage_status.isin(['CURRENT_PUBLIC_FACTS_MATCHED_NOT_PIT_OR_TAX_CERTIFIED','PUBLIC_NOTICE_DOCUMENTED_COMPOSITE_NOT_PIT_OR_TAX_CERTIFIED'])].copy().sort_values(['status_day','sid']);assert len(target)==402 and target.sid.nunique()==402
pub={r['round_id']:r for r in target.to_dict('records')};old_by=old.set_index('round_id')
events=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',parse_dates=['day','previous_common_day'],low_memory=False).set_index('event_id')
controls=old[old.sid.eq('000001.SZ')&old.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')].round_id.tolist();assert len(controls)==3

def verify_seal():
 s=read(O/'CONTRACT_SEAL.json');assert all(sha(p)==h for p,h in s['source_hashes'].items()),'Frozen source/code changed';return s

def prepare():
 assert not (O/'CONTRACT_SEAL.json').exists(),'Do not overwrite a frozen contract'
 unit_sids=['300390.SZ','000708.SZ','000895.SZ','601808.SH','600188.SH','002507.SZ']
 sold=set(oldact[oldact.side.eq('sell_add')].round_id)
 sold_target=target[target.round_id.isin(sold)].iloc[0];unit_sids.append(sold_target.sid)
 # Select an ex-date exit case from known prior-close I state, never later outcome.
 ex_exit=None
 for t in target.to_dict('records'):
  rr=old_by.loc[t['round_id']];f=pd.read_parquet(manifest[t['sid']]['refs']['facts'],columns=['i_target'])
  rec=pd.Timestamp(t['record_date'])
  if rec in f.index and false(f.loc[rec,'i_target']):ex_exit=t['sid'];unit_sids.append(ex_exit);break
 unit_ids=target[target.sid.isin(unit_sids)].round_id.tolist()
 files=[Path(__file__),OLD/'simulate.py',OLD/'PROTOCOL.json',OLD/'ROUNDS.csv',OLD/'ACTIONS.csv',E/'SEALED_ALL_BIRTH_EVENTS.csv',E/'EVENT_SEAL.json',panel_path,U/'STOCK_MANIFEST.json',B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json',B/'code/market_rules.py',B/'code/sector_account.py',PUB/'EVENT_FACTS_WITH_DOCUMENTED_COMPOSITES.csv',PUB/'FINAL_INDEPENDENT_AUDIT.json',PUB/'FINAL_OUTPUT_HASHES.json',PUB/'PUBLIC_SOURCE_CHECKS.json',PUB/'COMPOSITE_NOTICE_ADJUDICATION.json',PUB/'COMPOSITE_NOTICE_ADJUDICATION_600188.json',BR/'BRIDGED_ROUNDS.csv',BR/'BRIDGED_ACTIONS.csv']
 for sid in list(target.sid)+['000001.SZ']:
  m=manifest[sid];sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
  for p in [sp,m['refs']['facts'],m['refs']['CP1']]:
   expected={**m['source_sha256'],**m['output_sha256']}[p];assert sha(p)==expected,(sid,p,'manifest mismatch');files.append(Path(p))
 for t in target.to_dict('records'):files.extend([PUB/'raw'/(t['sid']+'.json'),AS/'inputs-v1/actions'/(t['sid']+'.json')])
 # Source files for an algebraic initial-only baseline, not a second full selection run.
 base_sids=set(old[old.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')].sid)|set(pd.read_csv(BR/'BRIDGED_ROUNDS.csv').sid)
 for sid in base_sids:
  p=AS/'inputs-v1/actions'/(sid+'.json')
  if p.exists():files.append(p)
 s={'created_utc':str(pd.Timestamp.now(tz='UTC')),'targets':target.round_id.tolist(),'unit_case_ids':unit_ids,'unit_prior_sold_add_sid':sold_target.sid,'unit_ex_open_exit_sid':ex_exit,'controls':controls,'net_dividend_factor':'0.8, explicit historical-model scenario, not actual investor tax','modes':['FULL_CORE_PLUS_ADD','CORE_ONLY'],'scope':'Original 402 permits from 2022 A_UNION_B only; no reselection, no later births, no shared capital, no PIT claim.','event_policy':'Only the one preverified first pure-cash event for each whitelisted round. Any later unparsed factor or source change/missing price remains UNKNOWN. 24 precision conflicts, 50 share actions and 32 missing opens excluded.','clock':['At record-date CLOSE lock each arm own simulated inventory; FULL must match original register inventory. CORE_ONLY is from entry with adds disabled.','At ex-date before OPEN recognize NET80 receivable. No share count, acquisition cash, spending denominator or fee change.','Only matching factor bridge with unchanged lineage and prior-close formula verified: update fac to stored source factor, raw addfloor and addpending by Fold/Fnew, preserve all pending exit flags.','Process original next OPEN and CLOSE state machine. CORE_ONLY retains original I/CP/source failure gates but clears new addpending.','At pay-date CLOSE after signals, transfer receivable to cash exactly once. Availability next common OPEN is a conservative date-level convention, not a fact about actual intraday broker credit.','Claims survive stock exit or UNKNOWN. Stock termination and payout settlement dates separately retained. No prices are simulated beyond a stock UNKNOWN.'],'sizing':'Unchanged fixed INIT24000/SLOT48000/RISK3000 and volume proxy. Original formula never uses cash balance; dividend settlement does not enlarge budget. Equity including dividends can alter the existing positive-profit add gate.','baseline':'Show old1913 closed and accepted10 entry bridges separately. CORE_ONLY baseline is same known core entry/exit with stand-alone dated fees, only after local corporate-action interval check. Not arbitrary allocation of full-round sell_all fees.','reporting':'Closed, open-censored, UNKNOWN separate. Full versus core-only on each own denominator and common closed cohort. Original and recovered cohort distribution, by birth quarter and A/B, no UNKNOWN treated as losses.','source_hashes':{str(p):sha(p) for p in sorted(set(files))}}
 save(O/'CONTRACT_SEAL.json',s);print('SEALED',len(s['source_hashes']),'sources',len(unit_ids),'case rounds',flush=True)

def run_round(rid,mode,event):
 global MODE
 MODE=mode;rr=old_by.loc[rid].to_dict();rr['round_id']=rid;sid=rr['sid'];load(sid)
 r=events.loc[rr['event_id']].to_dict();r['event_id']=rr['event_id'];d=pd.Timestamp(rr['signal_day']);r['day']=d;ck=checkclose(r);assert ck['close_check']=='PASS'
 st=dict(r,state='BUY_PENDING',arm='A_UNION_B',round_id=rid+'|NET80|'+mode,original_round_id=rid,signal_day=d,birth_end=pd.Timestamp('2022-12-31'),close_q=ck['close_q'],prior20_capacity=ck['prior20_capacity'],receivable=D(0),dividend_total=D(0),dividend_paid=D(0),dividend_applied=False)
 rootst=st;states={sid:st};qrec=None;processed=False;bridge_done=False
 rec=pd.Timestamp(event['record_date']) if event else None;ex=pd.Timestamp(event['status_day']) if event else None;pay=pd.Timestamp(event['pay_date']) if event else None
 for k,t in enumerate(cal):
  if t<=d:continue
  active=sid in states and states[sid]['state'] in ('BUY_PENDING','HELD')
  if event and t==ex and qrec is not None and qrec>0:
   inc=accrue(rootst,qrec,D(str(event['public_gross_cash_per_share'])),t);processed=True
   divs.append(dict(round_id=rootst['round_id'],original_round_id=rid,mode=MODE,sid=sid,day=str(t.date()),event='ACCRUE_NET80_RECEIVABLE',record_date=str(rec.date()),record_qty=qrec,gross_per_share=event['public_gross_cash_per_share'],amount=float(inc),cash_delta=0,receivable_delta=float(inc),available_for_orders_from=None))
  if active:
   st=states[sid]
   if st['state']=='HELD':
    cur=raw[sid].get(t,{})
    # Preserve original OPEN/CLOSE validation order. No daily-close flag gate at OPEN.
    if event and t==ex:
     if qrec is None or qrec<=0:freeze_unknown(states,sid,st,'REGISTER_OWNERSHIP_UNKNOWN',t);active=False
     elif not finite(cur.get('raw_open')) or cur['raw_open']<=0:freeze_unknown(states,sid,st,'MISSING_OPEN_PATH_UNKNOWN',t);active=False
     elif lineage(cur)!=st['origin']:freeze_unknown(states,sid,st,'SOURCE_CHANGE_PATH_UNKNOWN',t);active=False
     else:
      prev=raw[sid].get(rec,{});fnew=D(str(cur.get('adjustment_factor')));fold=st['fac'];cash=D(str(event['public_gross_cash_per_share']))
      if not finite(prev.get('raw_close')) or not finite(cur.get('adjustment_factor')) or fnew<=0 or D(str(prev['raw_close']))<=cash:
       freeze_unknown(states,sid,st,'CASH_FACTOR_BRIDGE_UNKNOWN',t);active=False
      else:
       pred=D(str(prev['adjustment_factor']))*D(str(prev['raw_close']))/(D(str(prev['raw_close']))-cash)
       if abs(pred/fnew-D(1))>D('1e-11'):
        freeze_unknown(states,sid,st,'CASH_FACTOR_BRIDGE_UNKNOWN',t);active=False
       else:
        before_qty=st['core']+st['add'];before=(st['cash'],st['spent'],st['fees']);reb=rebase(st,fnew);bridge_done=True
        assert before==(st['cash'],st['spent'],st['fees']) and before_qty==st['core']+st['add']
        bridges.append(dict(round_id=st['round_id'],original_round_id=rid,mode=MODE,day=str(t.date()),old_factor=str(fold),new_factor=str(fnew),predicted_factor=str(pred),register_qty=qrec,protections=reb,exitpending=st['exitpending'],addexitpending=st['addexitpending']))
   if active:
    if st['state']=='BUY_PENDING':entry_open(states,sid,st,t)
    elif st['state']=='HELD':held_open(states,sid,st,t,cal[k-1])
   if sid in states and states[sid]['state']=='HELD':
    held_close(states,sid,states[sid],t)
    if states[sid]['state']=='HELD':
     st=states[sid]
     if MODE=='CORE_ONLY':st['addpending']=None;assert st['add']==0 and not st['added']
     if event and t==rec:qrec=st['core']+st['add']
     marks.append(dict(round_id=st['round_id'],original_round_id=rid,mode=MODE,day=str(t.date()),core=st['core'],add=st['add'],cash_before_payout=float(st['cash']),receivable_before_payout=float(st['receivable']),net_equity_at_close=st.get('last_mark_net'),addpending=st['addpending'] is not None,exitpending=st['exitpending']))
  if event and processed and t==pay:
   inc=settle(rootst,t);nextd=cal[k+1] if k+1<len(cal) else None
   divs.append(dict(round_id=rootst['round_id'],original_round_id=rid,mode=MODE,sid=sid,day=str(t.date()),event='PAY_CLOSE_TRANSFER',record_date=str(rec.date()),record_qty=qrec,gross_per_share=event['public_gross_cash_per_share'],amount=float(inc),cash_delta=float(inc),receivable_delta=-float(inc),available_for_orders_from=str(nextd.date()) if nextd is not None else None))
  active=sid in states and states[sid]['state'] in ('BUY_PENDING','HELD')
  pending_claim=(qrec is not None and qrec>0 and ((not processed) or rootst['receivable']>0))
  if not active and not pending_claim:break
 if sid in states and states[sid]['state']=='HELD':record(rootst,'OPEN_CENSORED_AT_2026_06_30',END)
 elif sid in states and states[sid]['state']=='BUY_PENDING':record(rootst,'BUY_PENDING_CENSORED_AT_DATA_END',END)
 assert '_output_index' in rootst,(rid,MODE,'no outcome')
 row=rounds[rootst['_output_index']];row.update(cash_after_known_payouts=float(rootst.get('cash',0)),receivable_after_known_payouts=float(rootst.get('receivable',0)),dividend_net80_total=float(rootst.get('dividend_total',0)),dividend_net80_paid=float(rootst.get('dividend_paid',0)),register_qty=qrec,bridge_applied=bridge_done,payout_date=str(rootst['last_payout_day'].date()) if 'last_payout_day' in rootst else None,old_status=rr['status'],old_status_day=rr['status_day'])
 if row['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND':
  row.update(status='SCENARIO_CLOSED_NOT_FACT',net_pnl=float(rootst['cash']+rootst['receivable']),net_return_on_buy_cash=float((rootst['cash']+rootst['receivable'])/rootst['spent']))
 if event and mode=='FULL_CORE_PLUS_ADD' and qrec is not None:assert qrec==int(event['register_held_qty_in_original_simulation'])
 # Full path before the original interruption is unchanged; core-only deliberately differs only by omitted adds.
 cutoff=rr['status_day'] if event else '9999-12-31'
 orig=oldact[oldact.round_id.eq(rid)].reset_index(drop=True)
 aa=pd.DataFrame([x for x in actions if x['round_id']==rootst['round_id'] and x['day']<cutoff]).reset_index(drop=True)
 if MODE=='FULL_CORE_PLUS_ADD':
  assert len(orig)==len(aa),(rid,'prefix count')
  for col in ['day','side','q','price','fee']:
   if col in ['price','fee']:assert np.allclose(orig[col],aa[col],atol=1e-8,rtol=0),(rid,col)
   else:assert orig[col].tolist()==aa[col].tolist(),(rid,col)
 else:
  x=orig[orig.side.eq('buy_core')].iloc[0];y=aa[aa.side.eq('buy_core')].iloc[0]
  assert all(x[c]==y[c] for c in ['day','q']) and abs(x.price-y.price)<1e-9 and abs(x.fee-y.fee)<1e-8
 prefix.append(dict(round_id=rid,mode=MODE,prefix_check=True,register_qty=qrec))
 return row

def synthetic_tests():
 s={'cash':D('-100'),'receivable':D(0),'spent':D('100'),'fees':D('1'),'core':10,'add':5,'fac':D(2),'factor':2,'addfloor':D(7),'addpending':D(8),'exitpending':'I_STRUCTURE_EXIT','addexitpending':True}
 inc=accrue(s,15,D('.5'),pd.Timestamp('2022-01-01'));assert inc==D(6) and s['core']==10 and s['add']==5
 reb=rebase(s,D(4));assert s['addfloor']==D('3.5') and s['addpending']==D(4) and s['addexitpending'] and s['exitpending']=='I_STRUCTURE_EXIT'
 s['cash']+=D(150);s['core']=s['add']=0;before=s['cash']+s['receivable'];settle(s,pd.Timestamp('2022-01-05'));assert s['cash']==before and s['receivable']==0 and s['spent']==100
 # Original fail-closed branches remain active for second factor, missing open and source change.
 global freeze_unknown
 saved_freeze=freeze_unknown;captured=[];sid='SYNTHETIC';saved_raw=raw.get(sid)
 def cap(states,sid,st,status,d):captured.append(status);states[sid]={'state':'UNKNOWN'}
 freeze_unknown=cap
 try:
  t=pd.Timestamp('2022-01-06');z={'raw_open':10,'adjustment_factor':2,'source_kind':'a','source_path':'b','segment_id':'c'}
  for changes,expected in [({},'FACTOR_PATH_UNKNOWN'),({'raw_open':np.nan},'MISSING_OPEN_PATH_UNKNOWN'),({'adjustment_factor':1,'source_path':'changed'},'SOURCE_CHANGE_PATH_UNKNOWN')]:
   zz={**z,**changes};raw[sid]=DayFrame(pd.DataFrame([zz],index=[t]));st={'origin':('a','b','c'),'factor':1};held_open({},sid,st,t,t-pd.Timedelta(days=1));assert captured[-1]==expected
 finally:
  freeze_unknown=saved_freeze
  if saved_raw is None:raw.pop(sid,None)
  else:raw[sid]=saved_raw
 return {'accrual_shares_cost_unchanged':True,'two_raw_floors_rebased':True,'pending_exit_flags_preserved':True,'claim_survives_flat_until_later_payment':True,'payment_equity_conservation':True,'future_factor_missing_open_source_change_fail_closed':True,'synthetic_only_no_return_stats':True}

def ledger_qa():
 out=[]
 for r in rounds:
  aa=[x for x in actions if x['round_id']==r['round_id']];q=0;c=D(0);spent=D(0);fees=D(0);bought={}
  for x in aa:
   n=int(x['q']);px=D(str(x['price']));ff=D(str(x['fee']));buy=x['side'].startswith('buy');day=x['day']
   if buy:q+=n;c-=n*px+ff;spent+=n*px+ff;bought[day]=bought.get(day,0)+n
   else:assert n<=q-bought.get(day,0);q-=n;c+=n*px-ff
   fees+=ff;assert q>=0
  paid=D(str(r['dividend_net80_paid']));rec=D(str(r['receivable_after_known_payouts']))
  assert abs(float(c+paid)-r['cash_after_known_payouts'])<1e-7 and abs(float(spent)-r['total_buy_cash'])<1e-7 and abs(float(fees)-r['all_fees'])<1e-7
  if r['status']=='SCENARIO_CLOSED_NOT_FACT':assert q==0 and abs(float(c+paid+rec)-r['net_pnl'])<1e-7
  if r['mode']=='CORE_ONLY':assert all(x['side'] in ['buy_core','sell_all'] for x in aa)
  out.append(dict(round_id=r['round_id'],inventory=q,trade_cash=float(c),dividend_paid=float(paid),receivable=float(rec),reconciled=True))
 return out

def phase(which):
 s=verify_seal();dest=O/which;dest.mkdir(exist_ok=True)
 assert not (dest/'RUN_ONCE.json').exists(),'Never repeat an economic phase'
 if which=='full':assert read(O/'UNIT_INDEPENDENT_AUDIT.json')['full_run_permitted'] is True
 ids=s['unit_case_ids']+s['controls'] if which=='unit' else s['targets']
 save(dest/'RUN_ONCE.json',{'start_utc':str(pd.Timestamp.now(tz='UTC')),'contract_sha256':sha(O/'CONTRACT_SEAL.json'),'mode':which,'fixed_permits':ids,'outcomes_not_computed_yet':True})
 syn=synthetic_tests();start=time.monotonic()
 for n,rid in enumerate(ids):
  for mode in ['FULL_CORE_PLUS_ADD','CORE_ONLY']:run_round(rid,mode,pub.get(rid))
  if n%40==0:print(which,n+1,'/',len(ids),'seconds',round(time.monotonic()-start,1),flush=True)
 rz=pd.DataFrame(rounds);ac=pd.DataFrame(actions);ledger=ledger_qa()
 rz.to_csv(dest/'ROUNDS.csv',index=False);ac.to_csv(dest/'ACTIONS.csv',index=False);pd.DataFrame(divs).to_csv(dest/'DIVIDEND_LEDGER.csv',index=False);pd.DataFrame(marks).to_csv(dest/'DAILY_MARKS.csv',index=False);save(dest/'BRIDGES.json',bridges)
 verify_seal()
 checks={'synthetic':syn,'prefix_checks':prefix,'ledger':ledger,'frozen_sources_unchanged':True,'economic_paths':len(rounds),'fixed_permits':len(ids),'no_selection_or_shared_account_run':True,'seconds':time.monotonic()-start}
 if which=='unit':
  previous=pd.read_csv(E/'cash_dividend_sensitivity_v1/SCENARIO_ROUNDS.csv')
  for sid in ['300390.SZ','000708.SZ','000895.SZ']:
   v=rz[(rz.sid==sid)&(rz['mode']=='FULL_CORE_PLUS_ADD')].iloc[0];p=previous[(previous.sid==sid)&(previous.scenario=='NET80_RECEIVABLE')].iloc[0]
   assert v.status=='SCENARIO_CLOSED_NOT_FACT' and abs(v.net_pnl-p.net_pnl)<1e-7 and pd.Timestamp(v.exit_day)==pd.Timestamp(p.exit_day)
  checks['prior_three_receivable_scenario_full_economics_unchanged']=True
  for rid in controls:
   v=rz[(rz.original_round_id==rid)&(rz['mode']=='FULL_CORE_PLUS_ADD')].iloc[0];p=old_by.loc[rid]
   assert abs(v.net_pnl-p.net_pnl)<1e-7 and pd.Timestamp(v.exit_day)==pd.Timestamp(p.exit_day)
  checks['three_no_action_controls_match']=True
 save(dest/'QA.json',checks);save(dest/'OUTPUT_HASHES.json',{p.name:sha(p) for p in dest.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
 print(rz.groupby(['mode','status']).size().to_string(),flush=True);print('DONE',which,round(time.monotonic()-start,1),flush=True)

if __name__=='__main__':
 mode=sys.argv[1]
 if mode=='prepare':prepare()
 elif mode in ['unit','full']:phase(mode)
 else:raise ValueError(mode)
