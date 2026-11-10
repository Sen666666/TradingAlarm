"""Saved price-proxy statistics and four original-source samples; no model imports."""
from pathlib import Path
from collections import Counter
import hashlib,json,math
import pandas as pd

P=Path(__file__).resolve().parents[1];R=P.parent;O=Path(__file__).resolve().parent
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def finite(v):return v is not None and not pd.isna(v) and math.isfinite(float(v))
def same(a,b):return a==b or finite(a) and finite(b) and abs(a-b)<=1e-11*max(1,abs(a),abs(b))
def qtile(xs,q):
    xs=sorted(float(x) for x in xs if finite(x));v=(len(xs)-1)*q;i=math.floor(v);j=math.ceil(v)
    return xs[i] if i==j else xs[i]*(j-v)+xs[j]*(v-i)
def distcheck(xs,b):
    xs=[float(x) for x in xs if finite(x)];assert len(xs)==b['n']
    if xs:
        assert same(math.fsum(xs)/len(xs),b['mean'])
        for q in [0,.1,.5,.9,1]:assert same(qtile(xs,q),b[f'q{int(q*100):02}'])
def perfcheck(xs,b):
    xs=list(xs);distcheck(xs,b['distribution'])
    assert sum(x<0 for x in xs)==b['negative_n'] and sum(x==0 for x in xs)==b['zero_n']
    assert same(sum(x for x in xs if x<0),b['negative_sum_percentage_points'])
    assert same(sum(x for x in xs if x>0),b['positive_sum_percentage_points'])
def trueflag(x):return isinstance(x,bool) and x or type(x).__name__=='bool' and bool(x)

d=pd.read_parquet(P/'PRICE_DIAGNOSTIC_ROWS.parquet');s=load(P/'FIXED_H20_AND_POST5_STATS.json')
assert len(d)==49345 and s['raw_existing_mother']==51026 and s['diagnostic_rows']==len(d)
assert not d[['sid','anchor_id','original_window']].duplicated().any()
assert d.execution_status.eq('UNKNOWN_FOR_ALL_REFERENCES').all()
groups={};native={};matched=load(P/'MATCHED_PANEL_NATIVE_VS_H20.json')
for g,b in s['groups'].items():
    z=d[d.original_window.eq('2024-09-01__2024-12-31')] if g.startswith('BRIDGE') else d[d.primary_group.eq(g)]
    h=z[z.h20_status.eq('PAIRED_H20_QUOTED')]
    assert len(z)==b['raw_anchor_n'] and z.sid.nunique()==b['distinct_stocks']
    assert z.pair_status.value_counts().to_dict()==b['pair_status'] and z.h20_status.value_counts().to_dict()==b['h20_funnel']
    assert len(z)==b['all_actual_execution_UNKNOWN_n']
    if g=='2024_924_DEC':assert z.anchor_day.ge('2024-09-24').all() and z.anchor_day.le('2024-12-31').all()
    if g=='2026_H1_SEMICONDUCTOR':assert z.anchor_day.ge('2026-01-01').all() and z.anchor_day.le('2026-06-30').all()
    for arm in ['CP','ATR3']:
        a=b['branches'][arm];perfcheck(h[f'{arm}_H20_proxy_pp'],a['H20'])
        assert h[f'{arm}_H20_kind'].value_counts().to_dict()==a['H20_kind']
        assert z[f'{arm}_post5_status'].fillna('NOT_PAIRED_OR_ENTRY_UNKNOWN').value_counts().to_dict()==a['post5_status']
        distcheck(z[f'{arm}_preexit_close_giveback_pp'],a['preexit_giveback_pp'])
        post=z[z[f'{arm}_post5_status'].eq('COMPLETE_5_WITHIN_ORIGINAL_I')]
        assert len(post)==a['post5']['n']
        for col,key in [('endpoint_pp','endpoint_pp'),('max_pp','max_close_pp'),('min_pp','min_close_pp')]:distcheck(post[f'{arm}_post5_{col}'],a['post5'][key])
        assert post[f'{arm}_post5_all_above_exit_OPEN'].sum()==a['post5']['all_above_exit_OPEN_n']
        assert post[f'{arm}_post5_strict_up'].sum()==a['post5']['strict_up_n']
        for _,row in h.iterrows():
            E=row.entry_OPEN;kind=row[f'{arm}_H20_kind']
            X=row[f'{arm}_exit_OPEN'] if kind=='SAVED_EXIT_QUOTE_WITHIN20' else row.terminal_OPEN
            assert kind in ['SAVED_EXIT_QUOTE_WITHIN20','COMMON_H20_MARK_NOT_EXIT']
            assert same(row[f'{arm}_H20_proxy_pp'],100*(X/E-1)) and row[f'{arm}_H20_proxy_pp']>-100
            if kind=='SAVED_EXIT_QUOTE_WITHIN20':assert row[f'{arm}_exit_day']<=row.h20_close_day
            elif pd.notna(row[f'{arm}_exit_day']):assert row[f'{arm}_exit_day']>row.h20_close_day
    assert (h.H20_ATR_minus_CP_pp-(h.ATR3_H20_proxy_pp-h.CP_H20_proxy_pp)).abs().max()<1e-10
    distcheck(h.H20_ATR_minus_CP_pp,b['H20_ATR_minus_CP_pp'])
    assert (h.H20_ATR_minus_CP_pp>0).sum()==b['H20_ATR_better_n']
    assert (h.H20_ATR_minus_CP_pp<0).sum()==b['H20_ATR_worse_n']
    assert (h.H20_ATR_minus_CP_pp==0).sum()==b['H20_same_n']
    labels=z[z.common_H20_proxy_pp.notna()];q=b['common_H20_strong_q90']
    threshold=qtile(labels.common_H20_proxy_pp,.9);assert same(threshold,q['threshold_pp'])
    strong_labels=labels[labels.common_H20_proxy_pp>=q['threshold_pp']]
    strong=h[h.common_H20_proxy_pp>=q['threshold_pp']]
    assert len(labels)==q['common_label_n'] and len(strong_labels)==q['strong_label_n'] and len(strong)==q['n']
    assert len(strong_labels)-len(strong)==q['strong_label_but_paired_comparison_unavailable_n']
    assert strong.sid.nunique()==q['stocks']
    for arm in ['CP','ATR3']:
        perfcheck(strong[f'{arm}_H20_proxy_pp'],q[arm])
        total=b['branches'][arm]['H20']['positive_sum_percentage_points']
        assert same(q[arm]['share_of_all_positive_unit_price_proxies'],q[arm]['positive_sum_percentage_points']/total)
    distcheck(strong.H20_ATR_minus_CP_pp,q['ATR_minus_CP_pp'])
    for _,row in labels.iterrows():assert same(row.common_H20_proxy_pp,100*(row.terminal_OPEN/row.entry_OPEN-1))
    nm=z[z.CP_native_proxy_pp.notna()&z.ATR3_native_proxy_pp.notna()]
    mm=h[h.CP_native_proxy_pp.notna()&h.ATR3_native_proxy_pp.notna()]
    delta=nm.ATR3_native_proxy_pp-nm.CP_native_proxy_pp
    native[g]={'n':len(nm),'native_mean_delta_pp':float(delta.mean())}
    if g in matched:
        m=matched[g];assert len(mm)==m['n']
        assert same((mm.ATR3_native_proxy_pp-mm.CP_native_proxy_pp).mean(),m['native_mean_delta_pp'])
        assert same(mm.H20_ATR_minus_CP_pp.mean(),m['same_subset_H20_mean_delta_pp'])
    groups[g]={'raw':len(z),'funnel':b['h20_funnel'],'paired_H20_n':len(h),'common_label_n':len(labels),
       'strong_label_n':len(strong_labels),'strong_paired_n':len(strong),'H20_mean_delta_pp':b['H20_ATR_minus_CP_pp']['mean'],
       'native_comparable_n':len(nm),'matched_native_and_H20_n':len(mm)}
assert len(d[d.primary_group.isna()])==508
assert 51026-len(d)==1681

manifest=load('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
meta={x['symbol']:x for x in manifest};samples=[];sources={}
sample_keys=[('601949.SH','2023-04-12'),('000833.SZ','2024-10-25'),('688502.SH','2024-09-27'),('688082.SH','2026-04-27')]
for sid,anchor in sample_keys:
    row=d[d.sid.eq(sid)&d.anchor_day.eq(anchor)].iloc[0]
    parent='semiconductor_full' if row.primary_group=='2026_H1_SEMICONDUCTOR' else next(n for n in ['shard_a','shard_b'] if (R/n/'run_v1'/sid.replace('.','_')).exists())
    folder=R/parent/'run_v1'/sid.replace('.','_');sf=load(folder/'SOURCE_FREEZE.json')
    pp=next(x for x in sf['source_sha256'] if x.endswith('/signal.parquet'))
    fp=meta[sid]['refs']['facts']
    for p in [pp,fp]:assert sha(p)==sf['source_sha256'][p];sources[p]=sha(p)
    price=pd.read_parquet(pp).loc[:'2026-06-30'];nativefact=pd.read_parquet(fp)
    pair=next(x for x in load(folder/'CP_ANCHOR_PAIRS.json') if x['anchor_day']==anchor)
    ai=price.index.get_loc(pd.Timestamp(anchor));end=price.index.get_loc(pd.Timestamp(pair['common_end_day']))
    if pair['common_end_reason'] in ['UNKNOWN_DATA_OR_I','SOURCE_INCOMPARABLE']:end-=1
    fut=[]
    for j in range(ai+1,end+1):
        x=price.iloc[j]
        flags=[flag for flag in [x.price_eligible,x.observed_bar,x.synthetic_event_bar,x.source_invalid]]
        if not all(type(v).__name__ in ['bool','bool_'] for v in flags) or list(map(bool,flags))!=[True,True,False,False]:break
        if not (x.high>=x.close>=x.low>0) or x.segment_id!=price.iloc[ai].segment_id:break
        fut.append(j)
    assert len(fut)>=20
    assert str(price.index[fut[19]].date())==row.h20_close_day
    ti=fut[19]+1;assert str(price.index[ti].date())==row.terminal_day
    assert price.iloc[ai+1].open==row.entry_OPEN and price.iloc[ti].open==row.terminal_OPEN
    I=nativefact.reindex(price.index[ai+1:fut[19]+1]).i_target
    assert I.iloc[:-1].eq(1).all() and I.iloc[-1] in [0,1]
    evidence=[]
    for arm in ['CP','ATR3']:
        ej=price.index.get_loc(pd.Timestamp(row[f'{arm}_exit_day']))
        assert price.iloc[ej+1].open==row[f'{arm}_exit_OPEN']
        field=row[f'{arm}_H20_kind'];X=row[f'{arm}_exit_OPEN'] if field=='SAVED_EXIT_QUOTE_WITHIN20' else row.terminal_OPEN
        evidence.append({'arm':arm,'signal_exit_day':row[f'{arm}_exit_day'],'exit_reference_day':str(price.index[ej+1].date()),
           'exit_OPEN':row[f'{arm}_exit_OPEN'],'H20_kind':field,'H20_value_pp':100*(X/row.entry_OPEN-1)})
    samples.append({'sid':sid,'anchor':anchor,'entry_day':str(price.index[ai+1].date()),'entry_OPEN':row.entry_OPEN,
       'h20_close_day':row.h20_close_day,'terminal_day':row.terminal_day,'terminal_OPEN':row.terminal_OPEN,
       'original_I_first19_all_on':True,'arms':evidence,'delta_pp':row.H20_ATR_minus_CP_pp,
       'coordinate':'All E/T/X read exact adjusted OPEN from the same original source file; no cross-domain mixing.'})

out={'status':'PASS_BOUNDED_SAVED_H20_POST5_AND_FOUR_SOURCE_SAMPLES_WITH_LIMITS',
 'groups':groups,'native_comparable':native,'date_bridge':{'old2024':12412,'from924':11904,'Sep1_to23':508,'old2025_26semi':2901,'2026H1semi':1220,'2025excluded':1681},
 'all_saved_diagnostic_rows_checked':len(d),'source_samples':samples,'source_sha256_verified':sources,
 'current_bindings':{str(p):sha(p) for p in [P/'FREEZE.md',P/'fixed_horizon.py',P/'PRICE_DIAGNOSTIC_ROWS.parquet',P/'FIXED_H20_AND_POST5_STATS.json',P/'MATCHED_PANEL_NATIVE_VS_H20.json']},
 'scope':'Recount all saved row funnels/proxies/distributions/labels/post5 aggregates and matched panels; independently read original price/nativeI for four H20 extremes. No full-source post5 path recomputation or model execution.',
 'limits':['All price proxies and terminal marks, no actual execution/cash/quantity/fees/returns',
   'Native, matched H20 and all H20 populations/holding periods differ; differences cannot be attributed solely to clock',
   'Shared labels conditional on original-I surviving20; not all failed anchors or full-life tails',
   'Whole missing calendar sessions, legal limit/halt/ST/orderbook/receive remain unknown'],
 'remaining_blocks_for_this_statistical_scope':[],'new_FSM_runs':0,'new_accounts':0,'parameter_searches':0}
(O/'H20_POST5_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps({'status':out['status'],'groups':groups,'source_samples':samples},ensure_ascii=False))
