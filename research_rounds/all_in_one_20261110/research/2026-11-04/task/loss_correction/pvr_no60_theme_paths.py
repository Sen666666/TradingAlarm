"""Actual strict-semiconductor H1 stock cashflows and lifecycle only.
Reuse the saved-reader's original price, metadata and original native books.
No opportunity labels, pool60 formulas, engine imports or account events.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,hashlib,importlib.util
import analyze_pvr_no60 as L
A,M,META=L.A,L.M,L.META;Z=D(0)
P=Path(__file__).resolve().parent/'pvr_no60_2025_26'
ROOTS={'PVR_BASELINE':L.OLD/'runs/2025_26','PVR_NO60':Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/runs/2025_26')}
SECTOR='URFI881121';BEFORE='2025-12-31';LO='2026-01-01';END='2026-06-30'
def day(at):return str(at)[:10]
def n(x):return D(str(x))
def save(name,x):
    with (P/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str)
def main():
    ids={sid for sid,m in META.items() if m['sector_id']==SECTOR};result={};source={}
    for name,root in ROOTS.items():
        book=A.book(root/'pair/B.json.gz');daily=A.rows(root/'pair/daily.jsonl.gz');dd={day(r['at']):r for r in daily};assert BEFORE in dd and END in dd
        source[str(root/'pair/B.json.gz')]=L.sha(root/'pair/B.json.gz');source[str(root/'pair/daily.jsonl.gz')]=L.sha(root/'pair/daily.jsonl.gz')
        acts=json.loads((P/(name+'-ENTRY_ACTIONS.json')).read_text());exits=json.loads((P/(name+'-EXIT_CHAIN.json')).read_text());layers=json.loads((P/'analysis/2025_26'/name/'LAYERS.json').read_text());out=[]
        for layer in layers:
            for key in ['cost','net','value']:layer[key]=n(layer[key])
        for sid in sorted(ids):
            tx=[t for t in book['trades'] if t['security_id']==sid and LO<=day(t['at'])<=END];buys=[t for t in tx if t['side']=='buy'];sells=[t for t in tx if t['side']=='sell']
            q0=dd[BEFORE]['positions'].get(sid,0);q1=dd[END]['positions'].get(sid,0)
            if not tx and not q0 and not q1:continue
            v0=D(q0)*A.price(sid,BEFORE) if q0 else Z;v1=D(q1)*A.price(sid,END) if q1 else Z
            bg=sum((n(t['gross_cny']) for t in buys),Z);sg=sum((n(t['gross_cny']) for t in sells),Z);fee=sum((n(t['fees_cny']) for t in tx),Z)
            div=sum((n(a['receivable']['net_local']) for a in book['audit'] if a['kind']=='dividend_accrual' and a['receivable']['security_id']==sid and LO<=day(a['receivable']['ex_at'])<=END),Z)
            net=sg-bg-fee+div+v1-v0
            aa=[a for a in acts if a['sid']==sid and LO<=day(a['at'])<=END]
            es=[x for x in exits if x['sid']==sid and LO<=day(x['request_at'])<=END]
            rr=[l for l in layers if l['sid']==sid]
            out.append(dict(sid=sid,name=META[sid]['name'],industry=META[sid]['industry'],strict_sector=SECTOR,H1_interval_contribution=net,initial_qty=q0,terminal_qty=q1,initial_value=v0,terminal_value=v1,H1_actual_buy_gross=bg,H1_actual_buy_including_fees=bg+sum((n(t['fees_cny']) for t in buys),Z),H1_actual_sell_gross=sg,H1_all_trade_fees=fee,H1_accrued_dividend=div,actual_first_H1_buy=buys[0]['at'] if buys else None,actual_buys=buys,actual_sells=sells,H1_entry_action_counts=dict(Counter(a['action'] for a in aa)),H1_entry_actions=aa,H1_exit_requests_and_fills=es,H1_exit_reasons=dict(Counter(x['reason'] for x in es)),whole_original_window_layers=rr,whole_original_window_contribution=M.contribution(rr),interval_cash_inventory_identity='sell-buy-fees+recognized_dividend+terminal_inventory-initial_inventory; no original lifecycle labels reused as interval PnL'))
        result[name]=dict(strict_members_in_current_metadata=len(ids),active_H1_stocks=len(out),H1_total_contribution=sum((z['H1_interval_contribution'] for z in out),Z),H1_buy_gross=sum((z['H1_actual_buy_gross'] for z in out),Z),H1_buy_including_fees=sum((z['H1_actual_buy_including_fees'] for z in out),Z),all_stock_rows=sorted(out,key=lambda z:-z['H1_interval_contribution']),H1_actions=dict(Counter(a['action'] for a in acts if a['sid'] in ids and LO<=day(a['at'])<=END)))
    save('STRICT_SEMICONDUCTOR_H1_STOCK_LIFECYCLES.json',result)
    save('STRICT_SEMICONDUCTOR_H1_SOURCE.json',dict(sources=source,price_reader_sha256=L.sha(L.ROOT/'c1-drawdown-capacity-20261101/analyze_saved.py'),analysis_sha256=L.sha(__file__),financial_events=0,no_pool60_remaining_capacity_used=True,no_adjacent_electronic_chemicals_or_components_merged=True))
    print(json.dumps({name:{k:v for k,v in r.items() if k!='all_stock_rows'} for name,r in result.items()},ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
