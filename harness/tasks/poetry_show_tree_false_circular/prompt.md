# poetry show --tree falsely reports shared dependencies as circular

`poetry show --tree` walks the dependency graph and tracks "visited" packages
to detect cycles. The bug: visited entries are appended on entry into a
subtree but never popped on exit. So a package that legitimately appears as
a shared dependency of two sibling subtrees gets flagged as circular on the
second visit.

This produces noisy false positives in the tree output that look like real
circular-import bugs but aren't.

Fix `src/poetry/console/commands/show.py`. The visited tracker should follow
ancestor-only semantics (so only true cycles are flagged). Switching to a
set with try/finally pop semantics is one way; you'll find the right shape
when you read the existing walk.
