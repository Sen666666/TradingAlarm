"""Synthetic CLOSE old-factor request to exact known cash-event OPEN bridge."""
from pathlib import Path
import copy
import importlib.util
import json
import os
import sys
P=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('bridge_branch_engine',P/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
f=e.frozen;D=e.D;pd=e.pd
t=f.module('bridge_synthetic_fixture',e.FROZEN/'synthetic_tests.py')
t.CAL=pd.bdate_range('2024-10-01',periods=45);t.dt,t.nxt,t.later=t.CAL[7:10]
CHECKS=[]
def check(n,v=True):assert v,n;CHECKS.append(n)
def main():
    ev=e.read(e.ADAPTER)[0];sid=ev['sid'];old=D(ev['factor_old']);new=D(ev['factor_new'])
    for binding in [False,True]:
        tag='WAIT' if binding else 'FILL'
        x=t.setup(cls=e.Engine);data=x.d
        data.ids.append(sid);data.names[sid]=sid;data.sid_sector[sid]='A';data.stock[sid]=1;data.cap[sid]=pd.Series(100000,index=t.CAL)
        for day,fac,op,close in [(t.dt,old,117.18,118.11),(t.nxt,new,115.5,106.55)]:
            data.prices[(sid,day)]=dict(raw_open=op,raw_close=close,close=float(D(str(close))*fac),adjustment_factor=float(fac))
        data.events[(sid,t.nxt)]=copy.deepcopy(ev);data.actions[(sid,t.nxt)]=[dict(effective_date='2024-10-11',cash_per_old_share='.23',split_ratio='1')]
        if binding:
            t.hold(x,qty=110000);x.cash=D(20000);data.main_rows[('old',t.dt)]={'M':0,'E':0,'W':True}
        r=t.seed(sid,when=t.dt,nav=D(1200000));r.update(factor=old,signal_day='2024-09-26',planned_q=200)
        ident=f.request_id(r) # stable request identity, factor does not enter it
        ticket=f.rules.ticket_from_seed(r,D(30000),{'cash_reserve':D(0),'attempt_budget':D(100000)})
        assert ticket is not None
        ticket['last_verified_day']='2024-10-10';x.tickets[sid]=ticket;r['ticket_id']=ticket['ticket_id']
        rows=t.planned(x,[r]);ident=f.request_id(rows[0]);book=f.digest(x.funding_book);original_identity=f.rules.immutable_identity(ticket)
        before_cash=x.cash;x.register_pay(t.dt);x.economic_preflight(t.nxt,rows);x.accrue(t.nxt)
        check(tag+'_native_bridge_zero_cash',x.cash==before_cash and x.receivable==0 and not x.claims)
        check(tag+'_live_ticket_factor_updated',ticket['current_factor']==new and ticket['original_factor']==old)
        check(tag+'_frozen_book_not_rewritten_by_bridge',book==f.digest(x.funding_book))
        common,_,_=x.conditional_prefix(t.nxt)
        full=x.funding_book['branches'][0];shadow=x.funding_book['branches'][-1]
        full_state=f.scratch(common);installed=full_state.install(full,rows)
        check(tag+'_install_does_not_restore_old_live_factor',full_state.tickets[sid]['current_factor']==new)
        check(tag+'_installed_original_factor_is_passive',installed and installed[0]['factor']==old and f.request_id(installed[0])==ident)
        nav=full_state.nav(t.nxt,'raw_open');sv={s:full_state.qvalue(a,t.nxt,'raw_open') for s,a in full_state.active.items()}
        native=f.base.Engine.noncash(full_state,installed[0],t.nxt,'raw_open',nav,sv)
        check(tag+'_native_noncash_uses_current_quote_factor',native['reason']=='PASS')
        shadow_state=f.scratch(common);shadow_rows=shadow_state.install(shadow,rows)
        check(tag+'_shadow_same_bridge_cash_and_ticket',shadow_state.cash==full_state.cash and shadow_state.tickets[sid]['current_factor']==new and not shadow_rows)
        decision=x.select_open(t.nxt,rows);x.execute_selected(t.nxt,rows,decision)
        check(tag+'_ticket_not_reborn',x.tickets[sid]['ticket_id']==ticket['ticket_id'] and f.rules.immutable_identity(x.tickets[sid])==original_identity)
        check(tag+'_no_dividend_or_claim_created',x.receivable==0 and not x.claims and all(a['dividend']==0 for a in x.archive.values()))
        if binding:
            check('WAIT_same_retained_ticket_no_order',x.tickets[sid]['status']=='RETAINED' and sid not in x.active and not any(o['sid']==sid for o in x.orders))
        else:
            check('FILL_original_ticket_consumed_once',x.tickets[sid]['status']=='CONSUMED' and sum(o['sid']==sid for o in x.orders)==1)
            check('FILL_new_round_uses_current_factor',x.active[sid]['factor']==new)
    result=dict(result='PASS',assertions=len(CHECKS),checks=CHECKS,history_run=False,real_Data_constructed=False,engine_sha256=e.sha(P/'engine.py'),tests_sha256=e.sha(P/'bridge_branch_tests.py'))
    e.save(Path(os.environ.get('QA_RESULT_PATH',P/'BRIDGE_BRANCH_QA.json')),result);print(json.dumps(result))
if __name__=='__main__':main()
