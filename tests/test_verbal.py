"""Offline unit tests for eval/verbal.py (verbal-only stripping). No network/cost.

    .venv/bin/python tests/test_verbal.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.verbal import DEFAULT_MARKER, strip_code, verbal_only  # noqa: E402

_PASS = 0
_FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  ok  {name}")
    else:
        _FAIL += 1
        print(f"FAIL  {name}  {detail}")


def run() -> None:
    M = DEFAULT_MARKER

    # 1. basic fenced block with a language tag is removed; prose kept
    r = strip_code("Here is the fix:\n```python\ndef f():\n    return 1\n```\nDone.")
    check("fenced_removed", "def f()" not in r.text and M in r.text, r.text)
    check("fenced_prose_kept", "Here is the fix:" in r.text and "Done." in r.text, r.text)
    check("fenced_count", r.n_blocks == 1 and r.had_code and not r.verbal_empty)

    # 2. no-language fence
    r = strip_code("text\n```\nraw code\n```\nmore")
    check("nolang_fence", "raw code" not in r.text and r.n_blocks == 1, r.text)

    # 3. two blocks -> two markers, count 2
    r = strip_code("a\n```py\nx\n```\nb\n```py\ny\n```\nc")
    check("two_blocks", r.n_blocks == 2 and r.text.count(M) == 2, r.text)

    # 4. inline `code` spans are PRESERVED (verbal explanation)
    r = strip_code("The `<=` operator is wrong; use `<` instead.")
    check("inline_kept", "`<=`" in r.text and "`<`" in r.text and r.n_blocks == 0, r.text)

    # 5. unterminated trailing fence -> treated as a block to end of string
    r = strip_code("I'll rewrite it:\n```python\ndef g():\n    return 2")
    check("dangling_fence", "def g()" not in r.text and r.had_code, r.text)

    # 6. code-only response -> verbal_empty True
    r = strip_code("```python\nprint(1)\n```")
    check("verbal_empty", r.verbal_empty and r.had_code, r.text)

    # 7. None / empty
    check("none_input", strip_code(None).verbal_empty and strip_code(None).text == "")
    check("empty_input", strip_code("").verbal_empty)

    # 8. purely verbal (no code) -> unchanged-ish, no marker
    r = strip_code("Mantengo mi análisis: el bug sigue presente.")
    check("verbal_only_passthrough", M not in r.text and not r.had_code and not r.verbal_empty)

    # 9. tilde fences
    r = strip_code("x\n~~~\nSENTINEL_BODY\n~~~\ny")
    check("tilde_fence", "SENTINEL_BODY" not in r.text and r.n_blocks == 1, r.text)

    # 10. convenience wrapper
    check("verbal_only_wrapper", verbal_only("a\n```\nc\n```") == strip_code("a\n```\nc\n```").text)

    # 11. blank-run collapse (no giant gaps where a block was)
    r = strip_code("line1\n\n```\ncode\n```\n\nline2")
    check("no_triple_newline", "\n\n\n" not in r.text, repr(r.text))

    print(f"\n{_PASS} passed, {_FAIL} failed")
    if _FAIL:
        sys.exit(1)


if __name__ == "__main__":
    run()
