"""One presealed fixed24 source-coordinate NET80 experiment. Not official ex-price/tax/PIT."""
from pathlib import Path
from decimal import Decimal as D
import ast,inspect,importlib.util,json,hashlib,sys,time
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;V=O.parent/'cash_dividend_402_scenario_v2'
spec=importlib.util.spec_from_file_location('prior_frozen_v2',V/'run_scenario.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
target=pd.read_csv(O/'ADJUDICATED_24.csv',dtype={'d_cash':str,'d_source':str,'d_ref':str});assert len(target)==24 and target.sid.nunique()==24
pub={r['round_id']:r for r in target.to_dict('records')}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
# Reuse the independently approved state machine. Only three explicit source edits below.
base=inspect.getsource(s.run_round)
assert base.count("cash=D(str(event['public_gross_cash_per_share']))")==1
base=base.replace("cash=D(str(event['public_gross_cash_per_share']))", "cash=D(str(event['cash_per_old_share']))")
assert base.count("round_id=rid+'|NET80|'+mode,")==1
base=base.replace("round_id=rid+'|NET80|'+mode,", "round_id=rid+'|NET80|'+mode+'|'+CASH_VARIANT,")
exec(compile(base,'frozen_v2_run_round_with_cash_coordinate_separation','exec'),s.__dict__)
# Log, never change, original equity values read by OPEN and CLOSE decisions.
marks=[];original_mark=s.mark
def traced_mark(st,px,d):
 value=original_mark(st,px,d)
 if st.get('dividend_applied'):
  marks.append(dict(round_id=st['round_id'],original_round_id=st['original_round_id'],mode=s.MODE,cash_variant=s.CASH_VARIANT,day=str(d.date()),caller=inspect.currentframe().f_back.f_code.co_name,net_equity=str(value),strictly_positive=value>0))
 return value
s.mark=traced_mark

def verify():
 seal=json.loads((O/'CONTRACT_SEAL.json').read_text());assert all(sha(p)==h for p,h in seal['source_hashes'].items()),'source/code drift';s.verify_seal();return seal

def prepare():
 assert not (O/'CONTRACT_SEAL.json').exists()
 paths=list(json.loads((V/'CONTRACT_SEAL.json').read_text())['source_hashes'])
 paths += [str(V/'FINAL_INDEPENDENT_AUDIT.json'),str(V/'run_scenario.py'),str(Path(__file__)),str(O/'adjudicate_notices.py'),str(O/'ADJUDICATED_24.csv'),str(O/'NOTICE_EVIDENCE.json'),str(O/'FACT_SUMMARY.json')]
 paths += [str(p) for p in (O/'notice_pdf').iterdir() if p.is_file()]
 paths += [str(p) for p in (O/'notices').iterdir() if p.is_file()]
 for r in target.to_dict('records'):
  m=s.manifest[r['sid']];sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
  for p in [sp,m['refs']['facts'],m['refs']['CP1']]:assert sha(p)=={**m['source_sha256'],**m['output_sha256']}[p];paths.append(p)
  paths += [r['source_path'],str(s.AS/'inputs-v1/actions'/(r['sid']+'.json'))]
 sample=['000333.SZ','300002.SZ','002056.SZ','000060.SZ','300229.SZ','601615.SH','600938.SH'];ids=target[target.sid.isin(sample)].round_id.tolist();assert len(ids)==7
 save(O/'CONTRACT_SEAL.json',{'created_utc':str(pd.Timestamp.now(tz='UTC')),'fixed_targets':target.round_id.tolist(),'unit_ids':ids,'controls':s.controls,'variants':['PRECISE_PUBLIC_CASH','OLD_SOURCE_CASH_DIAGNOSTIC'],'modes':['FULL_CORE_PLUS_ADD','CORE_ONLY'],'scope':'24 preexisting unresolved permits only, fixed original signal coordinates; no later births, no shared capital, no actual tax or PIT or official ex-reference-price certification.','three_quantities':'d_cash is declared shareholder gross cash; d_source only explains stored legacy factor; d_ref is optional official exchange ex-reference deduction, disclosed but never used to rewrite source.','coordinate_policy':'Only verify first bridge using d_source and original factor with 1e-11 relative tolerance; use stored Fold/Fnew for both raw protections; no changes to I/CP/source series or other state machine order.','cash_policy':'Own arm record CLOSE inventory. NET80 explicit scenario accrued before ex OPEN. Known pay-date CLOSE transfer after signals, next common OPEN convention. Budget unchanged.','diagnostic_policy':'Compare identical frozen coordinates with cash ledger using d_source vs precise d_cash. Report all decisions/actions and first divergence. Point dividend delta is a PnL delta only if complete action paths identical; not assumed.','gate_margin_policy':'Log unchanged mark() on every post-event OPEN/CLOSE use. If both endpoint paths identical and profit-sign traces identical, then within this exact two-cash interval no mark sign flip along those paths. Not a bound on alternative signals, prices, taxes or future events.','failure_policy':'Any unverified later action/source/missing price stays UNKNOWN; no invented suspension or delisting recovery.','reporting':'Overlay only PRECISE_PUBLIC_CASH 24 rows onto strict prior fixed2432. Keep closed/UNKNOWN/censored/nofill separate, each own and common closed denominator.','source_hashes':{p:sha(p) for p in sorted(set(paths))}});print('SEALED',len(set(paths)),flush=True)

def threshold_test():
 # Exercise the unchanged held_open boundary with controlled mark values, no economic outcomes.
 saved={k:getattr(s,k) for k in ['mark','getmeta','fee','size']};sid='SYNTH_PRECISION';d=pd.Timestamp('2022-01-05');prev=d-pd.Timedelta(days=1);calls=[]
 savedraw=s.raw.get(sid);savedfacts=s.facts.get(sid);savedcap=s.capacity.get(sid)
 s.raw[sid]=s.DayFrame(pd.DataFrame([{'raw_open':10,'adjustment_factor':1,'source_kind':'x','source_path':'y','segment_id':'z'}],index=[d]));s.facts[sid]=s.DayFrame(pd.DataFrame([{'i_floor':5}],index=[prev]));s.capacity[sid]={prev:100}
 s.getmeta=lambda *a:(None,None,D(1));s.fee=lambda *a:D(0);s.size=lambda *a:(calls.append(1) or (0,D(0),D(0),None,None))
 result=[]
 try:
  for v in [D('-.0001'),D(0),D('.0001')]:
   s.mark=lambda *a,_v=v:_v
   st={'origin':('x','y','z'),'factor':1,'fac':D(1),'exitpending':None,'addexitpending':False,'addpending':D(5),'add':0,'core':100,'initial_fee':D(0),'add_attempts':0,'add_profit_floor_rejects':0,'add_size_rejects':0,'added':False}
   before=len(calls);s.held_open({sid:st},sid,st,d,prev);passed=len(calls)>before;assert passed==(v>0);result.append({'net':str(v),'passed_profit_gate':passed})
 finally:
  for k,v in saved.items():setattr(s,k,v)
  for g,v in [(s.raw,savedraw),(s.facts,savedfacts),(s.capacity,savedcap)]:
   if v is None:g.pop(sid,None)
   else:g[sid]=v
 return result

def compare_cash_endpoints():
 out=[];rz=pd.DataFrame(s.rounds);ac=pd.DataFrame(s.actions);mk=pd.DataFrame(marks)
 for (rid,mode),g in rz.groupby(['original_round_id','mode']):
  if rid not in pub:continue
  p=g[g.cash_variant=='PRECISE_PUBLIC_CASH'].iloc[0];q=g[g.cash_variant=='OLD_SOURCE_CASH_DIAGNOSTIC'].iloc[0]
  pa=ac[ac.round_id.eq(p.round_id)][['day','side','q','price','fee']].reset_index(drop=True);qa=ac[ac.round_id.eq(q.round_id)][['day','side','q','price','fee']].reset_index(drop=True);same=pa.equals(qa)
  pm=mk[mk.round_id.eq(p.round_id)].reset_index(drop=True);qm=mk[mk.round_id.eq(q.round_id)].reset_index(drop=True)
  sameclock=pm[['day','caller']].equals(qm[['day','caller']]);samesign=sameclock and pm.strictly_positive.equals(qm.strictly_positive)
  delta=D(str(p.register_qty))*D('.8')*(D(str(pub[rid]['d_cash']))-D(str(pub[rid]['d_source'])))
  casherr=float(p.cash_after_known_payouts-q.cash_after_known_payouts)-float(delta)
  if same:assert abs(casherr)<1e-7
  pnl_delta=float(p.net_pnl-q.net_pnl) if p.status==q.status=='SCENARIO_CLOSED_NOT_FACT' else None
  if same and pnl_delta is not None:assert abs(pnl_delta-float(delta))<1e-7
  v=[abs(D(str(v))) for v in pm.net_equity];minimum=min(v) if v else None
  first=None
  if not same:
   for i in range(max(len(pa),len(qa))):
    if i>=len(pa) or i>=len(qa) or not pa.iloc[i].equals(qa.iloc[i]):first={'index':i,'precise':pa.iloc[i].to_dict() if i<len(pa) else None,'oldcash':qa.iloc[i].to_dict() if i<len(qa) else None};break
  out.append(dict(original_round_id=rid,mode=mode,precise_status=p.status,oldcash_status=q.status,actions_identical=same,mark_clocks_identical=sameclock,profit_signs_identical=samesign,own_register_qty=int(p.register_qty),net80_cash_delta=float(delta),observed_pnl_delta=pnl_delta,post_event_min_abs_mark=float(minimum) if minimum is not None else None,min_mark_exceeds_cash_delta=(minimum>abs(delta)) if minimum is not None else None,first_action_divergence=first))
 return out

def run(phase):
 seal=verify();dest=O/phase;dest.mkdir(exist_ok=True);assert not (dest/'RUN_ONCE.json').exists()
 if phase=='full':assert json.loads((O/'UNIT_INDEPENDENT_AUDIT.json').read_text())['full_run_permitted'] is True
 ids=seal['unit_ids']+seal['controls'] if phase=='unit' else seal['fixed_targets']
 save(dest/'RUN_ONCE.json',{'contract_sha256':sha(O/'CONTRACT_SEAL.json'),'fixed_permits':ids,'start_utc':str(pd.Timestamp.now(tz='UTC'))})
 syn=s.synthetic_tests();gate=threshold_test();start=time.monotonic()
 for rid in ids:
  for variant in seal['variants']:
   s.CASH_VARIANT=variant
   for mode in seal['modes']:
    e=pub[rid].copy() if rid in pub else None
    if e:e['public_gross_cash_per_share']=e['d_cash'] if variant=='PRECISE_PUBLIC_CASH' else e['d_source']
    starts=[len(s.rounds),len(s.actions),len(s.divs),len(s.bridges),len(s.marks)]
    r=s.run_round(rid,mode,e)
    for arr,i in zip([s.rounds,s.actions,s.divs,s.bridges,s.marks],starts):
     for row in arr[i:]:row['cash_variant']=variant
    r.update(d_source=e['d_source'] if e else None,d_cash=e['d_cash'] if e else None,d_ref=e.get('d_ref') if e else None,cash_used_per_share=e['public_gross_cash_per_share'] if e else None)
 ledger=s.ledger_qa();comparison=compare_cash_endpoints();verify()
 if phase=='unit':
  for rid in seal['controls']:
   for r in [x for x in s.rounds if x['original_round_id']==rid and x['mode']=='FULL_CORE_PLUS_ADD']:
    old=s.old_by.loc[rid];assert abs(r['net_pnl']-old.net_pnl)<1e-7 and pd.Timestamp(r['exit_day'])==pd.Timestamp(old.exit_day)
 for fn,arr in [('ROUNDS.csv',s.rounds),('ACTIONS.csv',s.actions),('DIVIDEND_LEDGER.csv',s.divs),('DAILY_MARKS.csv',s.marks),('PROFIT_GATE_VALUES.csv',marks),('CASH_ENDPOINT_COMPARISON.csv',comparison)]:pd.DataFrame(arr).to_csv(dest/fn,index=False)
 save(dest/'BRIDGES.json',s.bridges);save(dest/'QA.json',{'synthetic':syn,'strict_zero_gate':gate,'ledger':ledger,'prefix_checks':s.prefix,'economic_paths':len(s.rounds),'fixed_permits':len(ids),'source_unchanged':True,'seconds':time.monotonic()-start,'same_action_paths_all':all(x['actions_identical'] for x in comparison),'same_profit_signs_all':all(x['profit_signs_identical'] for x in comparison),'comparison':comparison});save(dest/'OUTPUT_HASHES.json',{p.name:sha(p) for p in dest.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'});print(pd.DataFrame(s.rounds).groupby(['cash_variant','mode','status']).size().to_string());print('DONE',phase,flush=True)
if __name__=='__main__':
 if sys.argv[1]=='prepare':prepare()
 elif sys.argv[1] in ['unit','full']:run(sys.argv[1])
 else:raise ValueError(sys.argv[1])
