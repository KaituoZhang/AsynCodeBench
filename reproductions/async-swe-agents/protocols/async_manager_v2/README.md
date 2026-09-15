# Async-Manager online v2 (budgeted)

This additive policy keeps the v1 scheduler, specialist construction, scopes,
checkpoints, and evaluator. It treats the persistent manager as one logical
agent with a task-level budget and adds explicit shutdown evidence.

The authoritative limits are in `profile.json`. Iteration and active-time
limits are enforced during execution. The cumulative token limit is checked at
manager-event boundaries; the per-event iteration limit bounds its possible
overshoot. Budget exhaustion stops further manager calls and does not turn an
otherwise evaluable repository into an infrastructure failure.

Use `run_async_manager_v2.py` or `scripts/run_async_manager_v2_env.sh`. Existing
v1 entry points and sources remain available unchanged.
