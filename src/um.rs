use std::{
    collections::BTreeSet,
    fs,
    path::{Path, PathBuf},
};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Step {
    Running,
    Yielded,
    Exited(i32),
}

pub trait HostOps {
    fn syscall(&mut self, opcode: i32, vm: &mut Vm) -> Result<Step, String>;
}

#[derive(Debug, Clone)]
enum Instruction {
    Raw(String),
    Noop,
    Conditional {
        condition: Expr,
        statement: Box<Instruction>,
    },
    Jump {
        target: Expr,
    },
    Exit {
        code: Option<Expr>,
    },
    Assign {
        index: usize,
        value: Option<Expr>,
    },
    OutputNumber {
        value: Option<Expr>,
    },
    OutputChar {
        value: Option<Expr>,
    },
}

#[derive(Debug, Clone)]
struct Expr {
    terms: Vec<ExprTerm>,
}

#[derive(Debug, Clone, Copy)]
struct ExprTerm {
    load_var: Option<usize>,
    offset: i32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum PendingStep {
    Running,
    HostSyscall(i32),
    PrintNumber(i32),
    PrintChar(Option<char>),
    Exited(i32),
}

pub struct Vm {
    instructions: Vec<Instruction>,
    vars: Vec<i32>,
    pc: usize,
    exit: Option<i32>,
}

impl Vm {
    pub fn parse(source: &str) -> Result<Self, String> {
        let expanded = expand_imports(source, None, &mut BTreeSet::new())?;
        Self::parse_expanded(&expanded)
    }

    pub fn parse_file(path: impl AsRef<Path>) -> Result<Self, String> {
        let source = load_source_file(path.as_ref())?;
        Self::parse_expanded(&source)
    }

    pub fn load_source_file(path: impl AsRef<Path>) -> Result<String, String> {
        load_source_file(path.as_ref())
    }

    fn parse_expanded(source: &str) -> Result<Self, String> {
        let normalized = source.replace("\r\n", "\n").replace('\r', "\n");
        let parts: Vec<&str> = if normalized.contains('~') {
            normalized.split('~').collect()
        } else {
            normalized.lines().collect()
        };
        let first = parts
            .first()
            .map(|line| line.trim())
            .ok_or_else(|| "empty source".to_string())?;
        let last = parts
            .iter()
            .rev()
            .find(|line| !line.trim().is_empty())
            .map(|line| line.trim())
            .ok_or_else(|| "empty source".to_string())?;

        if first != "어떻게" {
            return Err("program must start with 어떻게".to_string());
        }
        if last != "이 사람이름이냐ㅋㅋ" {
            return Err("program must end with 이 사람이름이냐ㅋㅋ".to_string());
        }

        let mut instructions = vec![Instruction::Noop];
        for raw in parts.iter().skip(1) {
            let line = raw.trim();
            if line == "이 사람이름이냐ㅋㅋ" {
                break;
            }
            if line.is_empty() {
                instructions.push(Instruction::Noop);
            } else {
                instructions.push(Instruction::Raw(line.to_string()));
            }
        }
        instructions.push(Instruction::Noop);

        Ok(Self {
            instructions,
            vars: vec![0; 4096],
            pc: 0,
            exit: None,
        })
    }

    pub fn run_until_yield<H: HostOps>(
        &mut self,
        host: &mut H,
        max_steps: usize,
    ) -> Result<Step, String> {
        let mut steps = 0usize;
        while self.pc < self.instructions.len() {
            let instruction_index = self.pc;
            self.pc += 1;
            self.compile_instruction(instruction_index)?;
            let action = execute_instruction(
                &self.instructions[instruction_index],
                &mut self.vars,
                &mut self.pc,
                &mut self.exit,
                self.instructions.len(),
            )?;
            match action {
                PendingStep::Running => {}
                PendingStep::HostSyscall(opcode) => match host.syscall(opcode, self)? {
                    Step::Running => {}
                    Step::Yielded => return Ok(Step::Yielded),
                    Step::Exited(code) => return Ok(Step::Exited(code)),
                },
                PendingStep::PrintNumber(value) => println!("{value}"),
                PendingStep::PrintChar(None) => println!(),
                PendingStep::PrintChar(Some(ch)) => print!("{ch}"),
                PendingStep::Exited(code) => return Ok(Step::Exited(code)),
            }

            steps += 1;
            if steps >= max_steps {
                return Err(format!(
                    "instruction limit reached near line {}",
                    self.pc.saturating_add(1)
                ));
            }
            if let Some(code) = self.exit {
                return Ok(Step::Exited(code));
            }
        }
        Ok(Step::Exited(self.exit.unwrap_or(0)))
    }

    pub fn get_var(&self, index: usize) -> i32 {
        self.vars.get(index).copied().unwrap_or(0)
    }

    pub fn set_var(&mut self, index: usize, value: i32) {
        if index >= self.vars.len() {
            self.vars.resize(index + 1, 0);
        }
        self.vars[index] = value;
    }

    fn compile_instruction(&mut self, index: usize) -> Result<(), String> {
        let raw = match &self.instructions[index] {
            Instruction::Raw(code) => Some(code.clone()),
            _ => None,
        };
        if let Some(raw) = raw {
            self.instructions[index] = parse_statement(&raw)?;
        }
        Ok(())
    }
}

fn parse_statement(code: &str) -> Result<Instruction, String> {
    if let Some(rest) = code.strip_prefix("동탄") {
        let (condition, statement) = rest
            .split_once('?')
            .ok_or_else(|| format!("invalid 동탄 statement: {code}"))?;
        return Ok(Instruction::Conditional {
            condition: parse_expr(condition),
            statement: Box::new(parse_statement(statement)?),
        });
    }

    if let Some(rest) = code.strip_prefix("준") {
        return Ok(Instruction::Jump {
            target: parse_expr(rest),
        });
    }

    if let Some(rest) = code.strip_prefix("화이팅!") {
        return Ok(Instruction::Exit {
            code: parse_optional_expr(rest),
        });
    }

    if let Some((left, right)) = code.split_once('엄') {
        return Ok(Instruction::Assign {
            index: left.matches('어').count() + 1,
            value: parse_optional_expr(right),
        });
    }

    if code.starts_with('식') && code.ends_with('!') {
        let expr = &code['식'.len_utf8()..code.len() - '!'.len_utf8()];
        return Ok(Instruction::OutputNumber {
            value: parse_optional_expr(expr),
        });
    }

    if code.starts_with('식') && code.ends_with('ㅋ') {
        let expr = &code['식'.len_utf8()..code.len() - 'ㅋ'.len_utf8()];
        return Ok(Instruction::OutputChar {
            value: parse_optional_expr(expr),
        });
    }

    Err(format!("unknown statement: {code}"))
}

fn parse_optional_expr(expr: &str) -> Option<Expr> {
    (!expr.trim().is_empty()).then(|| parse_expr(expr))
}

fn parse_expr(expr: &str) -> Expr {
    let terms = expr
        .split(' ')
        .filter(|term| !term.is_empty())
        .map(parse_expr_term)
        .collect();
    Expr { terms }
}

fn parse_expr_term(term: &str) -> ExprTerm {
    let mut load_count = 0usize;
    let mut offset = 0i32;
    for ch in term.chars() {
        match ch {
            '어' => load_count += 1,
            '.' => offset = offset.wrapping_add(1),
            ',' => offset = offset.wrapping_sub(1),
            _ => {}
        }
    }
    ExprTerm {
        load_var: (load_count > 0).then_some(load_count),
        offset,
    }
}

fn execute_instruction(
    instruction: &Instruction,
    vars: &mut Vec<i32>,
    pc: &mut usize,
    exit: &mut Option<i32>,
    instruction_count: usize,
) -> Result<PendingStep, String> {
    match instruction {
        Instruction::Raw(code) => Err(format!("uncompiled statement: {code}")),
        Instruction::Noop => Ok(PendingStep::Running),
        Instruction::Conditional {
            condition,
            statement,
        } => {
            if eval_expr(vars, condition) == 0 {
                execute_instruction(statement, vars, pc, exit, instruction_count)
            } else {
                Ok(PendingStep::Running)
            }
        }
        Instruction::Jump { target } => {
            let line = eval_expr(vars, target);
            if line <= 0 {
                return Err(format!("준 target out of range: {line}"));
            }
            let target = line as usize - 1;
            if target >= instruction_count {
                return Err(format!("준 target out of range: {line}"));
            }
            *pc = target;
            Ok(PendingStep::Running)
        }
        Instruction::Exit { code } => {
            let code = eval_optional_expr(vars, code);
            *exit = Some(code);
            Ok(PendingStep::Exited(code))
        }
        Instruction::Assign { index, value } => {
            let value = eval_optional_expr(vars, value);
            set_var(vars, *index, value);
            Ok(PendingStep::Running)
        }
        Instruction::OutputNumber { value } => {
            let value = eval_optional_expr(vars, value);
            if value < 0 {
                Ok(PendingStep::HostSyscall(value))
            } else {
                Ok(PendingStep::PrintNumber(value))
            }
        }
        Instruction::OutputChar { value } => {
            let Some(value) = value else {
                return Ok(PendingStep::PrintChar(None));
            };
            Ok(PendingStep::PrintChar(char::from_u32(
                eval_expr(vars, value) as u32,
            )))
        }
    }
}

fn eval_optional_expr(vars: &[i32], expr: &Option<Expr>) -> i32 {
    expr.as_ref().map_or(0, |expr| eval_expr(vars, expr))
}

fn eval_expr(vars: &[i32], expr: &Expr) -> i32 {
    if expr.terms.is_empty() {
        return 0;
    }

    expr.terms.iter().fold(1i32, |result, term| {
        let value = term
            .load_var
            .and_then(|index| vars.get(index).copied())
            .unwrap_or(0)
            .wrapping_add(term.offset);
        result.wrapping_mul(value)
    })
}

fn set_var(vars: &mut Vec<i32>, index: usize, value: i32) {
    if index >= vars.len() {
        vars.resize(index + 1, 0);
    }
    vars[index] = value;
}

fn load_source_file(path: &Path) -> Result<String, String> {
    let canonical = path
        .canonicalize()
        .map_err(|err| format!("failed to resolve {}: {err}", path.display()))?;
    let source = fs::read_to_string(&canonical)
        .map_err(|err| format!("failed to read {}: {err}", canonical.display()))?;
    let base_dir = canonical.parent().unwrap_or_else(|| Path::new("."));
    expand_imports(&source, Some(base_dir), &mut BTreeSet::new())
}

fn expand_imports(
    source: &str,
    base_dir: Option<&Path>,
    stack: &mut BTreeSet<PathBuf>,
) -> Result<String, String> {
    let normalized = source.replace("\r\n", "\n").replace('\r', "\n");
    let parts: Vec<&str> = if normalized.contains('~') {
        normalized.split('~').collect()
    } else {
        normalized.lines().collect()
    };
    let mut expanded = String::new();

    for raw in parts {
        let line = raw.trim();
        if let Some(path) = import_path(line) {
            let resolved = resolve_import_path(path, base_dir)?;
            let source = fs::read_to_string(&resolved)
                .map_err(|err| format!("failed to read {}: {err}", resolved.display()))?;
            if !stack.insert(resolved.clone()) {
                return Err(format!("cyclic Umlang import: {}", resolved.display()));
            }
            let imported_base = resolved.parent().unwrap_or_else(|| Path::new("."));
            expanded.push_str(&expand_imports(&source, Some(imported_base), stack)?);
            stack.remove(&resolved);
        } else {
            expanded.push_str(raw);
            expanded.push('\n');
        }
    }

    Ok(expanded)
}

fn import_path(line: &str) -> Option<&str> {
    line.strip_prefix("가져와 ")
        .or_else(|| line.strip_prefix("include "))
        .or_else(|| line.strip_prefix("import "))
        .map(|path| path.trim().trim_matches('"'))
        .filter(|path| !path.is_empty())
}

fn resolve_import_path(path: &str, base_dir: Option<&Path>) -> Result<PathBuf, String> {
    let path = Path::new(path);
    let joined = if path.is_absolute() {
        path.to_path_buf()
    } else {
        base_dir.unwrap_or_else(|| Path::new(".")).join(path)
    };
    if let Ok(canonical) = joined.canonicalize() {
        return Ok(canonical);
    }
    if !path.is_absolute() {
        if let Ok(canonical) = path.canonicalize() {
            return Ok(canonical);
        }
    }
    Err(format!(
        "failed to resolve Umlang import {}",
        joined.display()
    ))
}

#[cfg(test)]
mod tests {
    use crate::animation as package_animation;
    use crate::assets as package_assets;
    use crate::game as package_game;
    use crate::keymap;
    use crate::menu as package_menu;
    use crate::palette as package_palette;
    use crate::player as package_player;
    use crate::render as package_render;
    use crate::rng as package_rng;
    use crate::settings as package_settings;
    use crate::sfx as package_sfx;
    use crate::sprites as package_sprites;
    use crate::syscalls::*;
    use crate::timing as package_timing;
    use crate::vars::*;

    use super::*;

    #[derive(Default)]
    struct FakeHost {
        yields: usize,
        played_sounds: Vec<i32>,
        sound_events: Vec<[i32; 3]>,
        bgm_plays: usize,
        bgm_stops: usize,
        texture_filters: Vec<i32>,
        target_fps_values: Vec<i32>,
        defined_colors: Vec<[i32; 5]>,
        defined_textures: Vec<[i32; 2]>,
        defined_audio: Vec<[i32; 2]>,
        configured_windows: Vec<[i32; 2]>,
        configured_settings: Vec<i32>,
        settings: std::collections::BTreeMap<i32, i32>,
        saved_settings: Vec<[i32; 2]>,
        keys_down: Vec<i32>,
        keys_pressed: Vec<i32>,
        record_sprites: bool,
        drawn_sprites: Vec<[i32; 8]>,
        drawn_sprite_calls: Vec<[i32; 9]>,
        alpha_sprites: Vec<[i32; 9]>,
        alpha_rects: Vec<[i32; 6]>,
    }

    const FIXED_GOLDEN_RAND: i32 = 13_762;
    const SETTING_WINNING_SCORE: i32 = package_settings::SETTING_WINNING_SCORE;
    const SETTING_PRACTICE_MODE: i32 = package_settings::SETTING_PRACTICE_MODE;
    const SETTING_BGM_ON: i32 = package_settings::SETTING_BGM_ON;
    const SETTING_SFX_MODE: i32 = package_settings::SETTING_SFX_MODE;
    const SETTING_SOFT_GRAPHICS: i32 = package_settings::SETTING_SOFT_GRAPHICS;
    const SETTING_TARGET_FPS: i32 = package_settings::SETTING_TARGET_FPS;
    const SCREEN_SCALE: i32 = package_game::SCREEN_SCALE;
    fn expected_asset_id(relative_path: &str) -> i32 {
        let config = crate::package::default_config().expect("package manifest should parse");
        package_assets::asset_id_for_asset_path(&config.asset_root, relative_path)
    }

    fn expected_settings_profile() -> i32 {
        package_assets::asset_id_for_normalized_path(package_assets::SETTINGS_PROFILE)
    }

    fn expected_sfx_bank() -> Vec<[i32; 4]> {
        package_assets::SFX_WAVES
            .iter()
            .enumerate()
            .map(|(index, wave)| {
                let sound_id = (index + 1) as i32;
                [
                    sound_id,
                    expected_asset_id(&format!("sfx/WAVE{wave}_1.wav")),
                    expected_asset_id(&format!("sfx/stereo/WAVE{wave}_1_left.wav")),
                    expected_asset_id(&format!("sfx/stereo/WAVE{wave}_1_right.wav")),
                ]
            })
            .collect()
    }

    fn sfx_audio_slot(sound_id: i32, mode: i32, side: i32) -> i32 {
        let side_code = match side {
            -1 => package_assets::SFX_LEFT_SIDE_CODE,
            0 => package_assets::SFX_CENTER_SIDE_CODE,
            1 => package_assets::SFX_RIGHT_SIDE_CODE,
            _ => panic!("invalid side {side}"),
        };
        package_assets::SFX_BASE_SLOT
            + sound_id * package_assets::SFX_SOUND_STRIDE
            + mode * package_assets::SFX_MODE_STRIDE
            + side_code
    }

    fn expected_audio_definitions() -> Vec<[i32; 2]> {
        let mut expected = vec![[
            package_assets::BGM_AUDIO_SLOT,
            expected_asset_id(package_assets::BGM_AUDIO),
        ]];
        for [sound_id, center_asset, left_asset, right_asset] in expected_sfx_bank() {
            expected.extend([
                [
                    sfx_audio_slot(sound_id, package_assets::SFX_MONO_MODE, -1),
                    center_asset,
                ],
                [
                    sfx_audio_slot(sound_id, package_assets::SFX_MONO_MODE, 0),
                    center_asset,
                ],
                [
                    sfx_audio_slot(sound_id, package_assets::SFX_MONO_MODE, 1),
                    center_asset,
                ],
                [
                    sfx_audio_slot(sound_id, package_assets::SFX_STEREO_MODE, -1),
                    left_asset,
                ],
                [
                    sfx_audio_slot(sound_id, package_assets::SFX_STEREO_MODE, 0),
                    center_asset,
                ],
                [
                    sfx_audio_slot(sound_id, package_assets::SFX_STEREO_MODE, 1),
                    right_asset,
                ],
            ]);
        }
        expected
    }

    fn decode_sfx_audio_slot(slot: i32) -> Option<[i32; 3]> {
        let value = slot.checked_sub(package_assets::SFX_BASE_SLOT)?;
        let sound_id = value / package_assets::SFX_SOUND_STRIDE;
        let mode_and_side = value % package_assets::SFX_SOUND_STRIDE;
        let mode = mode_and_side / package_assets::SFX_MODE_STRIDE;
        let side = match mode_and_side % package_assets::SFX_MODE_STRIDE {
            package_assets::SFX_LEFT_SIDE_CODE => -1,
            package_assets::SFX_CENTER_SIDE_CODE => 0,
            package_assets::SFX_RIGHT_SIDE_CODE => 1,
            _ => return None,
        };
        if (1..=package_assets::SFX_WAVES.len() as i32).contains(&sound_id)
            && [
                package_assets::SFX_MONO_MODE,
                package_assets::SFX_STEREO_MODE,
            ]
            .contains(&mode)
        {
            Some([sound_id, mode, side])
        } else {
            None
        }
    }

    fn expected_window_size() -> [i32; 2] {
        let config = crate::package::default_config().expect("package manifest should parse");
        [config.window_width, config.window_height]
    }

    fn setting_min(values: &[i32]) -> i32 {
        *values
            .iter()
            .min()
            .expect("setting values should not be empty")
    }

    fn setting_max(values: &[i32]) -> i32 {
        *values
            .iter()
            .max()
            .expect("setting values should not be empty")
    }

    fn setting_three_values(values: &[i32]) -> [i32; 3] {
        assert_eq!(values.len(), 3, "setting should have three hotkey values");
        [values[0], values[1], values[2]]
    }

    fn action_id_for_key_code(key_code: i32) -> Option<i32> {
        keymap::KEY_BINDINGS
            .iter()
            .find_map(|binding| (binding.code == key_code).then_some(binding.action))
    }

    fn contains_test_key(keys: &[i32], key_code: i32) -> bool {
        action_id_for_key_code(key_code).is_some_and(|action_id| keys.contains(&action_id))
    }

    fn run_with_pressed_key(vm: &mut Vm, host: &mut FakeHost, key: i32, message: &str) {
        host.keys_pressed.clear();
        host.keys_pressed.push(key);
        assert_eq!(
            vm.run_until_yield(host, 600_000).expect(message),
            Step::Yielded
        );
        host.keys_pressed.clear();
    }

    impl HostOps for FakeHost {
        fn syscall(&mut self, opcode: i32, vm: &mut Vm) -> Result<Step, String> {
            match opcode {
                SYS_CLEAR | SYS_DRAW_RECT | SYS_DRAW_CIRCLE | SYS_DRAW_NUMBER => Ok(Step::Running),
                SYS_SET_TEXTURE_FILTER => {
                    self.texture_filters.push(vm.get_var(2));
                    Ok(Step::Running)
                }
                SYS_SET_TARGET_FPS => {
                    self.target_fps_values.push(vm.get_var(2));
                    Ok(Step::Running)
                }
                SYS_LOAD_SETTING => {
                    let key = vm.get_var(2);
                    let out = vm.get_var(3).max(0) as usize;
                    let default = vm.get_var(4);
                    vm.set_var(out, self.settings.get(&key).copied().unwrap_or(default));
                    Ok(Step::Running)
                }
                SYS_SAVE_SETTING => {
                    let key = vm.get_var(2);
                    let value = vm.get_var(3);
                    self.settings.insert(key, value);
                    self.saved_settings.push([key, value]);
                    Ok(Step::Running)
                }
                SYS_DEFINE_COLOR => {
                    self.defined_colors.push([
                        vm.get_var(2),
                        vm.get_var(3),
                        vm.get_var(4),
                        vm.get_var(5),
                        vm.get_var(6),
                    ]);
                    Ok(Step::Running)
                }
                SYS_CONFIGURE_WINDOW => {
                    self.configured_windows.push([vm.get_var(2), vm.get_var(3)]);
                    Ok(Step::Running)
                }
                SYS_CONFIGURE_SETTINGS => {
                    self.configured_settings.push(vm.get_var(2));
                    Ok(Step::Running)
                }
                SYS_DEFINE_TEXTURE => {
                    self.defined_textures.push([vm.get_var(2), vm.get_var(3)]);
                    Ok(Step::Running)
                }
                SYS_DRAW_TEXTURE => {
                    if self.record_sprites {
                        self.drawn_sprites.push([
                            vm.get_var(3),
                            vm.get_var(4),
                            vm.get_var(5),
                            vm.get_var(6),
                            vm.get_var(7),
                            vm.get_var(8),
                            vm.get_var(9),
                            vm.get_var(10),
                        ]);
                        self.drawn_sprite_calls.push([
                            vm.get_var(3),
                            vm.get_var(4),
                            vm.get_var(5),
                            vm.get_var(6),
                            vm.get_var(7),
                            vm.get_var(8),
                            vm.get_var(9),
                            vm.get_var(10),
                            vm.get_var(11),
                        ]);
                    }
                    Ok(Step::Running)
                }
                SYS_DRAW_TEXTURE_ALPHA => {
                    if self.record_sprites {
                        self.drawn_sprites.push([
                            vm.get_var(3),
                            vm.get_var(4),
                            vm.get_var(5),
                            vm.get_var(6),
                            vm.get_var(7),
                            vm.get_var(8),
                            vm.get_var(9),
                            vm.get_var(10),
                        ]);
                        self.drawn_sprite_calls.push([
                            vm.get_var(3),
                            vm.get_var(4),
                            vm.get_var(5),
                            vm.get_var(6),
                            vm.get_var(7),
                            vm.get_var(8),
                            vm.get_var(9),
                            vm.get_var(10),
                            vm.get_var(11),
                        ]);
                        self.alpha_sprites.push([
                            vm.get_var(3),
                            vm.get_var(4),
                            vm.get_var(5),
                            vm.get_var(6),
                            vm.get_var(7),
                            vm.get_var(8),
                            vm.get_var(9),
                            vm.get_var(10),
                            vm.get_var(12),
                        ]);
                    }
                    Ok(Step::Running)
                }
                SYS_DEFINE_AUDIO => {
                    self.defined_audio.push([vm.get_var(2), vm.get_var(3)]);
                    Ok(Step::Running)
                }
                SYS_PLAY_AUDIO => {
                    let slot = vm.get_var(2);
                    let looped = vm.get_var(3) != 0;
                    if slot == package_assets::BGM_AUDIO_SLOT && looped {
                        self.bgm_plays += 1;
                    }
                    if let Some([sound_id, mode, side]) = decode_sfx_audio_slot(slot) {
                        self.played_sounds.push(sound_id);
                        self.sound_events.push([sound_id, mode, side]);
                    }
                    Ok(Step::Running)
                }
                SYS_STOP_AUDIO => {
                    if vm.get_var(2) == package_assets::BGM_AUDIO_SLOT {
                        self.bgm_stops += 1;
                    }
                    Ok(Step::Running)
                }
                SYS_DRAW_RECT_ALPHA => {
                    self.alpha_rects.push([
                        vm.get_var(2),
                        vm.get_var(3),
                        vm.get_var(4),
                        vm.get_var(5),
                        vm.get_var(6),
                        vm.get_var(7),
                    ]);
                    Ok(Step::Running)
                }
                SYS_KEY_DOWN => {
                    let key = vm.get_var(2);
                    let out = vm.get_var(3).max(0) as usize;
                    vm.set_var(out, i32::from(contains_test_key(&self.keys_down, key)));
                    Ok(Step::Running)
                }
                SYS_KEY_PRESSED => {
                    let key = vm.get_var(2);
                    let out = vm.get_var(3).max(0) as usize;
                    vm.set_var(out, i32::from(contains_test_key(&self.keys_pressed, key)));
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
                    self.keys_pressed.clear();
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
                _ => Err(format!("unknown fake syscall {opcode}")),
            }
        }
    }

    #[test]
    fn checked_in_umkachu_core_sample_reaches_first_frame_yield() {
        let source = include_str!("../examples/umkachu-core.umm");
        let mut vm = Vm::parse(source).expect("checked-in core Umlang sample should parse");
        let mut host = FakeHost::default();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("checked-in core Umlang sample should yield"),
            Step::Yielded
        );
        assert_eq!(host.yields, 1);
        assert_eq!(host.configured_windows.as_slice(), &[[640, 360]]);
        assert_eq!(host.defined_colors.len(), 4);
    }

    fn has_sprite(host: &FakeHost, sprite: [i32; 8]) -> bool {
        host.drawn_sprites.iter().any(|drawn| *drawn == sprite)
    }

    fn sprite_index(host: &FakeHost, sprite: [i32; 8]) -> Option<usize> {
        host.drawn_sprites.iter().position(|drawn| *drawn == sprite)
    }

    fn has_alpha_sprite(host: &FakeHost, sprite: [i32; 9]) -> bool {
        host.alpha_sprites.iter().any(|drawn| *drawn == sprite)
    }

    fn has_sprite_call(host: &FakeHost, sprite: [i32; 9]) -> bool {
        host.drawn_sprite_calls.iter().any(|drawn| *drawn == sprite)
    }

    fn sprite_call(rect: [i32; 4], dx: i32, dy: i32, dw: i32, dh: i32, flip: i32) -> [i32; 9] {
        [rect[0], rect[1], rect[2], rect[3], dx, dy, dw, dh, flip]
    }

    fn sprite_draw(rect: [i32; 4], dx: i32, dy: i32, dw: i32, dh: i32) -> [i32; 8] {
        [rect[0], rect[1], rect[2], rect[3], dx, dy, dw, dh]
    }

    fn render_values<const N: usize>(values: &[i32]) -> [i32; N] {
        values.try_into().expect("render ABI length should match")
    }

    fn menu_values<const N: usize>(values: &[i32]) -> [i32; N] {
        values.try_into().expect("menu ABI length should match")
    }

    fn render_alpha_sprite(values: &[i32], alpha: i32) -> [i32; 9] {
        let sprite = render_values::<8>(values);
        [
            sprite[0], sprite[1], sprite[2], sprite[3], sprite[4], sprite[5], sprite[6], sprite[7],
            alpha,
        ]
    }

    fn fade_alpha(numerator: i32, denominator: i32) -> i32 {
        numerator * 255 / denominator
    }

    fn player_sprite_index(state: i32, frame: usize) -> usize {
        package_animation::PLAYER_DRAW_STATES
            .iter()
            .find(|entry| entry.state == state)
            .expect("player animation draw state should exist")
            .sprite_indices
            .get(frame)
            .copied()
            .expect("player animation frame should exist")
    }

    fn round_sfx_event(flag_name: &str) -> package_sfx::SfxEvent {
        *package_sfx::ROUND_SFX_EVENTS
            .iter()
            .find(|event| event.flag_name == flag_name)
            .expect("round SFX event should exist")
    }

    fn ui_sfx_event(flag_name: &str) -> package_sfx::SfxEvent {
        *package_sfx::UI_SFX_EVENTS
            .iter()
            .find(|event| event.flag_name == flag_name)
            .expect("UI SFX event should exist")
    }

    fn fixed_sfx_side(event: package_sfx::SfxEvent) -> i32 {
        match event.side {
            package_sfx::SfxSide::Fixed(side) => side,
            package_sfx::SfxSide::BallX => panic!("expected fixed SFX side"),
        }
    }

    fn sfx_event_for_fixed_side(event: package_sfx::SfxEvent, mode: i32) -> [i32; 3] {
        [event.sound_id, mode, fixed_sfx_side(event)]
    }

    fn sfx_event_for_ball_side(event: package_sfx::SfxEvent, mode: i32, side: i32) -> [i32; 3] {
        assert_eq!(
            event.side,
            package_sfx::SfxSide::BallX,
            "expected ball-position SFX side"
        );
        [event.sound_id, mode, side]
    }

    fn selected_menu_option(values: &[i32], no_input_counter: i32) -> [i32; 8] {
        let mut sprite = render_values::<8>(values);
        let [clamp_min, clamp_max] = menu_values::<2>(package_menu::OPTION_NO_INPUT_CLAMP);
        let [size_base] = menu_values::<1>(package_menu::OPTION_SIZE_DIFF_BASE);
        let [expand_bias] = menu_values::<1>(package_menu::OPTION_EXPAND_BIAS);
        let [x_multiplier] = menu_values::<1>(package_menu::OPTION_X_MULTIPLIER);
        let [width_multiplier] = menu_values::<1>(package_menu::OPTION_WIDTH_MULTIPLIER);
        let [y_multiplier] = menu_values::<1>(package_menu::OPTION_Y_MULTIPLIER);
        let [height_multiplier] = menu_values::<1>(package_menu::OPTION_HEIGHT_MULTIPLIER);
        let size_diff = no_input_counter.clamp(clamp_min, clamp_max) + size_base;
        let expand = size_diff + expand_bias;
        sprite[4] -= expand * x_multiplier;
        sprite[6] += expand * width_multiplier;
        sprite[5] -= size_diff * y_multiplier;
        sprite[7] += size_diff * height_multiplier;
        sprite
    }

    fn set_rng_seed(vm: &mut Vm, seed: u64) {
        for byte_index in 0..8 {
            vm.set_var(
                RNG_BYTE0 + byte_index,
                ((seed >> (8 * byte_index)) & 0xff) as i32,
            );
        }
        vm.set_var(RNG_STATE, 0);
    }

    #[derive(Clone, Copy)]
    struct AiGoldenFrame {
        frame: usize,
        touched: i32,
        p1: [i32; 7],
        p2: [i32; 7],
        ball: [i32; 8],
    }

    fn ai_frame(
        frame: usize,
        touched: i32,
        p1: [i32; 7],
        p2: [i32; 7],
        ball: [i32; 8],
    ) -> AiGoldenFrame {
        AiGoldenFrame {
            frame,
            touched,
            p1,
            p2,
            ball,
        }
    }

    fn assert_ai_player_snapshot(
        vm: &Vm,
        vars: [usize; 7],
        expected: [i32; 7],
        scenario: &str,
        frame: usize,
    ) {
        for (var, value) in vars.into_iter().zip(expected) {
            assert_eq!(
                vm.get_var(var),
                value,
                "{scenario} frame {frame} actual ball [{}, {}, {}, {}, {}, {}, {}, {}, {}]",
                vm.get_var(BALL_X),
                vm.get_var(BALL_Y),
                vm.get_var(BALL_DX),
                vm.get_var(BALL_DY),
                vm.get_var(BALL_EXPECTED_X),
                vm.get_var(BALL_ROTATION),
                vm.get_var(BALL_FINE_ROT),
                vm.get_var(BALL_IS_POWER_HIT),
                vm.get_var(BALL_TOUCH_GROUND),
            );
        }
    }

    fn assert_ai_ball_snapshot(vm: &Vm, expected: [i32; 8], scenario: &str, frame: usize) {
        assert_eq!(vm.get_var(BALL_X), expected[0], "{scenario} frame {frame}");
        assert_eq!(vm.get_var(BALL_Y), expected[1], "{scenario} frame {frame}");
        assert_eq!(vm.get_var(BALL_DX), expected[2], "{scenario} frame {frame}");
        assert_eq!(vm.get_var(BALL_DY), expected[3], "{scenario} frame {frame}");
        assert_eq!(
            vm.get_var(BALL_EXPECTED_X),
            expected[4],
            "{scenario} frame {frame}"
        );
        assert_eq!(
            vm.get_var(BALL_ROTATION),
            expected[5],
            "{scenario} frame {frame}"
        );
        assert_eq!(
            vm.get_var(BALL_FINE_ROT),
            expected[6],
            "{scenario} frame {frame}"
        );
        assert_eq!(
            vm.get_var(BALL_IS_POWER_HIT),
            expected[7],
            "{scenario} frame {frame}"
        );
    }

    fn run_forced_ai_golden(
        scenario: &str,
        frame_count: usize,
        p1_computer: i32,
        p2_computer: i32,
        ball_x: i32,
        ball_dx: i32,
        ball_expected_x: i32,
        expectations: &[AiGoldenFrame],
    ) {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("script should initialize before forced AI golden scenario"),
            Step::Yielded
        );

        vm.set_var(PHASE, 5);
        vm.set_var(FRAME_COUNTER, 0);
        vm.set_var(P1_COMPUTER, p1_computer);
        vm.set_var(P2_COMPUTER, p2_computer);
        vm.set_var(P1_BOLDNESS, 2);
        vm.set_var(P2_BOLDNESS, 2);
        vm.set_var(P1_STANDBY, 0);
        vm.set_var(P2_STANDBY, 0);
        vm.set_var(RNG_FIXED_ENABLED, 1);
        vm.set_var(RNG_FIXED_VALUE, FIXED_GOLDEN_RAND);
        vm.set_var(PRACTICE_MODE, 1);
        vm.set_var(SFX_MODE, 0);
        vm.set_var(BGM_ON, 0);
        vm.set_var(PAUSED, 0);
        vm.set_var(SCORE1, 0);
        vm.set_var(SCORE2, 0);
        vm.set_var(P1_X, 72);
        vm.set_var(P1_Y, 488);
        vm.set_var(P1_DY, 0);
        vm.set_var(P1_STATE, 0);
        vm.set_var(P1_FRAME, 0);
        vm.set_var(P1_DELAY, 0);
        vm.set_var(P1_COLLIDING, 0);
        vm.set_var(P2_X, 792);
        vm.set_var(P2_Y, 488);
        vm.set_var(P2_DY, 0);
        vm.set_var(P2_STATE, 0);
        vm.set_var(P2_FRAME, 0);
        vm.set_var(P2_DELAY, 0);
        vm.set_var(P2_COLLIDING, 0);
        vm.set_var(BALL_X, ball_x);
        vm.set_var(BALL_Y, 160);
        vm.set_var(BALL_DX, ball_dx);
        vm.set_var(BALL_DY, 8);
        vm.set_var(BALL_EXPECTED_X, ball_expected_x);
        vm.set_var(BALL_ROTATION, 0);
        vm.set_var(BALL_FINE_ROT, 0);
        vm.set_var(BALL_PUNCH_RADIUS, 0);
        vm.set_var(BALL_PUNCH_X, 0);
        vm.set_var(BALL_PUNCH_Y, 0);
        vm.set_var(BALL_IS_POWER_HIT, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);
        vm.set_var(SLOW_MOTION_FRAMES_LEFT, 0);
        vm.set_var(SLOW_MOTION_SKIP, 0);

        let mut expectation_index = 0;
        for step in 0..frame_count {
            host.keys_down.clear();
            host.keys_pressed.clear();

            assert_eq!(
                vm.run_until_yield(&mut host, 800_000)
                    .expect("AI golden frame should yield"),
                Step::Yielded
            );

            if expectation_index >= expectations.len()
                || expectations[expectation_index].frame != step + 1
            {
                continue;
            }

            let snapshot = expectations[expectation_index];
            expectation_index += 1;
            let frame = snapshot.frame;

            assert_ai_player_snapshot(
                &vm,
                [
                    P1_X,
                    P1_Y,
                    P1_DY,
                    P1_STATE,
                    P1_FRAME,
                    P1_DELAY,
                    P1_COLLIDING,
                ],
                snapshot.p1,
                scenario,
                frame,
            );
            assert_ai_player_snapshot(
                &vm,
                [
                    P2_X,
                    P2_Y,
                    P2_DY,
                    P2_STATE,
                    P2_FRAME,
                    P2_DELAY,
                    P2_COLLIDING,
                ],
                snapshot.p2,
                scenario,
                frame,
            );
            assert_ai_ball_snapshot(&vm, snapshot.ball, scenario, frame);
            assert_eq!(
                vm.get_var(BALL_TOUCH_GROUND),
                snapshot.touched,
                "{scenario} frame {frame}"
            );
        }

        assert_eq!(expectation_index, expectations.len());
    }

    #[test]
    fn generated_pikachu_script_reaches_first_frame_yield() {
        let mut vm =
            Vm::parse_file("scripts/pikachu.umm").expect("generated 엄랭 package should parse");
        let mut host = FakeHost::default();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("script should reach frame yield"),
            Step::Yielded
        );
        assert_eq!(host.yields, 1);
        assert_eq!(
            host.configured_windows.as_slice(),
            &[expected_window_size()]
        );
        assert_eq!(host.configured_settings, [expected_settings_profile()]);
        assert_eq!(host.defined_colors.as_slice(), package_palette::PALETTE);
        assert_eq!(
            host.defined_textures,
            [[
                package_assets::SPRITE_TEXTURE_SLOT,
                expected_asset_id(package_assets::SPRITE_TEXTURE)
            ]]
        );
        assert_eq!(host.defined_audio, expected_audio_definitions());
        assert_eq!(vm.get_var(FLOOR_Y), package_game::INITIAL_FLOOR_Y);
        assert_eq!(vm.get_var(BALL_FLOOR_Y), package_game::INITIAL_BALL_FLOOR_Y);
        assert_eq!(vm.get_var(LEFT_WALL), 40);
        assert_eq!(vm.get_var(RIGHT_WALL), 864);
        assert_eq!(vm.get_var(BALL_RADIUS), 40);
        assert_eq!(vm.get_var(COLLISION_RADIUS), 64);
        assert_eq!(vm.get_var(P1_X), 72);
        assert_eq!(vm.get_var(P2_X), 792);
        assert_eq!(vm.get_var(P1_Y), vm.get_var(FLOOR_Y));
        assert_eq!(vm.get_var(P2_Y), vm.get_var(FLOOR_Y));
        assert_eq!(vm.get_var(BALL_X), 112);
        assert_eq!(vm.get_var(BALL_Y), 0);
        assert_eq!(vm.get_var(BALL_DX), 0);
        assert_eq!(vm.get_var(BALL_DY), 2);
        assert_eq!(vm.get_var(PHASE), package_game::PHASE_INTRO);
        assert_eq!(vm.get_var(59), 1);
        assert_eq!(vm.get_var(P1_BOLDNESS), 4);
        assert_eq!(vm.get_var(P2_BOLDNESS), 0);
        assert_eq!(vm.get_var(CLOUD1_X), -120);
        assert_eq!(vm.get_var(CLOUD1_Y), 68);
        assert_eq!(vm.get_var(CLOUD1_VX), 4);
        assert_eq!(vm.get_var(CLOUD1_SIZE_TURN), 6);
        assert_eq!(vm.get_var(CLOUD10_X), 398);
        assert_eq!(vm.get_var(CLOUD10_Y), 24);
        assert_eq!(vm.get_var(CLOUD10_VX), 2);
        assert_eq!(vm.get_var(CLOUD10_SIZE_TURN), 2);
    }

    #[test]
    fn generated_rng_abi_defines_64_bit_lcg_bytes() {
        assert_eq!(package_rng::RNG_SEED_BYTES.len(), 8);
        assert_eq!(package_rng::RNG_MULTIPLIER_BYTES.len(), 8);
        assert!(package_rng::RNG_SEED_BYTES
            .iter()
            .all(|byte| (0..=255).contains(byte)));
        assert!(package_rng::RNG_MULTIPLIER_BYTES
            .iter()
            .all(|byte| (0..=255).contains(byte)));
    }

    #[test]
    fn generated_timing_abi_defines_phase_and_fade_boundaries() {
        assert!(package_timing::INTRO_TO_MENU_FRAME > package_timing::INTRO_FADE_OUT_START);
        assert!(package_timing::MENU_OPENING_END_FRAME >= package_timing::MENU_FULL_ALPHA_FRAME);
        assert!(package_timing::MESSAGE_GROW_FRAMES > 0);
        assert!(package_timing::READY_BLINK_DIVISOR > 0);
        assert!(package_timing::READY_BLINK_MODULO > 0);
        assert!(package_timing::PHASE_FADE_AFTER_MENU_FRAMES > 0);
        assert!(package_timing::PHASE_FADE_START_NEW_GAME_FRAMES > 0);
        assert!(package_timing::PHASE_FADE_AFTER_ROUND_FRAMES > 0);
        assert!(package_timing::PHASE_FADE_BEFORE_NEXT_FRAMES > 0);
        assert!(
            package_timing::GAME_END_TIMEOUT_FRAME > package_timing::GAME_END_POWER_RESTART_FRAME
        );
    }

    #[test]
    fn generated_menu_abi_defines_original_menu_animation_curves() {
        let [rows, cols] = menu_values::<2>(package_menu::SITTING_GRID);
        let [scroll_mul, scroll_mod, scroll_scale] = menu_values::<3>(package_menu::SITTING_SCROLL);
        assert!(rows > 0 && cols > 0);
        assert!(scroll_mul > 0 && scroll_mod > 0 && scroll_scale > 0);

        let [fight_grow_frames] = menu_values::<1>(package_menu::FIGHT_GROW_FRAMES);
        assert!(fight_grow_frames > 0);
        assert_eq!(package_menu::FIGHT_SIZE_CYCLE.len(), 9);

        let [show, slide, squash, stretch] = menu_values::<4>(package_menu::TITLE_PHASE_FRAMES);
        assert!(show < slide && slide < squash && squash < stretch);

        let [clamp_min, clamp_max] = menu_values::<2>(package_menu::OPTION_NO_INPUT_CLAMP);
        assert!(clamp_min <= clamp_max);
    }

    #[test]
    fn generated_player_abi_defines_original_player_state_machine() {
        assert_eq!(package_player::STATE_NORMAL, 0);
        assert_eq!(package_player::STATE_JUMP, 1);
        assert_eq!(package_player::STATE_POWER_HIT, 2);
        assert_eq!(package_player::STATE_DIVING, 3);
        assert_eq!(package_player::STATE_LYING, 4);
        assert_eq!(package_player::STATE_WIN, 5);
        assert_eq!(package_player::STATE_LOSE, 6);
        assert!(package_player::LIE_TIMER_INITIAL > package_player::LIE_TIMER_STAND_THRESHOLD);
        assert!(package_player::POWER_HIT_START_DELAY >= 0);
        assert!(package_player::POWER_HIT_LAST_FRAME > 0);
        assert!(package_player::NORMAL_SWING_FRAME_MIN < package_player::NORMAL_SWING_FRAME_MAX);
        assert!(package_player::GAME_END_ANIM_LAST_FRAME > 0);
    }

    #[test]
    fn generated_pikachu_script_draws_original_intro_and_menu_animation_sprites() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost {
            record_sprites: true,
            ..Default::default()
        };

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("intro frame should yield"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(PHASE), 0);
        assert!(has_alpha_sprite(
            &host,
            render_alpha_sprite(
                package_render::INTRO_MARK,
                fade_alpha(1, package_timing::INTRO_FADE_DENOMINATOR)
            )
        ));

        vm.set_var(PHASE, 1);
        vm.set_var(FRAME_COUNTER, package_timing::MENU_OPENING_END_FRAME + 1);
        vm.set_var(MENU_SELECTION, 1);
        vm.set_var(NO_INPUT_COUNTER, 7);
        host.drawn_sprites.clear();
        host.alpha_sprites.clear();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("menu animation frame should yield"),
            Step::Yielded
        );

        assert!(has_sprite(
            &host,
            render_values::<8>(package_render::MENU_POKEMON_LABEL)
        ));
        assert!(has_sprite(
            &host,
            render_values::<8>(package_render::MENU_TITLE_FINAL)
        ));
        assert!(has_sprite(
            &host,
            selected_menu_option(package_render::MENU_OPTION_FRIEND, 7)
        ));
        assert!(has_alpha_sprite(
            &host,
            render_alpha_sprite(package_render::MENU_SACHISOFT, 255)
        ));

        vm.set_var(PHASE, 0);
        vm.set_var(FRAME_COUNTER, package_timing::INTRO_TO_MENU_FRAME);
        vm.set_var(MENU_SELECTION, 1);
        host.bgm_stops = 0;
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("intro-to-menu transition should yield"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(PHASE), 1);
        assert_eq!(vm.get_var(FRAME_COUNTER), 0);
        assert_eq!(vm.get_var(MENU_SELECTION), 0);
        assert_eq!(host.bgm_stops, 1);
    }

    #[test]
    fn generated_pikachu_script_draws_original_diving_player_flips() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost {
            record_sprites: true,
            ..Default::default()
        };

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("first frame should yield before forced draw state"),
            Step::Yielded
        );

        vm.set_var(PHASE, 5);
        vm.set_var(PAUSED, 1);
        vm.set_var(P1_X, 200);
        vm.set_var(P1_Y, 300);
        vm.set_var(P1_STATE, 3);
        vm.set_var(P1_FRAME, 0);
        vm.set_var(P1_DIVE_DIR, -1);
        vm.set_var(P2_X, 700);
        vm.set_var(P2_Y, 300);
        vm.set_var(P2_STATE, 3);
        vm.set_var(P2_FRAME, 0);
        vm.set_var(P2_DIVE_DIR, 1);
        host.drawn_sprite_calls.clear();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("paused round draw should yield"),
            Step::Yielded
        );

        let diving_sprite = package_sprites::PLAYER_FRAMES[player_sprite_index(3, 0)];
        assert!(has_sprite_call(
            &host,
            sprite_call(diving_sprite, 136, 236, 128, 128, 1)
        ));
        assert!(has_sprite_call(
            &host,
            sprite_call(diving_sprite, 636, 236, 128, 128, 0)
        ));
    }

    #[test]
    fn generated_pikachu_script_runs_many_frames_without_runtime_error() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();

        for _ in 0..570 {
            assert_eq!(
                vm.run_until_yield(&mut host, 600_000)
                    .expect("script should keep yielding frames"),
                Step::Yielded
            );
        }

        assert_eq!(host.yields, 570);
        assert_eq!(vm.get_var(58), 5);
        assert!((0..=900).contains(&vm.get_var(28)));
        assert!((0..=540).contains(&vm.get_var(29)));
        assert!((0..=15).contains(&vm.get_var(41)));
        assert!((0..=15).contains(&vm.get_var(42)));
        assert!((0..=4).contains(&vm.get_var(68)));
        assert!((0..=4).contains(&vm.get_var(69)));
        assert!((0..=5).contains(&vm.get_var(BALL_FRAME)));
        assert!((0..=5).contains(&vm.get_var(BALL_ROTATION)));
        assert!((0..=11).contains(&vm.get_var(71)));
        assert_ne!(vm.get_var(72), 70);
        assert_ne!(vm.get_var(128), 360);
        assert_ne!(vm.get_var(152), 1260);
        assert_eq!(vm.get_var(78), 1);
        assert_eq!(vm.get_var(79), 1);
        assert_ne!(vm.get_var(107), 19741);
        assert!((0..=4).contains(&vm.get_var(109)));
        assert!((0..=4).contains(&vm.get_var(110)));
        assert!((0..=1).contains(&vm.get_var(111)));
        assert!((0..=1).contains(&vm.get_var(112)));
        assert!((-39..=32).contains(&vm.get_var(156)));
        assert!((-1..=2).contains(&vm.get_var(157)));
        assert!((550..=720).contains(&vm.get_var(WAVE1_Y)));
        assert!((550..=720).contains(&vm.get_var(WAVE27_Y)));
    }

    #[test]
    fn generated_pikachu_script_applies_extra_p1_key_and_ai_demo_interrupt() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();

        for _ in 0..570 {
            assert_eq!(
                vm.run_until_yield(&mut host, 600_000)
                    .expect("script should reach round phase"),
                Step::Yielded
            );
        }
        assert_eq!(vm.get_var(PHASE), 5);

        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 0);
        host.keys_down.push(11);
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("1P extra positive key should yield"),
            Step::Yielded
        );
        host.keys_down.clear();
        assert_eq!(vm.get_var(P1_INPUT_X), 1);
        assert_eq!(vm.get_var(P1_INPUT_Y), 1);

        vm.set_var(PHASE, 5);
        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 0);
        host.keys_down.extend([1, 11, 6, 7, 8, 9]);
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("simultaneous axis inputs should yield"),
            Step::Yielded
        );
        host.keys_down.clear();
        assert_eq!(vm.get_var(P1_INPUT_X), 0);
        assert_eq!(vm.get_var(P1_INPUT_Y), 1);
        assert_eq!(vm.get_var(P2_INPUT_X), 0);
        assert_eq!(vm.get_var(P2_INPUT_Y), 0);

        vm.set_var(PHASE, 5);
        vm.set_var(FRAME_COUNTER, 100);
        vm.set_var(P1_COMPUTER, 1);
        vm.set_var(P2_COMPUTER, 0);
        vm.set_var(P1_X, 300);
        vm.set_var(P1_Y, vm.get_var(FLOOR_Y));
        vm.set_var(P1_DY, 0);
        vm.set_var(P1_STATE, 0);
        vm.set_var(P1_BOLDNESS, 0);
        vm.set_var(P1_STANDBY, 0);
        vm.set_var(P1_INPUT_X, 99);
        vm.set_var(P1_INPUT_Y, 99);
        vm.set_var(P1_POWER, 99);
        vm.set_var(P2_X, 760);
        vm.set_var(P2_Y, vm.get_var(FLOOR_Y));
        vm.set_var(P2_DY, 0);
        vm.set_var(P2_STATE, 0);
        vm.set_var(BALL_X, 432);
        vm.set_var(BALL_Y, 100);
        vm.set_var(BALL_DX, 0);
        vm.set_var(BALL_DY, 1);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);
        vm.set_var(SLOW_MOTION_FRAMES_LEFT, 0);
        vm.set_var(SLOW_MOTION_SKIP, 0);
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("P1 AI should track near exact-boundary landing directly"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(BALL_EXPECTED_X), 432);
        assert_eq!(vm.get_var(P1_INPUT_X), 1);
        assert_eq!(vm.get_var(P1_X), 312);

        vm.set_var(PHASE, 5);
        vm.set_var(FRAME_COUNTER, 100);
        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 1);
        vm.set_var(P1_X, 402);
        vm.set_var(P1_Y, vm.get_var(FLOOR_Y));
        vm.set_var(P1_DY, 0);
        vm.set_var(P1_STATE, 0);
        vm.set_var(P2_X, 486);
        vm.set_var(P2_Y, 300);
        vm.set_var(P2_DY, 0);
        vm.set_var(P2_STATE, 1);
        vm.set_var(P2_BOLDNESS, 0);
        vm.set_var(BALL_X, 486);
        vm.set_var(BALL_Y, 300);
        vm.set_var(BALL_DX, 0);
        vm.set_var(BALL_DY, -5);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);
        vm.set_var(SLOW_MOTION_FRAMES_LEFT, 0);
        vm.set_var(SLOW_MOTION_SKIP, 0);
        set_rng_seed(&mut vm, 5);
        host.keys_down.push(2);
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("P2 AI should observe P1 after P1 movement"),
            Step::Yielded
        );
        host.keys_down.clear();
        assert_eq!(vm.get_var(P1_X), 368);
        assert_eq!(vm.get_var(P2_POWER), 1);
        assert_eq!(vm.get_var(P2_INPUT_Y), -1);

        vm.set_var(P1_COMPUTER, 1);
        vm.set_var(P2_COMPUTER, 1);
        host.keys_pressed.push(5);
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("AI demo power press should return to intro"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(PHASE), 0);
        assert_eq!(vm.get_var(FRAME_COUNTER), 0);
    }

    #[test]
    fn generated_pikachu_script_loads_persisted_runtime_options() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();
        let winning_scores = setting_three_values(package_settings::WINNING_SCORE_VALUES);
        let target_fps_values = setting_three_values(package_settings::TARGET_FPS_VALUES);
        let sfx_values = setting_three_values(package_settings::SFX_MODE_VALUES);
        host.settings.extend([
            (SETTING_WINNING_SCORE, winning_scores[1]),
            (
                SETTING_PRACTICE_MODE,
                setting_max(package_settings::PRACTICE_MODE_VALUES),
            ),
            (SETTING_BGM_ON, setting_min(package_settings::BGM_ON_VALUES)),
            (SETTING_SFX_MODE, sfx_values[1]),
            (
                SETTING_SOFT_GRAPHICS,
                setting_max(package_settings::SOFT_GRAPHICS_VALUES),
            ),
            (SETTING_TARGET_FPS, target_fps_values[2]),
        ]);

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("persisted runtime options should load before first yield"),
            Step::Yielded
        );

        assert_eq!(vm.get_var(WINNING_SCORE), winning_scores[1]);
        assert_eq!(
            vm.get_var(PRACTICE_MODE),
            setting_max(package_settings::PRACTICE_MODE_VALUES)
        );
        assert_eq!(
            vm.get_var(BGM_ON),
            setting_min(package_settings::BGM_ON_VALUES)
        );
        assert_eq!(vm.get_var(SFX_MODE), sfx_values[1]);
        assert_eq!(
            vm.get_var(SOFT_GRAPHICS),
            setting_max(package_settings::SOFT_GRAPHICS_VALUES)
        );
        assert_eq!(vm.get_var(TARGET_FPS), target_fps_values[2]);
        assert_eq!(
            host.texture_filters.last().copied(),
            Some(setting_max(package_settings::SOFT_GRAPHICS_VALUES))
        );
        assert_eq!(
            host.target_fps_values.last().copied(),
            Some(target_fps_values[2])
        );
        assert!(host.saved_settings.is_empty());
    }

    #[test]
    fn generated_pikachu_script_applies_runtime_options_and_practice_mode() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();
        let winning_scores = setting_three_values(package_settings::WINNING_SCORE_VALUES);
        let target_fps_values = setting_three_values(package_settings::TARGET_FPS_VALUES);
        let sfx_values = setting_three_values(package_settings::SFX_MODE_VALUES);

        run_with_pressed_key(&mut vm, &mut host, 13, "winning score hotkey should yield");
        assert_eq!(vm.get_var(WINNING_SCORE), winning_scores[0]);
        assert_eq!(host.bgm_stops, 0);

        run_with_pressed_key(&mut vm, &mut host, 14, "winning score hotkey should yield");
        assert_eq!(vm.get_var(WINNING_SCORE), winning_scores[1]);
        assert_eq!(host.bgm_stops, 0);

        run_with_pressed_key(&mut vm, &mut host, 15, "winning score hotkey should yield");
        assert_eq!(vm.get_var(WINNING_SCORE), winning_scores[2]);
        assert_eq!(host.bgm_stops, 0);

        run_with_pressed_key(&mut vm, &mut host, 12, "practice hotkey should yield");
        assert_eq!(
            vm.get_var(PRACTICE_MODE),
            setting_max(package_settings::PRACTICE_MODE_VALUES)
        );
        assert_eq!(host.bgm_stops, 0);

        run_with_pressed_key(&mut vm, &mut host, 12, "practice hotkey should yield");
        assert_eq!(
            vm.get_var(PRACTICE_MODE),
            setting_min(package_settings::PRACTICE_MODE_VALUES)
        );
        assert_eq!(host.bgm_stops, 0);
        run_with_pressed_key(&mut vm, &mut host, 17, "BGM hotkey should yield");
        assert_eq!(
            vm.get_var(BGM_ON),
            setting_min(package_settings::BGM_ON_VALUES)
        );
        assert_eq!(host.bgm_stops, 1);

        run_with_pressed_key(&mut vm, &mut host, 17, "BGM hotkey should yield");
        assert_eq!(
            vm.get_var(BGM_ON),
            setting_max(package_settings::BGM_ON_VALUES)
        );

        run_with_pressed_key(&mut vm, &mut host, 18, "SFX hotkey should yield");
        assert_eq!(vm.get_var(SFX_MODE), sfx_values[1]);

        run_with_pressed_key(&mut vm, &mut host, 18, "SFX hotkey should yield");
        assert_eq!(vm.get_var(SFX_MODE), sfx_values[0]);

        run_with_pressed_key(&mut vm, &mut host, 18, "SFX hotkey should yield");
        assert_eq!(vm.get_var(SFX_MODE), sfx_values[2]);

        run_with_pressed_key(&mut vm, &mut host, 20, "soft graphics hotkey should yield");
        assert_eq!(
            vm.get_var(SOFT_GRAPHICS),
            setting_max(package_settings::SOFT_GRAPHICS_VALUES)
        );
        assert_eq!(
            host.texture_filters.last().copied(),
            Some(setting_max(package_settings::SOFT_GRAPHICS_VALUES))
        );

        run_with_pressed_key(&mut vm, &mut host, 20, "soft graphics hotkey should yield");
        assert_eq!(
            vm.get_var(SOFT_GRAPHICS),
            setting_min(package_settings::SOFT_GRAPHICS_VALUES)
        );
        assert_eq!(
            host.texture_filters.last().copied(),
            Some(setting_min(package_settings::SOFT_GRAPHICS_VALUES))
        );

        run_with_pressed_key(&mut vm, &mut host, 21, "slow FPS hotkey should yield");
        assert_eq!(vm.get_var(TARGET_FPS), target_fps_values[0]);
        assert_eq!(
            host.target_fps_values.last().copied(),
            Some(target_fps_values[0])
        );

        run_with_pressed_key(&mut vm, &mut host, 22, "fast FPS hotkey should yield");
        assert_eq!(vm.get_var(TARGET_FPS), target_fps_values[2]);
        assert_eq!(
            host.target_fps_values.last().copied(),
            Some(target_fps_values[2])
        );

        run_with_pressed_key(&mut vm, &mut host, 23, "normal FPS hotkey should yield");
        assert_eq!(vm.get_var(TARGET_FPS), package_settings::DEFAULT_TARGET_FPS);
        assert_eq!(
            host.target_fps_values.last().copied(),
            Some(package_settings::DEFAULT_TARGET_FPS)
        );
        for expected in [
            [SETTING_WINNING_SCORE, winning_scores[0]],
            [SETTING_WINNING_SCORE, winning_scores[1]],
            [SETTING_WINNING_SCORE, winning_scores[2]],
            [
                SETTING_PRACTICE_MODE,
                setting_max(package_settings::PRACTICE_MODE_VALUES),
            ],
            [
                SETTING_PRACTICE_MODE,
                setting_min(package_settings::PRACTICE_MODE_VALUES),
            ],
            [SETTING_BGM_ON, setting_min(package_settings::BGM_ON_VALUES)],
            [SETTING_BGM_ON, setting_max(package_settings::BGM_ON_VALUES)],
            [SETTING_SFX_MODE, sfx_values[1]],
            [SETTING_SFX_MODE, sfx_values[0]],
            [SETTING_SFX_MODE, sfx_values[2]],
            [
                SETTING_SOFT_GRAPHICS,
                setting_max(package_settings::SOFT_GRAPHICS_VALUES),
            ],
            [
                SETTING_SOFT_GRAPHICS,
                setting_min(package_settings::SOFT_GRAPHICS_VALUES),
            ],
            [SETTING_TARGET_FPS, target_fps_values[0]],
            [SETTING_TARGET_FPS, target_fps_values[2]],
            [SETTING_TARGET_FPS, package_settings::DEFAULT_TARGET_FPS],
        ] {
            assert!(host.saved_settings.contains(&expected));
        }

        vm.set_var(PHASE, 5);
        vm.set_var(PAUSED, 0);
        vm.set_var(FRAME_COUNTER, 123);
        vm.set_var(BALL_X, 321);
        vm.set_var(BALL_DX, 1);
        vm.set_var(CLOUD1_X, 77);
        host.keys_pressed.push(19);
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("pause hotkey should yield"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(PAUSED), 1);
        assert_eq!(vm.get_var(PHASE), 5);
        assert_eq!(vm.get_var(FRAME_COUNTER), 123);
        assert_eq!(vm.get_var(BALL_X), 321);
        assert_eq!(vm.get_var(CLOUD1_X), 77);

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("paused frame should keep yielding"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(PAUSED), 1);
        assert_eq!(vm.get_var(FRAME_COUNTER), 123);
        assert_eq!(vm.get_var(BALL_X), 321);
        assert_eq!(vm.get_var(CLOUD1_X), 77);

        host.keys_pressed.push(19);
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("unpause hotkey should resume simulation"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(PAUSED), 0);
        assert_eq!(vm.get_var(FRAME_COUNTER), 124);
        assert_ne!(vm.get_var(BALL_X), 321);

        vm.set_var(PHASE, 5);
        vm.set_var(FRAME_COUNTER, 42);
        host.keys_pressed.push(16);
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("restart hotkey should yield"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(PHASE), 0);
        assert_eq!(vm.get_var(FRAME_COUNTER), 0);

        let ball_ground_sfx = round_sfx_event("BALL_SOUND_GROUND");
        vm.set_var(PHASE, 5);
        vm.set_var(PRACTICE_MODE, 0);
        vm.set_var(SFX_MODE, 0);
        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 0);
        vm.set_var(P1_X, 100);
        vm.set_var(P1_Y, vm.get_var(FLOOR_Y));
        vm.set_var(P1_DY, 0);
        vm.set_var(P1_STATE, 0);
        vm.set_var(P2_X, 760);
        vm.set_var(P2_Y, vm.get_var(FLOOR_Y));
        vm.set_var(P2_DY, 0);
        vm.set_var(P2_STATE, 0);
        vm.set_var(BALL_X, 200);
        vm.set_var(BALL_Y, vm.get_var(BALL_FLOOR_Y) + 1);
        vm.set_var(BALL_DX, 0);
        vm.set_var(BALL_DY, 3);
        vm.set_var(SCORE1, 0);
        vm.set_var(SCORE2, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);
        vm.set_var(SLOW_MOTION_FRAMES_LEFT, 0);
        vm.set_var(SLOW_MOTION_SKIP, 0);
        host.played_sounds.clear();
        host.sound_events.clear();
        host.bgm_stops = 0;

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("SFX-off floor touch should yield without host sound"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(SCORE2), 1);
        assert!(!host.played_sounds.contains(&ball_ground_sfx.sound_id));
        assert!(!host
            .sound_events
            .iter()
            .any(|event| event[0] == ball_ground_sfx.sound_id));

        vm.set_var(PHASE, 5);
        vm.set_var(PRACTICE_MODE, 1);
        vm.set_var(SFX_MODE, 1);
        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 0);
        vm.set_var(P1_X, 100);
        vm.set_var(P1_Y, vm.get_var(FLOOR_Y));
        vm.set_var(P1_DY, 0);
        vm.set_var(P1_STATE, 0);
        vm.set_var(P2_X, 760);
        vm.set_var(P2_Y, vm.get_var(FLOOR_Y));
        vm.set_var(P2_DY, 0);
        vm.set_var(P2_STATE, 0);
        vm.set_var(BALL_X, 200);
        vm.set_var(BALL_Y, vm.get_var(BALL_FLOOR_Y) + 1);
        vm.set_var(BALL_DX, 0);
        vm.set_var(BALL_DY, 3);
        vm.set_var(SCORE1, 0);
        vm.set_var(SCORE2, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);
        vm.set_var(SLOW_MOTION_FRAMES_LEFT, 0);
        vm.set_var(SLOW_MOTION_SKIP, 0);
        host.played_sounds.clear();
        host.sound_events.clear();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("practice floor touch should yield without scoring"),
            Step::Yielded
        );

        assert_eq!(vm.get_var(SCORE1), 0);
        assert_eq!(vm.get_var(SCORE2), 0);
        assert_eq!(vm.get_var(ROUND_ENDED), 0);
        assert_eq!(vm.get_var(PHASE), 5);
        assert_eq!(vm.get_var(BALL_TOUCH_GROUND), 1);
        assert!(host.played_sounds.contains(&ball_ground_sfx.sound_id));
        assert!(host.sound_events.contains(&sfx_event_for_ball_side(
            ball_ground_sfx,
            package_assets::SFX_MONO_MODE,
            -1
        )));

        vm.set_var(PHASE, 7);
        vm.set_var(FRAME_COUNTER, 0);
        vm.set_var(ROUND_ENDED, 1);
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("next-round init should keep round-ended state during ready phase"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(PHASE), 7);
        assert_eq!(vm.get_var(ROUND_ENDED), 1);
        assert_eq!(vm.get_var(IS_P2_SERVE), 1);
        assert_eq!(vm.get_var(BALL_X), 752);
        assert_eq!(vm.get_var(BALL_Y), 0);
        assert_eq!(vm.get_var(BALL_DX), 0);
        assert_eq!(vm.get_var(BALL_DY), 2);

        vm.set_var(PHASE, 7);
        vm.set_var(
            FRAME_COUNTER,
            package_timing::PHASE_BEFORE_START_NEXT_ROUND_END_FRAME,
        );
        vm.set_var(ROUND_ENDED, 1);
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("next-round completion should clear round-ended state"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(PHASE), 5);
        assert_eq!(vm.get_var(ROUND_ENDED), 0);
    }

    #[test]
    fn generated_pikachu_script_restarts_bgm_in_all_original_playing_phases() {
        let source = include_str!("../scripts/pikachu.umm");

        for phase in [7, 8] {
            let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
            let mut host = FakeHost::default();

            assert_eq!(
                vm.run_until_yield(&mut host, 600_000)
                    .expect("script should initialize before forced playing phase"),
                Step::Yielded
            );

            vm.set_var(PHASE, phase);
            vm.set_var(FRAME_COUNTER, 0);
            vm.set_var(BGM_ON, 0);
            host.bgm_plays = 0;
            host.keys_pressed.push(17);

            assert_eq!(
                vm.run_until_yield(&mut host, 600_000)
                    .expect("BGM re-enable should yield in playing phase"),
                Step::Yielded
            );

            assert_eq!(vm.get_var(BGM_ON), 1);
            assert_eq!(host.bgm_plays, 1);
        }
    }

    #[test]
    fn generated_pikachu_script_matches_scaled_upstream_serve_neutral_golden() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("script should initialize before forced golden scenario"),
            Step::Yielded
        );

        vm.set_var(PHASE, 5);
        vm.set_var(FRAME_COUNTER, 0);
        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 0);
        vm.set_var(PRACTICE_MODE, 0);
        vm.set_var(SFX_MODE, 0);
        vm.set_var(BGM_ON, 0);
        vm.set_var(SCORE1, 0);
        vm.set_var(SCORE2, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);
        vm.set_var(SLOW_MOTION_FRAMES_LEFT, 0);
        vm.set_var(SLOW_MOTION_SKIP, 0);

        for (ball_y, ball_dy, player_frame, player_delay) in [
            (2, 4, 0, 1),
            (6, 6, 0, 2),
            (12, 8, 0, 3),
            (20, 10, 1, 0),
            (30, 12, 1, 1),
        ] {
            assert_eq!(
                vm.run_until_yield(&mut host, 600_000)
                    .expect("neutral golden frame should yield"),
                Step::Yielded
            );

            assert_eq!(vm.get_var(P1_X), 72);
            assert_eq!(vm.get_var(P2_X), 792);
            assert_eq!(vm.get_var(P1_Y), 488);
            assert_eq!(vm.get_var(P2_Y), 488);
            assert_eq!(vm.get_var(P1_DY), 0);
            assert_eq!(vm.get_var(P2_DY), 0);
            assert_eq!(vm.get_var(P1_STATE), 0);
            assert_eq!(vm.get_var(P2_STATE), 0);
            assert_eq!(vm.get_var(P1_FRAME), player_frame);
            assert_eq!(vm.get_var(P2_FRAME), player_frame);
            assert_eq!(vm.get_var(P1_DELAY), player_delay);
            assert_eq!(vm.get_var(P2_DELAY), player_delay);
            assert_eq!(vm.get_var(P1_COLLIDING), 0);
            assert_eq!(vm.get_var(P2_COLLIDING), 0);

            assert_eq!(vm.get_var(BALL_X), 112);
            assert_eq!(vm.get_var(BALL_Y), ball_y);
            assert_eq!(vm.get_var(BALL_DX), 0);
            assert_eq!(vm.get_var(BALL_DY), ball_dy);
            assert_eq!(vm.get_var(BALL_EXPECTED_X), 112);
            assert_eq!(vm.get_var(BALL_ROTATION), 0);
            assert_eq!(vm.get_var(BALL_FINE_ROT), 0);
            assert_eq!(vm.get_var(BALL_PUNCH_RADIUS), 0);
            assert_eq!(vm.get_var(BALL_PUNCH_X), 112);
            assert_eq!(vm.get_var(BALL_PUNCH_Y), 0);
            assert_eq!(vm.get_var(BALL_IS_POWER_HIT), 0);
            assert_eq!(vm.get_var(BALL_TOUCH_GROUND), 0);
        }
    }

    #[test]
    fn generated_pikachu_script_matches_scaled_upstream_movement_jump_power_golden() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("script should initialize before forced movement golden scenario"),
            Step::Yielded
        );

        vm.set_var(PHASE, 5);
        vm.set_var(FRAME_COUNTER, 0);
        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 0);
        // Practice mode bypasses game-level scoring so this can track the raw
        // upstream physics fixture after the first floor touch.
        vm.set_var(PRACTICE_MODE, 1);
        vm.set_var(SFX_MODE, 0);
        vm.set_var(BGM_ON, 0);
        vm.set_var(PAUSED, 0);
        vm.set_var(SCORE1, 0);
        vm.set_var(SCORE2, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);
        vm.set_var(SLOW_MOTION_FRAMES_LEFT, 0);
        vm.set_var(SLOW_MOTION_SKIP, 0);

        let expectations = [
            (1, 0, 84, 488, 0, 0, 0, 1, 780, 0, 1, 2, 4, 0, 112, 0),
            (2, 0, 96, 488, 0, 0, 0, 2, 768, 0, 2, 6, 6, 0, 112, 0),
            (3, 0, 108, 456, -30, 1, 1, 2, 756, 0, 3, 12, 8, 0, 112, 0),
            (4, 0, 120, 426, -28, 1, 2, 2, 744, 1, 0, 20, 10, 0, 112, 0),
            (5, 0, 132, 398, -26, 1, 0, 2, 732, 1, 1, 30, 12, 0, 112, 0),
            (6, 0, 144, 372, -24, 2, 0, 4, 720, 1, 2, 42, 14, 0, 112, 0),
            (10, 0, 192, 288, -16, 2, 0, 0, 672, 2, 2, 110, 22, 0, 112, 0),
            (15, 0, 252, 228, -6, 1, 0, 0, 672, 3, 3, 240, 32, 0, 112, 0),
            (20, 0, 288, 218, 4, 1, 2, 0, 672, 3, 0, 420, 42, 0, 112, 0),
            (
                22, 1, 288, 228, 8, 1, 1, 0, 672, 3, 2, 504, -44, 36, 112, 544,
            ),
            (
                25, 0, 288, 258, 14, 1, 1, 0, 672, 2, 1, 378, -38, 24, 112, 544,
            ),
            (
                30, 0, 288, 348, 24, 1, 0, 0, 672, 1, 2, 208, -28, 4, 112, 544,
            ),
            (40, 0, 288, 488, 0, 0, 1, 1, 672, 2, 0, 18, -8, 0, 112, 544),
            (50, 0, 288, 488, 0, 0, 3, 3, 672, 4, 2, 56, 16, 0, 112, 544),
        ];
        let mut expectation_index = 0;

        for step in 0..50 {
            host.keys_down.clear();
            host.keys_pressed.clear();

            if step < 18 {
                host.keys_down.push(2);
            }
            if step == 2 {
                host.keys_down.push(3);
            }
            if step < 10 {
                host.keys_down.push(6);
            }
            if step == 5 {
                host.keys_pressed.push(5);
            }

            assert_eq!(
                vm.run_until_yield(&mut host, 600_000)
                    .expect("movement golden frame should yield"),
                Step::Yielded
            );

            if expectation_index >= expectations.len()
                || expectations[expectation_index].0 != step + 1
            {
                continue;
            }

            let (
                _frame,
                touched,
                p1_x,
                p1_y,
                p1_dy,
                p1_state,
                p1_frame,
                p1_delay,
                p2_x,
                p2_frame,
                p2_delay,
                ball_y,
                ball_dy,
                punch_radius,
                punch_x,
                punch_y,
            ) = expectations[expectation_index];
            expectation_index += 1;

            assert_eq!(vm.get_var(P1_X), p1_x);
            assert_eq!(vm.get_var(P1_Y), p1_y);
            assert_eq!(vm.get_var(P1_DY), p1_dy);
            assert_eq!(vm.get_var(P1_STATE), p1_state);
            assert_eq!(vm.get_var(P1_FRAME), p1_frame);
            assert_eq!(vm.get_var(P1_DELAY), p1_delay);
            assert_eq!(vm.get_var(P1_COLLIDING), 0);

            assert_eq!(vm.get_var(P2_X), p2_x);
            assert_eq!(vm.get_var(P2_Y), 488);
            assert_eq!(vm.get_var(P2_DY), 0);
            assert_eq!(vm.get_var(P2_STATE), 0);
            assert_eq!(vm.get_var(P2_FRAME), p2_frame);
            assert_eq!(vm.get_var(P2_DELAY), p2_delay);
            assert_eq!(vm.get_var(P2_COLLIDING), 0);

            assert_eq!(vm.get_var(BALL_X), 112);
            assert_eq!(vm.get_var(BALL_Y), ball_y);
            assert_eq!(vm.get_var(BALL_DX), 0);
            assert_eq!(vm.get_var(BALL_DY), ball_dy);
            assert_eq!(vm.get_var(BALL_EXPECTED_X), 112);
            assert_eq!(vm.get_var(BALL_ROTATION), 0);
            assert_eq!(vm.get_var(BALL_FINE_ROT), 0);
            assert_eq!(vm.get_var(BALL_PUNCH_RADIUS), punch_radius);
            assert_eq!(vm.get_var(BALL_PUNCH_X), punch_x);
            assert_eq!(vm.get_var(BALL_PUNCH_Y), punch_y);
            assert_eq!(vm.get_var(BALL_IS_POWER_HIT), 0);
            assert_eq!(vm.get_var(BALL_TOUCH_GROUND), touched);
        }

        assert_eq!(expectation_index, expectations.len());
    }

    #[test]
    fn generated_pikachu_script_matches_scaled_upstream_player_collision_power_hit_golden() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("script should initialize before forced collision golden scenario"),
            Step::Yielded
        );

        vm.set_var(PHASE, 5);
        vm.set_var(FRAME_COUNTER, 0);
        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 0);
        vm.set_var(PRACTICE_MODE, 1);
        vm.set_var(SFX_MODE, 0);
        vm.set_var(BGM_ON, 0);
        vm.set_var(PAUSED, 0);
        vm.set_var(SCORE1, 0);
        vm.set_var(SCORE2, 0);
        vm.set_var(P1_X, 160);
        vm.set_var(P1_Y, 440);
        vm.set_var(P1_DY, 0);
        vm.set_var(P1_STATE, 2);
        vm.set_var(P1_FRAME, 0);
        vm.set_var(P1_DELAY, 0);
        vm.set_var(P1_COLLIDING, 0);
        vm.set_var(P2_X, 792);
        vm.set_var(P2_Y, 488);
        vm.set_var(P2_DY, 0);
        vm.set_var(P2_STATE, 0);
        vm.set_var(P2_FRAME, 0);
        vm.set_var(P2_DELAY, 0);
        vm.set_var(P2_COLLIDING, 0);
        vm.set_var(BALL_X, 164);
        vm.set_var(BALL_Y, 440);
        vm.set_var(BALL_DX, 0);
        vm.set_var(BALL_DY, 20);
        vm.set_var(BALL_EXPECTED_X, 112);
        vm.set_var(BALL_ROTATION, 0);
        vm.set_var(BALL_FINE_ROT, 0);
        vm.set_var(BALL_PUNCH_RADIUS, 0);
        vm.set_var(BALL_PUNCH_X, 0);
        vm.set_var(BALL_PUNCH_Y, 0);
        vm.set_var(BALL_IS_POWER_HIT, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);
        vm.set_var(SLOW_MOTION_FRAMES_LEFT, 0);
        vm.set_var(SLOW_MOTION_SKIP, 0);

        let expectations = [
            (1, 172, 440, 2, 2, 1, 0, 1, 164, 460, 40, -60, 524, 0, 0, 36),
            (
                2, 172, 442, 4, 2, 2, 0, 1, 204, 400, 40, -58, 524, 1, 10, 32,
            ),
            (
                3, 172, 446, 6, 2, 3, 0, 0, 244, 342, 40, -56, 524, 2, 20, 28,
            ),
            (
                4, 172, 452, 8, 2, 4, 0, 0, 284, 286, 40, -54, 524, 3, 30, 24,
            ),
            (
                5, 172, 460, 10, 1, 0, 0, 0, 324, 232, 40, -52, 524, 4, 40, 20,
            ),
            (
                6, 172, 470, 12, 1, 1, 0, 0, 364, 180, 40, -50, 524, 5, 50, 16,
            ),
            (10, 172, 488, 0, 0, 0, 3, 0, 524, 38, 40, 4, 524, 4, 40, 0),
            (15, 172, 488, 0, 0, 2, 0, 0, 724, 78, 40, 14, 524, 4, 40, 0),
            (
                20, 172, 488, 0, 0, 3, 1, 0, 764, 168, -40, 24, 524, 2, 20, 0,
            ),
        ];
        let mut expectation_index = 0;

        for step in 0..20 {
            host.keys_down.clear();
            host.keys_pressed.clear();

            if step == 0 {
                host.keys_down.extend([2, 3]);
            }
            if step == 1 {
                host.keys_pressed.push(5);
            }

            assert_eq!(
                vm.run_until_yield(&mut host, 800_000)
                    .expect("collision golden frame should yield"),
                Step::Yielded
            );

            if expectation_index >= expectations.len()
                || expectations[expectation_index].0 != step + 1
            {
                continue;
            }

            let (
                _frame,
                p1_x,
                p1_y,
                p1_dy,
                p1_state,
                p1_frame,
                p1_delay,
                p1_collision,
                ball_x,
                ball_y,
                ball_dx,
                ball_dy,
                ball_expected_x,
                ball_rotation,
                ball_fine_rotation,
                punch_radius_after_render,
            ) = expectations[expectation_index];
            expectation_index += 1;

            assert_eq!(vm.get_var(P1_X), p1_x);
            assert_eq!(vm.get_var(P1_Y), p1_y);
            assert_eq!(vm.get_var(P1_DY), p1_dy);
            assert_eq!(vm.get_var(P1_STATE), p1_state);
            assert_eq!(vm.get_var(P1_FRAME), p1_frame);
            assert_eq!(vm.get_var(P1_DELAY), p1_delay);
            assert_eq!(vm.get_var(P1_COLLIDING), p1_collision);

            assert_eq!(vm.get_var(P2_X), 792);
            assert_eq!(vm.get_var(P2_Y), 488);
            assert_eq!(vm.get_var(P2_DY), 0);
            assert_eq!(vm.get_var(P2_STATE), 0);
            assert_eq!(vm.get_var(P2_COLLIDING), 0);

            assert_eq!(vm.get_var(BALL_X), ball_x);
            assert_eq!(vm.get_var(BALL_Y), ball_y);
            assert_eq!(vm.get_var(BALL_DX), ball_dx);
            assert_eq!(vm.get_var(BALL_DY), ball_dy);
            assert_eq!(vm.get_var(BALL_EXPECTED_X), ball_expected_x);
            assert_eq!(vm.get_var(BALL_ROTATION), ball_rotation);
            assert_eq!(vm.get_var(BALL_FINE_ROT), ball_fine_rotation);
            assert_eq!(vm.get_var(BALL_PUNCH_RADIUS), punch_radius_after_render);
            assert_eq!(vm.get_var(BALL_PUNCH_X), 164);
            assert_eq!(vm.get_var(BALL_PUNCH_Y), 460);
            assert_eq!(vm.get_var(BALL_IS_POWER_HIT), 1);
            assert_eq!(vm.get_var(BALL_TOUCH_GROUND), 0);
        }

        assert_eq!(expectation_index, expectations.len());
    }

    #[test]
    fn generated_pikachu_script_matches_scaled_upstream_right_player_collision_power_hit_golden() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("script should initialize before forced right collision golden scenario"),
            Step::Yielded
        );

        vm.set_var(PHASE, 5);
        vm.set_var(FRAME_COUNTER, 0);
        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 0);
        vm.set_var(PRACTICE_MODE, 1);
        vm.set_var(SFX_MODE, 0);
        vm.set_var(BGM_ON, 0);
        vm.set_var(PAUSED, 0);
        vm.set_var(SCORE1, 0);
        vm.set_var(SCORE2, 0);
        vm.set_var(P1_X, 72);
        vm.set_var(P1_Y, 488);
        vm.set_var(P1_DY, 0);
        vm.set_var(P1_STATE, 0);
        vm.set_var(P1_FRAME, 0);
        vm.set_var(P1_DELAY, 0);
        vm.set_var(P1_COLLIDING, 0);
        vm.set_var(P2_X, 704);
        vm.set_var(P2_Y, 440);
        vm.set_var(P2_DY, 0);
        vm.set_var(P2_STATE, 2);
        vm.set_var(P2_FRAME, 0);
        vm.set_var(P2_DELAY, 0);
        vm.set_var(P2_COLLIDING, 0);
        vm.set_var(BALL_X, 700);
        vm.set_var(BALL_Y, 440);
        vm.set_var(BALL_DX, 0);
        vm.set_var(BALL_DY, 20);
        vm.set_var(BALL_EXPECTED_X, 112);
        vm.set_var(BALL_ROTATION, 0);
        vm.set_var(BALL_FINE_ROT, 0);
        vm.set_var(BALL_PUNCH_RADIUS, 0);
        vm.set_var(BALL_PUNCH_X, 0);
        vm.set_var(BALL_PUNCH_Y, 0);
        vm.set_var(BALL_IS_POWER_HIT, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);
        vm.set_var(SLOW_MOTION_FRAMES_LEFT, 0);
        vm.set_var(SLOW_MOTION_SKIP, 0);

        let expectations = [
            (
                1, 0, 1, 692, 440, 2, 2, 1, 0, 1, 700, 460, -40, -60, 420, 0, 0, 36,
            ),
            (
                2, 0, 2, 692, 442, 4, 2, 2, 0, 1, 660, 400, -40, -58, 420, 4, 40, 32,
            ),
            (
                3, 0, 3, 692, 446, 6, 2, 3, 0, 0, 620, 342, -40, -56, 420, 3, 30, 28,
            ),
            (
                4, 1, 0, 692, 452, 8, 2, 4, 0, 0, 580, 286, -40, -54, 420, 2, 20, 24,
            ),
            (
                5, 1, 1, 692, 460, 10, 1, 0, 0, 0, 540, 232, -40, -52, 420, 1, 10, 20,
            ),
            (
                6, 1, 2, 692, 470, 12, 1, 1, 0, 0, 500, 180, -40, -50, 420, 0, 0, 16,
            ),
            (
                10, 2, 2, 692, 488, 0, 0, 0, 3, 0, 340, 38, -40, 4, 420, 1, 10, 0,
            ),
            (
                15, 3, 3, 692, 488, 0, 0, 2, 0, 0, 140, 78, -40, 14, 420, 1, 10, 0,
            ),
            (
                20, 3, 0, 692, 488, 0, 0, 3, 1, 0, 180, 168, 40, 24, 420, 5, 50, 0,
            ),
        ];
        let mut expectation_index = 0;

        for step in 0..20 {
            host.keys_down.clear();
            host.keys_pressed.clear();

            if step == 0 {
                host.keys_down.extend([6, 8]);
            }
            if step == 1 {
                host.keys_pressed.push(10);
            }

            assert_eq!(
                vm.run_until_yield(&mut host, 800_000)
                    .expect("right collision golden frame should yield"),
                Step::Yielded
            );

            if expectation_index >= expectations.len()
                || expectations[expectation_index].0 != step + 1
            {
                continue;
            }

            let (
                _frame,
                p1_frame,
                p1_delay,
                p2_x,
                p2_y,
                p2_dy,
                p2_state,
                p2_frame,
                p2_delay,
                p2_collision,
                ball_x,
                ball_y,
                ball_dx,
                ball_dy,
                ball_expected_x,
                ball_rotation,
                ball_fine_rotation,
                punch_radius_after_render,
            ) = expectations[expectation_index];
            expectation_index += 1;

            assert_eq!(vm.get_var(P1_X), 72);
            assert_eq!(vm.get_var(P1_Y), 488);
            assert_eq!(vm.get_var(P1_DY), 0);
            assert_eq!(vm.get_var(P1_STATE), 0);
            assert_eq!(vm.get_var(P1_FRAME), p1_frame);
            assert_eq!(vm.get_var(P1_DELAY), p1_delay);
            assert_eq!(vm.get_var(P1_COLLIDING), 0);

            assert_eq!(vm.get_var(P2_X), p2_x);
            assert_eq!(vm.get_var(P2_Y), p2_y);
            assert_eq!(vm.get_var(P2_DY), p2_dy);
            assert_eq!(vm.get_var(P2_STATE), p2_state);
            assert_eq!(vm.get_var(P2_FRAME), p2_frame);
            assert_eq!(vm.get_var(P2_DELAY), p2_delay);
            assert_eq!(vm.get_var(P2_COLLIDING), p2_collision);

            assert_eq!(vm.get_var(BALL_X), ball_x);
            assert_eq!(vm.get_var(BALL_Y), ball_y);
            assert_eq!(vm.get_var(BALL_DX), ball_dx);
            assert_eq!(vm.get_var(BALL_DY), ball_dy);
            assert_eq!(vm.get_var(BALL_EXPECTED_X), ball_expected_x);
            assert_eq!(vm.get_var(BALL_ROTATION), ball_rotation);
            assert_eq!(vm.get_var(BALL_FINE_ROT), ball_fine_rotation);
            assert_eq!(vm.get_var(BALL_PUNCH_RADIUS), punch_radius_after_render);
            assert_eq!(vm.get_var(BALL_PUNCH_X), 700);
            assert_eq!(vm.get_var(BALL_PUNCH_Y), 460);
            assert_eq!(vm.get_var(BALL_IS_POWER_HIT), 1);
            assert_eq!(vm.get_var(BALL_TOUCH_GROUND), 0);
        }

        assert_eq!(expectation_index, expectations.len());
    }

    #[test]
    fn generated_pikachu_script_matches_scaled_upstream_wall_net_ground_golden() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("script should initialize before forced wall/net/ground golden scenario"),
            Step::Yielded
        );

        vm.set_var(PHASE, 5);
        vm.set_var(FRAME_COUNTER, 0);
        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 0);
        vm.set_var(PRACTICE_MODE, 1);
        vm.set_var(SFX_MODE, 0);
        vm.set_var(BGM_ON, 0);
        vm.set_var(PAUSED, 0);
        vm.set_var(SCORE1, 0);
        vm.set_var(SCORE2, 0);
        vm.set_var(P1_X, 72);
        vm.set_var(P1_Y, 488);
        vm.set_var(P1_DY, 0);
        vm.set_var(P1_STATE, 0);
        vm.set_var(P1_FRAME, 0);
        vm.set_var(P1_DELAY, 0);
        vm.set_var(P1_COLLIDING, 0);
        vm.set_var(P2_X, 792);
        vm.set_var(P2_Y, 488);
        vm.set_var(P2_DY, 0);
        vm.set_var(P2_STATE, 0);
        vm.set_var(P2_FRAME, 0);
        vm.set_var(P2_DELAY, 0);
        vm.set_var(P2_COLLIDING, 0);
        vm.set_var(BALL_X, 420);
        vm.set_var(BALL_Y, 360);
        vm.set_var(BALL_DX, 16);
        vm.set_var(BALL_DY, 12);
        vm.set_var(BALL_EXPECTED_X, 112);
        vm.set_var(BALL_ROTATION, 0);
        vm.set_var(BALL_FINE_ROT, 0);
        vm.set_var(BALL_PUNCH_RADIUS, 0);
        vm.set_var(BALL_PUNCH_X, 0);
        vm.set_var(BALL_PUNCH_Y, 0);
        vm.set_var(BALL_IS_POWER_HIT, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);
        vm.set_var(SLOW_MOTION_FRAMES_LEFT, 0);
        vm.set_var(SLOW_MOTION_SKIP, 0);

        let expectations = [
            (1, 0, 1, 0, 1, 436, 348, 16, -10, 740, 0, 4, 0, 0),
            (2, 0, 2, 0, 2, 452, 338, 16, -8, 740, 0, 8, 0, 0),
            (3, 0, 3, 0, 3, 468, 330, 16, -6, 740, 1, 12, 0, 0),
            (4, 1, 0, 1, 0, 484, 324, 16, -4, 740, 1, 16, 0, 0),
            (5, 1, 1, 1, 1, 500, 320, 16, -2, 740, 2, 20, 0, 0),
            (6, 1, 2, 1, 2, 516, 318, 16, 0, 740, 2, 24, 0, 0),
            (10, 2, 2, 2, 2, 580, 330, 16, 8, 740, 4, 40, 0, 0),
            (15, 3, 3, 3, 3, 660, 390, 16, 18, 740, 1, 10, 0, 0),
            (20, 3, 0, 3, 0, 740, 500, -16, -30, 244, 3, 30, 0, 1),
            (25, 2, 1, 2, 1, 660, 370, -16, -20, 244, 1, 10, 0, 0),
            (30, 1, 2, 1, 2, 580, 290, -16, -10, 244, 4, 40, 0, 0),
            (40, 2, 0, 2, 0, 420, 280, -16, 10, 244, 0, 0, 0, 0),
            (50, 4, 2, 4, 2, 260, 470, -16, 30, 244, 1, 10, 0, 0),
        ];
        let mut expectation_index = 0;

        for step in 0..50 {
            host.keys_down.clear();
            host.keys_pressed.clear();

            assert_eq!(
                vm.run_until_yield(&mut host, 800_000)
                    .expect("wall/net/ground golden frame should yield"),
                Step::Yielded
            );

            if expectation_index >= expectations.len()
                || expectations[expectation_index].0 != step + 1
            {
                continue;
            }

            let (
                _frame,
                p1_frame,
                p1_delay,
                p2_frame,
                p2_delay,
                ball_x,
                ball_y,
                ball_dx,
                ball_dy,
                ball_expected_x,
                ball_rotation,
                ball_fine_rotation,
                p1_collision,
                p2_collision,
            ) = expectations[expectation_index];
            expectation_index += 1;

            assert_eq!(vm.get_var(P1_X), 72);
            assert_eq!(vm.get_var(P1_Y), 488);
            assert_eq!(vm.get_var(P1_DY), 0);
            assert_eq!(vm.get_var(P1_STATE), 0);
            assert_eq!(vm.get_var(P1_FRAME), p1_frame);
            assert_eq!(vm.get_var(P1_DELAY), p1_delay);
            assert_eq!(vm.get_var(P1_COLLIDING), p1_collision);

            assert_eq!(vm.get_var(P2_X), 792);
            assert_eq!(vm.get_var(P2_Y), 488);
            assert_eq!(vm.get_var(P2_DY), 0);
            assert_eq!(vm.get_var(P2_STATE), 0);
            assert_eq!(vm.get_var(P2_FRAME), p2_frame);
            assert_eq!(vm.get_var(P2_DELAY), p2_delay);
            assert_eq!(vm.get_var(P2_COLLIDING), p2_collision);

            assert_eq!(vm.get_var(BALL_X), ball_x);
            assert_eq!(vm.get_var(BALL_Y), ball_y);
            assert_eq!(vm.get_var(BALL_DX), ball_dx);
            assert_eq!(vm.get_var(BALL_DY), ball_dy);
            assert_eq!(vm.get_var(BALL_EXPECTED_X), ball_expected_x);
            assert_eq!(vm.get_var(BALL_ROTATION), ball_rotation);
            assert_eq!(vm.get_var(BALL_FINE_ROT), ball_fine_rotation);
            assert_eq!(vm.get_var(BALL_PUNCH_RADIUS), 0);
            assert_eq!(vm.get_var(BALL_PUNCH_X), 0);
            assert_eq!(vm.get_var(BALL_PUNCH_Y), 0);
            assert_eq!(vm.get_var(BALL_IS_POWER_HIT), 0);
            assert_eq!(vm.get_var(BALL_TOUCH_GROUND), 0);
        }

        assert_eq!(expectation_index, expectations.len());
    }

    #[test]
    fn generated_pikachu_script_matches_scaled_upstream_left_wall_ceiling_golden() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("script should initialize before forced left-wall/ceiling golden scenario"),
            Step::Yielded
        );

        vm.set_var(PHASE, 5);
        vm.set_var(FRAME_COUNTER, 0);
        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 0);
        vm.set_var(PRACTICE_MODE, 1);
        vm.set_var(SFX_MODE, 0);
        vm.set_var(BGM_ON, 0);
        vm.set_var(PAUSED, 0);
        vm.set_var(SCORE1, 0);
        vm.set_var(SCORE2, 0);
        vm.set_var(P1_X, 72);
        vm.set_var(P1_Y, 488);
        vm.set_var(P1_DY, 0);
        vm.set_var(P1_STATE, 0);
        vm.set_var(P1_FRAME, 0);
        vm.set_var(P1_DELAY, 0);
        vm.set_var(P1_COLLIDING, 0);
        vm.set_var(P2_X, 792);
        vm.set_var(P2_Y, 488);
        vm.set_var(P2_DY, 0);
        vm.set_var(P2_STATE, 0);
        vm.set_var(P2_FRAME, 0);
        vm.set_var(P2_DELAY, 0);
        vm.set_var(P2_COLLIDING, 0);
        vm.set_var(BALL_X, 48);
        vm.set_var(BALL_Y, 12);
        vm.set_var(BALL_DX, -16);
        vm.set_var(BALL_DY, -14);
        vm.set_var(BALL_EXPECTED_X, 112);
        vm.set_var(BALL_ROTATION, 0);
        vm.set_var(BALL_FINE_ROT, 0);
        vm.set_var(BALL_PUNCH_RADIUS, 0);
        vm.set_var(BALL_PUNCH_X, 0);
        vm.set_var(BALL_PUNCH_Y, 0);
        vm.set_var(BALL_IS_POWER_HIT, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);
        vm.set_var(SLOW_MOTION_FRAMES_LEFT, 0);
        vm.set_var(SLOW_MOTION_SKIP, 0);

        let expectations = [
            (1, 0, 1, 0, 1, 64, 14, 16, 4, 384, 4, 46, 0, 0, 0, 0),
            (2, 0, 2, 0, 2, 80, 18, 16, 6, 384, 5, 50, 0, 0, 0, 0),
            (3, 0, 3, 0, 3, 96, 24, 16, 8, 384, 0, 4, 0, 0, 0, 0),
            (4, 1, 0, 1, 0, 112, 32, 16, 10, 384, 0, 8, 0, 0, 0, 0),
            (5, 1, 1, 1, 1, 128, 42, 16, 12, 384, 1, 12, 0, 0, 0, 0),
            (6, 1, 2, 1, 2, 144, 54, 16, 14, 384, 1, 16, 0, 0, 0, 0),
            (10, 2, 2, 2, 2, 208, 122, 16, 22, 384, 3, 32, 0, 0, 0, 0),
            (15, 3, 3, 3, 3, 288, 252, 16, 32, 384, 0, 2, 0, 0, 0, 0),
            (20, 3, 0, 3, 0, 368, 432, 16, 42, 384, 2, 22, 0, 0, 0, 0),
            (
                22, 3, 2, 3, 2, 384, 504, -16, -44, 384, 3, 30, 36, 384, 544, 1,
            ),
            (
                25, 2, 1, 2, 1, 336, 378, -16, -38, 384, 1, 18, 24, 384, 544, 0,
            ),
            (
                30, 1, 2, 1, 2, 256, 208, -16, -28, 384, 4, 48, 4, 384, 544, 0,
            ),
            (40, 2, 0, 2, 0, 96, 18, -16, -8, 384, 0, 8, 0, 384, 544, 0),
            (50, 4, 2, 4, 2, 160, 56, 16, 16, 384, 1, 16, 0, 384, 544, 0),
            (
                65, 0, 1, 0, 1, 384, 504, -16, -44, 384, 2, 26, 36, 384, 544, 1,
            ),
        ];
        let mut expectation_index = 0;

        for step in 0..70 {
            host.keys_down.clear();
            host.keys_pressed.clear();

            assert_eq!(
                vm.run_until_yield(&mut host, 800_000)
                    .expect("left-wall/ceiling golden frame should yield"),
                Step::Yielded
            );

            if expectation_index >= expectations.len()
                || expectations[expectation_index].0 != step + 1
            {
                continue;
            }

            let (
                _frame,
                p1_frame,
                p1_delay,
                p2_frame,
                p2_delay,
                ball_x,
                ball_y,
                ball_dx,
                ball_dy,
                ball_expected_x,
                ball_rotation,
                ball_fine_rotation,
                punch_radius_after_render,
                punch_x,
                punch_y,
                touched,
            ) = expectations[expectation_index];
            expectation_index += 1;

            assert_eq!(vm.get_var(P1_X), 72);
            assert_eq!(vm.get_var(P1_Y), 488);
            assert_eq!(vm.get_var(P1_DY), 0);
            assert_eq!(vm.get_var(P1_STATE), 0);
            assert_eq!(vm.get_var(P1_FRAME), p1_frame);
            assert_eq!(vm.get_var(P1_DELAY), p1_delay);
            assert_eq!(vm.get_var(P1_COLLIDING), 0);

            assert_eq!(vm.get_var(P2_X), 792);
            assert_eq!(vm.get_var(P2_Y), 488);
            assert_eq!(vm.get_var(P2_DY), 0);
            assert_eq!(vm.get_var(P2_STATE), 0);
            assert_eq!(vm.get_var(P2_FRAME), p2_frame);
            assert_eq!(vm.get_var(P2_DELAY), p2_delay);
            assert_eq!(vm.get_var(P2_COLLIDING), 0);

            assert_eq!(vm.get_var(BALL_X), ball_x);
            assert_eq!(vm.get_var(BALL_Y), ball_y);
            assert_eq!(vm.get_var(BALL_DX), ball_dx);
            assert_eq!(vm.get_var(BALL_DY), ball_dy);
            assert_eq!(vm.get_var(BALL_EXPECTED_X), ball_expected_x);
            assert_eq!(vm.get_var(BALL_ROTATION), ball_rotation);
            assert_eq!(vm.get_var(BALL_FINE_ROT), ball_fine_rotation);
            assert_eq!(vm.get_var(BALL_PUNCH_RADIUS), punch_radius_after_render);
            assert_eq!(vm.get_var(BALL_PUNCH_X), punch_x);
            assert_eq!(vm.get_var(BALL_PUNCH_Y), punch_y);
            assert_eq!(vm.get_var(BALL_IS_POWER_HIT), 0);
            assert_eq!(vm.get_var(BALL_TOUCH_GROUND), touched);
        }

        assert_eq!(expectation_index, expectations.len());
    }

    #[test]
    fn generated_pikachu_script_matches_scaled_upstream_ai_left_tracks_ball_golden() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("script should initialize before forced left-AI golden scenario"),
            Step::Yielded
        );

        vm.set_var(PHASE, 5);
        vm.set_var(FRAME_COUNTER, 0);
        vm.set_var(P1_COMPUTER, 1);
        vm.set_var(P2_COMPUTER, 0);
        vm.set_var(P1_BOLDNESS, 2);
        vm.set_var(P2_BOLDNESS, 2);
        vm.set_var(P1_STANDBY, 0);
        vm.set_var(P2_STANDBY, 0);
        vm.set_var(RNG_FIXED_ENABLED, 1);
        vm.set_var(RNG_FIXED_VALUE, FIXED_GOLDEN_RAND);
        vm.set_var(PRACTICE_MODE, 1);
        vm.set_var(SFX_MODE, 0);
        vm.set_var(BGM_ON, 0);
        vm.set_var(PAUSED, 0);
        vm.set_var(SCORE1, 0);
        vm.set_var(SCORE2, 0);
        vm.set_var(P1_X, 72);
        vm.set_var(P1_Y, 488);
        vm.set_var(P1_DY, 0);
        vm.set_var(P1_STATE, 0);
        vm.set_var(P1_FRAME, 0);
        vm.set_var(P1_DELAY, 0);
        vm.set_var(P1_COLLIDING, 0);
        vm.set_var(P2_X, 792);
        vm.set_var(P2_Y, 488);
        vm.set_var(P2_DY, 0);
        vm.set_var(P2_STATE, 0);
        vm.set_var(P2_FRAME, 0);
        vm.set_var(P2_DELAY, 0);
        vm.set_var(P2_COLLIDING, 0);
        vm.set_var(BALL_X, 240);
        vm.set_var(BALL_Y, 160);
        vm.set_var(BALL_DX, 4);
        vm.set_var(BALL_DY, 8);
        vm.set_var(BALL_EXPECTED_X, 240);
        vm.set_var(BALL_ROTATION, 0);
        vm.set_var(BALL_FINE_ROT, 0);
        vm.set_var(BALL_PUNCH_RADIUS, 0);
        vm.set_var(BALL_PUNCH_X, 0);
        vm.set_var(BALL_PUNCH_Y, 0);
        vm.set_var(BALL_IS_POWER_HIT, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);
        vm.set_var(SLOW_MOTION_FRAMES_LEFT, 0);
        vm.set_var(SLOW_MOTION_SKIP, 0);

        let expectations = [
            (1, 84, 0, 1, 0, 1, 244, 168, 4, 10, 300, 0, 1),
            (2, 96, 0, 2, 0, 2, 248, 178, 4, 12, 300, 0, 2),
            (3, 108, 0, 3, 0, 3, 252, 190, 4, 14, 300, 0, 3),
            (4, 120, 1, 0, 1, 0, 256, 204, 4, 16, 300, 0, 4),
            (5, 132, 1, 1, 1, 1, 260, 220, 4, 18, 300, 0, 5),
            (6, 144, 1, 2, 1, 2, 264, 238, 4, 20, 300, 0, 6),
            (10, 192, 2, 2, 2, 2, 280, 330, 4, 28, 300, 1, 10),
            (15, 252, 3, 3, 3, 3, 314, 418, 18, -34, 728, 1, 18),
            (20, 312, 3, 0, 3, 0, 404, 268, 18, -24, 728, 3, 38),
            (25, 368, 2, 1, 2, 1, 494, 168, 18, -14, 728, 0, 8),
            (30, 368, 1, 2, 1, 2, 584, 118, 18, -4, 728, 2, 28),
            (40, 368, 2, 0, 2, 0, 764, 168, 18, 16, 728, 1, 18),
        ];
        let mut expectation_index = 0;

        for step in 0..40 {
            host.keys_down.clear();
            host.keys_pressed.clear();

            assert_eq!(
                vm.run_until_yield(&mut host, 800_000)
                    .expect("left-AI golden frame should yield"),
                Step::Yielded
            );

            if expectation_index >= expectations.len()
                || expectations[expectation_index].0 != step + 1
            {
                continue;
            }

            let (
                _frame,
                p1_x,
                p1_frame,
                p1_delay,
                p2_frame,
                p2_delay,
                ball_x,
                ball_y,
                ball_dx,
                ball_dy,
                ball_expected_x,
                ball_rotation,
                ball_fine_rotation,
            ) = expectations[expectation_index];
            expectation_index += 1;

            assert_eq!(vm.get_var(P1_X), p1_x);
            assert_eq!(vm.get_var(P1_Y), 488);
            assert_eq!(vm.get_var(P1_DY), 0);
            assert_eq!(vm.get_var(P1_STATE), 0);
            assert_eq!(vm.get_var(P1_FRAME), p1_frame);
            assert_eq!(vm.get_var(P1_DELAY), p1_delay);
            assert_eq!(vm.get_var(P1_COLLIDING), 0);

            assert_eq!(vm.get_var(P2_X), 792);
            assert_eq!(vm.get_var(P2_Y), 488);
            assert_eq!(vm.get_var(P2_DY), 0);
            assert_eq!(vm.get_var(P2_STATE), 0);
            assert_eq!(vm.get_var(P2_FRAME), p2_frame);
            assert_eq!(vm.get_var(P2_DELAY), p2_delay);
            assert_eq!(vm.get_var(P2_COLLIDING), 0);

            assert_eq!(vm.get_var(BALL_X), ball_x);
            assert_eq!(vm.get_var(BALL_Y), ball_y);
            assert_eq!(vm.get_var(BALL_DX), ball_dx);
            assert_eq!(vm.get_var(BALL_DY), ball_dy);
            assert_eq!(vm.get_var(BALL_EXPECTED_X), ball_expected_x);
            assert_eq!(vm.get_var(BALL_ROTATION), ball_rotation);
            assert_eq!(vm.get_var(BALL_FINE_ROT), ball_fine_rotation);
            assert_eq!(vm.get_var(BALL_PUNCH_RADIUS), 0);
            assert_eq!(vm.get_var(BALL_PUNCH_X), 0);
            assert_eq!(vm.get_var(BALL_PUNCH_Y), 0);
            assert_eq!(vm.get_var(BALL_IS_POWER_HIT), 0);
            assert_eq!(vm.get_var(BALL_TOUCH_GROUND), 0);
        }

        assert_eq!(expectation_index, expectations.len());
    }

    #[test]
    fn generated_pikachu_script_matches_scaled_upstream_ai_right_tracks_ball_golden() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("script should initialize before forced right-AI golden scenario"),
            Step::Yielded
        );

        vm.set_var(PHASE, 5);
        vm.set_var(FRAME_COUNTER, 0);
        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 1);
        vm.set_var(P1_BOLDNESS, 2);
        vm.set_var(P2_BOLDNESS, 2);
        vm.set_var(P1_STANDBY, 0);
        vm.set_var(P2_STANDBY, 0);
        vm.set_var(RNG_FIXED_ENABLED, 1);
        vm.set_var(RNG_FIXED_VALUE, FIXED_GOLDEN_RAND);
        vm.set_var(PRACTICE_MODE, 1);
        vm.set_var(SFX_MODE, 0);
        vm.set_var(BGM_ON, 0);
        vm.set_var(PAUSED, 0);
        vm.set_var(SCORE1, 0);
        vm.set_var(SCORE2, 0);
        vm.set_var(P1_X, 72);
        vm.set_var(P1_Y, 488);
        vm.set_var(P1_DY, 0);
        vm.set_var(P1_STATE, 0);
        vm.set_var(P1_FRAME, 0);
        vm.set_var(P1_DELAY, 0);
        vm.set_var(P1_COLLIDING, 0);
        vm.set_var(P2_X, 792);
        vm.set_var(P2_Y, 488);
        vm.set_var(P2_DY, 0);
        vm.set_var(P2_STATE, 0);
        vm.set_var(P2_FRAME, 0);
        vm.set_var(P2_DELAY, 0);
        vm.set_var(P2_COLLIDING, 0);
        vm.set_var(BALL_X, 624);
        vm.set_var(BALL_Y, 160);
        vm.set_var(BALL_DX, -4);
        vm.set_var(BALL_DY, 8);
        vm.set_var(BALL_EXPECTED_X, 624);
        vm.set_var(BALL_ROTATION, 0);
        vm.set_var(BALL_FINE_ROT, 0);
        vm.set_var(BALL_PUNCH_RADIUS, 0);
        vm.set_var(BALL_PUNCH_X, 0);
        vm.set_var(BALL_PUNCH_Y, 0);
        vm.set_var(BALL_IS_POWER_HIT, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);
        vm.set_var(SLOW_MOTION_FRAMES_LEFT, 0);
        vm.set_var(SLOW_MOTION_SKIP, 0);

        let expectations = [
            (1, 0, 1, 780, 0, 1, 620, 168, -4, 10, 564, 4, 49),
            (2, 0, 2, 768, 0, 2, 616, 178, -4, 12, 564, 4, 48),
            (3, 0, 3, 756, 0, 3, 612, 190, -4, 14, 564, 4, 47),
            (4, 1, 0, 744, 1, 0, 608, 204, -4, 16, 564, 4, 46),
            (5, 1, 1, 732, 1, 1, 604, 220, -4, 18, 564, 4, 45),
            (6, 1, 2, 720, 1, 2, 600, 238, -4, 20, 564, 4, 44),
            (10, 2, 2, 672, 2, 2, 584, 330, -4, 28, 564, 4, 40),
            (15, 3, 3, 612, 3, 3, 550, 418, -18, -34, 208, 3, 32),
            (20, 3, 0, 552, 3, 0, 460, 268, -18, -24, 208, 1, 12),
            (25, 2, 1, 496, 2, 1, 370, 168, -18, -14, 208, 4, 42),
            (30, 1, 2, 496, 1, 2, 280, 118, -18, -4, 208, 2, 22),
            (40, 2, 0, 496, 2, 0, 100, 168, -18, 16, 208, 3, 32),
        ];
        let mut expectation_index = 0;

        for step in 0..40 {
            host.keys_down.clear();
            host.keys_pressed.clear();

            assert_eq!(
                vm.run_until_yield(&mut host, 800_000)
                    .expect("right-AI golden frame should yield"),
                Step::Yielded
            );

            if expectation_index >= expectations.len()
                || expectations[expectation_index].0 != step + 1
            {
                continue;
            }

            let (
                _frame,
                p1_frame,
                p1_delay,
                p2_x,
                p2_frame,
                p2_delay,
                ball_x,
                ball_y,
                ball_dx,
                ball_dy,
                ball_expected_x,
                ball_rotation,
                ball_fine_rotation,
            ) = expectations[expectation_index];
            expectation_index += 1;

            assert_eq!(vm.get_var(P1_X), 72);
            assert_eq!(vm.get_var(P1_Y), 488);
            assert_eq!(vm.get_var(P1_DY), 0);
            assert_eq!(vm.get_var(P1_STATE), 0);
            assert_eq!(vm.get_var(P1_FRAME), p1_frame);
            assert_eq!(vm.get_var(P1_DELAY), p1_delay);
            assert_eq!(vm.get_var(P1_COLLIDING), 0);

            assert_eq!(vm.get_var(P2_X), p2_x);
            assert_eq!(vm.get_var(P2_Y), 488);
            assert_eq!(vm.get_var(P2_DY), 0);
            assert_eq!(vm.get_var(P2_STATE), 0);
            assert_eq!(vm.get_var(P2_FRAME), p2_frame);
            assert_eq!(vm.get_var(P2_DELAY), p2_delay);
            assert_eq!(vm.get_var(P2_COLLIDING), 0);

            assert_eq!(vm.get_var(BALL_X), ball_x);
            assert_eq!(vm.get_var(BALL_Y), ball_y);
            assert_eq!(vm.get_var(BALL_DX), ball_dx);
            assert_eq!(vm.get_var(BALL_DY), ball_dy);
            assert_eq!(vm.get_var(BALL_EXPECTED_X), ball_expected_x);
            assert_eq!(vm.get_var(BALL_ROTATION), ball_rotation);
            assert_eq!(vm.get_var(BALL_FINE_ROT), ball_fine_rotation);
            assert_eq!(vm.get_var(BALL_PUNCH_RADIUS), 0);
            assert_eq!(vm.get_var(BALL_PUNCH_X), 0);
            assert_eq!(vm.get_var(BALL_PUNCH_Y), 0);
            assert_eq!(vm.get_var(BALL_IS_POWER_HIT), 0);
            assert_eq!(vm.get_var(BALL_TOUCH_GROUND), 0);
        }

        assert_eq!(expectation_index, expectations.len());
    }

    #[test]
    fn generated_pikachu_script_matches_scaled_upstream_ai_left_long_golden() {
        let expectations = [
            ai_frame(
                1,
                0,
                [84, 488, 0, 0, 0, 1, 0],
                [792, 488, 0, 0, 0, 1, 0],
                [244, 168, 4, 10, 300, 0, 1, 0],
            ),
            ai_frame(
                2,
                0,
                [96, 488, 0, 0, 0, 2, 0],
                [792, 488, 0, 0, 0, 2, 0],
                [248, 178, 4, 12, 300, 0, 2, 0],
            ),
            ai_frame(
                3,
                0,
                [108, 488, 0, 0, 0, 3, 0],
                [792, 488, 0, 0, 0, 3, 0],
                [252, 190, 4, 14, 300, 0, 3, 0],
            ),
            ai_frame(
                4,
                0,
                [120, 488, 0, 0, 1, 0, 0],
                [792, 488, 0, 0, 1, 0, 0],
                [256, 204, 4, 16, 300, 0, 4, 0],
            ),
            ai_frame(
                5,
                0,
                [132, 488, 0, 0, 1, 1, 0],
                [792, 488, 0, 0, 1, 1, 0],
                [260, 220, 4, 18, 300, 0, 5, 0],
            ),
            ai_frame(
                6,
                0,
                [144, 488, 0, 0, 1, 2, 0],
                [792, 488, 0, 0, 1, 2, 0],
                [264, 238, 4, 20, 300, 0, 6, 0],
            ),
            ai_frame(
                10,
                0,
                [192, 488, 0, 0, 2, 2, 0],
                [792, 488, 0, 0, 2, 2, 0],
                [280, 330, 4, 28, 300, 1, 10, 0],
            ),
            ai_frame(
                15,
                0,
                [252, 488, 0, 0, 3, 3, 0],
                [792, 488, 0, 0, 3, 3, 0],
                [314, 418, 18, -34, 728, 1, 18, 0],
            ),
            ai_frame(
                20,
                0,
                [312, 488, 0, 0, 3, 0, 0],
                [792, 488, 0, 0, 3, 0, 0],
                [404, 268, 18, -24, 728, 3, 38, 0],
            ),
            ai_frame(
                26,
                0,
                [368, 488, 0, 0, 2, 2, 0],
                [792, 488, 0, 0, 2, 2, 0],
                [512, 154, 18, -12, 728, 1, 12, 0],
            ),
            ai_frame(
                51,
                0,
                [368, 488, 0, 0, 4, 3, 0],
                [792, 488, 0, 0, 4, 3, 1],
                [746, 454, -14, -38, 186, 2, 22, 0],
            ),
            ai_frame(
                76,
                0,
                [200, 488, 0, 0, 3, 0, 0],
                [792, 488, 0, 0, 3, 0, 0],
                [396, 104, -14, 12, 186, 4, 47, 0],
            ),
            ai_frame(
                101,
                0,
                [332, 488, 0, 0, 1, 1, 0],
                [792, 488, 0, 0, 1, 1, 0],
                [46, 124, -14, -18, 746, 2, 22, 0],
            ),
            ai_frame(
                126,
                0,
                [368, 488, 0, 0, 1, 2, 0],
                [792, 488, 0, 0, 1, 2, 0],
                [396, 274, 14, 32, 746, 4, 41, 0],
            ),
            ai_frame(
                151,
                0,
                [368, 488, 0, 0, 3, 3, 0],
                [792, 488, 0, 0, 3, 3, 0],
                [746, 32, 14, 12, 746, 1, 16, 0],
            ),
            ai_frame(
                176,
                0,
                [260, 488, 0, 0, 4, 0, 0],
                [792, 488, 0, 0, 4, 0, 0],
                [620, 140, -14, -26, 228, 4, 45, 0],
            ),
            ai_frame(
                201,
                0,
                [248, 488, 0, 0, 2, 1, 0],
                [792, 488, 0, 0, 2, 1, 0],
                [270, 342, -14, 38, 228, 2, 20, 0],
            ),
            ai_frame(
                226,
                0,
                [92, 306, -18, 1, 1, 3, 0],
                [792, 488, 0, 0, 0, 2, 0],
                [96, 68, -6, 16, 72, 3, 39, 0],
            ),
            ai_frame(
                251,
                1,
                [308, 456, 32, 1, 0, 0, 0],
                [792, 488, 0, 0, 2, 3, 0],
                [380, 504, -20, -36, 360, 1, 18, 1],
            ),
            ai_frame(
                259,
                1,
                [320, 306, -18, 2, 2, 0, 0],
                [792, 488, 0, 0, 0, 3, 0],
                [320, 504, -20, -12, 60, 0, 8, 1],
            ),
            ai_frame(
                273,
                1,
                [152, 236, 10, 1, 2, 0, 0],
                [792, 488, 0, 0, 4, 1, 0],
                [60, 504, -20, -14, 320, 3, 38, 1],
            ),
            ai_frame(
                276,
                0,
                [116, 272, 16, 1, 2, 0, 0],
                [792, 488, 0, 0, 3, 0, 0],
                [80, 468, 20, -8, 320, 3, 33, 1],
            ),
        ];

        run_forced_ai_golden("ai_left_long_300", 300, 1, 0, 240, 4, 240, &expectations);
    }

    #[test]
    fn generated_pikachu_script_matches_scaled_upstream_ai_right_long_golden() {
        let expectations = [
            ai_frame(
                1,
                0,
                [72, 488, 0, 0, 0, 1, 0],
                [780, 488, 0, 0, 0, 1, 0],
                [620, 168, -4, 10, 564, 4, 49, 0],
            ),
            ai_frame(
                2,
                0,
                [72, 488, 0, 0, 0, 2, 0],
                [768, 488, 0, 0, 0, 2, 0],
                [616, 178, -4, 12, 564, 4, 48, 0],
            ),
            ai_frame(
                3,
                0,
                [72, 488, 0, 0, 0, 3, 0],
                [756, 488, 0, 0, 0, 3, 0],
                [612, 190, -4, 14, 564, 4, 47, 0],
            ),
            ai_frame(
                4,
                0,
                [72, 488, 0, 0, 1, 0, 0],
                [744, 488, 0, 0, 1, 0, 0],
                [608, 204, -4, 16, 564, 4, 46, 0],
            ),
            ai_frame(
                5,
                0,
                [72, 488, 0, 0, 1, 1, 0],
                [732, 488, 0, 0, 1, 1, 0],
                [604, 220, -4, 18, 564, 4, 45, 0],
            ),
            ai_frame(
                6,
                0,
                [72, 488, 0, 0, 1, 2, 0],
                [720, 488, 0, 0, 1, 2, 0],
                [600, 238, -4, 20, 564, 4, 44, 0],
            ),
            ai_frame(
                10,
                0,
                [72, 488, 0, 0, 2, 2, 0],
                [672, 488, 0, 0, 2, 2, 0],
                [584, 330, -4, 28, 564, 4, 40, 0],
            ),
            ai_frame(
                15,
                0,
                [72, 488, 0, 0, 3, 3, 0],
                [612, 488, 0, 0, 3, 3, 0],
                [550, 418, -18, -34, 208, 3, 32, 0],
            ),
            ai_frame(
                20,
                0,
                [72, 488, 0, 0, 3, 0, 0],
                [552, 488, 0, 0, 3, 0, 0],
                [460, 268, -18, -24, 208, 1, 12, 0],
            ),
            ai_frame(
                26,
                0,
                [72, 488, 0, 0, 2, 2, 0],
                [496, 488, 0, 0, 2, 2, 0],
                [352, 154, -18, -12, 208, 3, 38, 0],
            ),
            ai_frame(
                51,
                0,
                [72, 488, 0, 0, 4, 3, 0],
                [496, 488, 0, 0, 4, 3, 0],
                [190, 454, 18, 38, 208, 4, 44, 0],
            ),
            ai_frame(
                53,
                1,
                [72, 488, 0, 0, 3, 1, 0],
                [508, 488, 0, 0, 3, 1, 0],
                [208, 504, 18, -40, 766, 0, 2, 0],
            ),
            ai_frame(
                76,
                0,
                [72, 488, 0, 0, 3, 0, 0],
                [748, 488, 0, 0, 3, 0, 0],
                [622, 90, 18, 6, 766, 4, 44, 0],
            ),
            ai_frame(
                101,
                0,
                [72, 488, 0, 0, 1, 1, 0],
                [640, 488, 0, 0, 1, 1, 0],
                [748, 156, -18, -20, 190, 3, 38, 0],
            ),
            ai_frame(
                126,
                0,
                [72, 488, 0, 0, 1, 2, 0],
                [496, 488, 0, 0, 1, 2, 0],
                [298, 256, -18, 30, 190, 3, 38, 0],
            ),
            ai_frame(
                133,
                1,
                [72, 488, 0, 0, 1, 1, 0],
                [508, 488, 0, 0, 1, 1, 0],
                [190, 504, -18, -42, 676, 1, 10, 0],
            ),
            ai_frame(
                151,
                0,
                [72, 488, 0, 0, 3, 3, 0],
                [664, 488, 0, 0, 3, 3, 0],
                [226, 54, 18, -6, 676, 1, 10, 0],
            ),
            ai_frame(
                176,
                0,
                [72, 488, 0, 0, 4, 0, 0],
                [652, 488, 0, 0, 4, 0, 0],
                [656, 420, -2, -40, 572, 0, 6, 0],
            ),
            ai_frame(
                201,
                0,
                [72, 488, 0, 0, 2, 1, 0],
                [592, 348, -22, 1, 2, 0, 0],
                [606, 20, -2, 10, 572, 0, 6, 0],
            ),
            ai_frame(
                226,
                0,
                [72, 488, 0, 0, 0, 2, 0],
                [496, 398, 28, 1, 2, 0, 0],
                [188, 190, 40, 28, 348, 3, 36, 1],
            ),
            ai_frame(
                235,
                1,
                [72, 488, 0, 0, 2, 3, 0],
                [496, 488, 0, 0, 1, 2, 0],
                [348, 504, -40, -44, 188, 3, 36, 1],
            ),
            ai_frame(
                251,
                0,
                [72, 488, 0, 0, 2, 3, 0],
                [496, 488, 0, 0, 3, 2, 0],
                [428, 40, 40, -12, 188, 3, 36, 1],
            ),
            ai_frame(
                276,
                0,
                [72, 488, 0, 0, 3, 0, 0],
                [496, 488, 0, 0, 3, 3, 0],
                [228, 420, -40, 42, 188, 0, 6, 1],
            ),
            ai_frame(
                278,
                1,
                [72, 488, 0, 0, 3, 2, 0],
                [496, 488, 0, 0, 4, 1, 0],
                [188, 504, -40, -44, 108, 3, 36, 1],
            ),
        ];

        run_forced_ai_golden("ai_right_long_300", 300, 0, 1, 624, -4, 624, &expectations);
    }

    #[test]
    fn generated_pikachu_script_records_floor_touch_and_slow_motion_state() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();

        for _ in 0..570 {
            assert_eq!(
                vm.run_until_yield(&mut host, 600_000)
                    .expect("script should reach round phase"),
                Step::Yielded
            );
        }
        assert_eq!(vm.get_var(PHASE), 5);

        let floor_y = vm.get_var(FLOOR_Y);
        let ball_floor_y = vm.get_var(BALL_FLOOR_Y);
        let ball_ground_sfx = round_sfx_event("BALL_SOUND_GROUND");
        vm.set_var(BALL_X, 200);
        vm.set_var(BALL_Y, ball_floor_y + 1);
        vm.set_var(BALL_DX, 0);
        vm.set_var(BALL_DY, 3);
        vm.set_var(SCORE1, 0);
        vm.set_var(SCORE2, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);
        vm.set_var(SLOW_MOTION_FRAMES_LEFT, 0);
        vm.set_var(SLOW_MOTION_SKIP, 0);
        host.played_sounds.clear();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("forced floor contact should yield"),
            Step::Yielded
        );

        assert_eq!(vm.get_var(SCORE1), 0);
        assert_eq!(vm.get_var(SCORE2), 1);
        assert_eq!(vm.get_var(IS_P2_SERVE), 1);
        assert_eq!(vm.get_var(BALL_TOUCH_GROUND), 1);
        assert_eq!(vm.get_var(ROUND_ENDED), 1);
        assert_eq!(vm.get_var(GAME_ENDED), 0);
        assert_eq!(vm.get_var(SLOW_MOTION_FRAMES_LEFT), 6);
        assert_eq!(vm.get_var(SLOW_MOTION_SKIP), 0);
        assert!(host.played_sounds.contains(&ball_ground_sfx.sound_id));
        assert!(host.sound_events.contains(&sfx_event_for_ball_side(
            ball_ground_sfx,
            package_assets::SFX_STEREO_MODE,
            -1
        )));
        assert_eq!(vm.get_var(BALL_SOUND_GROUND), 0);
        assert_eq!(vm.get_var(BALL_PUNCH_X), 200);
        assert_eq!(
            vm.get_var(BALL_PUNCH_Y),
            ball_floor_y + vm.get_var(BALL_RADIUS)
        );
        assert!((1..=vm.get_var(BALL_RADIUS)).contains(&vm.get_var(BALL_PUNCH_RADIUS)));
        assert_eq!(vm.get_var(BALL_Y), ball_floor_y);
        assert!(vm.get_var(BALL_DY) < 0);
        assert_eq!(vm.get_var(PHASE), 5);

        vm.set_var(PHASE, 5);
        vm.set_var(FRAME_COUNTER, 100);
        vm.set_var(PRACTICE_MODE, 0);
        vm.set_var(SFX_MODE, 2);
        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 0);
        vm.set_var(P1_X, 100);
        vm.set_var(P1_Y, floor_y);
        vm.set_var(P1_STATE, 0);
        vm.set_var(P2_X, 760);
        vm.set_var(P2_Y, floor_y);
        vm.set_var(P2_STATE, 0);
        vm.set_var(BALL_X, vm.get_var(MID_X));
        vm.set_var(BALL_Y, ball_floor_y + 1);
        vm.set_var(BALL_DX, 0);
        vm.set_var(BALL_DY, 3);
        vm.set_var(SCORE1, 0);
        vm.set_var(SCORE2, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);
        vm.set_var(SLOW_MOTION_FRAMES_LEFT, 0);
        vm.set_var(SLOW_MOTION_SKIP, 0);
        host.played_sounds.clear();
        host.sound_events.clear();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("center-line floor contact should score for player 1"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(SCORE1), 1);
        assert_eq!(vm.get_var(SCORE2), 0);
        assert_eq!(vm.get_var(IS_P2_SERVE), 0);
        assert_eq!(vm.get_var(BALL_PUNCH_X), vm.get_var(MID_X));

        vm.set_var(PHASE, 5);
        vm.set_var(FRAME_COUNTER, 100);
        vm.set_var(PRACTICE_MODE, 0);
        vm.set_var(SFX_MODE, 2);
        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 0);
        vm.set_var(P1_X, 100);
        vm.set_var(P1_Y, floor_y);
        vm.set_var(P1_STATE, 0);
        vm.set_var(P2_X, 760);
        vm.set_var(P2_Y, floor_y);
        vm.set_var(P2_STATE, 0);
        vm.set_var(BALL_X, 200);
        vm.set_var(BALL_Y, ball_floor_y + 1);
        vm.set_var(BALL_DX, 0);
        vm.set_var(BALL_DY, 3);
        vm.set_var(SCORE1, 0);
        vm.set_var(SCORE2, 14);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);
        vm.set_var(P1_GAME_ENDED, 0);
        vm.set_var(P2_GAME_ENDED, 0);
        vm.set_var(P1_WINNER, 0);
        vm.set_var(P2_WINNER, 0);
        vm.set_var(SLOW_MOTION_FRAMES_LEFT, 0);
        vm.set_var(SLOW_MOTION_SKIP, 0);
        host.played_sounds.clear();
        host.sound_events.clear();
        host.bgm_stops = 0;

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("winning floor contact should enter game end"),
            Step::Yielded
        );

        assert_eq!(vm.get_var(SCORE2), 15);
        assert_eq!(vm.get_var(PHASE), 8);
        assert_eq!(vm.get_var(GAME_ENDED), 1);
        assert_eq!(vm.get_var(P1_GAME_ENDED), 1);
        assert_eq!(vm.get_var(P2_GAME_ENDED), 1);
        assert_eq!(vm.get_var(P1_WINNER), 0);
        assert_eq!(vm.get_var(P2_WINNER), 1);
        assert_eq!(vm.get_var(P1_STATE), 6);
        assert_eq!(vm.get_var(P2_STATE), 5);
        assert_eq!(vm.get_var(SLOW_MOTION_FRAMES_LEFT), 0);
        let p2_pipikachu_sfx = round_sfx_event("P2_SOUND_PIPIKACHU");
        assert!(host.played_sounds.contains(&p2_pipikachu_sfx.sound_id));
        assert!(host.sound_events.contains(&sfx_event_for_fixed_side(
            p2_pipikachu_sfx,
            package_assets::SFX_STEREO_MODE
        )));
        assert_eq!(host.bgm_stops, 0);
    }

    #[test]
    fn generated_pikachu_script_applies_ball_wall_and_net_world_collisions() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();

        for _ in 0..570 {
            assert_eq!(
                vm.run_until_yield(&mut host, 600_000)
                    .expect("script should reach round phase"),
                Step::Yielded
            );
        }
        assert_eq!(vm.get_var(PHASE), 5);

        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 0);
        vm.set_var(P1_X, 100);
        vm.set_var(P1_Y, vm.get_var(FLOOR_Y));
        vm.set_var(P1_DY, 0);
        vm.set_var(P1_STATE, 0);
        vm.set_var(P2_X, 760);
        vm.set_var(P2_Y, vm.get_var(FLOOR_Y));
        vm.set_var(P2_DY, 0);
        vm.set_var(P2_STATE, 0);

        vm.set_var(BALL_X, 25);
        vm.set_var(BALL_Y, 200);
        vm.set_var(BALL_DX, -8);
        vm.set_var(BALL_DY, 0);
        vm.set_var(BALL_FINE_ROT, 30);
        vm.set_var(BALL_ROTATION, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("wall collision should keep yielding"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(BALL_DX), 8);
        assert_eq!(vm.get_var(BALL_X), 33);
        assert_eq!(vm.get_var(BALL_Y), 200);
        assert_eq!(vm.get_var(BALL_FINE_ROT), 28);
        assert_eq!(vm.get_var(BALL_ROTATION), 2);
        assert_eq!(vm.get_var(BALL_TOUCH_GROUND), 0);

        vm.set_var(BALL_X, 430);
        vm.set_var(BALL_Y, 390);
        vm.set_var(BALL_DX, 10);
        vm.set_var(BALL_DY, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("net side collision should keep yielding"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(BALL_DX), -10);
        assert_eq!(vm.get_var(BALL_X), 420);
        assert_eq!(vm.get_var(BALL_Y), 390);
        assert_eq!(vm.get_var(BALL_TOUCH_GROUND), 0);

        vm.set_var(BALL_X, 430);
        vm.set_var(BALL_Y, 360);
        vm.set_var(BALL_DX, 0);
        vm.set_var(BALL_DY, 10);
        vm.set_var(BALL_TOUCH_GROUND, 0);

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("net top collision should keep yielding"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(BALL_DX), 0);
        assert_eq!(vm.get_var(BALL_X), 430);
        assert_eq!(vm.get_var(BALL_Y), 350);
        assert_eq!(vm.get_var(BALL_DY), -8);
        assert_eq!(vm.get_var(BALL_TOUCH_GROUND), 0);

        host.record_sprites = true;
        host.drawn_sprites.clear();
        host.drawn_sprite_calls.clear();
        vm.set_var(PHASE, 5);
        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 0);
        vm.set_var(P1_X, 100);
        vm.set_var(P1_Y, vm.get_var(FLOOR_Y));
        vm.set_var(P1_DY, 0);
        vm.set_var(P1_STATE, 0);
        vm.set_var(P2_X, 760);
        vm.set_var(P2_Y, vm.get_var(FLOOR_Y));
        vm.set_var(P2_DY, 0);
        vm.set_var(P2_STATE, 0);
        vm.set_var(BALL_X, 300);
        vm.set_var(BALL_Y, 200);
        vm.set_var(BALL_DX, 0);
        vm.set_var(BALL_DY, 0);
        vm.set_var(BALL_FINE_ROT, 30);
        vm.set_var(BALL_ROTATION, 0);
        vm.set_var(BALL_FRAME, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(BALL_IS_POWER_HIT, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("ball render should use physics rotation"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(BALL_ROTATION), 3);
        assert_eq!(vm.get_var(BALL_FRAME), 0);
        assert!(has_sprite(
            &host,
            sprite_draw(package_sprites::BALL_FRAMES[3], 260, 160, 80, 80)
        ));
        assert!(!has_sprite(
            &host,
            sprite_draw(package_sprites::BALL_FRAMES[0], 260, 160, 80, 80)
        ));

        host.drawn_sprites.clear();
        host.drawn_sprite_calls.clear();
        vm.set_var(PHASE, 5);
        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 0);
        vm.set_var(BALL_X, 300);
        vm.set_var(BALL_Y, 200);
        vm.set_var(BALL_DX, 0);
        vm.set_var(BALL_DY, 0);
        vm.set_var(BALL_FINE_ROT, 120);
        vm.set_var(BALL_ROTATION, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(BALL_IS_POWER_HIT, 0);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("ball render should clamp out-of-range physics rotation"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(BALL_ROTATION), 7);
        assert!(has_sprite(
            &host,
            sprite_draw(package_sprites::BALL_FRAMES[5], 260, 160, 80, 80)
        ));
    }

    #[test]
    fn generated_pikachu_script_emits_menu_selection_and_confirm_sfx() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();
        let ui_pi_sfx = ui_sfx_event("UI_SOUND_PI");
        let ui_pikachu_sfx = ui_sfx_event("UI_SOUND_PIKACHU");

        for _ in 0..(package_timing::INTRO_TO_MENU_FRAME + 2) {
            assert_eq!(
                vm.run_until_yield(&mut host, 600_000)
                    .expect("script should reach menu phase"),
                Step::Yielded
            );
        }
        assert_eq!(vm.get_var(PHASE), 1);
        vm.set_var(FRAME_COUNTER, package_timing::MENU_OPENING_END_FRAME - 1);
        vm.set_var(MENU_SELECTION, 0);
        vm.set_var(NO_INPUT_COUNTER, 0);
        host.keys_down.push(4);
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("last menu opening frame should ignore direction input"),
            Step::Yielded
        );
        host.keys_down.clear();
        assert_eq!(
            vm.get_var(FRAME_COUNTER),
            package_timing::MENU_OPENING_END_FRAME
        );
        assert_eq!(vm.get_var(MENU_SELECTION), 0);
        assert_eq!(vm.get_var(NO_INPUT_COUNTER), 0);

        vm.set_var(FRAME_COUNTER, package_timing::MENU_OPENING_END_FRAME + 1);
        vm.set_var(MENU_SELECTION, 0);

        host.played_sounds.clear();
        host.sound_events.clear();
        host.keys_down.push(4);
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("menu down should yield"),
            Step::Yielded
        );
        host.keys_down.clear();
        assert_eq!(vm.get_var(MENU_SELECTION), 1);
        assert!(host.played_sounds.contains(&ui_pi_sfx.sound_id));
        assert!(host.sound_events.contains(&sfx_event_for_fixed_side(
            ui_pi_sfx,
            package_assets::SFX_STEREO_MODE
        )));

        host.played_sounds.clear();
        host.sound_events.clear();
        host.keys_down.push(4);
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("held menu down should yield"),
            Step::Yielded
        );
        host.keys_down.clear();
        assert_eq!(vm.get_var(MENU_SELECTION), 1);
        assert!(!host.played_sounds.contains(&ui_pi_sfx.sound_id));
        assert!(!host
            .sound_events
            .iter()
            .any(|event| event[0] == ui_pi_sfx.sound_id));

        host.played_sounds.clear();
        host.sound_events.clear();
        host.keys_pressed.push(5);
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("menu confirm should yield"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(PHASE), 2);
        assert!(host.played_sounds.contains(&ui_pikachu_sfx.sound_id));
        assert!(host.sound_events.contains(&sfx_event_for_fixed_side(
            ui_pikachu_sfx,
            package_assets::SFX_STEREO_MODE
        )));
    }

    #[test]
    fn generated_pikachu_script_selects_all_original_menu_modes() {
        let source = include_str!("../scripts/pikachu.umm");
        let ui_pikachu_sfx = ui_sfx_event("UI_SOUND_PIKACHU");

        for (selection, pressed_key, expected_p1_computer, expected_p2_computer) in
            [(0, 5, 0, 1), (0, 10, 1, 0), (1, 5, 0, 0), (1, 10, 0, 0)]
        {
            let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
            let mut host = FakeHost::default();

            assert_eq!(
                vm.run_until_yield(&mut host, 600_000)
                    .expect("script should initialize before forced menu mode"),
                Step::Yielded
            );

            vm.set_var(PHASE, 1);
            vm.set_var(FRAME_COUNTER, package_timing::MENU_OPENING_END_FRAME + 1);
            vm.set_var(MENU_SELECTION, selection);
            vm.set_var(NO_INPUT_COUNTER, 0);
            host.keys_pressed.push(pressed_key);

            assert_eq!(
                vm.run_until_yield(&mut host, 600_000)
                    .expect("menu mode selection should yield"),
                Step::Yielded
            );

            assert_eq!(vm.get_var(PHASE), 2);
            assert_eq!(vm.get_var(P1_COMPUTER), expected_p1_computer);
            assert_eq!(vm.get_var(P2_COMPUTER), expected_p2_computer);
            assert_eq!(vm.get_var(NO_INPUT_COUNTER), 0);
            assert!(host.played_sounds.contains(&ui_pikachu_sfx.sound_id));
            assert!(host.sound_events.contains(&sfx_event_for_fixed_side(
                ui_pikachu_sfx,
                package_assets::SFX_STEREO_MODE
            )));
        }
    }

    #[test]
    fn generated_pikachu_script_draws_phase_messages_on_playfield() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("script should reach first frame"),
            Step::Yielded
        );

        host.record_sprites = true;

        vm.set_var(PHASE, 4);
        vm.set_var(FRAME_COUNTER, package_timing::MESSAGE_GROW_FRAMES / 2 - 1);
        host.drawn_sprites.clear();
        host.alpha_rects.clear();
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("game start phase should render"),
            Step::Yielded
        );
        let game_start_source = render_values::<4>(package_render::GAME_START_MESSAGE_SOURCE);
        assert!(has_sprite(
            &host,
            sprite_draw(game_start_source, 336, 148, 192, 48)
        ));
        let [score1_x, score1_y] = render_values::<2>(package_render::SCORE1_ORIGIN);
        let score_index = sprite_index(&host, [204, 124, 32, 32, score1_x, score1_y, 64, 64])
            .expect("score should be drawn");
        let [shadow_sx, shadow_sy, shadow_sw, shadow_sh, shadow_y, shadow_dw, shadow_dh] =
            render_values::<7>(package_render::SHADOW_SPRITE);
        let shadow_index = sprite_index(
            &host,
            [
                shadow_sx, shadow_sy, shadow_sw, shadow_sh, 40, shadow_y, shadow_dw, shadow_dh,
            ],
        )
        .expect("playfield shadow should be drawn");
        assert!(score_index < shadow_index);
        let [wave_sx, wave_sy, wave_sw, wave_sh, _wave_dw, _wave_dh] =
            render_values::<6>(package_render::WAVE_SPRITE);
        assert_eq!(
            host.drawn_sprites
                .iter()
                .filter(|sprite| sprite[0..4] == [wave_sx, wave_sy, wave_sw, wave_sh])
                .count(),
            27
        );
        assert!(host.alpha_rects.is_empty());

        vm.set_var(PHASE, 7);
        vm.set_var(FRAME_COUNTER, package_timing::READY_BLINK_DIVISOR);
        host.drawn_sprites.clear();
        host.alpha_rects.clear();
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("ready phase should render"),
            Step::Yielded
        );
        assert!(has_sprite(
            &host,
            render_values::<8>(package_render::READY_MESSAGE)
        ));
        let [window_width, window_height] = expected_window_size();
        let ready_fade_numerator = package_timing::PHASE_FADE_BEFORE_NEXT_FRAMES
            - (package_timing::READY_BLINK_DIVISOR + 1);
        assert!(host.alpha_rects.contains(&[
            0,
            0,
            window_width,
            window_height,
            7,
            fade_alpha(
                ready_fade_numerator,
                package_timing::PHASE_FADE_BEFORE_NEXT_FRAMES
            )
        ]));

        vm.set_var(PHASE, 8);
        vm.set_var(FRAME_COUNTER, package_timing::MESSAGE_GROW_FRAMES);
        host.drawn_sprites.clear();
        host.alpha_rects.clear();
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("game end phase should render"),
            Step::Yielded
        );
        assert!(has_sprite(
            &host,
            render_values::<8>(package_render::GAME_END_MESSAGE)
        ));
        assert!(host.alpha_rects.is_empty());

        vm.set_var(PHASE, 8);
        vm.set_var(FRAME_COUNTER, package_timing::GAME_END_POWER_RESTART_FRAME);
        host.keys_pressed.push(5);
        host.bgm_stops = 0;
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("game end should restart from power input after frame 70"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(PHASE), 0);
        assert_eq!(vm.get_var(FRAME_COUNTER), 0);
        assert_eq!(host.bgm_stops, 1);

        vm.set_var(PHASE, 8);
        vm.set_var(FRAME_COUNTER, package_timing::GAME_END_TIMEOUT_FRAME);
        host.bgm_stops = 0;
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("game end should restart from original timeout"),
            Step::Yielded
        );
        assert_eq!(vm.get_var(PHASE), 0);
        assert_eq!(vm.get_var(FRAME_COUNTER), 0);
        assert_eq!(host.bgm_stops, 1);

        vm.set_var(PHASE, 2);
        vm.set_var(
            FRAME_COUNTER,
            package_timing::PHASE_FADE_AFTER_MENU_FRAMES / 2 - 1,
        );
        host.drawn_sprites.clear();
        host.alpha_rects.clear();
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("after menu phase should render fade"),
            Step::Yielded
        );
        assert!(host.alpha_rects.contains(&[
            0,
            0,
            window_width,
            window_height,
            7,
            fade_alpha(
                package_timing::PHASE_FADE_AFTER_MENU_FRAMES / 2,
                package_timing::PHASE_FADE_AFTER_MENU_FRAMES
            )
        ]));

        vm.set_var(PHASE, 3);
        vm.set_var(FRAME_COUNTER, 3);
        host.alpha_rects.clear();
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("before start phase should render full fade"),
            Step::Yielded
        );
        assert!(host
            .alpha_rects
            .contains(&[0, 0, window_width, window_height, 7, 255]));

        vm.set_var(PHASE, 6);
        vm.set_var(
            FRAME_COUNTER,
            package_timing::PHASE_FADE_AFTER_ROUND_FRAMES / 4 - 1,
        );
        host.alpha_rects.clear();
        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("after round phase should render fade"),
            Step::Yielded
        );
        assert!(host.alpha_rects.contains(&[
            0,
            0,
            window_width,
            window_height,
            7,
            fade_alpha(
                package_timing::PHASE_FADE_AFTER_ROUND_FRAMES / 4 + 1,
                package_timing::PHASE_FADE_AFTER_ROUND_FRAMES
            )
        ]));
    }

    #[test]
    fn generated_pikachu_script_applies_player_collision_rng_center_fallback() {
        let source = include_str!("../scripts/pikachu.umm");
        let mut vm = Vm::parse(source).expect("generated 엄랭 script should parse");
        let mut host = FakeHost::default();

        for _ in 0..570 {
            assert_eq!(
                vm.run_until_yield(&mut host, 600_000)
                    .expect("script should reach round phase"),
                Step::Yielded
            );
        }
        assert_eq!(vm.get_var(PHASE), 5);
        let ball_power_hit_sfx = round_sfx_event("BALL_SOUND_POWER_HIT");

        vm.set_var(P1_COMPUTER, 0);
        vm.set_var(P2_COMPUTER, 0);
        for (cloud_x, cloud_vx) in [
            (72, 122),
            (73, 123),
            (74, 124),
            (128, 130),
            (132, 134),
            (136, 138),
            (140, 142),
            (144, 146),
            (148, 150),
            (152, 154),
        ] {
            vm.set_var(cloud_x, 0);
            vm.set_var(cloud_vx, 0);
        }
        vm.set_var(WAVE_VERTICAL, 10);
        vm.set_var(WAVE_VELOCITY, 0);
        set_rng_seed(&mut vm, 3);
        vm.set_var(P1_X, 200);
        vm.set_var(P1_Y, 300);
        vm.set_var(P1_DY, 0);
        vm.set_var(P1_STATE, 0);
        vm.set_var(P1_COLLIDING, 0);
        vm.set_var(P2_X, 760);
        vm.set_var(P2_Y, vm.get_var(FLOOR_Y));
        vm.set_var(P2_DY, 0);
        vm.set_var(P2_STATE, 0);

        vm.set_var(BALL_X, 200);
        vm.set_var(BALL_Y, 300);
        vm.set_var(BALL_DX, 0);
        vm.set_var(BALL_DY, 0);
        vm.set_var(BALL_EXPECTED_X, -999);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        vm.set_var(BALL_IS_POWER_HIT, 1);
        vm.set_var(ROUND_ENDED, 0);
        vm.set_var(GAME_ENDED, 0);
        vm.set_var(SLOW_MOTION_FRAMES_LEFT, 0);
        vm.set_var(SLOW_MOTION_SKIP, 0);
        host.played_sounds.clear();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("center player collision should keep yielding"),
            Step::Yielded
        );

        assert_eq!(vm.get_var(P1_COLLIDING), 1);
        assert_eq!(vm.get_var(BALL_DX), SCREEN_SCALE);
        assert_eq!(vm.get_var(BALL_DY), -30);
        assert!(vm.get_var(BALL_EXPECTED_X) > 200);
        assert_eq!(vm.get_var(BALL_IS_POWER_HIT), 0);
        assert_eq!(vm.get_var(BALL_SOUND_POWER_HIT), 0);
        assert!(!host.played_sounds.contains(&ball_power_hit_sfx.sound_id));
        assert!(!host
            .sound_events
            .iter()
            .any(|event| event[0] == ball_power_hit_sfx.sound_id));
        assert_eq!(vm.get_var(BALL_TOUCH_GROUND), 0);
        assert_eq!(vm.get_var(PHASE), 5);

        vm.set_var(P1_X, 200);
        vm.set_var(P1_Y, 300);
        vm.set_var(P1_STATE, 0);
        vm.set_var(P1_COLLIDING, 0);
        vm.set_var(BALL_X, 200 + vm.get_var(COLLISION_RADIUS));
        vm.set_var(BALL_Y, 300);
        vm.set_var(BALL_DX, 0);
        vm.set_var(BALL_DY, 0);
        vm.set_var(BALL_IS_POWER_HIT, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        host.played_sounds.clear();
        host.sound_events.clear();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("inclusive edge player collision should keep yielding"),
            Step::Yielded
        );

        assert_eq!(vm.get_var(P1_COLLIDING), 1);
        assert_eq!(
            vm.get_var(BALL_DX),
            (vm.get_var(COLLISION_RADIUS) / (3 * SCREEN_SCALE)) * SCREEN_SCALE
        );
        assert_eq!(vm.get_var(BALL_DY), -30);
        assert_eq!(vm.get_var(BALL_TOUCH_GROUND), 0);

        vm.set_var(P1_X, 220);
        vm.set_var(P1_Y, 320);
        vm.set_var(P1_STATE, 2);
        vm.set_var(P1_COLLIDING, 0);
        vm.set_var(BALL_X, 220);
        vm.set_var(BALL_Y, 320);
        vm.set_var(BALL_DX, 0);
        vm.set_var(BALL_DY, -4);
        vm.set_var(BALL_IS_POWER_HIT, 0);
        vm.set_var(BALL_TOUCH_GROUND, 0);
        host.played_sounds.clear();
        host.sound_events.clear();

        assert_eq!(
            vm.run_until_yield(&mut host, 600_000)
                .expect("power-hit player collision should keep yielding"),
            Step::Yielded
        );

        assert_eq!(vm.get_var(P1_COLLIDING), 1);
        assert_eq!(vm.get_var(BALL_IS_POWER_HIT), 1);
        assert_eq!(vm.get_var(BALL_SOUND_POWER_HIT), 0);
        assert!(host.played_sounds.contains(&ball_power_hit_sfx.sound_id));
        assert!(host.sound_events.contains(&sfx_event_for_ball_side(
            ball_power_hit_sfx,
            package_assets::SFX_STEREO_MODE,
            -1
        )));
    }
}
