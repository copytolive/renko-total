from pathlib import Path
import sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from copytolive_renko.io import load_ticks_csv,parse_timestamp_ms

class IoTests(unittest.TestCase):
    def test_timestamp_units(self):
        self.assertEqual(parse_timestamp_ms("1700000000"),1700000000000)
        self.assertEqual(parse_timestamp_ms("1700000000000"),1700000000000)
    def test_flexible_header(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"x.csv"; p.write_text("timestamp,askPrice,bidPrice,askVolume,bidVolume\n1700000000000,2000.12,2000.10,1.2,1.1\n")
            ticks=load_ticks_csv(p,price_unit="0.01")
            self.assertEqual((len(ticks),ticks[0].ask_units,ticks[0].bid_units),(1,200012,200010))
if __name__=="__main__": unittest.main()
