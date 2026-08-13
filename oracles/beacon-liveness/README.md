# oracles/beacon-liveness

**Claim under test:** every live, page-bearing ship actually *fires a countable
first-party beacon* when a browser loads it.

**Method:** none of it is static analysis. `public/` is served locally, each page is
loaded in Chromium (Playwright), and the beacon is observed **at the receiving end** —
the local server plays the worker for `/_b` and keeps the bytes, because `sendBeacon`
ships a Blob and Playwright reports `post_data == None` for exactly the request this
oracle exists to see.

```
python3 oracles/beacon-liveness/oracle.py            # 0 PASS · 1 FAIL · 2 CANNOT-CERTIFY
python3 oracles/beacon-liveness/probe.py             # probe-the-oracle, 23 controls
```

`probe.py` is not a test suite for the pages — it is the negative-control harness for
the **oracle**, required by PLAYBOOK §ARCHITECT. Every predicate has a control that
flips it, and clause (b)'s surviving breaks are recorded as KNOWN LIMITS in
`oracle.py`'s docstring rather than left implicit.

**Dependency:** `pip install playwright --break-system-packages`, with Chromium at
`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers` (pre-installed in the sandbox). Absent a
browser the oracle returns **CANNOT-CERTIFY**, never PASS.
