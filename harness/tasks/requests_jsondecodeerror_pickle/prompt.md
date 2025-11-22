# requests.exceptions.JSONDecodeError can't be unpickled

`requests.exceptions.JSONDecodeError` inherits from both `requests.RequestException`
and the stdlib `json.JSONDecodeError`. The default `__reduce__` method on the resulting
class returns an args tuple that doesn't match `JSONDecodeError.__init__`'s signature,
so `pickle.loads(pickle.dumps(err))` crashes with a TypeError about positional args.

This shows up in real workflows that pass exceptions across process boundaries
(e.g., multiprocessing, distributed task queues, error-reporting middleware).

Fix it so a `JSONDecodeError` instance round-trips cleanly through `pickle`.

The relevant source is in `src/requests/exceptions.py`.
