"""Bounded original two-session technical identity/causality gates only."""
from pathlib import Path
import json,time,copy,traceback,pickle,hashlib,re
import adapter as A
E=A.E
def norm(x):return json.loads(json.dumps(x,default=E.encode))
def grant(r,out,end):
    p=out/'GRANT.json';A.save(p,dict(parent_approved=True,technical_prefix_only=True,runtime_sha256=A.sha(A.__file__),window=r.window,ablation_enabled=r.ablation_enabled,branch=r.branch,start='2022-01-04' if r.window=='2022' else '2025-07-01',end=end))
    r.bind_grant(p)
def run(window,on,branch,out):
    out.mkdir(parents=True,exist_ok=False);t=time.perf_counter();r=A.Runner(window,ablation_enabled=on,branch=branch)
    days=A.M.P.EXPECTED[window];grant(r,out,days[-1]);load=time.perf_counter()-t
    events=[]
    for day in days:
        if r.inputs.actions(day):r.corporate_actions(day)
        for phase in ['OPEN','CLOSE']:
            r.step(day,phase);r.assert_observers()
            if phase=='CLOSE':E.require(r.close_stages[r.last_completed_event.isoformat()]['optional_status']=='succeeded','optional phase not completed')
            events.append(dict(day=day,phase=phase,bridge=norm(r.account.bridge(r.last_completed_event))))
    p=out/'FINAL.pkl';r.checkpoint(p);n=A.Runner.restore(p)
    E.require(norm(r.observable(r.last_completed_event))==norm(n.observable(n.last_completed_event)),'complete observable restart changed')
    E.require(r.binding()==n.binding(),'restored exact binding changed')
    d=dict(window=window,on=on,branch=branch,load_seconds=load,total_seconds=time.perf_counter()-t,events=events,final=norm(r.observable(r.last_completed_event)),source=r.source_binding(),restart_exact=True)
    A.save(out/'RESULT.json',d);print('DONE',window,on,branch,'load',round(load,2),'total',round(d['total_seconds'],2),flush=True);return d
def early_compare(a,b):
    # Prefix clocks, full cash bridge, fills/trades, Q/D including failures and
    # pending/retained quantity are compared, identity envelopes kept separate.
    aa=a['final'];bb=b['final'];account_keys=['balance','layers','buys','exits','trades','fills','rejections','native_settlements','native_dividends','native_actions','native_completed','core_epochs','share_ratio','market_marks','market_asof','market_factors','facts_floors']
    checks={}
    for k in account_keys:checks['account.'+k]=aa['account'][k]==bb['account'][k]
    for k in ['f1','f1seq','pending','local_wait','last_completed','action_log','events','mapping']:checks[k]=aa[k]==bb[k]
    checks['all_projection_QD']=[(x['projection']['Q'],x['projection']['D']) for x in aa['results']]==[(x['projection']['Q'],x['projection']['D']) for x in bb['results']]
    return checks
def fullstate(path):
    p=Path(path);side=A.read(p.with_suffix('.provenance.json'))
    E.require(A.sha(p)==side['checkpoint_sha256'],'comparison checkpoint byte identity')
    r=pickle.loads(p.read_bytes());r.account.owner=r
    E.require(r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'actual loaded source/engine binding changed')
    r.assert_observers()
    for c in r.authority.certificates.values():r.verify_native(c)
    fields=['lifecycle','last_stock_state','cursor','goal_intents','_busy_goals','active_intents','rank_bindings','native_audit','events','action_log','transitions','windows','event_ids','action_ids','trusted']
    d=dict(observable=norm(r.observable(r.last_completed_event)))
    d.update({k:norm(r.__dict__[k]) for k in fields if k in r.__dict__})
    d['native_audit']=norm(r.account.audit_log)
    d['native_decisions']=norm(r.account.decisions)
    # Reconstruct the ONLY differing necessary-stage digest, the final day,
    # under the audited D-empty two-day witness. Previous source goals come
    # from the ORIGINAL OPEN, with explicit prior-certificate ID rebinding.
    lastday=A.M.P.EXPECTED[r.window][-1]
    E.require(r.last_completed_event.date().isoformat()==lastday and not r.results[-1]['projection']['D'],'D-empty final two-day witness required')
    original_dir=A.ROOT/f'g-s-C-two-day-finance-20261102/runs/{r.window}-C10'
    op=A.read(original_dir/(lastday+'-OPEN.json'))
    origclose_dir=original_dir if r.window=='2025_26' else original_dir.with_name('2022-C10-recovered')
    origclose=A.read(origclose_dir/(lastday+'-CLOSE.json'))
    ids={x['certificate']['certificate_id']:y['certificate']['certificate_id'] for x,y in zip(origclose['results'],r.results)}
    def replace_ids(x):
        for raw,new in ids.items():x=x.replace(raw,new)
        return x
    def rebound(x):
        if isinstance(x,dict):return {replace_ids(k):rebound(v) for k,v in x.items()}
        if isinstance(x,list):return [rebound(v) for v in x]
        return replace_ids(x) if isinstance(x,str) else x
    old=r.account.funding.goals
    r.account.funding.goals=rebound(copy.deepcopy(op['account']['funding_coverage']['goals']))
    from dataclasses import asdict
    body=dict(account=r.account.exported(r.last_completed_event),f1={k:asdict(v) for k,v in r.f1.items()},f1seq=r.f1seq,cursor=r.cursor)
    r.account.funding.goals=old
    raw=r.close_stages[r.last_completed_event.isoformat()]['necessary_digest']
    method='original_OPEN_prior_cert_rebinding'
    if E.digest(body)!=raw:
        # ON may have different prior Q. Its own immutable registry retains
        # every authorization with original known_at; at this D-empty prefix
        # remove only the just-added final CLOSE authorizations. Exact raw hash
        # validates the reconstruction, rather than assuming equivalence.
        prior={}
        for k,v in old.items():
            z=copy.deepcopy(v);z['authorizations']={kk:vv for kk,vv in z['authorizations'].items() if vv['known_at']<r.last_completed_event.isoformat()}
            if z['authorizations']:prior[k]=z
        r.account.funding.goals=prior
        body=dict(account=r.account.exported(r.last_completed_event),f1={k:asdict(v) for k,v in r.f1.items()},f1seq=r.f1seq,cursor=r.cursor)
        r.account.funding.goals=old;method='own_registry_prior_known_at_exact_raw_digest'
    witnessed=E.digest(body)==raw
    # Explicit scoped acceptance: the digest is consumed only for failed
    # optional-stage retry. Every tested prefix first attempt succeeded. The
    # continuous entry refuses any optional failure and never invokes retry.
    E.require(all(s['optional_status']=='succeeded' for s in r.close_stages.values()),'failure/retry branch is outside scope')
    d['necessary_witness_status']=dict(passed=witnessed,scope='successful optional stages only; failure/retry not authorized',path=str(p))
    if witnessed:
        d['necessary_hash_raw_body_witness']=norm(body)
        d['necessary_hash_raw_body_sha256']=raw
    return d
def compare(a,b):
    """Complete observer/trusted/lifecycle comparison with bound hash aliases.

    Only technical source dictionaries, manifest storage and hashes DERIVED
    from those identities are normalized. Every underlying snapshot, quantity,
    floor, risk, lock, receipt, budget body and account field remains compared.
    """
    checks=early_compare(a,b);aa=copy.deepcopy(a['state']);bb=copy.deepcopy(b['state']);aliases_a={};aliases_b={};reasons=[]
    witness_a=aa.pop('necessary_witness_status');witness_b=bb.pop('necessary_witness_status')
    retry_uncovered=not(witness_a['passed'] and witness_b['passed'])
    if retry_uncovered:
        for d in [aa,bb]:
            d.pop('necessary_hash_raw_body_witness',None);d.pop('necessary_hash_raw_body_sha256',None)
    def alias(x,y,label):
        if x==y:return
        E.require(isinstance(x,str) and isinstance(y,str),'non-string identity alias')
        if x in aliases_a or y in aliases_b:
            E.require(x in aliases_a and y in aliases_b and aliases_a[x]==aliases_b[y],'ambiguous identity pair');return
        aliases_a[x]=label;aliases_b[y]=label;reasons.append(dict(kind=label,left=x,right=y))
    ra=aa['observable']['results'];rb=bb['observable']['results'];E.require(len(ra)==len(rb),'projection count differs')
    source_a=[];source_b=[]
    for i,(x,y) in enumerate(zip(ra,rb)):
        E.require(x['at']==y['at'],'projection clock differs')
        for k in ['certificate_id','trusted_id','snapshot_hash','projection_hash']:alias(x['certificate'][k],y['certificate'][k],f'CERT/{i}/{k}')
        source_a.append(x['certificate']['source_binding']);source_b.append(y['certificate']['source_binding'])
        for k in ['snapshot_sha256','base_B_result_id','base_private_B_result_id','result_id','budget_after_sha256']:
            if k in x['projection']:alias(x['projection'][k],y['projection'][k],f'PROJECTION/{i}/{k}')
        if 'C_rank_binding' in x['projection']:alias(x['projection']['C_rank_binding']['original_snapshot_sha256'],y['projection']['C_rank_binding']['original_snapshot_sha256'],f'RANK/{i}/snapshot')
    for k in aa['observable']['close_stages']:
        if aa['observable']['close_stages'][k]['necessary_digest']!=bb['observable']['close_stages'][k]['necessary_digest']:
            E.require(k==aa['observable']['last_completed'].replace(' ','T')==bb['observable']['last_completed'].replace(' ','T'),'only witnessed final necessary hash may differ')
        alias(aa['observable']['close_stages'][k]['necessary_digest'],bb['observable']['close_stages'][k]['necessary_digest'],'NECESSARY/'+k)
    for k in ['input_manifest','input_sha256']:
        alias(aa['observable'][k],bb['observable'][k],'INPUT_STORAGE/'+k)
    # Common frozen policy sources must match. Extra source files are preserved
    # in the report and correspond to this wrapper and input storage only.
    sources=[]
    for x,y in zip(source_a,source_b):
        common=set(x)&set(y);E.require(all(x[p]==y[p] for p in common),'shared frozen policy file changed')
        sources.append(dict(common_exact=len(common),left_only={p:x[p] for p in set(x)-set(y)},right_only={p:y[p] for p in set(y)-set(x)}))
    checksum_paths=[]
    def canonical(v,aliases,sources,path=''):
        def replace_ids(x):
            for raw,new in aliases.items():x=x.replace(raw,new)
            return x
        if isinstance(v,dict):
            if any(v==s for s in sources):return 'REGISTERED_EXACT_POLICY_SOURCE_VIEW'
            return {replace_ids(str(k)):canonical(z,aliases,sources,path+'/'+str(k)) for k,z in v.items()}
        if isinstance(v,list):return [canonical(z,aliases,sources,path+'/'+str(i)) for i,z in enumerate(v)]
        if isinstance(v,str):
            if v in aliases:return aliases[v]
            if v.startswith('{'):
                try:q=json.loads(v)
                except Exception:return v
                if isinstance(q,dict) and 'body' in q and 'state_id' in q:
                    # Native OffBook.loads already validates the exact envelope;
                    # compare its COMPLETE underlying body after hash aliases.
                    E.require(q['state_id']==E.digest(q['body']),'budget raw body checksum')
                    checksum_paths.append(path);body=canonical(q['body'],aliases,sources,path+'<body>')
                    q=dict(q,body=body,state_id=E.digest(body))
                return canonical(q,aliases,sources,path+'<json>')
            return replace_ids(v)
        return v
    # Added empty rights observer is explicit zero-event metadata at these two
    # prefix dates; the full-month test retains and compares every later entry.
    for d in [aa,bb]:
        if d['observable'].get('no_subscription_actions')=={}:d['observable'].pop('no_subscription_actions',None)
    ca=canonical(aa,aliases_a,source_a);cb=canonical(bb,aliases_b,source_b)
    diffs=[]
    def walk(x,y,p=''):
        if type(x)!=type(y):diffs.append(dict(path=p,kind='type'));return
        if isinstance(x,dict):
            if x.keys()!=y.keys():diffs.append(dict(path=p,kind='keys',left_only=list(x.keys()-y.keys()),right_only=list(y.keys()-x.keys())))
            for k in x.keys()&y.keys():walk(x[k],y[k],p+'/'+str(k))
        elif isinstance(x,list):
            if len(x)!=len(y):diffs.append(dict(path=p,kind='length',left=len(x),right=len(y)))
            for i,(u,v) in enumerate(zip(x,y)):walk(u,v,p+'/'+str(i))
        elif x!=y:diffs.append(dict(path=p,left=str(x)[:200],right=str(y)[:200]))
    walk(ca,cb)
    return dict(complete_economic_state_equal=not diffs,raw_quick_checks=checks,remaining_differences=diffs,registered_identity_aliases=reasons,source_identity_views=sources,budget_checksum_envelopes_compared_via_validated_complete_body=sorted(set(checksum_paths)),necessary_retry_audit_metadata_uncovered=retry_uncovered,necessary_witnesses=[witness_a,witness_b],mandatory_stop_on_any_optional_failure=True)
def main():
    base=A.HERE/'gates';base.mkdir(exist_ok=True);summ=[]
    for window in ['2025_26','2022']:
        ds={}
        for on,branch in [(False,'physical'),(False,'full'),(True,'physical'),(True,'full')]:
            key=('ON' if on else 'OFF')+'-'+branch;p=base/window/key
            if (p/'RESULT.json').exists():ds[key]=A.read(p/'RESULT.json')
            else:ds[key]=run(window,on,branch,p)
            ds[key]['state']=fullstate(p/'FINAL.pkl')
        olddir=A.ROOT/f'g-s-C-two-day-finance-20261102/runs/{window}-C10'
        if window=='2022':olddir=olddir.with_name('2022-C10-recovered')
        baseline=A.read(olddir/f'{A.M.P.EXPECTED[window][-1]}-CLOSE.json')
        oldcp=olddir/f'{A.M.P.EXPECTED[window][-1]}-CLOSE.pkl'
        offchecks=compare(ds['OFF-physical'],dict(final=baseline,state=fullstate(oldcp)))
        causality={s:compare(ds[s+'-full'],ds[s+'-physical']) for s in ['OFF','ON']}
        result=dict(window=window,original_OFF=offchecks,physical_prefix=causality,all_required_passed=offchecks['complete_economic_state_equal'] and all(x['complete_economic_state_equal'] for x in causality.values()),identity_envelopes_reported_not_ignored=dict(original_source=baseline['active']['source_binding'] if baseline['active'] else None,current_source=ds['OFF-full']['source']))
        summ.append(result);A.save(base/window/'COMPARISON.json',result)
    A.save(base/'SUMMARY.json',dict(cases=summ,passed=all(x['all_required_passed'] for x in summ),scope='TWO_ORIGINAL_SESSIONS_ONLY',new_continuous_paths=0))
if __name__=='__main__':main()
