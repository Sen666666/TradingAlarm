"""Six fixed stocks, seven actual ACT cycles; original G1 reproduction, no trading engine."""
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict
from decimal import Decimal as D
import sys,json,csv,gzip,time,hashlib
import numpy as np
import pandas as pd
T=time.monotonic();O=Path(__file__).resolve().parent;R=Path('/Users/bytedance/Documents/ChatGPT/money');RR=R/'research_rounds';BASE=RR/'pvr-local-finite-capital-20261029/baseline/accounts-v2';P=O.parent/'act-loss-facts-20261030';B5=RR/'pv-strength-b5-20261025/code';G1=RR/'b5-g1-20261025/code'
def read(p):return json.loads(Path(p).read_text())
def csvrows(p):return list(csv.DictReader(Path(p).open()))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def export(n,rr):pd.DataFrame(rr).to_csv(O/n,index=False)
IDs={'605118.SH':'力鼎光电','301486.SZ':'致尚科技','688143.SH':'长盈通','601138.SH':'工业富联','688498.SH':'源杰科技','002130.SZ':'沃尔核材'}
snapshot=Path(read(RR/'pvr-act-comparison-20261027/input.json')['snapshot']['path']);cycles=[x for x in csvrows(P/'actual-cycles.csv') if x['symbol'] in IDs];assert len(cycles)==7 and {x['symbol'] for x in cycles}==set(IDs)
for x in cycles:assert x['name']==IDs[x['symbol']]
sys.path[:0]=[str(B5),str(G1),str(RR/'pv-participation-response-20261020/code')]
from data_utils import eligible_prices
from evidence import build_evidence
from policy import e0_policy
from grade import classify
from policies_g1 import project
proof=read(RR/'ph1-cross-sector-20261028/event-validation.json');assert proof['passed']
for p,h in proof['source_sha256'].items():assert sha(p)==h,p
files=[Path(__file__),P/'actual-cycles.csv',P/'actual-holding-close-paths.csv',O.parent/'old-side-exit-all69-20261030/FROZEN_69_CYCLES.csv',BASE/'I__S0_base.json',BASE/'daily.jsonl.gz',B5/'evidence.py',B5/'policy.py',B5/'arithmetic.py',G1/'grade.py',G1/'policies_g1.py',RR/'pv-strength-b4-20261025/code/model.py']
for s in IDs:files.extend([snapshot/'signals'/f'{s}.parquet',snapshot/'facts'/f'{s}.parquet'])
identity={str(p):sha(p) for p in files};save('INPUT_IDENTITY.json',dict(at=datetime.now(timezone.utc).isoformat(),symbols=IDs,cycle_ids=[x['cycle_id'] for x in cycles],definition='Each cycle from original buy decision: latch first observed S21=+1 and mu21>0; candidate only held, original I/E0 valid, ACT on, no original sell, S21=-1 and mu21<0. Original floor/ACT priority. No economic action.',before_candidate_inspection=True,sha256=identity))
frames={};checks=[];(O/'fields').mkdir(exist_ok=False)
for s in IDs:
 sig=pd.read_parquet(snapshot/'signals'/f'{s}.parquet');parent=pd.read_parquet(snapshot/'facts'/f'{s}.parquet');f=eligible_prices(sig)[['open','high','low','close','volume','segment_id']].copy();f['valid_price_observation']=True;f['valid_strength_observation']=np.isfinite(f.volume)&f.volume.gt(0);assert f.index.equals(parent.index),(s,'history clock differs')
 e,journal=build_evidence(f);g,_=classify(e);e['decline_candidate']=False;b,_=e0_policy(e);ip=project(e,b,g,'G1_I')
 compare={'close':f.close,'segment_id':f.segment_id,'e0_target':b.target,'e0_floor':b.floor,'e0_ready':b.ready,'i_target':ip.target,'i_floor':ip.floor,'i_buy':ip.buy_event,'g_grade':g.grade,'g_fresh_up':g.fresh_up,'g_acute_down':g.acute_down,'g_ready':g.ready}
 for name,value in compare.items():np.testing.assert_array_equal(value.to_numpy(float),parent[name].to_numpy(float),err_msg=s+'/'+name)
 z=pd.DataFrame(index=f.index);z['symbol']=s;z['close']=f.close;z['segment_id']=f.segment_id
 for col in ['strength_mu21','strength_mu5','strength_S21','strength_S63','strength_acute_up','event']:z[col.replace('strength_','')]=e[col]
 for col in ['grade','ready','fresh_up','acute_down','reason','proposal']:z['g_'+col]=g[col]
 z['base_warm']=(z.mu21>0)&(z.S21==1);z['launch']=(z.acute_up==1)&(z.event==1)&(z.mu5>0)
 for k in ['e0_target','e0_floor','i_target','i_floor','i_buy']:z[k]=compare[k]
 z.to_parquet(O/'fields'/f'{s}.parquet');frames[s]=z;checks.append(dict(symbol=s,rows=len(f),history_start=str(f.index[0].date()),history_end=str(f.index[-1].date()),exact_parent_columns=list(compare)));print(json.dumps(dict(stage='parent_outputs_exact',symbol=s,rows=len(f),seconds=time.monotonic()-T)),flush=True)
 del e,journal,g,b,ip
save('REPRODUCTION_VERIFICATION.json',dict(passed=True,symbols=6,cycles=7,complete_source_history=True,parent_checks=checks,indicators_reproduced_only_fixed6=True,trade_engines_run=0,seconds=time.monotonic()-T))
# Only after all six exact matches: inspect v0 states on fixed actual holding cycles.
oa=read(BASE/'I__S0_base.json')['audit_log'];cp={x['at'][:10]:x for x in oa if x['kind']=='risk_checkpoint'}
with gzip.open(BASE/'daily.jsonl.gz','rt') as f:daily={x['at'][:10]:x for line in f if (x:=json.loads(line))['account']=='I__S0_base'}
hp=defaultdict(list)
for x in csvrows(P/'actual-holding-close-paths.csv'):hp[x['cycle_id']].append(x)
warnings={x['cycle_id']:x for x in csvrows(O.parent/'old-side-exit-all69-20261030/FROZEN_69_CYCLES.csv')};rows=[];details=[]
def comparison(day,other):return None if not day or not other else 'before' if day<other else 'same' if day==other else 'after'
for c in cycles:
 key=c['cycle_id'];s=c['symbol'];df=frames[s];start=c['entry_decision'][:10];entry=c['entry_at'][:10];stop=c['exit_request'][:10];er=df.loc[pd.Timestamp(start)];assert bool(er.i_buy),(key,'actual buy decision not original I event');firstmain=None;firstraw=None;firstcandidate=None;missing=[];local=[]
 for day in sorted(d for d in daily if start<=d<=stop):
  t=pd.Timestamp(day);held=int(daily[day]['positions'].get(s,0))>0;pending=s in daily[day]['pending_sells']
  if t not in df.index:missing.append(day);continue
  z=df.loc[t];known=bool(z.g_ready and np.isfinite(z.mu21) and np.isfinite(z.S21))
  if not known:missing.append(day);continue
  if firstmain is None and z.base_warm:firstmain=day
  raw=bool(firstmain and z.S21==-1 and z.mu21<0);reason=[]
  if not held:reason.append('not_yet_actual_holding')
  if not bool(z.e0_target and z.i_target):reason.append('original_structure_exit_priority')
  if not cp[day]['on']:reason.append('ACT_exit_priority')
  if pending:reason.append('original_sell_pending')
  if raw and firstraw is None:firstraw=day
  candidate=raw and not reason
  if candidate and firstcandidate is None:firstcandidate=day
  q=dict(cycle_id=key,date=day,S21=float(z.S21),mu21=float(z.mu21),base_warm=bool(z.base_warm),launch=bool(z.launch),has_main_up=bool(firstmain),held=held,e0_I_active=bool(z.e0_target and z.i_target),ACT_on=bool(cp[day]['on']),original_sell_pending=pending,raw_state_conjunction=raw,legal_candidate=candidate,gate_reasons='|'.join(reason));local.append(q)
 details+=local;path=sorted(hp[key],key=lambda x:x['day']);firstcross={str(n):next((x['day'] for x in path if D(x['net_liquidation_return'])<=-D(n)/100),None) for n in [10,20,30]};at=next((x for x in path if x['day']==firstcandidate),None);prior=[x for x in path if firstcandidate and x['day']<=firstcandidate];peak=max([D(0)]+[D(x['nav_mark_return']) for x in prior]);dd=(1+D(at['nav_mark_return']))/(1+peak)-1 if at else None;warn=warnings[key]['date'] or None
 if firstcandidate:why='candidate_present_before_original_exit'
 elif firstmain is None:why='no_main_up_observed_in_cycle'
 elif firstraw:why='raw_conjunction_only_when_original_exit_or_ACT_or_held_gate_blocks'
 elif not any(x['has_main_up'] and x['S21']==-1 for x in local):why='S21_not_negative_after_main_up_before_original_exit'
 else:why='mu21_not_negative_when_S21_negative_before_original_exit'
 if missing:why+=';missing_observations_preserved'
 rows.append(dict(cycle_id=key,symbol=s,name=c['name'],entry_decision=c['entry_decision'],entry=c['entry_at'],original_exit_request=c['exit_request'],original_exit=c['exit_at'],entry_S21=float(er.S21),entry_mu21=float(er.mu21),entry_base_warm=bool(er.base_warm),entry_launch=bool(er.launch),entry_primary='base' if er.base_warm else 'acute_only' if er.launch else 'unclassified',first_main_up=firstmain,first_raw_conjunction=firstraw,first_legal_candidate=firstcandidate,candidate_close_net_liquidation_return=at['net_liquidation_return'] if at else None,candidate_close_NAV_return=at['nav_mark_return'] if at else None,past_peak_NAV_return=peak if at else None,candidate_drawdown_from_past_peak=dd,first_old_negative_warning=warn,first_minus10=firstcross['10'],first_minus20=firstcross['20'],first_minus30=firstcross['30'],candidate_vs_old_warning=comparison(firstcandidate,warn),candidate_vs_minus10=comparison(firstcandidate,firstcross['10']),candidate_vs_minus20=comparison(firstcandidate,firstcross['20']),candidate_vs_minus30=comparison(firstcandidate,firstcross['30']),missing_observation_days=json.dumps(missing),status=why))
export('cycle-timelines.csv',rows);export('observed-cycle-states.csv',details);assert len(rows)==7 and all(sha(p)==h for p,h in identity.items());save('COMPLETION.json',dict(completed_at=datetime.now(timezone.utc).isoformat(),passed=True,symbols=6,cycles=7,trade_engines_run=0,new_exit_PnL_computed=False,source_hashes_unchanged=True,seconds=time.monotonic()-T));print(json.dumps(dict(stage='complete',rows=rows,seconds=time.monotonic()-T),ensure_ascii=False,default=str),flush=True)
