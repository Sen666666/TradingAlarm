from native_risk import *
sys.path.insert(0,str(BASE))
from state_hash import full_state_hash
r=Runner.restore(sys.argv[1]);at=iso(sys.argv[3]);IO.write_json(Path(sys.argv[2]),dict(full_state_hash=full_state_hash(r),digest=digest(r.observable(at)),observable=digest(r.observable(at)),bridge=r.account.bridge(at)),encoder=encode)
