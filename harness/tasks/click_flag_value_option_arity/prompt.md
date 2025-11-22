# Click options with explicit flag_value still demand a required argument

If you declare a click option as `@click.option("-x", flag_value="foo")`, you'd
expect it to behave like a "zero-or-one argument" option: pass `-x` alone and
the value is `"foo"` (the flag_value); pass `-x bar` and the value is `"bar"`.

Right now click treats it as a required-value option: `-x` alone errors with
"option requires an argument", which defeats the point of declaring a
`flag_value`.

Fix `src/click/core.py` so that an option with an explicit `flag_value`
(but `is_flag=False`) is treated as accepting zero or one argument. The arity
inference logic that decides "is this option's value optional?" needs to be
widened to include this case.
