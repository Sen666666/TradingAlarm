"""Matched D1 saved-book finance; original audited account reader unchanged."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze_pvr_pool_finance as F
A=F.A;M=F.M;Z=D(0);HERE=Path(__file__).resolve().parent;OUT=HERE/'no60_d1_strong_finance'
OLD=F.ROOT/'pvr-slot1-d1-v2-composition-preflight-20261101/run-PVR-D1'
NEW=HERE.parent/'pvr_pressure_readiness/run-D1-strong'
def n(x):return D(str(x))
def main():
    OUT.mkdir(exist_ok=False);A.O=OUT;M.O=OUT;data={};result={}
    for ref,root in [('PVR_SLOT1_D1',OLD),('PVR_NO_CONFIRMED60_D1',NEW)]:
        assert F.read(root/'DONE.json')['completed'];a=A.account('2025_26',ref,root);data[ref]=a
        ds=a['daily'];book=a['book'];reserves=[j for j in book['journal'] if j['kind']=='real_reserve'];filled={j['budget_order'] for j in book['journal'] if j['kind']=='real_buy_fill'}
        result[ref]=dict(metrics=a['metrics'],money_split=F.money_split(a),layer_contributions=M.contribution(a['layers']),
            mean_available_cash_pct=sum((n(r['available'])/n(r['nav'])*100 for r in ds),Z)/242,
            mean_reserved_assets_pct=sum((n(r['order_reserved'])/n(r['nav'])*100 for r in ds),Z)/242,
            mean_confirmed_commitment_pct=sum((n(r['pool_confirmed'][0])/n(r['nav'])*100 for r in ds),Z)/242,
            mean_nominal_risk_pct=sum(((n(r['pool_probe'][1])+n(r['pool_confirmed'][1]))/n(r['nav'])*100 for r in ds),Z)/242,
            actual_reservations=len(reserves),actual_filled_orders=len(filled),zero_fill_reservations_including_terminal_pending=sum(j['budget_order'] not in filled for j in reserves),
            terminal_available=ds[-1]['available'],terminal_order_reserved=ds[-1]['order_reserved'],terminal_sale_receivable=ds[-1]['sale_receivable'],
            verification=F.native_saved_audit(a,root,'2025_26'),
            pending_assets_are_not_spendable_cash=True,zero_fill_is_not_all_cancelled=True)
        F.save(OUT/(ref+'_THEMES.json'),F.themes(a,'2025_26'));F.save(OUT/(ref+'_DAILY.json'),ds)
        for name in ['B.json.gz','daily.jsonl.gz','balances.jsonl.gz','B-D1_AUDIT.json']:
            p=root/'pair'/name
            if p.exists():F.SRC[str(p)]=F.sha(p)
    old=data['PVR_SLOT1_D1'];new=data['PVR_NO_CONFIRMED60_D1'];delta=[]
    for sid in set(old['stock'])|set(new['stock']):delta.append(dict(sid=sid,name=A.META[sid]['name'],old=old['stock'].get(sid,Z),new=new['stock'].get(sid,Z),delta=new['stock'].get(sid,Z)-old['stock'].get(sid,Z)))
    navdelta=n(new['book']['ending_NAV'])-n(old['book']['ending_NAV']);assert abs(sum((r['delta'] for r in delta),Z)-navdelta)<D('.00001')
    normal=F.read(HERE/'pvr_pool_results_2025_26/FINANCE_COMPARISON.json')
    result['matched_D1_delta_NAV']=navdelta;result['matched_D1_return_pp_gain']=result['PVR_NO_CONFIRMED60_D1']['metrics']['return_pct']-result['PVR_SLOT1_D1']['metrics']['return_pct']
    result['normal_policy_return_pp_gain']=n(normal['PVR_NO_CONFIRMED60']['metrics']['return_pct'])-n(normal['PVR_SLOT1']['metrics']['return_pct'])
    result['interaction_D1_minus_normal_policy_gain_pp']=result['matched_D1_return_pp_gain']-result['normal_policy_return_pp_gain']
    result['normal_references']={k:normal[k]['metrics'] for k in ['PVR_SLOT1','PVR_NO_CONFIRMED60']}
    result['scope']='Only paired D1 old/new isolates capital60 under same pressure; normal comparisons are whole-path pressure effects, not per-order one-day return subtraction'
    F.save(OUT/'COMPARISON.json',result);F.save(OUT/'ALL_STOCK_WEALTH_BRIDGE.json',delta)
    for sid in A.frames:
        p=Path(A.SM[sid]['refs']['facts']);assert F.sha(p)==A.SM[sid]['output_sha256'][str(p)];F.SRC[str(p)]=F.sha(p)
    F.SRC[str(Path(F.__file__))]=F.sha(F.__file__);F.SRC[str(Path(__file__))]=F.sha(__file__)
    F.save(OUT/'SOURCE_MANIFEST.json',dict(sources=F.SRC,new_account_runs=0,old_D1_not_replayed=True,only_new_D1_frozen_path=NEW.as_posix()))
    print('NO60_MATCHED_D1_FINANCE_READY',navdelta,flush=True)
if __name__=='__main__':main()
