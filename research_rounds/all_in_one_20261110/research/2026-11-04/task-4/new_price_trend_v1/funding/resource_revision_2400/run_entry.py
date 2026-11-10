"""Explicit technical/full entrypoints for the frozen two-window entry ablation.

No account is constructed by import or --prepare. --technical requires parent
authorization; --full also requires a passing independent technical review.
"""
from pathlib import Path
from datetime import datetime,time as dt
import argparse, copy, gc, gzip, json, time, traceback
import entry_adapter as E
import input_loader as D
J,L,N,IO=E.J,E.L,E.N,E.IO
O=E.O
TECH_CUTS={'long':'2022-01-14','strong':'2025-07-15'}
STREAMS=['daily','opportunities','funding','industry','balances','rank-policy']

def read(p):return json.loads(Path(p).read_text())
def save(p,x):IO.write_json(p,J.W.canon(x))
def rows(p):
    with gzip.open(p,'rt')as f:return [json.loads(x)for x in f]
def book(p):
    with gzip.open(p,'rt')as f:return json.load(f)
def difference(a,b,path='$'):
    if type(a)is not type(b):return dict(path=path,old_type=type(a).__name__,new_type=type(b).__name__,old=str(a)[:300],new=str(b)[:300])
    if isinstance(a,dict):
        if a.keys()!=b.keys():return dict(path=path,old_keys=list(a),new_keys=list(b))
        for k in a:
            d=difference(a[k],b[k],path+'.'+str(k))
            if d:return d
    elif isinstance(a,list):
        if len(a)!=len(b):return dict(path=path,old_length=len(a),new_length=len(b))
        for i,(x,y)in enumerate(zip(a,b)):
            d=difference(x,y,path+'['+str(i)+']')
            if d:return d
    elif a!=b:return dict(path=path,old=a,new=b)
    return None
def compare_pairs(old,new,cut=None,include_book=True):
    checks={};diffs={}
    if include_book:
        a,b=book(old/'B.json.gz'),book(new/'B.json.gz')
        d=difference(a,b);checks['B']=d is None
        if d:diffs['B']=d
    for name in STREAMS:
        a,b=rows(old/(name+'.jsonl.gz')),rows(new/(name+'.jsonl.gz'))
        if cut:
            a=[x for x in a if str(x.get('day',x.get('at','')))[:10]<=cut]
            b=[x for x in b if str(x.get('day',x.get('at','')))[:10]<=cut]
        d=difference(a,b);checks[name]=d is None
        if d:diffs[name]=d
    return dict(passed=all(checks.values()),checks=checks,first_differences=diffs)

def freeze():
    value=E.source_freeze()
    for p in [*D.RECEIPT_MANIFESTS,*D.SCORES.values(),O/'generated_entry_planning.py']:
        value[str(p.resolve())]=E.sha(p)
    return value

def prepare():
    (O/'generated_entry_planning.py').write_text(E.GATED_PLANNING_SOURCE)
    import difflib
    (O/'ENTRY_PLANNING.diff').write_text(''.join(difflib.unified_diff(
        E.ORIGINAL_PLANNING_SOURCE.splitlines(True),E.GATED_PLANNING_SOURCE.splitlines(True),
        fromfile=str(Path(J.__file__))+':Runner.planning',tofile='ENTRY_BB20_flat_gate')))
    value=dict(policy=E.POLICY,sources=freeze(),windows=D.WINDOWS,technical_cuts=TECH_CUTS,
        feature_manifest_sha256=E.sha(E.ROOT/'PRICE_FEATURE_MANIFEST.json'),
        technical_compute_limit_seconds=180,full_compute_limit_seconds=1200,
        old_baseline_pairs={k:str(v)for k,v in D.BASELINES.items()},prior_account_imports=0,
        entry_hook_insertions=1,original_planning_sha256=__import__('hashlib').sha256(E.ORIGINAL_PLANNING_SOURCE.encode()).hexdigest(),
        physical_feature_policy='exact day only; truncate lookup as well as original inputs',accounts_executed=0)
    path=O/'SOURCE_FREEZE.json'
    if path.exists():assert read(path)==value,'prepared sources changed'
    else:save(path,value)
    print('PREPARED',path,flush=True)

class Budget:
    def __init__(self,limit,path):self.limit=limit;self.used=0.;self.path=path
    def run(self,callback):
        left=self.limit-self.used
        assert left>0,'frozen compute budget exhausted'
        t=time.monotonic()
        try:return callback(left)
        finally:
            self.used+=time.monotonic()-t
            save(self.path,dict(limit_seconds=self.limit,used_seconds=self.used,remaining_seconds=max(0,self.limit-self.used)))

def construct(value,mode,original=False):
    shared,receipts,cp,states,ir,_=value
    kw=E.S.kwargs(cp,states,ir)
    r=E.A.Runner(shared,receipts,**kw)if original else E.Runner(shared,receipts,entry_mode=mode,**kw)
    r.source_freeze=dict(read(O/'SOURCE_FREEZE.json')['sources'])
    a=r.accounts['B']
    assert a.available==a.current_nav==a.initial_cash==J.D(1000000)
    assert not(a.positions or a.layers or a.trades or a.buys or a.exits or a.core_epoch or a.budget.orders or a.budget.lots or a.budget.losses)
    return r

def run(r,out,end,budget):
    out.mkdir(parents=True,exist_ok=False)
    with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):
        done=budget.run(lambda left:r.run_prepared(out,left,end=end))
    if not done:raise RuntimeError('native run saved timeout checkpoint/partial; no automatic replay')
    return out/'pair'

def technical(auth):
    assert auth['approved']is True and auth['scope']=='ENTRY_BB20_technical_only'
    assert auth['source_freeze_sha256']==E.sha(O/'SOURCE_FREEZE.json')
    assert freeze()==read(O/'SOURCE_FREEZE.json')['sources']
    root=O/'technical';root.mkdir(exist_ok=True)
    assert not(root/'GATE.json').exists(),'do not repeat completed technical paths'
    budget=Budget(180,root/'TIMING.json');E.configure_features();full_features=E.FEATURES
    proofs={};prep={}
    for window,cut in TECH_CUTS.items():
        t=time.monotonic();N.configure_scores(D.SCORES[window]);value=D.inputs(window)
        prep[window]=time.monotonic()-t
        # Full immutable future lookup vs physically truncated input/features.
        E.FEATURES=full_features
        original=construct(value,'OFF',original=True)
        original_pair=run(original,root/(window+'_native'),cut,budget);del original;gc.collect()
        off=construct(value,'OFF');off_pair=run(off,root/(window+'_OFF'),cut,budget);del off;gc.collect()
        offproof=compare_pairs(original_pair,off_pair)
        oldproof=compare_pairs(D.BASELINES[window],off_pair,cut=cut,include_book=False)
        save(root/(window+'_OFF_IDENTITY.json'),dict(native=offproof,old_prefix=oldproof))
        assert offproof['passed']and oldproof['passed'],'OFF identity failed'
        on=construct(value,'BB20');onpair=run(on,root/(window+'_BB20_full_lookup'),cut,budget);del on;gc.collect()
        physical=D.physical(value,cut)
        E.FEATURES=copy.copy(full_features)
        E.FEATURES.values={s:{d:v for d,v in rs.items()if str(d)<=cut}for s,rs in full_features.values.items()}
        E.FEATURES.physical_through=cut
        small=construct(physical,'BB20');smallpair=run(small,root/(window+'_BB20_physical'),cut,budget)
        prefix=compare_pairs(onpair,smallpair)
        prefix['entry_gate_exact']=rows(onpair/'entry-gate.jsonl.gz')==rows(smallpair/'entry-gate.jsonl.gz')
        prefix['passed']=prefix['passed']and prefix['entry_gate_exact']
        save(root/(window+'_PHYSICAL_PREFIX.json'),prefix);assert prefix['passed'],'physical prefix failed'
        proofs[window]=dict(off=offproof,old_prefix=oldproof,physical=prefix)
        del small,physical,value;gc.collect()
    E.FEATURES=full_features
    assert freeze()==read(O/'SOURCE_FREEZE.json')['sources']
    save(root/'GATE.json',dict(passed=True,proofs=proofs,compute_seconds=budget.used,input_preparation_seconds=prep,
        source_freeze_sha256=E.sha(O/'SOURCE_FREEZE.json'),full_accounts_executed=0))

def full(auth):
    assert auth['approved']is True and auth['scope']=='ENTRY_BB20_four_full_paths'
    assert auth['source_freeze_sha256']==E.sha(O/'SOURCE_FREEZE.json')
    assert read(O/'technical/GATE.json')['passed']
    review=read(auth['technical_review_path']);assert review['passed']is True
    assert auth['technical_gate_sha256']==E.sha(O/'technical/GATE.json')
    assert freeze()==read(O/'SOURCE_FREEZE.json')['sources']
    root=O/'runs';root.mkdir(exist_ok=True);budget=Budget(1200,root/'TIMING.json')
    assert not(root/'TIMING.json').exists(),'prior compute needs explicit review, never silently repeat'
    E.configure_features()
    for window,(_,end)in D.WINDOWS.items():
        N.configure_scores(D.SCORES[window]);t=time.monotonic();value=D.inputs(window)
        save(root/(window+'_INPUT_IDENTITY.json'),value[-1])
        print('INPUT_READY',window,'seconds',time.monotonic()-t,flush=True)
        for mode in ('OFF','BB20'):
            r=construct(value,mode);out=root/(window+'_'+mode)
            save(root/(window+'_'+mode+'_FRESH.json'),dict(cash=1000000,positions=0,orders=0,account_imports=0))
            pair=run(r,out,end,budget)
            if mode=='OFF':
                proof=compare_pairs(D.BASELINES[window],pair)
                save(out/'ORIGINAL_IDENTITY.json',proof)
                assert proof['passed'],'full OFF differs from original No60; candidate stopped'
            assert freeze()==read(O/'SOURCE_FREEZE.json')['sources']
            print('FULL_SAVED',window,mode,'compute_used',round(budget.used,3),flush=True)
            del r;gc.collect()
        del value;gc.collect()
    save(root/'COMPLETE.json',dict(passed=True,compute_seconds=budget.used,paths=4,source_freeze_sha256=E.sha(O/'SOURCE_FREEZE.json')))

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','technical','full']);p.add_argument('--authorization-file',type=Path)
    args=p.parse_args()
    if args.action=='prepare':return prepare()
    assert args.authorization_file
    try:
        if args.action=='technical':technical(read(args.authorization_file))
        else:full(read(args.authorization_file))
    except BaseException as e:
        save(O/(args.action+'_FAILURE.json'),dict(error=str(e),traceback=traceback.format_exc(),automatic_replay=False));raise

if __name__=='__main__':main()
