# OpenAPI Union responses accumulate duplicate $ref entries across routes

When you register multiple routes that share an app-level `responses=`
dict containing a Union model (e.g. `Union[ErrorA, ErrorB]`), the generated
OpenAPI schema accumulates duplicate `$ref` entries inside the response's
`anyOf` list, growing by one duplicate per registered route.

Root cause is aliasing: somewhere in the OpenAPI generator a `.copy()` is
producing a shallow copy that still shares the inner `anyOf` list across
routes. Each route registration mutates the same list.

Fix `fastapi/openapi/utils.py` so per-route OpenAPI processing operates on
its own copy of the response definition, not a shared one. Once you trace
the bug to the right `.copy()` call, the fix is one character (`copy` →
`deepcopy`); finding it is the work.
