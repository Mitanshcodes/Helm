<!-- OWNER: P3 -->
# Evaluation protocol

How to run each evaluation, step by step. The design is in `docs/SPEC.md` section 12. Raw data goes in
`eval/results/*.csv`; `eval/analysis.py` turns it into the three charts.

Every reported number needs a participant count, a median and a baseline. No participant had a motor
impairment; the restricted-range condition is a proxy.

## 1. Latency, motion to screen

TODO(P3): setup, filming, frame counting, the real-controller baseline, the CSV columns.

## 2. False triggers per minute

TODO(P3): calibrate, record negatives, the three one-minute tasks, how to run `false_triggers.py`.

## 3. Target test with restricted movement

TODO(P3): conditions (c) and (d), recalibration to the small range, trial counts, throughput formula.

## Also logged

TODO(P3): leave-one-take-out accuracy per participant, median time from launch to first race.
