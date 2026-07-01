use std::time::{Duration, Instant};

use umkachu_volleyball_umlang::{
    syscalls::*,
    um::{HostOps, Step, Vm},
};

#[derive(Default)]
struct BenchHost {
    yields: usize,
    syscalls: usize,
}

impl HostOps for BenchHost {
    fn syscall(&mut self, opcode: i32, vm: &mut Vm) -> Result<Step, String> {
        self.syscalls += 1;
        match opcode {
            SYS_CLEAR
            | SYS_DRAW_RECT
            | SYS_DRAW_CIRCLE
            | SYS_DRAW_NUMBER
            | SYS_DRAW_RECT_ALPHA
            | SYS_SET_TEXTURE_FILTER
            | SYS_SET_TARGET_FPS
            | SYS_DEFINE_COLOR
            | SYS_CONFIGURE_WINDOW
            | SYS_CONFIGURE_SETTINGS
            | SYS_DEFINE_TEXTURE
            | SYS_DRAW_TEXTURE
            | SYS_DRAW_TEXTURE_ALPHA
            | SYS_DEFINE_AUDIO
            | SYS_PLAY_AUDIO
            | SYS_STOP_AUDIO
            | SYS_SAVE_SETTING => Ok(Step::Running),
            SYS_LOAD_SETTING => {
                let out = vm.get_var(3).max(0) as usize;
                vm.set_var(out, vm.get_var(4));
                Ok(Step::Running)
            }
            SYS_KEY_DOWN | SYS_KEY_PRESSED => {
                let out = vm.get_var(3).max(0) as usize;
                vm.set_var(out, 0);
                Ok(Step::Running)
            }
            SYS_ADD => {
                let dst = vm.get_var(2).max(0) as usize;
                let a = vm.get_var(vm.get_var(3).max(0) as usize);
                let b = vm.get_var(vm.get_var(4).max(0) as usize);
                vm.set_var(dst, a.wrapping_add(b));
                Ok(Step::Running)
            }
            SYS_SUB => {
                let dst = vm.get_var(2).max(0) as usize;
                let a = vm.get_var(vm.get_var(3).max(0) as usize);
                let b = vm.get_var(vm.get_var(4).max(0) as usize);
                vm.set_var(dst, a.wrapping_sub(b));
                Ok(Step::Running)
            }
            SYS_ADD_CONST => {
                let dst = vm.get_var(2).max(0) as usize;
                let a = vm.get_var(vm.get_var(3).max(0) as usize);
                vm.set_var(dst, a.wrapping_add(vm.get_var(4)));
                Ok(Step::Running)
            }
            SYS_CLAMP => {
                let dst = vm.get_var(2).max(0) as usize;
                let value = vm.get_var(vm.get_var(3).max(0) as usize);
                vm.set_var(dst, value.clamp(vm.get_var(4), vm.get_var(5)));
                Ok(Step::Running)
            }
            SYS_WAIT_FRAME => {
                self.yields += 1;
                Ok(Step::Yielded)
            }
            SYS_GT => {
                let dst = vm.get_var(2).max(0) as usize;
                let a = vm.get_var(vm.get_var(3).max(0) as usize);
                let b = vm.get_var(vm.get_var(4).max(0) as usize);
                vm.set_var(dst, i32::from(a > b));
                Ok(Step::Running)
            }
            SYS_LT => {
                let dst = vm.get_var(2).max(0) as usize;
                let a = vm.get_var(vm.get_var(3).max(0) as usize);
                let b = vm.get_var(vm.get_var(4).max(0) as usize);
                vm.set_var(dst, i32::from(a < b));
                Ok(Step::Running)
            }
            SYS_ABS => {
                let dst = vm.get_var(2).max(0) as usize;
                let value = vm.get_var(vm.get_var(3).max(0) as usize);
                vm.set_var(dst, value.wrapping_abs());
                Ok(Step::Running)
            }
            SYS_MUL => {
                let dst = vm.get_var(2).max(0) as usize;
                let a = vm.get_var(vm.get_var(3).max(0) as usize);
                let b = vm.get_var(vm.get_var(4).max(0) as usize);
                vm.set_var(dst, a.wrapping_mul(b));
                Ok(Step::Running)
            }
            SYS_EQ => {
                let dst = vm.get_var(2).max(0) as usize;
                let a = vm.get_var(vm.get_var(3).max(0) as usize);
                let b = vm.get_var(vm.get_var(4).max(0) as usize);
                vm.set_var(dst, i32::from(a == b));
                Ok(Step::Running)
            }
            SYS_DIV => {
                let dst = vm.get_var(2).max(0) as usize;
                let a = vm.get_var(vm.get_var(3).max(0) as usize);
                let b = vm.get_var(vm.get_var(4).max(0) as usize);
                vm.set_var(dst, if b == 0 { 0 } else { a / b });
                Ok(Step::Running)
            }
            SYS_MOD => {
                let dst = vm.get_var(2).max(0) as usize;
                let a = vm.get_var(vm.get_var(3).max(0) as usize);
                let b = vm.get_var(vm.get_var(4).max(0) as usize);
                vm.set_var(dst, if b == 0 { 0 } else { a % b });
                Ok(Step::Running)
            }
            _ => Err(format!("unknown benchmark syscall {opcode}")),
        }
    }
}

#[derive(Debug, Clone)]
struct Stats {
    mean: f64,
    median: f64,
    min: f64,
    max: f64,
}

fn main() {
    let mut args = std::env::args().skip(1);
    let mode = args.next().unwrap_or_else(|| "micro".to_string());
    let result = match mode.as_str() {
        "micro" => {
            let lines = args
                .next()
                .and_then(|value| value.parse().ok())
                .unwrap_or(100_000);
            let iterations = args
                .next()
                .and_then(|value| value.parse().ok())
                .unwrap_or(7);
            run_micro(lines, iterations)
        }
        "pikachu" => {
            let iterations = args
                .next()
                .and_then(|value| value.parse().ok())
                .unwrap_or(3);
            run_pikachu(iterations)
        }
        "pikachu-frames" => {
            let frames = args
                .next()
                .and_then(|value| value.parse().ok())
                .unwrap_or(60);
            let iterations = args
                .next()
                .and_then(|value| value.parse().ok())
                .unwrap_or(3);
            run_pikachu_frames(frames, iterations)
        }
        _ => Err(format!("unknown benchmark mode: {mode}")),
    };

    if let Err(err) = result {
        eprintln!("{err}");
        std::process::exit(1);
    }
}

fn run_micro(lines: usize, iterations: usize) -> Result<(), String> {
    let source = micro_source(lines);
    let mut parse_times = Vec::with_capacity(iterations);
    let mut run_times = Vec::with_capacity(iterations);
    let mut total_times = Vec::with_capacity(iterations);

    for _ in 0..iterations {
        let start = Instant::now();
        let mut vm = Vm::parse(&source)?;
        let parsed = Instant::now();
        let mut host = BenchHost::default();
        match vm.run_until_yield(&mut host, lines + 16)? {
            Step::Exited(_) => {}
            step => {
                return Err(format!(
                    "micro benchmark ended with unexpected step: {step:?}"
                ))
            }
        }
        let ended = Instant::now();
        parse_times.push(parsed.duration_since(start));
        run_times.push(ended.duration_since(parsed));
        total_times.push(ended.duration_since(start));
    }

    let parse = stats(&parse_times);
    let run = stats(&run_times);
    let total = stats(&total_times);
    let throughput = lines as f64 / (run.mean / 1000.0);

    print_csv_header();
    println!(
        "rust,micro_assign_expr,{iterations},{lines},{:.3},{:.3},{:.3},{:.3},{:.0},{:.3},{:.3}",
        parse.mean, run.mean, total.mean, total.median, throughput, total.min, total.max
    );
    Ok(())
}

fn run_pikachu(iterations: usize) -> Result<(), String> {
    let mut parse_times = Vec::with_capacity(iterations);
    let mut run_times = Vec::with_capacity(iterations);
    let mut total_times = Vec::with_capacity(iterations);
    let mut syscall_count = 0usize;

    for _ in 0..iterations {
        let start = Instant::now();
        let mut vm = Vm::parse_file("scripts/pikachu.umm")?;
        let parsed = Instant::now();
        let mut host = BenchHost::default();
        match vm.run_until_yield(&mut host, 600_000)? {
            Step::Yielded => {}
            step => {
                return Err(format!(
                    "pikachu benchmark ended with unexpected step: {step:?}"
                ))
            }
        }
        let ended = Instant::now();
        syscall_count = host.syscalls;
        parse_times.push(parsed.duration_since(start));
        run_times.push(ended.duration_since(parsed));
        total_times.push(ended.duration_since(start));
    }

    let parse = stats(&parse_times);
    let run = stats(&run_times);
    let total = stats(&total_times);

    print_csv_header();
    println!(
        "rust,pikachu_first_frame,{iterations},{syscall_count},{:.3},{:.3},{:.3},{:.3},0,{:.3},{:.3}",
        parse.mean, run.mean, total.mean, total.median, total.min, total.max
    );
    Ok(())
}

fn run_pikachu_frames(frames: usize, iterations: usize) -> Result<(), String> {
    let mut parse_times = Vec::with_capacity(iterations);
    let mut run_times = Vec::with_capacity(iterations);
    let mut total_times = Vec::with_capacity(iterations);
    let mut syscall_count = 0usize;
    let mut yielded_frames = 0usize;

    for _ in 0..iterations {
        let start = Instant::now();
        let mut vm = Vm::parse_file("scripts/pikachu.umm")?;
        let parsed = Instant::now();
        let mut host = BenchHost::default();
        let mut frames_this_run = 0usize;
        for _ in 0..frames {
            match vm.run_until_yield(&mut host, 600_000)? {
                Step::Yielded => frames_this_run += 1,
                Step::Exited(_) => break,
                step => {
                    return Err(format!(
                        "pikachu frame benchmark ended with unexpected step: {step:?}"
                    ))
                }
            }
        }
        let ended = Instant::now();
        syscall_count = host.syscalls;
        yielded_frames = frames_this_run;
        parse_times.push(parsed.duration_since(start));
        run_times.push(ended.duration_since(parsed));
        total_times.push(ended.duration_since(start));
    }

    let parse = stats(&parse_times);
    let run = stats(&run_times);
    let total = stats(&total_times);
    let throughput = yielded_frames as f64 / (run.mean / 1000.0);

    print_csv_header();
    println!(
        "rust,pikachu_vm_frames,{iterations},{yielded_frames},{:.3},{:.3},{:.3},{:.3},{:.0},{:.3},{:.3}",
        parse.mean, run.mean, total.mean, total.median, throughput, total.min, total.max
    );
    eprintln!("syscalls={syscall_count}");
    Ok(())
}

fn micro_source(lines: usize) -> String {
    let mut source = String::with_capacity(lines * 20);
    source.push_str("어떻게\n");
    source.push_str("엄.....\n");
    source.push_str("어엄...\n");
    for i in 0..lines {
        let slot = 2 + (i % 31);
        source.push_str(&"어".repeat(slot));
        source.push_str("엄어... 어어,\n");
    }
    source.push_str("이 사람이름이냐ㅋㅋ\n");
    source
}

fn stats(values: &[Duration]) -> Stats {
    let mut millis: Vec<f64> = values
        .iter()
        .map(|duration| duration.as_secs_f64() * 1000.0)
        .collect();
    millis.sort_by(f64::total_cmp);
    let mean = millis.iter().sum::<f64>() / millis.len() as f64;
    let median = millis[millis.len() / 2];
    let min = *millis.first().unwrap_or(&0.0);
    let max = *millis.last().unwrap_or(&0.0);
    Stats {
        mean,
        median,
        min,
        max,
    }
}

fn print_csv_header() {
    println!(
        "runtime,workload,iterations,units,parse_mean_ms,run_mean_ms,total_mean_ms,total_median_ms,throughput_units_per_s,total_min_ms,total_max_ms"
    );
}
