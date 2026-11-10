"""One frozen signal replay and bounded diagnostics; never imports an account runner."""
from pathlib import Path
import json,hashlib,sys,datetime
import numpy as np
import pandas as pd
from temperature import temperature_frame
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
PRIOR=ROOT/'research_rounds/pv-participation-response-20261020'
sys.path.insert(0,str(PRIOR/'code'))
from numeric import event_frame_numeric
from participation import participation_frame
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,(np.integer,)):return int(x)
    if isinstance(x,(np.bool_,)):return bool(x)
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    return x
def dump(p,x):p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def segments(d,fn):
    parts=[]
    for _,z in d.groupby('segment_id',sort=False):parts.append(fn(z))
    return pd.concat(parts).reindex(d.index)
def baseline(d):
    e=event_frame_numeric(d.close,d.volume,joint=True,event_exit=False)
    s,_=participation_frame(d,e,mode='volume');return s
def intervals(z,target,entered=None,exited=None):
    a=z[target].astype(bool)
    ent=(a&~a.shift(fill_value=False)) if entered is None else z[entered].astype(bool)
    ex=(~a&a.shift(fill_value=False)) if exited is None else z[exited].astype(bool)
    out=[]
    for k in np.flatnonzero(ent):
        follow=np.flatnonzero(ex.to_numpy()[k+1:k+11])
        outcome='failed_within_10' if len(follow) else 'survived_10' if k+10<len(z) else 'censored'
        out.append(dict(date=str(z.index[k].date()),outcome=outcome))
    return out
def describe(z):
    row=dict(observations=len(z))
    for label,target,entered,exited in [('baseline','baseline_target','baseline_entered','baseline_exited'),
       ('structure','structure',None,'structural_invalidated'),('temperature','target','entered','exited'),
       ('price_only','price_target','price_entered','price_exited')]:
        ep=intervals(z,target,entered,exited)
        # A projected structure alive at the window boundary is a carry-in, not an opening.
        if entered is None and len(z) and z[target].iloc[0]:ep=ep[1:]
        row.update({label+'_starts':len(ep),label+'_days':int(z[target].sum()),
          label+'_carry':int(bool(len(z) and z[target].iloc[0] and not (z[entered].iloc[0] if entered else False))),
          label+'_failure10':sum(r['outcome']=='failed_within_10' for r in ep),
          label+'_censored':sum(r['outcome']=='censored' for r in ep)})
    row['heat_crosses']=int(z.heat_cross.sum());row['hot_days']=int(z.level.ge(4).sum())
    row['level_changes']=int(z.level_change.ne(0).sum());row['guard_days']=int(z.guard.sum())
    row['rapid_days']=int(z.fast.sum());row['expansion_days']=int(z.level.eq(6).sum())
    row['first_baseline']=str(z.index[z.baseline_target.astype(bool)][0].date()) if z.baseline_target.any() else None
    row['first_temperature']=str(z.index[z.target.astype(bool)][0].date()) if z.target.any() else None
    return row

def main():
    protocol=json.loads((HERE/'protocol.json').read_text());fr=json.loads((HERE/'input-freeze.json').read_text())
    assert sha(HERE/'temperature.py')==protocol['code_sha256']
    assert sha(HERE/'input-freeze.json')==protocol['input_freeze_sha256']
    for n,h in fr['baseline_code'].items():assert sha(PRIOR/'code'/n)==h
    out=HERE/'results/v0';out.mkdir(parents=True,exist_ok=False);(out/'daily').mkdir();(out/'ledgers').mkdir()
    dump(out/'run-freeze.json',dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
      protocol_sha256=sha(HERE/'protocol.json'),run_code_sha256=sha(__file__),temperature_sha256=sha(HERE/'temperature.py'),
      baseline_code=fr['baseline_code'],account_runs=0,market_downloads=0,old_algorithm_changes=0))
    all_frames={};checks=[];summary=[]
    prior_manifest=json.loads((PRIOR/'results/v0-input-fixed/manifest.json').read_text())
    for rec in fr['series']:
        sid=rec['symbol'];p=HERE/'inputs'/(sid+'.parquet');assert sha(p)==rec['input_sha256']
        d=pd.read_parquet(p);bs=segments(d,baseline)
        outputs=[];ledgers=[]
        for seg,z in d.groupby('segment_id',sort=False):
            t,ledger=temperature_frame(z);pstate,_=temperature_frame(z,use_volume=False)
            t=t.join(pstate[['target','entered','exited','level']].add_prefix('price_'))
            outputs.append(t)
            if not ledger.empty:ledger['segment_id']=seg;ledgers.append(ledger)
        t=pd.concat(outputs).reindex(d.index)
        joined=d[['open','high','low','close','volume','segment_id']].join(t).join(bs[['target','entered','exited','floor','entry_kind']].add_prefix('baseline_'))
        joined.to_parquet(out/'daily'/(sid+'.parquet'));joined.to_csv(out/'daily'/(sid+'.csv'),float_format='%.17g')
        if ledgers:pd.concat(ledgers).to_csv(out/'ledgers'/(sid+'.csv'),index=False)
        old=PRIOR/'results/v0-input-fixed'/(sid+'-states.csv')
        if old.exists():
            assert sha(old)==prior_manifest[old.name]
            saved=pd.read_csv(old,index_col='date',parse_dates=True,float_precision='round_trip')
            for col in ['target','entered','exited','floor']:
                np.testing.assert_array_equal(bs[col].to_numpy(),saved[col].to_numpy())
            checks.append(dict(symbol=sid,baseline_exact_rows=len(bs)))
        all_frames[sid]=joined
        z=joined.loc['2024-01-01':'2026-10-16']
        summary.append(dict(symbol=sid,name=rec['name'],primary=sid in fr['primary'],**describe(z)))
        print(sid,'done',len(joined),flush=True)
    windows=[]
    for case in json.loads((HERE/'cases.json').read_text()):
        z=all_frames[case['symbol']].loc[case['start']:case['end']]
        windows.append(dict(**case,**describe(z)))
    pd.DataFrame(summary).to_csv(out/'series-summary.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(windows).to_csv(out/'window-summary.csv',index=False,encoding='utf-8-sig')
    # Three current-classification A-stock/industry pairs; HK remains an explicit single-asset diagnostic.
    pairs=[]
    for sid,sec in fr['pairs'].items():
        a=all_frames[sid];b=all_frames[sec];idx=a.index.intersection(b.index)
        z=pd.DataFrame(index=idx)
        z['baseline_target']=(a.baseline_target.reindex(idx).astype(bool)&b.baseline_target.reindex(idx).astype(bool)).astype(int)
        z['structure_target']=(a.structure.reindex(idx).astype(bool)&b.structure.reindex(idx).astype(bool)).astype(int)
        z['stock_level']=a.level.reindex(idx);z['sector_level']=b.level.reindex(idx)
        active=False;rows=[]
        for dt,row in z.iterrows():
            ent=ex=0
            if active and not row.structure_target:active=False;ex=1
            if not active and not ex and row.stock_level>=4 and row.sector_level>=4:active=True;ent=1
            rows.append((int(active),ent,ex))
        z[['target','entered','exited']]=rows
        z.to_csv(out/(sid+'-joint.csv'))
        w=z.loc['2024-01-01':'2026-10-16']
        be=w.baseline_target.gt(0)&~z.baseline_target.shift(fill_value=0).reindex(w.index).gt(0)
        pairs.append(dict(symbol=sid,sector=sec,baseline_starts=int(be.sum()),temperature_starts=int(w.entered.sum()),
          baseline_days=int(w.baseline_target.sum()),temperature_days=int(w.target.sum()),
          baseline_carry=int(bool(w.baseline_target.iloc[0] and not be.iloc[0])),
          temperature_carry=int(bool(w.target.iloc[0] and not w.entered.iloc[0]))))
    pd.DataFrame(pairs).to_csv(out/'joint-summary.csv',index=False,encoding='utf-8-sig')
    dump(out/'baseline-verification.json',checks)
    dump(out/'complete.json',dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),series=summary,windows=windows,pairs=pairs,
      caveat='Signal projections only. failure10 means structure invalidated within ten subsequent observed bars; not a losing trade. Windows overlap, no summed independent performance claim.',
      model_sha256=sha(HERE/'temperature.py'),protocol_sha256=sha(HERE/'protocol.json'),account_runs=0,post_run_mechanism_revisions=0))
    print('completed',len(summary),'series',len(windows),'fixed windows',flush=True)
if __name__=='__main__':main()
