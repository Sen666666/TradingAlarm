"""Saved baseline local-high coverage + CORE-sized trial static sensitivity."""
from pathlib import Path
from decimal import Decimal as D, getcontext, ROUND_CEILING, ROUND_HALF_UP
from collections import defaultdict
from datetime import date, datetime
from dataclasses import dataclass
from typing import Mapping
from types import SimpleNamespace
import ast, gzip, hashlib, json
import pandas as pd

getcontext().prec = 60
O = Path(__file__).resolve().parent
B = Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
W = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
R = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
SOURCES = {}; Z=D(0)
def read(p):
    p=Path(p); SOURCES[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    if p.suffix=='.gz':
        with gzip.open(p,'rt') as f:return json.load(f)
    return json.loads(p.read_text())
def save(name,value):
    with (O/name).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def n(x):return D(str(x))
def at(x):return datetime.fromisoformat(x)
def ast_only(path,names,env):
    path=Path(path);raw=path.read_bytes();SOURCES[str(path)]=hashlib.sha256(raw).hexdigest()
    nodes=[x for x in ast.parse(raw).body if isinstance(x,(ast.FunctionDef,ast.ClassDef)) and x.name in names]
    assert len(nodes)==len(names)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path)+'::pure-selected','exec'),env)
    return env

def agg(rows):
    net=sum((n(x['net']) for x in rows),Z)
    known=[x for x in rows if x.get('qnew') is not None]
    loss=sum((-x['cut']*min(Z,n(x['net'])) for x in known),Z)
    profit=sum((x['cut']*max(Z,n(x['net'])) for x in known),Z)
    return dict(layers=len(rows),stocks=len({x['sid'] for x in rows}),buycash=sum((n(x['cost']) for x in rows),Z),
        original_net=net,original_positive=sum((max(Z,n(x['net'])) for x in rows),Z),original_negative=sum((min(Z,n(x['net'])) for x in rows),Z),
        unknown_quantity_layers=sum(x.get('qnew') is None for x in rows),known_changed_layers=sum(x['qnew']<x['actual_fill_quantity'] for x in known),
        original_buycash_of_changed=sum((n(x['cost']) for x in known if x['cut']>0),Z),
        removed_negative_STATIC=loss,removed_positive_STATIC=profit,net_change_STATIC=loss-profit,
        reduced_actual_gross=sum((D(x['actual_fill_quantity']-x['qnew'])*n(x['actual_execution_price']) for x in known),Z),
        open_layers=sum(bool(x['qty']) for x in rows))

def main():
    read(O/'PROTOCOL.json')
    env=dict(Decimal=D,ZERO=Z,ONE=D(1),SLIP=D('.0005'),D=D,dataclass=dataclass,Mapping=Mapping,
             ROUND_CEILING=ROUND_CEILING,ROUND_HALF_UP=ROUND_HALF_UP)
    ast_only(R/'rs-h1-execution-20261025/code/sector_account.py',{'dec','positive','FeeComponent','FeeSchedule'},env)
    ast_only(R/'lot-risk-allocation-20261029/code/study.py',{'fees','protection_risk','maximum_quantity'},env)
    FeeComponent,FeeSchedule=env['FeeComponent'],env['FeeSchedule']
    maxq,protection=env['maximum_quantity'],env['protection_risk']
    class RuleUnavailable(ValueError):pass
    ven=dict(date=date,datetime=datetime,RuleUnavailable=RuleUnavailable)
    ast_only(R/'rs-h1-execution-20261025/code/market_rules.py',{'day','version_on'},ven)
    version=ven['version_on']
    ruledata=read(R/'pvr-act-comparison-20261027/execution-rules-v2.json')
    approved=read(R/'rs-h1-execution-20261025/inputs-v2/economic-protocol.json')['approved_proxy_ids']
    sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
    frames={}
    def frame(sid):
        if sid not in frames:
            p=Path(sm[sid]['refs']['facts']);h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==sm[sid]['output_sha256'][str(p)];SOURCES[str(p)]=h
            frames[sid]=pd.read_parquet(p,columns=['close','segment_id','i_target','i_floor','factor','raw_close'])
        return frames[sid]
    results={}
    for ref in ['2022_2024','strong']:
        entries=read(B/f'loss_correction/entry_risk_commitment_review/{ref}_ENTRIES.json')
        campath=B/('loss_correction/continuation2024_layers/PVR_NO60-CAMPAIGNS.json' if ref=='2022_2024' else 'loss_correction/pvr_no60_2025_26/PVR_NO60-CAMPAIGNS.json')
        campaigns=read(campath); cmap={lid:c for c in campaigns for lid in c['layer_ids']}
        assert len(cmap)==len(entries)
        bysid=defaultdict(list)
        for x in entries:bysid[x['sid']].append(x)
        mobilecycles={}
        for sid,seq in bysid.items():
            cycles=[]
            for x in sorted((x for x in seq if x['role']=='mobile'),key=lambda x:(at(x['opened']),x['layer'])):
                if not cycles or (cycles[-1]['closed'] is not None and at(x['opened'])>=at(cycles[-1]['closed'])):
                    cycles.append(dict(opened=x['opened'],closed=x['closed'],layers=[x['layer']]))
                else:
                    c=cycles[-1];c['layers'].append(x['layer'])
                    c['closed']=None if c['closed'] is None or x['closed'] is None else max(c['closed'],x['closed'])
            mobilecycles[sid]=cycles
        rows=[]
        for e in entries:
            x=dict(e);sid=e['sid'];clock=at(e['decision_at']);day=pd.Timestamp(e['decision_at'][:10]);f=frame(sid);cur=f.loc[day];segment=cur.segment_id
            prior=[p for p in bysid[sid] if at(p['opened'])<clock];live=[p for p in prior if not p['closed'] or at(p['closed'])>clock]
            last=max(prior,key=lambda p:(at(p['opened']),p['layer'])) if prior else None
            hist=f.iloc[0:0] if last is None else f.loc[pd.Timestamp(last['opened'][:10]):].loc[:day].iloc[:-1]
            # Current observation is excluded before the strict comparison.
            hist=hist.loc[hist.index<day]
            same=hist.empty or hist.segment_id.eq(segment).all()
            high=None if hist.empty or not same else float(hist.close.max())
            completed=[c for c in mobilecycles[sid] if c['closed'] and at(c['closed'])<clock]
            previous=completed[-1] if completed else None
            exithist=f.iloc[0:0] if previous is None else f.loc[(f.index>=pd.Timestamp(previous['opened'][:10]))&(f.index<pd.Timestamp(previous['closed'][:10]))]
            exit_same=exithist.empty or exithist.segment_id.eq(segment).all()
            exit_high=None if exithist.empty or not exit_same else float(exithist.close.max())
            i_alive=bool(cur.i_target) and pd.notna(cur.i_floor) and float(cur.close)>float(cur.i_floor)
            broke_high=high is not None and float(cur.close)>high
            broke_exit=previous is None or (exit_high is not None and float(cur.close)>exit_high)
            if e['role']=='core':label='CORE_UNCHANGED'
            elif not live:label='FLAT_FIRST_TRIAL'
            elif not same or not exit_same:label='UNKNOWN_PRICE_DOMAIN'
            elif not i_alive:label='I_PROTECTION_NOT_ALIVE'
            elif not broke_high:label='NO_NEW_POST_ENTRY_CLOSE_HIGH'
            elif not broke_exit:label='NOT_RECOVERED_PREVIOUS_MOBILE_EXIT_HIGH'
            else:label='MATURE_LOCAL_AND_EXIT_HIGH_PROOF'
            campaign=cmap[e['layer']]
            campaign_prior=[p for p in prior if p['layer'] in campaign['layer_ids']]
            live_mobile=[p for p in live if p['role']=='mobile']
            subcycle_restart=bool(live and not live_mobile and previous is not None)
            trial_available=(not campaign_prior) or subcycle_restart
            x.update(proof_class=label,current_signal_close=float(cur.close),original_I_floor=float(cur.i_floor) if pd.notna(cur.i_floor) else None,
                original_I_alive=i_alive,baseline_live_layer_ids=[p['layer'] for p in live],
                last_actual_buy_layer=None if last is None else last['layer'],last_actual_buy_at=None if last is None else last['opened'],
                post_entry_high_excluding_current=high,post_entry_high_observations=len(hist),
                previous_completed_mobile_cycle=previous,previous_mobile_exit_high=exit_high,
                trial_available_in_baseline=trial_available,mobile_restart_with_core_alive=subcycle_restart,
                baseline_campaign_number=campaign['campaign_number'],qnew=None,quantity_unknown=[],cut=Z)
            q0=e['actual_fill_quantity'];minimum=version(ruledata['quantity_versions'][sid],e['opened'][:10],approved)['rule'];rule=SimpleNamespace(buy_minimum=minimum['buy_minimum'],buy_step=minimum['buy_step'])
            if e['role']=='core' or label=='MATURE_LOCAL_AND_EXIT_HIGH_PROOF':x['qnew']=q0
            elif label=='UNKNOWN_PRICE_DOMAIN':x['quantity_unknown'].append('price_source_domain_changed')
            elif not trial_available:x['qnew']=0
            else:
                why=list(e['reference_unknown_reasons'])
                if not i_alive:why.append('original_I_floor_not_valid')
                if n(e['signal_factor'])!=n(e['fill_factor']):why.append('factor_changed_no_new_trial_mapping')
                if why:x['quantity_unknown']=why
                else:
                    floor=n(cur.i_floor)/n(e['signal_factor']);refp=n(e['signal_close_raw'])*D('1.0005');p=n(e['actual_execution_price']);risk=n(e['decision_NAV'])*D('.0025')
                    qrule=version(ruledata['venue_versions'][sid],e['opened'][:10],approved);venue=qrule['venue'];v=version(ruledata['fee_versions'][venue],e['opened'][:10],approved)['schedule']
                    schedule=FeeSchedule(v['schedule_id'],tuple(FeeComponent(**c) for c in v['components']));par=n(ruledata['security_metadata'][sid]['par_value'])
                    # Freeze decision cap, then OPEN risk recheck. No gap expansion.
                    cap=min(q0,int(e['frozen_intent']['cap']))
                    if floor<=0 or floor>=n(e['signal_close_raw']) or floor>=n(e['actual_raw_open']):x['qnew']=0
                    else:
                        qdec=maxq(rule,cap,lambda q:protection(q,refp,floor,schedule,par)<=risk)
                        x['qnew']=maxq(rule,qdec,lambda q:protection(q,p,floor,schedule,par)<=risk)
                    x.update(trial_CORE_reference_I_floor_raw=floor,trial_risk_budget=risk,trial_decision_reference_price=refp,trial_OPEN_execution_price=p,
                        trial_fee_schedule=v['schedule_id'],trial_legal_minimum=rule.buy_minimum,trial_legal_step=rule.buy_step)
            if x['qnew'] is not None:
                assert 0<=x['qnew']<=q0
                x['cut']=D(q0-x['qnew'])/D(q0)
            rows.append(x)
        scopes={'ALL':rows}
        if ref=='2022_2024':
            scopes['2022_2023']=[x for x in rows if x['opened'][:10]<='2023-12-29']
            scopes['strict303_postOct8_newfills']=[x for x in rows if '2024-10-08'<x['opened'][:10]<='2024-12-31'];assert len(scopes['strict303_postOct8_newfills'])==303
        summary={}
        for name,sr in scopes.items():
            summary[name]=dict(all=agg(sr),by_proof={k:agg([x for x in sr if x['proof_class']==k]) for k in sorted({x['proof_class'] for x in sr})},
                by_action={a:dict(all=agg([x for x in sr if x['action']==a]),by_proof={k:agg([x for x in sr if x['action']==a and x['proof_class']==k]) for k in sorted({x['proof_class'] for x in sr})}) for a in sorted({x['action'] for x in sr})},
                core_alive_mobile_restart=agg([x for x in sr if x['mobile_restart_with_core_alive']]))
        old=read(B/f'risk_constraints/ma63_information_diagnostic_v1/{ref}_ORIGINAL_FIXED_TAIL_COVERAGE.json');bylayer={x['layer']:x for x in rows};tails=[]
        for t in old:
            tails.append(dict(original=t['original'],matched_actual_No60_rows=[bylayer[lid] for lid in t['matched_No60_layers']],unmatched=t['unmatched']))
        matches=[x for t in tails for x in t['matched_actual_No60_rows']]
        assert len(tails)==(83 if ref=='2022_2024' else 94)
        summary['fixed_original_tail']=dict(original_members=len(tails),matched_members=sum(not t['unmatched'] for t in tails),unmatched_members=sum(t['unmatched'] for t in tails),
            actual_matched_money=agg(matches),actual_matched_by_proof={k:agg([x for x in matches if x['proof_class']==k]) for k in sorted({x['proof_class'] for x in matches})})
        save(ref+'_ROWS.json',rows);save(ref+'_FIXED_TAILS.json',tails)
        save(ref+'_FOCUS_CASES.json',[x for x in rows if x['sid'] in ['002969.SZ','688146.SH','301319.SZ','601595.SH','000620.SZ']])
        results[ref]=summary
        print(ref,json.dumps(summary,default=str,ensure_ascii=False),flush=True)
    save('RESULTS.json',results)
    save('SOURCE_MANIFEST.json',dict(sources=SOURCES,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),account_events=0,new_signal_events=0,
        quantity_is_baseline_static_sensitivity=True,limitations=['future candidate fills/campaigns/signals/resources not reconstructed','minimum fees and dividends scaled only in sensitivity, no exact shadow ledger','source/factor unknowns excluded from primary sensitivity','current snapshots and daily execution proxy, not PIT/OOS','pivot higher-low exception not selected or tested']))

if __name__=='__main__':main()
