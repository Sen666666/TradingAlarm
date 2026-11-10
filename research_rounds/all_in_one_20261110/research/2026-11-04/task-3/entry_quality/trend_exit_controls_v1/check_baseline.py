"""Compare existing new baseline checkpoint/full book to frozen original path."""
from pathlib import Path
import gzip,json,pickle,hashlib,argparse
import load_inputs as V
O=Path(__file__).resolve().parent;B=V.B;J=V.J
OLD={'2022_2024':B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024','strong':B/'pvr_pool_feasibility/runs/2025_26'}
def readrows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def main(window):
 r=O/'runs/BASELINE'/window;p=r/'checkpoint.pkl';meta=json.loads((r/'checkpoint.json').read_text());raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==meta['sha256'],'checkpoint changing; inspect again, do not mix cursor'
 payload=pickle.loads(raw);at=str(payload['last_completed_event']);new=J.W.canon(payload['runner']['daily']);old=[x for x in readrows(OLD[window]/'pair/daily.jsonl.gz') if x['at']<=at]
 assert len(new)==len(old),(len(new),len(old));diff=[]
 for a,b in zip(new,old):
  if a!=b:diff.append(dict(at=a['at'],different_keys=[k for k in a.keys()|b.keys() if a.get(k)!=b.get(k)],money_differences={k:[a.get(k),b.get(k)] for k in ['nav','inventory','available','order_reserved','dividend_receivable','settlement_locked'] if a.get(k)!=b.get(k)}))
 ac=payload['accounts']['B'];book=json.loads(gzip.open(OLD[window]/'pair/B.json.gz','rt').read());trades=[x for x in book['trades'] if str(x['at'])<=at];nt=J.W.canon(ac['trades']);assert nt==trades,'native trade receipts differ'
 assert not diff,('daily baseline mismatch',diff[:5])
 out=dict(passed=True,window=window,through=at,daily_rows=len(new),daily_all_fields_exact=True,trade_receipts=len(nt),all_trade_fields_exact=True,checkpoint_sha256=meta['sha256'],original_daily_path=str(OLD[window]/'pair/daily.jsonl.gz'),full_window_completed=(r/'DONE.json').exists(),no_original_account_import=True,baseline_full_replay_only=True)
 target=r/('FULL_BASELINE_EQUALITY.json' if out['full_window_completed'] else 'PREFIX_BASELINE_EQUALITY.json');target.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__':p=argparse.ArgumentParser();p.add_argument('window',choices=list(OLD));main(p.parse_args().window)
