use std::{
    collections::{BTreeMap, BTreeSet},
    path::{Path, PathBuf},
};

use macroquad::{audio::*, prelude::*};

use umkachu_volleyball_umlang::{
    assets,
    keymap::*,
    syscalls::*,
    um::{HostOps, Step, Vm},
};

pub struct Host {
    beep: Option<Sound>,
    sound_bank: BTreeMap<i32, Sound>,
    texture_bank: BTreeMap<i32, Texture2D>,
    audio_slots: BTreeMap<i32, i32>,
    looped_audio_slots: BTreeSet<i32>,
    texture_slots: BTreeMap<i32, i32>,
    settings: BTreeMap<i32, i32>,
    settings_prefix: PathBuf,
    settings_path: PathBuf,
    colors: BTreeMap<i32, Color>,
    soft_graphics: bool,
    target_fps: i32,
    #[cfg(not(target_arch = "wasm32"))]
    last_frame_started: Option<std::time::Instant>,
}

impl Host {
    pub async fn new(asset_root: impl Into<PathBuf>, settings_prefix: impl Into<PathBuf>) -> Self {
        let asset_root = asset_root.into();
        let settings_prefix = settings_prefix.into();
        let beep = load_sound_from_bytes(&beep_wav()).await.ok();
        let sound_bank = load_sound_bank(&asset_root).await;
        let texture_bank = load_texture_bank(&asset_root).await;
        let settings_path = settings_path_for_profile(&settings_prefix, 0);
        Self {
            beep,
            sound_bank,
            texture_bank,
            audio_slots: BTreeMap::new(),
            looped_audio_slots: BTreeSet::new(),
            texture_slots: BTreeMap::new(),
            settings: load_settings(&settings_path),
            settings_prefix,
            settings_path,
            colors: BTreeMap::new(),
            soft_graphics: false,
            target_fps: 60,
            #[cfg(not(target_arch = "wasm32"))]
            last_frame_started: None,
        }
    }

    pub fn begin_frame(&mut self) {
        #[cfg(not(target_arch = "wasm32"))]
        {
            let frame_duration =
                std::time::Duration::from_secs_f64(1.0 / f64::from(self.target_fps.clamp(1, 240)));
            if let Some(last_frame_started) = self.last_frame_started {
                if let Some(remaining) = frame_duration.checked_sub(last_frame_started.elapsed()) {
                    std::thread::sleep(remaining);
                }
            }
            self.last_frame_started = Some(std::time::Instant::now());
        }
    }

    pub fn end_frame(&mut self) {
        // Rendering is driven by the 엄랭 program; the host only presents the frame.
    }

    fn play_audio_slot(&mut self, slot: i32, looped: bool, volume_percent: i32) {
        if slot == 0 {
            return;
        }
        let volume = (volume_percent.clamp(0, 100) as f32) / 100.0;
        let sound = self
            .audio_slots
            .get(&slot)
            .and_then(|asset_id| self.sound_bank.get(asset_id));
        if let Some(sound) = sound {
            if looped {
                if self.looped_audio_slots.insert(slot) {
                    play_sound(
                        sound,
                        PlaySoundParams {
                            looped: true,
                            volume,
                        },
                    );
                }
            } else {
                play_sound(
                    sound,
                    PlaySoundParams {
                        looped: false,
                        volume,
                    },
                );
            }
        } else if !looped {
            if let Some(beep) = &self.beep {
                play_sound_once(beep);
            }
        }
    }

    fn stop_audio_slot(&mut self, slot: i32) {
        if let Some(sound) = self
            .audio_slots
            .get(&slot)
            .and_then(|asset_id| self.sound_bank.get(asset_id))
        {
            stop_sound(sound);
        }
        self.looped_audio_slots.remove(&slot);
    }

    fn save_setting(&mut self, key: i32, value: i32) {
        self.settings.insert(key, value);
        let mut text = String::new();
        for (key, value) in &self.settings {
            text.push_str(&format!("{key}={value}\n"));
        }
        let _ = std::fs::write(&self.settings_path, text);
    }

    fn configure_settings(&mut self, profile: i32) {
        let settings_path = settings_path_for_profile(&self.settings_prefix, profile);
        self.settings = if profile > 0 && !settings_path.exists() {
            load_settings(&settings_path_for_profile(&self.settings_prefix, 0))
        } else {
            load_settings(&settings_path)
        };
        self.settings_path = settings_path;
    }

    fn color_from_id(&self, id: i32) -> Color {
        self.colors.get(&id).copied().unwrap_or(MAGENTA)
    }

    fn texture_for_slot(&self, slot: i32) -> Option<&Texture2D> {
        self.texture_slots
            .get(&slot)
            .and_then(|asset_id| self.texture_bank.get(asset_id))
    }

    fn apply_texture_filter(&self) {
        let filter = if self.soft_graphics {
            FilterMode::Linear
        } else {
            FilterMode::Nearest
        };
        for asset_id in self.texture_slots.values() {
            if let Some(texture) = self.texture_bank.get(asset_id) {
                texture.set_filter(filter);
            }
        }
    }

    fn draw_texture_region(&self, slot: i32, vm: &Vm, offset: usize, alpha: i32) {
        if let Some(texture) = self.texture_for_slot(slot) {
            let source = Rect::new(
                vm.get_var(offset) as f32,
                vm.get_var(offset + 1) as f32,
                vm.get_var(offset + 2) as f32,
                vm.get_var(offset + 3) as f32,
            );
            let dest_size = Vec2::new(vm.get_var(offset + 6) as f32, vm.get_var(offset + 7) as f32);
            let mut color = WHITE;
            color.a = (alpha.clamp(0, 255) as f32) / 255.0;
            draw_texture_ex(
                texture,
                vm.get_var(offset + 4) as f32,
                vm.get_var(offset + 5) as f32,
                color,
                DrawTextureParams {
                    source: Some(source),
                    dest_size: Some(dest_size),
                    flip_x: vm.get_var(offset + 8) != 0,
                    ..Default::default()
                },
            );
        }
    }
}

impl HostOps for Host {
    fn syscall(&mut self, opcode: i32, vm: &mut Vm) -> Result<Step, String> {
        match opcode {
            SYS_CLEAR => {
                clear_background(self.color_from_id(vm.get_var(2)));
                Ok(Step::Running)
            }
            SYS_DRAW_RECT => {
                draw_rectangle(
                    vm.get_var(2) as f32,
                    vm.get_var(3) as f32,
                    vm.get_var(4) as f32,
                    vm.get_var(5) as f32,
                    self.color_from_id(vm.get_var(6)),
                );
                Ok(Step::Running)
            }
            SYS_DRAW_RECT_ALPHA => {
                let mut color = self.color_from_id(vm.get_var(6));
                color.a = (vm.get_var(7).clamp(0, 255) as f32) / 255.0;
                draw_rectangle(
                    vm.get_var(2) as f32,
                    vm.get_var(3) as f32,
                    vm.get_var(4) as f32,
                    vm.get_var(5) as f32,
                    color,
                );
                Ok(Step::Running)
            }
            SYS_DRAW_CIRCLE => {
                draw_circle(
                    vm.get_var(2) as f32,
                    vm.get_var(3) as f32,
                    vm.get_var(4) as f32,
                    self.color_from_id(vm.get_var(5)),
                );
                Ok(Step::Running)
            }
            SYS_KEY_DOWN => {
                let out = vm.get_var(3).max(0) as usize;
                let is_down = physical_key_from_code(vm.get_var(2)).is_some_and(is_key_down);
                vm.set_var(out, i32::from(is_down));
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
            SYS_WAIT_FRAME => Ok(Step::Yielded),
            SYS_DRAW_NUMBER => {
                draw_text(
                    &vm.get_var(vm.get_var(2).max(0) as usize).to_string(),
                    vm.get_var(3) as f32,
                    vm.get_var(4) as f32,
                    vm.get_var(5).max(1) as f32,
                    self.color_from_id(vm.get_var(6)),
                );
                Ok(Step::Running)
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
            SYS_KEY_PRESSED => {
                let out = vm.get_var(3).max(0) as usize;
                let is_pressed = physical_key_from_code(vm.get_var(2)).is_some_and(is_key_pressed);
                vm.set_var(out, i32::from(is_pressed));
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
            SYS_SET_TEXTURE_FILTER => {
                self.soft_graphics = vm.get_var(2) != 0;
                self.apply_texture_filter();
                Ok(Step::Running)
            }
            SYS_SET_TARGET_FPS => {
                self.target_fps = vm.get_var(2).clamp(1, 240);
                Ok(Step::Running)
            }
            SYS_LOAD_SETTING => {
                let key = vm.get_var(2);
                let dst = vm.get_var(3).max(0) as usize;
                let default = vm.get_var(4);
                vm.set_var(dst, self.settings.get(&key).copied().unwrap_or(default));
                Ok(Step::Running)
            }
            SYS_SAVE_SETTING => {
                self.save_setting(vm.get_var(2), vm.get_var(3));
                Ok(Step::Running)
            }
            SYS_DEFINE_COLOR => {
                self.colors.insert(
                    vm.get_var(2),
                    Color::from_rgba(
                        vm.get_var(3).clamp(0, 255) as u8,
                        vm.get_var(4).clamp(0, 255) as u8,
                        vm.get_var(5).clamp(0, 255) as u8,
                        vm.get_var(6).clamp(0, 255) as u8,
                    ),
                );
                Ok(Step::Running)
            }
            SYS_CONFIGURE_WINDOW => {
                let width = vm.get_var(2).clamp(1, 16_384) as f32;
                let height = vm.get_var(3).clamp(1, 16_384) as f32;
                request_new_screen_size(width, height);
                Ok(Step::Running)
            }
            SYS_CONFIGURE_SETTINGS => {
                self.configure_settings(vm.get_var(2));
                Ok(Step::Running)
            }
            SYS_DEFINE_TEXTURE => {
                self.texture_slots.insert(vm.get_var(2), vm.get_var(3));
                self.apply_texture_filter();
                Ok(Step::Running)
            }
            SYS_DRAW_TEXTURE => {
                self.draw_texture_region(vm.get_var(2), vm, 3, 255);
                Ok(Step::Running)
            }
            SYS_DRAW_TEXTURE_ALPHA => {
                self.draw_texture_region(vm.get_var(2), vm, 3, vm.get_var(12));
                Ok(Step::Running)
            }
            SYS_DEFINE_AUDIO => {
                self.audio_slots.insert(vm.get_var(2), vm.get_var(3));
                Ok(Step::Running)
            }
            SYS_PLAY_AUDIO => {
                self.play_audio_slot(vm.get_var(2), vm.get_var(3) != 0, vm.get_var(4));
                Ok(Step::Running)
            }
            SYS_STOP_AUDIO => {
                self.stop_audio_slot(vm.get_var(2));
                Ok(Step::Running)
            }
            _ => Err(format!("unknown host syscall opcode {opcode}")),
        }
    }
}

async fn load_sound_bank(asset_root: &Path) -> BTreeMap<i32, Sound> {
    let mut sounds = BTreeMap::new();
    let mut paths = collect_asset_paths(asset_root, &["wav"]);
    paths.sort();
    paths.dedup();

    for path in paths {
        let Some(asset_id) = assets::asset_id_for_path(&path) else {
            continue;
        };
        let Some(path) = path.to_str() else {
            continue;
        };
        if let Ok(sound) = load_sound(path).await {
            sounds.insert(asset_id, sound);
        }
    }

    sounds
}

async fn load_texture_bank(asset_root: &Path) -> BTreeMap<i32, Texture2D> {
    let mut textures = BTreeMap::new();
    let mut paths = collect_asset_paths(asset_root, &["png"]);
    paths.sort();

    for path in paths {
        let Some(asset_id) = assets::asset_id_for_path(&path) else {
            continue;
        };
        let Some(path) = path.to_str() else {
            continue;
        };
        if let Ok(texture) = load_texture(path).await {
            texture.set_filter(FilterMode::Nearest);
            textures.insert(asset_id, texture);
        }
    }

    textures
}

fn collect_asset_paths(root: &Path, extensions: &[&str]) -> Vec<PathBuf> {
    let mut paths = Vec::new();
    let mut pending = vec![root.to_path_buf()];

    while let Some(path) = pending.pop() {
        if path.is_dir() {
            let Ok(entries) = std::fs::read_dir(path) else {
                continue;
            };
            pending.extend(entries.flatten().map(|entry| entry.path()));
            continue;
        }

        let Some(extension) = path.extension().and_then(|value| value.to_str()) else {
            continue;
        };
        if extensions
            .iter()
            .any(|candidate| extension.eq_ignore_ascii_case(candidate))
        {
            paths.push(path);
        }
    }

    paths
}

fn settings_path_for_profile(prefix: &Path, profile: i32) -> PathBuf {
    if profile <= 0 {
        return prefix.to_path_buf();
    }
    let mut path = prefix.as_os_str().to_owned();
    path.push(format!("-{profile}"));
    PathBuf::from(path)
}

fn load_settings(path: &Path) -> BTreeMap<i32, i32> {
    let mut settings = BTreeMap::new();
    let Ok(text) = std::fs::read_to_string(path) else {
        return settings;
    };
    for line in text.lines() {
        let Some((key, value)) = line.split_once('=') else {
            continue;
        };
        let (Ok(key), Ok(value)) = (key.trim().parse(), value.trim().parse()) else {
            continue;
        };
        settings.insert(key, value);
    }
    settings
}

fn physical_key_from_code(code: i32) -> Option<KeyCode> {
    Some(match code {
        KEY_BACKSPACE => KeyCode::Backspace,
        KEY_ENTER => KeyCode::Enter,
        KEY_SPACE => KeyCode::Space,
        KEY_LEFT_BRACKET => KeyCode::LeftBracket,
        KEY_BACKSLASH => KeyCode::Backslash,
        KEY_RIGHT_BRACKET => KeyCode::RightBracket,
        KEY_LEFT => KeyCode::Left,
        KEY_RIGHT => KeyCode::Right,
        KEY_UP => KeyCode::Up,
        KEY_DOWN => KeyCode::Down,
        KEY_0..=KEY_9 => digit_key_from_code(code)?,
        KEY_A..=KEY_Z => letter_key_from_code(code)?,
        code if (i32::from(b'a')..=i32::from(b'z')).contains(&code) => {
            letter_key_from_code(code - i32::from(b'a' - b'A'))?
        }
        _ => return None,
    })
}

fn digit_key_from_code(code: i32) -> Option<KeyCode> {
    Some(match code {
        48 => KeyCode::Key0,
        49 => KeyCode::Key1,
        50 => KeyCode::Key2,
        51 => KeyCode::Key3,
        52 => KeyCode::Key4,
        53 => KeyCode::Key5,
        54 => KeyCode::Key6,
        55 => KeyCode::Key7,
        56 => KeyCode::Key8,
        57 => KeyCode::Key9,
        _ => return None,
    })
}

fn letter_key_from_code(code: i32) -> Option<KeyCode> {
    Some(match code {
        65 => KeyCode::A,
        66 => KeyCode::B,
        67 => KeyCode::C,
        68 => KeyCode::D,
        69 => KeyCode::E,
        70 => KeyCode::F,
        71 => KeyCode::G,
        72 => KeyCode::H,
        73 => KeyCode::I,
        74 => KeyCode::J,
        75 => KeyCode::K,
        76 => KeyCode::L,
        77 => KeyCode::M,
        78 => KeyCode::N,
        79 => KeyCode::O,
        80 => KeyCode::P,
        81 => KeyCode::Q,
        82 => KeyCode::R,
        83 => KeyCode::S,
        84 => KeyCode::T,
        85 => KeyCode::U,
        86 => KeyCode::V,
        87 => KeyCode::W,
        88 => KeyCode::X,
        89 => KeyCode::Y,
        90 => KeyCode::Z,
        _ => return None,
    })
}

fn beep_wav() -> Vec<u8> {
    let sample_rate = 44_100u32;
    let duration_samples = sample_rate / 16;
    let data_len = duration_samples * 2;
    let mut out = Vec::with_capacity(44 + data_len as usize);
    out.extend_from_slice(b"RIFF");
    out.extend_from_slice(&(36 + data_len).to_le_bytes());
    out.extend_from_slice(b"WAVEfmt ");
    out.extend_from_slice(&16u32.to_le_bytes());
    out.extend_from_slice(&1u16.to_le_bytes());
    out.extend_from_slice(&1u16.to_le_bytes());
    out.extend_from_slice(&sample_rate.to_le_bytes());
    out.extend_from_slice(&(sample_rate * 2).to_le_bytes());
    out.extend_from_slice(&2u16.to_le_bytes());
    out.extend_from_slice(&16u16.to_le_bytes());
    out.extend_from_slice(b"data");
    out.extend_from_slice(&data_len.to_le_bytes());
    for i in 0..duration_samples {
        let phase = (i * 880 / sample_rate) % 2;
        let sample: i16 = if phase == 0 { 9000 } else { -9000 };
        out.extend_from_slice(&sample.to_le_bytes());
    }
    out
}
