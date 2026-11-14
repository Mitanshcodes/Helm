# OWNER: P3
"""Reads eval/results/*.csv, writes the three charts as PNG and prints the headline numbers (docs/SPEC.md 12).

Inputs (all in eval/results/, any missing one is reported as "not measured" rather than guessed):
  latency.csv            participant,condition,trial,frames[,fps]   condition: helm | controller; fps default 240
  software_latency.csv   participant,total_ms                       optional: Helm's logged median total latency
  false_triggers.csv     written by eval/false_triggers.py
  target_*.csv           downloaded from eval/target_test.html      condition: helm (c) | fixed (d) | mouse
  participants.csv       participant,loto_accuracy,launch_to_race_s optional extras for the slide footnotes

Outputs: latency.png, false_triggers.png, throughput.png and headline.json in eval/results/, plus the numbers
printed with participant counts, medians and baselines, and the block to paste into ui/src/results.ts.

    python eval/analysis.py [--results eval/results]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HELM = "#2457e6"          # the dashboard's accent; validated against BASE for colour-vision deficiency
BASE = "#eb6834"
INK, MUTED, GRID = "#1c2026", "#5a6170", "#e4e0d8"


# ------------------------------------------------------------------ reading

def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return [{k.strip(): (v or "").strip() for k, v in row.items() if k} for row in csv.DictReader(fh)]


def p90(values: list[float]) -> float:
    v = sorted(values)
    k = 0.9 * (len(v) - 1)
    lo, hi = math.floor(k), math.ceil(k)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


# ------------------------------------------------------------------ the three measures

def latency(rows: list[dict]) -> dict:
    """Motion to screen in ms, from frame counts of a high-speed video: pooled median and 90th percentile."""
    out: dict = {}
    for condition in ("helm", "controller"):
        ms = [float(r["frames"]) * 1000.0 / float(r.get("fps") or 240) for r in rows
              if r.get("condition") == condition and r.get("frames")]
        people = {r["participant"] for r in rows if r.get("condition") == condition and r.get("frames")}
        if ms:
            out[condition] = {"median_ms": statistics.median(ms), "p90_ms": p90(ms), "trials": len(ms),
                              "participants": len(people), "values": ms}
    return out


def false_triggers(rows: list[dict]) -> dict:
    """Per participant: all fires over all minutes; then the median across participants."""
    out: dict = {}
    for condition in ("baseline", "helm"):
        per: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
        for r in rows:
            if r.get("condition") == condition:
                per[r["participant"]][0] += float(r["fires"])
                per[r["participant"]][1] += float(r["minutes"])
        rates = {p: f / m for p, (f, m) in per.items() if m > 0}
        if rates:
            out[condition] = {"median_per_min": statistics.median(rates.values()), "participants": len(rates),
                              "per_participant": rates}
    return out


def block_throughput(trials: list[dict]) -> float | None:
    """ISO 9241-9 effective throughput of one block: TP = IDe / MT, IDe = log2(Ae / We + 1), We = 4.133 * SDx,
    where dx is each selection's offset from the target centre along the movement axis."""
    dx, ae, mt = [], [], []
    for t in trials:
        fx, fy, tx, ty = (float(t[k]) for k in ("from_x", "from_y", "to_x", "to_y"))
        sx, sy = float(t["sel_x"]), float(t["sel_y"])
        a = math.hypot(tx - fx, ty - fy) or 1.0
        d = ((sx - tx) * (tx - fx) + (sy - ty) * (ty - fy)) / a
        dx.append(d)
        ae.append(a + d)
        mt.append(float(t["mt_ms"]) / 1000.0)
    if len(dx) < 2:
        return None
    we = 4.133 * statistics.stdev(dx)
    if we <= 0 or statistics.mean(mt) <= 0:
        return None
    return math.log2(statistics.mean(ae) / we + 1) / statistics.mean(mt)


def throughput(rows: list[dict]) -> dict:
    """Per participant and condition: mean of the block throughputs; then the median across participants."""
    blocks: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for r in rows:
        blocks[(r["participant"], r["condition"], r["block"])].append(r)
    per: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for (participant, condition, _), trials in blocks.items():
        tp = block_throughput(trials)
        if tp is not None:
            per[condition][participant].append(tp)
    out: dict = {}
    for condition, people in per.items():
        means = {p: statistics.mean(v) for p, v in people.items()}
        errors = [1 - float(r["hit"]) for r in rows if r["condition"] == condition]
        out[condition] = {"median_bits_per_s": statistics.median(means.values()), "participants": len(means),
                          "per_participant": means, "error_rate": statistics.mean(errors) if errors else None}
    return out


# ------------------------------------------------------------------ charts

def _style(ax, title: str, xlabel: str) -> None:
    ax.set_title(title, loc="left", fontsize=13, color=INK, pad=12)
    ax.set_xlabel(xlabel, color=MUTED)
    ax.grid(axis="x", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)


def chart_latency(lat: dict, out: Path) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 3.2), dpi=160)
    rows = [("controller", "Real controller (finger)", BASE), ("helm", "Helm (eyebrow raise)", HELM)]
    rows = [r for r in rows if r[0] in lat]
    for y, (key, label, color) in enumerate(rows):
        values = lat[key]["values"]
        jitter = [y + ((i * 0.37) % 1 - 0.5) * 0.28 for i in range(len(values))]
        ax.scatter(values, jitter, s=40, color=color, alpha=0.75, edgecolors="white", linewidths=1.5, zorder=3)
        med = lat[key]["median_ms"]
        ax.plot([med, med], [y - 0.32, y + 0.32], color=INK, linewidth=2, zorder=4)
        ax.annotate(f"median {med:.0f} ms", (med, y + 0.36), color=INK, fontsize=10, ha="center", va="bottom")
    ax.set_yticks(range(len(rows)), [r[1] for r in rows], color=INK)
    ax.set_ylim(-0.7, len(rows) - 0.2)
    ax.set_xlim(left=0)
    _style(ax, "Motion to screen latency", "milliseconds (each dot is one press, filmed at 240 fps)")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def chart_paired(per_base: dict, per_helm: dict, base_label: str, helm_label: str, title: str, xlabel: str,
                 out: Path, higher_is_better: bool) -> None:
    """One row per participant: baseline dot, Helm dot, joined. Median row on top."""
    import matplotlib.pyplot as plt

    people = sorted(set(per_base) & set(per_helm))
    rows = [("Median", statistics.median(per_base[p] for p in people), statistics.median(per_helm[p] for p in people))]
    rows += [(p, per_base[p], per_helm[p]) for p in people]
    fig, ax = plt.subplots(figsize=(8, 0.55 * len(rows) + 1.6), dpi=160)
    for y, (name, b, h) in enumerate(reversed(rows)):
        bold = name == "Median"
        ax.plot([b, h], [y, y], color=GRID, linewidth=3, zorder=2, solid_capstyle="round")
        ax.scatter([b], [y], s=90 if bold else 60, color=BASE, edgecolors="white", linewidths=2, zorder=3)
        ax.scatter([h], [y], s=90 if bold else 60, color=HELM, edgecolors="white", linewidths=2, zorder=3)
        if bold:
            ax.annotate(f"{h:.2f}", (h, y), xytext=(0, 9), textcoords="offset points", ha="center", color=INK, fontsize=10)
            ax.annotate(f"{b:.2f}", (b, y), xytext=(0, 9), textcoords="offset points", ha="center", color=INK, fontsize=10)
    labels = [r[0] for r in reversed(rows)]
    ax.set_yticks(range(len(rows)), labels, color=INK)
    for tick in ax.get_yticklabels():
        if tick.get_text() == "Median":
            tick.set_fontweight("bold")
    ax.set_ylim(-0.6, len(rows) - 0.3)
    ax.set_xlim(left=0)
    ax.scatter([], [], color=BASE, label=base_label)
    ax.scatter([], [], color=HELM, label=helm_label)
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=2, frameon=False, labelcolor=INK,
              handletextpad=0.3, columnspacing=1.2)
    _style(ax, title, xlabel + ("  (higher is better)" if higher_is_better else "  (lower is better)"))
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


# ------------------------------------------------------------------ report

def results_ts(head: dict) -> str:
    def entry(key: str, helm, base, n) -> str:
        fmt = lambda v: "null" if v is None else f"{v:.2f}".rstrip("0").rstrip(".")
        return f"  {key}: {{ helm: {fmt(helm)}, baseline: {fmt(base)}, participants: {n if n else 'null'} }},"
    lat, ft, tp = head.get("latency", {}), head.get("false_triggers", {}), head.get("throughput", {})
    return "\n".join([
        entry("latency", lat.get("helm", {}).get("median_ms"), lat.get("controller", {}).get("median_ms"),
              lat.get("helm", {}).get("participants")),
        entry("falseTriggers", ft.get("helm", {}).get("median_per_min"), ft.get("baseline", {}).get("median_per_min"),
              ft.get("helm", {}).get("participants")),
        entry("throughput", tp.get("helm", {}).get("median_bits_per_s"), tp.get("fixed", {}).get("median_bits_per_s"),
              tp.get("helm", {}).get("participants")),
    ])


def main(argv: list[str] | None = None) -> dict:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--results", type=Path, default=ROOT / "eval" / "results")
    args = p.parse_args(argv)
    res: Path = args.results

    head: dict = {}
    lat = latency(read_csv(res / "latency.csv"))
    ft = false_triggers(read_csv(res / "false_triggers.csv"))
    target_rows = [r for f in sorted(res.glob("target_*.csv")) for r in read_csv(f)]
    tp = throughput(target_rows)
    software = [float(r["total_ms"]) for r in read_csv(res / "software_latency.csv") if r.get("total_ms")]
    extras = read_csv(res / "participants.csv")

    lines = []
    if lat:
        head["latency"] = {k: {kk: vv for kk, vv in v.items() if kk != "values"} for k, v in lat.items()}
        for key, label in (("helm", "Helm"), ("controller", "real controller")):
            if key in lat:
                v = lat[key]
                lines.append(f"Latency, {label}: median {v['median_ms']:.0f} ms, p90 {v['p90_ms']:.0f} ms "
                             f"({v['trials']} presses, n={v['participants']})")
        chart_latency(lat, res / "latency.png")
    else:
        lines.append("Latency: not measured (eval/results/latency.csv missing)")
    if software:
        head["software_latency_ms"] = {"median": statistics.median(software), "participants": len(software)}
        lines.append(f"Software latency (capture to pad write): median {statistics.median(software):.1f} ms (n={len(software)})")

    if ft:
        head["false_triggers"] = ft
        for key, label in (("helm", "Helm"), ("baseline", "fixed 0.5 threshold")):
            if key in ft:
                lines.append(f"False triggers, {label}: median {ft[key]['median_per_min']:.2f} per minute "
                             f"(n={ft[key]['participants']})")
        if "helm" in ft and "baseline" in ft:
            chart_paired(ft["baseline"]["per_participant"], ft["helm"]["per_participant"],
                         "Fixed threshold, no calibration", "Helm", "False triggers while talking and watching",
                         "false triggers per minute", res / "false_triggers.png", higher_is_better=False)
    else:
        lines.append("False triggers: not measured (run eval/false_triggers.py)")

    if tp:
        head["throughput"] = tp
        for key, label in (("helm", "Helm, scaled to the player (c)"), ("fixed", "fixed gain (d)"), ("mouse", "mouse")):
            if key in tp:
                v = tp[key]
                err = "" if v["error_rate"] is None else f", {v['error_rate'] * 100:.0f}% misses"
                lines.append(f"Throughput, {label}: median {v['median_bits_per_s']:.2f} bits/s (n={v['participants']}{err})")
        if "helm" in tp and "fixed" in tp:
            chart_paired(tp["fixed"]["per_participant"], tp["helm"]["per_participant"], "Fixed gain",
                         "Helm, scaled to the player", "Pointing throughput with restricted movement",
                         "bits per second", res / "throughput.png", higher_is_better=True)
    else:
        lines.append("Throughput: not measured (no eval/results/target_*.csv)")

    acc = [float(r["loto_accuracy"]) for r in extras if r.get("loto_accuracy")]
    race = [float(r["launch_to_race_s"]) for r in extras if r.get("launch_to_race_s")]
    if acc:
        head["loto_accuracy"] = {"median": statistics.median(acc), "participants": len(acc)}
        lines.append(f"Learned-gesture accuracy (leave one take out): median {statistics.median(acc) * 100:.0f}% (n={len(acc)})")
    if race:
        head["launch_to_race_s"] = {"median": statistics.median(race), "participants": len(race)}
        lines.append(f"Launch to first race: median {statistics.median(race):.0f} s (n={len(race)})")

    res.mkdir(parents=True, exist_ok=True)
    (res / "headline.json").write_text(json.dumps(head, indent=2, default=float))
    print("\n".join(lines))
    print("\nNo participant had a motor impairment; the restricted-range condition is a proxy.")
    print("\nFor ui/src/results.ts:\n" + results_ts(head))
    return head


if __name__ == "__main__":
    main()
