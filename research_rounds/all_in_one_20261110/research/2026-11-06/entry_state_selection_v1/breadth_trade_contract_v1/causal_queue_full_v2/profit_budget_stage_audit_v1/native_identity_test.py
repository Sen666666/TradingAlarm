import importlib.util,sys,json,hashlib
from pathlib import Path
from datetime import date
P=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/budget_v3/model.py')
sp=importlib.util.spec_from_file_location('native_budget_identity_test',P);M=importlib.util.module_from_spec(sp);sys.modules[sp.name]=M;sp.loader.exec_module(M)
sec='URFI881121';ep='1f87f9fa300e427ed46d5a815ded2de4e20156d358f97cabeecc29196f793d59';r16='2eed8214ae23c351ce37266ff3575cef11e145605d0354ec2413931dbf0e605a';attempt=ep+':'+r16
def n(s):return date.fromisoformat(s).toordinal()
lots=[M.Lot('breadth_hu','688126.SH',sec,ep,'probe',302,34.567275,29.59,'core','BREADTH_2026_06_11'),M.Lot('breadth_li','605358.SH',sec,ep,'probe',100,73.946955,66.1,'core','BREADTH_2026_06_11')]
cash=1182154.8442897955;prices={'688126.SH':36.18,'605358.SH':77.}
b=M.Contract(nav=cash+18626.36,cash=cash,prices=prices,lots=lots);b.sectors[sec]=M.Sector(ep,n('2026-06-16'),level=1,status='confirmed',active=True,attempt=attempt,episode_started=n('2026-06-11'))
pre=(b.cash,b.nav,b.resources(),[(x.batch,x.attempt,x.pool)for x in b.lots]);r=b.migrate(sec);post=(b.cash,b.nav,b.resources(),[(x.batch,x.attempt,x.pool)for x in b.lots]);assert pre==post and r
tok=M.Evidence('6121e1c3ea9aab2fcf39a0bb119420c1177667b3b3753013a7918c932bb08f26',sec,'stock_cp1','21',n('2026-06-12'),n('2026-06-26'),n('2026-06-26'),ep,'605358.SH',attempt)
assert b.valid(tok,'stock_cp1',n('2026-06-26'))
res=b.request('new_li_add','605358.SH',sec,100,77.0385,66.1,tok,n('2026-06-26'),5.493816785/100,probe_request=False,role='mobile',order_expiry_bar=n('2026-06-29'))
print(json.dumps(dict(source_sha256=hashlib.sha256(P.read_bytes()).hexdigest(),migration_return=r,old_lots_unchanged=pre==post,old_lots=[(x.batch,x.attempt,x.pool)for x in b.lots],new_mobile_request=res,new_order=vars(b.orders['new_li_add']),resources=b.resources(),no_fills=True,native_Account_initializations=0),ensure_ascii=False,indent=2))
