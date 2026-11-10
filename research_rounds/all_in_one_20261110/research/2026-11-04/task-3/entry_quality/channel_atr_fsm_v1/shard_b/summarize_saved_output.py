"""Aggregate saved pure-signal outputs only; never calls the engine or Account."""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,math,statistics
import pandas as pd

O=Path(__file__).resolve().parent;R=O/'run_v1'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):
    (O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def stats(x):
    x=[float(v) for v in x if v is not None and math.isfinite(float(v))]
    return {'n':len(x),'min':min(x) if x else None,'median':statistics.median(x) if x else None,
            'mean':statistics.fmean(x) if x else None,'max':max(x) if x else None}

receipt=json.loads((R/'RUN_RECEIPT.json').read_text());assert receipt['status']=='COMPLETE' and receipt['errors']==0
claim=json.loads((O.parent/'CLAIM_SHA256.json').read_text())
for p,h in claim['code_sha256'].items():assert sha(p)==h,(p,'code changed after release')
coverage=json.loads((R/'COVERAGE_ALL_SYMBOLS.json').read_text())
groups=defaultdict(list);flat=[];strong_candidates=[];main_kind_counts=defaultdict(Counter)
for c in coverage:
    if c.get('status')!='COMPLETE':continue
    sid=c['sid'];d=R/sid.replace('.','_')
    for e in json.loads((d/'MARKET_EVENTS.json').read_text()):main_kind_counts[e['window']][e['kind']]+=1
    pp=json.loads((d/'CP_ANCHOR_PAIRS.json').read_text())
    assert len(pp)==c['raw_CP_anchors']
    for p in pp:
        groups[p['window']].append(p)
        row={k:p.get(k) for k in ['sid','anchor_day','anchor_id','window','status','anchor_C','anchor_ATR_prior','P0','common_end_reason','common_end_day','common_observations','common_max_close','common_favorable_excursion_ATR']}
        for branch in ['CP','ATR3']:
            q=p.get(branch)
            for k in ['outcome','exit_day','exit_reason','exit_line','effective_observations_held','status_at20','post20_observations','post20_max_close_drawdown_ATR','common_peak_after_shadow_truncation_ATR','unknown_reason','censor_reason']:
                row[branch+'_'+k]=None if q is None else q.get(k)
            t=None if q is None else q.get('twentieth_observation')
            row[branch+'_twentieth_close']=None if t is None else t.get('C')
            row[branch+'_twentieth_P_old']=None if t is None else t.get('P_old')
            row[branch+'_twentieth_P_after']=None if t is None else t.get('P_after')
            row[branch+'_twentieth_stop_distance_ATR']=None if t is None else t.get('stop_distance_ATR')
        flat.append(row)
        if p.get('status')=='PAIRED_SHADOWS':
            cp=p['CP'];a=p['ATR3']
            if a['outcome']=='EXIT_SIGNAL' and (cp['outcome']=='RIGHT_CENSORED' or cp['outcome']=='EXIT_SIGNAL' and a['exit_day']<cp['exit_day']):
                strong_candidates.append(p)

summary={'status':'SAVED_OUTPUT_SUMMARY_ONLY','run_receipt_sha256':sha(R/'RUN_RECEIPT.json'),
         'version':receipt['version'],'symbols_requested':receipt['symbols_requested'],
         'symbols_completed':receipt['symbols_completed'],'symbols_not_applicable':receipt['symbols_not_applicable'],
         'display_observations':receipt['display_observations'],'raw_CP_anchors':receipt['raw_CP_anchors'],
         'periods':{},'new_engine_runs':0,'new_accounts':0,'new_quantities':0,'new_returns':0,
         'global_strong_deciles':'NOT_ASSIGNED; parent must merge complete A/B window cohorts before decile assignment',
         'limits':['Paired references are not holdings or executable fills.',
                   'Any early-exit post20 risk is missing, not zero.',
                   'Hold statistics below are explicit both-exit subcohorts, not all-cohort economic results.',
                   'Source calendar completeness and execution flags remain unverified.']}
for window,pp in groups.items():
    valid=[p for p in pp if p['status']=='PAIRED_SHADOWS']
    order=Counter();cross=Counter();outcomes=Counter();cp20=[];a20=[];both_exit_cp=[];both_exit_a=[];diff=[]
    for p in valid:
        c,a=p['CP'],p['ATR3'];outcomes[c['outcome']+'__'+a['outcome']]+=1
        cross[c['status_at20']+'__'+a['status_at20']]+=1
        if c['outcome']=='EXIT_SIGNAL' and a['outcome']=='EXIT_SIGNAL':
            label='ATR_EARLIER' if a['exit_day']<c['exit_day'] else 'ATR_LATER' if a['exit_day']>c['exit_day'] else 'SAME_CLOSE'
            order[label]+=1
            both_exit_cp.append(c['effective_observations_held']);both_exit_a.append(a['effective_observations_held']);diff.append(a['effective_observations_held']-c['effective_observations_held'])
        if c['post20_max_close_drawdown_ATR'] is not None:cp20.append(c['post20_max_close_drawdown_ATR'])
        if a['post20_max_close_drawdown_ATR'] is not None:a20.append(a['post20_max_close_drawdown_ATR'])
    any_right=sum(p['CP']['outcome']=='RIGHT_CENSORED' or p['ATR3']['outcome']=='RIGHT_CENSORED' for p in valid)
    any_unknown=sum(p['CP']['outcome']=='UNKNOWN' or p['ATR3']['outcome']=='UNKNOWN' for p in valid)
    r={'raw_CP_anchors':len(pp),'pair_status_counts':dict(Counter(p['status'] for p in pp)),
       'paired_references':len(valid),'both_exit_order_counts':dict(order),
       'any_right_censored':any_right,'any_unknown':any_unknown,
       'any_branch_not_exit':sum(p['CP']['outcome']!='EXIT_SIGNAL' or p['ATR3']['outcome']!='EXIT_SIGNAL' for p in valid),
       'outcome_cross_counts':dict(outcomes),'CP_ATR3_status_at20_cross_counts':dict(cross),
       'both_exit_CP_holding_observations':stats(both_exit_cp),
       'both_exit_ATR3_holding_observations':stats(both_exit_a),
       'both_exit_ATR3_minus_CP_holding_observations':stats(diff),
       'CP_post20_drawdown_ATR_available_only':stats(cp20),'ATR3_post20_drawdown_ATR_available_only':stats(a20),
       'main_event_kind_counts':dict(main_kind_counts[window])}
    assert sum(order.values())+r['any_branch_not_exit']==len(valid)
    assert sum(cross.values())==len(valid)
    summary['periods'][window]=r
assert sum(len(x) for x in groups.values())==receipt['raw_CP_anchors']
save('SUMMARY_FROM_SAVED_OUTPUTS.json',summary)
pd.DataFrame(flat).to_parquet(O/'ALL_PAIR_REFERENCE_ROWS.parquet',index=False)

tops={}
for window in groups:
    candidates=[p for p in strong_candidates if p['window']==window and p.get('common_favorable_excursion_ATR') is not None]
    tops[window]=sorted(candidates,key=lambda p:(-p['common_favorable_excursion_ATR'],p['sid'],p['anchor_day']))[:30]
save('TOP_RAW_EXCURSION_ATR_EARLY_INPUTS.json',{'scope':'Top raw common-horizon excursion inputs among ATR-earlier known exits; NOT a global decile and NOT economic winners.','periods':tops})

d=R/'000620_SZ';events=json.loads((d/'MARKET_EVENTS.json').read_text());gens=json.loads((d/'MARKET_GENERATIONS.json').read_text());pairs=json.loads((d/'CP_ANCHOR_PAIRS.json').read_text())
save('YINGXIN_2022_JAN_COMPLETE_STATE_WITNESS.json',{'scope':'Fixed frozen complete FSM and paired reference outputs only; not holdings/fills/returns.',
     'events':[x for x in events if '2022-01-01'<=x['day']<='2022-01-31'],
     'generations':[x for x in gens if '2022-01-01'<=x['start_day']<='2022-01-31'],
     'same_anchor_CP_ATR3':[x for x in pairs if '2022-01-01'<=x['anchor_day']<='2022-01-31']})
files=['SUMMARY_FROM_SAVED_OUTPUTS.json','ALL_PAIR_REFERENCE_ROWS.parquet','TOP_RAW_EXCURSION_ATR_EARLY_INPUTS.json','YINGXIN_2022_JAN_COMPLETE_STATE_WITNESS.json','summarize_saved_output.py']
save('SAVED_OUTPUT_SUMMARY_SHA256.json',{str((O/x).resolve()):sha(O/x) for x in files})
print(json.dumps(summary,ensure_ascii=False),flush=True)
