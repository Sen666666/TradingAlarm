"""Fixed-14 source-only case trace. No consumer imports, account or indicator runs."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,gzip,hashlib,traceback,math
import pandas as pd,numpy as np
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
A=R/'act_only_ablation_continuous_v1'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
U=W/'universe-cp1-inputs-20261031'
O=Path(__file__).resolve().parent
IDS=[27,17,28,1527,1542,2891,2893,343,361,1942,1952,2898,2905,2897]
TAGS=['2022_fast_failure']*3+['2024_fast_failure']*2+['2026_fast_failure']*2+['2022_closed_tail30']*2+['2024_09_10_closed_tail30']*2+['2026_closed_tail30']*2+['prior_Jiangfeng_control']
END='2026-05-15';Z=D(0);TOL=D('1e-8')
sources={};unknowns=[];checks=Counter()
def hashfile(p,expected=None):
 p=Path(p);h=hashlib.sha256(p.read_bytes()).hexdigest()
 if str(p) in sources:assert sources[str(p)]['sha256']==h,('source changed during analysis',p)
 sources[str(p)]={'sha256':h,**({'expected_sha256':expected,'matches_expected':h==expected} if expected else {})}
 if expected is not None:assert h==expected,('source hash drift',p)
 return h
def read(p,expected=None):hashfile(p,expected);return json.loads(Path(p).read_text())
def para(p,expected=None):hashfile(p,expected);return pd.read_parquet(p)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
 if isinstance(x,(list,tuple,set)):return [clean(v)for v in x]
 if isinstance(x,D):return str(x)
 if isinstance(x,(pd.Timestamp,Path)):return str(x)
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
 return x
def dump(name,x):
 with (O/name).open('x')as h:json.dump(clean(x),h,ensure_ascii=False,indent=2,allow_nan=False)
def csv(name,rows):
 assert not (O/name).exists(),('never overwrite',name)
 pd.DataFrame(clean(rows)).to_csv(O/name,index=False)
def j(x):return json.dumps(clean(x),ensure_ascii=False,separators=(',',':'))
def day(x):return str(x)[:10]
def dec(x):return D(str(x))
def prevfact(f,d):return f.iloc[f.index.searchsorted(pd.Timestamp(d),side='right')-1]
def name_for(sid):return {'000877.SZ':'天山股份','000963.SZ':'华东医药','002050.SZ':'三花智控','601918.SH':'新集能源','000651.SZ':'格力电器','002195.SZ':'岩山科技','600498.SH':'烽火通信','300034.SZ':'钢研高纳','600366.SH':'宁波韵升','300442.SZ':'润泽科技','601881.SH':'中国银河','002716.SZ':'湖南白银','600482.SH':'中国动力','300666.SZ':'江丰电子'}[sid]
def main():
 assert O==R/'mobile_first_probe_protection_v1/case_trace'
 assert not (O/'SUMMARY.json').exists(),'No overwrite or blind rerun'
 hashfile(__file__)
 # Cohort was frozen by parent before this script. It deliberately uses historical outcome labels.
 dump('FROZEN_CASES.json',dict(round_ids=IDS,tags=dict(zip(IDS,TAGS)),scope='NOACT original empty-stock MOBILE first layers only',selection='Prior historical labels, not out-of-sample, no case replacement',account_runs=0,indicator_recomputations=0,new_strategy_tests=0,window_after_exit='First 20 COMMON account closes strictly after actual first-layer exit, capped at 2026-05-15; exit-day close separate',further_thresholds=None))
 out_hash=read(A/'run/OUTPUT_HASHES.json');runtime=read(A/'run/RUNTIME_DEPENDENCY_FREEZE.json')
 ap=A/'run/pair/NOACT.json.gz';hashfile(ap,out_hash['pair/NOACT.json.gz']);account=json.load(gzip.open(ap,'rt'))
 for p in [A/'code/run_act_only.py',A/'code/ablation_support.py',A/'code/continuous_execution.py',R/'account_comparison_continuous_v1/inputs/continuous_inputs.py',W/'case-stage-ledger-20261031/v3/joint_v3.py',W/'pvr-slot1-native-readiness-20261101/native_rank.py',Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py'),Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/engine.py'),Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py')]:hashfile(p,runtime.get(str(p)))
 rp=A/'analysis/STOCK_ROUNDS.csv';lp=A/'analysis/LAYER_ATTRIBUTION.csv';hashfile(rp);hashfile(lp)
 rounds=pd.read_csv(rp);layers_df=pd.read_csv(lp);no=rounds[rounds.account.eq('NOACT')].copy()
 selected=no[no.round_id.isin(IDS)].set_index('round_id').loc[IDS]
 assert len(selected)==14 and selected.initial_kind.eq('add').all() and selected.closed.notna().all()
 lids=set(int(x)for x in selected.initial_layer);sids=set(selected.sid)
 original_layers={x['id']:x for x in account['layers']};buys={x['layer']:x for x in account['trades']if x['side']=='buy'}
 case_by_lid={int(r.initial_layer):int(rid)for rid,r in selected.iterrows()}
 daily={}
 dp=A/'run/pair/daily.jsonl.gz';hashfile(dp,out_hash['pair/daily.jsonl.gz'])
 for line in gzip.open(dp,'rt'):
  x=json.loads(line)
  if x['account']=='NOACT':daily[day(x['at'])]={'layers':{y['id']:y for y in x['layers']if y['sid']in sids},'positions':{k:v for k,v in x['positions'].items()if k in sids},'pending_sells':x['pending_sells']}
 cal=sorted(daily);assert len(cal)==1054 and cal[-1]==END
 opp={};fund=defaultdict(list)
 for basename,target in [('opportunities',opp),('funding',fund)]:
  p=A/f'run/pair/{basename}.jsonl.gz';hashfile(p,out_hash[f'pair/{basename}.jsonl.gz'])
  for line in gzip.open(p,'rt'):
   x=json.loads(line)
   if x['account']!='NOACT' or x['sid']not in sids:continue
   d=x.get('day',day(x.get('at','')))
   if basename=='opportunities':target[(x['sid'],d)]=x
   else:target[(x['sid'],d)].append(x)
 manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
 receipt_refs=defaultdict(list)
 for mp in [W/'2022-normal-reference-20261031/inputs/MANIFEST.json',W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/MANIFEST.json')]:
  for x in read(mp):
   if x['sid']in sids and not x['industry']:receipt_refs[x['sid']].append((x['output_path'],x['output_sha256']))
 for x in read(R/'account_comparison_continuous_v1/inputs/H1_MANIFEST.json'):
  if x['sid']in sids and not x['industry']:receipt_refs[x['sid']].append((x['receipt_path'],x['receipt_sha256']))
 data={}
 for sid in sids:
  m=manifest[sid];f=para(m['refs']['facts'],m['output_sha256'][m['refs']['facts']]);cp=para(m['refs']['CP1'],m['output_sha256'][m['refs']['CP1']]);ci=para(m['refs']['CP1_input'],m['output_sha256'][m['refs']['CP1_input']])
  sp=next(p for p in m['source_sha256']if p.endswith('/signal.parquet'));p=para(sp,m['source_sha256'][sp])
  f=f.loc[:END];cp=cp.loc[:END];ci=ci.loc[:END]
  assert f.index.equals(cp.index)and f.index.equals(ci.index)
  for k in ['close','i_target','i_floor','segment_id']:pd.testing.assert_series_equal(f[k],ci[k],check_names=False,check_exact=True,check_dtype=False)
  receipts={}
  for path,h in receipt_refs[sid]+[(m['refs']['receipts'],m['output_sha256'][m['refs']['receipts']])]:
   for x in read(path,h):
    d=x['confirmed_day']
    if '2022-01-01'<=d<=END:assert d not in receipts;receipts[d]=x
  expected={str(t.date())for t in cp.loc['2022-01-01':END].index[cp.loc['2022-01-01':END].receipt.eq(True)]}
  assert set(receipts)==expected,(sid,'receipt dates')
  checks['receipt_union_exact_stocks']+=1
  data[sid]=(f,cp,p,receipts)
 # Parent identified 577 as a typo. Verify only the supplied saved boundary, not a new population experiment.
 qa=read(R/'act_entry_research_synthesis_v1/FAST_FAILURE_SOURCE_AND_QA.json')
 for p,h in qa['sources'].items():hashfile(p,h)
 ag=R/'act_entry_research_synthesis_v1/FAST_FAILURE_INITIAL_EXIT_REASON.csv';hashfile(ag,qa['output_sha256']);boundary=pd.read_csv(ag)
 dump('SOURCE_PREFLIGHT.json',dict(passed=True,selected_rounds=14,source_hashes_checked=len(sources),receipt_union_exact_stocks=14,account_complete_through=END,prior_577='Parent clarified typo; actual frozen group is 578.',frozen_group_source_rows=boundary.to_dict('records'),source_reuse_only=True))
 dailyrows=[];summaries=[];raiserows=[];trade_rows=[];postrows=[];lossrows=[];eventrows=[]
 for rid,r in selected.iterrows():
  sid=r.sid;lid=int(r.initial_layer);b=buys[lid];layer=original_layers[lid];f,cp,p,receipts=data[sid]
  initial=dec(b['floor']);entry=day(b['at']);signal=day(b['signal_at']);exitday=day(layer['closed']);q0=int(b['shares'])
  tr=[(t,part)for t in account['trades']if t['side']=='sell'for part in t['parts']if part['layer']==lid]
  exits=[x for x in account['audit']if x.get('kind')=='pilot_layer_exit'and lid in x.get('layers',[])]
  assert exits and tr and day(tr[-1][0]['at'])==exitday
  firstexit=exits[0];trigger=day(firstexit['at']);reason=firstexit['reason']
  assert reason in ['CP1_add_protection','I_structure_exit']
  assert len(tr)==1,('multiple first-layer sells need extended allocation',rid)
  assert int(tr[0][1]['shares'])==q0 and int(r.split_events)==0,('split-aware generalization required',rid)
  checks['selected_no_split_exact_qty']+=1
  assert layer['reason']==reason and all(part['reason']==reason for _,part in tr),('reason rewrite',rid)
  checks['first_exit_reason_matches_final_layer_and_sell']+=1
  sigrec=receipts[signal];sigfr=f.loc[signal];sigcp=cp.loc[signal]
  assert initial==max(dec(sigfr.i_floor),dec(sigcp.candidate))
  jr=[x for x in account['journal']if x.get('kind')=='real_buy_fill'and x.get('layer')==lid]
  assert len(jr)==1 and jr[0]['CP1_id']==sigrec['receipt_id']
  round_lids=json.loads(r.layer_ids);adds=[buys[k]for k in round_lids if k!=lid]
  # Original receipt interval and initial floor are immutable. Their coordinates are adjusted-price.
  prior=str(f.index[f.index.searchsorted(pd.Timestamp(signal))-1].date())
  days=sorted(set([prior]+[d for d in cal if signal<=d<=exitday]))
  old=initial;last_src='BUY_initial';last_day=signal;last_formation=sigrec['formation_start_exclusive'];pending=False;triggerrow=None
  for d in days:
   observed=pd.Timestamp(d)in f.index;fr=prevfact(f,d);cr=cp.loc[d]if pd.Timestamp(d)in cp.index else None;pr=p.loc[d]if pd.Timestamp(d)in p.index else None;receipt=receipts.get(d)
   factday=str(fr.name.date());factor=dec(fr.factor);held=entry<=d<exitday
   saved=daily.get(d,{}).get('layers',{}).get(lid);before=old if held or (d==exitday and pending)else None
   row={'round_id':int(rid),'tag':dict(zip(IDS,TAGS))[rid],'sid':sid,'name':name_for(sid),'layer_id':lid,'day':d,'phase':'SIGNAL_PREV'if d==prior else 'SIGNAL'if d==signal else 'ACTUAL_EXIT_OPEN'if d==exitday else 'PENDING_EXIT'if pending else 'HELD_CLOSE','observed_fact_today':observed,'fact_source_day':factday,'i_target':bool(fr.i_target),'i_buy_latest_fact':bool(fr.i_buy),'fresh_i_buy_today':bool(observed and fr.i_buy),'I_line_adjusted':fr.i_floor,'I_line_raw_asof_factor':dec(fr.i_floor)/factor if pd.notna(fr.i_floor)else None,'check_close_adjusted':fr.close,'check_close_raw':fr.raw_close,'factor_asof_close':factor,'raw_open_today':pr.raw_open if pr is not None else None,'raw_close_today':pr.raw_close if pr is not None else None,'CP_receipt_today':bool(cr.receipt)if cr is not None else False,'CP_candidate_adjusted':cr.candidate if cr is not None else None,'CP_receipt_id':receipt.get('receipt_id')if receipt else None,'CP_formation_start_exclusive':receipt.get('formation_start_exclusive')if receipt else None,'CP_formation_end_inclusive':receipt.get('formation_end_inclusive')if receipt else None,'CP_trace_unknown_count':len(receipt.get('trace_unknown',[]))if receipt else None,'immutable_BUY_initial_floor_adjusted':initial,'initial_floor_raw_asof_factor':initial/factor,'effective_floor_before_check_adjusted':before,'floor_provenance_before_check':last_src,'floor_provenance_day_before_check':last_day,'floor_formation_start_before_check':last_formation,'first_layer_qty_after_open':q0 if held else 0,'first_layer_qty_at_close_original':saved['qty']if saved else 0,'all_round_buy_layer_ids':j(round_lids),'additional_buys_today':j([x for x in adds if day(x['at'])==d]),'all_held_layers_at_close':j([x for x in daily.get(d,{}).get('layers',{}).values()if x['sid']==sid]),'check_clock':'I/ACT precedence, then compare close <= old floor; only if not hit update max(old,I,CP); after exit pending CP checks skipped','floor_update_sources':None,'CP_protection_checked':False,'CP_trigger':False,'I_structure_trigger':False}
   if held:
    assert saved is not None,('missing original held-layer daily',rid,d)
    if not bool(fr.i_target):
     row['I_structure_trigger']=True;pending=True
    elif not pending:
     row['CP_protection_checked']=True
     if dec(fr.close)<=old:
      row['CP_trigger']=True;pending=True
     else:
      middle=old;src=[]
      if pd.notna(fr.i_floor)and dec(fr.i_floor)>middle:middle=dec(fr.i_floor);src.append('I')
      if cr is not None and bool(cr.receipt)and dec(cr.candidate)>middle:middle=dec(cr.candidate);src.append('CP1')
      if src:
       if src[-1]=='CP1':assert receipt is not None
       rr={'round_id':int(rid),'sid':sid,'layer_id':lid,'day':d,'old_floor_adjusted':old,'new_floor_adjusted':middle,'intermediate_I_floor_adjusted':fr.i_floor,'CP_candidate_adjusted':cr.candidate if cr is not None else None,'sources':'+'.join(src),'final_source':src[-1],'receipt_id':receipt.get('receipt_id')if receipt else None,'formation_start_exclusive':receipt.get('formation_start_exclusive')if receipt else None,'formation_strictly_after_entry':bool(receipt and receipt['formation_start_exclusive']>=entry),'check_close_adjusted':fr.close}
       raiserows.append(rr);old=middle;last_src=src[-1];last_day=d;last_formation=receipt['formation_start_exclusive']if last_src=='CP1'else None;row['floor_update_sources']='+'.join(src)
    row['effective_floor_after_processing_adjusted']=old;row['original_daily_saved_floor_adjusted']=saved['floor'];row['floor_log_match']=abs(old-dec(saved['floor']))<D('1e-10');assert row['floor_log_match'],('floor differs',rid,d,old,saved['floor']);checks['daily_floor_matches']+=1
   else:row['effective_floor_after_processing_adjusted']=None;row['original_daily_saved_floor_adjusted']=saved['floor']if saved else None;row['floor_log_match']=None
   row['pending_exit_after_close']=pending if d<exitday else False
   row['initial_floor_breached_at_check']=dec(fr.close)<=initial if held else None
   if d==trigger:
    assert (row['CP_trigger']if reason=='CP1_add_protection'else row['I_structure_trigger'])
    triggerrow=dict(row)
   dailyrows.append(row)
  assert triggerrow is not None
  st,part=tr[0];sq=dec(part['shares']);exitprice=dec(st['price']);exitraw=dec(st['raw_open']);sellgross=sq*exitprice;sellfee=dec(st['fees_cny'])*sq/dec(st['shares']);sellnet=dec(part['net_cash'])
  assert abs(sellgross-sellfee-sellnet)<TOL
  cash=-dec(b['gross_cny'])-dec(b['fees_cny'])+sellnet;div=dec(layer['dividend']);pnl=cash+div
  assert abs(cash-dec(layer['cash']))<TOL
  source_layer=layers_df[(layers_df.account=='NOACT')&(layers_df.id==lid)].iloc[0];assert abs(pnl-dec(source_layer.pnl))<D('1e-6')
  for t in [b,st]:
   pr=p.loc[day(t['at'])];assert dec(pr.raw_open)==dec(t['raw_open']);mult=D('1.0005')if t['side']=='buy'else D('.9995');assert dec(t['price'])==dec(t['raw_open'])*mult
   checks['raw_fill_price_exact']+=1
  ef=dec(triggerrow['effective_floor_before_check_adjusted']);tf=dec(triggerrow['factor_asof_close']);rawfloor=ef/tf;close=dec(triggerrow['check_close_raw'])
  nextcommon=cal[cal.index(trigger)+1];aftertrigger=[str(t.date())for t in p.loc[trigger:exitday].index if str(t.date())>trigger and pd.notna(p.loc[t,'raw_open'])and p.loc[t,'raw_open']>0]
  firstobserved=aftertrigger[0];firstop=dec(p.loc[firstobserved,'raw_open']);missing=[d for d in cal if trigger<d<firstobserved and pd.Timestamp(d)not in p.index]
  # Full loss bridge, positive means loss. No alternative exit or investment is simulated.
  components={'entry_to_effective_floor':dec(b['gross_cny'])-sq*rawfloor,'effective_floor_to_trigger_close':sq*(rawfloor-close),'trigger_close_to_first_observed_open':sq*(close-firstop),'first_observed_open_to_actual_exit_open':sq*(firstop-exitraw),'sell_slippage':sq*(exitraw-exitprice),'buy_fees':dec(b['fees_cny']),'allocated_sell_fees':sellfee,'negative_dividend_accrual':-div}
  bridge=sum(components.values(),Z);assert abs(bridge+pnl)<D('1e-7'),('loss bridge',rid,bridge,pnl)
  split_events=[x for x in account['audit']if x.get('kind')in ['split','split_fraction_floor_proxy']and x.get('sid')==sid and entry<=day(x.get('at',''))<=exitday];assert not split_events
  lr={'round_id':int(rid),'sid':sid,'first_layer_id':lid,'first_layer_net_pnl':pnl,'net_loss_signed':-pnl,'net_loss_bridge':bridge,'residual':bridge+pnl,'buy_gross':b['gross_cny'],'buy_fees':b['fees_cny'],'exit_gross_allocated':sellgross,'exit_fees_allocated':sellfee,'dividend_accrual':div,'qty_same_at_buy_and_exit':q0,'trigger_floor_adjusted':ef,'trigger_factor':tf,'trigger_floor_raw':rawfloor,'trigger_raw_close':close,'immediate_next_common_open_day':nextcommon,'first_observed_open_day':firstobserved,'actual_exit_open_day':exitday,'immediate_next_common_open_missing':firstobserved!=nextcommon,'missing_common_stock_bar_days':j(missing),'gap_interpretation':'FIRST_OBSERVED_OPEN_GAP; immediate next common OPEN unknown'if firstobserved!=nextcommon else 'NEXT_COMMON_OPEN_GAP','split_events':0,'factor_changed_during_hold':p.loc[entry:exitday,'adjustment_factor'].nunique()>1,**components}
  lossrows.append(lr)
  for t in [b]+[x for x in adds]+[st]:
   prts=t.get('parts',[]);isfirst=t.get('layer')==lid or any(z['layer']==lid for z in prts)
   trade_rows.append({'round_id':int(rid),'sid':sid,'first_layer':isfirst,'at':t['at'],'side':t['side'],'layer_id':t.get('layer'),'shares_total_fill':t['shares'],'price':t['price'],'raw_open':t['raw_open'],'gross_total_fill':t['gross_cny'],'fees_total_fill':t['fees_cny'],'parts':j(prts),'initial_buy_floor':t.get('floor'),'signal_at':t.get('signal_at'),'reason':t['reason']})
  # Source event list includes actual dividends, pending exits, fills and no synthesized decisions.
  for x in account['audit']:
   xs=x.get('sid',x.get('receivable',{}).get('security_id'));xd=day(x.get('at',x.get('receivable',{}).get('ex_at','')))
   if xs==sid and entry<=xd<=exitday and x.get('kind')in ['dividend_accrual','split','split_fraction_floor_proxy','pilot_layer_exit','pilot_buy_rejected']:eventrows.append({'round_id':int(rid),'sid':sid,'source_event':j(x)})
  post=[d for d in cal if d>exitday][:20];assert len(post)<=20
  for offset,d in enumerate([exitday]+post):
   fr=prevfact(f,d);obs=pd.Timestamp(d)in f.index;cr=cp.loc[d]if pd.Timestamp(d)in cp.index else None;receipt=receipts.get(d);op=opp.get((sid,d));assert op is not None
   laterbuys=[t for t in account['trades']if t['side']=='buy'and t['security_id']==sid and day(t['at'])==d and t['at']>st['at']]
   rowsfund=fund.get((sid,d),[]);roles=op['roles'];bars=op['barriers'];legal=bool(roles and not bars)
   postrows.append({'round_id':int(rid),'sid':sid,'name':name_for(sid),'day':d,'common_close_number_after_exit':offset,'is_exit_day_close_separate':offset==0,'stock_bar_observed_today':obs,'fact_source_day':str(fr.name.date()),'i_target':bool(fr.i_target),'fresh_i_buy_today':bool(obs and fr.i_buy),'I_line_adjusted':fr.i_floor,'CP_receipt_today':bool(cr.receipt)if cr is not None else False,'CP_candidate_adjusted':cr.candidate if cr is not None else None,'receipt_id':receipt.get('receipt_id')if receipt else None,'formation_start_exclusive':receipt.get('formation_start_exclusive')if receipt else None,'original_core_Q':op['core_Q'],'original_mobile_Q':op['mobile_Q'],'original_held_at_planning':op['held'],'original_roles':j(roles),'original_barriers':j(bars),'original_signal_side_legal':legal,'original_opportunity':j(op),'original_funding_at_this_OPEN':j(rowsfund),'actual_later_buys_at_this_OPEN':j(laterbuys),'reentry_contract':'Original account observation only. Does not establish changed-exit cash/risk feasibility or permit stale CP reuse.'})
  later=[x for x in postrows if x['round_id']==int(rid)and not x['is_exit_day_close_separate']]
  additional_during_first=[x for x in adds if day(x['at'])<=exitday]
  sr={'round_id':int(rid),'tag':dict(zip(IDS,TAGS))[rid],'sid':sid,'name':name_for(sid),'first_layer_id':lid,'signal_day':signal,'entry_day':entry,'trigger_day':trigger,'exit_day':exitday,'reason':reason,'initial_buy_floor_adjusted':initial,'trigger_effective_floor_adjusted':ef,'trigger_close_adjusted':triggerrow['check_close_adjusted'],'initial_floor_breached':dec(triggerrow['check_close_adjusted'])<=initial,'raised_floor_only':reason=='CP1_add_protection'and dec(triggerrow['check_close_adjusted'])>initial,'I_valid_at_trigger':bool(triggerrow['i_target']),'last_floor_source':triggerrow['floor_provenance_before_check'],'last_floor_day':triggerrow['floor_provenance_day_before_check'],'last_floor_formation_start':triggerrow['floor_formation_start_before_check'],'last_CP_formation_after_entry':triggerrow['floor_provenance_before_check']=='CP1'and triggerrow['floor_formation_start_before_check']>=entry,'raise_count':sum(x['round_id']==int(rid)for x in raiserows),'initial_receipt_id':sigrec['receipt_id'],'initial_CP_formation_start':sigrec['formation_start_exclusive'],'buy_price':b['price'],'buy_raw_open':b['raw_open'],'buy_shares':q0,'buy_fees':b['fees_cny'],'sell_price':st['price'],'sell_raw_open':st['raw_open'],'sell_shares_first_layer':part['shares'],'sell_fees_first_layer':sellfee,'T1_no_same_day_sale':exitday>entry,'trigger_same_day_as_entry':trigger==entry,'immediate_next_common_open':nextcommon,'first_observed_open_after_trigger':firstobserved,'missing_common_stock_bars_before_exit':j(missing),'first_layer_net_pnl':pnl,'round_net_pnl':r.pnl,'additional_buy_layers_before_first_exit':j([x['layer']for x in additional_during_first]),'post_exit_common_closes':len(post),'post_exit_last_day':post[-1]if post else None,'fresh_CP_days':j([x['day']for x in later if x['CP_receipt_today']]),'fresh_I_days':j([x['day']for x in later if x['fresh_i_buy_today']]),'original_signal_side_legal_days':j([x['day']for x in later if x['original_signal_side_legal']]),'actual_rebuy_days':j([x['day']for x in later if json.loads(x['actual_later_buys_at_this_OPEN'])]),'source_status':'Original logs plus frozen facts and canonical receipts, no strategy simulation'}
  sr.update(signal_I_floor_adjusted=dec(sigfr.i_floor),signal_CP_candidate_adjusted=dec(sigcp.candidate),initial_floor_dominant_source='CP1' if dec(sigcp.candidate)>dec(sigfr.i_floor) else 'I' if dec(sigfr.i_floor)>dec(sigcp.candidate) else 'TIE',signal_CP_minus_I_adjusted=dec(sigcp.candidate)-dec(sigfr.i_floor),entry_factor=dec(p.loc[entry,'adjustment_factor']),signal_I_floor_raw_at_entry_factor=dec(sigfr.i_floor)/dec(p.loc[entry,'adjustment_factor']),signal_CP_floor_raw_at_entry_factor=dec(sigcp.candidate)/dec(p.loc[entry,'adjustment_factor']),signal_CP_minus_I_raw_at_entry_factor=(dec(sigcp.candidate)-dec(sigfr.i_floor))/dec(p.loc[entry,'adjustment_factor']),entry_price_to_original_I_floor_per_share=dec(b['price'])-dec(sigfr.i_floor)/dec(p.loc[entry,'adjustment_factor']),entry_price_to_original_CP_floor_per_share=dec(b['price'])-initial/dec(p.loc[entry,'adjustment_factor']))
  window_end=post[-1] if post else exitday
  iscan=[d for d in cal if entry<=d<=window_end]
  iinvalid=[d for d in iscan if not bool(prevfact(f,d).i_target)]
  sr.update(first_I_invalid_after_entry_through_window=iinvalid[0] if iinvalid else None,first_I_invalid_strictly_after_exit_in_20=next((d for d in post if not bool(prevfact(f,d).i_target)),None),I_valid_at_end_of_20_common_closes=bool(prevfact(f,window_end).i_target),I_continuously_valid_from_original_trigger_through_window=all(bool(prevfact(f,d).i_target) for d in iscan if d>=trigger),I_path_is_readonly_not_alternative_exit='No hypothetical realizable returns or stitched new rounds; migrating first layer to I requires new I-line risk sizing, not retaining original CP-sized shares.')
  summaries.append(sr)
  print('CASE',rid,sid,reason,'initial_breached',sr['initial_floor_breached'],'last',sr['last_floor_source'],sr['last_floor_day'],'first_net',pnl,flush=True)
 for name,rows in [('CASE_SUMMARY.csv',summaries),('CASE_DAILY.csv',dailyrows),('FLOOR_RAISES.csv',raiserows),('ACTUAL_TRADES.csv',trade_rows),('LOSS_BRIDGE.csv',lossrows),('POST_EXIT_20_COMMON_CLOSES.csv',postrows),('SOURCE_EVENTS.csv',eventrows)]:csv(name,rows)
 fast=[x for x in summaries if 'fast_failure'in x['tag']]
 summary={'status':'COMPLETE_SOURCE_ONLY_FIXED14','case_count':14,'account_runs':0,'indicator_recomputations':0,'new_strategy_tests':0,'source_hashes_checked':len(sources),'checks':dict(checks),'fast_failure_count':len(fast),'fast_initial_floor_already_breached':sum(x['initial_floor_breached']for x in fast),'fast_raised_floor_only':sum(x['raised_floor_only']for x in fast),'Jiangfeng_initial_floor_already_breached':next(x['initial_floor_breached']for x in summaries if x['round_id']==2897),'all_CP_exit_I_still_valid':all(x['I_valid_at_trigger']for x in summaries if x['reason']=='CP1_add_protection'),'I_structure_exit_case':[x['round_id']for x in summaries if x['reason']=='I_structure_exit'],'daily_floor_unknowns':0,'missing_market_data_case':[x['round_id']for x in summaries if json.loads(x['missing_common_stock_bars_before_exit'])],'loss_bridge_max_abs_residual':max(abs(dec(x['residual']))for x in lossrows),'source_snapshot_timing':'Hashes verified against existing source manifests; this small report is NOT a retrospective pre-outcome sample freeze.','selection_limits':'Fixed 14 history-labelled mechanism-development cases; no population efficacy, win-rate or out-of-sample inference.','critical_result':'6/7 fast-failure cases and Jiangfeng already broke immutable initial BUY floor; changing later floor-raising alone cannot explain them. Gree 1542 raised floor from fresh CP formed after entry.','counterfactual_boundary':'Original post-exit admission/funding/rebuys are original-account observations, not changed-exit counterfactual cash/risk feasibility. Missing immediate next common opening quote is UNKNOWN, not assumed zero.','prior_577':'Correct frozen population boundary is 578, parent typo corrected, no new all-population experiment.','unknowns':unknowns}
 dump('SUMMARY.json',summary);dump('CASE_SUMMARY.json',summaries);dump('LOSS_BRIDGE.json',lossrows)
 # Re-read hashes to verify no source mutation between initial reads and completion.
 for path,info in list(sources.items()):assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==info['sha256'],('source changed',path)
 dump('SOURCE_HASHES.json',sources)
 lines=['# Fixed-14 MOBILE first-layer source trace','','This is a fixed historical-label mechanism development set, not an out-of-sample test. No account, E0/I/CP calculation, strategy, threshold search or alternative consumer was run.','','## Main facts','- 6 of 7 fast failures already breached the immutable BUY floor at the actual trigger; Gree 1542 is the sole raised-floor-only fast failure. Jiangfeng 2897 also breached its unchanged initial floor.','- Gree last raise was a fresh CP receipt formed during its own holding period; verify exact receipt start in CASE_SUMMARY and FLOOR_RAISES.','- All 13 CP-protection exits had I still valid at their trigger. Ningbo 361 instead had I invalid and an I_structure_exit.','- All saved held-day floors reproduce exactly by old-floor test before same-day max(I, CP) updates. The calculation does not rerun account behavior.','- Jiangfeng had no observed stock bars between 2026-01-29 and 2026-02-06. Its immediate next common open is UNKNOWN; do not describe its 2/6 fill as the 1/30 next-open gap.','','## Cash and timing','- LOSS_BRIDGE is a signed arithmetic loss decomposition using original per-layer net-cash allocation: entry gross to trigger-day effective raw floor; floor to trigger raw close; close to first observed next open; any first-open-to-actual-fill drift; sale slippage; buy/sell fees; minus dividend accrual. It sums to negative first-layer net P&L.','- Adjusted floor is divided by trigger-date factor, never compared directly to raw traded prices. These 14 selected first layers have no split and retain exact buy-to-sell share quantity. Corporate-action factor changes and dividends are explicit.','- The actual sell allocation for 2898 uses 2,200/2,800 of the combined fill fees; the additional 600-share layer is not treated as first-layer cash.','- No same-day sells occurred. A trigger on the buy day (2891) still executes no sooner than next OPEN.','','## Follow-up evidence','- POST_EXIT_20_COMMON_CLOSES includes exit-day close separately as offset 0, then exactly min(20, remaining observation period) COMMON closes. Stock missing bars are explicit and fresh I requires a same-day observed fact.','- Fresh CP/I, original opportunity barriers, original OPEN funding and actual later BUY fills are reported. Their funding history cannot be reused as counterfactual feasibility after changing an exit. Exit-followed-by-rally is not labeled a mistaken sale.','','## Boundaries','- The previously stated 577 was a typo; the parent-supplied saved group boundary is 578 CP-initial-layer exits among closed negative EXIT_BEFORE20 rounds. This report does not expand to new all-population simulation.','- SOURCE_PREFLIGHT and SOURCE_HASHES bind reused sources. CASE_DAILY has exact floor provenance; FLOOR_RAISES lists each raise with canonical receipt formation start.','','## Cases']
 for x in summaries:lines.append(f"- {x['round_id']} {x['sid']}: {x['reason']}; initial floor breached={x['initial_floor_breached']}; I valid={x['I_valid_at_trigger']}; last floor={x['last_floor_source']} {x['last_floor_day']}; first-layer net={x['first_layer_net_pnl']}.")
 with(O/'READOUT.md').open('x')as h:h.write('\n'.join(lines)+'\n')
 outputs={str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(O.iterdir())if p.is_file()}
 dump('OUTPUT_HASHES.json',outputs)
 print(j(summary),flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  fail=O/'FAILURE.txt'
  if not fail.exists():fail.write_text(traceback.format_exc())
  raise
