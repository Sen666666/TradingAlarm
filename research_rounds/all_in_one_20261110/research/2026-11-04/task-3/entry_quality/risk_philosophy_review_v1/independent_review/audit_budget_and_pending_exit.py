"""Read source AST and original book only. No import of models or account code."""
from pathlib import Path
from decimal import Decimal as D
import ast,gzip,hashlib,json,signal,time
O=Path(__file__).resolve().parent;E=O.parent.parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');T=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
J=W/'case-stage-ledger-20261031/v3/joint_v3.py';V=W/'case-stage-ledger-20261031/budget_v3/model.py';N=W/'account-risk-ablation-20261031/model_without_account_check.py';C=T/'pvr_pool_feasibility/component.py';NA=T/'pvr_pool_feasibility/native_adapter.py'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fn(p,cls,name):
 z=ast.parse(Path(p).read_text());c=next(x for x in z.body if isinstance(x,ast.ClassDef)and x.name==cls);return next(x for x in c.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))and x.name==name)
def source(p,cls,name):return ast.get_source_segment(Path(p).read_text(),fn(p,cls,name))
def main():
 started=time.monotonic();signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('pure read60s')));signal.setitimer(signal.ITIMER_REAL,60)
 O.mkdir(exist_ok=True);js=J.read_text();ns=NA.read_text();cs=C.read_text();rs=(W/'account-risk-ablation-20261031/route_without_account_check.py').read_text()
 assert "shared_loss_budget=20000,exhausted_policy='record_only'"in source(J,'Budget','__init__')
 assert 'request=P.MOD.Contract.request'in ns and 'route=P.ROUTES[True]'in ns and 'return P.MOD.Contract.migrate(self,sector) if self.expand else False'in ns
 for method in ['loss','resources','start']:
  assert ast.dump(fn(V,'Contract',method),include_attributes=False)==ast.dump(fn(N,'Contract',method),include_attributes=False)
 assert "if self.exhausted_policy != 'record_only'"in source(V,'Contract','loss') and "if self.exhausted_policy != 'record_only'"in source(N,'Contract','request')
 assert "NEW_MODEL=MODEL.replace(MG,'').replace(PG,PN)"in cs and 'NEW_ROUTE=ROUTE.replace(RG,RN)'in cs
 opening=source(J,'Runner','opening');assert opening.index('for sid in sorted(a.exits)')<opening.index('a.settle_due(at);a.sync(at);funded=[];done=set()')<opening.index('for i in sorted(')<opening.index('self.route(a,i,x,at)')<opening.index('for sid,i,x,q in funded:')
 assert 'if sid in done or sid in a.buys or sid in a.exits:continue'in opening
 assert "if sid in a.exits:why.append('exit_pending')"in source(J,'Runner','planning')
 p=E/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair/B.json.gz'
 with gzip.open(p,'rt')as f:b=json.load(f)
 buy=next(x for x in b['trades']if x.get('layer')==1963);sell=next(x for x in b['trades']if any(z['layer']==1963 for z in x.get('parts',[])))
 assert buy['side']=='buy'and buy['shares']==300 and buy['price']=='49.874925'and buy['at'][:10]=='2024-10-10'
 assert sell['shares']==300 and sell['price']=='30.194895'and sell['at'][:10]=='2024-10-11'and sell['parts'][0]['reason']=='CP1_add_protection'
 assert next(x for x in b['layers']if x['id']==1963)['qty']==0
 audit=[x for x in b['audit']if x.get('sid')=='300085.SZ'and str(x.get('at',''))[:10]in['2024-10-10','2024-10-11']]
 assert any(x['kind']=='pilot_layer_exit'and x['layers']==[1963]and x['at'][:10]=='2024-10-10'for x in audit)
 dp=E/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair/daily.jsonl.gz'
 with gzip.open(dp,'rt')as f:daily=next(json.loads(l)for l in f if '2024-10-10 15:10:00' in l)
 layer=next(x for x in daily['layers']if x['id']==1963);assert layer['qty']==300 and '300085.SZ'in daily['pending_sells']
 fp=E/'entry_exit_scale/decision_features/2022_2024_ROWS.json';feat=next(x for x in json.loads(fp.read_text())if x['layer']==1963)
 floor=D(layer['floor'])/D(feat['fill_factor']);close=D('37.76');assert floor>close
 risk=D(300)*max(D(0),close-floor);capital=D(300)*close;assert risk==0 and capital==D('11328')
 net=D(sell['gross_cny'])-D(sell['fees_cny'])-D(buy['gross_cny'])-D(buy['fees_cny']);assert net==D('-5920.0779768886000')
 day='2024-10-11';sellidx=[i for i,x in enumerate(b['trades'])if x['side']=='sell'and x['at'][:10]==day];buyidx=[i for i,x in enumerate(b['trades'])if x['side']=='buy'and x['at'][:10]==day];assert sellidx and buyidx and max(sellidx)<min(buyidx)
 assert not any(x['side']=='buy'and x['security_id']=='300085.SZ'and x['at'][:10]==day for x in b['trades'])
 paths=[J,V,N,C,NA,W/'account-risk-ablation-20261031/adapter.py',W/'account-risk-ablation-20261031/route_without_account_check.py',E/'trend_exit_controls_v1/load_inputs.py',RR/'lot-risk-allocation-20261029/code/study.py',RR/'rs-h1-execution-20261025/code/sector_account.py',p,dp,fp,Path(__file__)]
 z=dict(status='PASS_READ_ONLY_ACTUAL_NO60_BUDGET_AND_PENDING_EXIT_WITH_LIMITS',budget=dict(initial_shared_loss_budget=20000,exhausted_policy='record_only',loss_definition='Each actual buy fee plus each sold part gross negative (split-adjusted unit cost minus actual sell execution, floored0) plus its allocated actual sell fee. Positive gross realized gains do not offset this ledger.',loss_identity='losses[(sector,original_episode)] retained; shared_loss=sum(all entries), no reset by attempt promotion or episode replacement.',disabled_by_record_only=['loss(): budget-exhaustion pending-order cancellation branch','request(): shared_loss_exhausted rejection branch'],ACT='Independent ACT20_BREAK current NAV/peak episode rule, not this cumulative gross-loss ledger.'),
  actual_no60_wiring=dict(request='NoConfirmed60Budget.request = P.MOD.Contract.request',migrate='NoConfirmed60Budget.migrate -> P.MOD.Contract.migrate if expand',route='Runner.route = P.ROUTES[True]',model_derivation='Original no-account-check Contract; only confirmed60 migration/request/route predicates removed. loss/resources/start unchanged original methods.',constructor='NoConfirmed60Budget inherits NoAccountBudget -> J.Budget; constructor remains J.Budget20000/record_only',account_and_opening='Original J.Account and J.Runner.opening asserted by actual adapter; no replacement ledger.'),
  pending_responsibility=dict(lots='Exit requests do not remove qty from J.sync/budget.lots; live marked capital remains until actual fill callback changes inventory.',orders='open and cancel_pending positive quantities keep gross+fee reserve and capital/risk until actual cancel acknowledgement.',cash='Zero mark-to-floor risk is not a cash refund; native actual available+reserved and receivable domains remain reconciled.',same_stock='planning exit_pending blocks intent; opening skips remaining exits/buys and per-opening done stock. done is not claimed to be a permanent whole-day or post-exit future-signal ban.'),
  yinzhijie=dict(layer=1963,sid='300085.SZ',buy=buy,sell=sell,request_audit=audit,raw_floor=str(floor),Oct10_CLOSE_raw=str(close),Oct10_qty=300,Oct10_marked_capital=str(capital),Oct10_mark_to_floor_proxy=str(risk),Oct10_pending_CP=True,Oct10_ACT_on=daily['on'],Oct10_shared_grossloss=daily['shared_loss'],actual_terminal_net=str(net),Oct11_all_sell_trade_records=len(sellidx),Oct11_all_buy_trade_records=len(buyidx),all_exits_before_all_buys_in_original_book=True,no_same_stock_Oct11_buy=True),
  conclusion='This case proves executable next-OPEN gap loss beyond a mark-to-floor proxy, not reuse of unexited principal for new purchases. Its300shares are sold at Oct11OPEN before any new reservation/buy phase. Other-stock nominal-risk room from a breached-line position is a code possibility only under remaining probe/sector/cash/capital/ACT gates; this audit does not establish actual use or amount.',
  source_sha256={str(p.resolve()):sha(p)for p in paths},new_models=0,new_accounts=0,new_backtests=0,new_shadow_projections=0,new_counterfactuals=0,elapsed_seconds=time.monotonic()-started,remaining_blocks=[],limits=['Only original source/AST and the specified actual case read; no cross-stock atomic reallocation search or hypothetical projection.','Raw floor uses the prior independently audited original decision-feature factor joined to original book adjusted floor; no market/indicator recomputation.','No claim that a nominal proxy bounds gap loss, guarantees stop execution, or establishes actual excess-risk admission.'])
 out=O/'BUDGET_AND_PENDING_EXIT_AUDIT.json';out.write_text(json.dumps(z,ensure_ascii=False,indent=2)+'\n')
 (O/'READOUT.txt').write_text('No60 的 shared_loss_budget=20000、exhausted_policy=record_only 是累计损耗记账，不是2万元硬停。实际 request/migrate/route 已核，不只读未启用模型。gross负损与买卖费按行业/原episode累计，正收益不冲抵；record_only 同时跳过耗尽撤单和新请求拒绝，ACT20为另一套规则。\n\n银之杰1963：Oct10买300@49.874925；当日收盘37.76低于已知保护线约41.023422，CP退出待执行，名义mark-to-floor风险0，但300股/11328元市值仍入资本与真实NAV。Oct11先全部卖300@30.194895，再进入其他新reserve/buy；原账同日也没有该股新买。损失5920.08元证明跳空与执行尺度不能由名义保护距离保证，不证明未退出本金被风险0腾挪重用。\n\n退出请求不删除旧仓；open/cancel_pending买单在ack前不释放原reserve。same-stock exit_pending与每次opening done是实际屏障，done不是永久全日封禁。跨股风险额度重用仅为源码可能，实际用途未审，不可把本例当资金挤占或超额风险证据。本审0模型/0账户/0回测/0shadow投影。\n')
 signal.setitimer(signal.ITIMER_REAL,0);print(z['status'],round(z['elapsed_seconds'],3),sha(out))
if __name__=='__main__':main()
