"""Analyze completed H2 outputs only; reuse the sealed financial reader.

No Runner/Account/ledger import, no order placement or account advancement.
The sealed reader is imported read-only, with only input roots/periods supplied.
Its old EMA diagnostic entry fields are discarded and replaced by H2 context.
"""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D,getcontext
import argparse,bisect,csv,gzip,hashlib,importlib.util,json,sys
import pandas as pd

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;E=ROOT.parent
OLDROOT=E/'trend_exit_controls_v1'
READER=OLDROOT/'execution_review/account_comparison/compare_accounts.py'
sys.dont_write_bytecode=True  # read the sealed helper without cache writes there
spec=importlib.util.spec_from_file_location('sealed_exit_financial_reader_for_h2',READER);M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
getcontext().prec=65
Z=D(0);ARMS=['BASELINE','R_ONLY','P_ONLY','JOINT'];WINDOWS=['2022_2024','strong']
PERIODS={k:list(v) for k,v in M.PERIODS.items()}
PERIODS['2022_2024'].insert(2,('Dec2022','2022-12-01','2022-12-31'))
M.PERIODS=PERIODS
# Only used by the sealed reader's disposable legacy EMA entry diagnostics.
M.INDICATORS={a:'EMA20' for a in ARMS[1:]}

def save(out,name,v):M.save(out,name,v)
def read(p,gz=False,lines=False):return M.read(p,gz=gz,lines=lines)
def eq(a,b,k):M.eq(a,b,k)
def runpath(arm,window):return (OLDROOT if arm=='BASELINE' else ROOT)/'runs'/arm/window
def auditpath(arm,window):return (OLDROOT if arm=='BASELINE' else ROOT)/'independent_review'/f'{arm}_{window}_ACCOUNT_AUDIT.json'

class LegacyDiagnosticView:
    """EMA compatibility for an unused old report field, never an H2 policy."""
    def __init__(self,provider):self.provider=provider
    def at(self,sid,at,unused_indicator):
        q=self.provider.at(sid,at)
        return dict(status='READY' if q['ready_P'] else 'UNKNOWN',day=q['day'],causal_close=q['close'],line=q['EMA20'],
                    source_segment=q['source_segment'],source_max_day=q['source_max_day'],unknown_reason=q['unknown_reason'])

def mode_decision(q,arm):
    if arm=='BASELINE':ready=True;weak=False
    elif arm=='R_ONLY':ready=q['ready_R'];weak=ready and q['RS20']<=0
    elif arm=='P_ONLY':ready=q['ready_P'];weak=ready and q['close']<q['EMA20']
    else:ready=q['ready_R'] and q['ready_P'];weak=ready and q['RS20']<=0 and q['close']<q['EMA20']
    return dict(mode_ready=bool(ready),known_weak=bool(weak),unknown_keeps_native=not ready)

def analyze(arm,window,provider,calendar):
    # Financial formulas, integer partial-layer sidecars, native daily mark,
    # wealth split and independent-audit endpoint checks stay untouched.
    M.ROOT=OLDROOT if arm=='BASELINE' else ROOT
    r=M.analyze_run(arm,window,runpath(arm,window),LegacyDiagnosticView(provider),calendar)
    for x in r['layers']:
        for field in ['entry_decision_tool','entry_day_CLOSE_tool','buy_OPEN_vs_prior_decision_line_below','entry_day_CLOSE_is_after_buy_and_not_known_at_OPEN']:x.pop(field,None)
        q=provider.at(x['sid'],x['decision_at']);x['H2_entry_context']=q;x['H2_entry_mode_decision']=mode_decision(q,arm)
        if arm!='BASELINE' and x['role']=='mobile':assert not x['H2_entry_mode_decision']['known_weak'],'Actual weak mobile bypassed policy guard'
    raw=read(runpath(arm,window)/'pair/daily.jsonl.gz',gz=True,lines=True);book=read(runpath(arm,window)/'pair/B.json.gz',gz=True)
    r.update(raw_daily=raw,book=book,raw_byid={x['id']:x for x in book['layers']},byid={x['layer_in_this_book']:x for x in r['layers']})
    r['raw_dmap']={d['at'][:10]:d for d in raw};r['native_times']=[M.ts(d['at']) for d in raw]
    return r

def partial_at(r,lid,at):
    states=r['validation']['partial_basis_state_points'].get(lid)
    if states is None:states=r['validation']['partial_basis_state_points'].get(str(lid))
    if states is None:return None
    j=bisect.bisect_right([M.ts(x['at']) for x in states],M.ts(at))-1
    return None if j<0 else states[j]

def components(r,day):
    d=r['raw_dmap'][day];at=M.ts(d['at']);held={x['id']:x for x in d['layers']};out={}
    for x in r['layers']:
        lid=x['layer_in_this_book']
        if x['opened']>at:real=unreal=ar=Z
        elif x['closed'] is not None and x['closed']<=at:real=D(r['raw_byid'][lid]['cash']);unreal=Z;ar=D(r['raw_byid'][lid]['dividend'])
        else:
            h=held[lid];ps=partial_at(r,lid,at);basis=ps['basis'] if ps is not None else D(x['cost']);real=ps['strict_realized'] if ps is not None else Z
            eq(D(h['cash']),real-basis,'held partial/native cash');unreal=D(h['qty'])*M.quote(x['sid'],day)[0]-basis;ar=D(h['dividend'])
        out[x['key']]=dict(real=real,unreal=unreal,AR=ar,wealth=real+unreal+ar)
    totals={k:sum((v[k] for v in out.values()),Z) for k in ['real','unreal','AR','wealth']};eq(totals['wealth'],D(d['nav'])-1000000,'Dec boundary wealth')
    native=next(x for x in r['daily'] if x['day']==day)
    for k,n in [('real','strict_realized'),('unreal','open_unrealized'),('AR','AR')]:eq(totals[k],native[n],'financial reader boundary component')
    return out

def month_totals(rows):
    return dict(layers=len(rows),stocks=len({x['sid'] for x in rows}),Dec_wealth=sum((x['Dec_components']['wealth'] for x in rows),Z),
      Dec_realized=sum((x['Dec_components']['real'] for x in rows),Z),Dec_unrealized=sum((x['Dec_components']['unreal'] for x in rows),Z),Dec_AR=sum((x['Dec_components']['AR'] for x in rows),Z),
      positive=sum((max(Z,x['Dec_components']['wealth']) for x in rows),Z),negative=sum((min(Z,x['Dec_components']['wealth']) for x in rows),Z),
      Dec_new_actual_buycash=sum((D(x['cost']) for x in rows if x['cohort'].startswith('Dec_new_')),Z),
      previous_CLOSE_mark_yuan_observations=sum((x['capitaltime']['previous_CLOSE_mark_yuan_observations'] for x in rows),Z),
      previous_CLOSE_basis_yuan_observations=sum((x['capitaltime']['previous_CLOSE_basis_yuan_observations'] for x in rows),Z),
      CLOSE_mark_yuan_observations=sum((x['capitaltime']['CLOSE_mark_yuan_observations'] for x in rows),Z))

def december(r):
    a=components(r,'2022-11-30');b=components(r,'2022-12-30');start=r['raw_dmap']['2022-11-30'];oldids={x['id'] for x in start['layers']}
    rows=[];capital=defaultdict(lambda:dict(previous_CLOSE_mark_yuan_observations=Z,previous_CLOSE_basis_yuan_observations=Z,CLOSE_mark_yuan_observations=Z,CLOSE_held_observations=0,previous_CLOSE_held_observations=0))
    raw=r['raw_daily'];days=[d for d in raw if d['at'][:7]=='2022-12'];assert len(days)==22
    for d in days:
        j=raw.index(d)
        for snapshot,phase in [(raw[j-1],'previous_CLOSE'),(d,'CLOSE')]:
            mark=Z
            for h in snapshot['layers']:
                lid=h['id'];x=r['byid'][lid];q=D(h['qty'])*M.quote(h['sid'],snapshot['at'][:10])[0];mark+=q;ps=partial_at(r,lid,snapshot['at']);basis=ps['basis'] if ps else D(x['cost'])
                capital[lid][phase+'_mark_yuan_observations']+=q;capital[lid][phase+'_held_observations']+=1
                if phase=='previous_CLOSE':capital[lid]['previous_CLOSE_basis_yuan_observations']+=basis
            eq(mark,snapshot['inventory'],'month capitaltime native inventory')
    for x in r['layers']:
        lid=x['layer_in_this_book'];delta={k:b[x['key']][k]-a[x['key']][k] for k in ['real','unreal','AR','wealth']}
        new=M.ts(start['at'])<x['opened']<=M.ts(r['raw_dmap']['2022-12-30']['at'])
        if lid not in oldids and not new and not delta['wealth']:continue
        cohort='old_inventory_Nov30' if lid in oldids else 'Dec_new_'+x['actual_entry_action'] if new else 'other_prior'
        rows.append(dict(x,cohort=cohort,Nov30_components=a[x['key']],Dec30_components=b[x['key']],Dec_components=delta,capitaltime=capital[lid]))
    groups={}
    for c in sorted({x['cohort'] for x in rows}):groups[c]=month_totals([x for x in rows if x['cohort']==c])
    summary=month_totals(rows);summary.update(arm=r['arm'],own_cohorts=groups,by_actual_role={role:month_totals([x for x in rows if x['role']==role]) for role in ['core','mobile']},NAV_begin=start['nav'],NAV_end=r['raw_dmap']['2022-12-30']['nav'],
      capitaltime_units='yuan x native CLOSE observations, previous and current CLOSE separate; not natural days')
    period=next(x for x in r['periods'] if x['period']=='Dec2022');eq(summary['Dec_wealth'],period['net_wealth_change'],'own December cohort wealth bridge')
    r.update(Dec_rows=rows,Dec_bykey={x['key']:x for x in rows},Dec_components_bykey={k:{z:b[k][z]-a[k][z] for z in ['real','unreal','AR','wealth']} for k in a},Dec_summary=summary)
    return summary

def policy_activity(r,provider):
    arm=r['arm'];logs=[] if arm=='BASELINE' else read(runpath(arm,r['window'])/'pair/mobile-authorization-policy.jsonl.gz',gz=True,lines=True)
    rolelogs=[x for x in logs if x['phase']=='new_mobile_role_before_pending'];heldlogs=[x for x in logs if x['phase']=='held_mobile_after_native_hard_exits']
    denied={};actual_intents={(M.ts(d['at']),i['sid'],i['role'],i.get('CP1_id')) for d in r['book']['decisions'] for i in d['intents']}
    for x in rolelogs:
        if not x['allowed']:
            key=(M.ts(x['at']),x['sid'],'mobile',x['CP1_id']);assert key not in actual_intents,'Denied mobile leaked into native pending';denied[key]=x
    for x in heldlogs:assert x['core_exit_ids_added']==[];assert all(r['byid'][lid]['role']=='mobile' for lid in x['added_mobile_exit_layer_ids'])
    overlay=[];corebad=[]
    for x in r['layers']:
        for p in x['actual_sale_parts']:
            if p['reason'].startswith('mobile_authorization_'):
                overlay.append(dict(entry_key=x['key'],sid=x['sid'],role=x['role'],actual_sale_part=p,endpoint_net=x['net']))
                if x['role']!='mobile':corebad.append(x['key'])
    assert not corebad
    mobile_rebuys=[]
    for x in r['layers']:
        if x['role']!='mobile':continue
        earlier=[p for p in overlay if p['sid']==x['sid'] and M.ts(p['actual_sale_part']['at'])<x['decision_at']]
        if not earlier:continue
        last=max(earlier,key=lambda p:p['actual_sale_part']['at']);old=r['bykey'][last['entry_key']]
        assert old['receipt']!=x['receipt'],'Old consumed CP receipt reused as a new mobile entry'
        mobile_rebuys.append(dict(new_entry_key=x['key'],sid=x['sid'],actual_action=x['actual_entry_action'],fresh_CP=x['receipt'],entry_context=x['H2_entry_context'],
          previous_overlay_exit=last,remaining_CORE_after_exit_possible=x['actual_entry_action']=='add',net=x['net']))
    scope={}
    for label,start,end in [('full',None,None),('Dec2022','2022-12-01','2022-12-30')]:
        ll=[x for x in logs if start is None or start<=str(x['at'])[:10]<=end];rl=[x for x in ll if x['phase']=='new_mobile_role_before_pending'];hl=[x for x in ll if x['phase']=='held_mobile_after_native_hard_exits']
        scope[label]=dict(log_events=len(ll),role_checks=len(rl),new_mobile_denials=sum(not x['allowed'] for x in rl),role_unknown=sum(x['decision']['predicate_state']=='UNKNOWN' for x in rl),
          held_checks=len(hl),held_unknown=sum(x['decision']['predicate_state']=='UNKNOWN' for x in hl),held_requests=sum(bool(x['added_mobile_exit_layer_ids']) for x in hl),
          held_new_layer_targets=sum(len(x['added_mobile_exit_layer_ids']) for x in hl),known_weak_already_pending_or_no_new_targets=sum(x['decision']['denies_mobile'] and not x['added_mobile_exit_layer_ids'] for x in hl))
    r.update(policy_logs=logs,denial_index=denied)
    return dict(summary=dict(arm=arm,window=r['window'],scopes=scope,actual_overlay_sell_parts=len(overlay),direct_CORE_overlay_sell_parts=0,
      actual_CORE=M.layer_totals([x for x in r['layers'] if x['role']=='core']),actual_mobile=M.layer_totals([x for x in r['layers'] if x['role']=='mobile']),
      mobile_new_entries_after_previous_overlay_exit=len(mobile_rebuys),full_flat_reentries=sum(x['actual_action']=='reentry' for x in mobile_rebuys),
      same_stock_adds_with_existing_position=sum(x['actual_action']=='add' for x in mobile_rebuys),
      caveat='Counts are policy checks/layer targets, not independent market confirmations. Actual CORE quantities/entries/ACT can change endogenously although no CORE is directly targeted.'),
      role_rejection_logs=list(denied.values()),actual_mobile_exit_parts=overlay,mobile_reentry_rows=mobile_rebuys)

def fixed_december_cohort(base,r,keys,label):
    rr=[]
    for k in keys:
        b=base['bykey'][k];x=r['bykey'].get(k);month=r['Dec_components_bykey'].get(k);parts=json.loads(k)
        denial=r['denial_index'].get((parts[3],parts[0],parts[1],parts[2]));sid=b['sid']
        overlap=[z['key'] for z in r['layers'] if z['sid']==sid and z['opened']<'2022-12-30T15:10:00+08:00' and (z['closed'] is None or z['closed']>'2022-11-30T15:10:00+08:00')]
        rr.append(dict(original_full_entry_key=k,sid=sid,original_layer=base['Dec_bykey'][k],candidate_exact_entry=x,candidate_Dec_components=month,
          candidate_same_key_held_Nov30=(k in r['Dec_bykey'] and r['Dec_bykey'][k]['cohort']=='old_inventory_Nov30'),
          candidate_own_Dec_cohort=None if k not in r['Dec_bykey'] else r['Dec_bykey'][k]['cohort'],direct_guard_rejection_at_original_decision=denial,
          candidate_other_same_stock_entries=[z['key'] for z in r['layers'] if z['sid']==sid and z['key']!=k],candidate_has_any_Dec_stock_holding=bool(overlap),
          interpretation='Original fixed key correspondence across actual full paths, not a same-hold counterfactual or avoided loss.'))
    return dict(summary=dict(label=label,original_members=len(rr),candidate_exact_entry_matches=sum(x['candidate_exact_entry'] is not None for x in rr),
      direct_denied_at_original_decision=sum(x['direct_guard_rejection_at_original_decision'] is not None for x in rr),
      candidate_same_key_held_Nov30=sum(x['candidate_same_key_held_Nov30'] for x in rr),
      original_CORE_members=sum(x['original_layer']['role']=='core' for x in rr),
      candidate_original_CORE_keys_held_Nov30=sum(x['original_layer']['role']=='core' and x['candidate_same_key_held_Nov30'] for x in rr),
      original_Dec_wealth=sum((base['Dec_bykey'][k]['Dec_components']['wealth'] for k in keys),Z),
      candidate_same_key_Dec_contribution=sum((x['candidate_Dec_components']['wealth'] for x in rr if x['candidate_Dec_components'] is not None),Z),
      no_actual_Dec_holding_same_stock=sum(not x['candidate_has_any_Dec_stock_holding'] for x in rr)),rows=rr)

def case_stocks(r,base):
    result=[]
    for sid in ['000564.SZ','002317.SZ','601858.SH','000029.SZ']:
        rows=[x for x in r['layers'] if x['sid']==sid and x['opened']<='2022-12-30T15:10:00+08:00'];keys={x['key'] for x in rows}
        result.append(dict(sid=sid,actual_entries=rows,Dec_components={k:r['Dec_components_bykey'][k] for k in keys},
          actual_campaigns=[x for x in r['campaigns'] if x['sid']==sid and x['opened']<='2022-12-30T15:10:00+08:00'],
          policy_logs_through_Dec=[x for x in r['policy_logs'] if x['sid']==sid and str(x['at'])[:10]<='2022-12-30'],
          baseline_original_entry_keys=[x['key'] for x in base['layers'] if x['sid']==sid and x['opened']<='2022-12-30T15:10:00+08:00'],
          caveat='Campaign lifecycle net can extend after Dec; use Dec_components for month wealth, not future terminal P&L. Actual sell parts preserve original order clocks and mixed reasons.'))
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=HERE/'results_v1');p.add_argument('--available',action='store_true');args=p.parse_args()
    ready={};waiting=[]
    for arm in ARMS:
        for win in WINDOWS:
            rp=runpath(arm,win);ok=all((rp/f).exists() for f in ['DONE.json','TIMING.json','RUN_METADATA.json','pair/B.json.gz','pair/daily.jsonl.gz']) and auditpath(arm,win).exists()
            if ok:ok=json.loads((rp/'DONE.json').read_text())['completed'] and json.loads((rp/'TIMING.json').read_text())['completed']
            ready[arm,win]=ok
            if not ok:waiting.append(arm+'|'+win)
    if not args.available:assert not waiting,('Wait for DONE + independent audit, do not execute accounts',waiting)
    assert all(ready['BASELINE',w] for w in WINDOWS),'Reused audited baselines required'
    assert not args.out.exists(),'Preserve prior analysis; use a fresh --out for another authorized scan'
    freeze=read(ROOT/'H2_POLICY_FREEZE.json');assert freeze['arms']==ARMS
    M.SM={x['symbol']:x for x in read(M.W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
    spec=importlib.util.spec_from_file_location('h2_comparison_context',ROOT/'context_provider.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);provider=m.ContextProvider()
    read(ROOT/'relative_context/MANIFEST.json');fixed=read(E/'entry_exit_scale/analysis_summary/FIXED_ORIGINAL_TAILS.json')
    args.out.mkdir(parents=True);matrix=[];valid={};tails={};paths={};months={};cohorts={};activity={};completed=[]
    try:
        for win in WINDOWS:
            calendar=[x['at'] for x in read(runpath('BASELINE',win)/'pair/daily.jsonl.gz',gz=True,lines=True)]
            base=analyze('BASELINE',win,provider,calendar)
            originals=read(E/'entry_exit_scale/holding_exit'/f'{win}_LAYERS.json');expected={M.old_key(x):x for x in originals};assert set(expected)==base['bykey'].keys()
            for k,x in base['bykey'].items():eq(x['cost'],expected[k]['cost'],'original baseline cost');eq(x['net'],expected[k]['net'],'original baseline net')
            if win=='2022_2024':december(base);assert len([x for x in base['Dec_rows'] if x['cohort']=='old_inventory_Nov30'])==87;assert sum(x['cohort'].startswith('Dec_new_') for x in base['Dec_rows'])==122
            for arm in ARMS:
                if not ready[arm,win]:continue
                r=base if arm=='BASELINE' else analyze(arm,win,provider,calendar)
                if arm!='BASELINE' and win=='2022_2024':december(r)
                policy=policy_activity(r,provider);activity[arm+'|'+win]=policy['summary'];save(args.out,arm+'_'+win+'_AUTHORIZATION_ACTIVITY.json',policy)
                matrix+=r['periods'];valid[arm+'|'+win]=r['validation'];completed.append(arm+'|'+win)
                save(args.out,arm+'_'+win+'_LAYERS.json',r['layers']);save(args.out,arm+'_'+win+'_DAILY_WEALTH_SPLIT.json',r['daily'])
                t=M.tails_for(win,fixed[win],base,r);assert t['summary']['baseline_current_matches']=={'2022_2024':45,'strong':67}[win];tails[arm+'|'+win]=t['summary'];save(args.out,arm+'_'+win+'_FIXED83_94_TAILS.json',t)
                if arm!='BASELINE':c=M.matching(base,r);paths[arm+'|'+win]=c['summary'];save(args.out,arm+'_'+win+'_FULL_ENTRY_PATH_COMPARISON.json',c)
                if win=='2022_2024':
                    months[arm]=r['Dec_summary'];save(args.out,arm+'_DEC_OWN_CLOCK_CAPITALTIME_ROWS.json',r['Dec_rows']);save(args.out,arm+'_FOUR_STOCK_CLOCK_CHAINS.json',case_stocks(r,base))
                    for label,keys in [('ORIGINAL87',[x['key'] for x in base['Dec_rows'] if x['cohort']=='old_inventory_Nov30']),('ORIGINAL122',[x['key'] for x in base['Dec_rows'] if x['cohort'].startswith('Dec_new_')])]:
                        c=fixed_december_cohort(base,r,keys,label);cohorts[arm+'|'+label]=c['summary'];save(args.out,arm+'_'+label+'_FULL_KEY_CORRESPONDENCE.json',c)
            del base
        save(args.out,'PERIOD_ACCOUNT_MATRIX.json',matrix);save(args.out,'DEC_OWN_COHORT_WEALTH_CAPITALTIME_SUMMARY.json',months);save(args.out,'ORIGINAL87_122_CORRESPONDENCE_SUMMARY.json',cohorts)
        save(args.out,'FIXED_TAIL_SUMMARY.json',tails);save(args.out,'FULL_PATH_COMPARISON_SUMMARY.json',paths);save(args.out,'AUTHORIZATION_ACTIVITY_SUMMARY.json',activity)
        with (args.out/'PERIOD_ACCOUNT_MATRIX.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
        if not args.available:assert len(matrix)==32 and len(completed)==8
        save(args.out,'VALIDATION.json',dict(status='PASS_AVAILABLE_ONLY' if waiting else 'PASS_ALL_FIXED_32_PERIODS',completed=completed,waiting=waiting,financial_reader_source=str(READER),financial_reader_sha256=M.sha(READER),
          native_daily_mark_wealth_and_partial_basis=valid,original_baselines_3436_full_keys_cost_net_exact=True,new_accounts=0,new_account_events=0,
          limits='Existing outputs only. Core direct-targeting invariant is separate from actual endogenous CORE allocation. Fixed87/122 key correspondence is not a same-hold counterfactual; missing entries are not avoidable losses.'))
    except BaseException as e:save(args.out,'FAILURE.json',dict(error=repr(e),analysis_partial_preserved=True,new_accounts=0));raise
    finally:
        M.SRC[str(Path(__file__).resolve())]=M.sha(__file__);M.SRC[str(READER)]=M.sha(READER);M.SRC[str(ROOT/'context_provider.py')]=M.sha(ROOT/'context_provider.py')
        save(args.out,'SOURCE_SHA256.json',M.SRC);save(args.out,'DELIVERABLE_SHA256.json',{str(f.resolve()):M.sha(f) for f in args.out.iterdir() if f.is_file() and f.name!='DELIVERABLE_SHA256.json'})
    print('H2_COMPARISON_COMPLETE',len(completed),'existing paths',len(matrix),'fixed period rows',args.out)

if __name__=='__main__':main()
