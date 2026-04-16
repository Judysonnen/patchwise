# httpx Response.iter_text() emits spurious empty strings

`Response.iter_text()` is supposed to yield decoded text chunks. The current
implementation can yield empty strings for chunks that decode to nothing
(e.g., a multi-byte UTF-8 sequence split across two raw chunks where the
first chunk holds only continuation bytes and decodes to empty before the
next chunk arrives).

Downstream code that does `for chunk in resp.iter_text(): assert chunk` or
joins text fragments with separators gets surprising behavior. The decoder
should buffer until it has a non-empty decoded result before yielding.

Fix touches both `httpx/_decoders.py` (the decoder needs to skip yielding
empty results) and `httpx/_models.py` (where iter_text dispatches into the
decoder). Tests live in `tests/test_decoders.py`.
