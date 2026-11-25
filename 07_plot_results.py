#!/usr/bin/env python3
"""Vẽ biểu đồ và bảng tổng hợp từ file kết quả của 06_benchmark.py.

Ví dụ:
    py -3.12 07_plot_results.py results\\bench_1m_20261125_214622.csv
    py -3.12 07_plot_results.py results\\bench_100k_*.csv results\\bench_1m_*.csv   # nhiều file -> thêm biểu đồ quy mô

Đầu ra (cùng thư mục với file CSV):
    <tên>_<mode>.png     : thời gian trung vị MySQL vs MongoDB cho từng thao tác (trục log)
    <tên>_summary.md     : bảng số liệu để dán vào báo cáo
    scale_<mode>.png     : (khi truyền nhiều file) so sánh theo quy mô dữ liệu
"""
import csv
import glob
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLORS = {"MySQL": "#2a78d6", "MongoDB": "#eb6834"}  # bảng màu đã kiểm tra an toàn cho người mù màu
INK, INK_MUTED, GRID, SURFACE = "#1f1f1e", "#6b6a64", "#e4e3de", "#fcfcfb"
MODE_TITLE = {"no_index": "chỉ index cơ bản (PK/UNIQUE/FK)", "with_index": "có thêm index phụ"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK_MUTED,
    "xtick.color": INK_MUTED, "ytick.color": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
})


def load(paths):
    rows = []
    for p in paths:
        with open(p, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                r["median_ms"] = float(r["median_ms"])
                r["p95_ms"] = float(r["p95_ms"])
                rows.append(r)
    return rows


def bar_chart(rows, mode, label, out):
    data = [r for r in rows if r["mode"] == mode and r["label"] == label]
    ops = list(dict.fromkeys(r["op"] for r in data))
    titles = {r["op"]: r["title"] for r in data}
    value = {(r["op"], r["system"]): r["median_ms"] for r in data}

    fig, ax = plt.subplots(figsize=(9, 0.48 * len(ops) + 1.6), dpi=160)
    h = 0.36
    for i, system in enumerate(("MySQL", "MongoDB")):
        ys = [k + (i - 0.5) * (h + 0.04) for k in range(len(ops))]
        xs = [value.get((op, system), 0) for op in ops]
        ys_, xs_ = zip(*[(y, x) for y, x in zip(ys, xs) if x > 0])
        ax.barh(ys_, xs_, height=h, color=COLORS[system], label=system, edgecolor=SURFACE, linewidth=1)
    ax.set_yticks(range(len(ops)))
    ax.set_yticklabels([f"{op}  {titles[op]}" for op in ops])
    ax.invert_yaxis()
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_xlabel("Thời gian trung vị (ms, thang log) - càng ngắn càng nhanh")
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title(f"MySQL vs MongoDB - {label}, {MODE_TITLE.get(mode, mode)}", color=INK, loc="left", fontsize=11, pad=12)
    ax.legend(loc="lower right", frameon=False, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)


def scale_chart(rows, mode, out):
    labels = list(dict.fromkeys(r["label"] for r in rows))
    ops = list(dict.fromkeys(r["op"] for r in rows if r["mode"] == mode))
    value = {(r["label"], r["op"], r["system"]): r["median_ms"] for r in rows if r["mode"] == mode}
    cols = 4
    nrows = (len(ops) + cols - 1) // cols
    fig, axes = plt.subplots(nrows, cols, figsize=(2.6 * cols, 2.1 * nrows), dpi=160, squeeze=False)
    for ax, op in zip(axes.flat, ops):
        for system in ("MySQL", "MongoDB"):
            ys = [value.get((lb, op, system)) for lb in labels]
            if all(v is not None for v in ys):
                ax.plot(labels, ys, color=COLORS[system], linewidth=2, marker="o", markersize=5, label=system)
        ax.set_title(op, color=INK, fontsize=9, loc="left")
        ax.set_yscale("log")
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    for ax in list(axes.flat)[len(ops):]:
        ax.axis("off")
    handles, names = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="upper right", frameon=False, labelcolor=INK)
    fig.suptitle(f"Thời gian trung vị (ms, log) theo quy mô dữ liệu - {MODE_TITLE.get(mode, mode)}", color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)


def summary_md(rows, out):
    lines = []
    for (label, mode) in dict.fromkeys((r["label"], r["mode"]) for r in rows):
        data = [r for r in rows if r["label"] == label and r["mode"] == mode]
        by_op = defaultdict(dict)
        for r in data:
            by_op[r["op"]][r["system"]] = r
        lines += [f"\n### Bộ {label} - {MODE_TITLE.get(mode, mode)}\n",
                  "| Mã | Thao tác | MySQL trung vị (ms) | MySQL p95 | MongoDB trung vị (ms) | MongoDB p95 | Nhanh hơn |",
                  "|---|---|---:|---:|---:|---:|---|"]
        for op, d in by_op.items():
            m, g = d.get("MySQL"), d.get("MongoDB")
            title = (m or g)["title"]
            if m and g:
                fast, slow = (("MySQL", m, g) if m["median_ms"] < g["median_ms"] else ("MongoDB", g, m))[0], None
                ratio = max(m["median_ms"], g["median_ms"]) / max(min(m["median_ms"], g["median_ms"]), 1e-9)
                verdict = f"{fast} ×{ratio:.1f}" if ratio >= 1.15 else "tương đương"
            else:
                verdict = "-"
            fmt = lambda r, k: f"{r[k]:.2f}" if r else "-"
            lines.append(f"| {op} | {title} | {fmt(m, 'median_ms')} | {fmt(m, 'p95_ms')} | {fmt(g, 'median_ms')} | {fmt(g, 'p95_ms')} | {verdict} |")
    lines.append("\n'Tương đương' = chênh lệch dưới 15%. ×k = bên nhanh hơn nhanh gấp k lần (theo trung vị).")
    out.write_text("\n".join(lines).lstrip() + "\n", encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    paths = [p for arg in sys.argv[1:] for p in sorted(glob.glob(arg))]
    paths = [p for p in paths if not p.endswith("_plans.csv")]
    if not paths:
        raise SystemExit("Cách dùng: py -3.12 07_plot_results.py results\\bench_<label>_<time>.csv [...]")
    rows = load(paths)
    first = Path(paths[0])
    for p in paths:
        stem = Path(p).with_suffix("")
        subset = load([p])
        for mode in dict.fromkeys(r["mode"] for r in subset):
            out = Path(f"{stem}_{mode}.png")
            bar_chart(subset, mode, subset[0]["label"], out)
            print("Đã vẽ", out)
        summary_md(subset, Path(f"{stem}_summary.md"))
        print("Đã ghi", f"{stem}_summary.md")
    if len({r["label"] for r in rows}) > 1:
        for mode in dict.fromkeys(r["mode"] for r in rows):
            out = first.parent / f"scale_{mode}.png"
            scale_chart(rows, mode, out)
            print("Đã vẽ", out)


if __name__ == "__main__":
    main()
