"""Read-only terminal stock attribution, validated to each native inventory."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,csv,hashlib
import pandas as pd
ROOT=Path(__file__).resolve().parent
SM=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
def read(p):return json.loads(p.read_text())
def dec(x):return D(str(x))
def main():
 sm={x['symbol']:x for x in read(SM)}
 rr={k:read(ROOT/f'performance/{k.upper()}_ALL_ROUNDS.json') for k in ['original','growth']}
 pos={k:{r['sid']:r['qty'] for r in rows if not r['exited']} for k,rows in rr.items()}
 marks={};sources={}
 for sid in set(pos['original'])|set(pos['growth']):
  p=Path(next(p for p in sm[sid]['source_sha256'] if p.endswith('/signal.parquet')))
  assert hashlib.sha256(p.read_bytes()).hexdigest()==sm[sid]['source_sha256'][str(p)]
  f=pd.read_parquet(p,columns=['raw_close']).loc[:'2023-04-28'];f=f[f.raw_close.notna() & (f.raw_close>0)]
  assert len(f);marks[sid]=dec(f.raw_close.iloc[-1]);sources[str(p)]=sm[sid]['source_sha256'][str(p)]
 for key,stem in [('original','baseline'),('growth','growth')]:
  day=[json.loads(l) for l in gzip.open(ROOT/stem/'run/pair/daily.jsonl.gz','rt')][-1]
  inv=sum((dec(q)*marks[sid] for sid,q in pos[key].items()),D(0))
  assert inv==dec(day['inventory']),(key,inv,day['inventory'])
 def stock_pnl(key,sid):
  return sum((dec(r['sell_net'])-dec(r['buy_cash'])+dec(r['dividend'])+(dec(r['qty'])*marks[sid] if not r['exited'] else 0) for r in rr[key] if r['sid']==sid),D(0))
 out=[]
 for sid in {r['sid'] for rs in rr.values() for r in rs}:
  old=stock_pnl('original',sid);new=stock_pnl('growth',sid)
  out.append(dict(sid=sid,name=sm[sid].get('name',sid),old_end_qty=pos['original'].get(sid,0),growth_end_qty=pos['growth'].get(sid,0),raw_mark=marks.get(sid),original_total_pnl=old,growth_total_pnl=new,difference=new-old))
 out.sort(key=lambda x:x['difference'])
 navs=read(ROOT/'comparison/SUMMARY.json')
 assert sum((x['difference'] for x in out),D(0))==dec(navs['end_nav_difference'])
 path=ROOT/'performance/STOCK_NAV_ATTRIBUTION.csv';assert not path.exists()
 with path.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
 (ROOT/'performance/ATTRIBUTION_SOURCE_HASHES.json').write_text(json.dumps(dict(manifest_sha256=hashlib.sha256(SM.read_bytes()).hexdigest(),raw_sources=sources,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2))
 print(json.dumps(dict(worst=out[:8],best=out[-8:],sum_difference=str(sum((x['difference'] for x in out),D(0))),inventory_exact=True),ensure_ascii=False,default=str))
if __name__=='__main__':main()
