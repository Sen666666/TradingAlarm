from pathlib import Path
import hashlib
O=Path(__file__).resolve().parent; P=O.parent
old=(P/'continuous_candidate_v1/engine.py').read_text()
s=old.replace('One frozen offline candidate. No routes, no writes outside this new directory.','Frozen multi-sector joint-account research candidate. No real orders.')
a=s.index('class Data:');b=s.index(' def z(self,s,d):',a)
s=s[:a]+'''def sector_frame(known,right):
 N=len(known.columns);K=known.sum(axis=1);n=right.sum(axis=1);pair=known&known.shift(3,fill_value=False);J=pair.sum(axis=1);entered=(pair&right&~right.shift(3,fill_value=False)).sum(axis=1);left=(pair&~right&right.shift(3,fill_value=False)).sum(axis=1);diff=entered-left;u=N-K
 lo=n.ge(3)&((3*n>=N)&J.gt(0)&diff.gt(0)|(2*n>=N));hi=(n+u).ge(3)&((3*(n+u)>=N)&(diff.gt(0)|J.eq(0))|(2*(n+u)>=N))
 return pd.DataFrame(dict(N=N,K=K,n=n,U=u,paired_K=J,entered3=entered,left3=left,diff=diff,state=np.where(lo,1,np.where(~hi,0,-1)),strength=(2*n>=N)&(2*n.shift()>=N)&diff.gt(0)))
class Data:
 def __init__(self,end='2024-10-31'):
  self.end=pd.Timestamp(end);self.hashes={};self.admission=[]
  def hashed(p):
   p=Path(p)
   if str(p) not in self.hashes:self.hashes[str(p)]=sha(p)
   return p
  def checked(p,h):
   hashed(p);assert self.hashes[str(p)]==h,('INPUT_DRIFT',str(p))
  self.ro=pd.read_csv(hashed(O/'CLASSIFICATION_ALL1709.csv'),keep_default_na=False);assert len(self.ro)==1709 and self.ro.symbol.is_unique
  for p,h in read(hashed(O/'MAPPING_SOURCE_HASHES.json')).items():checked(p,h)
  self.excluded=self.ro[~self.ro.eligible.eq(True)].to_dict('records')
  selected=self.ro[self.ro.eligible.eq(True)];self.ids=sorted(selected.symbol);self.sid_sector=selected.set_index('symbol').sector51.to_dict();self.names=selected.set_index('symbol').name.to_dict();self.sector_ids=sorted(set(self.sid_sector.values()));assert len(self.sector_ids)<=50
  self.manifest={m['symbol']:m for m in read(hashed(U/'STOCK_MANIFEST.json'))};assert set(self.ro.symbol)==set(self.manifest)
  self.rules=read(hashed(B/'inputs-v2/market-rules.json'));self.proxies=read(hashed(B/'inputs-v2/economic-protocol.json'))['approved_proxy_ids']
  for p in [B/'code/market_rules.py',B/'code/sector_account.py',O/'FROZEN_CONTRACT.md',O/'engine.py',O/'SYNTHETIC_QA.json']:hashed(p)
  Q=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
  k=pd.read_parquet(hashed(Q/'KNOWN3.parquet'))[self.ids].loc[:self.end];r=pd.read_parquet(hashed(Q/'RIGHT3.parquet'))[self.ids].loc[:self.end]
  ps=pd.read_parquet(hashed(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet'),columns=['sid','day','state']);ps=ps[ps.sid.isin(self.ids)].pivot(index='day',columns='sid',values='state').reindex(index=k.index,columns=self.ids)
  known=k&ps.ge(0);right=r&known;self.stock=pd.DataFrame(np.where(known,np.where(right,1,0),-1),index=k.index,columns=self.ids)
  self.sectors={}
  for sector in self.sector_ids:
   ids=[s for s in self.ids if self.sid_sector[s]==sector];self.sectors[sector]=sector_frame(known[ids],right[ids])
  self.cal=k.index;self.days=self.cal[self.cal>=pd.Timestamp('2024-09-02')];self.raw={};self.facts={};self.cp={};self.cap={};self.actions={};self.events={};self.meta={}
  for sid in self.ids:
   m=self.manifest[sid];ex={**m['source_sha256'],**m['output_sha256']};paths=[next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')),m['refs']['facts'],m['refs']['CP1']]
   for p in paths:checked(p,ex[p])
   z,f,c=[pd.read_parquet(p).loc[:self.end] for p in paths];self.raw[sid]=z;self.facts[sid]=f;self.cp[sid]=c
   v=z.raw_volume[z.raw_volume.gt(0)];self.cap[sid]=(v.rolling(20,min_periods=20).mean()*.01).reindex(z.index).ffill()
   ap=AS/'inputs-v1/actions'/(sid+'.json');a=read(hashed(ap));assert a['series_id']==sid and a['currency']=='CNY';self.actions[sid]=a
   for ce in a.get('coverage_evidence',[]):checked(ce['path'],ce['sha256'])
  ep=E/'cash_dividend_2024_coverage_v1/EVENT_ADAPTER_CANDIDATES.json';events=read(hashed(ep))
  au=E/'cash_dividend_2024_coverage_v1/FINAL_INDEPENDENT_AUDIT.json';audit=read(hashed(au));assert audit['result']=='PASS_COMPANY_FACT_EVIDENCE_ONLY';checked(ep,audit['audited_artifact_sha256'][ep.name])
  xp=P/'continuous_candidate_v1/EXTRA_REVIEWED_EQUITY_EVENTS_V2.json';events+=read(hashed(xp))
  for e in events:
   s=e['sid'];dt=pd.Timestamp(e['ex_date'])
   if s not in self.ids or not pd.Timestamp('2024-09-02')<=dt<=self.end:continue
   assert (s,dt) not in self.events,('DUPLICATE_EVENT',s,dt)
   for p,h in e.get('evidence_hashes',{}).items():checked(p,h)
   for stem in ['source_fact','local_action','signal']:
    if e.get(stem+'_path'):checked(e[stem+'_path'],e[stem+'_sha256'])
   notice=e.get('notice')
   if notice and notice.get('pdf_path'):checked(notice['pdf_path'],notice['pdf_sha256'])
   a=self.actions[s];terms=[x for x in a['events'] if x['effective_date']==e['ex_date']];assert len(terms)==1
   term=terms[0];assert dec(term['split_ratio'])==1 and dec(term['cash_per_old_share'])==dec(e['d_source'])
   z=self.raw[s];prev=z[z.index<dt].iloc[-1];cur=z.loc[dt];fo=dec(prev.adjustment_factor);fn=dec(cur.adjustment_factor);ds=dec(e['d_source']);pc=dec(prev.raw_close)
   assert lineage(prev)==lineage(cur) and abs(fo*pc/(pc-ds)/fn-1)<D('1e-11')
   assert pd.Timestamp(e['record_date'])==prev.name and pd.Timestamp(e['record_date'])<dt<=pd.Timestamp(e['pay_date'])
   if 'factor_old' in e:assert abs(fo/dec(e['factor_old'])-1)<D('1e-11') and abs(fn/dec(e['factor_new'])-1)<D('1e-11')
   assert dec(e['d_cash'])>=0
   e=dict(e,factor_old=str(fo),factor_new=str(fn));self.events[(s,dt)]=e;self.admission.append(dict(sid=s,sector51=self.sid_sector[s],ex_date=day(dt),event_id=e['economic_event_id_candidate'],status='BOUNDED_RESEARCH_NET80_ONLY',factor_bridge_verified=True,not_PIT=True,not_production_admission=True))
  core=pd.read_csv(hashed(P/'CORE_DAILY_51CLASS_SIGNALS.csv'),parse_dates=['day']);core=core[core.day<=self.end]
  for sector,g in core.groupby('sector51'):
   g=g.set_index('day')
   for col in ['N','K','n','U','state']:assert np.array_equal(g[col].to_numpy(dtype=int),self.sectors[sector].loc[g.index,col].to_numpy(dtype=int)),('CORE_SECTOR_MISMATCH',sector,col)
''' +s[b:]
s=s.replace('self.blockers=[]','self.blockers=[];self.sector_daily=[]')
s=s.replace(" def qvalue(self,a,d,field):return self.quantity(a)*dec(self.d.z(a['sid'],d)[field])", """ def qvalue(self,a,d,field):
  z=self.d.z(a['sid'],d)
  if not finite(z.get(field)) or z[field]<=0:raise Blocked(f\"{day(d)} {a['sid']} {field.upper()}_MISSING\")
  return self.quantity(a)*dec(z[field])""")
s=s.replace("pre_nav=self.nav(d,'raw_open');sv={s:self.qvalue(a,d,'raw_open') for s,a in self.active.items()};sec=sum(sv.values(),ZERO);cash=self.cash", "pre_nav=self.nav(d,'raw_open');sv={s:self.qvalue(a,d,'raw_open') for s,a in self.active.items()};sec=defaultdict(lambda:ZERO);cash=self.cash\n  for s,v in sv.items():sec[self.d.sid_sector[s]]+=v")
s=s.replace("D('.10')*pre_nav-sec)","D('.10')*pre_nav-sec[self.d.sid_sector[s]])")
s=s.replace('cash-=cost;sec+=cost;sv[s]', 'cash-=cost;sec[self.d.sid_sector[s]]+=cost;sv[s]')
s=s.replace("sec=self.d.sector.loc[d];nav=self.nav(d,'raw_close');pending=[]", "nav=self.nav(d,'raw_close');pending=[]")
s=s.replace("   z=self.d.z(s,d);f=self.d.f(s,d);c=self.d.c(s,d)", "   sec=self.d.sectors[self.d.sid_sector[s]].loc[d];z=self.d.z(s,d);f=self.d.f(s,d);c=self.d.c(s,d)")
s=s.replace("   typ=trigger(int(self.d.sector.at[prev,'state']),int(sec.state),", "   secframe=self.d.sectors[self.d.sid_sector[s]];sec=secframe.loc[d]\n   typ=trigger(int(secframe.at[prev,'state']),int(sec.state),")
s=s.replace(",sector_state=int(sec.state),n=int(sec.n),strength=bool(sec.strength),fees_paid=", ",fees_paid=")
s=s.replace("  return pending\n def run(self):", "  self.attribute(d,nav)\n  return pending\n def attribute(self,d,nav):\n  for sector in self.d.sector_ids:\n   sec=self.d.sectors[sector].loc[d];attempts=[a for a in self.archive.values() if self.d.sid_sector[a['sid']]==sector];active=[a for a in self.active.values() if self.d.sid_sector[a['sid']]==sector];trades=[t for t in self.orders if t['day']==day(d) and self.d.sid_sector[t['sid']]==sector];cand=[t for t in self.candidates if t['day']==day(d) and self.d.sid_sector[t['sid']]==sector];mv=sum((self.qvalue(a,d,'raw_close') for a in active),ZERO);cf=sum((a['cashflow'] for a in attempts),ZERO);div=sum((a['dividend'] for a in attempts),ZERO)\n   self.sector_daily.append(dict(day=day(d),sector51=sector,**{k:int(sec[k]) for k in ['N','K','n','U','paired_K','entered3','left3','diff','state']},strength=bool(sec.strength),stocks=len(active),market_value=str(mv),account_weight_pct=str(100*mv/nav),trade_cashflow=str(cf),net80_entitlement=str(div),marked_net_pnl=str(cf+div+mv),seeds_filled=sum(t['side']=='BUY_SEED' for t in trades),adds_filled=sum(t['side']=='BUY_ADD' for t in trades),sells_filled=sum(t['side'].startswith('SELL') for t in trades),seed_buy_cash=str(-sum((dec(t['cash_delta']) for t in trades if t['side']=='BUY_SEED'),ZERO)),add_buy_cash=str(-sum((dec(t['cash_delta']) for t in trades if t['side']=='BUY_ADD'),ZERO)),sell_cash=str(sum((dec(t['cash_delta']) for t in trades if t['side'].startswith('SELL')),ZERO)),new_A=sum(t['phase']=='CLOSE' and t['event']=='A' for t in cand),new_B=sum(t['phase']=='CLOSE' and t['event']=='B' for t in cand),open_rejected=sum(t['phase']=='OPEN' and t['decision']!='PASS' for t in cand)))\n def run(self,checkpoint=False):")
s=s.replace("'holdings','equity'];lengths", "'holdings','equity','sector_daily'];lengths")
s=s.replace("pending=self.close(d,prev)\n   except", "pending=self.close(d,prev)\n    if checkpoint and day(d)=='2024-09-23':\n     self.pending=pending;self.export(O/'prefix_20240923_once');print('CHECKPOINT_20240923 '+json.dumps(self.ledger[-1]),flush=True)\n   except")
s=s.replace("'EQUITY_EVENTS':self.equity}","'EQUITY_EVENTS':self.equity,'SECTOR_DAILY':self.sector_daily}")
s=s.replace("  for name,rr in rows.items():save(path/(name+'.json'),rr);pd.DataFrame(rr).to_csv(path/(name+'.csv'),index=False)", "  for name,rr in rows.items():\n   rr=[dict(r,sector51=self.d.sid_sector[r['sid']]) if 'sid' in r else r for r in rr];save(path/(name+'.json'),rr);pd.DataFrame(rr).to_csv(path/(name+'.csv'),index=False)")
s=s.replace("r['final_qty']=self.quantity(a)","r['sector51']=self.d.sid_sector[a['sid']];r['final_qty']=self.quantity(a)")
s=s.replace("  save(path/'SOURCE_HASHES.json',self.d.hashes)", "  save(path/'EXCLUDED_UNCLASSIFIED.json',self.d.excluded);save(path/'EVENT_ADMISSION.json',self.d.admission)\n  save(path/'SOURCE_HASHES.json',self.d.hashes)")
s=s.replace("names={'x':'x'}", "names={'x':'x'};sid_sector={'x':'TEST'}")
s=s.replace(" return dict(result='PASS',checks=", " return dict(result='PASS',checks=")
idx=s.index("if __name__=='__main__':")
s=s[:idx]+'''if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['synthetic','freeze','run'],required=True);ap.add_argument('--end',default='2024-10-31');ap.add_argument('--output',default='full_20241031_once');ap.add_argument('--seal',default='FREEZE.json');args=ap.parse_args()
 if args.mode=='synthetic':
  v=synthetic();from synthetic_joint import run as joint_tests;v['checks']+=joint_tests();save(O/'SYNTHETIC_QA.json',v);print(v)
 elif args.mode=='freeze':
  assert read(O/'SYNTHETIC_QA.json')['result']=='PASS';assert not (O/args.seal).exists();d=Data();save(O/args.seal,dict(created_utc=str(pd.Timestamp.now(tz='UTC')),hashes=d.hashes,no_candidate_outcome_run=True,universe_total=1709,eligible=len(d.ids),excluded=len(d.excluded),populated_sectors=len(d.sector_ids),bounded_events=len(d.events)));print('FROZEN',len(d.hashes),'stocks',len(d.ids),'sectors',len(d.sector_ids),'events',len(d.events))
 else:
  assert args.end=='2024-10-31';f=read(O/args.seal);assert all(sha(p)==h for p,h in f['hashes'].items());d=Data(args.end);assert d.hashes==f['hashes'];e=Engine(d).run(checkpoint=True);e.export(O/args.output);print(json.dumps(dict(days=len(e.ledger),orders=len(e.orders),blockers=e.blockers,last=e.ledger[-1] if e.ledger else None),ensure_ascii=False))
'''
assert 'self.d.sector.' not in s and 'N=52' not in s and 'sec+=cost' not in s
(O/'engine.py').write_text(s)
contract=(P/'continuous_candidate_v1/FROZEN_CONTRACT.md').read_text()
contract=contract.replace('# Frozen bounded candidate, version 1','# Frozen joint 51-class candidate, version 1')
contract=contract.replace('Exactly the 52 research members classified D061+D062 in CORE_CLASSIFICATION.csv. Local securities/insurance cash account, initial cash CNY1,200,000. This is not the 51-sector competing portfolio and cannot establish total-strategy capture.','All eligible mapped members of the fixed existing 1709-member research roster, using the supplied 51-group leaf-code mapping (50 named industries plus unclassified). Each stock has one sector; unclassified and unknown leaf codes are retained in an exclusion file, never guessed. Current master classifications are not PIT and the roster is not historical all-A. One shared real cash/NAV account starts with CNY1,200,000. No future winners or old episode focus list filters entrants; the broad-market episode list is evaluation only.')
contract=contract.replace('10% this sector','10% independently for each sector').replace('all 52 symbols','all eligible symbols')
contract+='\n## Joint-account technical extension\nEvery sector state, breadth and two-close strengthening is recalculated on its own fixed mapped members. All sectors compete in a single global exit/ADD/SEED queue. Sector exposures and reservations are separate buckets; cash and NAV are truly shared. Report all mapped sectors daily, even zero holdings. No PVR ranking, top-two gate, hindsight sector ranking, shared risk pool, or trial capital pool. The unchanged 2% ADD and 4% attempt capital budgets are capital slots, not loss limits, and a few yuan of positive liquidation profit can still trigger a large ADD; profit does not establish downside coverage.\n\nThe previously audited 165 cash-event candidates plus separately reviewed existing financial-sector supplements are evidence inputs, not automatic production admission. Each in-window event must re-pass evidence hashes, exact local pure-cash term, record date, payment date and unchanged source-factor bridge. This only admits it to the bounded NET80 research scenario. Missing held/pending action, price or source bridges stop and roll back the whole uncertified day. A 2024-09-23 checkpoint is exported during the single forward run, not an independently tuned account. Export order, holdings, candidate decisions, CP history, equity events, attempt outcomes, account ledger, per-sector daily attribution and source hashes.\n'
(O/'FROZEN_CONTRACT.md').write_text(contract)
print('created',O,'engine_sha256',hashlib.sha256(s.encode()).hexdigest())
