"""Independent raw-book replay/classification and standalone all-in fee audit."""
from pathlib import Path
from decimal import Decimal, getcontext, ROUND_CEILING, ROUND_HALF_UP
from collections import defaultdict
from datetime import datetime
import gzip, hashlib, json
import pandas as pd

getcontext().prec=70
D=Decimal; Z=D(0); O=Path(__file__).resolve().parent; P=O.parent/'local_high'
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
checks=defaultdict(int)
def read(p):
    p=Path(p)
    if p.suffix=='.gz':
        with gzip.open(p,'rt') as f:return json.load(f)
    return json.loads(p.read_text())
def n(x):return D(str(x))
def dt(x):return datetime.fromisoformat(x)
def eq(a,b,key):
    assert abs(n(a)-n(b))<D('1e-17'),(key,a,b)
    checks[key]+=1
def version(vs,day):
    found=[v for v in vs if v['from']<=day and (not v.get('to') or day<v['to'])]
    assert len(found)==1
    return found[0]
rules=read(R/'pvr-act-comparison-20261027/execution-rules-v2.json')
sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
frames={}
def frame(sid):
    if sid not in frames:frames[sid]=pd.read_parquet(sm[sid]['refs']['facts'],columns=['close','segment_id','i_target','i_floor','factor','raw_close'])
    return frames[sid]
def fee(q,p,components,side,par):
    if not q:return Z
    total=Z
    for c in components:
        if c.get('side','both') not in ['both',side]:continue
        amount_basis=c.get('amount_basis','notional')
        base=D(q)*p if amount_basis=='notional' else D(q) if amount_basis=='shares' else D(q)*par
        value=max(n(c.get('minimum_local','0')),base*n(c['rate']))
        if c.get('maximum_local') is not None:value=min(value,n(c['maximum_local']))
        if c.get('rounding_unit') is not None:
            unit=n(c['rounding_unit']);value=(value/unit).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil' else ROUND_HALF_UP)*unit
        total+=value
    return total
def risk(q,p,floor,components,par):
    stop=floor*D('.9995')
    return max(Z,D(q)*(p-stop)+fee(q,p,components,'buy',par)+fee(q,stop,components,'sell',par))
def qmax(cap,minimum,step,allowed):
    # Independent single joint constraint, then verify the next legal quantity.
    if cap<minimum or not allowed(minimum):return 0
    lo=0;hi=(cap-minimum)//step
    while lo<hi:
        mid=(lo+hi+1)//2
        if allowed(minimum+mid*step):lo=mid
        else:hi=mid-1
    q=minimum+lo*step
    assert allowed(q) and (q+step>cap or not allowed(q+step))
    return q
def aggregate(rows):
    known=[x for x in rows if x['qnew'] is not None]
    loss=sum((D(x['actual_fill_quantity']-x['qnew'])/D(x['actual_fill_quantity'])*-min(Z,n(x['net'])) for x in known),Z)
    profit=sum((D(x['actual_fill_quantity']-x['qnew'])/D(x['actual_fill_quantity'])*max(Z,n(x['net'])) for x in known),Z)
    return dict(layers=len(rows),stocks=len({x['sid'] for x in rows}),buycash=sum((n(x['cost']) for x in rows),Z),original_net=sum((n(x['net']) for x in rows),Z),
        original_positive=sum((max(Z,n(x['net'])) for x in rows),Z),original_negative=sum((min(Z,n(x['net'])) for x in rows),Z),
        unknown_quantity_layers=sum(x['qnew'] is None for x in rows),known_changed_layers=sum(x['qnew']<x['actual_fill_quantity'] for x in known),
        original_buycash_of_changed=sum((n(x['cost']) for x in known if x['qnew']<x['actual_fill_quantity']),Z),removed_negative_STATIC=loss,removed_positive_STATIC=profit,net_change_STATIC=loss-profit,
        reduced_actual_gross=sum((D(x['actual_fill_quantity']-x['qnew'])*n(x['actual_execution_price']) for x in known),Z),open_layers=sum(bool(x['qty']) for x in rows))
def checkagg(rows,value):
    actual=aggregate(rows)
    assert set(actual)==set(value)
    for k,v in actual.items():eq(v,value[k],'aggregate_'+k)

manifest=read(P/'SOURCE_MANIFEST.json')
assert manifest['script_sha256']==hashlib.sha256((P/'analyze.py').read_bytes()).hexdigest()
for path,sha in manifest['sources'].items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha,path
    checks['source_sha256']+=1
results=read(P/'RESULTS.json');summaries={}
for ref,root in [('2022_2024',B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024'),('strong',B/'pvr_pool_feasibility/runs/2025_26')]:
    rows=read(P/(ref+'_ROWS.json')); byid={x['layer']:x for x in rows}
    original=read(B/f'loss_correction/entry_risk_commitment_review/{ref}_ENTRIES.json');orig={x['layer']:x for x in original}
    book=read(root/'pair/B.json.gz')
    rawbuys={t['layer']:t for t in book['trades'] if t['side']=='buy'}
    assert len(rawbuys)==len(rows)
    for lid,e in orig.items():
        t=rawbuys[lid]
        eq(t['shares'],e['actual_fill_quantity'],'all_raw_fill_quantity')
        eq(t['floor'],e['frozen_initial_adjusted_floor'],'all_raw_initial_floor')
        eq(n(t['gross_cny'])+n(t['fees_cny']),e['cost'],'all_raw_buycash')
    events=[]
    for i,t in enumerate(book['trades']):events.append((dt(t['at']),1,i,'trade',t))
    for i,a in enumerate(book['audit']):
        if a['kind']=='split':events.append((dt(a['at']),0,i,'split',a))
    events.sort(key=lambda x:x[:3])
    timeline=sorted(rows,key=lambda x:(dt(x['decision_at']),x['layer']))
    holdings=defaultdict(int); buys={};active_campaign={};active_mobile={};campaigns=defaultdict(list);mobilecycles=defaultdict(list)
    ep=0; unknown=[]
    def advance(clock):
        nonlocal_unused=None
        global ep
        while ep<len(events) and events[ep][0]<clock:
            when,_,_,kind,t=events[ep];ep+=1
            if kind=='split':
                for lid,q in list(holdings.items()):
                    if orig[lid]['sid']==t['sid'] and q:
                        product=D(q)*n(t['ratio']);assert product==int(product);holdings[lid]=int(product)
                continue
            sid=t['security_id'];before=sum(q for lid,q in holdings.items() if orig[lid]['sid']==sid)
            before_m=sum(q for lid,q in holdings.items() if orig[lid]['sid']==sid and orig[lid]['role']=='mobile')
            if t['side']=='buy':
                lid=t['layer'];assert lid not in buys;buys[lid]=t
                eq(t['shares'],orig[lid]['actual_fill_quantity'],'actual_fill_quantity')
                eq(t['floor'],orig[lid]['frozen_initial_adjusted_floor'],'actual_initial_floor')
                eq(n(t['gross_cny'])+n(t['fees_cny']),orig[lid]['cost'],'raw_buycash')
                if before==0:active_campaign[sid]=dict(opened=t['at'],closed=None,layers=[],anchor_kind='full_stock_campaign')
                active_campaign[sid]['layers'].append(lid)
                if orig[lid]['role']=='mobile':
                    if before_m==0:active_mobile[sid]=dict(opened=t['at'],closed=None,layers=[],anchor_kind='mobile_only_subcycle')
                    active_mobile[sid]['layers'].append(lid)
                holdings[lid]+=t['shares']
            else:
                for part in t['parts']:
                    lid=part['layer'];holdings[lid]-=part['shares'];assert holdings[lid]>=0
                after=sum(q for lid,q in holdings.items() if orig[lid]['sid']==sid)
                after_m=sum(q for lid,q in holdings.items() if orig[lid]['sid']==sid and orig[lid]['role']=='mobile')
                if before_m and not after_m:
                    c=active_mobile.pop(sid);c['closed']=t['at'];mobilecycles[sid].append(c)
                if before and not after:
                    c=active_campaign.pop(sid);c['closed']=t['at'];campaigns[sid].append(c)
    for row in timeline:
        originalrow=orig[row['layer']];assert all(row[k]==v for k,v in originalrow.items())
        sid=row['sid'];clock=dt(row['decision_at']);day=pd.Timestamp(row['decision_at'][:10]);advance(clock)
        f=frame(sid);cur=f.loc[day]
        live=sorted(lid for lid,q in holdings.items() if q and orig[lid]['sid']==sid)
        assert live==sorted(row['baseline_live_layer_ids']);checks['raw_live_layer_ids']+=1
        prior=[(lid,t) for lid,t in buys.items() if orig[lid]['sid']==sid]
        last=max(prior,key=lambda x:(dt(x[1]['at']),x[0])) if prior else None
        assert row['last_actual_buy_layer']==(None if last is None else last[0])
        history=f[(f.index>=pd.Timestamp(last[1]['at'][:10]))&(f.index<day)] if last else f.iloc[0:0]
        same=history.empty or history.segment_id.eq(cur.segment_id).all()
        high=None if history.empty or not same else float(history.close.max())
        assert high==row['post_entry_high_excluding_current'] and len(history)==row['post_entry_high_observations'];checks['post_entry_H_excludes_current']+=1
        completed=campaigns[sid]+mobilecycles[sid]
        previous=max(completed,key=lambda x:(dt(x['closed']),x['anchor_kind']=='full_stock_campaign')) if completed else None
        assert previous==row['previous_completed_mobile_cycle'];checks['raw_exit_anchor_identity']+=1
        exithistory=f[(f.index>=pd.Timestamp(previous['opened'][:10]))&(f.index<pd.Timestamp(previous['closed'][:10]))] if previous else f.iloc[0:0]
        exit_same=exithistory.empty or exithistory.segment_id.eq(cur.segment_id).all()
        exit_high=None if exithistory.empty or not exit_same else float(exithistory.close.max())
        assert exit_high==row['previous_mobile_exit_high'];checks['exit_H_excludes_flat_day']+=1
        ialive=bool(cur.i_target) and pd.notna(cur.i_floor) and float(cur.close)>float(cur.i_floor)
        oldalive=all(n(cur.close)>n(buys[lid]['floor']) for lid in live if orig[lid]['role']=='mobile')
        if row['role']=='core':label='CORE_UNCHANGED'
        elif not live:label='FLAT_FIRST_TRIAL'
        elif not same or not exit_same:label='UNKNOWN_PRICE_DOMAIN'
        elif not ialive:label='I_PROTECTION_NOT_ALIVE'
        elif not oldalive:label='OLD_MOBILE_PROTECTION_NOT_ALIVE'
        elif high is None or not float(cur.close)>high:label='NO_NEW_POST_ENTRY_CLOSE_HIGH'
        elif previous is not None and (exit_high is None or not float(cur.close)>exit_high):label='NOT_RECOVERED_PREVIOUS_MOBILE_EXIT_HIGH'
        else:label='MATURE_LOCAL_AND_EXIT_HIGH_PROOF'
        assert label==row['proof_class'];checks['proof_classification']+=1
        core_restart=not any(orig[lid]['role']=='mobile' for lid in live) and bool(mobilecycles[sid]) and any(orig[lid]['role']=='core' and dt(buys[lid]['at'])<dt(mobilecycles[sid][-1]['closed']) for lid in live)
        assert bool(core_restart)==row['mobile_restart_with_core_alive'];checks['same_core_survived_mobile_flat']+=1
        campaign_prior=bool(active_campaign.get(sid))
        trial=not campaign_prior or core_restart
        assert bool(trial)==row['trial_available_in_baseline'];checks['one_trial_availability']+=1
        q0=row['actual_fill_quantity'];expected=None;why=[]
        if row['role']=='core' or label=='MATURE_LOCAL_AND_EXIT_HIGH_PROOF':expected=q0
        elif label=='UNKNOWN_PRICE_DOMAIN':why=['price_source_domain_changed']
        elif not trial:expected=0
        else:
            why=list(row['reference_unknown_reasons'])
            if not ialive:why.append('original_I_floor_not_valid')
            if n(row['signal_factor'])!=n(row['fill_factor']):why.append('factor_changed_no_new_trial_mapping')
            if not why:
                floor=n(cur.i_floor)/n(row['signal_factor']);pref=n(row['signal_close_raw'])*D('1.0005');p=n(row['actual_execution_price']);budget=n(row['decision_NAV'])*D('.0025')
                cap=min(q0,row['frozen_intent']['cap']);qr=version(rules['quantity_versions'][sid],row['opened'][:10])['rule']
                venue=version(rules['venue_versions'][sid],row['opened'][:10])['venue'];schedule=version(rules['fee_versions'][venue],row['opened'][:10])['schedule'];components=schedule['components'];par=n(rules['security_metadata'][sid]['par_value'])
                # Also ensure no frozen decision schedule/version was replaced by a new OPEN version.
                oldvenue=version(rules['venue_versions'][sid],row['decision_at'][:10])['venue']
                assert version(rules['fee_versions'][oldvenue],row['decision_at'][:10])['schedule']==schedule
                assert version(rules['quantity_versions'][sid],row['decision_at'][:10])['rule']==qr
                checks['decision_OPEN_rule_schedule_identical']+=1
                if floor<=0 or floor>=n(row['signal_close_raw']) or floor>=n(row['actual_raw_open']):expected=0
                else:expected=qmax(cap,qr['buy_minimum'],qr['buy_step'],lambda q:risk(q,pref,floor,components,par)<=budget and risk(q,p,floor,components,par)<=budget)
                eq(floor,row['trial_CORE_reference_I_floor_raw'],'trial_I_floor_raw');eq(budget,row['trial_risk_budget'],'trial_CORE_budget')
                assert schedule['schedule_id']==row['trial_fee_schedule']
        assert row['quantity_unknown']==why,(row['layer'],row['quantity_unknown'],why)
        assert row['qnew']==expected,(row['layer'],row['qnew'],expected)
        checks['independent_joint_CORE_quantity']+=1
        if expected is None:unknown.append(dict(layer=row['layer'],sid=sid,reasons=why,original_net=row['net']))
        else:eq(D(q0-expected)/D(q0),row['cut'],'static_cut')
    scopes={'ALL':rows}
    if ref=='2022_2024':
        scopes['2022_2023']=[x for x in rows if x['opened'][:10]<='2023-12-29']
        scopes['strict303_postOct8_newfills']=[x for x in rows if '2024-10-08'<x['opened'][:10]<='2024-12-31']
    for scope,sr in scopes.items():
        r=results[ref][scope];checkagg(sr,r['all'])
        for label,value in r['by_proof'].items():checkagg([x for x in sr if x['proof_class']==label],value)
        for action,value in r['by_action'].items():
            ar=[x for x in sr if x['action']==action];checkagg(ar,value['all'])
            for label,group in value['by_proof'].items():checkagg([x for x in ar if x['proof_class']==label],group)
        checkagg([x for x in sr if x['mobile_restart_with_core_alive']],r['core_alive_mobile_restart'])
    tails=read(P/(ref+'_FIXED_TAILS.json'));oldtail=read(B/f'risk_constraints/ma63_information_diagnostic_v1/{ref}_ORIGINAL_FIXED_TAIL_COVERAGE.json')
    for new,old in zip(tails,oldtail):
        assert new['original']==old['original'] and new['unmatched']==old['unmatched']
        assert [x['layer'] for x in new['matched_actual_No60_rows']]==old['matched_No60_layers']
        assert all(x==byid[x['layer']] for x in new['matched_actual_No60_rows']);checks['fixed_tail_identity']+=1
    matched=[x for t in tails for x in t['matched_actual_No60_rows']];assert len(matched)==(45 if ref=='2022_2024' else 67)
    r=results[ref]['fixed_original_tail'];checkagg(matched,r['actual_matched_money'])
    for label,g in r['actual_matched_by_proof'].items():checkagg([x for x in matched if x['proof_class']==label],g)
    summaries[ref]=dict(scopes={k:results[ref][k]['all'] for k in scopes},matched_fixed_tail=r['actual_matched_money'],unknown=unknown,
        core_alive_restarts=aggregate([x for x in rows if x['mobile_restart_with_core_alive']]),
        focus_cases=[{k:x[k] for k in ['sid','name','layer','role','action','decision_at','opened','last_actual_buy_layer','post_entry_high_excluding_current','previous_mobile_exit_high','baseline_live_layer_ids','mobile_restart_with_core_alive','proof_class','actual_fill_quantity','qnew','cost','net','cut','quantity_unknown']} for x in rows if x['sid'] in ['002969.SZ','688146.SH','301319.SZ']])

out=dict(status='PASS_WITH_SCOPE_LIMITS',checks=dict(checks),summaries=summaries,
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    reviewed_producer_script_sha256=manifest['script_sha256'],
    conclusion='STOP before account engineering: strong-window static positive reduction exceeds static negative reduction; simple local-high/CORE trial candidate materially harms known actual tails.',
    limitations=['Baseline path classification only. Candidate quantities would change whether later baseline mature/high/campaign anchors exist.',
        'Static scaled net includes original fee/AR/marks and is not a shadow ledger, policy return, avoidable-loss estimate or NAV.',
        'Market signal calculation and fresh CP1 inputs reused from actual funded baseline; not recomputed.',
        'Changed factor/source and invalid reference known-quantity exclusions retained, never set to zero in primary totals.',
        'Higher-low exception not specified/tested; no evidence licenses adding it after results.',
        'Current universe/industry snapshots, daily execution proxy and already-consumed historical data remain.'])
(O/'AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps(dict(status=out['status'],checks=checks),ensure_ascii=False,default=str,indent=2))
