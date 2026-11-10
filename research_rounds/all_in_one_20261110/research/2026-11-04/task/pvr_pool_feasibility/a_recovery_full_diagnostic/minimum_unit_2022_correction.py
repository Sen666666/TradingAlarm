"""Three frozen dates: single-probe necessary conditions, no orders/S0/account."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import sys,json,hashlib,math
import pandas as pd
O=Path(__file__).resolve().parent;ROOT=O.parents[1]
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');M=Path('/Users/bytedance/Documents/ChatGPT/money');SRC={};FR={};ST={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p.resolve())]=sha(p);return json.loads(p.read_text())
OUTPUT=O/'minimum-unit-2022-source-correction'
OUTPUT.mkdir(exist_ok=True)
def save(n,x):(OUTPUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def version(rows,day):
    v=[r for r in rows if r['from']<=day and(not r.get('to')or day<r['to'])];assert len(v)==1;return v[0]
def main():
    assert not (OUTPUT/'MINIMUM_UNIT_RESULTS.json').exists()
    scope=read(O/'MINIMUM_UNIT_SCOPE_FREEZE.json');assert sha(O/'MINIMUM_UNIT_SCOPE.txt')==scope['scope_sha256']
    days=['2022-06-01'];sm={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};im={r['series']:r for r in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
    rulepath=M/'research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json';rules=read(rulepath)
    opp=read(O/'2022_2024_INCREMENTAL_OPPORTUNITIES.json');rows=read(O/'2022_2024_ALL_PAUSED_ROWS.json');by={r['day']:r for r in rows};cand={d:[r for r in opp[d]if'mobile'in r['roles']and not r['non_ACT_barriers']]for d in days}
    rec=pd.read_csv(W/'mainline-absolute-Q4-20261031/recovery.csv',index_col=0,parse_dates=True);calendar=rec.index
    src=[]
    for d in days:
        for q in cand[d]:
            m=sm[q['sid']];p=Path(m['refs']['facts']);src.append(p)
            raw=next(Path(k)for k in m['source_sha256']if k.endswith('/signal.parquet'));src.append(raw)
            src.append(Path(im[q['sector']]['refs']['state']));src.append(Path(m['refs']['CP1']))
            cr=W/'2022-normal-reference-20261031/inputs/stock-receipts'/f"{m['symbol']}.json"if d[:4]=='2022'else W/'recovery-2023-readiness-20261101/inputs/stock-receipts'/f"{q['sid']}.json"if d[:4]=='2023'else ROOT/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/stock-receipts'/f"{q['sid']}.json"
            src.append(cr)
    ledger=M/'research_rounds/rs-h1-execution-20261025/code/sector_account.py';src.append(ledger)
    for p in sorted(set(src)):
        if p.exists():SRC[str(p.resolve())]=sha(p)
    SRC[str(Path(__file__))]=sha(__file__)
    save('MINIMUM_UNIT_INPUT_FREEZE.json',dict(before_probe_necessary_condition_numerics=True,sources=dict(SRC),candidate_counts={d:len(cand[d])for d in days}))
    sys.path.insert(0,str(ledger.parent));import sector_account as L
    result=[]
    for d in days:
        nav=D(by[d]['old_NAV']);cash=D(by[d]['old_available']);nd=str(calendar[calendar.get_loc(pd.Timestamp(d))+1].date());tested=[]
        for q in sorted(cand[d],key=lambda r:(r['original_rank'],r['sid'])):
            sid=q['sid'];m=sm[sid];sec=q['sector'];bad=[];r=dict(day=d,next_OPEN_day=nd,sid=sid,sector=sec,original_rank=q['original_rank'],CP1_id=q['CP1_id'],old_NAV=nav,old_available=cash,unknown=None)
            try:
                fp=Path(m['refs']['facts']);rp=next(Path(k)for k in m['source_sha256']if k.endswith('/signal.parquet'));sp=Path(im[sec]['refs']['state']);cp=Path(m['refs']['CP1'])
                if sid not in FR:
                    assert sha(fp)==m['output_sha256'][str(fp)]and sha(rp)==m['source_sha256'][str(rp)]
                    FR[sid]=(pd.read_parquet(fp),pd.read_parquet(rp),pd.read_parquet(cp))
                fact,raw,cps=FR[sid];a=fact.loc[pd.Timestamp(d)];op=raw.loc[pd.Timestamp(nd)];z=cps.loc[pd.Timestamp(d)]
                assert bool(z.receipt)and bool(a.i_target)
                canon=W/'2022-normal-reference-20261031/inputs/stock-receipts'/f"{m['symbol']}.json"if d[:4]=='2022'else W/'recovery-2023-readiness-20261101/inputs/stock-receipts'/f'{sid}.json'if d[:4]=='2023'else ROOT/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/stock-receipts'/f'{sid}.json'
                cc=read(canon);match=[x for x in cc if x['confirmed_day']==d and x['receipt_id']==q['CP1_id']];assert len(match)==1
                if sec not in ST:
                    f=pd.read_parquet(sp);f.index=pd.to_datetime(f.day);ST[sec]=f
                s=ST[sec].loc[pd.Timestamp(d)]
                if not bool(s.E0_valid)or pd.isna(s.attempt_id)or int(s.stage)<1:bad.append('industry_not_active_attempt')
                if not bool(op.observed_bar)or bool(op.synthetic_event_bar):bad.append('next_OPEN_not_original_observed_bar')
                qr=L.QuantityRule(**version(rules['quantity_versions'][sid],nd)['rule']);qty=qr.buy_minimum
                venue=version(rules['venue_versions'][sid],nd)['venue'];fs=version(rules['fee_versions'][venue],nd)['schedule'];fee=L.FeeSchedule(fs['schedule_id'],tuple(L.FeeComponent(**x)for x in fs['components']))
                factor=D(str(fact.loc[pd.Timestamp(nd),'factor']));rawopen=D(str(op.raw_open));price=rawopen*D('1.0005');flooradj=max(D(str(a.i_floor)),D(str(z.candidate)));floor=flooradj/factor
                par=D(rules['security_metadata'][sid]['par_value']);gross=D(qty)*price;fee0=sum(fee.incremental('buy',gross,{},{},1,shares=qty,par_value=par).values(),D(0));bnav=nav-fee0;risk=D(qty)*max(D(0),price-floor)
                cap=qr.buy_floor(int(nav*D('.02')/D(str(a.raw_close))))
                if rawopen<=floor or not(D(0)<=floor<=price):bad.append('OPEN_at_or_below_original_mobile_protection')
                if qty>cap or gross>nav*D('.02'):bad.append('minimum_exceeds_original_mobile2pct_target')
                if gross+fee0>cash-nav*D('.1'):bad.append('cash_or_original10pct_reserve')
                if gross>D('.1')*bnav:bad.append('probe10pct_capital')
                if gross>D('.02')*bnav:bad.append('sector_probe2pct_capital')
                if risk>D('.005')*bnav:bad.append('probe_halfpct_risk')
                if risk>D('.01')*bnav:bad.append('sector1pct_risk')
                if gross>D('.1')*nav:bad.append('stock10pct_capital')
                r.update(minimum_quantity=qty,unit_rule=qr.rule_id,fee_schedule=fee.schedule_id,raw_OPEN=rawopen,adverse_price=price,factor_at_OPEN=factor,
                  original_mobile_floor_adjusted=flooradj,floor_raw=floor,minimum_gross=gross,minimum_buy_fee=fee0,minimum_cash=gross+fee0,minimum_nominal_risk=risk,
                  original_mobile_max_shares=cap,original_mobile_nominal_budget=nav*D('.02'),industry_original_stage=int(s.stage),industry_original_attempt=str(s.attempt_id),
                  necessary_condition_failures=bad,passes_single_probe_necessary_conditions=not bad)
            except (KeyError,ValueError,AssertionError,StopIteration)as e:r.update(unknown=repr(e),passes_single_probe_necessary_conditions=False,necessary_condition_failures=['source_or_identity_unknown'])
            tested.append(r)
        passes=[r for r in tested if r['passes_single_probe_necessary_conditions']]
        result.append(dict(day=d,candidates=len(tested),passing_individual_minimum_probe_orders=len(passes),unknown=sum(r['unknown']is not None for r in tested),
          failure_presence=dict(Counter(k for r in tested for k in r.get('necessary_condition_failures',[]))),
          passing_minimum_cash_range=[min(r['minimum_cash']for r in passes),max(r['minimum_cash']for r in passes)]if passes else None,
          passing_nominal_risk_range=[min(r['minimum_nominal_risk']for r in passes),max(r['minimum_nominal_risk']for r in passes)]if passes else None,
          examples_first3_by_original_rank=passes[:3],all_rows=tested))
        print('A_MIN',d,'candidate',len(tested),'pass',len(passes),'unknown',result[-1]['unknown'],flush=True)
    for p,h in SRC.items():assert sha(p)==h
    save('MINIMUM_UNIT_RESULTS.json',dict(results=result,new_account_constructions=0,new_S0=0,new_orders=0,new_strategy_events=0,
      scope='single original flat-reference probe necessary conditions only; no aggregate routing/fill or candidate future path',source_sha256=SRC))
if __name__=='__main__':main()
