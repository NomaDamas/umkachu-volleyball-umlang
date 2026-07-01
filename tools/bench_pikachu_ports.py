#!/usr/bin/env python3
import csv
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH_DIR = ROOT / "docs" / "benchmarks"
DEFAULT_JS_REPO = Path(os.environ.get("PIKACHU_JS_REPO", "/private/tmp/pikachu-volleyball-js"))
DEFAULT_RUST_REPO = Path(os.environ.get("PIKACHU_RUST_REPO", "/private/tmp/pikatchu-volleyball-rust"))
ORIGINAL_BINARY = os.environ.get("PIKACHU_ORIGINAL_BINARY", "")

CORE_TICK_FRAMES = int(os.environ.get("PIKACHU_PORT_BENCH_FRAMES", "250000"))
CORE_TICK_ITERATIONS = int(os.environ.get("PIKACHU_PORT_BENCH_ITERATIONS", "5"))
UMKACHU_VM_FRAMES = int(os.environ.get("UMKACHU_VM_BENCH_FRAMES", "60"))
UMKACHU_VM_ITERATIONS = int(os.environ.get("UMKACHU_VM_BENCH_ITERATIONS", "3"))


def run(command, cwd, timeout=300):
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def run_csv_command(command, cwd, timeout=300):
    completed = run(command, cwd, timeout)
    rows = list(csv.DictReader(completed.stdout.splitlines()))
    if len(rows) != 1:
        raise RuntimeError(f"expected one CSV row from {command}, got {len(rows)}")
    return rows[0], completed.stderr.strip()


def git_rev(path):
    if not (path / ".git").exists():
        return "-"
    try:
        rev = run(["git", "rev-parse", "--short", "HEAD"], path).stdout.strip()
        status = run(["git", "status", "--short"], path).stdout.strip()
        return f"{rev}+dirty" if status else rev
    except Exception:
        return "unknown"


def source_stats(root, suffixes):
    if not root.exists():
        return 0, 0, 0
    files = 0
    loc = 0
    bytes_ = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        if any(part in {".git", "target", "node_modules", "dist", "__pycache__"} for part in path.parts):
            continue
        files += 1
        data = path.read_bytes()
        bytes_ += len(data)
        try:
            loc += sum(1 for line in data.decode("utf-8", errors="ignore").splitlines() if line.strip())
        except UnicodeDecodeError:
            pass
    return files, loc, bytes_


def row(
    target,
    runtime,
    repo,
    commit,
    benchmark,
    iterations,
    units,
    total_mean_ms,
    throughput_per_s,
    source_files,
    source_loc,
    source_bytes,
    status,
    notes,
):
    return {
        "target": target,
        "runtime": runtime,
        "repo": repo,
        "commit": commit,
        "benchmark": benchmark,
        "iterations": str(iterations),
        "units": str(units),
        "total_mean_ms": f"{total_mean_ms:.3f}" if isinstance(total_mean_ms, float) else str(total_mean_ms),
        "throughput_per_s": f"{throughput_per_s:.0f}" if isinstance(throughput_per_s, float) else str(throughput_per_s),
        "source_files": str(source_files),
        "source_loc": str(source_loc),
        "source_bytes": str(source_bytes),
        "status": status,
        "notes": notes,
    }


def original_row():
    if ORIGINAL_BINARY:
        binary = Path(ORIGINAL_BINARY)
        status = "pending_manual_harness" if binary.exists() else "missing_binary"
        notes = "Original binary path was provided, but emulator/window instrumentation is not automated in this repo."
    else:
        status = "not_measured"
        notes = "Original SACHI SOFT binary is not included; direct FPS needs an emulator/manual harness."
    return row(
        "Original Pikachu Volleyball",
        "native binary",
        "SACHI SOFT / SAWAYAKAN original",
        "-",
        "direct_original_fps",
        "-",
        "-",
        "-",
        "-",
        0,
        0,
        0,
        status,
        notes,
    )


def js_core_tick(js_repo):
    files, loc, bytes_ = source_stats(js_repo / "src", {".js", ".css", ".html", ".json"})
    if not js_repo.exists():
        return row(
            "gorisanson/pikachu-volleyball",
            "Node.js physics.js",
            str(js_repo),
            "-",
            "core_physics_tick",
            CORE_TICK_ITERATIONS,
            CORE_TICK_FRAMES,
            "-",
            "-",
            files,
            loc,
            bytes_,
            "missing_repo",
            "Clone https://github.com/gorisanson/pikachu-volleyball and set PIKACHU_JS_REPO.",
        )

    with tempfile.TemporaryDirectory(prefix="umkachu-js-bench-") as tmp:
        tmp = Path(tmp)
        shutil.copy2(js_repo / "src" / "resources" / "js" / "physics.js", tmp / "physics.js")
        shutil.copy2(js_repo / "src" / "resources" / "js" / "rand.js", tmp / "rand.js")
        (tmp / "package.json").write_text('{"type":"module"}\n', encoding="utf-8")
        (tmp / "bench.mjs").write_text(JS_BENCH, encoding="utf-8")
        result, _stderr = run_csv_command(
            ["node", str(tmp / "bench.mjs"), str(CORE_TICK_FRAMES), str(CORE_TICK_ITERATIONS)],
            tmp,
        )

    return row(
        "gorisanson/pikachu-volleyball",
        "Node.js physics.js",
        "https://github.com/gorisanson/pikachu-volleyball",
        git_rev(js_repo),
        "core_physics_tick",
        result["iterations"],
        result["units"],
        float(result["total_mean_ms"]),
        float(result["throughput_per_s"]),
        files,
        loc,
        bytes_,
        "measured",
        "Headless original-logic physics tick, render/audio excluded.",
    )


def rust_core_tick(rust_repo):
    files, loc, bytes_ = source_stats(rust_repo / "src", {".rs"})
    if not rust_repo.exists():
        return row(
            "NomaDamas/Pikatchu-Volleyball-Rust",
            "Rust pikachu_core",
            str(rust_repo),
            "-",
            "core_physics_tick",
            CORE_TICK_ITERATIONS,
            CORE_TICK_FRAMES,
            "-",
            "-",
            files,
            loc,
            bytes_,
            "missing_repo",
            "Clone https://github.com/NomaDamas/Pikatchu-Volleyball-Rust and set PIKACHU_RUST_REPO.",
        )

    bin_dir = rust_repo / "src" / "bin"
    bin_dir.mkdir(exist_ok=True)
    bench_path = bin_dir / "core_bench.rs"
    previous = bench_path.read_text(encoding="utf-8") if bench_path.exists() else None
    try:
        bench_path.write_text(RUST_CORE_BENCH, encoding="utf-8")
        result, _stderr = run_csv_command(
            [
                "cargo",
                "run",
                "--release",
                "--quiet",
                "--bin",
                "core_bench",
                "--",
                str(CORE_TICK_FRAMES),
                str(CORE_TICK_ITERATIONS),
            ],
            rust_repo,
            timeout=600,
        )
    finally:
        if previous is None:
            bench_path.unlink(missing_ok=True)
            try:
                bin_dir.rmdir()
            except OSError:
                pass
        else:
            bench_path.write_text(previous, encoding="utf-8")
    return row(
        "NomaDamas/Pikatchu-Volleyball-Rust",
        "Rust pikachu_core",
        "https://github.com/NomaDamas/Pikatchu-Volleyball-Rust",
        git_rev(rust_repo),
        "core_physics_tick",
        result["iterations"],
        result["units"],
        float(result["total_mean_ms"]),
        float(result["throughput_per_s"]),
        files,
        loc,
        bytes_,
        "measured",
        "Headless Rust core physics tick, macroquad render/audio excluded.",
    )


def umkachu_rows():
    files, loc, bytes_ = source_stats(ROOT / "scripts", {".umm"})
    run([sys.executable, str(ROOT / "tools" / "bench_umlang_runtimes.py")], ROOT, timeout=600)
    rows = []
    with (BENCH_DIR / "umlang-runtime-results.csv").open(newline="", encoding="utf-8") as handle:
        for result in csv.DictReader(handle):
            if result["workload"] != "micro_assign_expr":
                continue
            runtime = {
                "rust": "Rust Umlang VM",
                "node": "Node.js Umlang runner",
                "python": "Python-style Umlang runner",
            }.get(result["runtime"], result["runtime"])
            rows.append(
                row(
                    "Umkachu Volleyball",
                    runtime,
                    "https://github.com/NomaDamas/umkachu-volleyball-umlang",
                    git_rev(ROOT),
                    "umlang_micro_assign_expr",
                    result["iterations"],
                    result["units"],
                    float(result["total_mean_ms"]),
                    float(result["throughput_units_per_s"]),
                    files,
                    loc,
                    bytes_,
                    "measured",
                    "Umlang assignment/expression VM microbench; not a game FPS number.",
                )
            )

    result, stderr = run_csv_command(
        [
            str(ROOT / "target" / "release" / "um_bench"),
            "pikachu-frames",
            str(UMKACHU_VM_FRAMES),
            str(UMKACHU_VM_ITERATIONS),
        ],
        ROOT,
        timeout=600,
    )
    notes = "Committed scripts/pikachu.umm frame-yield loop with no-op Host API; render/audio excluded."
    if stderr:
        notes = f"{notes} {stderr}"
    rows.append(
        row(
            "Umkachu Volleyball",
            "Rust Umlang VM",
            "https://github.com/NomaDamas/umkachu-volleyball-umlang",
            git_rev(ROOT),
            "umlang_vm_frame_yield",
            result["iterations"],
            result["units"],
            float(result["total_mean_ms"]),
            float(result["throughput_units_per_s"]),
            files,
            loc,
            bytes_,
            "measured",
            notes,
        )
    )
    return rows


def write_csv(rows):
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    path = BENCH_DIR / "pikachu-port-results.csv"
    fieldnames = [
        "target",
        "runtime",
        "repo",
        "commit",
        "benchmark",
        "iterations",
        "units",
        "total_mean_ms",
        "throughput_per_s",
        "source_files",
        "source_loc",
        "source_bytes",
        "status",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_svg(rows):
    measured = [item for item in rows if item["status"] == "measured" and item["throughput_per_s"] not in {"", "-"}]
    measured.sort(key=lambda item: float(item["throughput_per_s"]), reverse=True)
    width = 1080
    row_height = 58
    height = 136 + row_height * len(measured)
    left = 310
    right = 190
    chart_width = width - left - right
    max_log = max((math.log10(float(item["throughput_per_s"]) + 1) for item in measured), default=1)
    palette = {
        "core_physics_tick": "#d56b3f",
        "umlang_micro_assign_expr": "#4d9f4a",
        "umlang_vm_frame_yield": "#3975a6",
    }
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        "<style>",
        ".bg{fill:#101820}.title{fill:#f8f1df;font:700 25px sans-serif}.sub{fill:#cdbf9b;font:14px sans-serif}.label{fill:#f8f1df;font:700 14px sans-serif}.metric{fill:#9dadbd;font:12px monospace}.value{fill:#f8f1df;font:700 13px monospace}.axis{stroke:#3b4755;stroke-width:1}.note{fill:#9dadbd;font:12px sans-serif}",
        "</style>",
        f'<rect class="bg" x="0" y="0" width="{width}" height="{height}" rx="22"/>',
        '<text class="title" x="32" y="42">Pikachu Volleyball Port Benchmark Matrix</text>',
        '<text class="sub" x="32" y="68">Core tick, Umlang VM microbench, and Umkachu frame-yield results on this machine</text>',
    ]
    for tick in range(5):
        x = left + chart_width * tick / 4
        lines.append(f'<line class="axis" x1="{x:.1f}" y1="96" x2="{x:.1f}" y2="{height - 58}"/>')
    for index, item in enumerate(measured):
        y = 108 + index * row_height
        throughput = float(item["throughput_per_s"])
        scaled = math.log10(throughput + 1) / max_log if max_log else 0
        bar_width = max(2, chart_width * scaled)
        color = palette.get(item["benchmark"], "#bbbbbb")
        label = f'{item["target"]} · {item["runtime"]}'
        lines.append(f'<text class="label" x="32" y="{y + 14}">{escape_xml(label[:38])}</text>')
        lines.append(f'<text class="metric" x="32" y="{y + 34}">{escape_xml(item["benchmark"])}</text>')
        lines.append(f'<rect x="{left}" y="{y - 4}" width="{bar_width:.1f}" height="32" rx="9" fill="{color}"/>')
        lines.append(
            f'<text class="value" x="{left + bar_width + 12:.1f}" y="{y + 17}">{pretty_throughput(throughput)}</text>'
        )
    lines.append(
        f'<text class="note" x="32" y="{height - 24}">Log-scale bar widths; benchmark classes are not direct FPS equivalents.</text>'
    )
    lines.append("</svg>")
    path = BENCH_DIR / "pikachu-port-comparison.svg"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_report(rows):
    path = BENCH_DIR / "pikachu-port-comparison.md"
    lines = [
        "# Pikachu Volleyball Port Benchmark Matrix",
        "",
        "Generated by `tools/bench_pikachu_ports.py`.",
        "",
        '<p align="center">',
        '  <img src="pikachu-port-comparison.svg" alt="Pikachu Volleyball port benchmark matrix">',
        "</p>",
        "",
        "| Target | Runtime | Benchmark | Mean total | Throughput | Status | Notes |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for item in rows:
        total = item["total_mean_ms"]
        throughput = item["throughput_per_s"]
        if throughput not in {"", "-"}:
            throughput = pretty_throughput(float(throughput))
        lines.append(
            f"| {item['target']} | {item['runtime']} | {item['benchmark']} | {total} ms | {throughput} | {item['status']} | {item['notes']} |"
        )
    lines.extend(
        [
            "",
            "## Reading The Numbers",
            "",
            "- `core_physics_tick` compares JS and Rust ports without browser/macroquad rendering or audio.",
            "- `umlang_micro_assign_expr` compares the current Umlang runner implementations with the same synthetic `.umm` workload.",
            "- `umlang_vm_frame_yield` runs committed `scripts/pikachu.umm` until repeated frame yields with a no-op Host API.",
            "- Original Pikachu Volleyball is listed as the reference target, but the original binary is not committed here and needs a separate emulator/manual instrumentation harness for direct FPS.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def escape_xml(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def pretty_throughput(value):
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M/s"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K/s"
    return f"{value:.1f}/s"


def main():
    started = time.perf_counter()
    rows = [original_row()]
    for collector in (lambda: js_core_tick(DEFAULT_JS_REPO), lambda: rust_core_tick(DEFAULT_RUST_REPO)):
        try:
            rows.append(collector())
        except Exception as err:
            rows.append(
                row(
                    "benchmark collector",
                    "unknown",
                    "-",
                    "-",
                    "collector_failure",
                    "-",
                    "-",
                    "-",
                    "-",
                    0,
                    0,
                    0,
                    "failed",
                    str(err).replace("\n", " "),
                )
            )
    rows.extend(umkachu_rows())
    csv_path = write_csv(rows)
    svg_path = write_svg(rows)
    report_path = write_report(rows)
    print(f"wrote {csv_path.relative_to(ROOT)}")
    print(f"wrote {svg_path.relative_to(ROOT)}")
    print(f"wrote {report_path.relative_to(ROOT)}")
    print(f"elapsed_ms={(time.perf_counter() - started) * 1000:.1f}")


JS_BENCH = r"""
import { performance } from 'node:perf_hooks';
import { PikaPhysics, PikaUserInput } from './physics.js';

const frames = Number.parseInt(process.argv[2] || '250000', 10);
const iterations = Number.parseInt(process.argv[3] || '5', 10);

function stats(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const sum = sorted.reduce((acc, value) => acc + value, 0);
  return {
    mean: sum / sorted.length,
    median: sorted[Math.floor(sorted.length / 2)],
    min: sorted[0],
    max: sorted[sorted.length - 1],
  };
}

function runOnce() {
  const physics = new PikaPhysics(true, true);
  const inputs = [new PikaUserInput(), new PikaUserInput()];
  let checksum = 0;
  for (let i = 0; i < frames; i++) {
    inputs[0].xDirection = i % 180 < 60 ? 1 : i % 180 < 120 ? -1 : 0;
    inputs[0].yDirection = i % 211 === 0 ? -1 : 0;
    inputs[0].powerHit = i % 113 === 0 ? 1 : 0;
    inputs[1].xDirection = i % 150 < 50 ? -1 : i % 150 < 100 ? 1 : 0;
    inputs[1].yDirection = i % 197 === 0 ? -1 : 0;
    inputs[1].powerHit = i % 127 === 0 ? 1 : 0;
    if (physics.runEngineForNextFrame(inputs)) {
      physics.ball.initializeForNewRound(false);
    }
    checksum = (checksum + physics.ball.x + physics.ball.y + physics.player1.x + physics.player2.x) | 0;
  }
  return checksum;
}

const times = [];
let checksum = 0;
for (let i = 0; i < iterations; i++) {
  const start = performance.now();
  checksum ^= runOnce();
  const end = performance.now();
  times.push(end - start);
}
const total = stats(times);
const throughput = frames / (total.mean / 1000);
console.log('runtime,workload,iterations,units,total_mean_ms,total_median_ms,throughput_per_s,total_min_ms,total_max_ms,checksum');
console.log(`node,core_physics_tick,${iterations},${frames},${total.mean.toFixed(3)},${total.median.toFixed(3)},${throughput.toFixed(0)},${total.min.toFixed(3)},${total.max.toFixed(3)},${checksum}`);
"""


RUST_CORE_BENCH = r"""
use std::{
    hint::black_box,
    time::{Duration, Instant},
};

use pikachu_core::{PikaPhysics, PikaUserInput};

#[derive(Debug, Clone)]
struct Stats {
    mean: f64,
    median: f64,
    min: f64,
    max: f64,
}

fn main() {
    let mut args = std::env::args().skip(1);
    let frames = args
        .next()
        .and_then(|value| value.parse().ok())
        .unwrap_or(250_000);
    let iterations = args.next().and_then(|value| value.parse().ok()).unwrap_or(5);
    let mut times = Vec::with_capacity(iterations);
    let mut checksum = 0i64;

    for _ in 0..iterations {
        let start = Instant::now();
        checksum ^= run_once(frames);
        times.push(start.elapsed());
    }

    let total = stats(&times);
    let throughput = frames as f64 / (total.mean / 1000.0);
    println!("runtime,workload,iterations,units,total_mean_ms,total_median_ms,throughput_per_s,total_min_ms,total_max_ms,checksum");
    println!(
        "rust,core_physics_tick,{iterations},{frames},{:.3},{:.3},{:.0},{:.3},{:.3},{checksum}",
        total.mean, total.median, throughput, total.min, total.max
    );
}

fn run_once(frames: usize) -> i64 {
    let mut physics = PikaPhysics::new(true, true);
    let mut inputs = [PikaUserInput::neutral(), PikaUserInput::neutral()];
    let mut checksum = 0i64;
    for i in 0..frames {
        inputs[0].x_direction = if i % 180 < 60 { 1 } else if i % 180 < 120 { -1 } else { 0 };
        inputs[0].y_direction = if i % 211 == 0 { -1 } else { 0 };
        inputs[0].power_hit = if i % 113 == 0 { 1 } else { 0 };
        inputs[1].x_direction = if i % 150 < 50 { -1 } else if i % 150 < 100 { 1 } else { 0 };
        inputs[1].y_direction = if i % 197 == 0 { -1 } else { 0 };
        inputs[1].power_hit = if i % 127 == 0 { 1 } else { 0 };
        if physics.run_engine_for_next_frame(&mut inputs) {
            physics.initialize_round(false);
        }
        checksum = checksum.wrapping_add(
            physics.ball.x as i64
                + physics.ball.y as i64
                + physics.player1.x as i64
                + physics.player2.x as i64,
        );
    }
    black_box(checksum)
}

fn stats(values: &[Duration]) -> Stats {
    let mut millis: Vec<f64> = values
        .iter()
        .map(|duration| duration.as_secs_f64() * 1000.0)
        .collect();
    millis.sort_by(|a, b| a.total_cmp(b));
    let sum: f64 = millis.iter().sum();
    Stats {
        mean: sum / millis.len() as f64,
        median: millis[millis.len() / 2],
        min: millis[0],
        max: millis[millis.len() - 1],
    }
}
"""


if __name__ == "__main__":
    main()
