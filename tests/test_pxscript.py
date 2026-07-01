from ssotk import pxscript

# Two real programs captured from the live PXScript VM (SSOClient.exe).
DUMP = """\
=== program @0x10ed29ef8  count=5 ===
     0  L1     ACTOR_REF  'this/parent'
     1  L1     PUSH_VAL   'Stop'
     2  L1     ACTOR_REF  'global/PlayerActions'
     3  L1     CALL2      'RunScriptEx'
     4  L-1    END        <t0>

=== program @0xd3c0d858  count=9 ===
     0  L26    ACTOR_REF  'global/CurrentRHand/ParticleSystem'
     1  L26    ACTOR_REF  'sys'
     2  L26    CALL2      'ObjectExists'
     3  L26    PUSH_VAL   0
     4  L26    GT         <t0>
     5  L26    JZ         8
     6  L28    ACTOR_REF  'global/CurrentRHand/ParticleSystem'
     7  L28    CALL2      'Stop'
     8  L-1    END        <t0>
"""


def test_parse_dump_reads_programs_and_instrs():
    progs = pxscript.parse_dump(DUMP)
    assert len(progs) == 2
    assert progs[0].addr == "0x10ed29ef8"
    assert progs[0].count == 5
    assert len(progs[0].instrs) == 5
    assert progs[0].instrs[3].op == "CALL2"
    assert progs[0].instrs[3].operand == "'RunScriptEx'"
    # the END terminator's raw line 0xffffffff normalizes to -1
    assert progs[0].instrs[4].op == "END"
    assert progs[0].instrs[4].line == -1


def test_to_pseudo_folds_call_into_statement():
    prog = pxscript.parse_dump(DUMP)[0]
    src = pxscript.to_pseudo(prog)
    assert src == 'RunScriptEx("this/parent", "Stop", "global/PlayerActions");'


def test_to_pseudo_reconstructs_if_block_with_condition():
    prog = pxscript.parse_dump(DUMP)[1]
    src = pxscript.to_pseudo(prog)
    lines = src.splitlines()
    # JZ folds into an if whose condition keeps the call + comparison
    assert lines[0] == 'if ( ObjectExists("global/CurrentRHand/ParticleSystem", "sys") > 0 ) {'
    assert lines[1] == '    Stop("global/CurrentRHand/ParticleSystem");'
    assert lines[-1] == "}"


IF_ELSE = """\
=== program @0xabc count=12 ===
     0  L1  ACTOR_REF  'x'
     1  L1  ACTOR_REF  'sys'
     2  L1  CALL2      'ObjectExists'
     3  L1  PUSH_VAL   0
     4  L1  GT         <t0>
     5  L1  JZ         9
     6  L2  ACTOR_REF  'x'
     7  L2  CALL2      'Start'
     8  L2  JUMP       11
     9  L4  ACTOR_REF  'x'
    10  L4  CALL2      'Stop'
    11  L-1 END        <t0>
"""


def test_to_pseudo_folds_jump_into_if_else():
    src = pxscript.to_pseudo(pxscript.parse_dump(IF_ELSE)[0])
    assert src == (
        'if ( ObjectExists("x", "sys") > 0 ) {\n'
        '    Start("x");\n'
        "} else {\n"
        '    Stop("x");\n'
        "}"
    )
    assert "goto" not in src  # the dividing JUMP is folded, not left as goto


def test_render_dump_emits_every_program():
    out = pxscript.render_dump(DUMP)
    assert "// program @0x10ed29ef8" in out
    assert "// program @0xd3c0d858" in out
    assert "RunScriptEx(" in out
