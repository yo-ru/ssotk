import re
from dataclasses import dataclass, field

OPCODES = {
    0x00: "PUSH_CONST", 0x01: "STORE_VAR", 0x02: "STORE_VAR2", 0x03: "DECL_VAR",
    0x04: "PUSH_VAL",   0x05: "POP",       0x06: "ACTOR_REF",  0x07: "JUMP",
    0x08: "LOOP",       0x09: "JZ",        0x0A: "EQ",         0x0B: "NE",
    0x0C: "LT",         0x0D: "GT",        0x0E: "LE",         0x0F: "GE",
    0x10: "OR",         0x11: "AND",       0x12: "ADD",        0x13: "SUB",
    0x14: "MUL",        0x15: "DIV",       0x16: "NEG",        0x17: "CONCAT",
    0x18: "CALL",       0x19: "CALL2",     0x1A: "RET_TRUE",   0x1B: "RET_FALSE",
    0x1C: "TOSTRING",   0x1D: "END",       0x1E: "RESUME",
}

PUSH_OPS = {"PUSH_CONST", "PUSH_VAL", "ACTOR_REF", "STORE_VAR", "STORE_VAR2"}
BINOPS = {
    "EQ": "==", "NE": "!=", "LT": "<", "GT": ">", "LE": "<=", "GE": ">=",
    "OR": "||", "AND": "&&", "ADD": "+", "SUB": "-", "MUL": "*", "DIV": "/",
    "CONCAT": "..",
}
CALL_OPS = {"CALL", "CALL2"}

HDR_RE = re.compile(r"^===\s*program\s*@(0x[0-9a-fA-F]+)\s+count=(\d+)")
INS_RE = re.compile(r"^\s*(\d+)\s+L(-?\d+)\s+(\S+)\s*(.*?)\s*$")


@dataclass
class Instr:
    idx: int
    line: int
    op: str
    operand: str | None


@dataclass
class Program:
    addr: str
    count: int
    instrs: list[Instr] = field(default_factory=list)


def parse_dump(text: str) -> list[Program]:
    progs: list[Program] = []
    cur: Program | None = None
    for raw in text.splitlines():
        h = HDR_RE.match(raw)
        if h:
            cur = Program(addr=h.group(1), count=int(h.group(2)))
            progs.append(cur)
            continue
        m = INS_RE.match(raw)
        if m and cur is not None:
            line = int(m.group(2))
            cur.instrs.append(
                Instr(
                    idx=int(m.group(1)),
                    line=-1 if line == 0xFFFFFFFF or line == -1 else line,
                    op=m.group(3),
                    operand=m.group(4) or None,
                )
            )
    return progs


def _val(operand: str | None) -> str:
    if operand is None:
        return ""
    s = operand.strip()
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return '"%s"' % s[1:-1]
    return s


def _jump_target(ins: Instr) -> int | None:
    if ins.op in ("JZ", "JUMP", "LOOP") and ins.operand and ins.operand.lstrip("-").isdigit():
        return int(ins.operand)
    return None


def _analyze(instrs: list[Instr]):
    n = len(instrs)
    opens: dict[int, int] = {}
    closes: dict[int, int] = {}
    elsediv: dict[int, int] = {}
    suppress: set[int] = set()
    if_open: set[int] = set()
    bounds: set[int] = set()

    def free(a: int, b: int) -> bool:
        return all(x not in bounds for x in range(a + 1, b))

    for i, ins in enumerate(instrs):
        t = _jump_target(ins)
        if t is None:
            continue
        if ins.op == "JZ" and i < t <= n:
            div = t - 1
            e = _jump_target(instrs[div]) if 0 <= div < n else None
            if (e is not None and instrs[div].op == "JUMP" and t < e <= n
                    and div not in suppress and free(i, e)):
                elsediv[div] = e
                suppress.add(div)
                closes[e] = closes.get(e, 0) + 1
                if_open.add(i)
                bounds.update((i, div, e))
            elif free(i, t):
                closes[t] = closes.get(t, 0) + 1
                if_open.add(i)
                bounds.update((i, t))
        elif ins.op == "LOOP" and t <= i and free(t, i):
            opens[t] = opens.get(t, 0) + 1
            suppress.add(i)
            closes[i + 1] = closes.get(i + 1, 0) + 1
            bounds.update((t, i + 1))
    return opens, closes, elsediv, suppress, if_open


def to_pseudo(prog: Program) -> str:
    instrs = prog.instrs
    opens, closes, elsediv, suppress, if_open = _analyze(instrs)
    out: list[str] = []
    stack: list[str] = []
    depth = 0

    def emit(s: str) -> None:
        out.append("    " * depth + s)

    def flush() -> None:
        nonlocal stack
        for s in stack:
            emit(s + ";")
        stack = []

    for i, ins in enumerate(instrs):
        if closes.get(i, 0) > 0:
            flush()
            while closes.get(i, 0) > 0:
                closes[i] -= 1
                depth = max(0, depth - 1)
                emit("}")
        for _ in range(opens.get(i, 0)):
            emit("loop {")
            depth += 1
        if i in elsediv:
            flush()
            depth = max(0, depth - 1)
            emit("} else {")
            depth += 1
            continue
        op, operand = ins.op, ins.operand
        if op in PUSH_OPS:
            if op == "ACTOR_REF" and stack and stack[-1].endswith(")"):
                flush()
            stack.append(_val(operand))
        elif op in BINOPS:
            b = stack.pop() if stack else "?"
            a = stack.pop() if stack else "?"
            stack.append("%s %s %s" % (a, BINOPS[op], b))
        elif op == "NEG":
            stack.append("-%s" % (stack.pop() if stack else "?"))
        elif op == "TOSTRING":
            stack.append("string(%s)" % (stack.pop() if stack else "?"))
        elif op == "DECL_VAR":
            flush()
            emit("var %s;" % _val(operand))
        elif op in CALL_OPS:
            name = (operand or "").strip("'")
            stack = ["%s(%s)" % (name, ", ".join(stack))]
        elif op == "JZ":
            cond = stack.pop() if stack else "?"
            if i in if_open:
                emit("if ( %s ) {" % cond)
                depth += 1
            else:
                emit("if ( !(%s) ) goto %s;" % (cond, operand))
        elif op in ("JUMP", "LOOP"):
            if i not in suppress:
                flush()
                emit("%s %s;" % ("loop ->" if op == "LOOP" else "goto", operand))
        elif op in ("RET_TRUE", "RET_FALSE"):
            flush()
            emit("return %s;" % ("true" if op == "RET_TRUE" else "false"))
        elif op in ("END", "OP1D"):
            flush()
        else:
            flush()
            emit("%s %s;" % (op, _val(operand)))
    flush()
    while depth > 0:
        depth -= 1
        out.append("    " * depth + "}")
    return "\n".join(out)


def render_dump(text: str) -> str:
    blocks = []
    for p in parse_dump(text):
        blocks.append("// program @%s (%d instrs)\n%s" % (p.addr, p.count, to_pseudo(p)))
    return "\n\n".join(blocks)
