"""Freeze only the two authorized input prefixes; no account/model execution."""
from loader import *
import argparse, time, os
import pyarrow.parquet as pq
P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
READY=B/'g-s-minimal-input-readiness';BOOT=B/'g-s-market-bootstrap-v1'
SPECS={'2022':('2021-12-31',['2022-01-04','2022-01-05']), '2025_26':('2025-06-30',['2025-07-01','2025-07-02'])}
MAP=dict(retained=['common_ready STOCK component','current selection/issuer/company cap >10bn/fixed sector identity',
 'original historical venue/availability and observation/readiness masks','I target / I daily event for core only',
 'same-session original stock H1 readiness','canonical fresh CP1 for mobile, unchanged scale/source/formation clock',
 'core structure lock; actual core/mobile priority remains account responsibility'],
 replaced=['common_ready legacy INDUSTRY component','sector_observed_today','sector_rs_ready_fresh','sector_up',
 'old budget/D1 industry active/episode/attempt authorization'],
 replacement='original F1 G/S State/source/proof in separate policy_scope, subject to frozen V2 purpose and ACT clocks',
 attribution_only=['old industry Q facts, episode/attempt/stage (not new authorization)'],
 caution='retained_stock_Q is necessary stock-input qualification, not F1 permission, order sizing or capital admission')

def filtered(path,end,key='date'):
 return pq.read_table(path,filters=[(key,'<=',pd.Timestamp(end).to_pydatetime())]).to_pandas()
def longframe(f,sid):
 g=f.copy();g.index=pd.to_datetime(g.index);g['day']=g.index.strftime('%Y-%m-%d');g['sid']=sid;return g.reset_index(drop=True)
def select_prefix(f,warm,days):
 # preserve actual last known row, not a made-up row on warm cutoff
 old=f.loc[:warm].tail(1);new=f[f.index.isin(pd.to_datetime(days))]
 return pd.concat([old,new]).loc[lambda z:~z.index.duplicated(keep='last')]
def structures(sid,f):
 on=f.e0_target.astype(bool);seg=f.segment_id
 starts=on & ~on.groupby(seg).shift(fill_value=False)
 ids=pd.Series([None]*len(f),index=f.index,dtype=object)
 ids.loc[starts]=[sid+'|'+str(int(f.loc[t,'segment_id']))+'|'+str(t.date()) for t in f.index[starts]]
 ids=ids.groupby(seg).ffill().where(on)
 out=[]
 for identity,g in ids.dropna().groupby(ids.dropna(),sort=False):
  out.append(dict(identity=identity,start=str(g.index.min().date()),end=str(g.index.max().date())))
 return out

def prepare(out):
 out=Path(out);out.mkdir(parents=True,exist_ok=False);begun=time.monotonic()
 inventory=read(READY/'STOCK_INPUT_INVENTORY.json');expected=read(READY/'SOURCE_SHA256.json')
 bindings={};source_access=[]
 def bind(p):
  p=Path(p);actual=sha(p);e=expected.get(str(p))
  if e and actual!=e:raise ValueError('original source changed '+str(p))
  bindings[str(p)]=actual;return actual
 def get(p):bind(p);return read(p)
 assert sha(BOOT/'PACKAGE_SHA256.json')=='693bcafee5236c69f37cb063e458ba47e4637ffefe013de787432ed08a34bcc9'
 bootcat=get(BOOT/'READY_CHECKPOINTS.json')['ready_states'];bhash=read(BOOT/'PACKAGE_SHA256.json')
 ids=[r['symbol'] for r in inventory];sectors=sorted({r['sector_id'] for r in inventory});assert len(ids)==1709 and len(sectors)==90
 runtime=get(P/'manifest.json');runtime={r['series_id']:r for r in runtime['series']}
 selection=get(RR/'a-share-selection-e0-20261024/inputs-v2/selection.json')
 rules=get(RR/'pvr-act-comparison-20261027/execution-rules-v2.json')
 protocol=get(RR/'a-share-selection-e0-20261024/inputs-v2/economic-protocol.json')
 hpath=P/'h1.npz';bind(hpath);h=np.load(hpath,allow_pickle=False);hd=pd.DatetimeIndex(h['dates']);hc={str(s):i for i,s in enumerate(h['symbols'])};hscores=h['score']
 cat=get(B/'industry-coverage/run-v1/NODE_CATALOGUE.json')
 nodes=[dict(node_id='NATIVE1709_global',sector=None,input_file=str(B/'input-preparation/prepared-v2/NATIVE1709/market.parquet'))]+[r for r in cat if r['domain']=='NATIVE1709']
 acc={k:dict(facts=[],cp=[],raw=[],pvr=[],h1=[],receipts=[],actions=[],metadata={},f1_observations=[],legacy_industry=[]) for k in SPECS}
 for n,r in enumerate(inventory):
  sid=r['symbol'];refs=r['refs']
  # Read original parquet by genuine date predicates before materialization.
  for v in ['facts','CP1','raw_bars','PVR']:bind(refs[v])
  ff=filtered(refs['facts'],'2025-07-02');cc=filtered(refs['CP1'],'2025-07-02');pv=filtered(refs['PVR'],'2025-07-02',key='day')
  raw=filtered(refs['raw_bars'],'2025-07-02',key='trade_date').set_index('trade_date')
  aa=get(refs['actions']) if refs['actions'] else dict(events=[])
  rr={k:get(refs['receipts_2022' if k=='2022' else 'receipts']) for k in SPECS}
  for k,(warm,days) in SPECS.items():
   d=acc[k];end=days[-1];f=ff.loc[:end];c=cc.loc[:end]
   for name,data in [('facts',f),('cp',c),('pvr',pv.loc[:end])]:d[name].append(longframe(select_prefix(data,warm,days),sid))
   # Original proxy needs past20 positive-volume capacity; retain last21
   # observations plus exact prefix rows, not fabricated quotes or fills.
   pre=raw.loc[:warm];ix=pre.index[pre.volume.gt(0)&np.isfinite(pre.volume)].tolist()[-21:]
   rraw=pd.concat([pre.loc[ix],raw[raw.index.isin(pd.to_datetime(days))]]).sort_index()
   d['raw'].append(longframe(rraw,sid))
   hv=[]
   for day in [warm]+days:
    i=hd.get_indexer([pd.Timestamp(day)])[0];assert i>=0
    hv.append(dict(sid=sid,day=day,score=float(hscores[i,hc[sid]])))
   d['h1'].extend(hv)
   d['receipts'].extend(x for x in rr[k] if days[0]<=x['confirmed_day']<=end)
   for e in aa['events']:
    # Include declared later payments only if they actually fall in prefix.
    if days[0]<=e['effective_date']<=end or e.get('paid_at') and days[0]<=e['paid_at'][:10]<=end:
     d['actions'].append(dict(sid=sid,**e,known_action_date=e['effective_date'],
       unpaid_policy='original unknown date stays attributed receivable, 80% net research proxy; no financing',
       sellability_proxy='unknown new-share sellable date follows original next source trading day proxy; not certified'))
   d['metadata'][sid]=dict(name=r['name'],sector=r['sector_id'],runtime_record=runtime[sid],structures=structures(sid,f),
     stock_source_status=r['universe_status'],actions_status=r['action_status'],factor_coordinate='adjusted_close = raw_close * price_factor; cash dividend factor is not share multiplier')
  if (n+1)%400==0:print('READ_ONLY_EXPORT',n+1,round(time.monotonic()-begun,2),flush=True)
 for node in nodes:
  p=Path(node['input_file']);bind(p);f=filtered(p,'2025-07-02')
  for k,(warm,days) in SPECS.items():
   z=f[f.index.isin(pd.to_datetime(days))].copy();z['node_id']=node['node_id'];z['policy_scope']=node['sector'] or 'G';z['original_F1_scope']='NATIVE1709_industry_'+node['sector'] if node['sector'] else 'NATIVE1709_global'
   acc[k]['f1_observations'].append(longframe(z,node['node_id']))
 for sector in sectors:
  p=W/'mainline-I-quarter-2025Q3-20261031/industry-facts'/f'{sector}.parquet';bind(p);f=filtered(p,'2025-07-02')
  for k,(warm,days) in SPECS.items():acc[k]['legacy_industry'].append(longframe(select_prefix(f,warm,days),sector))
 summaries={}
 for k,(warm,days) in SPECS.items():
  root=out/k;root.mkdir();m=dict(schema=SCHEMA,window=k,warm_through=warm,days=days,fixed_ids=ids,sectors=sectors,
    eligibility_mapping=MAP,financial_authorization=False,files={},original_clock='date.toordinal + original aware event timestamp')
  def save_obj(name,x):
   p=root/(name+'.json');write(p,x);m['files'][name]=dict(path=p.name,sha256=sha(p))
  def save_tab(name,x):
   p=root/(name+'.parquet');x.to_parquet(p,index=False);m['files'][name]=dict(path=p.name,sha256=sha(p))
  for name in ['facts','cp','raw','pvr','f1_observations','legacy_industry']:save_tab(name,pd.concat(acc[k][name],ignore_index=True))
  save_tab('h1',pd.DataFrame(acc[k]['h1']))
  for name in ['receipts','actions','metadata']:save_obj(name,acc[k][name])
  save_obj('selection',selection);save_obj('rules',rules);save_obj('protocol',protocol)
  seeds={}
  for nid,record in bootcat[k].items():
   p=Path(record['path']);bind(p);assert sha(p)==record['sha256']==bhash[str(p.relative_to(BOOT))]
   seeds[nid]=read(p)
  save_obj('bootstrap',seeds);write(root/'MANIFEST.json',m)
  summaries[k]=dict(stocks=len(ids),sectors=len(sectors),days=days,receipts=len(acc[k]['receipts']),actions=len(acc[k]['actions']),market_seeds=len(seeds),manifest_sha256=sha(root/'MANIFEST.json'))
 write(out/'SOURCE_BINDINGS.json',bindings)
 write(out/'FREEZE.json',dict(kind='read-only input package',created_pid=os.getpid(),specs=SPECS,summary=summaries,
   source_files=len(bindings),source_bindings_sha256=sha(out/'SOURCE_BINDINGS.json'),bootstrap_package_sha256=sha(BOOT/'PACKAGE_SHA256.json'),
   no_accounts_created=True,no_intents_created=True,no_financial_events=True,no_models_recomputed=True,seconds=time.monotonic()-begun))
 print('EXPORTED',canonical(summaries),round(time.monotonic()-begun,2),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();prepare(a.out)
