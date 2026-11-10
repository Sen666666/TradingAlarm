"""Three entitlement-evidenced cash-event cases. Scenario, not historical truth.
80% receivable, never cash/reinvested. 0% is a labeled omitted-equity diagnostic only.
"""
from pathlib import Path
from decimal import Decimal as D
import ast,sys,json,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;E=O.parent;R=E.parent;OLD=E/'lifecycle_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
NAV=D('1200000');INIT=D('24000');SLOT=D('48000');RISK=D('3000');SLIP=D('.0005');END=pd.Timestamp('2026-06-30')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
assert not (O/'SCENARIO_ROUNDS.csv').exists(),'No overwrite'
facts_public=[
 dict(sid='300390.SZ',record_date='2022-03-15',ex_date='2022-03-16',gross_cash_per_share='0.50',split_ratio='1',source_url='https://static.cninfo.com.cn/finalpage/2022-04-11/1212886028.PDF',source_description='天风证券发行保荐书，第8页，2021年度实施现金分红表：登记3/15、除息3/16、每10股5元。',evidence_time='retrospective_filing_after_event',pay_date=None),
 dict(sid='000708.SZ',record_date='2022-04-12',ex_date='2022-04-13',gross_cash_per_share='0.80',split_ratio='1',source_url='https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=8892346&stockid=000708',source_description='中信特钢2022年年度报告所载2021年度分配：登记4/12、除息4/13、每10股8元。',supporting_source_url='https://www.xinbaomu.com/info/28039.shtml',supporting_description='2022-031实施公告转载，登记收盘持有人，4/13代派，差别化税而非统一20%。',evidence_time='retrospective_annual_report_and_dated_notice_reproduction',pay_date='2022-04-13'),
 dict(sid='000895.SZ',record_date='2022-04-28',ex_date='2022-04-29',gross_cash_per_share='1.298',split_ratio='1',source_url='https://disc.static.szse.cn/disc/disk03/finalpage/2022-04-21/547a1a64-48b7-4fd1-92dd-9b39646c6cf1.PDF',source_description='深交所2022-23实施公告：4/28收盘登记、4/29除息及代派，每10股12.98元；差别化红利税。',evidence_time='official_exchange_implementation_notice_before_event',pay_date='2022-04-29')]
save('PUBLIC_ENTITLEMENT_FACTS.json',facts_public)
public={(x['sid'],pd.Timestamp(x['ex_date'])):x for x in facts_public}
manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')};rules=read(B/'inputs-v2/market-rules.json');proxies=read(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids']
panel_path=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet';panel=pd.read_parquet(panel_path).sort_values(['sector','day']);cal=pd.DatetimeIndex(sorted(panel.day.unique()));cal=cal[cal<=END]
sector={s:g.set_index('day').M3_candidate.to_dict() for s,g in panel.groupby('sector')}
raw={};facts={};cp={};capacity={};meta={};load_count=0;hashes={};closecache={};rounds=[];actions=[]
source=(OLD/'simulate.py').read_text();tree=ast.parse(source)
names={'finite','true','false','lineage','flags','DayFrame','load','getmeta','fee','size','checkclose','act','record','freeze_unknown','mark','entry_open','held_open','held_close'}
for node in tree.body:
 if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names:
  text=ast.get_source_segment(source,node)
  if node.name=='mark':
   text=text.replace("return st['cash']+", "return st['cash']+st.get('receivable',D(0))+")
  if node.name=='record':
   text=text.replace("  out.update(exit_day=d,net_pnl=float(st['cash']),net_return_on_buy_cash=float(st['cash']/st['spent']))", "  out.update(exit_day=d,net_pnl=float(st['cash']+st.get('receivable',D(0))),net_return_on_buy_cash=float((st['cash']+st.get('receivable',D(0)))/st['spent']))")
   text=text.replace(' rounds.append(out)'," out.update(scenario=scenario,original_round_id=st['original_round_id'],dividend_receivable=float(st.get('receivable',D(0))),unpaid_receivable_not_in_cash=True,net_equity_is_scenario_not_actual_cash=True)\n rounds.append(out)")
  exec(compile(text,str(OLD/'simulate.py')+':scenario_definition','exec'),globals())
z=pd.read_csv(OLD/'ROUNDS.csv');oldact=pd.read_csv(OLD/'ACTIONS.csv')
target=z[z.window.eq('2022')&z.arm.eq('A_UNION_B')&z.status.eq('FACTOR_PATH_UNKNOWN')&z.sid.isin([x['sid'] for x in facts_public])].sort_values('status_day');assert len(target)==3
for sid in target.sid:load(sid)
events=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',parse_dates=['day','previous_common_day'],low_memory=False).set_index('event_id')
for p in [Path(__file__),O/'PUBLIC_ENTITLEMENT_FACTS.json',OLD/'simulate.py',OLD/'PROTOCOL.json',OLD/'ROUNDS.csv',OLD/'ACTIONS.csv',E/'SEALED_ALL_BIRTH_EVENTS.csv',panel_path,B/'inputs-v2/market-rules.json',B/'inputs-v2/economic-protocol.json',B/'code/market_rules.py',B/'code/sector_account.py']:hashes[str(p)]=sha(p)
for sid in target.sid:
 p=AS/'inputs-v1/actions'/f'{sid}.json';hashes[str(p)]=sha(p)
protocol=dict(scope='Three first chronological cash-only interruptions with verified record/ex dates: 300390,000708,000895. No full426 inference.',targets=target.round_id.tolist(),scenarios={'NET80_RECEIVABLE':'Old declared model net factor0.8; never cash, never reinvested, contributes to net equity/profit eligibility.','OMITTED_RECEIVABLE_DIAGNOSTIC':'Identical bridge but omit receivable to isolate bookkeeping and path sensitivity. Economically incomplete counterfactual, not original results.'},rules=['Retain original share quantities, no factor-scaled virtual shares.','Confirm recorded simulated ownership at verified record-date CLOSE; missing evidence stops UNKNOWN.','Before ex-date OPEN accrue a receivable from record-date quantities; selling on ex-date does not remove entitlement.','Rebase all outstanding raw protection prices by F_previous/F_current.','Cash, original buy cost, and quantities do not change on dividend accrual.','All unverified later actions remain UNKNOWN; no suspension price filling.','State persists within round through additions and exits, but later birth selection is not rerun.'],not_actual_tax_or_payment=True,account_run=False,selection_run=False,source_hashes=hashes)
save('PRE_RUN_SEAL.json',protocol)
divs=[];marks=[];bridges=[];prefix=[];eligibility={}
for scenario,netfactor in [('NET80_RECEIVABLE',D('.8')),('OMITTED_RECEIVABLE_DIAGNOSTIC',D('0'))]:
 for rr in target.to_dict('records'):
  sid=rr['sid'];r=events.loc[rr['event_id']].to_dict();r['event_id']=rr['event_id'];d=pd.Timestamp(rr['signal_day']);r['day']=d;ck=checkclose(r);assert ck['close_check']=='PASS'
  st=dict(r,state='BUY_PENDING',arm='A_UNION_B',round_id=rr['round_id']+'|'+scenario,original_round_id=rr['round_id'],signal_day=d,birth_end=pd.Timestamp('2022-12-31'),close_q=ck['close_q'],prior20_capacity=ck['prior20_capacity'],receivable=D(0));states={sid:st};inventory_close={};processed=set()
  for k,t in enumerate(cal):
   if t<=d:continue
   if sid not in states or states[sid]['state']=='UNKNOWN':break
   st=states[sid];qold=st.get('core',0)+st.get('add',0)
   if st['state']=='HELD':
    cur=raw[sid].get(t,{})
    change=finite(cur.get('adjustment_factor')) and not np.isclose(cur['adjustment_factor'],st['factor'],rtol=1e-11)
    if change:
     e=public.get((sid,t));ap=read(AS/'inputs-v1/actions'/f'{sid}.json');matches=[x for x in ap['events'] if x['effective_date']==str(t.date())]
     if e is not None and len(matches)==1:
      e0=matches[0];assert D(e0['cash_per_old_share'])==D(e['gross_cash_per_share']) and D(e0['split_ratio'])==D(1)
      rec=pd.Timestamp(e['record_date']);qrec=inventory_close.get(rec)
      if qrec is None:freeze_unknown(states,sid,st,'RECORD_DATE_OWNERSHIP_UNKNOWN',t);continue
      assert qrec>0 and rec<t and (sid,t) not in processed;processed.add((sid,t))
      prev=raw[sid].frame[raw[sid].frame.index<t].iloc[-1];cash=D(e['gross_cash_per_share']);f_old=st['fac'];f_new=D(str(cur['adjustment_factor']));pred=D(str(prev.adjustment_factor))*D(str(prev.raw_close))/(D(str(prev.raw_close))-cash)
      assert np.isclose(float(pred),float(f_new),rtol=1e-11)
      oldcash=st['cash'];spent=st['spent'];protect={}
      for key in ['addfloor','addpending']:
       if st.get(key) is not None:
        before=st[key];st[key]=before*f_old/f_new;protect[key]={'before':float(before),'after':float(st[key])}
      st['fac']=f_new;st['factor']=float(f_new);inc=D(qrec)*cash*netfactor;st['receivable']+=inc
      assert oldcash==st['cash'] and spent==st['spent'] and qold==st['core']+st['add']
      divs.append(dict(round_id=st['round_id'],original_round_id=rr['round_id'],scenario=scenario,sid=sid,record_date=e['record_date'],ex_date=e['ex_date'],record_close_shares=qrec,gross_cash=float(D(qrec)*cash),net_assumption=float(netfactor),receivable_increase=float(inc),cash_increase=0,share_increase=0,source_url=e['source_url']))
      bridges.append(dict(round_id=st['round_id'],day=str(t.date()),factor_old=float(f_old),factor_new=float(f_new),raw_protections_rebased=protect))
   if states[sid]['state']=='BUY_PENDING':entry_open(states,sid,states[sid],t)
   elif states[sid]['state']=='HELD':held_open(states,sid,states[sid],t,cal[k-1])
   if sid in states and states[sid]['state']=='HELD':
    held_close(states,sid,states[sid],t)
    if states[sid]['state']=='HELD':
     st=states[sid];inventory_close[t]=st['core']+st['add'];marks.append(dict(round_id=st['round_id'],scenario=scenario,sid=sid,day=str(t.date()),shares=inventory_close[t],trade_cash=float(st['cash']),receivable=float(st['receivable']),net_equity_at_close=st.get('last_mark_net'),addpending=st['addpending'] is not None,exitpending=st['exitpending']))
  if sid in states and states[sid]['state']=='HELD':record(states[sid],'OPEN_CENSORED_AT_2026_06_30',END)
  # The entire known prefix must reproduce original actions; only ex-date and later can differ.
  orig=oldact[oldact.round_id.eq(rr['round_id'])].reset_index(drop=True);new=pd.DataFrame([x for x in actions if x['round_id']==rr['round_id']+'|'+scenario and x['day']<rr['status_day']]).reset_index(drop=True)
  assert len(orig)==len(new)
  for col in ['day','side','q','price','fee']:
   if col in ['price','fee']:assert np.allclose(orig[col],new[col],atol=1e-9,rtol=0)
   else:assert orig[col].equals(new[col])
  prefix.append(dict(round_id=rr['round_id'],scenario=scenario,original_prefix_actions=len(orig),exact=True))
rz=pd.DataFrame(rounds);ac=pd.DataFrame(actions)
rz['status']=rz.status.replace({'COMPLETE_CONDITIONAL_STOCK_ROUND':'SCENARIO_CLOSED_NOT_FACT'})
rz.to_csv(O/'SCENARIO_ROUNDS.csv',index=False);ac.to_csv(O/'SCENARIO_ACTIONS.csv',index=False);pd.DataFrame(divs).to_csv(O/'SCENARIO_RECEIVABLES.csv',index=False);pd.DataFrame(marks).to_csv(O/'SCENARIO_DAILY_MARKS.csv',index=False);save('SCENARIO_BRIDGES.json',bridges)
qa=[]
for r in rz.to_dict('records'):
 aa=ac[ac.round_id.eq(r['round_id'])];c=D(0);q=0;fees=D(0)
 for x in aa.to_dict('records'):
  n=int(x['q']);px=D(str(x['price']));fee_=D(str(x['fee']));buy=x['side'].startswith('buy');q+=n if buy else -n;c+=-n*px-fee_ if buy else n*px-fee_;fees+=fee_;assert q>=0
 assert abs(float(c)-r['cashflow_to_date'])<1e-8
 if r['status']=='SCENARIO_CLOSED_NOT_FACT':assert q==0 and abs(float(c)+r['dividend_receivable']-r['net_pnl'])<1e-8
 qa.append(dict(round_id=r['round_id'],trade_cash=float(c),receivable=r['dividend_receivable'],inventory=q,cash_plus_receivable_matches=True))
assert all(sha(p)==h for p,h in hashes.items())
save('QA.json',dict(prefix_exact=prefix,ledger=qa,all_source_hashes_unchanged=True,economic_paths=6,new_selection_runs=0,account_runs=0))
print(rz[['scenario','sid','status','entry_day','exit_day','net_pnl','net_return_on_buy_cash','dividend_receivable','added']].to_string(index=False))
print('RECEIVABLES',json.dumps(divs,ensure_ascii=False))
