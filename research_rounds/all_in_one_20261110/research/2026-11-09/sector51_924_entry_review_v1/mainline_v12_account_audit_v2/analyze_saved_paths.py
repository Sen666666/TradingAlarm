"""Independent actual-money, fixed-cohort and focused protection paths at any frontier."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import accounting_core as au
Z=D(0);ANCHOR='2024-11-06'
FOCUS={'600779.SH','300085.SZ','000158.SZ'}

def analyze(candidate,end,out,summary,br,ar):
    out=Path(out);au.O=out;paths={'M12':Path(candidate),'M7':au.BASE};records={};at={};divrows=[];daily=[];role=Counter();focusdaily=[];focuslots=[];focusoutcomes=[]
    rules=au.read(au.RULES);proxies=au.read(au.PROTOCOL)['approved_proxy_ids']
    for label,path in paths.items():
        os=[x for x in au.read(path/'ORDERS.json') if x['day']<=end];hs=[x for x in au.read(path/'HOLDINGS.json') if x['day']<=end];eq=[x for x in au.read(path/'EQUITY_EVENTS.json') if x['day']<=end];ls=[x for x in au.read(path/'DAY_LEDGER.json') if x['day']<=end]
        seeds={x['round_id']:x for x in os if x['side']=='BUY_SEED'};keys={k:x['sid']+'|'+x['signal_day'] for k,x in seeds.items()};buys={x['lot_id']:x for x in os if x['side'].startswith('BUY')};capital=[x for x in au.read(path/'CAPITAL_LOTS.json') if x['day']<=end]
        records[label]=dict(orders=os,holds=hs,equity=eq,ledger=ls,seeds=seeds,keys=keys)
        for x in buys.values():assert x['capital_role']==('INITIAL' if x['side']=='BUY_SEED' and x.get('allocation_phase') in ('EVENT','RESIDUAL') else 'EXPANSION');role[label+'_buy_checks']+=1
        for x in capital:assert x['capital_role']==buys[x['lot_id']]['capital_role'];role[label+'_lot_role_checks']+=1
        terms=au.cash_event_terms(path)
        for e in au.read(path/'EVENT_ADMISSION.json'):
            sid,ex=e['sid'],e['ex_date']
            if not '2024-09-02'<=ex<=end:continue
            t=terms[sid,ex];q=sum(x['qty'] for x in hs if x['sid']==sid and x['day']==t['record_date']);expected=D(q)*D(t['d_cash'])*D('.8')
            accr=[x for x in eq if x['sid']==sid and x['day']==ex and x['event']=='ACCRUE_NET80'];paid=[x for x in eq if x['sid']==sid and x['day']==t['pay_date'] and x['event']=='PAY_CLOSE_NET80']
            au.near(au.sm(accr,'receivable_delta'),expected,'admitted_cash_entitlement');assert sum(x['record_qty'] for x in accr)==q
            if t['pay_date']<=end:au.near(au.sm(paid,'cash_delta'),expected,'admitted_cash_payment')
            if sid=='688200.SH' and ex=='2024-10-11':assert label=='M12' and q==0 and expected==0
            divrows.append(dict(account=label,sid=sid,ex_date=ex,record_date=t['record_date'],qty=q,expected_NET80=expected,accrued=au.sm(accr,'receivable_delta'),paid=au.sm(paid,'cash_delta')))
        ob=au.bykey(os,'day');hb=au.bykey(hs,'day');eb=au.bykey(eq,'day');cf=defaultdict(lambda:Z);div=defaultdict(lambda:Z);peak={};refs=au.bykey([x for x in au.read(path/'REFERENCE_DAILY.json') if x['day']<=end],'day')
        for l in ls:
            day=l['day']
            for x in ob[day]:cf[keys[x['round_id']]]+=D(x['cash_delta'])
            for x in eb[day]:
                if D(x.get('receivable_delta',0))>0:div[keys[x['round_id']]]+=D(x['receivable_delta'])
            rr={k:v+div[k] for k,v in cf.items()}
            for x in hb[day]:k=keys[x['round_id']];rr[k]=rr.get(k,Z)+D(x['market_value'])
            au.near(sum(rr.values(),Z),D(l['NAV'])-D(1200000),'daily_round_NAV')
            at[label,day]=rr
            oo=ob[day];daily.append(dict(account=label,day=day,cash=l['cash'],NAV=l['NAV'],weight_pct=l['weight_pct'],fees_paid=l['fees_paid'],original_D_total=au.sm(refs[day],'D'),all_buy_cost=-au.sm([x for x in oo if x['side'].startswith('BUY')],'cash_delta'),ADD_buy_cost=-au.sm([x for x in oo if x['side']=='BUY_ADD'],'cash_delta'),funding_net=au.sm([x for x in oo if x.get('transfer_rank') is not None],'cash_delta'),new_MATURE=sum(x['side']=='BUY_SEED' and x.get('allocation_phase')=='MATURE' for x in oo)))
            for rid,seed in seeds.items():
                if seed['sid'] not in FOCUS or seed['signal_day']!='2024-09-23' or seed['day']>day:continue
                sid=seed['sid'];k=keys[rid];hh=[x for x in hb[day] if x['round_id']==rid];q=sum(x['qty'] for x in hh)
                raw=D(hh[0]['raw_mark']) if q else None;fee=au.fee_calc(rules,proxies,sid,day,q,raw*D('.9995'),'sell') if q else Z
                net=cf[k]+div[k]+(q*raw*D('.9995')-fee if q else Z)
                for x in capital:
                    if x['round_id']==rid and x['day']==day:au.near(net,x['round_net'],'focused_saved_round_net')
                if k not in peak or net>peak[k][0]:peak[k]=(net,day)
                focusdaily.append(dict(account=label,name=seed['name'],sid=sid,opportunity_key=k,round_id=rid,day=day,qty=q,actual_trade_cashflow=cf[k],dividend=div[k],marked_net_PnL=rr[k],close_net_liquidation_PnL=net,close_MFE=peak[k][0],close_MFE_day=peak[k][1],close_peak_giveback=peak[k][0]-net,is_realized_closed_round=q==0,not_intraday_MFE=True))
                if day in {'2024-10-08','2024-10-10',end}:
                    for h in hh:
                        fl=D(h['protection_signal'])/D(h['factor']);p=fl*D('.9995')
                        focuslots.append(dict(account=label,name=seed['name'],day=day,lot_id=h['lot_id'],kind=h['kind'],qty=h['qty'],bought=h['bought'],cp_id=h['cp_id'],locked_exit=h['locked_exit'],raw_protection_price=fl,raw_close=raw,whole_round_hypothetical_if_all_remaining_sold_at_this_price=cf[k]+div[k]+q*p-au.fee_calc(rules,proxies,sid,day,q,p,'sell'),hypothetical_not_guaranteed=True))
        for rid,seed in seeds.items():
            if seed['sid'] not in FOCUS or seed['signal_day']!='2024-09-23':continue
            ds=[x for x in focusdaily if x['account']==label and x['round_id']==rid];last=ds[-1];after=[x for x in os if x['round_id']==rid and x['day']>'2024-10-10']
            old=[x for x in hs if x['round_id']==rid and x['day']=='2024-10-10']
            lotresults=[]
            for h in old:
                sales=[x for x in after if x['side'].startswith('SELL') and (x.get('lot_id')==h['lot_id'] or h['lot_id'] in x.get('lots',[]))]
                lotresults.append(dict(lot_id=h['lot_id'],qty_at_Oct10=h['qty'],locked_exit_at_Oct10=h['locked_exit'],actual_later_sell_orders=sales,exact_per_lot_cash_allocation_not_invented=True))
            focusoutcomes.append(dict(account=label,name=seed['name'],opportunity_key=keys[rid],at_certified_end=last,actual_orders_after_Oct10=after,Oct10_lot_actual_exit_evidence=lotresults,closed=last['qty']==0,realized_final_PnL=last['close_net_liquidation_PnL'] if last['qty']==0 else None,warning='Actual subsequent orders, not a counterfactual floor-price guarantee. Multi-lot sale cash is not artificially apportioned.'))
    au.save('ALL_ADMITTED_DIVIDEND_RECHECK',divrows);au.save('CAPITAL_ROLE_AUDIT',dict(role));au.save('DAILY_CASH_DEMAND_EXPOSURE',daily)
    au.save('FOCUSED_DAILY_CLOSE_MFE',focusdaily);au.save('FOCUSED_LOT_PROTECTION',focuslots);au.save('FOCUSED_ACTUAL_OUTCOMES',focusoutcomes)
    segment=dict(available=False,required_anchor=ANCHOR,certified_end=end)
    if end>=ANCHOR and all((label,ANCHOR) in at for label in paths):
        segment=dict(available=True,anchor=ANCHOR,end=end)
        for label,rec in records.items():
            l={x['day']:x for x in rec['ledger']};old={k for rid,k in rec['keys'].items() if rec['seeds'][rid]['day']<=ANCHOR};new=set(rec['keys'].values())-old
            oldnet=sum((at[label,end].get(k,Z)-at[label,ANCHOR].get(k,Z) for k in old),Z);newnet=sum((at[label,end].get(k,Z) for k in new),Z);pnl=D(l[end]['NAV'])-D(l[ANCHOR]['NAV'])
            au.near(oldnet+newnet,pnl,'Nov6_old_plus_new')
            segment[label]=dict(anchor_NAV=l[ANCHOR]['NAV'],end_NAV=l[end]['NAV'],actual_total_PnL_after_Nov6=pnl,old_round_increment=oldnet,new_round_actual_PnL=newnet,new_round_count=len(new),late_fees=D(l[end]['fees_paid'])-D(l[ANCHOR]['fees_paid']))
        segment['late_actual_PnL_improvement']=segment['M12']['actual_total_PnL_after_Nov6']-segment['M7']['actual_total_PnL_after_Nov6']
        au.near(D(segment['M12']['anchor_NAV'])-D(segment['M7']['anchor_NAV'])+segment['late_actual_PnL_improvement'],summary['delta']['NAV'],'Nov6_lead_closure')
        if end=='2025-01-20':au.near(segment['M7']['actual_total_PnL_after_Nov6'],'-204229.2637350250050','frozen_M7_late')
    au.save('NOV6_ACTUAL_ACCOUNT_SEGMENT',segment)
    b={x['opportunity_key']:x for x in br};c={x['opportunity_key']:x for x in ar};matched=set(b)&set(c);miss=set(b)-set(c);new=set(c)-set(b)
    attribution=dict(matched_actual_path_delta=sum((D(c[k]['marked_net_pnl'])-D(b[k]['marked_net_pnl']) for k in matched),Z),unmatched_baseline_reference_only=sum((D(b[k]['marked_net_pnl']) for k in miss),Z),new_candidate_actual_PnL=sum((D(c[k]['marked_net_pnl']) for k in new),Z),warning='Unfilled baseline losses are not candidate earned profit.')
    au.near(attribution['matched_actual_path_delta']-attribution['unmatched_baseline_reference_only']+attribution['new_candidate_actual_PnL'],summary['delta']['NAV'],'identity_money_closure')
    au.save('ACTUAL_ACCOUNT_ATTRIBUTION',attribution)
    summary['nov6_actual_account_segment']=segment;summary['all_admitted_cash_checks']=dict(total=len(divrows),by_account=dict(Counter(x['account'] for x in divrows)),not_hardcoded_534=True);summary['actual_account_attribution']=attribution
    return summary
