"""Seven fixed full-local stock-score cross sections, no account/labels."""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
INPUT=ROOT/'features/LOCAL_FIXED_DATE_FEATURES.parquet'
OLD=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
NAMES=Path('/Users/bytedance/repos/my-quant/data/processed/securities/securities.parquet')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    with p.open('x')as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def pct(s):return (s.rank(method='average')-1)/(len(s)-1)

def rank(a,scope):
    a=a.copy();a['scope']=scope
    for col in ['p_start','p_fast_CONT','p_slow_CONT','S_cont','CONT_exact_numerator','rank_PVR','rank_FAST','rank_CONT','N_PVR','N_FAST','N_CONT']:a[col]=np.nan
    for day,g in a.groupby('day',sort=True):
        for queue,value in [('PVR','score'),('FAST','E_fast')]:
            q=g[g.target_row_present&np.isfinite(g[value])]
            order=q.sort_values([value,'sid'],ascending=[False,True]).index
            a.loc[order,'rank_'+queue]=np.arange(1,len(q)+1);a.loc[g.index,'N_'+queue]=len(q)
            if queue=='FAST':a.loc[q.index,'p_start']=pct(q.E_fast)
        q=g[g.target_row_present&np.isfinite(g.E_fast)&np.isfinite(g.E_slow)]
        pf=pct(q.E_fast);ps=pct(q.E_slow);unit=2*(len(q)-1)
        A=np.rint(pf*unit);B=np.rint(ps*unit)
        assert np.allclose(A,pf*unit,atol=1e-10,rtol=0)and np.allclose(B,ps*unit,atol=1e-10,rtol=0)
        num=(3*A+7*B).astype('int64')
        a.loc[q.index,'p_fast_CONT']=pf;a.loc[q.index,'p_slow_CONT']=ps
        a.loc[q.index,'CONT_exact_numerator']=num;a.loc[q.index,'S_cont']=num/(20*(len(q)-1))
        order=q.assign(_num=num).sort_values(['_num','sid'],ascending=[False,True]).index
        a.loc[order,'rank_CONT']=np.arange(1,len(q)+1);a.loc[g.index,'N_CONT']=len(q)
    return a

def main():
    out=ROOT/'ranks';out.mkdir(exist_ok=False)
    x=pd.read_parquet(INPUT);assert len(x)==38619 and x.sid.nunique()==5517
    old={r['symbol']for r in json.loads(OLD.read_text())};assert len(old)==1709
    names=pd.read_parquet(NAMES,columns=['symbol','name']).rename(columns={'symbol':'sid','name':'current_name'})
    x=x.merge(names,on='sid',how='left',validate='many_to_one');x['in_old1709_exact']=x.sid.isin(old)
    x['current_name_contains_ST_snapshot']=x.current_name.str.contains('ST',na=False)
    full=rank(x,'FULL_LOCAL');sub=rank(x[x.in_old1709_exact],'OLD1709_EXACT_SUBPOOL')
    allr=pd.concat([full,sub],ignore_index=True);allr.to_parquet(out/'ALL_FIXED_DATE_RANKS.parquet',index=False)
    top=[]
    for queue in ['PVR','FAST','CONT']:
        a=allr[allr['rank_'+queue].le(20)].copy();a['queue']=queue;a['queue_rank']=a['rank_'+queue];a['queue_pool_N']=a['N_'+queue];top.append(a)
    t=pd.concat(top).sort_values(['scope','day','queue','queue_rank']);t.to_csv(out/'ALL_TOP20_LISTS.csv',index=False)
    t[t.scope.eq('FULL_LOCAL')&~t.in_old1709_exact].to_csv(out/'FULL_TOP20_OUTSIDE_OLD1709_EXACT.csv',index=False)
    t[t.scope.eq('FULL_LOCAL')].to_csv(out/'FULL_LOCAL_TOP20.csv',index=False)
    counts=[]
    for day,g in full.groupby('day'):
        z=dict(day=day,mother=len(g),observed=int(g.target_row_present.sum()),missing_target_bar=int((~g.target_row_present).sum()),PVR_ready=int(g.rank_PVR.notna().sum()),FAST_ready=int(g.rank_FAST.notna().sum()),CONT_ready=int(g.rank_CONT.notna().sum()),fast_ready_slow_notready=int((g.rank_FAST.notna()&g.rank_CONT.isna()).sum()),old_manifest=1709,old_in_canonical=int(g.in_old1709_exact.sum()),old_not_in_canonical=len(old-set(g.sid)),old_observed=int((g.in_old1709_exact&g.target_row_present).sum()))
        for q in ['PVR','FAST','CONT']:
            a=g[g['rank_'+q].le(20)];z[q+'_top20_outside_old']=int((~a.in_old1709_exact).sum());z[q+'_top20_current_ST_name']=int(a.current_name_contains_ST_snapshot.sum());z[q+'_score_ties']=int(g.loc[g['rank_'+q].notna(),q=='PVR'and'score'or(q=='FAST'and'E_fast'or'CONT_exact_numerator')].duplicated().sum())
        counts.append(z)
    pd.DataFrame(counts).to_csv(out/'COVERAGE_AND_TOP20_OLD_POOL_EXCLUSIONS.csv',index=False)
    target=json.loads((ROOT/'FREEZE.json').read_text())['fixed_named_cases']
    c=full[full.sid.isin(target)].copy();subcols=['sid','day','rank_PVR','rank_FAST','rank_CONT','N_PVR','N_FAST','N_CONT','p_start','p_fast_CONT','p_slow_CONT','S_cont']
    c=c.merge(sub[subcols],on=['sid','day'],how='left',validate='one_to_one',suffixes=('','_OLD_SUBPOOL'))
    c.sort_values(['sid','day']).to_csv(out/'NAMED_FIXED_STOCK_RANKS.csv',index=False)
    save(out/'COMPLETION.json',dict(status='COMPLETE_SEVEN_FIXED_LOCAL_SCORE_UNIVERSES_NO_FORWARD_LABELS',sources={str(p.resolve()):sha(p)for p in[Path(__file__),ROOT/'FREEZE.json',INPUT,OLD,NAMES]},outputs={p.name:sha(p)for p in out.iterdir()if p.is_file()},rows=len(x),full_top_rows=int(t.scope.eq('FULL_LOCAL').sum()),new_accounts=0,forward_labels_loaded=False,source_refreshes=0))
    print(pd.DataFrame(counts).to_string(index=False))
    print(t[t.scope.eq('FULL_LOCAL')&t.queue.eq('PVR')][['day','queue_rank','sid','current_name','score','E_fast','E_slow','in_old1709_exact']].to_string(index=False))

if __name__=='__main__':main()
