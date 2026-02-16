# APIRouter silently drops on_startup and on_shutdown handlers

If you pass `on_startup` or `on_shutdown` callables when constructing an
`APIRouter`, they get silently dropped — the handlers never fire on app
startup or shutdown. Lifespan-style apps don't notice; the bug only bites
the older event-handler style.

The cause is initialization ordering: `APIRouter.__init__` assigns these
attributes before delegating to its parent `__init__`, and the parent
clobbers them with empty defaults.

Fix `fastapi/routing.py` so user-passed `on_startup` / `on_shutdown` lists
survive parent initialization. The fix is a small reorder, but you need to
recognize that the parent class is the one wiping the attributes — reading
just `APIRouter.__init__` in isolation isn't enough.
