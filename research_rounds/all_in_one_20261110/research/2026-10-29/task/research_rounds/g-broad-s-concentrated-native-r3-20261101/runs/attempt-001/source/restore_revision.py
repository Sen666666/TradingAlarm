"""Resume one generated event after an actual close checkpoint."""
import sys
from datetime import datetime
from native_capital import SyntheticRunner,digest
from imports_native import IO
r=SyntheticRunner.restore(sys.argv[1]);at=datetime.fromisoformat(sys.argv[3]);r.event(at,is_open=True)
IO.write_json(sys.argv[2],dict(digest=digest(r.observable(at)),new_generated_events=1,historical_events=0))
