from native_c import *
from state_hash import full_state_hash
if __name__=='__main__':
 r=Runner.restore(sys.argv[1]);at=iso(sys.argv[3]);IO.write_json(Path(sys.argv[2]),dict(digest=digest(r.observable(at)),bridge=r.account.bridge(at),full_state_hash=full_state_hash(r),mode=r.mode,source=r.source_binding()),encoder=encode)
