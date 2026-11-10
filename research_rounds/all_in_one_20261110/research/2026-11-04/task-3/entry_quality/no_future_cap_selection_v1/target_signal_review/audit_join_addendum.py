"""Read-only42-row join addendum; preserve already sealed source review."""
from pathlib import Path
import json,hashlib
import pandas as pd
R=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    joined=R/'TARGET42_WITH_PVR_LIQUIDITY.parquet';source=R/'target_signal_completion/TARGET42.parquet';basepath=R/'SNAPSHOT_GATE_COMPARISON.parquet'
    x=pd.read_parquet(joined).set_index(['sid','day']).sort_index();s=pd.read_parquet(source).set_index(['sid','day']).sort_index();b=pd.read_parquet(basepath).set_index(['sid','day']).sort_index()
    assert len(x)==42 and x.index.is_unique and x.index.equals(s.index)
    for c in b.columns:pd.testing.assert_series_equal(x[c],b.loc[x.index,c],check_names=False)
    for c in s.columns:
        target=c if c not in b.columns else c+'_original_signal'
        pd.testing.assert_series_equal(x[target],s[c],check_names=False)
    ready=x.status.eq('EXACT_TARGET_STOCK_SIGNAL')&x.e0_ready.eq(1)
    assert ready.sum()==36
    assert x.loc[~ready,['stock_I_hold_research','stock_i_buy_research']].isna().all().all()
    assert x.loc[ready,'stock_I_hold_research'].tolist()==x.loc[ready,'i_target'].eq(1).tolist()
    assert x.loc[ready,'stock_i_buy_research'].tolist()==(x.loc[ready,'i_target'].eq(1)&x.loc[ready,'i_buy'].eq(True)).tolist()
    for name,expected in [('no_cap_PVR_and_i_buy_research',x.research_no_cap_pool&x.stock_i_buy_research),('snapshot_PVR_and_i_buy_comparator',x.snapshot_cap_PVR_pool&x.stock_i_buy_research)]:pd.testing.assert_series_equal(x[name],expected,check_names=False)
    assert x.executable_eligibility.eq('UNKNOWN_NOT_CERTIFIED').all()and x.full_S0_eligibility_q.isna().all()
    assert x.snapshot_cap_q.eq(True).all()
    summary=json.loads((R/'TARGET42_JOIN_SUMMARY.json').read_text())
    assert summary['original_E0_ready']==36 and summary['stock_I_hold_true']==int(x.stock_I_hold_research.eq(True).sum())==33
    assert summary['stock_i_buy_true']==int(x.stock_i_buy_research.eq(True).sum())==18
    result={'status':'PASS_BOUNDED_TARGET42_JOIN_NO_SCORE_OR_SIGNAL_MIX','remaining_blocks':[],'counts':{'rows':42,'ready':36,'hold_true':33,'i_buy_true':18,'missing':4,'present_unready':2},'checks':['All base score/rank/liquidity/legal metadata unchanged at all42 keys.','All original signal metadata/fields unchanged, no conflicting field override.','Missing4 and unready2 stock-hold/fresh-study booleans remain nullable NA.','All42 current snapshot cap pass does not grant execution; legal state remains UNKNOWN and full S0qNone.','Both PVR conjunction flags follow saved pandas nullable three-value conjunction; a known false PVR condition may yield false even when stock signal is unknown, not original S0q.'],'source_sha256':{str(p.resolve()):sha(p)for p in [joined,source,basepath,R/'merge_target_signals.py',R/'TARGET42_JOIN_SUMMARY.json',Path(__file__),O/'SEAL_RECEIPT.json']},'new_models':0,'new_accounts':0}
    f=O/'TARGET42_JOIN_ADDENDUM.json';f.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({'status':result['status'],'sha256':sha(f)}))
if __name__=='__main__':main()
