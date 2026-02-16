# Pydantic Json[T] in Form/Query/Header/Cookie wrapped in list before parsing

If you declare a parameter as `field: Json[MyModel] = Form(...)` (or `Query`,
`Header`, `Cookie`), FastAPI calls `getlist()` on the underlying multidict —
treating the JSON-typed field as if it were a multi-value sequence. The
result is `["{\\"foo\\": 1}"]` (the JSON string wrapped in a list) being
passed to the JSON parser, which then fails or produces garbage.

What should happen: `Json[T]` is a single-value type. FastAPI should call
the singular `get()` (not `getlist()`) when the annotation is a Json wrapper,
regardless of the surrounding parameter source.

Fix `fastapi/dependencies/utils.py` so the multi-value detection logic
recognizes `Json[T]` and routes through the singular-get path. Tests cover
all four sources (Form / Query / Header / Cookie).
