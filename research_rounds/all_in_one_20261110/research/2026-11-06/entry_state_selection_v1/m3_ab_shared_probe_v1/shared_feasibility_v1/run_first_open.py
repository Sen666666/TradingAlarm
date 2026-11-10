"""One real-data initial OPEN reservation feasibility fixture, no fills."""
from pathlib import Path
import sys,json,time,traceback,contextlib,hashlib
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'source_bridge_v1'))
import bridge
from limits import snapshot_from_ab,ReserveBook,reserve_initial,D
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
 with Path(p).open('x') as f:json.dump(v,f,indent=2,ensure_ascii=False,default=str);f.write('\n')
def main():
 dest=HERE/'first_open_2022';dest.mkdir(exist_ok=False)
 seal=json.loads((HERE/'CODE_SEAL.json').read_text())
 for p,h in seal['sha256'].items():assert sha(HERE/p)==h
 save(dest/'STARTED.json',{'stage':'REAL_INPUT_RESERVATION_FEASIBILITY_ONLY','at':datetime.now(timezone.utc).isoformat(),'code_seal':sha(HERE/'CODE_SEAL.json'),'shared_fills':False})
 with (dest/'RUN_LOG.txt').open('x') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
  try:
   s=bridge.load_original('2022');bridge.replay_no_budget(s,'2022-01-05')
   assert not s.actions
   states={x['sid']:{'state':x['final_state'],'round_id':x['round_id']} for x in s.blocks}
   day=s.pd.Timestamp('2022-01-06')
   snapshot=snapshot_from_ab(s,states,day,seed_cash=D('1200000'),daily_planning_nav=D('1200000'),pool_by_round={})
   assert snapshot.certified and snapshot.cash==snapshot.nav==D('1200000') and not snapshot.holdings
   selected=[x for x in s.archives.values() if x['state']=='BUY_PENDING' and x['signal_day']==s.pd.Timestamp('2022-01-05')]
   selected.sort(key=lambda x:(-x['PVR_score'],x['sid']))
   assert len(selected)==30 and max(s.pd.DataFrame(selected).groupby('sector').size())==2
   before=snapshot.cash
   book=ReserveBook(snapshot);plans=[reserve_initial(s,book,st,day,D('1200000')) for st in selected]
   assert snapshot.cash==before and not s.actions,'No fills and no cash debits allowed'
   save(dest/'PLANS.json',plans);save(dest/'RESERVATIONS.json',book.audit)
   save(dest/'SNAPSHOT.json',{'cash':snapshot.cash,'receivable':snapshot.receivable,'gross_nav':snapshot.nav,'daily_planning_nav':snapshot.daily_planning_nav,
        'known_holdings':len(snapshot.holdings),'unknown':snapshot.unknown,'reserved_cash':book.reserved_cash,'unbooked_buy_fees':book.unbooked_buy_fees,
        'probe_resources':book.resources(pool='probe')})
   bridge.verified_manifest()
   for p,h in seal['sha256'].items():assert sha(HERE/p)==h
   result={'status':'AUTHOR_PASS_REAL_INPUT_INITIAL_RESERVATION_FEASIBILITY_ONLY','original_selected':len(plans),'fundable_reservations':sum(x['shared_q']>0 for x in plans),
           'source_open':'2022-01-06','execution':'NO_SHARED_FILLS','no_shared_return':True,'sequential_fee_adjusted_caps':True,'queue':'original industry top-two, PVR descending/sid global merge',
           'limitations':['No held-OPEN perturbation test yet','No ADD/promotion phase wiring','No CP/equity proof adapter implemented here','No account economics','First-day empty holdings only'],
           'output_sha256':{p.name:sha(p) for p in dest.iterdir() if p.is_file() and p.name!='RUN_LOG.txt'}}
   save(dest/'RESULT.json',result)
  except BaseException as e:
   traceback.print_exc();save(dest/'RESULT.json',{'status':'FAIL','error_type':type(e).__name__,'error':str(e)});raise
 print(json.dumps(result,default=str),flush=True)
if __name__=='__main__':main()
