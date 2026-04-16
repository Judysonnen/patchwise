# poetry uses str.rstrip(".tar.gz") which eats alpha-version letters

`str.rstrip(".tar.gz")` doesn't strip the LITERAL suffix ".tar.gz" — it
strips any of the characters in that string, individually, from the right.
So `"pkg-1.0a.tar.gz".rstrip(".tar.gz")` returns `"pkg-1.0"` (the trailing
`a` from `1.0a` is treated as one of the characters to strip), and
`"pkg-1.0rc1.tar.gz".rstrip(".tar.gz")` becomes `"pkg-1.0rc"` (the `1` got
stripped too).

This corrupts package version detection for any pre-release version that
ends in a character that happens to appear in the suffix string.

This is the classic `str.rstrip` vs `str.removesuffix` confusion. Fix the
two call sites in `src/poetry/inspection/info.py` and
`src/poetry/installation/chef.py`.
