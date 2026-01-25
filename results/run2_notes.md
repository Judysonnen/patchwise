# run 2 notes

## 2026-01-24

ran the full 4-task eval finally. 64 trajectories, 8 pass, 56 fail. ~102 min wall clock, ~$5 spent.

headline number: tolerant variants pass 5/32, naive variants pass 3/32. that's a +6pp gap in the right direction (tool layer matters), but at n=32 per side with ~10% base rate, the 95% CI on each proportion is ±10pp ish — the gap is directionally supportive, not statistically clean. follow-up run after batch 2 fixtures land should sharpen this.

scaffold gap is literally zero — react and planner both hit 12.5% averaged across tool layers and models. so on this fixture set, the planner-executor doesn't help. and i can't make the "planner wins on multi-file" call because all 4 batch-1 tasks are single-file. that comparison is pending.

resume bullet softened today to drop the unsupported "planner wins multi-file, loses single-file" line. headline finding ("tool layer was the bigger lever") survives — direction is right, just needs more N to be confident.

three things worth flagging:

tolerant catches 127 structured errors (PartialHunkError + LineDriftError) across 32 trajectories, naive throws 15 unstructured ones (mostly MalformedDiff/IndexError). tolerant is doing 8x more work catching agent mistakes — that's the variant's design intent visible in data.

model effect dominates the variant effects — claude solves 6/32, gpt solves 2/32. didn't expect that gap. not in the resume framing (it's about tool layer vs scaffold) but worth flagging. fence-wrapped diffs from claude in my hand-collected failure cases also showed up at much higher rates than gpt — these two might be related, or not.

httpx_send_ignores_client_timeout is 0/16 across all variants and models. suspect the fixture's test asserts both sync and async timeout paths, agent probably only fixes one. need to look at the test before drawing conclusions about that task.

## what's next

- look at httpx test, see if the 0/16 is a fixture issue vs a real "agents can't do this" signal.
- max_steps=20 is saturated almost everywhere (mean tool calls ≈ 17). bumping to 30 might help on the close-but-not-quite trajectories. cheap experiment.
- multi-file scaffold comparison is the actual interesting one and i can't do it until batch 2/3 land. poetry_rstrip and httpx_iter_text are the two genuine multi-source tasks in the pipeline.
