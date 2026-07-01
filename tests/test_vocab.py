from ssotk import vocab


def test_deobfuscate_global_slash():
    # "fkna`k." + key 1 -> "global/" (verified from QC04_Jasper.scene)
    enc = b"fkna`k."
    assert vocab.deobfuscate(enc, 1) == b"global/"


def test_auto_deobfuscate_finds_key_one():
    dec, key = vocab.auto_deobfuscate(b"fkna`k.")
    assert dec == b"global/"
    assert key == 1


def test_auto_deobfuscate_plaintext_key_zero():
    dec, key = vocab.auto_deobfuscate(b"global/Jasper")
    assert dec == b"global/Jasper"
    assert key == 0


def test_auto_deobfuscate_empty_returns_none():
    # Empty input has no key; the fast path must not match on the empty loop.
    assert vocab.auto_deobfuscate(b"") == (b"", None)


def test_name_for_hash_known_and_unknown():
    assert vocab.name_for_hash(0x0B6EF964) == "offset"
    assert vocab.name_for_hash(0xDEADBEEF) == "0xdeadbeef"
