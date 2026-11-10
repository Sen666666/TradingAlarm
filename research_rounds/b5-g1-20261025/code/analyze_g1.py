"""Post-freeze reporting arithmetic only; cannot modify grades or policies."""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from g1util import *
from grade import LABELS,COLORS

FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
PC={'E0':'#287f74','G1_I':'#bc8542','G1_X':'#5579bb','G1_IX':'#ba596a'}

def main():
    from run_accounts import verify
    verify();assert read(HERE/'accounting-audit.json')['passed'];out=HERE/'analysis';out.mkdir(exist_ok=False);(out/'figures').mkdir()
    summary=pd.read_csv(HERE/'summary.csv',float_precision='round_trip');cases=read(HERE/'cases.json');base=summary.query("scenario=='base'")
    descriptive=summary.groupby(['role','scenario','policy'])[['net_return','max_drawdown','exposure_fraction','trades','natural_win_rate','tail_pnl','ordinary_pnl','fees','slippage']].mean().reset_index();descriptive.to_csv(out/'descriptive.csv',index=False)
    deltas=[]
    for role in ['fixed_scenario','continuous_check']:
        for scenario in SCENARIOS:
            z=summary.loc[summary.role.eq(role)&summary.scenario.eq(scenario)];original=z.loc[z.policy.eq('E0')].set_index('case')
            for policy in POLICIES[1:]:
                a=z.loc[z.policy.eq(policy)].set_index('case')
                for cid,r in a.iterrows():
                    o=original.loc[cid];deltas.append(dict(role=role,scenario=scenario,policy=policy,case=cid,return_difference=r.net_return-o.net_return,drawdown_difference=r.max_drawdown-o.max_drawdown,return_better=r.net_return>o.net_return,drawdown_better=r.max_drawdown<o.max_drawdown,both_better=r.net_return>o.net_return and r.max_drawdown<o.max_drawdown,exposure_difference=r.exposure_fraction-o.exposure_fraction))
    delta=pd.DataFrame(deltas);delta.to_csv(out/'paired-deltas.csv',index=False)
    paired=delta.groupby(['role','scenario','policy'])[['return_better','drawdown_better','both_better']].sum().reset_index();paired.to_csv(out/'paired-counts.csv',index=False)
    # Do not duplicate same dates from overlapping fixed scenes. Each of the
    # seven continuous checks contributes its own dates once. Hindsight labels
    # and future prices never enter classify().
    observations=[];associations=[]
    for c in [x for x in cases if x['role']=='continuous_check']:
        d=pd.read_parquet(HERE/'inputs'/f"{c['symbol']}.parquet").loc[c['start']:c['end']];g=pd.read_parquet(HERE/'grading'/f"{c['symbol']}.parquet").loc[d.index]
        for h in [5,21,63]:
            future=d.close.shift(-h)/d.close-1
            for dt,r in g.loc[g.ready&future.notna()].iterrows():observations.append(dict(symbol=c['symbol'],date=str(dt.date()),grade=int(r.grade),score=int(r.score),horizon=h,future_return=float(future.loc[dt])))
            for grade,group in future.groupby(g.grade):
                v=group.dropna()
                if len(v):associations.append(dict(symbol=c['symbol'],grade=int(grade),score=25*int(grade),horizon=h,observations=len(v),mean=float(v.mean()),median=float(v.median()),positive_fraction=float(v.gt(0).mean()),q10=float(v.quantile(.1)),q90=float(v.quantile(.9))))
    observations=pd.DataFrame(observations);observations.to_csv(out/'forward-association-observations.csv',index=False);pd.DataFrame(associations).to_csv(out/'forward-associations-by-asset.csv',index=False)
    assoc=observations.groupby(['grade','score','horizon']).future_return.agg(['count','mean','median']).reset_index();assoc.to_csv(out/'forward-associations-pooled.csv',index=False)
    # Which old E0 >=30% realized legs lose participation? This is a calendar
    # overlap diagnostic, not counterfactual recoverable profit or attribution.
    coverage=[]
    for c in cases:
        e0=pd.read_csv(HERE/'accounts'/f"{c['id']}__E0__base"/'trades.csv',float_precision='round_trip')
        for i,t in e0.loc[e0.net_return.ge(.3)].iterrows():
            for policy in POLICIES:
                p=HERE/'accounts'/f"{c['id']}__{policy}__base";l=pd.read_parquet(p/'ledger.parquet');tr=pd.read_csv(p/'trades.csv',float_precision='round_trip');g=pd.read_parquet(HERE/'grading'/f"{c['symbol']}.parquet")
                z=l.loc[t.entry_date:t.exit_date];entries=tr.loc[tr.entry_date.ge(t.entry_date)&tr.entry_date.le(t.exit_date)]
                exits=tr.loc[tr.exit_date.ge(t.entry_date)&tr.exit_date.le(t.exit_date)&tr.exit_reason.eq('G1_cold_or_acute')]
                signal=t.entry_signal;siggrade=None if signal=='preset_start' else int(g.loc[signal,'grade'])
                coverage.append(dict(case=c['id'],role=c['role'],E0_leg=int(i),E0_entry=t.entry_date,E0_exit=t.exit_date,E0_net_return=t.net_return,E0_net_pnl=t.net_pnl,policy=policy,calendar_observations=len(z),held_observations=int(z.held.sum()),held_fraction=float(z.held.mean()),first_own_entry=entries.entry_date.iloc[0] if len(entries) else None,first_sensitive_exit=exits.exit_date.iloc[0] if len(exits) else None,sensitive_exits_in_window=len(exits),grade_on_E0_entry_signal=siggrade,note='overlapping-window diagnostic, not return attribution'))
    pd.DataFrame(coverage).to_csv(out/'E0-tail-participation.csv',index=False)
    # Enrich every actual trade with its known entry/exit evidence.
    trade_rows=[]
    for x in base.to_dict('records'):
        t=pd.read_csv(HERE/'accounts'/x['key']/'trades.csv',float_precision='round_trip');g=pd.read_parquet(HERE/'grading'/f"{x['symbol']}.parquet")
        for tr in t.to_dict('records'):
            entry=tr['entry_signal'];exit=tr['exit_signal'];a=None if entry=='preset_start' else g.loc[entry];b=None if exit=='preset_end' else g.loc[exit]
            trade_rows.append(dict(case=x['case'],policy=x['policy'],**tr,entry_grade=None if a is None else int(a.grade),entry_phase=None if a is None else a.phase,entry_evidence=None if a is None else a.up_reasons,exit_grade=None if b is None else int(b.grade),exit_phase=None if b is None else b.phase))
    pd.DataFrame(trade_rows).to_csv(out/'actual-trades-with-evidence.csv',index=False)
    for cid in ['bull_semi25_26h1','semi_ytd26','continuous_USHJ518880']:
        c=next(x for x in cases if x['id']==cid);d=pd.read_parquet(HERE/'inputs'/f"{c['symbol']}.parquet").loc[c['start']:c['end']];g=pd.read_parquet(HERE/'grading'/f"{c['symbol']}.parquet").loc[d.index]
        fig,axs=plt.subplots(4,1,figsize=(14,9.8),sharex=True,gridspec_kw={'height_ratios':[2.3,1.3,2.3,1.3]})
        axs[0].plot(d.index,d.close,color='#283343',lw=.8);axs[0].scatter(d.index,d.close,c=[COLORS[int(v)] for v in g.grade],s=8);axs[0].set_title(c['name']+' '+c['start']+'—'+c['end']+'：量价等级、净值与回撤',fontproperties=FONT)
        axs[1].step(d.index,g.score,color='#aa7540',lw=.8,where='post');axs[1].axhline(50,lw=.4,color='gray');axs[1].axhline(-50,lw=.4,color='gray');axs[1].set_ylabel('G1 score')
        for policy in POLICIES:
            l=pd.read_parquet(HERE/'accounts'/f'{cid}__{policy}__base'/'ledger.parquet');x=base.loc[base.case.eq(cid)&base.policy.eq(policy)].iloc[0]
            axs[2].plot(l.index,l.nav,color=PC[policy],lw=1,label=f'{policy} {x.net_return:+.1%} / DD {x.max_drawdown:.1%}');axs[3].plot(l.index,l.drawdown*100,color=PC[policy],lw=.8)
        axs[2].set_ylabel('NAV');axs[2].legend(fontsize=8);axs[3].set_ylabel('drawdown %')
        for ax in axs:ax.grid(alpha=.15)
        fig.tight_layout();fig.savefig(out/'figures'/f'{cid}.png',dpi=130);plt.close(fig)
    write(out/'summary.json',dict(recorded_at=now(),descriptive=descriptive.to_dict('records'),paired_counts=paired.to_dict('records'),overlapping_seen_development=True,causal_grade_frozen_before_accounts=True,grade_formula_updates_after_results=0,pooled_means_are_not_portfolio=True))
    print(descriptive.to_string(index=False),flush=True)

if __name__=='__main__':main()
