"""Independent CSV subset-row money cross-check after primary raw-reader bridges."""
from pathlib import Path
from decimal import Decimal as D
import csv,json,hashlib
O=Path(__file__).resolve().parent;E=O.parent/'market_gross_rule_and_outcome_explanation_v1';src={}
def read(name):
    p=E/name;src[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();rs=list(csv.DictReader(p.open()));m={r['sid']:r for r in rs};assert len(m)==len(rs);return m
def near(a,b):assert abs(D(a)-D(b))<D('.000001'),(a,b)
out={}
for win in ('long','strong'):
    B=read(f'ALL_ACTUAL_STOCK_COMPONENTS_{win}_ARCHIVED_B.csv');A=read(f'ALL_ACTUAL_STOCK_COMPONENTS_{win}_D_GROSS10.csv');ws=read(f'FIXED_B_WINNERS_ALL_{win}.csv')
    for sid,r in ws.items():
        b=B[sid];a=A.get(sid);near(r['B_original_net'],b['whole_window_stock_net']);near(r['D_original_net'],a['whole_window_stock_net']if a else'0');near(r['B_actual_buy_cash'],b['actual_buy_cash']);near(r['D_actual_buy_cash'],a['actual_buy_cash']if a else'0');near(r['path_net_difference_NOT_alpha'],D(r['D_original_net'])-D(r['B_original_net']));assert r['B_fixed_winner_definition'].endswith('POSTHOC')
    for suffix in ('D_UNBOUGHT','D_REDUCED'):
        for sid,r in read(f'FIXED_B_WINNERS_{suffix}_{win}.csv').items():assert r==ws[sid]
    new=read(f'ALL_D_NEWLY_FUNDED_{win}.csv');positive=read(f'ALL_D_NEW_POSITIVE_BENEFICIARIES_{win}.csv')
    for sid,r in new.items():
        for k,v in A[sid].items():assert r[k]==v,(win,sid,k)
        near(r['path_net_NOT_alpha'],A[sid]['whole_window_stock_net'])
    for sid,r in positive.items():assert r==new[sid]
    delta=read(f'ALL_STOCK_PATH_DIFFERENCES_{win}.csv')
    for sid,r in read(f'ALL_POSITIVE_PATH_DIFFERENCES_{win}.csv').items():assert r==delta[sid]
    for rs in (A,B):
        for sid,r in rs.items():near(D(r['closed_layer_trade_cash_net_ex_dividend'])+D(r['open_layer_trade_cash_net_ex_dividend_NOT_unrealized_PnL'])+D(r['terminal_marked_inventory_VALUE_NOT_PnL'])+D(r['recognized_dividend_equity_paid_plus_AR']),r['whole_window_stock_net'])
    out[win]=dict(all_B_winner_money_rows=len(ws),all_new_money_rows=len(new),positive_new_rows=len(positive),subset_rows_identical_to_full_parent=True,CSV_native_component_arithmetic_exact=True)
r=dict(passed=True,status='PASS_SUPPLEMENTAL_COMPLETE_SUBSET_MONEY',scope='Cross-check all subset rows and amounts against whole component CSVs already bridged to original reader/native by primary AUDIT.json; no valuation.',results=out,source_SHA256=src,reviewer_source_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest());p=O/'SUBSET_MONEY_AUDIT.json';assert not p.exists();p.write_text(json.dumps(r,indent=2)+'\n');print(p,hashlib.sha256(p.read_bytes()).hexdigest())
