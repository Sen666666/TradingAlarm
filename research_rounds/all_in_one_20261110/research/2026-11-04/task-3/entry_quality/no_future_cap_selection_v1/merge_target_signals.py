"""Join the bounded causal-prefix signal exercise to unchanged research ranks."""
from pathlib import Path
import json
import pandas as pd

HERE=Path(__file__).resolve().parent


def main():
    base=pd.read_parquet(HERE/'SNAPSHOT_GATE_COMPARISON.parquet')
    signal=pd.read_parquet(HERE/'target_signal_completion/TARGET42.parquet')
    assert len(signal)==42 and not signal.duplicated(['sid','day']).any()
    out=base.merge(signal,on=['sid','day'],how='inner',validate='one_to_one',suffixes=('','_original_signal'))
    assert len(out)==42
    for name in ['stock_I_hold_research','stock_i_buy_research']:
        out[name]=pd.Series(pd.NA,index=out.index,dtype='boolean')
    ready=out.status.eq('EXACT_TARGET_STOCK_SIGNAL') & out.e0_ready.eq(1)
    out.loc[ready,'stock_I_hold_research']=out.loc[ready,'i_target'].eq(1)
    out.loc[ready,'stock_i_buy_research']=(out.loc[ready,'i_target'].eq(1) & out.loc[ready,'i_buy'].eq(True))
    out['no_cap_PVR_and_i_buy_research']=out.research_no_cap_pool & out.stock_i_buy_research
    out['snapshot_PVR_and_i_buy_comparator']=out.snapshot_cap_PVR_pool & out.stock_i_buy_research
    assert out.executable_eligibility.eq('UNKNOWN_NOT_CERTIFIED').all()
    out.to_parquet(HERE/'TARGET42_WITH_PVR_LIQUIDITY.parquet',index=False,compression='zstd')
    out.to_csv(HERE/'TARGET42_WITH_PVR_LIQUIDITY.csv',index=False)
    summary=dict(requests=42,exact_signals=int(out.status.eq('EXACT_TARGET_STOCK_SIGNAL').sum()),
        missing_target_bar=int(out.status.eq('MISSING_TARGET_BAR').sum()),
        original_E0_ready=int(ready.sum()),not_ready_on_present=int((out.status.eq('EXACT_TARGET_STOCK_SIGNAL') & ~ready).sum()),
        stock_I_hold_true=int(out.stock_I_hold_research.eq(True).sum()),
        stock_i_buy_true=int(out.stock_i_buy_research.eq(True).sum()),
        PVR_and_i_buy_true=int(out.no_cap_PVR_and_i_buy_research.eq(True).sum()),
        global_signal_qualified_ranking=False,executable_permission=False)
    (HERE/'TARGET42_JOIN_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
