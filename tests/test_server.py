import sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server

M="8=FIX.4.2|35=D|49=B|56=S|11=O1|55=AAPL|54=1|38=100|40=2|44=150.5"
def test_parse():
    p=server.parse_fix(M); assert p.msg_type=="D"; assert p.symbol=="AAPL"
def test_govern():
    assert any("MiFID" in f for f in server.govern_trade("8=x|35=D|55=AAPL|40=1").frameworks)
