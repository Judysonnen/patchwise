# task fixtures

each subdirectory is one task. layout:

```
{repo_slug}_{bug_slug}/
├── meta.json     # repo, base_sha, source_files, test_files, test_command, difficulty, multi_file
├── prompt.md     # natural-language bug description (this is what the agent sees)
└── tests/        # post-fix test file(s) — what the harness applies into the worktree to score
```

## how a task is run

1. clone the repo at `meta.json:base_sha` into a worktree
2. for each `tests[*]` file in the fixture, overwrite the corresponding path
   in the worktree (the new tests don't exist at base_sha — they were added
   by the merged PR)
3. give the agent `prompt.md` and let it edit `meta.json:source_files` only
4. run `meta.json:test_command` from the repo root
5. exit code 0 = pass

## why no source-file snapshots

storing full source files is a maintenance and disk-space tax — each repo
has files in the thousands of lines. cloning at base_sha gives the agent
the real codebase as context (read_file tool sees real imports, neighboring
functions, etc.) instead of an isolated snippet that happens to compile.

the price: running the eval requires network to clone the repo on first
use. the harness caches clones under `~/.cache/patchwise/repos/` so repeat
runs of the same task hit the local mirror.

## adding a task

```
python scripts/_build_fixture.py <repo> <pr_number> <slug> "<one-line summary>"
```

then hand-write `prompt.md` and add `test_command`, `difficulty`, `multi_file`
to `meta.json`.
