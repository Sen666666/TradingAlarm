"""Use the established collector with a 12-bar incremental page, not 750 bars."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'research_rounds/current-pool-20261022/code'))
import history_batch
history_batch.PAGE=12
if __name__=='__main__':history_batch.main()
