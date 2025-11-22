# client.send() ignores configured timeout for raw Request objects

When you do `client.build_request(...)` and then `client.send(req)`, the request
gets the client's configured timeout applied. But if you construct an `httpx.Request`
directly and pass it to `client.send()`, the timeout doesn't get attached, so the
request uses httpx's default timeout instead of the client's.

Both code paths should produce the same effective timeout. The asymmetry is a
gotcha that has burned a couple of users in the issue tracker.

Fix `httpx/_client.py` so that `client.send(request)` applies the client's
timeout regardless of how the `Request` was constructed. There are sync and
async send paths; both need the same treatment (a small helper or inlined
logic in both).
