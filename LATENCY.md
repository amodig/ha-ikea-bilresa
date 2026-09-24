# Early first scroll step (experimental fork)

Based on upstream 0.5.0. Emit one notch on the first InitialPress of a scroll
gesture, then subtract that notch from subsequent cumulative counts. Repeated
InitialPress events within the gesture do not add steps. Button behavior and
the existing post-press rotation suppression are unchanged.

Five single-notch observations from Matter Server receive/command logs showed:

| Sample | InitialPress to Complete | Complete to first lamp command |
| --- | ---: | ---: |
| 1 | 470 ms | 27 ms |
| 2 | 541 ms | 26 ms |
| 3 | 502 ms | 27 ms |
| 4 | 494 ms | 25 ms |
| 5 | 494 ms | 30 ms |

These are baseline server timestamps, not physical wheel-to-light measurements.
The patch removes waiting for Complete for the first step; actual improvement
still requires an installed hardware test. Continuous rotation still depends
on batched device reports. Later testing also showed a delayed Complete arriving
with the next gesture, so a fixed 500 ms hardware latency is not assumed.

Validation: existing pytest suite plus regression checks for immediate first
step, repeated InitialPress, cumulative counts, both directions, and reset.
Run `pytest -q` with the dependencies from `requirements-test.txt` installed.

Rollback: reinstall upstream 0.5.0 and restart Home Assistant. No configuration
schema or stored data is changed by this fork.
