"""Independent protection replay plus unchanged raw-price/Decimal ledger audit."""
from cp_common import *
from decimal import Decimal as D
from collections import Counter
sys.path.insert(0,str(PRIOR/'code'));import experiment as P

def checker(sector):
 strict={sid:pd.read_parquet(OLD_TABLES[sector]/f'{sid}.parquet') for sid in pool(sector).symbol}
 amt={sid:pd.read_parquet(SA/'signals'/sector/f'{sid}.parquet') for sid in pool(sector).symbol}
 cp={sid:pd.read_parquet(cpdir(sector)/f'{sid}.parquet') for sid in pool(sector).symbol}
 dates=sorted({x[:10] for x in read(PRIOR/'execution-rules-v2.json')['decision_cutoffs']}|{'2023-12-29','2026-10-23','2026-10-26','2026-10-27'})
 def check(aid,obj,ds,facts,records):
  mode=aid.split('__')[0];cnt=Counter();intents={};classes={};watch={};live={};pending=set();risk={};filled_orders=set();closed=set();last_buy={}
  for r in obj['audit_log']:
   k=r['kind'];sid=r.get('sid');day=(r['receipt']['at'] if k=='fill' else r.get('at',''))[:10]
   if k=='risk_checkpoint':risk[r['at']]=r;assert r['policy']=='ACT20_BREAK'
   elif k=='intent_create':
    assert mode in ['SW3F','WCP'];f=facts[sid].loc[day];assert f.i_buy and strict[sid].loc[day,'strict_target'];assert float(r['floor'])==float(f.i_floor);watch[sid]=dict(r);cnt['original_wait_create']+=1
   elif k=='waiting_support_raise':
    assert r['previous']==watch[sid]['floor'] and r['floor']>=r['previous'] and r['close']>r['floor'];watch[sid]['floor']=r['floor'];cnt['waiting_f_raises']+=1
   elif k=='intent_end':watch.pop(sid,None)
   elif k=='entry_contract':
    at=r['decision_at'][:10];f=facts[sid].loc[at];table=amt if mode in ['SAMT','MCP'] else strict
    if mode not in ['ACT','ACP']:assert bool(table[sid].loc[at,'strict_target'])
    w=watch.get(sid) if mode in ['SW3F','WCP'] else None
    floor=max(D(str(f.i_floor)),D(str(w['floor']))) if w else D(str(f.i_floor))
    assert D(r['floor_signal'])==floor,(aid,sid,at,'entry support')
    if not f.i_buy:assert w and f.i_target and f.g_ready and f.g_grade>=2
    if w:assert 0<=dates.index(at)-dates.index(w['day'])<3
    assert D(r['budget'])<=D('.15')*D(r['nav'])+D('.01');assert D(r['risk_budget'])==D('.01')*D(r['nav']);assert risk[r['at']]['on']
    intents[r['order_id']]=r;cnt['entry_strict_and_original_or_waiting']+=1
   elif k=='intent_entry_class':
    z=intents[r['order_id']];f=facts[sid].loc[day];assert bool(r['original'])==bool(f.i_buy)
    if r['origin']:assert mode in ['SW3F','WCP'] and r['window']==3 and D(z['floor_signal'])>=D(str(r['waiting_floor']))
    classes[r['order_id']]=r
   elif k=='fill':
    f=r['receipt'];sid=f['security_id'];mult=D(2) if aid.endswith('cost2') else D(1);sign=1 if f['side']=='buy' else -1
    assert f['at'][11:19]=='09:30:00';assert D(r['price'])==D(r['raw_open'])*(1+sign*D('.0005')*mult)
    if f['side']=='buy':
     z=intents[r['order_id']];assert z['decision_at'][:10]<f['at'][:10];factor=D(str(facts[sid].loc[:day].iloc[-1].factor));assert D(r['raw_open'])>D(z['floor_signal'])/factor
     filled_orders.add(r['order_id']);last_buy[sid]=r;cnt['causal_open_guard']+=1
   elif k=='waiting_support_inherited':
    z=intents[r['order_id']];assert r['floor']>=float(z['floor_signal']) and classes[r['order_id']]['origin']==r['origin'];cnt['f_inherited']+=1
   elif k=='fast_support_raise':
    assert mode in ['SF','SW3F'];assert r['previous'] is None or r['floor']>=r['previous']
   elif k=='fast_support_exit':assert mode in ['SF','SW3F'] and r['close']<=r['floor']
   elif k=='cp_start':
    assert mode in CPS and sid not in live and r['order_id'] in filled_orders
    z=intents[r['order_id']];assert r['P']==float(z['floor_signal']) and pd.Timestamp(r['entry_at'])==pd.Timestamp(r['at']);assert pd.Timestamp(last_buy[sid]['receipt']['at'])==pd.Timestamp(r['at']);assert r['segment']==str(facts[sid].loc[day].segment_id)
    live[sid]=dict(P=float(z['floor_signal']),cycle_id=r['cycle_id'],entry_at=r['at']);cnt['actual_fill_initialization']+=1
   elif k=='exit_request':pending.add(sid)
   elif k=='cp_checkpoint':
    s=live[sid];f=facts[sid];observed=pd.Timestamp(day) in f.index;row=f.loc[:day].iloc[-1];old=s['P']
    reason='ACT' if not risk[r['at']]['on'] else 'E0' if not row.i_target else 'locked' if sid in pending else 'CP' if observed and float(row.close)<=old else None
    receipt=False;candidate=None;new=old
    if not reason and observed:
     z=cp[sid].loc[day];receipt=bool(z.receipt)
     if receipt:candidate=float(z.candidate)
     if np.isfinite(row.i_floor):new=max(new,float(row.i_floor))
     if candidate is not None:new=max(new,candidate)
    expected=dict(observed=observed,close=float(row.close),E=float(row.i_floor),old_P=old,new_P=new,receipt=receipt,candidate=candidate,reason=reason,raised_by_cp=candidate is not None and candidate>max(old,float(row.i_floor)))
    for key,value in expected.items():
     both_nan=isinstance(value,float) and isinstance(r[key],float) and np.isnan(value) and np.isnan(r[key])
     assert both_nan or r[key]==value,(aid,sid,day,key,r[key],value)
    assert r['cycle_id']==s['cycle_id'] and pd.Timestamp(s['entry_at'])<pd.Timestamp(r['at']);s['P']=new;cnt['independent_cp_close']+=1
   elif k=='cp_end':
    s=live.pop(sid);assert r['cycle_id']==s['cycle_id'] and r['P']==s['P'];assert s['cycle_id'] not in closed;closed.add(s['cycle_id']);pending.discard(sid);cnt['actual_flat_end']+=1
  assert set(intents)==set(classes)
  return dict(passed=True,checks=dict(cnt),independent_cp_no_policy_helper=True)
 return check

def control(sector,stage):
 root=O/sector;source=root/('technical/short-v2' if stage=='short' else 'accounts-v2');daily=rows(source/'daily.jsonl.gz');n=0;cache={}
 for mode in ['ACT','S','SF','SW3F','SAMT']:
  ref,oldmode=reference(sector,mode)
  if ref not in cache:cache[ref]={(r['account'],r['at']):r for r in rows(ref/'daily.jsonl.gz')}
  for r in daily:
   if not r['account'].startswith(mode+'__'):continue
   aid=r['account'];oldaid=oldmode+aid[len(mode):];target=dict(cache[ref][oldaid,r['at']]);target['account']=aid
   assert r==target,(sector,aid,r['at'],'old daily control');n+=1
  end=max(r['at'] for r in daily)
  for stress in ['base','cost2','delay1']:
   aid=f'{mode}__S0_{stress}';oldaid=f'{oldmode}__S0_{stress}'
   assert read(source/f'{aid}.json')['fills']==[r for r in read(ref/f'{oldaid}.json')['fills'] if r['at']<=end],(sector,aid,'control fills')
 save(root/f'control-{stage}.json',dict(passed=True,accounts=15,daily_rows=n,complete_daily_and_fills_exact=True))

def audit(sector,stage):
 A=P.A;A.CORE=PRIOR/'input' if sector=='TECH' else PREPS[sector];A.PREP=PREPS[sector];A.HERE=O/sector;A.check_contract=checker(sector);A.main(stage);control(sector,stage)

def prefix(sector):
 root=O/sector;full=root/'accounts-v2';cut=root/'technical/prefix';counts={}
 for name in ['daily','decisions']:
  ref={(r['account'],r['at']):r for r in rows(full/f'{name}.jsonl.gz')};small=rows(cut/f'{name}.jsonl.gz')
  for r in small:assert r==ref[r['account'],r['at']],(sector,name,r['account'],r['at'])
  counts[name]=len(small)
 for mode in MODES:
  for stress in ['base','cost2','delay1']:
   aid=f'{mode}__S0_{stress}';a=read(cut/f'{aid}.json');b=read(full/f'{aid}.json')
   assert a['fills']==[r for r in b['fills'] if r['at'][:10]<='2026-06-30']
   small=[r for r in a['audit_log'] if r['kind'].startswith('cp_')];large=[r for r in b['audit_log'] if r['kind'].startswith('cp_') and r['at'][:10]<='2026-06-30']
   assert json.dumps(small,sort_keys=True)==json.dumps(large,sort_keys=True),(sector,aid,'CP log prefix')
 save(root/'prefix-verification.json',dict(passed=True,accounts=27,cp_logs_and_fills_exact=True,cutoff='2026-06-30',**counts))
if __name__=='__main__':prefix(sys.argv[2]) if sys.argv[1]=='prefix' else audit(sys.argv[1],sys.argv[2])
