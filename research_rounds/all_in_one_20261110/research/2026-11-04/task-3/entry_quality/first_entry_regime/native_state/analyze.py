"""Saved native state of first actual entries, no new features or accounts."""
from pathlib import Path
from decimal import Decimal as D, getcontext
from collections import defaultdict
from datetime import datetime
import json,gzip,hashlib,statistics
import pandas as pd

getcontext().prec=50
O=Path(__file__).resolve().parent;B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
LOCAL=O.parents[1]/'local_high';G=B/'loss_correction/mobile_current_grade_quickcheck_v1';M=B/'risk_constraints/ma63_information_diagnostic_v1';SRC={};STATES={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);SRC[str(p)]=sha(p)
 if p.suffix=='.gz':
  with gzip.open(p,'rt') as f:return json.load(f)
 return json.loads(p.read_text())
def lines(p):
 p=Path(p);SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def save(n,z):
 with (O/n).open('x') as f:json.dump(z,f,ensure_ascii=False,indent=2,default=str,allow_nan=False)
def scalar(x):
 if pd.isna(x):return None
 if hasattr(x,'item'):return x.item()
 return x
def agg(z):
 out=dict(layers=len(z),stocks=len({x['sid'] for x in z}))
 for k in ['cost','net','strict_realized','open_unrealized','recognized_dividend_AR','buy_fee','sell_fee']:
  out[k]=None if any(k not in x for x in z) else sum((D(str(x[k])) for x in z),D(0))
 out.update(positive_layers=sum(D(x['net'])>0 for x in z),negative_layers=sum(D(x['net'])<0 for x in z),positive_net=sum((D(x['net']) for x in z if D(x['net'])>0),D(0)),negative_net=sum((D(x['net']) for x in z if D(x['net'])<0),D(0)),open_layers=sum(bool(x['qty']) for x in z))
 tails=[x for x in z if D(x['net'])/D(x['cost'])>=D('.3')]
 out['terminal_tail_layer_count']=len(tails);out['terminal_tail_layer_net']=sum((D(x['net']) for x in tails),D(0));out['terminal_tail_layer_cost']=sum((D(x['cost']) for x in tails),D(0))
 return out
def grouped(z,*keys):
 groups=defaultdict(list)
 for x in z:groups[tuple(str(x[k]) for k in keys)].append(x)
 return [dict(labels=dict(zip(keys,k)),**agg(v)) for k,v in sorted(groups.items())]

def main():
 O.mkdir(parents=True,exist_ok=True)
 if not (O/'PROTOCOL.json').exists():
  save('PROTOCOL.json',dict(frozen_at=datetime.now().astimezone().isoformat(),scope='same saved first actual fills: 2022-23 first772 and strong first671; native decision state, no new thresholds/accounts',state_axes='original market industry stage/attempt and probeR; original G1/I; original ACT checkpoint+same frozen synthetic recovery input; actual fill pool separate',exclusions=['no cold full-market compute','no changed membership','no ETFMA substitute for synthetic market','no completed outcome used as signal','no deletion-PnL policy returns'],tail='actual first layer terminal net/cost>=30% descriptive only, open marks/AR retained; original fixed83/94 cross-arm correspondence separately'))
 im={x['series']:x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
 rp=W/'mainline-absolute-Q4-20261031/recovery.csv';SRC[str(rp)]=sha(rp);recovery=pd.read_csv(rp,parse_dates=['date']).set_index('date');assert recovery.index.is_unique
 def state(sector,day):
  if sector not in STATES:
   p=Path(im[sector]['refs']['state']);assert sha(p)==im[sector]['output_sha256'][str(p)];SRC[str(p)]=sha(p);f=pd.read_parquet(p);f['day']=f.day.astype(str).str[:10];assert f.day.is_unique;STATES[sector]=f.set_index('day',drop=False)
  f=STATES[sector];assert day in f.index;return f.loc[day],f.loc[:day]
 roots={'2022_2024':B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024','strong':B/'pvr_pool_feasibility/runs/2025_26'}
 allout={};checks={}
 for ref,root in roots.items():
  rich=read(LOCAL/(ref+'_ROWS.json'));grade={x['layer']:x for x in read(G/(ref+'_ROWS.json'))};book=read(root/'pair/B.json.gz');industry=lines(root/'pair/industry.jsonl.gz')
  selected=[x for x in rich if x['action']=='first_actual_participation' and (ref=='strong' or x['opened'][:10]<='2023-12-29')]
  assert len(selected)==(772 if ref=='2022_2024' else 671)
  cp={x['at']:x for x in book['audit'] if x['kind']=='risk_checkpoint'}
  decision={x['at']:x for x in book['decisions']};industrymap=defaultdict(list)
  for x in industry:industrymap[x['sector']].append(x)
  for seq in industrymap.values():seq.sort(key=lambda x:x['day'])
  resume=[x for x in cp.values() if x['event']=='resume'];resume.sort(key=lambda x:x['at']);rows=[]
  for e in selected:
   x=dict(e);day=x['decision_at'][:10];at=x['decision_at'];s,prefix=state(x['sector'],day);r=cp[at];d=decision[at];g=grade[x['layer']]
   assert r['on'] and d['on'];assert datetime.fromisoformat(at)<datetime.fromisoformat(x['opened'])
   rr=recovery.loc[pd.Timestamp(day)];assert bool(rr.fast_on)==r['fast'] and bool(rr.breakout)==r['breakout']
   # Original net progress R already rebuilt in rich entries; independently verify anchor identity and value.
   aid=s.attempt_id;probes=prefix[prefix.attempt_id.eq(aid)&prefix.action.eq('probe')];assert len(probes)
   p=probes.iloc[0];line=max(float(p.E0_floor),float(p.candidate_floor));risk=float(p.close)-line
   R=(float(s.close)-float(p.close))/risk;assert p.day==x['probe_progress']['probe_day'] and abs(R-x['probe_progress']['R'])<1e-10
   recent=[v for v in industrymap[x['sector']] if v['day']<=day];exact=[v for v in recent if v['day']==day]
   rs=[v for v in resume if v['at']<=at];last_resume=rs[-1] if rs else None
   native=dict(industry_market={k:scalar(s[k]) for k in ['stage','stage_name','stage_before','attempt_id','attempt_number','E0_valid','E0_episode','E0_floor','mobile_before','mobile_after','action','reason','authorization_usable','authorization_id']},
    industry_probe=dict(x['probe_progress']),industry_financial_log_exact_day=exact,industry_financial_log_latest_known=None if not recent else recent[-1],
    financial_log_scope='sparse native transition events, latest record not assumed current level when exact-day absent',
    stock_G1_I={k:g.get(k) for k in ['current_g_grade','current_g_ready','original_I_target','original_I_buy','grade_class','grade_unknown']},
    stock_I_alive=x['original_I_alive'],stock_I_floor=x['original_I_floor'],
    ACT_checkpoint=r,ACT_post_transition_phase_DD=(D(1)-D(r['nav'])/D(r['peak'])) if D(r['peak']) else None,
    ACT_original_synthetic_input={k:scalar(rr[k]) for k in ['market','prior_high63','breadth','breakout','fast_on']},
    ACT_input_is_original_synthetic_not_ETF=True,ACT_last_actual_resume=last_resume,
    ACT_permission_origin='initial_permission' if last_resume is None else 'after_actual_resume',ACT_episodes_not_cross_account_equal_regimes=True,
    actual_fill_pool=x['pool_at_fill'],ETF_MA_original_auxiliary=x['ETF_macro'])
   x['native_state']=native;x['native_industry_stage']=str(s.stage_name);x['native_industry_stage_number']=int(s.stage);x['native_industry_probe_R_bin']=x['probe_progress']['R_bin'];x['native_G1_grade']=g['current_g_grade'];x['native_G1_class']=g['grade_class'];x['native_I_target']=g['original_I_target'];x['native_ACT_fast']=r['fast'];x['native_ACT_breakout']=r['breakout'];x['native_ACT_episode']=r['episode'];x['native_ACT_permission_origin']=native['ACT_permission_origin'];rows.append(x)
  overall=agg(rows);assert abs(overall['net']-D('-148130.060499494881300000000000'))<D('.00001') if ref=='2022_2024' else True
  summary=dict(all=overall,by_industry_stage=grouped(rows,'native_industry_stage'),by_decision_stage_and_actual_fill_pool=grouped(rows,'native_industry_stage','pool_at_fill'),by_probe_progress=grouped(rows,'native_industry_probe_R_bin'),by_stage_and_probe_progress=grouped(rows,'native_industry_stage','native_industry_probe_R_bin'),by_G1_grade=grouped(rows,'native_G1_grade'),by_G1_class=grouped(rows,'native_G1_class'),by_I_target=grouped(rows,'native_I_target'),by_ACT_fast=grouped(rows,'native_ACT_fast'),by_ACT_breakout=grouped(rows,'native_ACT_breakout'),by_stage_and_ACT_fast=grouped(rows,'native_industry_stage','native_ACT_fast'),by_permission_origin=grouped(rows,'native_ACT_permission_origin'),by_ACT_episode=grouped(rows,'native_ACT_episode'),by_ETF_auxiliary=grouped(rows,'ETF_macro'))
  # Native fast is the original .6 breadth condition; retain continuous summaries without adding bins.
  summary['continuous_at_decision']={}
  for label,z in [('all',rows),('terminal_positive',[x for x in rows if D(x['net'])>0]),('terminal_negative',[x for x in rows if D(x['net'])<0]),('terminal_tail',[x for x in rows if D(x['net'])/D(x['cost'])>=D('.3')])]:
   summary['continuous_at_decision'][label]={}
   for key,fn in [('breadth',lambda x:x['native_state']['ACT_original_synthetic_input']['breadth']),('probe_R',lambda x:x['probe_progress']['R']),('phase_DD',lambda x:float(x['native_state']['ACT_post_transition_phase_DD']))]:
    vv=[fn(x) for x in z if fn(x) is not None];summary['continuous_at_decision'][label][key]=dict(n=len(vv),min=min(vv) if vv else None,median=statistics.median(vv) if vv else None,max=max(vv) if vv else None)
  fixed=read(M/(ref+'_ORIGINAL_FIXED_TAIL_COVERAGE.json'));firstids={x['layer']:x for x in rows};control=[]
  for c in fixed:
   ids=[lid for lid in c['matched_No60_layers'] if lid in firstids];control.append(dict(original=c['original'],all_matched_No60_layers=c['matched_No60_layers'],matched_first_No60_layers=ids,matched_first_money=agg([firstids[lid] for lid in ids]),matched_first_native_states=[firstids[lid]['native_state'] for lid in ids],unmatched=not c['matched_No60_layers']))
  summary['original_fixed_tail_controls']=dict(all_original_members=len(control),exact_No60_correspondence=sum(bool(c['all_matched_No60_layers']) for c in control),matched_first_members=sum(bool(c['matched_first_No60_layers']) for c in control),unmatched_original_members=sum(c['unmatched'] for c in control),matched_actual_first_money=agg([firstids[lid] for c in control for lid in c['matched_first_No60_layers']]))
  checks[ref]=dict(first_actual_layers=len(rows),unique_stocks=len({x['sid'] for x in rows}),all_ACT_on_at_decision=True,all_ACT_synthetic_fast_breakout_exact=True,all_original_probe_R_and_probe_day_exact=True,unknown_industry_stage=0,unknown_G1=sum(x['native_G1_class']=='unknown' for x in rows),industry_exact_day_log_rows=sum(bool(x['native_state']['industry_financial_log_exact_day']) for x in rows),all_only_past_or_current_state=True)
  allout[ref]=summary;save(ref+'_FIRST_ROWS.json',rows);save(ref+'_FIXED_OLD_TAIL_CORRESPONDENCE.json',control);print(ref,json.dumps(summary,ensure_ascii=False,default=str),flush=True)
 save('RESULTS.json',allout);save('VALIDATION.json',checks);save('SOURCE_MANIFEST.json',dict(sources=SRC,script_sha256=sha(__file__),new_feature_calculations=0,new_accounts=0,original_probeR_arithmetic_check_only=True,original_ACT_source_path=str(rp),original_ACT_source_sha256=sha(rp),limitations=['all selected stocks first participated within finite account windows; not all market first signals','stage/growth conditions shared by losers and winners; groups not causal avoided losses','current surviving stock and industry snapshot historical development','terminal first-layer tails are layer labels, not full-stock campaigns; unclosed marked and unpaid AR separately retained','sparse financial industry events do not certify all current financial levels']))
 print('COMPLETE',flush=True)
if __name__=='__main__':main()
