"""Read-only numerical adversarial audit of saved B4 synthetic outputs; no model import."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VAL = ROOT / 'validation'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def runs(f, mask):
    mask = np.asarray(mask.fillna(False), bool)
    bounds = np.flatnonzero(np.diff(np.r_[False, mask, False].astype(int)))
    out = []
    for a, b in bounds.reshape(-1, 2):
        previous = max(0, a-1)
        out.append(dict(start=int(a), end=int(b-1), observations=int(b-a),
                        start_date=str(f.index[a].date()), end_date=str(f.index[b-1].date()),
                        log_percentage_points=float(100*np.log(f.close.iloc[b-1]/f.close.iloc[previous])),
                        mu5_bp_min=float(f.mu5_bp.iloc[a:b].min()), mu5_bp_max=float(f.mu5_bp.iloc[a:b].max()),
                        mu21_bp_min=float(f.mu21_bp.iloc[a:b].min()), mu21_bp_max=float(f.mu21_bp.iloc[a:b].max())))
    return out

def first(f, start, column, direction):
    ix = np.flatnonzero((f[column].iloc[start:]*direction > 0).to_numpy())
    if not len(ix):
        return None
    i = int(ix[0]+start)
    return dict(observation=i, date=str(f.index[i].date()), ordinal_since_start=i-start+1,
                log_percentage_points=float(100*np.log(f.close.iloc[i]/f.close.iloc[start-1])))

def snap(f, i):
    fields = ['close','r_bp','mu5_bp','mu21_bp','S21','S63','acute_down','acute_up']
    return dict(observation=i,date=str(f.index[i].date()),phase=str(f.phase.iloc[i]),
                **{k: float(f[k].iloc[i]) for k in fields})

fs = {p.stem:pd.read_parquet(p) for p in sorted(VAL.glob('*.parquet'))}
assert len(fs)==25
all_path_stats=[]
event_violations=[]
confirmation_count=0
for name,f in fs.items():
    journal_path=VAL/(name+'-events.json')
    events=json.loads(journal_path.read_text())
    confirmed=[e for e in events if e['kind']=='structure_confirmed']
    confirmation_count += len(confirmed)
    for e in confirmed:
        q=e['receipt'];delta=q['threshold'];eps=32*np.finfo(float).eps*max(1,abs(delta),abs(q['x']),abs(q['credit']))
        tests=dict(positive_directed_return=e['direction']*e['r']>0,
                   positive_new_frontier=q['frontier_increment']>0 and q['new_frontier']==1,
                   physical_threshold=q['x']+eps>=delta,
                   credit_threshold=q['credit']+eps>=delta,
                   bounded_credit=.5*q['frontier']-eps<=q['credit']<=2*q['frontier']+eps)
        if not all(tests.values()): event_violations.append(dict(path=name,observation=e['observation'],horizon=e['horizon'],tests=tests))
    aligned=(f.S21==1)&(f.S63==1)
    down=(f.S21==-1)&(f.S63==-1)
    conflicts={
        'same_up_mu5_negative':runs(f,aligned&(f.mu5<0)),
        'same_up_mu21_negative':runs(f,aligned&(f.mu21<0)),
        'same_up_both_negative':runs(f,aligned&(f.mu5<0)&(f.mu21<0)),
        'same_up_mu21_under_one_bp':runs(f,aligned&(f.mu21_bp.abs()<1)),
        'same_down_both_positive':runs(f,down&(f.mu5>0)&(f.mu21>0)),
    }
    checks=dict(path=name, rows=len(f), input_sha256=sha(VAL/'inputs'/(name+'.parquet')),
                output_sha256=sha(VAL/(name+'.parquet')), journal_sha256=sha(journal_path),
                confirmations=len(confirmed), upward_confirmations=sum(e['direction']==1 for e in confirmed),
                phases=f.phase.value_counts().to_dict(), conflicts=conflicts,
                volume_structure_difference=int(((f.S21!=f.price_S21)|(f.S63!=f.price_S63)).where(f.S21.notna(),False).sum()) if 'price_S21' in f else None,
                volume_acute_down_difference=int((f.acute_down!=f.price_acute_down).where(f.S21.notna(),False).sum()) if 'price_acute_down' in f else None,
                tail=snap(f,len(f)-1))
    all_path_stats.append(checks)

response_specs={
 'slow_decline':(190,-1),'true_weakening':(185,-1),
 'shock_then_static':(190,-1),'shock_then_slow_decline':(190,-1),
 'shock_then_recovery':(191,1),'V_continues':(180,1),'rebound_fails':(180,1),
 'bear_rebound':(185,1),'fast_start':(120,1),'slow_rise':(120,1),
 'micro_rise':(120,1),'ordinary_rise':(120,1),'mirror_fast_start':(120,-1),
 'lowvol_selloff':(185,-1),'mirror_lowvol_selloff':(185,1),
}
responses={name:dict(start=start,direction=direction,
                     **{col:first(fs[name],start,col,direction) for col in ['mu5','mu21','S21','S63']})
           for name,(start,direction) in response_specs.items()}

prefixes=[]
for a,b,n in [('V_continues','rebound_fails',190),('shock_then_static','shock_then_recovery',191),('shock_then_static','shock_then_slow_decline',191)]:
    ea=json.loads((VAL/(a+'-events.json')).read_text());eb=json.loads((VAL/(b+'-events.json')).read_text())
    shared=fs[a].columns.intersection(fs[b].columns)
    prefixes.append(dict(a=a,b=b,observations=n,
                         common_saved_columns_exact=fs[a].loc[:,shared].iloc[:n].equals(fs[b].loc[:,shared].iloc[:n]),
                         comparison_columns=list(shared),
                         columns_only_in_a=list(fs[a].columns.difference(fs[b].columns)),
                         columns_only_in_b=list(fs[b].columns.difference(fs[a].columns)),
                         journal_prefix_exact=[e for e in ea if e['observation']<n]==[e for e in eb if e['observation']<n]))

shock=fs['shock_then_recovery'];recoveries=[]
for e in json.loads((VAL/'shock_then_recovery-events.json').read_text()):
    if e['kind']=='structure_confirmed' and e['direction']==1 and e['observation']>190:
        i=e['observation']; recoveries.append(dict(horizon=e['horizon'],receipt=e['receipt'],
             remaining_log_percentage_points_to_preshock=float(100*np.log(shock.close.iloc[i]/shock.close.iloc[189])),
             **snap(shock,i)))

static_summaries={}
for name,start in [('rise_then_static',190),('shock_then_static',191),('shock_then_recovery',195),('constant',64),('single_lowvol_shock',191)]:
    f=fs[name];tail=f.iloc[-21:]
    static_summaries[name]=dict(start=start, observations=len(f)-start,
       phases=f.phase.iloc[start:].value_counts().to_dict(),
       last21_mu5_bp_min=float(tail.mu5_bp.min()),last21_mu5_bp_max=float(tail.mu5_bp.max()),
       last21_mu21_bp_min=float(tail.mu21_bp.min()),last21_mu21_bp_max=float(tail.mu21_bp.max()),
       tail=snap(f,len(f)-1))

focus={}
for name,indices in {
    'slow_decline':[189,190,193,204,209,210,224,225,309],
    'true_weakening':[184,185,186,189,191,192,229],
    'V_continues':[179,180,183,184,185,189,190,208,239],
    'rebound_fails':[179,180,183,184,185,189,190,191,192,193,194,195,196,197,239],
    'bear_rebound':[184,185,188,190,192,193,194,195,196,197,198,237],
    'one_pulse':[119,120,121,122,179],
    'same_end_recovery':[119,120,121,122],
    'same_end_retracement':[119,120,121,122],
}.items():focus[name]=[snap(fs[name],i) for i in indices]

body_summaries={}
for name,start in [('slow_decline',190),('flat_box',190),('rise_then_static',190),('shock_then_static',191),('shock_then_slow_decline',191),('micro_box',120),('consolidation',180),('debt_partial_revisit',120)]:
    z=fs[name].iloc[start:];up=(z.S21==1)&(z.S63==1)
    body_summaries[name]=dict(start=start,rows=len(z),phases=z.phase.value_counts().to_dict(),
      same_up_count=int(up.sum()),same_up_mu5_negative=int((up&(z.mu5<0)).sum()),
      same_up_mu21_negative=int((up&(z.mu21<0)).sum()),same_up_mu21_under_one_bp=int((up&(z.mu21_bp.abs()<1)).sum()),
      new_up_events=int((z.confirmed_direction_21==1).sum()+(z.confirmed_direction_63==1).sum()),
      mu21_bp_min=float(z.mu21_bp.min()),mu21_bp_max=float(z.mu21_bp.max()))
volume_probes={}
for name in ['frontier_low','frontier_normal','frontier_high']:
    f=pd.read_parquet(VAL/'probes'/(name+'.parquet'))
    es=json.loads((VAL/'probes'/(name+'-events.json')).read_text())
    volume_probes[name]=dict(rows=len(f),tail=snap(f,len(f)-1),
        confirms=[dict(observation=e['observation'],horizon=e['horizon'],direction=e['direction'],receipt=e['receipt']) for e in es if e['kind']=='structure_confirmed'])

result=dict(recorded_at=datetime.now(timezone.utc).isoformat(),
            role='independent_saved_output_adversarial_audit', model_executions=0,accounts=0,
            paths=all_path_stats, confirmations_checked=confirmation_count, confirmation_violations=event_violations,
            response_specs=responses,prefixes=prefixes,shock_recovery_confirmations=recoveries,
            static_summaries=static_summaries,focus=focus,body_summaries=body_summaries,volume_probes=volume_probes,
            audit_collection_note='Initial collector attempt stopped on missing price_S21 in the derived path; optional ablation fields now report null if absent. No model execution or output changed.',
            meaning='Finite deterministic evidence; no market accuracy or promotion. Images reviewed separately.')
(HERE/'SELECTED_FACTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
for p in all_path_stats:
    print(p['path'], 'confirms',p['confirmations'],'up21negative',sum(r['observations'] for r in p['conflicts']['same_up_mu21_negative']),
          'up_nearzero',sum(r['observations'] for r in p['conflicts']['same_up_mu21_under_one_bp']),
          'volume_state_diff',p['volume_structure_difference'],'tail',p['tail']['phase'],round(p['tail']['mu21_bp'],6))
print('RESPONSES',json.dumps(responses,ensure_ascii=False))
print('PREFIXES',json.dumps(prefixes,ensure_ascii=False))
print('CONFIRMATIONS',confirmation_count,'violations',len(event_violations))
