"""Read-only saved-case fee-field correction and original PRICE S path supplement.
This is a posterior reporting fix, never a consumer or a policy input.
The frozen cases_saved.py and all its outputs remain unchanged.
"""
import argparse,sys,ast
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from runtime import O,R,SOURCE,sha,read
from run_economic import save
import pandas as pd

def build(w):
    dest=O/'report_supplements_v1'/w;dest.mkdir(exist_ok=False)
    cdir=O/('cases_'+w);case=read(cdir/'AFFECTED_OLD_COHORT_FULL_NEW_PATHS.json')
    protected={str(cdir/n):h for n,h in read(cdir/'OUTPUT_SHA256.json').items()}
    tables={}
    for arm,d in [('baseline',SOURCE/('economic_'+w)),('joint',O/('gate_'+w))]:
        p=d/'joint/ROUNDS.csv';protected[str(p)]=sha(p)
        tables[arm]=pd.read_csv(p,float_precision='round_trip').set_index('round_id').to_dict('index')
    tape={};results=[];checked=0
    for sid,c in case['whole_stock_paths'].items():
        p=O/'market_tape'/(sid+'.parquet')
        if p.exists():tape[sid]=pd.read_parquet(p);protected[str(p)]=sha(p)
        arms={}
        for arm,v in c['paths'].items():
            rr=[]
            for r in v['rounds']:
                native=tables[arm][r['round_id']];aa=r['actions'];observed_fee_sum=sum(float(a['fee']) for a in aa)
                allfees=native.get('all_fees');known=pd.notna(allfees);reconciled=None
                if aa and known:
                    assert abs(observed_fee_sum-float(allfees))<1e-8,(r['round_id'],'FEE_RECONCILIATION')
                    checked+=1;reconciled=True
                protection=[]
                if r['owner_lane']=='PRICE' and aa and sid in tape:
                    root=ast.literal_eval(native['price_root']);z=tape[sid]
                    end=native.get('exit_day') if pd.notna(native.get('exit_day')) else native.get('status_day')
                    z=z[z.day.ge(pd.Timestamp(native['signal_day']))&z.day.le(pd.Timestamp(end))&z.root_day.eq(pd.Timestamp(root[-1]))]
                    if len(z):
                        changes=z.S_new.ne(z.S_new.shift())|z.failed|z.root_unknown|z.e0_raised
                        changes.iloc[0]=True
                        protection=z.loc[changes,['day','root_day','S_old','S_new','e0_raised','failed','root_unknown','phase','receipt','generation','entry_active','gate_status']].to_dict('records')
                rr.append(dict(round_id=r['round_id'],native_round=native,all_fees=allfees,observed_action_fee_sum=observed_fee_sum,fee_sum_reconciled=reconciled,fee_sum_is_not_unknown_liability_total=not known,actions=aa,original_price_protection_changes=protection,protection_scope='Original market S only, joined by held root and date; gate retirement does not modify it' if r['owner_lane']=='PRICE' else 'Original AB rules unchanged; native entry floor/actions/exit evidence preserved'))
            arms[arm]=dict(stock=v['stock'],native_rounds=rr,claims=v['claims'])
        results.append(dict(sid=sid,difference=c['difference'],paths=arms))
    for p,h in protected.items():assert sha(p)==h,('SOURCE_CHANGED',p)
    save(dest/'CORRECTED_FEES_AND_PROTECTION_PATHS.json',dict(window=w,reporting_correction='Frozen cases selected nonexistent fees field. Original column is all_fees; all underlying action fee values and formal metrics were already correct. Original artifact is preserved; use this supplement for round fee display.',checked_entered_rounds=checked,stocks=len(results),cases=results,source_sha256=protected,script_sha256=sha(__file__),economic_runs=0,fee_recalculation=False,gate_policy_changed=False))
    save(dest/'OUTPUT_SHA256.json',{p.name:sha(p) for p in dest.iterdir() if p.is_file()})
    print('CASE_FEE_PROTECTION_SUPPLEMENT_READY',w,len(results),checked,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2024'],required=True);build(p.parse_args().window)
