from pathlib import Path
import sys
from prepare_cases import load,save
from quote_package import proposal
if __name__=='__main__':
    save(Path(sys.argv[3]),proposal(load(sys.argv[1]),expected_sha256=sys.argv[2]))
