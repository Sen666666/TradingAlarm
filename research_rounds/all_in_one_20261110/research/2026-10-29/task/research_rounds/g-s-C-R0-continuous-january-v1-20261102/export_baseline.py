"""Read already-audited Jan28 baseline snapshots, no original event/replay."""
from pathlib import Path
import json,pickle,sys
import jan_r0 as X
E=X.E;P=X.HERE;B=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/C-2022-month-native-baseline-20261102')
sys.path.insert(0,str(X.M.HERE));from analyze_short import accounting,grouped
O=P/'baseline_readonly';O.mkdir(exist_ok=True);rows=[];layers={};stocks={}
for mode in ['C10','C_BATCH20']:
 arm='2022-'+mode;done=X.read(B/(arm+'-DONE.json'));rec=done['progress']['record'];cp=Path(rec['checkpoint']);E.require(done['passed'] and X.sha(cp)==rec['sha256'],'frozen audited baseline bytes changed')
 side=X.read(cp.with_suffix('.provenance.json'));E.require(side['checkpoint_sha256']==rec['sha256'],'baseline provenance changed');r=pickle.loads(cp.read_bytes());r.account.owner=r
 E.require(type(r) is X.C.ContinuationRunner and r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'original baseline actual class/source changed');r.assert_observers()
 x=json.loads(json.dumps(dict(account=r.account.exported(r.last_completed_event)),default=E.encode));ll,ss,pnl=accounting(x);layers[mode]=ll;s=X.read(B/'analysis'/(arm+'-SUMMARY.json'))
 E.require(abs(E.D(pnl['realized_actual_sales_net_buy_and_sell_fees'])-E.D(s['realized_net']))<E.D('1e-10') and abs(E.D(pnl['unrealized_mark_minus_remaining_net_buy_cost'])-E.D(s['unrealized_net']))<E.D('1e-10'),'reused layer allocation differs from audited summary')
 X.save(O/(mode+'-NATIVE_ACCOUNT.json'),x);rows.append(dict(mode=mode,summary=s,pnl=pnl,source_checkpoint=str(cp),sha256=rec['sha256'],actual_native_state_read_only=True));print('BASELINE_READONLY_EXPORTED',mode,flush=True)
X.save(O/'RESULTS.json',rows);X.save(O/'ALL_LAYERS.json',layers)
