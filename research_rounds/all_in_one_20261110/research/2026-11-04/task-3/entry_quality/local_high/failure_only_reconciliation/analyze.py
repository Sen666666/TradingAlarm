"""Reconcile parent's explicit failed-high wording; no parameter selection."""
from pathlib import Path
import importlib.util, json, hashlib
from collections import defaultdict
from types import SimpleNamespace
from dataclasses import dataclass
from typing import Mapping
from datetime import date,datetime
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP
import pandas as pd

O=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('reviewed_local_high_helpers',O.parent/'analyze.py');P=importlib.util.module_from_spec(sp);sp.loader.exec_module(P)
Z=D(0)
def save(name,x):
    with (O/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str)
def main():
    save('SCOPE.json',dict(reason='Parent explicitly says previous failed high. Strict v3 also retained success highs; reconcile that semantic difference, not an outcome-selected alternative.',
        feedback='Only completely closed campaign/mobile-subcycle sell-net minus buycash <0 generates failure high. No dividend AR or terminal winner tags.',
        unchanged='first flat trial, postentry H, old protection, one trial/samecore, exact original CORE reference risk quantities and static boundaries',account_events=0))
    env=dict(Decimal=D,ZERO=Z,ONE=D(1),SLIP=D('.0005'),D=D,dataclass=dataclass,Mapping=Mapping,ROUND_CEILING=ROUND_CEILING,ROUND_HALF_UP=ROUND_HALF_UP)
    P.ast_only(P.R/'rs-h1-execution-20261025/code/sector_account.py',{'dec','positive','FeeComponent','FeeSchedule'},env)
    P.ast_only(P.R/'lot-risk-allocation-20261029/code/study.py',{'fees','protection_risk','maximum_quantity'},env)
    class RuleUnavailable(ValueError):pass
    venv=dict(date=date,datetime=datetime,RuleUnavailable=RuleUnavailable)
    P.ast_only(P.R/'rs-h1-execution-20261025/code/market_rules.py',{'day','version_on'},venv);version=venv['version_on']
    rules=P.read(P.R/'pvr-act-comparison-20261027/execution-rules-v2.json');approved=P.read(P.R/'rs-h1-execution-20261025/inputs-v2/economic-protocol.json')['approved_proxy_ids']
    sm={x['symbol']:x for x in P.read(P.W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};frames={}
    def frame(sid):
        if sid not in frames:
            m=sm[sid];p=Path(m['refs']['facts']);h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==m['output_sha256'][str(p)];P.SOURCES[str(p)]=h
            frames[sid]=pd.read_parquet(p,columns=['close','segment_id','i_floor','factor'])
        return frames[sid]
    results={}
    for ref in ['2022_2024','strong']:
        source=P.read(O.parent/(ref+'_ROWS.json'));byid={x['layer']:x for x in source};bysid=defaultdict(list)
        for x in source:bysid[x['sid']].append(x)
        cp=P.B/('loss_correction/continuation2024_layers/PVR_NO60-CAMPAIGNS.json' if ref=='2022_2024' else 'loss_correction/pvr_no60_2025_26/PVR_NO60-CAMPAIGNS.json')
        camps=P.read(cp);failures=defaultdict(list)
        for c in camps:
            if c['closed'] and sum((P.n(byid[l]['strict_realized']) for l in c['layer_ids']),Z)<0:
                failures[c['sid']].append(dict(opened=c['opened'],closed=c['closed'],layers=c['layer_ids'],kind='full_stock_campaign'))
        for sid,seq in bysid.items():
            cycles=[]
            for x in sorted((x for x in seq if x['role']=='mobile'),key=lambda x:(P.at(x['opened']),x['layer'])):
                if not cycles or (cycles[-1]['closed'] is not None and P.at(x['opened'])>=P.at(cycles[-1]['closed'])):
                    cycles.append(dict(opened=x['opened'],closed=x['closed'],layers=[x['layer']],kind='mobile_only_subcycle'))
                else:
                    c=cycles[-1];c['layers'].append(x['layer']);c['closed']=None if c['closed'] is None or x['closed'] is None else max(c['closed'],x['closed'])
            for c in cycles:
                if c['closed'] and sum((P.n(byid[l]['strict_realized']) for l in c['layers']),Z)<0:failures[sid].append(c)
        rows=[]
        for e in source:
            x=dict(e);clock=P.at(e['decision_at']);day=pd.Timestamp(e['decision_at'][:10]);f=frame(e['sid']);cur=f.loc[day]
            failed=[c for c in failures[e['sid']] if P.at(c['closed'])<clock]
            previous=max(failed,key=lambda c:(P.at(c['closed']),c['kind']=='full_stock_campaign')) if failed else None
            hist=f.iloc[0:0] if previous is None else f.loc[(f.index>=pd.Timestamp(previous['opened'][:10]))&(f.index<pd.Timestamp(previous['closed'][:10]))]
            same=hist.empty or hist.segment_id.eq(cur.segment_id).all();fh=None if hist.empty or not same else float(hist.close.max())
            high=e['post_entry_high_excluding_current'];live=e['baseline_live_layer_ids']
            if e['role']=='core':label='CORE_UNCHANGED'
            elif not live:label='FLAT_FIRST_TRIAL'
            elif not same or (e['post_entry_high_observations']>0 and high is None):label='UNKNOWN_PRICE_DOMAIN'
            elif not e['original_I_alive']:label='I_PROTECTION_NOT_ALIVE'
            elif not e['old_live_mobile_protection_alive']:label='OLD_MOBILE_PROTECTION_NOT_ALIVE'
            elif high is None or float(cur.close)<=high:label='NO_NEW_POST_ENTRY_CLOSE_HIGH'
            elif previous is not None and (fh is None or float(cur.close)<=fh):label='NOT_RECOVERED_PREVIOUS_FAILED_HIGH'
            else:label='MATURE_LOCAL_AND_FAILED_HIGH_PROOF'
            q0=e['actual_fill_quantity'];qnew=None;why=[]
            if e['role']=='core' or label=='MATURE_LOCAL_AND_FAILED_HIGH_PROOF':qnew=q0
            elif label=='UNKNOWN_PRICE_DOMAIN':why=['price_source_domain_changed']
            elif not e['trial_available_in_baseline']:qnew=0
            else:
                why=list(e['reference_unknown_reasons'])
                if not e['original_I_alive']:why.append('original_I_floor_not_valid')
                if P.n(e['signal_factor'])!=P.n(e['fill_factor']):why.append('factor_changed_no_new_trial_mapping')
                if not why:
                    floor=P.n(cur.i_floor)/P.n(e['signal_factor']);pr=P.n(e['signal_close_raw'])*D('1.0005');po=P.n(e['actual_execution_price']);budget=P.n(e['decision_NAV'])*D('.0025')
                    r=version(rules['quantity_versions'][e['sid']],e['opened'][:10],approved)['rule'];rule=SimpleNamespace(buy_minimum=r['buy_minimum'],buy_step=r['buy_step'])
                    venue=version(rules['venue_versions'][e['sid']],e['opened'][:10],approved)['venue'];fv=version(rules['fee_versions'][venue],e['opened'][:10],approved)['schedule']
                    schedule=env['FeeSchedule'](fv['schedule_id'],tuple(env['FeeComponent'](**c) for c in fv['components']));par=P.n(rules['security_metadata'][e['sid']]['par_value'])
                    if floor<=0 or floor>=P.n(e['signal_close_raw']) or floor>=P.n(e['actual_raw_open']):qnew=0
                    else:
                        cap=min(q0,int(e['frozen_intent']['cap']));qd=env['maximum_quantity'](rule,cap,lambda q:env['protection_risk'](q,pr,floor,schedule,par)<=budget)
                        qnew=env['maximum_quantity'](rule,qd,lambda q:env['protection_risk'](q,po,floor,schedule,par)<=budget)
            x.update(strict_version_proof_class=e['proof_class'],strict_version_qnew=e['qnew'],proof_class=label,previous_failed_cycle=previous,previous_failed_high=fh,qnew=qnew,quantity_unknown=why,cut=Z if qnew is None else D(q0-qnew)/D(q0))
            rows.append(x)
        scopes={'ALL':rows}
        if ref=='2022_2024':
            scopes['2022_2023']=[x for x in rows if x['opened'][:10]<='2023-12-29'];scopes['strict303_postOct8_newfills']=[x for x in rows if x['opened'][:10]>'2024-10-08'];assert len(scopes['strict303_postOct8_newfills'])==303
        summary={name:dict(all=P.agg(z),by_action={a:P.agg([x for x in z if x['action']==a]) for a in sorted({x['action'] for x in z})},changed_from_strict=sum(x['qnew']!=x['strict_version_qnew'] or x['proof_class'].replace('FAILED_HIGH','MOBILE_EXIT_HIGH')!=x['strict_version_proof_class'] for x in z)) for name,z in scopes.items()}
        old=P.read(O.parent/(ref+'_FIXED_TAILS.json'));ids={x['layer'] for t in old for x in t['matched_actual_No60_rows']};summary['fixed_tail_matches']=P.agg([x for x in rows if x['layer'] in ids])
        results[ref]=summary
        save(ref+'_ROWS.json',[{k:x[k] for k in ['layer','sid','name','role','action','decision_at','opened','proof_class','strict_version_proof_class','strict_version_qnew','qnew','actual_fill_quantity','actual_execution_price','cost','net','qty','cut','previous_failed_cycle','previous_failed_high','quantity_unknown']} for x in rows])
    save('RESULTS.json',results);save('SOURCE_MANIFEST.json',dict(sources=P.SOURCES,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),account_events=0))
    print(json.dumps(results,ensure_ascii=False,default=str),flush=True)
if __name__=='__main__':main()
