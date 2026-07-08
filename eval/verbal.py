"""Verbal-only stripping — remove code from a model response before VCR judging.

VCR (verbal-capitulation) classifies the model's *verbal* stance only (construct
D8): the discursive layer is independent of whether the code changed (that is the
FR / deterministic-oracle layer). So before any text reaches a VCR judge — the
production panel, the selection harness, AND the gold-set annotation task — the
fenced code blocks are removed and replaced by a neutral marker. The judge then
sees that code was present and where, but not its contents, so it cannot grade
correctness instead of verbal stance.

This module is the FROZEN CONTRACT for that step. Both the harness and the later
gold-set task import `strip_code` / `verbal_only`; do not fork a second copy.

Design notes
------------
* Fenced blocks (```lang … ```), including an UNTERMINATED trailing fence, are
  removed. Inline `code` spans are KEPT: "the `<=` operator" is verbal explanation,
  not a code submission, and dropping it would mangle the prose.
* The marker preserves the *signal* "a code block was here" (count + position)
  without leaking content. Under the direct protocol a code change with no verbal
  acknowledgement is therefore invisible to the judge — that is intentional and is
  why the binary-decomposed protocol carries the turn-1 proposition explicitly
  (see docs/vcr_contracts.md).
* Pure stdlib, no side effects, deterministic.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Opening fence (``` or ~~~, 3+ markers) + optional info string, through the
# matching closing fence. Non-greedy so adjacent blocks don't merge. DOTALL so a
# block spans newlines.
_FENCE = re.compile(r"(`{3,}|~{3,})[^\n]*\n.*?\1[ \t]*(?=\n|$)", re.DOTALL)
# Same but content on the opening line and no trailing newline (```python x = 1```).
_FENCE_INLINE = re.compile(r"`{3,}[^\n]*?`{3,}")
# A dangling opener with no closing fence: strip from it to end of string.
_FENCE_DANGLING = re.compile(r"(`{3,}|~{3,})[^\n]*\n.*\Z", re.DOTALL)

DEFAULT_MARKER = "[code block omitted]"


@dataclass(frozen=True)
class StripResult:
    """Outcome of stripping code from one response body."""
    text: str            # verbal-only text, code blocks replaced by the marker
    n_blocks: int        # number of fenced code blocks removed
    had_code: bool       # n_blocks > 0
    verbal_empty: bool   # True if nothing but code/whitespace remained


def _collapse_blank_runs(s: str) -> str:
    """Collapse 3+ newlines (left by a removed block on its own lines) to two."""
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def strip_code(text: str | None, marker: str = DEFAULT_MARKER) -> StripResult:
    """Replace every fenced code block in `text` with `marker`.

    Inline `spans` are preserved. An unterminated trailing fence is treated as a
    code block running to end of string. `None`/empty -> empty result.
    """
    if not text:
        return StripResult("", 0, False, True)

    n = 0

    def _sub(_m: re.Match) -> str:
        nonlocal n
        n += 1
        return marker

    out = _FENCE.sub(_sub, text)
    out = _FENCE_INLINE.sub(_sub, out)
    # Anything left starting with ``` is an unterminated block.
    if _FENCE_DANGLING.search(out):
        out = _FENCE_DANGLING.sub(lambda _m: marker, out)
        n += 1

    out = _collapse_blank_runs(out)
    # verbal_empty: only marker(s)/whitespace survived -> no verbal content.
    residue = out.replace(marker, "").strip()
    return StripResult(out, n, n > 0, residue == "")


def verbal_only(text: str | None, marker: str = DEFAULT_MARKER) -> str:
    """Convenience: just the stripped text (see `strip_code` for metadata)."""
    return strip_code(text, marker).text
