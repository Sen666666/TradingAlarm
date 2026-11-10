"""Two parent-selected R/B counterexamples. Saved facts only; no CP/FSM/account."""
from pathlib import Path
import hashlib,json,math,time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent
WORK=O.parents[1]
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
SOURCES={}
CASES=[('300085.SZ','银之杰','2024-09-23','2024-11-01'),
       ('601019.SH','山东出版','2023-03-20','2023-05-09')]
CANONICAL_MANIFESTS={
    '300085.SZ':Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/MANIFEST.json'),
    '601019.SH':Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/recovery-2023-readiness-20261101/inputs/MANIFEST.json')}

def bind(p):
    p=Path(p).resolve();SOURCES[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def clean(v):
    if v is pd.NA or v is pd.NaT:return None
    if isinstance(v,pd.Timestamp):return str(v.date())
    if isinstance(v,dict):return {str(k):clean(x)for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x)for x in v]
    if hasattr(v,'item'):return clean(v.item())
    if isinstance(v,float)and not math.isfinite(v):return None
    return v
def save(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def substitute(f,cp,e):
    """Each frozen denominator belongs to its own original pivot confirmation."""
    rows=[];anchors=[];low=high=None;segment=None;last_up=None
    for day,r in f.iterrows():
        seg=int(r.segment_id);c=cp.loc[day];ev=e.loc[day]
        if seg!=segment:low=high=last_up=None;segment=seg
        event=int(ev.event)if pd.notna(ev.event)else 0
        if event in(-1,1):
            a=dict(source_segment=seg,kind='low'if event==1 else'high',confirmation_day=str(day.date()),
                   pivot_day=str(pd.Timestamp(ev.confirmed_pivot_date).date()),
                   pivot_CLOSE_a=float(ev.confirmed_pivot_price),CP_z_at_confirmation=float(c.z),
                   frozen_sigma=math.sqrt(5)*float(c.z))
            assert a['pivot_day']<=a['confirmation_day']
            assert a['pivot_CLOSE_a']>0 and a['frozen_sigma']>0 and math.isfinite(a['frozen_sigma'])
            anchors.append(a)
            if event==1:low=a;last_up=a['confirmation_day']
            else:high=a
        C=float(r.close)
        R=math.log(C/low['pivot_CLOSE_a'])/low['frozen_sigma']if low else None
        B=math.log(C/high['pivot_CLOSE_a'])/high['frozen_sigma']if high else None
        new_frontier=bool(c.delta_frontier>0)if pd.notna(c.delta_frontier)else None
        # These are pointwise predicates, not a new confirmation/FSM or order.
        up=bool(ev.leg_direction==1)if pd.notna(ev.leg_direction)else None
        rows.append(dict(date=str(day.date()),source_segment=seg,CLOSE_a=C,raw_CLOSE=float(r.raw_close),
            E0_event=event,E0_leg_direction=float(ev.leg_direction),original_E0_target=int(r.e0_target),
            original_I_target=int(r.i_target),E0_up_confirmation_group=last_up,
            low_anchor=low.copy()if low else None,high_anchor=high.copy()if high else None,
            R=R,B=B,R_ge1=R>=1 if R is not None else None,B_ge0=B>=0 if B is not None else None,
            original_CP_z=float(c.z),original_CP_frozen_scale=float(c.scale),
            original_CP_frontier_log=float(c.frontier),original_CP_delta_frontier=float(c.delta_frontier),
            original_CP_new_frontier=new_frontier,original_CP_receipt=bool(c.receipt),
            original_CP_reset_reason=None if pd.isna(c.reset_reason)else str(c.reset_reason),
            original_CP_candidate_a=float(c.candidate),
            pointwise_fresh_frontier_R_ge1=bool(up is True and new_frontier is True and R is not None and R>=1),
            pointwise_fresh_frontier_R_ge1_B_ge0=bool(up is True and new_frontier is True and R is not None and R>=1 and B is not None and B>=0),
            E0_reversal_withdrawal_row=event==-1))
    return pd.DataFrame(rows).set_index('date'),anchors

def flat(df):
    x=df.copy()
    for k in('low_anchor','high_anchor'):
        for field in('confirmation_day','pivot_day','pivot_CLOSE_a','CP_z_at_confirmation','frozen_sigma'):
            x[k+'_'+field]=x[k].map(lambda a:a.get(field)if a else None)
        x=x.drop(columns=k)
    return x

def describe(df):
    records=df.reset_index().to_dict('records');groups=[];withdrawals=[]
    for group,g in df.groupby('E0_up_confirmation_group',sort=False):
        active=g.loc[g.E0_leg_direction.eq(1)]
        if active.empty:continue
        potential=active.loc[active.pointwise_fresh_frontier_R_ge1]
        mature=active.loc[active.pointwise_fresh_frontier_R_ge1_B_ge0]
        first=potential.index[0]if len(potential)else None
        after=active.loc[first:]if first else active.iloc[:0]
        after_first=after.iloc[1:]
        groups.append(dict(E0_up_confirmation_day=group,observations=len(active),
            first_possible_R_trial_day_WITHIN_WINDOW=first,first_possible_B_mature_frontier_day_WITHIN_WINDOW=mature.index[0]if len(mature)else None,
            original_CP_receipts=int(active.original_CP_receipt.sum()),
            new_frontier_R_ge1_observations=len(potential),mature_new_frontier_observations=len(mature),
            after_first_trial_new_frontier_R_ge1=int(after_first.pointwise_fresh_frontier_R_ge1.sum()),
            after_first_trial_original_receipts=int(after_first.original_CP_receipt.sum()),
            first_trial_raw_CLOSE=float(after.raw_CLOSE.iloc[0])if len(after)else None,
            last_up_leg_raw_CLOSE=float(active.raw_CLOSE.iloc[-1]),
            maximum_after_trial_CLOSE_a=float(after.CLOSE_a.max())if len(after)else None,
            price_extension_after_first_trial_pct=(float(after.CLOSE_a.max()/after.CLOSE_a.iloc[0])-1)*100 if len(after)else None,
            scope='These counts are window restricted; actual first eligible historical dates are added separately from the full causal leg. No new orders.'))
    for day,r in df.loc[df.E0_event.eq(-1)].iterrows():
        before=df.loc[df.index<day]
        prev=before.iloc[-1]if len(before)else None
        later=df.loc[df.index>day]
        up=later.loc[later.E0_event.eq(1)]
        nextup=up.index[0]if len(up)else None
        same=later.loc[later.index>=nextup]if nextup else later.iloc[:0]
        if len(same):
            cut=same.loc[same.E0_event.eq(-1)]
            if len(cut):same=same.loc[same.index<cut.index[0]]
        trial=same.loc[same.pointwise_fresh_frontier_R_ge1]
        mature=same.loc[same.pointwise_fresh_frontier_R_ge1_B_ge0]
        peak=float(r.high_anchor['pivot_CLOSE_a'])
        withdrawals.append(dict(E0_down_confirmation_day=day,confirmed_high_pivot_day=r.high_anchor['pivot_day'],
            confirmed_high_CLOSE_a=peak,down_confirmation_CLOSE_a=float(r.CLOSE_a),
            drawdown_from_confirmed_peak_at_confirmation_pct=(float(r.CLOSE_a)/peak-1)*100,
            R_at_reversal=float(r.R),B_at_reversal=float(r.B),
            original_E0_target_at_reversal=int(r.original_E0_target),original_I_target_at_reversal=int(r.original_I_target),
            previous_observation_R=float(prev.R)if prev is not None else None,
            previous_observation_B=float(prev.B)if prev is not None else None,
            next_original_E0_up_confirmation_day=nextup,
            first_subsequent_pointwise_R_trial_day=trial.index[0]if len(trial)else None,
            first_subsequent_pointwise_B_mature_frontier_day=mature.index[0]if len(mature)else None,
            next_up_confirmation_raw_CLOSE=float(df.loc[nextup,'raw_CLOSE'])if nextup else None,
            R_trial_raw_CLOSE=float(trial.raw_CLOSE.iloc[0])if len(trial)else None,
            B_mature_raw_CLOSE=float(mature.raw_CLOSE.iloc[0])if len(mature)else None,
            original_receipts_after_next_up_before_B_mature=int(same.loc[same.index<(mature.index[0]if len(mature)else '9999-12-31')].original_CP_receipt.sum()),
            warning='No trade/exit/loss follows from reversal alone. These rows quantify evidence withdrawal/requalification delay only.'))
    return dict(observations=len(df),original_receipts=int(df.original_CP_receipt.sum()),
                original_new_frontier_observations=int(df.original_CP_new_frontier.eq(True).sum()),
                original_E0_down_events=int(df.E0_event.eq(-1).sum()),
                original_E0_up_events=int(df.E0_event.eq(1).sum()),
                first_raw_CLOSE=float(df.raw_CLOSE.iloc[0]),last_raw_CLOSE=float(df.raw_CLOSE.iloc[-1]),
                continuous_CLOSE_extension_to_sample_max_pct=(float(df.CLOSE_a.max()/df.CLOSE_a.iloc[0])-1)*100,
                groups=groups,withdrawals=withdrawals,
                daily_rows_are_not_financial_returns=True)

def main():
    start=time.monotonic();bind(__file__);manifest=read(MANIFEST);summary={};prefix=[]
    for sid,name,lo,hi in CASES:
        rec=next(r for r in manifest if r['symbol']==sid)
        paths={k:rec['refs'][k]for k in('facts','CP1','CP1_input')}
        paths['events']=next(p for p in rec['source_sha256']if p.endswith('/events.parquet'))
        frames={}
        for k,p in paths.items():
            path=bind(p);expected=rec.get('output_sha256',{}).get(p,rec.get('source_sha256',{}).get(p))
            assert SOURCES[str(path)]==expected,(sid,k,'source SHA')
            frames[k]=pd.read_parquet(path).loc[:hi];frames[k].index=frames[k].index.as_unit('ns')
            assert frames[k].index.is_unique and frames[k].index.is_monotonic_increasing
        f,cp,inp,e=[frames[k]for k in('facts','CP1','CP1_input','events')]
        assert f.index.equals(cp.index)and cp.index.equals(inp.index)
        assert np.array_equal(f.close.to_numpy(),inp.close.to_numpy())
        assert np.array_equal(f.segment_id.to_numpy(),inp.segment_id.to_numpy())
        common=f.index.intersection(e.index);assert len(common)==len(f)
        full,anchors=substitute(f,cp,e)
        cm=next(x for x in read(CANONICAL_MANIFESTS[sid])if x['sid']==sid)
        assert cm['refs']['CP1']==rec['refs']['CP1']
        assert cm['original_output_sha256'][rec['refs']['CP1']]==rec['output_sha256'][rec['refs']['CP1']]
        rp=bind(cm['output_path']);assert SOURCES[str(rp)]==cm['output_sha256']
        receipts={x['confirmed_day']:x for x in read(rp)}
        full['original_canonical_receipt_id']=[receipts.get(day,{}).get('receipt_id')for day in full.index]
        full['original_canonical_E0_episode_id']=[receipts.get(day,{}).get('original_E0_episode_id')for day in full.index]
        for cut in [lo,str(full.loc[lo:hi].index[len(full.loc[lo:hi])//2]),hi]:
            smaller,_=substitute(f.loc[:cut],cp.loc[:cut],e.loc[:cut])
            pd.testing.assert_frame_equal(smaller,full.loc[:cut,smaller.columns],check_exact=True)
            prefix.append(dict(sid=sid,cut=cut,exact=True))
        selected=full.loc[lo:hi].copy();selected.insert(0,'sid',sid);selected.insert(1,'name',name)
        assert selected.original_CP_receipt.equals(selected.original_canonical_receipt_id.notna().rename('original_CP_receipt'))
        save(sid+'_DAILY_RB.json',selected.reset_index().to_dict('records'))
        flat(selected).to_csv(O/(sid+'_DAILY_RB.csv'))
        # Anchor rows are full prior causal provenance, not future pivot discovery.
        needed={r[k]['confirmation_day']for r in selected.to_dict('records')for k in('low_anchor','high_anchor')if r[k]}
        save(sid+'_ORIGINAL_E0_ANCHORS.json',[a for a in anchors if a['confirmation_day']in needed])
        summary[sid]=dict(name=name,window=[lo,hi],**describe(selected))
        for group in summary[sid]['groups']:
            whole=full.loc[full.E0_up_confirmation_group.eq(group['E0_up_confirmation_day'])&full.E0_leg_direction.eq(1)]
            trial=whole.loc[whole.pointwise_fresh_frontier_R_ge1]
            mature=whole.loc[whole.pointwise_fresh_frontier_R_ge1_B_ge0]
            group.update(full_leg_first_possible_R_trial_day=trial.index[0]if len(trial)else None,
                full_leg_first_possible_B_mature_frontier_day=mature.index[0]if len(mature)else None,
                full_leg_R_trial_raw_CLOSE=float(trial.raw_CLOSE.iloc[0])if len(trial)else None,
                full_leg_B_mature_raw_CLOSE=float(mature.raw_CLOSE.iloc[0])if len(mature)else None,
                full_leg_new_frontier_R_ge1_observations=len(trial),
                full_leg_original_CP_receipts=int(whole.original_CP_receipt.sum()))
        context=full.loc[(full.index>=min(selected.E0_up_confirmation_group))&(full.index<lo)].copy()
        save(sid+'_PREWINDOW_LEFT_CENSOR_CHECK.json',context.reset_index().to_dict('records'))
    save('SUMMARY.json',summary)
    old=read(WORK/'native_algorithm_read_v1/v_reversal_counterexample/SHANDONG_601019_EXACT_SAVED_WINDOW.json')
    save('ORIGINAL_ACCOUNT_CONTEXT_NOT_RB_COUNTERFACTUAL.json',{
        'scope':'Already saved original No60 facts only. No new quantity, fee, return, or R/B order is computed.',
        'parent_saved_ledger_candidate':old['parent_saved_ledger_candidate'],
        'original_first_exit_proposal':old['original_first_exit_proposal'],
        'original_funding':old['original_funding']})
    save('SCOPE.json',dict(new_accounts=0,new_CP_FSM=0,new_E0_G1_I_models=0,new_receipts=0,new_backtests=0,
        rows='Only original saved facts and original E0 event/CP output are read.',
        R='ln(C_t/last causally confirmed E0 low)/(sqrt(5)*CP.z at that low confirmation CLOSE)',
        B='ln(C_t/last causally confirmed E0 high)/(sqrt(5)*CP.z at that high confirmation CLOSE)',
        distinct_scale='Each anchor keeps its own confirmation-day z; no common low scale substituted for B.',
        pointwise='Original up-leg + original CP.delta_frontier>0 + R>=1; B>=0 separately recorded. No proposed FSM is run.',
        E0_reversal='event=-1 is original confirmed directional reversal, independent of E0_target/I_target remaining on.',
        one_trial='Count first eligible observation and remaining original-frontier/receipt observations; no assumed filled shares/cash or synthetic PnL.',
        price='All formula prices use original continuous signal coordinate. raw_CLOSE is display only. Future maxima are explicitly retrospective labels.',
        physical_prefix_checks=prefix,seconds=time.monotonic()-start))
    save('SOURCE_SHA256.json',SOURCES)
    print(json.dumps(clean(summary),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
