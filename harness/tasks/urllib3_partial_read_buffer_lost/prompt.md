# HTTPResponse.read(amt=None) loses bytes after a partial read with decompression

If you do a partial read on an `HTTPResponse` with a content-encoding (gzip,
deflate, etc.) — e.g., `resp.read(100)` — urllib3's decompressor may produce
more decoded bytes than you asked for, and the extra bytes get buffered.

The bug: a follow-up `resp.read()` (no `amt`, meant to "read the rest") goes
straight to the underlying socket reader without first draining the
decompression buffer. So those buffered bytes are silently lost from the
caller's view.

Fix `src/urllib3/response.py` so `read(amt=None)` drains the decompressed
buffer before reading from the underlying source. Tests cover both the
"buffer was empty" and "buffer had decoded data" paths.
