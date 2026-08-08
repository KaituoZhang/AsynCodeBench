# Commit0 Parsel final review — v0.3

Task: `commit0:parsel`  
Date: 2026-06-26  
Decision: do not construct as a final AsynCodeBench v0.3 task in the current
release pass.

## Reason

`commit0:parsel` has a strong conceptual async shape:

```text
csstranslator / utils / xpathfuncs -> selector public API
```

However, the stripped task ref `origin/commit0_combined` cannot collect any
public evaluator subset that imports `parsel`, because package import calls:

```python
xpathfuncs.setup()
```

and `parsel/xpathfuncs.py` at the stripped ref does not define `setup`.

This blocks even narrow public tests such as:

```text
tests/test_utils.py
tests/test_selector.py
tests/test_selector_csstranslator.py
tests/test_xpathfuncs.py
tests/test_selector_jmespath.py
```

## Why not use a curated bootstrap overlay

`xpathfuncs.setup()` is not a mechanical import shim. It is part of the core
XPath-extension behavior for the task. Pre-filling it would risk giving agents
substantive task behavior before evaluation.

Under the v0.3 data guide, a curated bootstrap may only supply non-substantive
import/class-definition prerequisites. This case does not meet that standard.

## Current status

Keep `commit0:parsel` in backlog. It may become usable later if the benchmark
explicitly supports answer-free bootstrap overlays for substantive import
blockers, but it should not be treated as final AsynCodeBench data now.
