mod host;

use std::{env, fs};

use host::Host;
use macroquad::prelude::*;
use umkachu_volleyball_umlang::{
    package,
    um::{Step, Vm},
};

fn window_conf() -> Conf {
    let config = package::default_config().ok();
    Conf {
        window_title: config
            .as_ref()
            .map(|config| config.window_title.clone())
            .unwrap_or_else(|| package::DEFAULT_WINDOW_TITLE.to_string()),
        window_width: config
            .as_ref()
            .map(|config| config.window_width)
            .unwrap_or(package::DEFAULT_WINDOW_WIDTH),
        window_height: config
            .as_ref()
            .map(|config| config.window_height)
            .unwrap_or(package::DEFAULT_WINDOW_HEIGHT),
        high_dpi: config
            .as_ref()
            .map(|config| config.high_dpi)
            .unwrap_or(package::DEFAULT_HIGH_DPI),
        ..Default::default()
    }
}

#[macroquad::main(window_conf)]
async fn main() {
    let package_config = package::default_config();
    let script_path = env::args().nth(1).unwrap_or_else(|| {
        package_config
            .as_ref()
            .unwrap_or_else(|err| panic!("{err}"))
            .main
            .clone()
    });
    let (asset_root, settings_prefix, max_steps_per_frame) = package_config
        .as_ref()
        .map(|config| {
            (
                config.asset_root.clone(),
                config.settings_prefix.clone(),
                config.max_steps_per_frame,
            )
        })
        .unwrap_or_else(|_| {
            (
                package::DEFAULT_ASSET_ROOT.to_string(),
                package::DEFAULT_SETTINGS_PREFIX.to_string(),
                package::DEFAULT_MAX_STEPS_PER_FRAME,
            )
        });
    let source = fs::read_to_string(&script_path)
        .unwrap_or_else(|err| panic!("failed to read {script_path}: {err}"));
    let mut vm = Vm::parse(&source).unwrap_or_else(|err| panic!("엄랭 parse error: {err}"));
    let mut host = Host::new(asset_root, settings_prefix).await;

    loop {
        host.begin_frame();

        match vm.run_until_yield(&mut host, max_steps_per_frame) {
            Ok(Step::Running) | Ok(Step::Yielded) => {}
            Ok(Step::Exited(code)) => {
                clear_background(BLACK);
                draw_text(
                    &format!("엄랭 program exited with code {code}"),
                    30.0,
                    60.0,
                    32.0,
                    WHITE,
                );
            }
            Err(err) => {
                clear_background(BLACK);
                draw_text("엄랭 runtime error", 30.0, 60.0, 36.0, RED);
                draw_text(&err, 30.0, 105.0, 24.0, WHITE);
            }
        }

        host.end_frame();
        next_frame().await;
    }
}
