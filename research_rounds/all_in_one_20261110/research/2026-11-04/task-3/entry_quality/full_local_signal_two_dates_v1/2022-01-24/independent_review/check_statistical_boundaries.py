"""Compile only saved bands/stats definitions; synthetic summary cells, no prices/models."""
from pathlib import Path
import ast,hashlib,json
import numpy as np,pandas as pd

R=Path(__file__).resolve().parents[2]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    reports=[]
    for day in ['2022-01-24','2026-01-15']:
        path=R/day/'summarize.py';source=path.read_text();tree=ast.parse(source)
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in ['bands','stats']]
        assert len(functions)==2
        ns={'np':np,'pd':pd,'COMMON_ENDPOINTS':{'5':'2000-01-06','20':'2000-01-21'}}
        exec(compile(ast.fix_missing_locations(ast.Module(body=functions,type_ignores=[])),str(path),'exec'),ns)
        # These are isolated statistical cell values, not a generated market path.
        frame=pd.DataFrame({'sid':['a','b','c'],'rank':pd.Series([1,2,pd.NA],dtype='Int64'),'decile':pd.Series([1,6,pd.NA],dtype='Int64'),'PVR_rank_unknown':[False,False,True]})
        frame['h5_complete']=[True,True,False];frame['h5_right_censored']=[False,False,True]
        frame['h5_source_union_missing_row_proxy']=0;frame['h5_return']=[.1,-.2,np.nan]
        frame['h5_max_up']=[.15,0.,np.nan];frame['h5_max_adverse']=[0.,-.2,np.nan]
        frame['h5_nth_date']=['2000-01-06','2000-01-06',None];frame['h5_calendar_span_days']=[5,5,np.nan]
        groups=dict(ns['bands'](frame,'rank','decile'))
        assert len(groups['ALL'])==3 and len(groups['RANKABLE'])==2 and len(groups['PVR_UNKNOWN'])==1
        assert len(groups['TOP20'])==len(groups['TOP100'])==2 and len(groups['REST20'])==len(groups['REST100'])==0
        assert groups['TOP20'].sid.tolist()==['a','b']and groups['PVR_UNKNOWN'].sid.tolist()==['c']
        tails={'EXPOST_TOP1PCT':{'a'},'EXPOST_TOP5PCT':{'a'}};denoms={'positive_terminal':.1,'MFE':.15}
        empty=ns['stats'](frame.iloc[:0],5,tails,denoms,'TEST','TEST','EMPTY')
        assert empty['prior_N']==empty['complete_N']==0 and pd.isna(empty['terminal_mean'])and pd.isna(empty['terminal_positive_rate_complete'])and pd.isna(empty['within_group_largest1_positive_terminal_mass_share'])
        assert empty['EXPOST_TOP1PCT_hits']==0 and empty['EXPOST_TOP1PCT_capture_global_complete']==0
        unknown=ns['stats'](groups['PVR_UNKNOWN'],5,tails,denoms,'TEST','TEST','UNKNOWN_PATH')
        assert unknown['prior_N']==unknown['unknown_N']==1 and unknown['complete_N']==0 and unknown['prior_PVR_unknown_N']==1
        assert pd.isna(unknown['terminal_mean'])and pd.isna(unknown['EXPOST_TOP1PCT_precision_group_complete'])
        negative=ns['stats'](frame.iloc[1:2],5,tails,denoms,'TEST','TEST','NO_POSITIVE_MASS')
        assert pd.isna(negative['within_group_largest1_positive_terminal_mass_share'])and negative['positive_terminal_change_mass_share']==0
        # Unknown PVR but known future label is retained in ALL and can be a tail.
        futureknown=frame.copy();futureknown.loc[2,['h5_complete','h5_right_censored']]=[True,False]
        futureknown.loc[2,['h5_return','h5_max_up','h5_max_adverse','h5_nth_date','h5_calendar_span_days']]=[.3,.4,0.,'2000-01-06',5]
        tailunknown={'EXPOST_TOP1PCT':{'c'},'EXPOST_TOP5PCT':{'c'}}
        allstats=ns['stats'](futureknown,5,tailunknown,{'positive_terminal':.4,'MFE':.55},'TEST','TEST','ALL')
        unknownstats=ns['stats'](futureknown.iloc[2:],5,tailunknown,{'positive_terminal':.4,'MFE':.55},'TEST','TEST','PVR_UNKNOWN')
        assert allstats['prior_N']==allstats['complete_N']==3 and abs(allstats['terminal_mean']-(.1-.2+.3)/3)<1e-15
        assert unknownstats['EXPOST_TOP1PCT_capture_global_complete']==1 and unknownstats['prior_rankable_N']==0
        result={'status':'PASS_BOUNDED_EMPTY_UNKNOWN_SMALL_N_STATISTICAL_FUNCTIONS','date':day,'scope':'Only original bands/stats definitions AST-extracted; no module-level receipt/future file loading, no source prices/model/Account imports.','checks':['Nrankable2 preserves third unknown in ALL/unknown bucket; decile/top/rest exclude it.','TOP20/TOP100=min(k,2); REST groups empty without fabricated members.','Empty means/precision/own-positive-mass ratios are NA; zero hits/global capture0 is legitimate empty-set count.','Unknown future path stays unknown and is not a zero-return observation.','Known future label on PVR-unknown member stays ALL and can appear in global ex-post tail; no future pruning.','Zero positive mass own-concentration ratio NA, not0/exception.'],'global_fraction_semantics':'positive count/priorN and empty-group global capture are extensive-count fractions, not a known success rate of censored members.','source_sha256':{str(path.resolve()):sha(path),str(Path(__file__).resolve()):sha(Path(__file__))},'new_models':0,'new_accounts':0,'real_future_labels_read':False,'final_data_audit':'PENDING'}
        out=R/day/'independent_review';out.mkdir(exist_ok=True);p=out/'STATISTICAL_BOUNDARY_AUDIT.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        reports.append({'day':day,'sha256':sha(p)})
    print(json.dumps(reports))
if __name__=='__main__':main()
