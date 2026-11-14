# OWNER: P3
"""Replays recorded sessions through the fixed-threshold baseline and full Helm (docs/SPEC.md 12, eval 2).

Writes false triggers per minute for each condition to eval/results/false_triggers.csv. Bootstrap stub.
"""


def main() -> None:
    # TODO(P3): for each recording, replay with helm.mock.ReplaySource(path, realtime=False) through
    # (a) baseline: any raw blendshape score crossing 0.5 fires, and (b) full Helm. Every fire counts.
    raise SystemExit("eval/false_triggers.py is not implemented yet")


if __name__ == "__main__":
    main()
