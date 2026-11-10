"""Restore identity only. Never invokes an account event/window/step."""
import sys
import replay_runtime as X
r=X.ReplayRunner.restore(sys.argv[1])
X.save(sys.argv[2],dict(cursor=r.last_completed_event,original_view_snapshot_hash=X.E.digest(X.snapshot(r)),binding=r.binding(),financial_events=0,tracked_stock_authorizations=len(r.risk.approvals),legacy_completed_orders=len(r.risk.legacy_orders),pending_intents=len(r.account.pending),actual_buy_orders=len(r.account.buys),sell_obligations=len(r.account.exits)))
