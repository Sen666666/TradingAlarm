"""PVR rotation, one predeclared mechanism, frozen ACT20 ledger and facts."""
from pathlib import Path
import sys,json,hashlib,copy,csv,inspect,textwrap
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1]
PREVIOUS=ROOT/'research_rounds/pvr-act-comparison-20261027'
sys.path.insert(0,str(PREVIOUS/'code'))
import experiment as P
E=P.E;R=P.R;C=P.C;A=P.A
pd=P.pd;np=P.np
from dataclasses import replace
from decimal import Decimal as D
from bisect import bisect_right
from datetime import timedelta
ZERO=D(0)
ENABLED=False;PAIRED_BPS=None

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(E.native.encoded(d),f,ensure_ascii=False,indent=2,allow_nan=False)

def choose(new_score,old_scores):
 """Scores are frozen to the existing 12-decimal ordering interface."""
 if new_score is None or not np.isfinite(new_score) or new_score<=50:return None
 ids=[(s,k) for k,s in old_scores.items() if s is not None and np.isfinite(s) and new_score-s>=15]
 return min(ids)[1] if ids else None

class Account(E.Account):
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs);self.rotation_enabled=ENABLED;self.paired_bps=PAIRED_BPS
 def reserve_pair(self,z,at):
  ctx=self.swap_context;sid=z['candidate'];q=self.market.quote(sid,at)
  if q is None:return False,'unknown_quote'
  cap=converted_cap(self,sid,ctx,at)
  clock=E.admission.Clock(at,at+timedelta(seconds=1),at.date())
  ok,oid=E.ledger.SectorAccount.reserve_budget(self,quote=q,clock=clock,gross_budget_cny=D(z['budget']),target_shares_cap=cap,candidate_id=z['id'])
  if ok:
   self.intents[oid]=dict(sid=sid,decision_at=ctx['signal_at'],funded_at=at,floor_signal=ctx['support'],risk_budget=ctx['nav']*D('.01'),nav=ctx['nav'],budget=self.buys[sid].budget_cny)
   self.log('entry_contract',at,order_id=oid,mode=self.mode,**self.intents[oid]);self.counts['buy_orders']+=1
  return ok,oid

def converted_cap(a,sid,ctx,at):
 cap=ctx['share_cap']
 for ev in a.market.actions.get(sid,[]):
  if ctx['signal_at'].date().isoformat()<ev['effective_date']<=at.date().isoformat():cap=int(D(cap)*D(ev['split_ratio']))
 return cap

class Runner(E.Runner):
 def start_pair(self,a,at,clock,stocks,sectors):
  if not a.rotation_enabled:return
  if a.swap:
   z=a.swap
   if z['phase']=='sell' and (z['candidate'] in a.buys or a.quantity(z['candidate'])):self.stop_pair(a,at,'ordinary_buy_superseded')
   return
  if not a.risk_state['on']:return
  sd={s.security_id:s for s in stocks};ss={s.sector_id:s for s in sectors}
  eligible={sid:E.admission.eligibility(s,ss,clock,'S0') for sid,s in sd.items()}
  ids=[sid for sid,e in eligible.items() if e.q is True and not a.quantity(sid) and sid not in a.buys and sid not in a.exits]
  priority=E.admission._priority(ids,sd,ss,eligible,clock,'S0',[],'PVR_rotation');marks=self.market.marks(at,a.positions)
  for new in priority:
   a.counts['rotation_candidate_checks']+=1
   if E.projected(a,new,stocks,sectors,clock,marks) is not None:
    a.counts['rotation_normal_buy_possible']+=1;continue
   new_score=sd[new].rank.read(clock) if sd[new].rank else None;feasible={};budgets={}
   for old,pos in a.positions.items():
    if old in a.buys or old in a.exits or any(l.sellable_at>clock.earliest_execution_at for l in pos.lots):continue
    sc=sd[old].rank.read(clock) if sd[old].rank else None
    if sc is None:continue
    budget=E.projected(a,new,stocks,sectors,clock,marks,remove=old)
    if budget is not None:feasible[old]=sc;budgets[old]=budget
   old=choose(new_score,feasible)
   if old is None:
    a.counts['rotation_no_feasible_victim' if not feasible else 'rotation_score_gap_reject']+=1;continue
   q=self.market.quote(new,at);support=self.facts.floor(new,at,'I')
   cap=q.quantity.buy_floor(int(budgets[old]/q.raw_price)) if q else 0
   if not cap or support is None:continue
   a.swap_seq+=1;j=bisect_right(self.market.sessions['A'],at)
   z=dict(id=f'PVRROT:{a.swap_seq}:{at.date()}',phase='sell',candidate=new,victim=old,signal_at=at,budget=budgets[old],candidate_score=new_score,victim_score=feasible[old],score_gap=new_score-feasible[old],sell_deadline=self.market.sessions['A'][j+1].date().isoformat(),intent_valid=True)
   a.swap=z;a.swap_context=dict(signal_at=at,support=support,nav=a.current_nav,share_cap=cap)
   a.request_exit(self.market.quote(old,at),clock);a.exits[old].purpose='rotation_exit'
   a.log('rotation_started',at,rotation=dict(z));a.log('same_day_rotation_contract',at,rotation_id=z['id'],**a.swap_context);a.counts['rotation_started']+=1
   return
 def stop_pair(self,a,at,reason):
  if not a.swap:return
  z=a.swap;old,new=z['victim'],z['candidate']
  if z['phase']=='sell':
   order=a.exits.get(old)
   if order and order.purpose=='rotation_exit':
    del a.exits[old];a.log('rotation_sell_cancelled',at,sid=old,event_id=order.event_id)
  elif new in a.buys:a.cancel_buy(new)
  self.end_swap(a,at,reason)
 def valid_intent(self,sid,at):
  clock,stocks,sectors=self.facts.packet(at,'I');s=next(s for s in stocks if s.security_id==sid)
  s=replace(s,buy_allowed=self.market.market_buyable(at)[sid])
  return E.admission.eligibility(s,{s.sector_id:s for s in sectors},clock,'S0').q is True
 def close_pair(self,a,at,clock):
  if not a.swap:return
  z=a.swap
  if not a.risk_state['on']:self.stop_pair(a,at,'account_paused');return
  if not self.valid_intent(z['candidate'],at):self.stop_pair(a,at,'candidate_invalid');return
  if z['phase']=='sell' and at.date().isoformat()>=z['sell_deadline']:self.stop_pair(a,at,'sell_incomplete');return
  if z['phase']=='buy':
   sid=z['candidate']
   if sid not in a.buys:self.end_swap(a,at,'bought' if a.quantity(sid) else 'not_bought');return
   if at.date().isoformat()>=z['buy_deadline']:
    a.cancel_buy(sid);self.end_swap(a,at,'partial_bought' if a.quantity(sid) else 'buy_expired')
 def preflight(self,a,at):
  a.pair_sale_ok=False
  if not a.swap or a.swap['phase']!='sell':return
  z=a.swap;old,new=z['victim'],z['candidate'];why=None
  if new in a.buys or a.quantity(new):self.stop_pair(a,at,'ordinary_buy_superseded');return
  sw=self.market.window(old,at,'sell',a.cost_multiplier);bw=self.market.window(new,at,'buy',a.cost_multiplier)
  if sw is None or sw.sell_allowed is not True:why='old_not_executable'
  elif bw is None or bw.buy_allowed is not True:why='new_not_executable'
  elif sw.capacity_shares<a.quantity(old):why='old_cannot_fully_sell'
  elif sum(l.shares for l in a.positions[old].lots if l.sellable_at<=at)<a.quantity(old):why='old_not_T1_sellable'
  else:
   factor=self.facts.factor(new,at);support=a.swap_context['support']/factor
   if bw.raw_open<=support:why='new_open_below_support'
   else:
    q=self.market.quote(old,at);sale=a.quantity(old)*sw.execution_price
    fees=sum(q.fees.incremental('sell',sale,{}, {},a.cost_multiplier,shares=a.quantity(old),par_value=q.par_value).values(),ZERO)
    cash=a.available+sale-fees;budget=min(D(z['budget']),cash);cap=converted_cap(a,new,a.swap_context,at)
    price=bw.raw_open*(1+D(str(a.paired_bps))/10000) if a.paired_bps is not None else bw.execution_price
    count=min(cap,int(max(ZERO,budget)/price),bw.capacity_shares);count=bw.quantity.buy_floor(count)
    nq=self.market.quote(new,at)
    buyfees=sum(nq.fees.incremental('buy',count*price,{}, {},a.cost_multiplier,shares=count,par_value=nq.par_value).values(),ZERO) if count and nq else ZERO
    if not count or count*price+buyfees>cash:why='new_minimum_or_cash'
  a.pair_sale_ok=why is None
  a.log('rotation_open_preflight',at,rotation_id=z['id'],passed=a.pair_sale_ok,reason=why,basis='daily_bar_execution_proxy_not_observed_intraday')
  if why:a.counts['rotation_preflight_'+why]+=1
 def allow_sale(self,a,sid):
  if not a.swap or a.swap['phase']!='sell' or sid!=a.swap['victim']:return True
  order=a.exits.get(sid)
  return bool(a.pair_sale_ok or (order and order.purpose!='rotation_exit'))
 def after_sales(self,a,at):
  if not a.swap or a.swap['phase']!='sell' or a.quantity(a.swap['victim']):return
  z=a.swap;z['sold_at']=next(e.completed_at for e in reversed(a.completed) if e.security_id==z['victim']);a.counts['rotation_sold']+=1
  ok,oid=a.reserve_pair(z,at)
  if not ok:self.end_swap(a,at,'reservation_failed');return
  j=bisect_right(self.market.sessions['A'],at)
  z.update(phase='buy',buy_order=oid,buy_deadline=self.market.sessions['A'][j].date().isoformat())
  a.log('rotation_buy_reserved',at,rotation=dict(z),order_id=oid,budget=a.buys[z['candidate']].budget_cny)
 def normal_buys(self,a):
  sid=a.swap['candidate'] if a.swap and a.swap['phase']=='buy' else None
  return [s for s in a.buys if s!=sid]
 def after_buys(self,a,at):
  if not a.swap or a.swap['phase']!='buy':return
  sid=a.swap['candidate']
  if sid not in a.buys:self.end_swap(a,at,'bought' if a.quantity(sid) else 'not_bought');return
  w=self.market.window(sid,at,'buy',a.cost_multiplier)
  if w:
   when=at+timedelta(seconds=1);price=w.execution_price if a.paired_bps is None else w.raw_open*(1+D(str(a.paired_bps))/10000)
   w=replace(w,event_id=w.event_id+':after_sale',at=when,execution_price=price,cash_due_at=max(when,w.cash_due_at),execution_basis='daily_open_proxy_after_sale_sequence_1s_not_observed_tick')
   a.fill_buy(sid,w);a.settle_due(when)
  if sid not in a.buys:self.end_swap(a,at,'bought' if a.quantity(sid) else 'not_bought')

# Extend the actual-account loop at explicit seams; no changes to risk, normal
# admission, expiry, sizing, execution price, settlement, or original ledger.
source=textwrap.dedent(inspect.getsource(E.Runner.run_tech))
edits=[
 ("     for sid in sorted(a.exits):", "     self.preflight(a,at)\n     for sid in sorted(a.exits):"),
 ("      if w:a.fill_exit(sid,w)","      if w and self.allow_sale(a,sid):a.fill_exit(sid,w)"),
 ("     a.settle_due(at);priority=self.priority.get(aid,())","     a.settle_due(at);self.after_sales(a,at);priority=self.priority.get(aid,())"),
 ("sorted(a.buys,key=","sorted(self.normal_buys(a),key="),
 ("     a.settle_due(at)\n   if at not in cutoffs", "     a.settle_due(at);self.after_buys(a,at)\n   if at not in cutoffs"),
 ("    risk_policy.step(a,at,RISK_MODE)","    risk_policy.step(a,at,RISK_MODE)\n    self.close_pair(a,at,clock)"),
 ("     d=ack.decisions[-1];self.sink.emit", "     self.start_pair(a,at,clock,stocks,sectors)\n     d=ack.decisions[-1];self.sink.emit")]
for old,new in edits:
 old='\n'.join(line[1:] if line.startswith(' ') else line for line in old.split('\n'))
 new='\n'.join(line[1:] if line.startswith(' ') else line for line in new.split('\n'))
 assert source.count(old)==1,(old,source.count(old));source=source.replace(old,new)
scope=dict(E.__dict__);scope['RISK_MODE']='ACT20_BREAK';exec(source,scope);Runner.run_tech=scope['run_tech']

def initialize():
 assert read(PREVIOUS/'verification.json')['passed']
 protocol={'version':'PVR-ROT15','decision':'新股原I当日新买点，原行业资格，PVR>50且新分-旧分>=15；原行业RS/行业内PVR顺序候选，选满足资源约束的最低PVR持仓，同分代码升序',
 'difference':15,'positive_floor_strict':50,'parameter_basis':'事前研究约定，一套机制，不按收益扫描阈值',
 'capital':'原100万元初始ACTIVE、407股11行业，2024首交易日至2026-10-27；同上一轮快照，不补数据',
 'normal_priority':'原正常开仓和结构退出优先；正常可买则不为该候选换仓。旧股无其他买卖单、次开盘T+1可卖；一换一后仍须6股/3行业/每行业2股、15%初仓/90%新增投入和现金费用整手。',
 'rate':'每天最多一对且全账户只允许一对未完成配对；不另加持有天数或冷却期',
 'frozen':'T收盘冻结新/旧、预算、最大股数和支持位；金额股数在已生效权息下转换，不按未来新分改绑。',
 'execution':'基础下一可执行开盘09:30先卖、09:30:01买；1秒只为因果顺序，非观测秒级价格。事前用既有日线可执行代理检查双方、旧股全量可卖、T+1、新股开盘高于冻结保护位、最低数量与现金费用。不满足先不卖，结构退出不受阻。',
 'intent':'卖最多T之后两个市场日，完整卖出后立即预约新股并尝试买；买最多卖成日及随后一交易日。普通买单仍原单日有效。后续只检查既有I结构/行业/数据/市场资格，不要求再有新买点、温度或分差；账户暂停/新股失效取消，保留卖后未买和部分成交。',
 'delay':'原delay1两腿各额外跳过一次可执行事件，卖出延迟后买单另计延迟，受配对期限约束。',
 'limitations':'无分钟数据；同日开盘先卖后买、日线高低/容量后验检查为研究代理，非真实原子可成交保证。另以配对买25bps作单独预声明压力。',
 'unchanged':'PVR公式/准备期、行业RS、E0-NR1/G1-I、账户暂停恢复、原普通预算/费用/权息/T+1/日线执行器、科技池均不改。新规则仅允许有限主动替换。',
 'paths':{'ROT':['base','cost2','delay1'],'ROT25':['base']},'controls':'原RS和仅PVR三个情景各完整技术恒等重放，不冒充新增策略；比较时展示全部9条主路径及1条滑点压力。',
 'evaluation':'原始量价图先看；短段合成/旧控制/独立核账后冻结资金；结果后全账/每对分差与起源事件/每腿因果及期限/实际换入失败/物理前缀；赢家参与、全部亏损与普通净损耗均报告。',
 'stop':'每新增路径仅一次经济；不按结果调参，不自动采用或改正式/模拟账户。'}
 save(O/'protocol.json',protocol)
 save(O/'input.json',{'prior':str(PREVIOUS),'prior_freeze_sha256':sha(PREVIOUS/'freeze.json'),'input_sha256':sha(PREVIOUS/'input.json'),'formula':read(PREVIOUS/'input.json')['formula_sha256'],'end':'2026-10-27'})
 (O/'execution-rules-v2.json').symlink_to(PREVIOUS/'execution-rules-v2.json')
 graphs()

def graphs():
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.patches import Rectangle
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 snap=Path(read(PREVIOUS/'input.json')['snapshot']['path'])
 cases=[('sector_slot','688498.SH','688008.SH','2025-09-01','2025-11-15'),('sector_count','300502.SZ','300131.SZ','2025-06-01','2025-07-31'),('winner_risk','688048.SH','001309.SZ','2026-04-01','2026-07-20')]
 for label,new,old,start,end in cases:
  fig,ax=plt.subplots(3,2,figsize=(15,9),sharex='col',gridspec_kw={'height_ratios':[2,1,1]})
  for j,sid in enumerate([new,old]):
   f=pd.read_parquet(snap/'signals'/f'{sid}.parquet').loc[start:end];z=pd.read_parquet(PREVIOUS/'scores'/f'{sid}.parquet').reindex(f.index);fact=pd.read_parquet(snap/'facts'/f'{sid}.parquet').reindex(f.index);x=np.arange(len(f))
   for i,(_,r) in enumerate(f.iterrows()):
    color='#b8332e' if r.close>=r.open else '#257e53';ax[0,j].vlines(i,r.low,r.high,color=color,lw=.6);ax[0,j].add_patch(Rectangle((i-.3,min(r.open,r.close)),.6,max(abs(r.close-r.open),1e-5),facecolor=color,lw=.4))
   buy=fact.i_buy.fillna(False).astype(bool)&fact.i_target.fillna(False).astype(bool);ax[0,j].scatter(x[buy],f.loc[buy,'low']*.97,marker='^',s=18,color='#303030',label='原I事件')
   ax[0,j].set_title(sid+' 因果复权OHLC');ax[0,j].legend();ax[1,j].bar(x,f.amount/1e8,color='#8196aa');ax[1,j].set_ylabel('金额 / 亿元');ax[2,j].plot(x,z.score,label='PVR');ax[2,j].axhline(50,color='grey',ls='--',lw=.6);ax[2,j].set_ylim(0,100);ticks=np.linspace(0,len(f)-1,5,dtype=int);ax[2,j].set_xticks(ticks,[str(f.index[i].date())[2:] for i in ticks],rotation=20)
  fig.suptitle('换仓机制图检：左为机会股，右为已有持仓对照；不代表实际新换仓');fig.tight_layout();fig.savefig(O/f'raw-{label}.png',dpi=125);plt.close(fig)

def run(version,stage):
 global ENABLED,PAIRED_BPS
 assert version in ['RS','PVR','ROT','ROT25'];assert stage in ['short','control','economic','prefix']
 ENABLED=version.startswith('ROT');PAIRED_BPS=25 if version=='ROT25' else None
 original=P.setup('RS' if version=='RS' else 'PVR')
 R.Account=Account;R.Runner=Runner
 root=O/version;root.mkdir(exist_ok=True)
 if not (root/'execution-rules-v2.json').exists():(root/'execution-rules-v2.json').symlink_to(O/'execution-rules-v2.json')
 out=root/('technical/short-v2' if stage=='short' else 'technical/prefix' if stage=='prefix' else 'technical/control' if stage=='control' else 'accounts-v2')
 if stage=='economic':assert read(O/'admission.json')['passed'];assert read(O/'graph-review.json')['reviewed'];assert (O/'freeze.json').exists()
 end='2024-06-28' if stage=='short' else '2026-06-30' if stage=='prefix' else '2026-10-27';stresses=['base'] if version=='ROT25' else ['base','cost2','delay1']
 R.run(out,modes=['I'],stresses=stresses,end=end,cutoff=end if stage=='prefix' else None,technical=stage!='economic')
 R.context=original

def freeze():
 assert read(O/'admission.json')['passed'] and read(O/'graph-review.json')['reviewed']
 fs=[O/'protocol.json',O/'input.json',O/'graph-review.json',O/'repair.json',*sorted((O/'code').glob('*.py')),*sorted((P.ACT/'code').glob('*.py')),*sorted((P.BASE/'code').glob('*.py')),*sorted((PREVIOUS/'code').glob('*.py')),PREVIOUS/'freeze.json',PREVIOUS/'coverage.csv',PREVIOUS/'execution-rules-v2.json',PREVIOUS/'input/manifest.json']
 save(O/'freeze.json',{'before_economic':True,'sha256':{str(f):sha(f) for f in fs}})

if __name__=='__main__':
 if sys.argv[1]=='initialize':initialize()
 elif sys.argv[1]=='freeze':freeze()
 else:run(sys.argv[2],sys.argv[1])
