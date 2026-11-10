from pathlib import Path
import collections, datetime, hashlib, json, math, sys
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
SEC = ROOT / 'research_rounds/sector-ix-i-20261026'
OLD = ROOT / 'research_rounds/rs-h1-execution-20261025'
IX = ROOT / 'research_rounds/ix-a-share-entry-20261025'
END = pd.Timestamp('2026-10-16')

def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p, obj):
    with Path(p).open('x') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False, default=str)
        f.write('\n')

manifest = {s['series_id']: s for s in read(OLD/'prepared-v2/manifest.json')['series']}
cache = {}
used = set()

def load(sid):
    if sid not in cache:
        p = IX/'signals'/f'{sid}.parquet'
        q = OLD/'prepared-v2'/manifest[sid]['files']['signal']['path']
        f = pd.read_parquet(p)
        sg = pd.read_parquet(q, columns=['adjustment_factor','close'])
        assert f.index.isin(sg.index).all(), sid
        np.testing.assert_allclose(f.close, sg.loc[f.index,'close'], rtol=1e-12, atol=0, err_msg=sid)
        f = f.join(sg[['adjustment_factor']])
        assert f.adjustment_factor.notna().all(), sid
        # segment-safe E0 identity, rather than treating a source reset as the same structure
        f['e0_sequence'] = f.groupby('segment_id', sort=False).e0_entered.cumsum()
        prev = f.groupby('segment_id', sort=False).close.shift()
        tr = pd.concat([(f.high-f.low)/prev, abs(f.high/prev-1), abs(f.low/prev-1)], axis=1).max(axis=1)
        f['lag_tr14'] = tr.groupby(f.segment_id, sort=False).transform(lambda x:x.shift().rolling(14, min_periods=14).mean())
        cache[sid] = f
        used.update([p,q])
    return cache[sid]

def features(sid, day, entry_px):
    f = load(sid); i = f.index.get_loc(day); r = f.iloc[i]
    floor = float(r.e0_floor)
    d = (entry_px-floor)/entry_px
    return dict(decision_day=str(day.date()), e0_age=float(r.e0_age_observations),
                segment=str(r.segment_id), e0_sequence=int(r.e0_sequence),
                grade=float(r.grade), phase=str(r.phase), z5=float(r.z5), z21=float(r.z21),
                support_signal=floor, entry_signal=entry_px, support_distance=d,
                lag_tr14=float(r.lag_tr14), distance_tr=d/float(r.lag_tr14) if r.lag_tr14>0 else np.nan,
                decision_close=float(r.close), decision_fresh_up=bool(r.fresh_up))

def prepare():
    out = HERE/'prepared-v2'; out.mkdir(exist_ok=False)
    f = pd.read_csv(SEC/'analysis-v2/campaigns.csv')
    curves = pd.read_csv(SEC/'analysis-v2/curves.csv')
    curves['account'] = curves['group']+'_'+curves['policy']+'__S1_base'
    nav = {(a,str(d)):float(n) for a,d,n in curves[['account','date','nav']].itertuples(index=False,name=None)}
    rows=[]; timing=[]
    for aid, cc in f.groupby('account', sort=False):
        p=SEC/'accounts-v2'/f'{aid}.json'; used.add(p); obj=read(p)
        reserves={r['order_id']:r for r in obj['audit_log'] if r['kind']=='reserve'}
        fills={(r['receipt']['security_id'],r['receipt']['at']):r for r in obj['audit_log'] if r['kind']=='fill' and r['receipt']['side']=='buy'}
        for c in cc.to_dict('records'):
            b=fills[c['symbol'],c['entry_at']]; r=reserves[b['order_id']]
            dt=pd.Timestamp(r['decision_at']); at=pd.Timestamp(c['entry_at']); day=dt.tz_localize(None).normalize(); ed=at.tz_localize(None).normalize()
            assert dt<at and r['sid']==c['symbol'] and c['buy_fills']==1
            sf=load(c['symbol']); assert day in sf.index and ed in sf.index
            factor=float(sf.loc[ed,'adjustment_factor']); px=float(b['price']); ep=px*factor
            z=features(c['symbol'], day, ep); floor_raw=z['support_signal']/factor
            shares=int(b['receipt']['shares']); cap=nav[aid,str(day.date())]
            gap=float(b['raw_open'])<=floor_raw
            risk=(px-floor_raw)*shares/cap if not gap else np.nan
            xd=pd.Timestamp(c['exit_at']).tz_localize(None).normalize() if pd.notna(c['exit_at']) else END+pd.Timedelta(days=1)
            path=sf.loc[(sf.index>=ed)&(sf.index<xd)&(sf.index<=END),'close']
            # Price path belongs to held source segment, and is never an entry feature.
            mask=sf.loc[path.index,'segment_id'].astype(str).eq(str(sf.loc[ed,'segment_id']))
            path=path[mask]
            row={**c,**z,'decision_at':str(dt),'actual_entry_price':px,'factor':factor,
                 'known_support_raw_at_fill':floor_raw,'raw_open':float(b['raw_open']),
                 'shares':shares,'decision_nav':cap,'initial_weight':float(b['receipt']['gross_cny'])/cap,
                 'gap_below_support':gap,'initial_risk_nav':risk,
                 'close_mfe':max(0.,float(path.max()/ep-1)) if len(path) else np.nan,
                 'close_mae':min(0.,float(path.min()/ep-1)) if len(path) else np.nan,
                 'price_feedback_pnl':float(c['sell_gross'])-float(c['sell_fees'])-float(c['buy_gross'])-float(c['buy_fees']),
                 'entry_drawdown':float(curves.loc[curves.account.eq(aid)&curves.date.eq(str(day.date())),'drawdown'].iloc[0])}
            rows.append(row)
            timing.append(dict(account=aid,symbol=c['symbol'],decision_at=str(dt),entry_at=str(at),valid=True))
    rows=pd.DataFrame(rows)
    rows['attempt_in_structure']=rows.sort_values(['account','symbol','entry_at']).groupby(['account','symbol','segment','e0_sequence']).cumcount()+1
    # Strictly prior realized price/fee outcomes, never final dividend-adjusted outcomes.
    feedback=[]
    for aid, g in rows.groupby('account',sort=False):
        cl=g[g.closed & g.sell_fills.eq(1)].copy()
        cl['sold_at']=pd.to_datetime(cl.exit_at,utc=True)
        cl=cl.sort_values(['sold_at','symbol'])
        for ix,c in g.iterrows():
            prior=cl[cl.sold_at<pd.Timestamp(c.decision_at)].tail(5)
            loss=int((prior.price_feedback_pnl<0).sum())
            feedback.append((ix,len(prior),loss,'insufficient' if len(prior)<5 else '4plus_losses' if loss>=4 else 'other'))
    for ix,n,l,k in feedback:
        rows.loc[ix,'prior_closed_n']=n;rows.loc[ix,'prior_price_losses']=l;rows.loc[ix,'feedback_bucket']=k
    rows.to_csv(out/'funded.csv',index=False)
    pd.DataFrame(timing).to_csv(out/'timing.csv',index=False)
    p=SEC/'pairs/events.parquet';used.add(p); pairs=pd.read_parquet(p); pr=[]
    for c in pairs.to_dict('records'):
        z=features(c['symbol'],pd.Timestamp(c['event_day']),float(c['entry_signal_price']))
        pr.append({**c,**z})
    pd.DataFrame(pr).to_parquet(out/'opportunities.parquet')
    # Outcome-independent raw chart selection within the already observed I funded sample.
    cases=[]
    for group,g in rows[rows.policy.eq('I')&rows.entry_at.str[:10].ge('2023-01-01')&~rows.gap_below_support].groupby('group'):
        lo,hi=g.support_distance.quantile([.25,.75])
        for label,sub in [('near',g[g.support_distance<=lo]),('far',g[g.support_distance>=hi])]:
            c=sub.sort_values(['entry_at','symbol']).iloc[0]
            cases.append({k:c[k] for k in ['account','group','symbol','name','entry_at','decision_day','support_distance']}|{'case':group+'_'+label})
    pd.DataFrame(cases).to_csv(out/'cases.csv',index=False)
    used.update([SEC/'analysis-v2/campaigns.csv',SEC/'analysis-v2/curves.csv',OLD/'prepared-v2/manifest.json',HERE/'PROTOCOL.md',Path(__file__)])
    write(HERE/'freeze.json',dict(recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='offline_descriptive_only',accounts=0,files={str(p.relative_to(ROOT)):sha(p) for p in sorted(used)},funded_rows=len(rows),opportunity_rows=len(pr)))
    print(dict(prepared=len(rows),opportunities=len(pr),raw_cases=cases))

def bins(f):
    f=f.copy()
    for key,edges,labels in [('support_distance',[-np.inf,.05,.1,.2,np.inf],['<5%','5-10%','10-20%','20%+']),
        ('distance_tr',[-np.inf,1,2,4,np.inf],['<1','1-2','2-4','4+']),
        ('e0_age',[-np.inf,6,21,64,np.inf],['0-5','6-20','21-63','64+'])]:
        f[key+'_bucket']=pd.cut(f[key],edges,labels=labels,right=False).astype(str)
    if 'initial_risk_nav' in f:
        f['risk_bucket']=pd.cut(f.initial_risk_nav,[-np.inf,.005,.01,.02,np.inf],labels=['<0.5%','0.5-1%','1-2%','2%+'],right=False).astype(str)
    return f

def summarize():
    out=HERE/'results-v1';out.mkdir(exist_ok=False)
    f=bins(pd.read_csv(HERE/'prepared-v2/funded.csv'))
    p=bins(pd.read_parquet(HERE/'prepared-v2/opportunities.parquet'))
    sums=[]
    for keys in [['group','policy'],['group','policy','risk_bucket'],['group','policy','support_distance_bucket'],['group','policy','distance_tr_bucket'],['group','policy','feedback_bucket'],['group','policy','e0_age_bucket']]:
        for vals,g in f.groupby(keys,dropna=False,observed=True):
            cl=g[g.closed];loss=cl[cl.net_pnl<0];tail=cl[cl.tail_closed]
            sums.append(dict(grouping='|'.join(keys),**dict(zip(keys,vals)),n=len(g),closed=len(cl),wins=int((cl.net_pnl>0).sum()),win_rate=float((cl.net_pnl>0).mean()) if len(cl) else np.nan,mean_return=cl.net_return.mean(),median_return=cl.net_return.median(),pnl=cl.net_pnl.sum(),loss=-loss.net_pnl.sum(),tail_n=len(tail),tail_pnl=tail.net_pnl.sum(),ordinary_pnl=cl[~cl.tail_closed].net_pnl.sum(),median_risk=g.initial_risk_nav.median(),median_distance=g.support_distance.median(),median_tr=g.distance_tr.median(),early_loss=-loss.loc[loss.close_mfe<.05,'net_pnl'].sum()))
    pd.DataFrame(sums).to_csv(out/'funded-groups.csv',index=False)
    # First event of a source-safe E0 episode is a non-overlapping descriptive representative.
    first=p.sort_values(['event_day','symbol']).drop_duplicates(['group','symbol','segment','e0_sequence'])
    ps=[]
    for sample,pp in [('all_ix_segments',p),('first_e0_event',first)]:
        for policy in ['I','IX']:
            for keys in [['group'],['group','support_distance_bucket'],['group','distance_tr_bucket'],['group','e0_age_bucket']]:
                for vals,g in pp.groupby(keys,dropna=False,observed=True):
                    vals=(vals,) if not isinstance(vals,tuple) else vals;cl=g[g[policy+'_closed']];r=cl[policy+'_return']
                    ps.append(dict(sample=sample,policy=policy,grouping='|'.join(keys),**dict(zip(keys,vals)),n=len(g),closed=len(cl),mean_return=r.mean(),median_return=r.median(),win_rate=(r>0).mean(),tail_n=int((r>=.3).sum())))
    pd.DataFrame(ps).to_csv(out/'opportunity-groups.csv',index=False)
    first.to_parquet(out/'first-e0-opportunities.parquet')
    # All account P&L remains the original unchanged path, including unfinished claims.
    old=pd.read_csv(SEC/'analysis-v2/summary.csv');errors=[]
    for _,r in old.iterrows():
        got=f.loc[f.account.eq(r.account),'net_pnl'].sum()
        errors.append(dict(account=r.account,net_pnl_error=float(got-(r.final_nav-1e6))))
    assert max(abs(x['net_pnl_error']) for x in errors)<1e-6
    write(out/'verification.json',dict(passed=True,funded_rows=len(f),all_opportunities=len(p),first_e0_opportunities=len(first),account_pnl_checks=errors,no_new_accounts=True,code_sha256=sha(__file__)))
    print(pd.DataFrame(sums).query("grouping == 'group|policy'").to_string(index=False))
    print('first_e0',len(first))

def charts(overlay=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out=HERE/('charts-overlay' if overlay else 'charts-raw');out.mkdir(exist_ok=False)
    for c in pd.read_csv(HERE/'prepared-v2/cases.csv').to_dict('records'):
        f=load(c['symbol']);d=pd.Timestamp(c['decision_day']);i=f.index.get_loc(d);g=f.iloc[max(0,i-80):i+65]
        fig,(ax,v)=plt.subplots(2,1,figsize=(13,7),sharex=True,gridspec_kw={'height_ratios':[4,1]})
        up=g.close>=g.open;colors=np.where(up,'#be4b48','#2c8577')
        ax.vlines(g.index,g.low,g.high,colors=colors,linewidth=.8)
        ax.vlines(g.index,g.open,g.close,colors=colors,linewidth=2.5)
        v.bar(g.index,g.volume/1e6,color=colors,width=1)
        for a in [ax,v]:a.axvline(d,color='#2f4d7b',linestyle='--');a.axvspan(d,g.index[-1],color='#6683a1',alpha=.06);a.grid(alpha=.15)
        if overlay:ax.plot(g.index,g.e0_floor,color='#bc872b',label='E0 support');ax.legend()
        ax.set_title(f"{c['case']} {c['symbol']} | decision {d.date()} | original OHLCV"+(' + unchanged E0 support' if overlay else ''))
        ax.set_ylabel('Signal price');v.set_ylabel('Volume / 1e6');fig.tight_layout();fig.savefig(out/(c['case']+'.png'),dpi=120);plt.close(fig)
    print(str(out))

if __name__=='__main__':
    mode=sys.argv[1]
    {'prepare':prepare,'summarize':summarize,'raw':lambda:charts(False),'overlay':lambda:charts(True)}[mode]()
