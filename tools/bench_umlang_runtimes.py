#!/usr/bin/env python3
import csv
import math
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH_DIR = ROOT / "docs" / "benchmarks"
MICRO_LINES = 100_000
MICRO_ITERATIONS = 7
PIKACHU_ITERATIONS = 3


def micro_source(line_count):
    rows = ["어떻게", "엄.....", "어엄..."]
    for i in range(line_count):
        slot = 2 + (i % 31)
        rows.append(f"{'어' * slot}엄어... 어어,")
    rows.append("이 사람이름이냐ㅋㅋ")
    return "\n".join(rows)


def parse_expr_term(term):
    load_count = 0
    offset = 0
    for ch in term:
        if ch == "어":
            load_count += 1
        elif ch == ".":
            offset += 1
        elif ch == ",":
            offset -= 1
    return (load_count, offset)


def parse_expr(expr):
    return [parse_expr_term(term) for term in expr.split(" ") if term]


def parse_statement(code):
    left, right = code.split("엄", 1)
    return ("assign", left.count("어") + 1, parse_expr(right))


def parse(source):
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines[0].strip() != "어떻게":
        raise ValueError("program must start with 어떻게")
    instructions = []
    for raw in lines[1:]:
        line = raw.strip()
        if line == "이 사람이름이냐ㅋㅋ":
            break
        instructions.append(line or None)
    return instructions


def i32(value):
    value &= 0xFFFFFFFF
    if value >= 0x80000000:
        value -= 0x100000000
    return value


def eval_expr(vars_, expr):
    if not expr:
        return 0
    result = 1
    for load_var, offset in expr:
        loaded = vars_[load_var] if load_var else 0
        result = i32(result * i32(loaded + offset))
    return result


def run(instructions):
    vars_ = [0] * 4096
    pc = 0
    while pc < len(instructions):
        instruction = instructions[pc]
        if isinstance(instruction, str):
            instruction = parse_statement(instruction)
            instructions[pc] = instruction
        if instruction and instruction[0] == "assign":
            _, index, expr = instruction
            vars_[index] = eval_expr(vars_, expr)
        pc += 1


def stats(values):
    values = sorted(values)
    return {
        "mean": sum(values) / len(values),
        "median": values[len(values) // 2],
        "min": values[0],
        "max": values[-1],
    }


def python_micro():
    source = micro_source(MICRO_LINES)
    parse_times = []
    run_times = []
    total_times = []
    for _ in range(MICRO_ITERATIONS):
        start = time.perf_counter()
        instructions = parse(source)
        parsed = time.perf_counter()
        run(instructions)
        ended = time.perf_counter()
        parse_times.append((parsed - start) * 1000)
        run_times.append((ended - parsed) * 1000)
        total_times.append((ended - start) * 1000)

    parse_stats = stats(parse_times)
    run_stats = stats(run_times)
    total_stats = stats(total_times)
    throughput = MICRO_LINES / (run_stats["mean"] / 1000)
    return {
        "runtime": "python",
        "workload": "micro_assign_expr",
        "iterations": str(MICRO_ITERATIONS),
        "units": str(MICRO_LINES),
        "parse_mean_ms": f"{parse_stats['mean']:.3f}",
        "run_mean_ms": f"{run_stats['mean']:.3f}",
        "total_mean_ms": f"{total_stats['mean']:.3f}",
        "total_median_ms": f"{total_stats['median']:.3f}",
        "throughput_units_per_s": f"{throughput:.0f}",
        "total_min_ms": f"{total_stats['min']:.3f}",
        "total_max_ms": f"{total_stats['max']:.3f}",
    }


def run_csv_command(command):
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    rows = list(csv.DictReader(completed.stdout.splitlines()))
    if len(rows) != 1:
        raise RuntimeError(f"expected one CSV row from {command}, got {len(rows)}")
    return rows[0]


def rust_micro():
    return run_csv_command(
        [
            str(ROOT / "target" / "release" / "um_bench"),
            "micro",
            str(MICRO_LINES),
            str(MICRO_ITERATIONS),
        ]
    )


def rust_pikachu():
    return run_csv_command(
        [
            str(ROOT / "target" / "release" / "um_bench"),
            "pikachu",
            str(PIKACHU_ITERATIONS),
        ]
    )


def node_micro():
    return run_csv_command(
        [
            "node",
            str(ROOT / "tools" / "umlang_node_micro_bench.mjs"),
            str(MICRO_LINES),
            str(MICRO_ITERATIONS),
        ]
    )


def write_csv(rows):
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    path = BENCH_DIR / "umlang-runtime-results.csv"
    fieldnames = [
        "runtime",
        "workload",
        "iterations",
        "units",
        "parse_mean_ms",
        "run_mean_ms",
        "total_mean_ms",
        "total_median_ms",
        "throughput_units_per_s",
        "total_min_ms",
        "total_max_ms",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def bar_svg(rows, metric, title, subtitle, output_path, unit_label, higher_is_better):
    width = 880
    height = 360
    margin_left = 150
    margin_right = 56
    bar_top = 96
    bar_height = 42
    gap = 28
    values = [float(row[metric]) for row in rows]
    max_value = max(values) if values else 1
    if max_value <= 0:
        max_value = 1
    chart_width = width - margin_left - margin_right
    palette = {
        "rust": "#d56b3f",
        "node": "#4d9f4a",
        "python": "#3975a6",
    }
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="880" height="360" viewBox="0 0 880 360" role="img">',
        "<style>",
        ".bg{fill:#101820}.title{fill:#f8f1df;font:700 24px sans-serif}.sub{fill:#cdbf9b;font:14px sans-serif}.label{fill:#f8f1df;font:700 15px sans-serif}.value{fill:#f8f1df;font:700 14px monospace}.axis{stroke:#3b4755;stroke-width:1}.note{fill:#9dadbd;font:12px sans-serif}",
        "</style>",
        '<rect class="bg" x="0" y="0" width="880" height="360" rx="22"/>',
        f'<text class="title" x="32" y="42">{escape_xml(title)}</text>',
        f'<text class="sub" x="32" y="68">{escape_xml(subtitle)}</text>',
    ]
    for tick in range(5):
        x = margin_left + chart_width * tick / 4
        lines.append(f'<line class="axis" x1="{x:.1f}" y1="88" x2="{x:.1f}" y2="292"/>')
    for index, row in enumerate(rows):
        y = bar_top + index * (bar_height + gap)
        value = float(row[metric])
        bar_width = 2 if value == 0 else chart_width * value / max_value
        runtime = row["runtime"]
        color = palette.get(runtime, "#bbbbbb")
        lines.append(f'<text class="label" x="32" y="{y + 27}">{escape_xml(runtime.title())}</text>')
        lines.append(
            f'<rect x="{margin_left}" y="{y}" width="{bar_width:.1f}" height="{bar_height}" rx="10" fill="{color}"/>'
        )
        pretty_value = pretty_metric(value, unit_label)
        lines.append(
            f'<text class="value" x="{margin_left + bar_width + 12:.1f}" y="{y + 27}">{pretty_value}</text>'
        )
    direction = "higher is better" if higher_is_better else "lower is better"
    lines.append(f'<text class="note" x="32" y="330">Benchmark script: tools/bench_umlang_runtimes.py · {direction}</text>')
    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def escape_xml(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def pretty_metric(value, unit_label):
    if unit_label == "instr/s":
        if abs(value) >= 1_000_000:
            return f"{value / 1_000_000:.2f}M {unit_label}"
        if abs(value) >= 1_000:
            return f"{value / 1_000:.1f}K {unit_label}"
        return f"{value:.0f} {unit_label}"
    if math.isfinite(value):
        return f"{value:.1f} {unit_label}"
    return f"0 {unit_label}"


def write_graphs(rows):
    micro_rows = [row for row in rows if row["workload"] == "micro_assign_expr"]
    order = {"rust": 0, "node": 1, "python": 2}
    micro_rows.sort(key=lambda row: order.get(row["runtime"], 99))
    throughput = BENCH_DIR / "umlang-throughput.svg"
    latency = BENCH_DIR / "umlang-total-latency.svg"
    bar_svg(
        micro_rows,
        "throughput_units_per_s",
        "Umkachu Umlang VM Throughput",
        f"{MICRO_LINES:,} assignment/expression statements, {MICRO_ITERATIONS} iterations",
        throughput,
        "instr/s",
        True,
    )
    bar_svg(
        micro_rows,
        "total_mean_ms",
        "Umkachu Umlang VM Total Latency",
        "parse raw Korean/Umlang text + lazy compile + execute",
        latency,
        "ms",
        False,
    )
    return throughput, latency


def write_report(rows):
    micro_rows = [row for row in rows if row["workload"] == "micro_assign_expr"]
    pikachu = next(row for row in rows if row["workload"] == "pikachu_first_frame")
    rust_throughput = next(float(row["throughput_units_per_s"]) for row in micro_rows if row["runtime"] == "rust")
    runtime_labels = {
        "rust": "Rust",
        "node": "Node.js",
        "python": "Python",
    }
    runtime_notes = {
        "rust": "Baseline runner used by the Umkachu package.",
        "node": "JavaScript runner signal for a future Node backend.",
        "python": "Python-style runner signal for scripting-heavy experiments.",
    }
    report = BENCH_DIR / "README.md"
    lines = [
        "# Umkachu Umlang VM Benchmarks",
        "",
        "Generated by `tools/bench_umlang_runtimes.py`.",
        "",
        '<p align="center">',
        '  <img src="umlang-throughput.svg" alt="Umkachu Umlang VM throughput benchmark graph">',
        "</p>",
        '<p align="center"><em>Figure 1. Umkachu Umlang VM throughput by runner: Rust, Node.js, and Python-style implementations.</em></p>',
        "",
        '<p align="center">',
        '  <img src="umlang-total-latency.svg" alt="Umkachu Umlang VM total latency benchmark graph">',
        "</p>",
        '<p align="center"><em>Figure 2. Umkachu Umlang VM total latency by runner: parse + lazy compile + execute.</em></p>',
        "",
        "## Method",
        "",
        "`tools/bench_umlang_runtimes.py` builds `src/bin/um_bench.rs` in release mode, runs the same generated Umlang",
        "micro workload through Rust, Node.js, and Python-style runners, and then runs the real `scripts/pikachu.umm`",
        "package with a no-op Host API until the first frame yield.",
        "",
        "## Umkachu Umlang VM Throughput Table",
        "",
        "| Runner | Workload | Throughput | Rust-relative | Signal |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for row in micro_rows:
        throughput = float(row["throughput_units_per_s"])
        lines.append(
            "| {runtime} | {workload} | {throughput:,} instr/s | {relative:.2f}x | {signal} |".format(
                runtime=runtime_labels.get(row["runtime"], row["runtime"].title()),
                workload=f"{MICRO_LINES:,} Umkachu/Umlang assignment-expression ops",
                throughput=int(throughput),
                relative=throughput / rust_throughput,
                signal=runtime_notes.get(row["runtime"], "Alternative runner signal."),
            )
        )
    lines.extend(
        [
            "",
            "## Full Results",
            "",
            "| Runtime | Workload | Iterations | Units | Parse mean | Run mean | Total mean | Throughput |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        throughput = row["throughput_units_per_s"]
        throughput_text = "-" if throughput == "0" else f"{int(float(throughput)):,}/s"
        lines.append(
            "| {runtime} | {workload} | {iterations} | {units} | {parse_mean_ms} ms | {run_mean_ms} ms | {total_mean_ms} ms | {throughput} |".format(
                runtime=row["runtime"],
                workload=row["workload"],
                iterations=row["iterations"],
                units=row["units"],
                parse_mean_ms=row["parse_mean_ms"],
                run_mean_ms=row["run_mean_ms"],
                total_mean_ms=row["total_mean_ms"],
                throughput=throughput_text,
            )
        )
    lines.extend(
        [
            "",
            "## Porting Signal",
            "",
            "- The micro workload isolates the cost of Korean/Umlang text parsing, lazy instruction compilation, variable-slot writes, and expression evaluation.",
            "- The `pikachu_first_frame` row uses the committed `scripts/pikachu.umm` package and a no-op Host API to measure how long the Rust VM takes to expand imports and reach the first game frame yield.",
            f"- The current Pikachu first-frame benchmark reached a frame yield in {float(pikachu['total_mean_ms']):.1f} ms on this machine, including import expansion and lazy compilation.",
            "- Higher instruction throughput helps this port because the game package is intentionally huge `.umm` text; faster VM dispatch means more room for physics, AI, input, and render syscalls before each frame budget is exhausted.",
            "",
            "## Cross-Port Matrix",
            "",
            "`tools/bench_pikachu_ports.py` compares the original reference target, the JS port, the Rust port, and",
            "the current Umkachu/Umlang runners with the measurements that can be automated without opening a game window.",
            "It writes `pikachu-port-results.csv`, `pikachu-port-comparison.svg`, and `pikachu-port-comparison.md`.",
        ]
    )
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main():
    subprocess.run(
        ["cargo", "build", "--release", "--bin", "um_bench"],
        cwd=ROOT,
        check=True,
    )
    rows = [rust_micro(), node_micro(), python_micro(), rust_pikachu()]
    write_csv(rows)
    write_graphs(rows)
    write_report(rows)
    for row in rows:
        print(
            f"{row['runtime']},{row['workload']},{row['total_mean_ms']}ms,{row['throughput_units_per_s']}/s"
        )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as err:
        print(err.stderr or err, file=sys.stderr)
        raise
