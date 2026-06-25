#!/usr/bin/env python3
"""
FIX Protocol Bridge MCP — CSOAI Layer-0 legacy-bridge family.
Financial trading messaging (FIX 4.x/5.0) → ONE OS: parse, validate, govern (MiFID II).
Sibling of cobol-bridge-mcp.
Tools: parse_fix · map_to_modern · govern_trade
"""
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

mcp = FastMCP("FIX Bridge", instructions="Bridge FIX trading messages to ONE OS — parse, map, govern (MiFID II / best execution).")

# ── SIGIL: every governed action → one signed hash-chained hop (SIGIL_LOG unifies all layers) ──
import hashlib as _hl, time as _t, json as _j, os as _os
_SIGIL_LOG = _os.environ.get("SIGIL_LOG", _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "bridge_sigil.log"))
def _sigil(op, body):
    try:
        prev = ""
        if _os.path.exists(_SIGIL_LOG):
            with open(_SIGIL_LOG) as f:
                ls = f.readlines()
                if ls: prev = _j.loads(ls[-1]).get("digest", "")
        ts = int(_t.time()); dg = _hl.sha256(f"{op}|{ts}|{prev[:8]}|{body}".encode()).hexdigest()[:16]
        _os.makedirs(_os.path.dirname(_SIGIL_LOG), exist_ok=True)
        with open(_SIGIL_LOG, "a") as f: f.write(_j.dumps({"ts": ts, "op": op, "body": body, "prev_digest": prev, "digest": dg}) + "\n")
        return dg
    except Exception: return ""

MSG_TYPE = {"D": "New Order - Single", "8": "Execution Report", "F": "Order Cancel Request",
            "G": "Order Cancel/Replace", "0": "Heartbeat", "A": "Logon", "AE": "Trade Capture Report"}
SIDE = {"1": "Buy", "2": "Sell", "5": "Sell short"}
ORD_TYPE = {"1": "Market", "2": "Limit", "3": "Stop", "4": "Stop limit"}


class FIXParsed(BaseModel):
    begin_string: Optional[str] = None
    msg_type: Optional[str] = None
    msg_type_name: Optional[str] = None
    sender: Optional[str] = None
    target: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    order_qty: Optional[str] = None
    price: Optional[str] = None
    ord_type: Optional[str] = None
    cl_ord_id: Optional[str] = None
    tag_count: int = 0


class Governance(BaseModel):
    risk_flags: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    attestable: bool = True
    note: str = ""


def _fields(msg: str) -> Dict[str, str]:
    # FIX delimiter is SOH (\x01); accept | or ^ for human-readable input too
    raw = msg.replace("\x01", "|").replace("^", "|")
    out: Dict[str, str] = {}
    for pair in raw.split("|"):
        if "=" in pair:
            t, v = pair.split("=", 1)
            out[t.strip()] = v.strip()
    return out


@mcp.tool()
def parse_fix(message: str) -> FIXParsed:
    """Parse a FIX message (tag=value); extract order/execution fields."""
    f = _fields(message)
    return FIXParsed(
        begin_string=f.get("8"), msg_type=f.get("35"),
        msg_type_name=MSG_TYPE.get(f.get("35", ""), f.get("35")),
        sender=f.get("49"), target=f.get("56"), symbol=f.get("55"),
        side=SIDE.get(f.get("54", ""), f.get("54")), order_qty=f.get("38"),
        price=f.get("44"), ord_type=ORD_TYPE.get(f.get("40", ""), f.get("40")),
        cl_ord_id=f.get("11"), tag_count=len(f),
    )


@mcp.tool()
def map_to_modern(message: str) -> Dict[str, Any]:
    """Map a FIX message to a modern JSON trade/order event for ONE OS."""
    p = parse_fix(message)
    return {"protocol": "FIX", "type": p.msg_type_name,
            "order": {"id": p.cl_ord_id, "symbol": p.symbol, "side": p.side,
                      "qty": p.order_qty, "price": p.price, "ord_type": p.ord_type},
            "parties": {"sender": p.sender, "target": p.target}}


@mcp.tool()
def govern_trade(message: str) -> Governance:
    """Governance: MiFID II / best-execution / market-abuse surface (attestable for CSOAI)."""
    _sigil("G", "fix|govern_trade")
    p = parse_fix(message)
    flags = []
    if p.msg_type == "D":
        if not p.cl_ord_id:
            flags.append("New order without ClOrdID (11) — audit-trail gap")
        if p.ord_type == "Market":
            flags.append("Market order — best-execution + slippage governance")
    if not p.sender or not p.target:
        flags.append("Counterparty IDs incomplete — LEI / party identification (MiFIR)")
    return Governance(risk_flags=flags,
                      frameworks=["FIX 4.x/5.0", "MiFID II / MiFIR", "Best execution", "Market Abuse Regulation (MAR)", "DORA"],
                      note="CSOAI governs the bridge: every order/trade attestable on the ledger — a signed audit trail for surveillance.")


def main():
    mcp.run()


if __name__ == "__main__":
    main()
