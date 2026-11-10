"""Cross-process identity/financial/evidence state readback, no new events."""
import sys
from pathlib import Path
from datetime import datetime
from native_capital import SyntheticRunner,digest
from imports_native import IO
r=SyntheticRunner.restore(Path(sys.argv[1]));at=datetime.fromisoformat(sys.argv[3])
IO.write_json(Path(sys.argv[2]),dict(digest=digest(r.account.exported(at)),contract=r.binding()['contract'],cross_process=True,new_account_events=0))
