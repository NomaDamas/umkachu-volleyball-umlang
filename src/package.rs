use std::fs;

pub const ABI_DIR: &str = "package/abi";
pub const DEFAULT_MANIFEST_PATH: &str = "package/abi/umlang-package.txt";
pub const DEFAULT_ASSET_ROOT: &str = "assets";
pub const DEFAULT_MAX_STEPS_PER_FRAME: usize = 200_000;
pub const DEFAULT_SETTINGS_PREFIX: &str = ".umlang-settings";
pub const DEFAULT_WINDOW_TITLE: &str = "엄랭 실행기";
pub const DEFAULT_WINDOW_WIDTH: i32 = 640;
pub const DEFAULT_WINDOW_HEIGHT: i32 = 480;
pub const DEFAULT_HIGH_DPI: bool = true;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PackageConfig {
    pub main: String,
    pub asset_root: String,
    pub max_steps_per_frame: usize,
    pub settings_prefix: String,
    pub window_title: String,
    pub window_width: i32,
    pub window_height: i32,
    pub high_dpi: bool,
}

pub fn default_script_path() -> Result<String, String> {
    Ok(default_config()?.main)
}

pub fn default_config() -> Result<PackageConfig, String> {
    let manifest = fs::read_to_string(DEFAULT_MANIFEST_PATH)
        .map_err(|err| format!("failed to read {DEFAULT_MANIFEST_PATH}: {err}"))?;
    parse_manifest_config(&manifest)
        .ok_or_else(|| format!("{DEFAULT_MANIFEST_PATH} must contain a non-empty main=... entry"))
}

pub fn parse_manifest_main(manifest: &str) -> Option<String> {
    parse_manifest_config(manifest).map(|config| config.main)
}

pub fn parse_manifest_config(manifest: &str) -> Option<PackageConfig> {
    let mut main = None;
    let mut asset_root = DEFAULT_ASSET_ROOT.to_string();
    let mut max_steps_per_frame = DEFAULT_MAX_STEPS_PER_FRAME;
    let mut settings_prefix = DEFAULT_SETTINGS_PREFIX.to_string();
    let mut window_title = DEFAULT_WINDOW_TITLE.to_string();
    let mut window_width = DEFAULT_WINDOW_WIDTH;
    let mut window_height = DEFAULT_WINDOW_HEIGHT;
    let mut high_dpi = DEFAULT_HIGH_DPI;

    for line in manifest.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let Some((key, value)) = line.split_once('=') else {
            continue;
        };
        let key = key.trim();
        let value = value.trim();
        if value.is_empty() {
            continue;
        }
        match key {
            "main" => main = Some(value.to_string()),
            "asset_root" => asset_root = value.to_string(),
            "settings_prefix" => settings_prefix = value.to_string(),
            "window_title" => window_title = value.to_string(),
            "max_steps_per_frame" => {
                if let Ok(value) = value.parse::<usize>() {
                    if value > 0 {
                        max_steps_per_frame = value;
                    }
                }
            }
            "window_width" => {
                if let Ok(value) = value.parse::<i32>() {
                    if value > 0 {
                        window_width = value;
                    }
                }
            }
            "window_height" => {
                if let Ok(value) = value.parse::<i32>() {
                    if value > 0 {
                        window_height = value;
                    }
                }
            }
            "high_dpi" => {
                if let Some(value) = parse_bool(value) {
                    high_dpi = value;
                }
            }
            _ => {}
        }
    }

    Some(PackageConfig {
        main: main?,
        asset_root,
        max_steps_per_frame,
        settings_prefix,
        window_title,
        window_width,
        window_height,
        high_dpi,
    })
}

fn parse_bool(value: &str) -> Option<bool> {
    match value.trim().to_ascii_lowercase().as_str() {
        "1" | "true" | "yes" | "on" => Some(true),
        "0" | "false" | "no" | "off" => Some(false),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_main_script_path_from_manifest() {
        let manifest = "\n# package entry\nname = ignored\nmain = game.umm\n";

        assert_eq!(parse_manifest_main(manifest), Some("game.umm".to_string()));
    }

    #[test]
    fn parses_asset_root_from_manifest() {
        let manifest = "\nmain = game.umm\nasset_root = game-assets\n";

        assert_eq!(
            parse_manifest_config(manifest),
            Some(PackageConfig {
                main: "game.umm".to_string(),
                asset_root: "game-assets".to_string(),
                max_steps_per_frame: DEFAULT_MAX_STEPS_PER_FRAME,
                settings_prefix: DEFAULT_SETTINGS_PREFIX.to_string(),
                window_title: DEFAULT_WINDOW_TITLE.to_string(),
                window_width: DEFAULT_WINDOW_WIDTH,
                window_height: DEFAULT_WINDOW_HEIGHT,
                high_dpi: DEFAULT_HIGH_DPI,
            })
        );
    }

    #[test]
    fn defaults_asset_root_when_manifest_omits_it() {
        assert_eq!(
            parse_manifest_config("main = game.umm\n"),
            Some(PackageConfig {
                main: "game.umm".to_string(),
                asset_root: DEFAULT_ASSET_ROOT.to_string(),
                max_steps_per_frame: DEFAULT_MAX_STEPS_PER_FRAME,
                settings_prefix: DEFAULT_SETTINGS_PREFIX.to_string(),
                window_title: DEFAULT_WINDOW_TITLE.to_string(),
                window_width: DEFAULT_WINDOW_WIDTH,
                window_height: DEFAULT_WINDOW_HEIGHT,
                high_dpi: DEFAULT_HIGH_DPI,
            })
        );
    }

    #[test]
    fn parses_max_steps_per_frame_from_manifest() {
        let manifest = "\nmain = game.umm\nmax_steps_per_frame = 800000\n";

        assert_eq!(
            parse_manifest_config(manifest),
            Some(PackageConfig {
                main: "game.umm".to_string(),
                asset_root: DEFAULT_ASSET_ROOT.to_string(),
                max_steps_per_frame: 800_000,
                settings_prefix: DEFAULT_SETTINGS_PREFIX.to_string(),
                window_title: DEFAULT_WINDOW_TITLE.to_string(),
                window_width: DEFAULT_WINDOW_WIDTH,
                window_height: DEFAULT_WINDOW_HEIGHT,
                high_dpi: DEFAULT_HIGH_DPI,
            })
        );
    }

    #[test]
    fn parses_runner_settings_from_manifest() {
        let manifest = "\nmain = game.umm\nsettings_prefix = saves/game\nwindow_title = Game\nwindow_width = 320\nwindow_height = 240\nhigh_dpi = false\n";

        assert_eq!(
            parse_manifest_config(manifest),
            Some(PackageConfig {
                main: "game.umm".to_string(),
                asset_root: DEFAULT_ASSET_ROOT.to_string(),
                max_steps_per_frame: DEFAULT_MAX_STEPS_PER_FRAME,
                settings_prefix: "saves/game".to_string(),
                window_title: "Game".to_string(),
                window_width: 320,
                window_height: 240,
                high_dpi: false,
            })
        );
    }

    #[test]
    fn ignores_empty_main_script_path() {
        assert_eq!(parse_manifest_main("main = \n"), None);
    }

    #[test]
    fn parses_bool_literals() {
        assert_eq!(parse_bool("true"), Some(true));
        assert_eq!(parse_bool("off"), Some(false));
        assert_eq!(parse_bool("maybe"), None);
    }
}
