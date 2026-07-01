#!/usr/bin/env python3
from __future__ import annotations

import os
import re


LABEL_REF = re.compile(r"@@([A-Za-z0-9_]+)@@")
MANIFEST_PATH = "umlang-package.txt"
SYSCALLS_PATH = "umlang-syscalls.txt"
KEYCODES_PATH = "umlang-keycodes.txt"
KEYMAP_PATH = "umlang-keymap.txt"
ASSETS_PATH = "umlang-assets.txt"
PALETTE_PATH = "umlang-palette.txt"
SETTINGS_PATH = "umlang-settings.txt"
VARS_PATH = "umlang-vars.txt"
GAME_PATH = "umlang-game.txt"
PLAYER_PATH = "umlang-player.txt"
SPRITES_PATH = "umlang-sprites.txt"
RNG_PATH = "umlang-rng.txt"
RENDER_PATH = "umlang-render.txt"
ANIMATION_PATH = "umlang-animation.txt"
SFX_PATH = "umlang-sfx.txt"
TIMING_PATH = "umlang-timing.txt"
MENU_PATH = "umlang-menu.txt"
SCRIPT_PARTS_DIR = "scripts/pikachu_parts"
SCRIPT_CHUNK_TARGET_BYTES = 24 * 1024 * 1024


def manifest_value(key: str, default: str) -> str:
    try:
        with open(MANIFEST_PATH, encoding="utf-8") as manifest:
            for raw_line in manifest:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                candidate_key, value = line.split("=", 1)
                if candidate_key.strip() == key and value.strip():
                    return value.strip()
    except FileNotFoundError:
        pass
    return default


def manifest_int_value(key: str, default: int) -> int:
    try:
        value = int(manifest_value(key, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def read_syscalls() -> dict[str, int]:
    syscalls: dict[str, int] = {}
    with open(SYSCALLS_PATH, encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            name, value = line.split("=", 1)
            syscalls[name.strip()] = int(value.strip())
    return syscalls


def read_keycodes() -> dict[str, int]:
    keycodes: dict[str, int] = {}
    with open(KEYCODES_PATH, encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            name, value = line.split("=", 1)
            keycodes[name.strip()] = int(value.strip())
    return keycodes


def read_key_bindings(keycodes: dict[str, int]) -> list[tuple[str, int, int]]:
    bindings: list[tuple[str, int, int]] = []
    action_names: set[str] = set()
    action_ids: set[int] = set()
    with open(KEYMAP_PATH, encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            action_name, value = line.split("=", 1)
            action_name = action_name.strip()
            if not re.fullmatch(r"ACTION_[A-Z0-9_]+", action_name):
                raise RuntimeError(f"invalid action name: {action_name}")
            if action_name in action_names:
                raise RuntimeError(f"duplicate action name: {action_name}")
            action_names.add(action_name)
            fields = [field.strip() for field in value.split(",")]
            if len(fields) != 2:
                raise RuntimeError(f"invalid keymap line for {action_name}: {line}")
            action_id = int(fields[0])
            if action_id in action_ids:
                raise RuntimeError(f"duplicate action id: {action_id}")
            action_ids.add(action_id)
            key_name = fields[1]
            bindings.append((action_name, action_id, keycodes[key_name]))
    return bindings


def read_asset_config() -> dict[str, str]:
    config: dict[str, str] = {}
    with open(ASSETS_PATH, encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            key, value = line.split("=", 1)
            config[key.strip()] = value.strip()
    return config


def asset_config_value(key: str, default: str) -> str:
    value = ASSET_CONFIG.get(key, default)
    return value if value else default


def asset_config_int(key: str, default: int) -> int:
    try:
        return int(asset_config_value(key, str(default)))
    except ValueError:
        return default


def asset_config_int_list(key: str, default: list[int]) -> list[int]:
    value = asset_config_value(key, ",".join(str(item) for item in default))
    try:
        parsed = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError:
        return default
    return parsed or default


def read_palette() -> list[tuple[int, int, int, int, int]]:
    colors: list[tuple[int, int, int, int, int]] = []
    with open(PALETTE_PATH, encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            color_id_text, rgba_text = line.split("=", 1)
            rgba = [int(item.strip()) for item in rgba_text.split(",") if item.strip()]
            if len(rgba) != 4:
                raise RuntimeError(f"invalid palette rgba line: {line}")
            colors.append((int(color_id_text.strip()), rgba[0], rgba[1], rgba[2], rgba[3]))
    colors.sort(key=lambda color: color[0])
    return colors


def read_runtime_settings() -> dict[str, tuple[int, int, list[int]]]:
    settings: dict[str, tuple[int, int, list[int]]] = {}
    with open(SETTINGS_PATH, encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            name, value = line.split("=", 1)
            fields = [field.strip() for field in value.split(",", 2)]
            if len(fields) != 3:
                raise RuntimeError(f"invalid setting line: {line}")
            key = int(fields[0])
            default = int(fields[1])
            allowed = [int(item.strip()) for item in fields[2].split("|") if item.strip()]
            if default not in allowed:
                raise RuntimeError(f"setting default must be allowed: {line}")
            settings[name.strip()] = (key, default, allowed)
    return settings


def runtime_setting(name: str, fallback: tuple[int, int, list[int]]) -> tuple[int, int, list[int]]:
    return RUNTIME_SETTINGS.get(name, fallback)


def read_vars() -> dict[str, int]:
    variables: dict[str, int] = {}
    slots: set[int] = set()
    with open(VARS_PATH, encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
                raise RuntimeError(f"invalid variable slot name: {name}")
            slot = int(value.strip())
            if slot <= 1:
                raise RuntimeError(f"variable slot {name} must not overlap syscall argument slots")
            if name in variables:
                raise RuntimeError(f"duplicate variable slot name: {name}")
            if slot in slots:
                raise RuntimeError(f"duplicate variable slot: {slot}")
            variables[name] = slot
            slots.add(slot)
    return variables


def read_game_constants() -> dict[str, int]:
    constants: dict[str, int] = {}
    with open(GAME_PATH, encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
                raise RuntimeError(f"invalid game constant name: {name}")
            if name in constants:
                raise RuntimeError(f"duplicate game constant name: {name}")
            constants[name] = int(value.strip())
    return constants


def read_player_config() -> dict[str, int]:
    config: dict[str, int] = {}
    with open(PLAYER_PATH, encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
                raise RuntimeError(f"invalid player key: {key}")
            if key in config:
                raise RuntimeError(f"duplicate player key: {key}")
            config[key] = int(value.strip())
    return config


def read_sprite_frames() -> dict[str, list[tuple[int, int, int, int]]]:
    frame_maps: dict[str, dict[int, tuple[int, int, int, int]]] = {
        "PLAYER_FRAME": {},
        "BALL_FRAME": {},
    }
    with open(SPRITES_PATH, encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
                raise RuntimeError(f"invalid sprite frame name: {name}")
            values = [int(item.strip()) for item in value.split(",") if item.strip()]
            if len(values) != 4:
                raise RuntimeError(f"sprite frame {name} must have exactly 4 values")

            matched = False
            for prefix, frames in frame_maps.items():
                full_prefix = f"{prefix}_"
                if not name.startswith(full_prefix):
                    continue
                index = int(name[len(full_prefix) :])
                if index in frames:
                    raise RuntimeError(f"duplicate sprite frame index: {name}")
                frames[index] = (values[0], values[1], values[2], values[3])
                matched = True
                break
            if not matched:
                raise RuntimeError(f"unknown sprite frame name: {name}")

    result: dict[str, list[tuple[int, int, int, int]]] = {}
    for prefix, frames in frame_maps.items():
        if not frames:
            raise RuntimeError(f"{prefix} must define at least one frame")
        result[prefix] = []
        for expected, index in enumerate(sorted(frames)):
            if index != expected:
                raise RuntimeError(f"{prefix} indices must be contiguous from 0; missing {expected}")
            result[prefix].append(frames[index])
    return result


def read_rng_config() -> dict[str, list[int]]:
    config: dict[str, list[int]] = {}
    with open(RNG_PATH, encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            values = [int(item.strip()) for item in value.split(",") if item.strip()]
            if len(values) != 8:
                raise RuntimeError(f"{key} must contain exactly 8 bytes")
            if any(item < 0 or item > 255 for item in values):
                raise RuntimeError(f"{key} values must be bytes")
            config[key] = values
    for key in ("seed_bytes", "multiplier_bytes"):
        if key not in config:
            raise RuntimeError(f"missing rng config key: {key}")
    return config


def read_render_config() -> dict[str, list[int]]:
    config: dict[str, list[int]] = {}
    with open(RENDER_PATH, encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
                raise RuntimeError(f"invalid render key: {key}")
            if key in config:
                raise RuntimeError(f"duplicate render key: {key}")
            values = [int(item.strip()) for item in value.split(",") if item.strip()]
            if not values:
                raise RuntimeError(f"render key {key} must not be empty")
            config[key] = values
    return config


def read_timing_config() -> dict[str, int]:
    config: dict[str, int] = {}
    with open(TIMING_PATH, encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
                raise RuntimeError(f"invalid timing key: {key}")
            if key in config:
                raise RuntimeError(f"duplicate timing key: {key}")
            parsed = int(value.strip())
            if parsed < 0:
                raise RuntimeError(f"timing key {key} must be non-negative")
            config[key] = parsed
    return config


def read_menu_config() -> dict[str, list[int]]:
    config: dict[str, list[int]] = {}
    with open(MENU_PATH, encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
                raise RuntimeError(f"invalid menu key: {key}")
            if key in config:
                raise RuntimeError(f"duplicate menu key: {key}")
            values = [int(item.strip()) for item in value.split(",") if item.strip()]
            if not values:
                raise RuntimeError(f"menu key {key} must not be empty")
            config[key] = values
    return config


def read_animation_config() -> tuple[dict[int, tuple[int, int]], dict[int, list[int]]]:
    anim_rules: dict[int, tuple[int, int]] = {}
    draw_states: dict[int, list[int]] = {}
    with open(ANIMATION_PATH, encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            values = [int(item.strip()) for item in value.split(",") if item.strip()]
            if key.startswith("player_anim_state_"):
                state = int(key.removeprefix("player_anim_state_"))
                if len(values) != 2:
                    raise RuntimeError(f"{key} must be frame_counter_divisor,frame_modulo")
                if values[0] <= 0 or values[1] <= 0:
                    raise RuntimeError(f"{key} values must be positive")
                if state in anim_rules:
                    raise RuntimeError(f"duplicate player animation state: {state}")
                anim_rules[state] = (values[0], values[1])
            elif key.startswith("player_draw_state_"):
                state = int(key.removeprefix("player_draw_state_"))
                if not values:
                    raise RuntimeError(f"{key} must list at least one sprite index")
                if any(value < 0 for value in values):
                    raise RuntimeError(f"{key} sprite indices must be non-negative")
                if state in draw_states:
                    raise RuntimeError(f"duplicate player draw state: {state}")
                draw_states[state] = values
            else:
                raise RuntimeError(f"unknown animation key: {key}")
    if not anim_rules:
        raise RuntimeError("animation config must define player animation states")
    if not draw_states:
        raise RuntimeError("animation config must define player draw states")
    return anim_rules, draw_states


def read_sfx_config() -> tuple[
    list[tuple[str, str, int, int | str]],
    list[tuple[str, str, int, int]],
    tuple[int, int],
]:
    round_events: list[tuple[str, str, int, int | str]] = []
    ui_events: list[tuple[str, str, int, int]] = []
    jump_sound: tuple[int, int] | None = None
    seen_flags: set[str] = set()

    def parse_sound_id(key: str, value: str) -> int:
        sound_id = int(value)
        if sound_id <= 0 or sound_id > len(SFX_WAVES):
            raise RuntimeError(f"{key} sound id must be within the SFX wave bank")
        return sound_id

    def parse_fixed_side(key: str, value: str) -> int:
        side = int(value)
        if side not in (-1, 0, 1):
            raise RuntimeError(f"{key} fixed side must be -1, 0, or 1")
        return side

    def parse_event(key: str, value: str) -> tuple[str, str, int, int | str]:
        fields = [field.strip() for field in value.split(",")]
        if len(fields) != 3:
            raise RuntimeError(f"{key} must be flag_variable,sound_id,side")
        flag_name = fields[0]
        if flag_name not in VARS:
            raise RuntimeError(f"{key} references unknown variable flag: {flag_name}")
        if flag_name in seen_flags:
            raise RuntimeError(f"duplicate SFX flag: {flag_name}")
        seen_flags.add(flag_name)
        sound_id = parse_sound_id(key, fields[1])
        side: int | str
        if fields[2] == "ball_x":
            side = "ball_x"
        else:
            side = parse_fixed_side(key, fields[2])
        return key, flag_name, sound_id, side

    with open(SFX_PATH, encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key.startswith("round_event_"):
                round_events.append(parse_event(key, value))
            elif key.startswith("ui_event_"):
                event_key, flag_name, sound_id, side = parse_event(key, value)
                if side == "ball_x":
                    raise RuntimeError(f"{event_key} cannot use ball_x side")
                ui_events.append((event_key, flag_name, sound_id, side))
            elif key == "jump_sound":
                fields = [field.strip() for field in value.split(",")]
                if len(fields) != 2:
                    raise RuntimeError("jump_sound must be sound_id,side")
                if jump_sound is not None:
                    raise RuntimeError("duplicate jump_sound")
                jump_sound = (
                    parse_sound_id(key, fields[0]),
                    parse_fixed_side(key, fields[1]),
                )
            else:
                raise RuntimeError(f"unknown sfx key: {key}")
    if not round_events:
        raise RuntimeError("sfx config must define round events")
    if not ui_events:
        raise RuntimeError("sfx config must define UI events")
    if jump_sound is None:
        raise RuntimeError("sfx config must define jump_sound")
    return round_events, ui_events, jump_sound


SYSCALLS = read_syscalls()
KEYCODES = read_keycodes()
KEY_BINDINGS = read_key_bindings(KEYCODES)
ASSET_CONFIG = read_asset_config()
PALETTE = read_palette()
RUNTIME_SETTINGS = read_runtime_settings()
VARS = read_vars()
GAME_CONSTANTS = read_game_constants()
PLAYER_CONFIG = read_player_config()
SPRITE_FRAMES = read_sprite_frames()
RNG_CONFIG = read_rng_config()
RENDER_CONFIG = read_render_config()
TIMING_CONFIG = read_timing_config()
MENU_CONFIG = read_menu_config()
PLAYER_ANIM_RULES, PLAYER_DRAW_STATES = read_animation_config()
MAIN_SCRIPT_PATH = manifest_value("main", "scripts/pikachu.umm")
ASSET_ROOT = manifest_value("asset_root", "assets")


def asset_path(relative_path: str) -> str:
    return f"{ASSET_ROOT.rstrip('/')}/{relative_path.lstrip('/')}"


def syscall(name: str) -> int:
    return SYSCALLS[name]


def num(value: int) -> str:
    if value > 0:
        return "." * value
    if value < 0:
        return "," * (-value)
    return ".,"


def var(index: int) -> str:
    return "어" * index


def assign(index: int, expr: str) -> str:
    return "어" * (index - 1) + "엄" + expr


def asset_id(path: str) -> int:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    value = 0x811C9DC5
    for byte in normalized.encode("utf-8"):
        value ^= byte
        value = (value * 16_777_619) & 0xFFFF_FFFF
    return (value % 10_000) + 1


class Program:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.labels: dict[str, int] = {}

    def label(self, name: str) -> None:
        if name in self.labels:
            raise RuntimeError(f"duplicate label: {name}")
        self.labels[name] = len(self.lines) + 2

    def emit(self, line: str) -> None:
        self.lines.append(line)

    def goto(self, name: str) -> str:
        return f"준@@{name}@@"

    def if_zero_goto(self, expr: str, name: str) -> None:
        self.emit(f"동탄{expr}?{self.goto(name)}")

    def call_expr(self, opcode: int, *args: str) -> None:
        self.emit(assign(1, num(opcode)))
        for i, arg in enumerate(args, start=2):
            self.emit(assign(i, arg))
        self.emit("식어!")

    def call(self, opcode: int, *args: int) -> None:
        self.call_expr(opcode, *(num(arg) for arg in args))

    def render_body_lines(self) -> list[str]:
        body: list[str] = []

        def replace_label(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in self.labels:
                raise RuntimeError(f"unresolved label: {name}")
            return num(self.labels[name])

        for line in self.lines:
            line = LABEL_REF.sub(replace_label, line)
            if "@@" in line:
                raise RuntimeError(f"unresolved label in {line}")
            body.append(line)
        return body

    def render(self) -> str:
        body = self.render_body_lines()
        return "\n".join(["어떻게", *body, "이 사람이름이냐ㅋㅋ", ""])


def write_chunked_script(program: Program, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    os.makedirs(SCRIPT_PARTS_DIR, exist_ok=True)

    for entry in os.scandir(SCRIPT_PARTS_DIR):
        if entry.is_file() and entry.name.endswith(".umm"):
            os.remove(entry.path)

    part_paths: list[str] = []
    chunk_lines: list[str] = []
    chunk_bytes = 0

    def flush_chunk() -> None:
        nonlocal chunk_lines, chunk_bytes
        if not chunk_lines:
            return
        part_name = f"pikachu_{len(part_paths):04d}.umm"
        part_path = os.path.join(SCRIPT_PARTS_DIR, part_name)
        tmp_part_path = f"{part_path}.tmp"
        with open(tmp_part_path, "w", encoding="utf-8") as part:
            part.write("\n".join(chunk_lines))
            part.write("\n")
        os.replace(tmp_part_path, part_path)
        part_paths.append(part_path.replace("\\", "/"))
        chunk_lines = []
        chunk_bytes = 0

    for line in program.render_body_lines():
        line_bytes = len(line.encode("utf-8")) + 1
        if chunk_lines and chunk_bytes + line_bytes > SCRIPT_CHUNK_TARGET_BYTES:
            flush_chunk()
        chunk_lines.append(line)
        chunk_bytes += line_bytes
    flush_chunk()

    tmp_path = f"{output_path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as entry:
            entry.write("어떻게\n")
            for part_path in part_paths:
                entry.write(f"가져와 {part_path}\n")
            entry.write("이 사람이름이냐ㅋㅋ\n")
        os.replace(tmp_path, output_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


# VM variable slots used by the script.
globals().update(VARS)

# Game constants and phase ids used by the script.
globals().update(GAME_CONSTANTS)

# Input action ids declared by the package keymap.
globals().update({action_name: action_id for action_name, action_id, _ in KEY_BINDINGS})


SYS_CLEAR = syscall("SYS_CLEAR")
SYS_DRAW_RECT = syscall("SYS_DRAW_RECT")
SYS_DRAW_CIRCLE = syscall("SYS_DRAW_CIRCLE")
SYS_KEY_DOWN = syscall("SYS_KEY_DOWN")
SYS_ADD = syscall("SYS_ADD")
SYS_SUB = syscall("SYS_SUB")
SYS_ADD_CONST = syscall("SYS_ADD_CONST")
SYS_CLAMP = syscall("SYS_CLAMP")
SYS_WAIT_FRAME = syscall("SYS_WAIT_FRAME")
SYS_DRAW_NUMBER = syscall("SYS_DRAW_NUMBER")
SYS_GT = syscall("SYS_GT")
SYS_LT = syscall("SYS_LT")
SYS_ABS = syscall("SYS_ABS")
SYS_MUL = syscall("SYS_MUL")
SYS_EQ = syscall("SYS_EQ")
SYS_KEY_PRESSED = syscall("SYS_KEY_PRESSED")
SYS_DIV = syscall("SYS_DIV")
SYS_MOD = syscall("SYS_MOD")
SYS_DRAW_RECT_ALPHA = syscall("SYS_DRAW_RECT_ALPHA")
SYS_SET_TEXTURE_FILTER = syscall("SYS_SET_TEXTURE_FILTER")
SYS_SET_TARGET_FPS = syscall("SYS_SET_TARGET_FPS")
SYS_LOAD_SETTING = syscall("SYS_LOAD_SETTING")
SYS_SAVE_SETTING = syscall("SYS_SAVE_SETTING")
SYS_DEFINE_COLOR = syscall("SYS_DEFINE_COLOR")
SYS_CONFIGURE_WINDOW = syscall("SYS_CONFIGURE_WINDOW")
SYS_CONFIGURE_SETTINGS = syscall("SYS_CONFIGURE_SETTINGS")
SYS_DEFINE_TEXTURE = syscall("SYS_DEFINE_TEXTURE")
SYS_DRAW_TEXTURE = syscall("SYS_DRAW_TEXTURE")
SYS_DRAW_TEXTURE_ALPHA = syscall("SYS_DRAW_TEXTURE_ALPHA")
SYS_DEFINE_AUDIO = syscall("SYS_DEFINE_AUDIO")
SYS_PLAY_AUDIO = syscall("SYS_PLAY_AUDIO")
SYS_STOP_AUDIO = syscall("SYS_STOP_AUDIO")


SETTING_WINNING_SCORE, DEFAULT_WINNING_SCORE, WINNING_SCORE_VALUES = runtime_setting(
    "winning_score", (1, 15, [5, 10, 15])
)
SETTING_PRACTICE_MODE, DEFAULT_PRACTICE_MODE, PRACTICE_MODE_VALUES = runtime_setting(
    "practice_mode", (2, 0, [0, 1])
)
SETTING_BGM_ON, DEFAULT_BGM_ON, BGM_ON_VALUES = runtime_setting("bgm_on", (3, 1, [0, 1]))
SETTING_SFX_MODE, DEFAULT_SFX_MODE, SFX_MODE_VALUES = runtime_setting("sfx_mode", (4, 2, [0, 1, 2]))
SETTING_SOFT_GRAPHICS, DEFAULT_SOFT_GRAPHICS, SOFT_GRAPHICS_VALUES = runtime_setting(
    "soft_graphics", (5, 0, [0, 1])
)
SETTING_TARGET_FPS, DEFAULT_TARGET_FPS, TARGET_FPS_VALUES = runtime_setting(
    "target_fps", (6, 25, [20, 25, 30])
)
if len(WINNING_SCORE_VALUES) != 3:
    raise RuntimeError("winning_score must have exactly 3 hotkey values")
if len(TARGET_FPS_VALUES) != 3:
    raise RuntimeError("target_fps must have exactly 3 hotkey values")
WINNING_SCORE_1, WINNING_SCORE_2, WINNING_SCORE_3 = WINNING_SCORE_VALUES
TARGET_FPS_SLOW, TARGET_FPS_NORMAL, TARGET_FPS_FAST = TARGET_FPS_VALUES
SFX_MODE_OFF = min(SFX_MODE_VALUES)
SFX_MODE_MONO = sorted(SFX_MODE_VALUES)[1]
SFX_MODE_STEREO = max(SFX_MODE_VALUES)

WINDOW_WIDTH = manifest_int_value("window_width", 864)
WINDOW_HEIGHT = manifest_int_value("window_height", 608)

SPRITE_TEXTURE_PATH = asset_config_value("sprite_texture", "sprite_sheet.png")
SPRITE_SHEET_ASSET = asset_id(asset_path(SPRITE_TEXTURE_PATH))
SPRITE_TEXTURE_SLOT = asset_config_int("sprite_texture_slot", 1)
BGM_AUDIO_PATH = asset_config_value("bgm_audio", "bgm.wav")
BGM_ASSET = asset_id(asset_path(BGM_AUDIO_PATH))
BGM_AUDIO_SLOT = asset_config_int("bgm_audio_slot", 1)
SETTINGS_PROFILE = asset_id(asset_config_value("settings_profile", "pikachu-volleyball"))
SFX_BASE_SLOT = asset_config_int("sfx_base_slot", 1000)
SFX_SOUND_STRIDE = asset_config_int("sfx_sound_stride", 100)
SFX_MODE_STRIDE = asset_config_int("sfx_mode_stride", 10)
SFX_MONO_MODE = asset_config_int("sfx_mono_mode", 1)
SFX_STEREO_MODE = asset_config_int("sfx_stereo_mode", 2)
SFX_LEFT_SIDE_CODE = asset_config_int("sfx_left_side_code", 1)
SFX_CENTER_SIDE_CODE = asset_config_int("sfx_center_side_code", 2)
SFX_RIGHT_SIDE_CODE = asset_config_int("sfx_right_side_code", 3)
SFX_WAVES = asset_config_int_list("sfx_waves", list(range(140, 147)))
SFX_ROUND_EVENTS, SFX_UI_EVENTS, JUMP_SFX = read_sfx_config()


def sfx_audio_slot(sound_id: int, mode: int, side: int) -> int:
    side_code = {
        -1: SFX_LEFT_SIDE_CODE,
        0: SFX_CENTER_SIDE_CODE,
        1: SFX_RIGHT_SIDE_CODE,
    }[side]
    return SFX_BASE_SLOT + sound_id * SFX_SOUND_STRIDE + mode * SFX_MODE_STRIDE + side_code


SFX_BANK = [
    (
        idx,
        asset_id(asset_path(f"sfx/WAVE{wave}_1.wav")),
        asset_id(asset_path(f"sfx/stereo/WAVE{wave}_1_left.wav")),
        asset_id(asset_path(f"sfx/stereo/WAVE{wave}_1_right.wav")),
    )
    for idx, wave in enumerate(SFX_WAVES, start=1)
]
SFX_AUDIO_BANK = [
    slot
    for sound_id, center_asset, left_asset, right_asset in SFX_BANK
    for slot in (
        (sfx_audio_slot(sound_id, SFX_MONO_MODE, -1), center_asset),
        (sfx_audio_slot(sound_id, SFX_MONO_MODE, 0), center_asset),
        (sfx_audio_slot(sound_id, SFX_MONO_MODE, 1), center_asset),
        (sfx_audio_slot(sound_id, SFX_STEREO_MODE, -1), left_asset),
        (sfx_audio_slot(sound_id, SFX_STEREO_MODE, 0), center_asset),
        (sfx_audio_slot(sound_id, SFX_STEREO_MODE, 1), right_asset),
    )
]


def sfx_event_flag_vars(events: list[tuple[str, str, int, int | str]]) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()
    for _, flag_name, _, _ in events:
        flag_var = VARS[flag_name]
        if flag_var not in seen:
            result.append(flag_var)
            seen.add(flag_var)
    return result


PLAYER_SFX_FLAG_VARS = [
    VARS[flag_name]
    for _, flag_name, _, _ in SFX_ROUND_EVENTS
    if flag_name.startswith(("P1_SOUND_", "P2_SOUND_"))
]
BALL_SFX_FLAG_VARS = [
    VARS[flag_name]
    for _, flag_name, _, _ in SFX_ROUND_EVENTS
    if flag_name.startswith("BALL_SOUND_")
]
UI_SFX_FLAG_VARS = sfx_event_flag_vars(SFX_UI_EVENTS)
ALL_SFX_FLAG_VARS = sfx_event_flag_vars(SFX_ROUND_EVENTS) + UI_SFX_FLAG_VARS
ACTION_KEY_CODES = {action: key_code for _, action, key_code in KEY_BINDINGS}


def timing_value(key: str) -> int:
    try:
        return TIMING_CONFIG[key]
    except KeyError as err:
        raise RuntimeError(f"missing timing key: {key}") from err


def player_value(key: str) -> int:
    try:
        return PLAYER_CONFIG[key]
    except KeyError as err:
        raise RuntimeError(f"missing player key: {key}") from err


def menu_values(key: str, expected_len: int | None = None) -> list[int]:
    try:
        values = MENU_CONFIG[key]
    except KeyError as err:
        raise RuntimeError(f"missing menu key: {key}") from err
    if expected_len is not None and len(values) != expected_len:
        raise RuntimeError(f"menu key {key} must have {expected_len} values")
    return values


def menu_value(key: str) -> int:
    return menu_values(key, 1)[0]


INTRO_FADE_IN_END = timing_value("intro_fade_in_end")
INTRO_FADE_OUT_START = timing_value("intro_fade_out_start")
INTRO_FADE_DENOMINATOR = timing_value("intro_fade_denominator")
INTRO_TO_MENU_FRAME = timing_value("intro_to_menu_frame")
MENU_FULL_ALPHA_FRAME = timing_value("menu_full_alpha_frame")
MENU_FADE_START_FRAME = timing_value("menu_fade_start_frame")
MENU_FADE_DENOMINATOR = timing_value("menu_fade_denominator")
MENU_OPENING_END_FRAME = timing_value("menu_opening_end_frame")
MENU_POKEMON_LABEL_FRAME = timing_value("menu_pokemon_label_frame")
MENU_WITH_WHO_FRAME = timing_value("menu_with_who_frame")
MENU_AI_DEMO_NO_INPUT_FRAMES = timing_value("menu_ai_demo_no_input_frames")
MESSAGE_GROW_FRAMES = timing_value("message_grow_frames")
READY_BLINK_DIVISOR = timing_value("ready_blink_divisor")
READY_BLINK_MODULO = timing_value("ready_blink_modulo")
PHASE_FADE_AFTER_MENU_FRAMES = timing_value("phase_fade_after_menu_frames")
PHASE_FADE_START_NEW_GAME_FRAMES = timing_value("phase_fade_start_new_game_frames")
PHASE_FADE_AFTER_ROUND_FRAMES = timing_value("phase_fade_after_round_frames")
PHASE_FADE_BEFORE_NEXT_FRAMES = timing_value("phase_fade_before_next_frames")
PHASE_AFTER_MENU_SELECTION_END_FRAME = timing_value("phase_after_menu_selection_end_frame")
PHASE_BEFORE_START_NEW_GAME_END_FRAME = timing_value("phase_before_start_new_game_end_frame")
PHASE_START_NEW_GAME_END_FRAME = timing_value("phase_start_new_game_end_frame")
PHASE_AFTER_END_ROUND_END_FRAME = timing_value("phase_after_end_round_end_frame")
PHASE_BEFORE_START_NEXT_ROUND_END_FRAME = timing_value(
    "phase_before_start_next_round_end_frame"
)
GAME_END_POWER_RESTART_FRAME = timing_value("game_end_power_restart_frame")
GAME_END_TIMEOUT_FRAME = timing_value("game_end_timeout_frame")
PLAYER_STATE_NORMAL = player_value("state_normal")
PLAYER_STATE_JUMP = player_value("state_jump")
PLAYER_STATE_POWER_HIT = player_value("state_power_hit")
PLAYER_STATE_DIVING = player_value("state_diving")
PLAYER_STATE_LYING = player_value("state_lying")
PLAYER_STATE_WIN = player_value("state_win")
PLAYER_STATE_LOSE = player_value("state_lose")
PLAYER_LIE_TIMER_INITIAL = player_value("lie_timer_initial")
PLAYER_LIE_TIMER_STAND_THRESHOLD = player_value("lie_timer_stand_threshold")
PLAYER_JUMP_FRAME_MODULO = player_value("jump_frame_modulo")
PLAYER_POWER_HIT_START_DELAY = player_value("power_hit_start_delay")
PLAYER_POWER_HIT_DELAY_THRESHOLD = player_value("power_hit_delay_threshold")
PLAYER_POWER_HIT_LAST_FRAME = player_value("power_hit_last_frame")
PLAYER_NORMAL_SWING_DELAY_LIMIT = player_value("normal_swing_delay_limit")
PLAYER_NORMAL_SWING_FRAME_MIN = player_value("normal_swing_frame_min")
PLAYER_NORMAL_SWING_FRAME_MAX = player_value("normal_swing_frame_max")
PLAYER_GAME_END_ANIM_LAST_FRAME = player_value("game_end_anim_last_frame")
PLAYER_GAME_END_ANIM_DELAY_LIMIT = player_value("game_end_anim_delay_limit")
MENU_SITTING_ROWS, MENU_SITTING_COLS = menu_values("sitting_grid", 2)
MENU_SITTING_SCROLL_FRAME_MULTIPLIER, MENU_SITTING_SCROLL_MODULO, MENU_SITTING_SCROLL_SCALE = (
    menu_values("sitting_scroll", 3)
)
MENU_FIGHT_GROW_FRAMES = menu_value("fight_grow_frames")
MENU_FIGHT_SIZE_CYCLE = menu_values("fight_size_cycle")
MENU_FIGHT_ANCHOR_X, MENU_FIGHT_ANCHOR_Y = menu_values("fight_anchor", 2)
MENU_FIGHT_WIDTH_DIVISOR = menu_value("fight_width_divisor")
MENU_FIGHT_SCALE = menu_value("fight_scale")
(
    MENU_TITLE_SHOW_FRAME,
    MENU_TITLE_SLIDE_END_FRAME,
    MENU_TITLE_SQUASH_END_FRAME,
    MENU_TITLE_STRETCH_END_FRAME,
) = menu_values("title_phase_frames", 4)
MENU_TITLE_SLIDE_SPEED = menu_value("title_slide_speed")
MENU_TITLE_SLIDE_OFFSET = menu_value("title_slide_offset")
MENU_TITLE_SQUASH_SPEED = menu_value("title_squash_speed")
MENU_TITLE_SQUASH_WIDTH = menu_value("title_squash_width")
MENU_TITLE_STRETCH_SPEED = menu_value("title_stretch_speed")
MENU_TITLE_STRETCH_BASE_WIDTH = menu_value("title_stretch_base_width")
MENU_OPTION_CLAMP_MIN, MENU_OPTION_CLAMP_MAX = menu_values("option_no_input_clamp", 2)
MENU_OPTION_SIZE_DIFF_BASE = menu_value("option_size_diff_base")
MENU_OPTION_EXPAND_BIAS = menu_value("option_expand_bias")
MENU_OPTION_X_MULTIPLIER = menu_value("option_x_multiplier")
MENU_OPTION_WIDTH_MULTIPLIER = menu_value("option_width_multiplier")
MENU_OPTION_Y_MULTIPLIER = menu_value("option_y_multiplier")
MENU_OPTION_HEIGHT_MULTIPLIER = menu_value("option_height_multiplier")


def call_add_const(p: Program, dst: int, src: int, amount: int) -> None:
    p.call(SYS_ADD_CONST, dst, src, amount)


def call_add(p: Program, dst: int, left: int, right: int) -> None:
    p.call(SYS_ADD, dst, left, right)


def call_sub(p: Program, dst: int, left: int, right: int) -> None:
    p.call(SYS_SUB, dst, left, right)


def call_clamp(p: Program, dst: int, src: int, lo: int, hi: int) -> None:
    p.call(SYS_CLAMP, dst, src, lo, hi)


def call_abs(p: Program, dst: int, src: int) -> None:
    p.call(SYS_ABS, dst, src)


def call_eq(p: Program, dst: int, left: int, right: int) -> None:
    p.call(SYS_EQ, dst, left, right)


def call_le(p: Program, dst: int, left: int, right: int) -> None:
    p.call(SYS_GT, dst, left, right)
    call_eq(p, dst, dst, ZERO)


def call_ge(p: Program, dst: int, left: int, right: int) -> None:
    p.call(SYS_LT, dst, left, right)
    call_eq(p, dst, dst, ZERO)


def if_var_nonzero_goto(p: Program, var_index: int, label: str) -> None:
    call_eq(p, TMP2, var_index, ZERO)
    p.if_zero_goto(var(TMP2), label)


def call_key(p: Program, key_id: int, out: int) -> None:
    p.call(SYS_KEY_DOWN, ACTION_KEY_CODES[key_id], out)


def call_key_pressed(p: Program, key_id: int, out: int) -> None:
    p.call(SYS_KEY_PRESSED, ACTION_KEY_CODES[key_id], out)


def call_div(p: Program, dst: int, left: int, right: int) -> None:
    p.call(SYS_DIV, dst, left, right)


def call_mod(p: Program, dst: int, left: int, right: int) -> None:
    p.call(SYS_MOD, dst, left, right)


def call_mul(p: Program, dst: int, left: int, right: int) -> None:
    p.call(SYS_MUL, dst, left, right)


def load_setting(p: Program, key: int, dst: int, default: int) -> None:
    p.call(SYS_LOAD_SETTING, key, dst, default)


def save_setting_var(p: Program, key: int, value_var: int) -> None:
    p.call_expr(SYS_SAVE_SETTING, num(key), var(value_var))


def define_palette(p: Program) -> None:
    for color in PALETTE:
        p.call(SYS_DEFINE_COLOR, *color)


def define_assets(p: Program) -> None:
    p.call(SYS_DEFINE_TEXTURE, SPRITE_TEXTURE_SLOT, SPRITE_SHEET_ASSET)
    p.call(SYS_DEFINE_AUDIO, BGM_AUDIO_SLOT, BGM_ASSET)
    for audio in SFX_AUDIO_BANK:
        p.call(SYS_DEFINE_AUDIO, *audio)


def configure_window(p: Program) -> None:
    p.call(SYS_CONFIGURE_WINDOW, WINDOW_WIDTH, WINDOW_HEIGHT)


def configure_settings(p: Program) -> None:
    p.call(SYS_CONFIGURE_SETTINGS, SETTINGS_PROFILE)


def render_values(key: str, expected_len: int | None = None) -> list[int]:
    values = RENDER_CONFIG.get(key)
    if values is None:
        raise RuntimeError(f"missing render key: {key}")
    if expected_len is not None and len(values) != expected_len:
        raise RuntimeError(f"render key {key} must have {expected_len} values")
    return values


def draw_render_sprite_const(p: Program, key: str) -> None:
    draw_sprite_const(p, *render_values(key, 8))


RNG_BYTES = [
    RNG_BYTE0,
    RNG_BYTE1,
    RNG_BYTE2,
    RNG_BYTE3,
    RNG_BYTE4,
    RNG_BYTE5,
    RNG_BYTE6,
    RNG_BYTE7,
]
RNG_NEXT_BYTES = [
    RNG_NEXT0,
    RNG_NEXT1,
    RNG_NEXT2,
    RNG_NEXT3,
    RNG_NEXT4,
    RNG_NEXT5,
    RNG_NEXT6,
    RNG_NEXT7,
]
RNG_MULTIPLIER_BYTES = RNG_CONFIG["multiplier_bytes"]
RNG_SEED_BYTES = RNG_CONFIG["seed_bytes"]


def init_rng_seed(p: Program) -> None:
    for byte_var, value in zip(RNG_BYTES, RNG_SEED_BYTES):
        p.emit(assign(byte_var, num(value)))
    for byte_var in RNG_NEXT_BYTES:
        p.emit(assign(byte_var, num(0)))
    p.emit(assign(RNG_CARRY, num(0)))
    p.emit(assign(RNG_STATE, num(0)))
    p.emit(assign(RNG_OUT, num(0)))
    p.emit(assign(RNG_FIXED_ENABLED, num(0)))
    p.emit(assign(RNG_FIXED_VALUE, num(0)))


def call_pika_rand(p: Program) -> None:
    p.emit(assign(RNG_CARRY, num(0)))
    for out_index, next_var in enumerate(RNG_NEXT_BYTES):
        p.emit(assign(TMP, num(1 if out_index == 0 else 0)))
        for byte_index in range(out_index + 1):
            multiplier = RNG_MULTIPLIER_BYTES[out_index - byte_index]
            if multiplier == 0:
                continue
            p.emit(assign(DIGIT_CONST, num(multiplier)))
            call_mul(p, TMP2, RNG_BYTES[byte_index], DIGIT_CONST)
            call_add(p, TMP, TMP, TMP2)
        call_add(p, TMP, TMP, RNG_CARRY)
        p.emit(assign(DIGIT_CONST, num(256)))
        call_mod(p, next_var, TMP, DIGIT_CONST)
        call_div(p, RNG_CARRY, TMP, DIGIT_CONST)

    for byte_var, next_var in zip(RNG_BYTES, RNG_NEXT_BYTES):
        p.emit(assign(byte_var, var(next_var)))

    p.emit(assign(DIGIT_CONST, num(2)))
    call_div(p, RNG_OUT, RNG_BYTE2, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(128)))
    call_mul(p, TMP, RNG_BYTE3, DIGIT_CONST)
    call_add(p, RNG_OUT, RNG_OUT, TMP)
    p.emit(assign(RNG_STATE, var(RNG_OUT)))

    call_sub(p, TMP, ONE, RNG_FIXED_ENABLED)
    call_mul(p, RNG_OUT, RNG_OUT, TMP)
    call_mul(p, TMP, RNG_FIXED_VALUE, RNG_FIXED_ENABLED)
    call_add(p, RNG_OUT, RNG_OUT, TMP)
    p.emit(assign(RNG_STATE, var(RNG_OUT)))


def call_rand_mod(p: Program, dst: int, modulo: int) -> None:
    call_pika_rand(p)
    p.emit(assign(DIGIT_CONST, num(modulo)))
    call_mod(p, dst, RNG_OUT, DIGIT_CONST)


def draw_circle_const(p: Program, x: int, y: int, radius: int, color: int) -> None:
    p.call(SYS_DRAW_CIRCLE, x, y, radius, color)


def draw_circle_vars(p: Program, x_var: int, y_var: int, radius: int, color: int) -> None:
    p.call_expr(SYS_DRAW_CIRCLE, var(x_var), var(y_var), num(radius), num(color))


def draw_sprite_values(
    p: Program,
    sx: int,
    sy: int,
    sw: int,
    sh: int,
    dx_expr: str,
    dy_expr: str,
    dw: int,
    dh: int,
    flip: int = 0,
) -> None:
    p.call_expr(
        SYS_DRAW_TEXTURE,
        num(SPRITE_TEXTURE_SLOT),
        num(sx),
        num(sy),
        num(sw),
        num(sh),
        dx_expr,
        dy_expr,
        num(dw),
        num(dh),
        num(flip),
    )


def draw_sprite_exprs(
    p: Program,
    sx: int,
    sy: int,
    sw: int,
    sh: int,
    dx_expr: str,
    dy_expr: str,
    dw_expr: str,
    dh_expr: str,
    flip: int = 0,
) -> None:
    p.call_expr(
        SYS_DRAW_TEXTURE,
        num(SPRITE_TEXTURE_SLOT),
        num(sx),
        num(sy),
        num(sw),
        num(sh),
        dx_expr,
        dy_expr,
        dw_expr,
        dh_expr,
        num(flip),
    )


def draw_sprite_alpha_exprs(
    p: Program,
    sx: int,
    sy: int,
    sw: int,
    sh: int,
    dx_expr: str,
    dy_expr: str,
    dw_expr: str,
    dh_expr: str,
    alpha_expr: str,
    flip: int = 0,
) -> None:
    p.call_expr(
        SYS_DRAW_TEXTURE_ALPHA,
        num(SPRITE_TEXTURE_SLOT),
        num(sx),
        num(sy),
        num(sw),
        num(sh),
        dx_expr,
        dy_expr,
        dw_expr,
        dh_expr,
        num(flip),
        alpha_expr,
    )


def draw_sprite_const(
    p: Program,
    sx: int,
    sy: int,
    sw: int,
    sh: int,
    dx: int,
    dy: int,
    dw: int,
    dh: int,
) -> None:
    draw_sprite_values(p, sx, sy, sw, sh, num(dx), num(dy), dw, dh)


def draw_rect(p: Program, x: int, y: int, w: int, h: int, color: int) -> None:
    p.call(SYS_DRAW_RECT, x, y, w, h, color)


def draw_rect_alpha_expr(
    p: Program, x: int, y: int, w: int, h: int, color: int, alpha_expr: str
) -> None:
    p.call_expr(
        SYS_DRAW_RECT_ALPHA,
        num(x),
        num(y),
        num(w),
        num(h),
        num(color),
        alpha_expr,
    )


def play_sfx_const_side(p: Program, sound_id: int, side: int, label: str) -> None:
    call_eq(p, TMP, SFX_MODE, ONE)
    if_var_nonzero_goto(p, TMP, f"{label}_mono")
    p.call(SYS_PLAY_AUDIO, sfx_audio_slot(sound_id, SFX_STEREO_MODE, side), 0, 100)
    p.emit(p.goto(f"{label}_done"))
    p.label(f"{label}_mono")
    p.call(SYS_PLAY_AUDIO, sfx_audio_slot(sound_id, SFX_MONO_MODE, side), 0, 100)
    p.label(f"{label}_done")


def play_sfx_var_side(p: Program, sound_id: int, side_var: int, label: str) -> None:
    p.emit(assign(DIGIT_CONST, num(-1)))
    call_eq(p, TMP, side_var, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{label}_left")
    call_eq(p, TMP, side_var, ONE)
    if_var_nonzero_goto(p, TMP, f"{label}_right")
    play_sfx_const_side(p, sound_id, 0, f"{label}_center")
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_left")
    play_sfx_const_side(p, sound_id, -1, f"{label}_left_play")
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_right")
    play_sfx_const_side(p, sound_id, 1, f"{label}_right_play")
    p.label(f"{label}_done")


def apply_jump(
    p: Program, key_id: int, y_var: int, dy_var: int, state_var: int, label: str
) -> None:
    call_key(p, key_id, KEY)
    p.if_zero_goto(var(KEY), f"{label}_done")
    call_eq(p, TMP, y_var, FLOOR_Y)
    p.if_zero_goto(var(TMP), f"{label}_done")
    p.emit(assign(dy_var, num(PLAYER_JUMP_Y_VELOCITY_SCREEN)))
    p.emit(assign(state_var, num(PLAYER_STATE_JUMP)))
    if_var_nonzero_goto(p, SFX_MODE, f"{label}_jump_sound_on")
    p.emit(p.goto(f"{label}_done"))
    p.label(f"{label}_jump_sound_on")
    play_sfx_const_side(p, JUMP_SFX[0], JUMP_SFX[1], f"{label}_jump")
    p.label(f"{label}_done")


def apply_vertical_physics(
    p: Program, y_var: int, dy_var: int, state_var: int, label: str
) -> None:
    call_add(p, y_var, y_var, dy_var)
    call_add_const(p, dy_var, dy_var, PLAYER_GRAVITY_SCREEN)
    p.call(SYS_GT, TMP, y_var, FLOOR_Y)
    p.if_zero_goto(var(TMP), f"{label}_floor_done")
    p.emit(assign(y_var, var(FLOOR_Y)))
    p.emit(assign(dy_var, num(0)))
    p.emit(assign(state_var, num(PLAYER_STATE_NORMAL)))
    p.label(f"{label}_floor_done")


def collide_player(
    p: Program,
    x_var: int,
    y_var: int,
    state_var: int,
    input_x_var: int,
    input_y_var: int,
    collision_flag_var: int,
    label: str,
) -> None:
    call_sub(p, TMP, BALL_X, x_var)
    call_abs(p, TMP, TMP)
    p.call(SYS_GT, KEY, TMP, COLLISION_RADIUS)
    p.if_zero_goto(var(KEY), f"{label}_check_y")
    p.emit(assign(collision_flag_var, num(0)))
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_check_y")
    call_sub(p, TMP, BALL_Y, y_var)
    call_abs(p, TMP, TMP)
    p.call(SYS_GT, KEY, TMP, COLLISION_RADIUS)
    p.if_zero_goto(var(KEY), f"{label}_hit")
    p.emit(assign(collision_flag_var, num(0)))
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_hit")
    if_var_nonzero_goto(p, collision_flag_var, f"{label}_done")
    p.emit(assign(collision_flag_var, num(1)))

    call_sub(p, TMP, BALL_X, x_var)
    call_abs(p, TMP2, TMP)
    p.emit(assign(DIGIT_CONST, num(3 * SCREEN_SCALE)))
    call_div(p, TMP2, TMP2, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(SCREEN_SCALE)))
    call_mul(p, TMP2, TMP2, DIGIT_CONST)
    p.call(SYS_LT, KEY, BALL_X, x_var)
    p.if_zero_goto(var(KEY), f"{label}_right_side_velocity")
    call_sub(p, BALL_DX, ZERO, TMP2)
    p.emit(p.goto(f"{label}_after_side_velocity"))

    p.label(f"{label}_right_side_velocity")
    p.call(SYS_GT, KEY, BALL_X, x_var)
    p.if_zero_goto(var(KEY), f"{label}_center_velocity")
    p.emit(assign(BALL_DX, var(TMP2)))
    p.emit(p.goto(f"{label}_after_side_velocity"))

    p.label(f"{label}_center_velocity")
    p.emit(p.goto(f"{label}_after_side_velocity"))

    p.label(f"{label}_after_side_velocity")
    call_eq(p, KEY, BALL_DX, ZERO)
    if_var_nonzero_goto(p, KEY, f"{label}_fallback_x_velocity")
    p.emit(p.goto(f"{label}_after_fallback_x_velocity"))

    p.label(f"{label}_fallback_x_velocity")
    call_rand_mod(p, RNG_OUT, 3)
    call_add_const(p, BALL_DX, RNG_OUT, -1)
    p.emit(assign(DIGIT_CONST, num(SCREEN_SCALE)))
    call_mul(p, BALL_DX, BALL_DX, DIGIT_CONST)

    p.label(f"{label}_after_fallback_x_velocity")
    call_abs(p, TMP, BALL_DY)
    call_sub(p, BALL_DY, ZERO, TMP)
    p.emit(assign(DIGIT_CONST, num(BALL_MIN_BOUNCE_Y_VELOCITY_SCREEN)))
    p.call(SYS_LT, KEY, TMP, DIGIT_CONST)
    p.if_zero_goto(var(KEY), f"{label}_after_min_y_velocity")
    p.emit(assign(BALL_DY, num(-BALL_MIN_BOUNCE_Y_VELOCITY_SCREEN)))
    p.label(f"{label}_after_min_y_velocity")

    p.emit(assign(DIGIT_CONST, num(PLAYER_STATE_POWER_HIT)))
    call_eq(p, KEY, state_var, DIGIT_CONST)
    if_var_nonzero_goto(p, KEY, f"{label}_power_hit")
    p.emit(p.goto(f"{label}_normal_hit_done"))

    p.label(f"{label}_power_hit")
    call_abs(p, TMP, input_x_var)
    call_add_const(p, TMP, TMP, 1)
    p.emit(assign(DIGIT_CONST, num(BALL_POWER_HIT_X_VELOCITY_SCREEN)))
    call_mul(p, TMP, TMP, DIGIT_CONST)
    p.call(SYS_LT, KEY, BALL_X, MID_X)
    p.if_zero_goto(var(KEY), f"{label}_power_right_court")
    p.emit(assign(BALL_DX, var(TMP)))
    p.emit(p.goto(f"{label}_after_power_dx"))

    p.label(f"{label}_power_right_court")
    call_sub(p, BALL_DX, ZERO, TMP)

    p.label(f"{label}_after_power_dx")
    call_abs(p, TMP, BALL_DY)
    call_mul(p, TMP, TMP, input_y_var)
    p.emit(assign(DIGIT_CONST, num(2)))
    call_mul(p, BALL_DY, TMP, DIGIT_CONST)
    p.emit(assign(BALL_PUNCH_X, var(BALL_X)))
    p.emit(assign(BALL_PUNCH_Y, var(BALL_Y)))
    p.emit(assign(BALL_PUNCH_RADIUS, var(BALL_RADIUS)))
    p.emit(assign(BALL_IS_POWER_HIT, num(1)))
    p.emit(assign(BALL_SOUND_POWER_HIT, num(1)))
    update_expected_landing(p, f"{label}_power_expected")
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_normal_hit_done")
    p.emit(assign(BALL_IS_POWER_HIT, num(0)))
    update_expected_landing(p, f"{label}_normal_expected")
    p.label(f"{label}_done")


def set_phase(p: Program, phase: int) -> None:
    p.emit(assign(PHASE, num(phase)))
    p.emit(assign(FRAME_COUNTER, num(0)))


def wait_and_loop(p: Program) -> None:
    p.call(SYS_WAIT_FRAME)
    p.emit(p.goto("frame"))


def reset_sfx_flags(p: Program, flag_vars: list[int]) -> None:
    for flag_var in flag_vars:
        p.emit(assign(flag_var, num(0)))


def reset_players(p: Program) -> None:
    p.emit(assign(P1_X, num(P1_START_X_SCREEN)))
    p.emit(assign(P1_Y, var(FLOOR_Y)))
    p.emit(assign(P1_DY, num(0)))
    p.emit(assign(P1_STATE, num(PLAYER_STATE_NORMAL)))
    p.emit(assign(P1_FRAME, num(0)))
    p.emit(assign(P1_DIVE_DIR, num(0)))
    p.emit(assign(P1_LIE_TIMER, num(PLAYER_LIE_TIMER_STAND_THRESHOLD)))
    p.emit(assign(P1_COLLIDING, num(0)))
    p.emit(assign(P1_DELAY, num(0)))
    p.emit(assign(P1_SWING_DIR, num(1)))
    p.emit(assign(P1_GAME_ENDED, num(0)))
    call_rand_mod(p, P1_BOLDNESS, 5)
    p.emit(assign(P1_STANDBY, num(0)))
    p.emit(assign(P2_X, num(P2_START_X_SCREEN)))
    p.emit(assign(P2_Y, var(FLOOR_Y)))
    p.emit(assign(P2_DY, num(0)))
    p.emit(assign(P2_STATE, num(PLAYER_STATE_NORMAL)))
    p.emit(assign(P2_FRAME, num(0)))
    p.emit(assign(P2_DIVE_DIR, num(0)))
    p.emit(assign(P2_LIE_TIMER, num(PLAYER_LIE_TIMER_STAND_THRESHOLD)))
    p.emit(assign(P2_COLLIDING, num(0)))
    p.emit(assign(P2_DELAY, num(0)))
    p.emit(assign(P2_SWING_DIR, num(1)))
    p.emit(assign(P2_GAME_ENDED, num(0)))
    call_rand_mod(p, P2_BOLDNESS, 5)
    p.emit(assign(P2_STANDBY, num(0)))
    reset_sfx_flags(p, PLAYER_SFX_FLAG_VARS)


def reset_ball(p: Program, prefix: str) -> None:
    p.emit(assign(BALL_Y, num(BALL_SERVE_Y_SCREEN)))
    p.emit(assign(BALL_DY, num(BALL_SERVE_DY)))
    p.emit(assign(BALL_FRAME, num(0)))
    p.emit(assign(BALL_FINE_ROT, num(0)))
    p.emit(assign(BALL_ROTATION, num(0)))
    call_eq(p, TMP, IS_P2_SERVE, ZERO)
    if_var_nonzero_goto(p, TMP, f"{prefix}_p1_serve")
    p.emit(assign(BALL_X, num(BALL_P2_SERVE_X_SCREEN)))
    p.emit(assign(BALL_DX, num(BALL_SERVE_DX)))
    p.emit(p.goto(f"{prefix}_serve_done"))
    p.label(f"{prefix}_p1_serve")
    p.emit(assign(BALL_X, num(BALL_P1_SERVE_X_SCREEN)))
    p.emit(assign(BALL_DX, num(BALL_SERVE_DX)))
    p.label(f"{prefix}_serve_done")
    p.emit(assign(BALL_EXPECTED_X, var(BALL_X)))
    p.emit(assign(BALL_PREV_X, var(BALL_X)))
    p.emit(assign(BALL_PREV_Y, var(BALL_Y)))
    p.emit(assign(BALL_PREV2_X, var(BALL_X)))
    p.emit(assign(BALL_PREV2_Y, var(BALL_Y)))
    p.emit(assign(BALL_PUNCH_RADIUS, num(0)))
    p.emit(assign(BALL_PUNCH_X, var(BALL_X)))
    p.emit(assign(BALL_PUNCH_Y, var(BALL_Y)))
    p.emit(assign(BALL_IS_POWER_HIT, num(0)))
    p.emit(assign(BALL_TOUCH_GROUND, num(0)))
    reset_sfx_flags(p, BALL_SFX_FLAG_VARS + UI_SFX_FLAG_VARS)


def update_expected_landing(p: Program, prefix: str, steps: int = 1000) -> None:
    p.emit(assign(SIM_X, var(BALL_X)))
    p.emit(assign(SIM_Y, var(BALL_Y)))
    p.emit(assign(SIM_DX, var(BALL_DX)))
    p.emit(assign(SIM_DY, var(BALL_DY)))
    p.emit(assign(SIM_ACTIVE, num(1)))
    p.emit(assign(BALL_EXPECTED_X, var(BALL_X)))
    p.emit(assign(SIM_COUNTER, num(steps)))

    p.label(f"{prefix}_loop")
    if_var_nonzero_goto(p, SIM_ACTIVE, f"{prefix}_active")
    p.emit(p.goto(f"{prefix}_done"))

    p.label(f"{prefix}_active")
    if_var_nonzero_goto(p, SIM_COUNTER, f"{prefix}_step")
    p.emit(p.goto(f"{prefix}_done"))

    p.label(f"{prefix}_step")
    call_add(p, SIM_FUTURE, SIM_X, SIM_DX)
    p.call(SYS_LT, KEY, SIM_FUTURE, LEFT_WALL)
    p.if_zero_goto(var(KEY), f"{prefix}_not_left_wall")
    call_sub(p, SIM_DX, ZERO, SIM_DX)
    p.label(f"{prefix}_not_left_wall")
    p.call(SYS_GT, KEY, SIM_FUTURE, RIGHT_WALL)
    p.if_zero_goto(var(KEY), f"{prefix}_not_right_wall")
    call_sub(p, SIM_DX, ZERO, SIM_DX)
    p.label(f"{prefix}_not_right_wall")

    call_add(p, SIM_FUTURE, SIM_Y, SIM_DY)
    p.call(SYS_LT, KEY, SIM_FUTURE, ZERO)
    p.if_zero_goto(var(KEY), f"{prefix}_not_ceiling")
    p.emit(assign(SIM_DY, num(BALL_CEILING_BOUNCE_DY_SCREEN)))
    p.label(f"{prefix}_not_ceiling")

    call_sub(p, TMP, SIM_X, MID_X)
    call_abs(p, TMP, TMP)
    p.call(SYS_LT, TMP2, TMP, NET_HALF)
    p.if_zero_goto(var(TMP2), f"{prefix}_net_done")
    p.call(SYS_GT, TMP2, SIM_Y, NET_TOP)
    p.if_zero_goto(var(TMP2), f"{prefix}_net_done")
    p.call(SYS_LT, TMP2, SIM_Y, NET_BOTTOM)
    p.if_zero_goto(var(TMP2), f"{prefix}_net_side")
    p.call(SYS_GT, TMP2, SIM_DY, ZERO)
    p.if_zero_goto(var(TMP2), f"{prefix}_net_done")
    call_sub(p, SIM_DY, ZERO, SIM_DY)
    p.emit(p.goto(f"{prefix}_net_done"))

    p.label(f"{prefix}_net_side")
    p.call(SYS_LT, TMP2, SIM_X, MID_X)
    p.if_zero_goto(var(TMP2), f"{prefix}_net_right_side")
    call_abs(p, SIM_DX, SIM_DX)
    call_sub(p, SIM_DX, ZERO, SIM_DX)
    p.emit(p.goto(f"{prefix}_net_done"))

    p.label(f"{prefix}_net_right_side")
    call_abs(p, SIM_DX, SIM_DX)
    p.label(f"{prefix}_net_done")

    call_add(p, SIM_FUTURE, SIM_Y, SIM_DY)
    p.call(SYS_GT, KEY, SIM_FUTURE, BALL_FLOOR_Y)
    p.if_zero_goto(var(KEY), f"{prefix}_not_landed")
    p.emit(assign(BALL_EXPECTED_X, var(SIM_X)))
    p.emit(assign(SIM_ACTIVE, num(0)))
    p.emit(p.goto(f"{prefix}_done"))

    p.label(f"{prefix}_not_landed")
    p.emit(assign(SIM_Y, var(SIM_FUTURE)))
    call_add(p, SIM_X, SIM_X, SIM_DX)
    call_add_const(p, SIM_DY, SIM_DY, BALL_GRAVITY_SCREEN)
    call_add_const(p, SIM_COUNTER, SIM_COUNTER, -1)
    p.emit(p.goto(f"{prefix}_loop"))

    p.label(f"{prefix}_done")


def simulate_power_landing(
    p: Program, input_x_abs: int, input_y: int, prefix: str, steps: int = 1000
) -> None:
    p.emit(assign(SIM_X, var(BALL_X)))
    p.emit(assign(SIM_Y, var(BALL_Y)))
    p.emit(assign(SIM_ACTIVE, num(1)))
    p.emit(assign(POWER_EXPECTED_X, var(BALL_X)))

    p.emit(assign(DIGIT_CONST, num(input_x_abs + 1)))
    p.emit(assign(TMP, num(BALL_POWER_HIT_X_VELOCITY_SCREEN)))
    call_mul(p, SIM_DX, DIGIT_CONST, TMP)
    p.call(SYS_LT, KEY, BALL_X, MID_X)
    p.if_zero_goto(var(KEY), f"{prefix}_right_court_dx")
    p.emit(p.goto(f"{prefix}_dx_ready"))

    p.label(f"{prefix}_right_court_dx")
    call_sub(p, SIM_DX, ZERO, SIM_DX)

    p.label(f"{prefix}_dx_ready")
    call_abs(p, SIM_DY, BALL_DY)
    p.emit(assign(DIGIT_CONST, num(input_y)))
    call_mul(p, SIM_DY, SIM_DY, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(2)))
    call_mul(p, SIM_DY, SIM_DY, DIGIT_CONST)

    p.emit(assign(SIM_COUNTER, num(steps)))

    p.label(f"{prefix}_loop")
    if_var_nonzero_goto(p, SIM_ACTIVE, f"{prefix}_active")
    p.emit(p.goto(f"{prefix}_done"))

    p.label(f"{prefix}_active")
    if_var_nonzero_goto(p, SIM_COUNTER, f"{prefix}_step")
    p.emit(p.goto(f"{prefix}_done"))

    p.label(f"{prefix}_step")
    call_add(p, SIM_FUTURE, SIM_X, SIM_DX)
    p.call(SYS_LT, KEY, SIM_FUTURE, LEFT_WALL)
    p.if_zero_goto(var(KEY), f"{prefix}_not_left_wall")
    call_sub(p, SIM_DX, ZERO, SIM_DX)
    p.label(f"{prefix}_not_left_wall")
    p.call(SYS_GT, KEY, SIM_FUTURE, RIGHT_WALL)
    p.if_zero_goto(var(KEY), f"{prefix}_not_right_wall")
    call_sub(p, SIM_DX, ZERO, SIM_DX)
    p.label(f"{prefix}_not_right_wall")

    call_add(p, SIM_FUTURE, SIM_Y, SIM_DY)
    p.call(SYS_LT, KEY, SIM_FUTURE, ZERO)
    p.if_zero_goto(var(KEY), f"{prefix}_not_ceiling")
    p.emit(assign(SIM_DY, num(BALL_CEILING_BOUNCE_DY_SCREEN)))
    p.label(f"{prefix}_not_ceiling")

    call_sub(p, TMP, SIM_X, MID_X)
    call_abs(p, TMP, TMP)
    p.call(SYS_LT, TMP2, TMP, NET_HALF)
    p.if_zero_goto(var(TMP2), f"{prefix}_net_done")
    p.call(SYS_GT, TMP2, SIM_Y, NET_TOP)
    p.if_zero_goto(var(TMP2), f"{prefix}_net_done")
    p.call(SYS_GT, TMP2, SIM_DY, ZERO)
    p.if_zero_goto(var(TMP2), f"{prefix}_net_done")
    call_sub(p, SIM_DY, ZERO, SIM_DY)
    p.label(f"{prefix}_net_done")

    call_add(p, SIM_FUTURE, SIM_Y, SIM_DY)
    p.call(SYS_GT, KEY, SIM_FUTURE, BALL_FLOOR_Y)
    p.if_zero_goto(var(KEY), f"{prefix}_not_landed")
    p.emit(assign(POWER_EXPECTED_X, var(SIM_X)))
    p.emit(assign(SIM_ACTIVE, num(0)))
    p.emit(p.goto(f"{prefix}_done"))

    p.label(f"{prefix}_not_landed")
    p.emit(assign(SIM_Y, var(SIM_FUTURE)))
    call_add(p, SIM_X, SIM_X, SIM_DX)
    call_add_const(p, SIM_DY, SIM_DY, BALL_GRAVITY_SCREEN)
    call_add_const(p, SIM_COUNTER, SIM_COUNTER, -1)
    p.emit(p.goto(f"{prefix}_loop"))

    p.label(f"{prefix}_done")


def try_power_hit_candidate(
    p: Program,
    input_x_abs: int,
    input_y: int,
    input_x_var: int,
    input_y_var: int,
    power_var: int,
    other_x_var: int,
    good_right_side: bool,
    success_label: str,
    label: str,
) -> None:
    simulate_power_landing(p, input_x_abs, input_y, f"{label}_sim")
    if good_right_side:
        call_ge(p, TMP2, POWER_EXPECTED_X, MID_X)
    else:
        call_le(p, TMP2, POWER_EXPECTED_X, MID_X)
    p.if_zero_goto(var(TMP2), f"{label}_reject")
    call_sub(p, TMP, POWER_EXPECTED_X, other_x_var)
    call_abs(p, TMP, TMP)
    p.emit(assign(DIGIT_CONST, num(PLAYER_LENGTH_SCREEN)))
    p.call(SYS_GT, TMP2, TMP, DIGIT_CONST)
    p.if_zero_goto(var(TMP2), f"{label}_reject")
    p.emit(assign(input_x_var, num(input_x_abs)))
    p.emit(assign(input_y_var, num(input_y)))
    p.emit(assign(power_var, num(1)))
    p.emit(assign(POWER_GOOD, num(1)))
    p.emit(p.goto(success_label))
    p.label(f"{label}_reject")


def choose_power_hit_input(
    p: Program,
    input_x_var: int,
    input_y_var: int,
    power_var: int,
    other_x_var: int,
    good_right_side: bool,
    label: str,
) -> None:
    p.emit(assign(POWER_GOOD, num(0)))
    call_rand_mod(p, RNG_OUT, 2)
    call_eq(p, TMP2, RNG_OUT, ZERO)
    if_var_nonzero_goto(p, TMP2, f"{label}_ascending_y")
    p.emit(p.goto(f"{label}_descending_y"))

    p.label(f"{label}_ascending_y")
    for candidate_x in (1, 0):
        for candidate_y in (-1, 0, 1):
            candidate_y_label = f"n{abs(candidate_y)}" if candidate_y < 0 else str(candidate_y)
            try_power_hit_candidate(
                p,
                candidate_x,
                candidate_y,
                input_x_var,
                input_y_var,
                power_var,
                other_x_var,
                good_right_side,
                f"{label}_done",
                f"{label}_asc_x{candidate_x}_y{candidate_y_label}",
            )
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_descending_y")
    for candidate_x in (1, 0):
        for candidate_y in (1, 0, -1):
            candidate_y_label = f"n{abs(candidate_y)}" if candidate_y < 0 else str(candidate_y)
            try_power_hit_candidate(
                p,
                candidate_x,
                candidate_y,
                input_x_var,
                input_y_var,
                power_var,
                other_x_var,
                good_right_side,
                f"{label}_done",
                f"{label}_desc_x{candidate_x}_y{candidate_y_label}",
            )
    p.label(f"{label}_done")


def read_axis_input(
    p: Program,
    negative_key: int,
    positive_key: int,
    out_var: int,
    label: str,
    extra_positive_key: int | None = None,
) -> None:
    p.emit(assign(out_var, num(0)))
    call_key(p, negative_key, KEY)
    call_key(p, positive_key, TMP)
    if extra_positive_key is not None:
        call_key(p, extra_positive_key, TMP2)
        call_add(p, TMP, TMP, TMP2)

    p.if_zero_goto(var(KEY), f"{label}_negative_not_down")
    if_var_nonzero_goto(p, TMP, f"{label}_done")
    p.emit(assign(out_var, num(-1)))
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_negative_not_down")
    if_var_nonzero_goto(p, TMP, f"{label}_positive_down")
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_positive_down")
    p.emit(assign(out_var, num(1)))

    p.label(f"{label}_done")


def read_player_inputs(p: Program) -> None:
    p.emit(assign(P1_POWER, num(0)))
    p.emit(assign(P2_POWER, num(0)))

    read_axis_input(p, 1, 2, P1_INPUT_X, "input_p1_x", 11)
    read_axis_input(p, 3, 4, P1_INPUT_Y, "input_p1_y", 11)

    call_key_pressed(p, ACTION_CONFIRM, P1_POWER)

    read_axis_input(p, 6, 7, P2_INPUT_X, "input_p2_x")
    read_axis_input(p, 8, 9, P2_INPUT_Y, "input_p2_y")

    call_key_pressed(p, ACTION_P2_CONFIRM, P2_POWER)


def apply_simple_ai(
    p: Program,
    computer_var: int,
    x_var: int,
    y_var: int,
    state_var: int,
    input_x_var: int,
    input_y_var: int,
    power_var: int,
    boldness_var: int,
    standby_var: int,
    other_x_var: int,
    left_bound: int,
    right_bound: int,
    standby_x: int,
    good_right_side: bool,
    label: str,
) -> None:
    call_eq(p, TMP, computer_var, ZERO)
    if_var_nonzero_goto(p, TMP, f"{label}_done")

    p.emit(assign(input_x_var, num(0)))
    p.emit(assign(input_y_var, num(0)))
    p.emit(assign(power_var, num(0)))
    p.emit(assign(AI_TARGET_X, var(BALL_EXPECTED_X)))
    p.emit(assign(AI_LEFT_BOUND, num(left_bound)))
    p.emit(assign(AI_RIGHT_BOUND, num(right_bound)))

    call_sub(p, TMP, BALL_X, x_var)
    call_abs(p, KEY, TMP)
    p.emit(assign(DIGIT_CONST, num(AI_VIRTUAL_TARGET_DISTANCE_SCREEN)))
    p.call(SYS_GT, TMP2, KEY, DIGIT_CONST)
    p.if_zero_goto(var(TMP2), f"{label}_after_virtual_target")
    call_abs(p, TMP, BALL_DX)
    call_add_const(p, KEY, boldness_var, 5)
    p.emit(assign(DIGIT_CONST, num(SCREEN_SCALE)))
    call_mul(p, KEY, KEY, DIGIT_CONST)
    p.call(SYS_LT, TMP2, TMP, KEY)
    p.if_zero_goto(var(TMP2), f"{label}_after_virtual_target")
    call_eq(p, TMP2, standby_var, ZERO)
    p.if_zero_goto(var(TMP2), f"{label}_after_virtual_target")
    call_le(p, TMP2, BALL_EXPECTED_X, AI_LEFT_BOUND)
    if_var_nonzero_goto(p, TMP2, f"{label}_use_standby_target")
    call_ge(p, TMP2, BALL_EXPECTED_X, AI_RIGHT_BOUND)
    if_var_nonzero_goto(p, TMP2, f"{label}_use_standby_target")
    p.emit(p.goto(f"{label}_after_virtual_target"))

    p.label(f"{label}_use_standby_target")
    p.emit(assign(AI_TARGET_X, num(standby_x)))

    p.label(f"{label}_after_virtual_target")
    call_sub(p, TMP, AI_TARGET_X, x_var)
    call_abs(p, KEY, TMP)
    call_add_const(p, TMP, boldness_var, 8)
    p.emit(assign(DIGIT_CONST, num(SCREEN_SCALE)))
    call_mul(p, TMP, TMP, DIGIT_CONST)
    p.call(SYS_GT, TMP2, KEY, TMP)
    if_var_nonzero_goto(p, TMP2, f"{label}_move_to_target")
    call_rand_mod(p, RNG_OUT, 20)
    call_eq(p, TMP2, RNG_OUT, ZERO)
    if_var_nonzero_goto(p, TMP2, f"{label}_reroll_standby")
    p.emit(p.goto(f"{label}_after_target_move"))

    p.label(f"{label}_reroll_standby")
    call_rand_mod(p, standby_var, 2)
    p.emit(p.goto(f"{label}_after_target_move"))

    p.label(f"{label}_move_to_target")
    p.call(SYS_GT, TMP2, AI_TARGET_X, x_var)
    p.if_zero_goto(var(TMP2), f"{label}_move_left")
    p.emit(assign(input_x_var, num(1)))
    p.emit(p.goto(f"{label}_after_target_move"))

    p.label(f"{label}_move_left")
    p.emit(assign(input_x_var, num(-1)))

    p.label(f"{label}_after_target_move")
    p.emit(assign(DIGIT_CONST, num(PLAYER_STATE_NORMAL)))
    call_eq(p, TMP, state_var, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{label}_ground_ai")
    p.emit(assign(DIGIT_CONST, num(1)))
    call_eq(p, TMP, state_var, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{label}_air_ai")
    p.emit(assign(DIGIT_CONST, num(2)))
    call_eq(p, TMP, state_var, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{label}_air_ai")
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_ground_ai")
    call_abs(p, TMP, BALL_DX)
    call_add_const(p, KEY, boldness_var, 3)
    p.emit(assign(DIGIT_CONST, num(SCREEN_SCALE)))
    call_mul(p, KEY, KEY, DIGIT_CONST)
    p.call(SYS_LT, TMP2, TMP, KEY)
    p.if_zero_goto(var(TMP2), f"{label}_ground_dive_check")
    call_sub(p, TMP, BALL_X, x_var)
    call_abs(p, KEY, TMP)
    p.call(SYS_LT, TMP2, KEY, COLLISION_RADIUS)
    p.if_zero_goto(var(TMP2), f"{label}_ground_dive_check")
    p.emit(assign(DIGIT_CONST, num(AI_JUMP_Y_MIN_SCREEN)))
    p.call(SYS_GT, TMP2, BALL_Y, DIGIT_CONST)
    p.if_zero_goto(var(TMP2), f"{label}_ground_dive_check")
    p.emit(assign(DIGIT_CONST, num(AI_JUMP_Y_BOLDNESS_STEP_SCREEN)))
    call_mul(p, TMP, boldness_var, DIGIT_CONST)
    call_add_const(p, TMP, TMP, AI_JUMP_Y_BASE_SCREEN)
    p.call(SYS_LT, TMP2, BALL_Y, TMP)
    p.if_zero_goto(var(TMP2), f"{label}_ground_dive_check")
    p.call(SYS_GT, TMP2, BALL_DY, ZERO)
    p.if_zero_goto(var(TMP2), f"{label}_ground_dive_check")
    p.emit(assign(input_y_var, num(-1)))
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_ground_dive_check")
    p.call(SYS_GT, TMP2, BALL_EXPECTED_X, AI_LEFT_BOUND)
    p.if_zero_goto(var(TMP2), f"{label}_done")
    p.call(SYS_LT, TMP2, BALL_EXPECTED_X, AI_RIGHT_BOUND)
    p.if_zero_goto(var(TMP2), f"{label}_done")
    call_sub(p, TMP, BALL_X, x_var)
    call_abs(p, KEY, TMP)
    p.emit(assign(DIGIT_CONST, num(AI_BOLDNESS_DISTANCE_STEP_SCREEN)))
    call_mul(p, TMP, boldness_var, DIGIT_CONST)
    call_add_const(p, TMP, TMP, PLAYER_LENGTH_SCREEN)
    p.call(SYS_GT, TMP2, KEY, TMP)
    p.if_zero_goto(var(TMP2), f"{label}_done")
    p.call(SYS_GT, TMP2, BALL_X, AI_LEFT_BOUND)
    p.if_zero_goto(var(TMP2), f"{label}_done")
    p.call(SYS_LT, TMP2, BALL_X, AI_RIGHT_BOUND)
    p.if_zero_goto(var(TMP2), f"{label}_done")
    p.emit(assign(DIGIT_CONST, num(AI_GROUND_DIVE_Y_MIN_SCREEN)))
    p.call(SYS_GT, TMP2, BALL_Y, DIGIT_CONST)
    p.if_zero_goto(var(TMP2), f"{label}_done")
    p.emit(assign(power_var, num(1)))
    p.call(SYS_GT, TMP2, BALL_X, x_var)
    p.if_zero_goto(var(TMP2), f"{label}_ground_dive_left")
    p.emit(assign(input_x_var, num(1)))
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_ground_dive_left")
    p.emit(assign(input_x_var, num(-1)))
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_air_ai")
    call_sub(p, TMP, BALL_X, x_var)
    call_abs(p, KEY, TMP)
    p.emit(assign(DIGIT_CONST, num(AI_AIR_TRACK_DEADZONE_SCREEN)))
    p.call(SYS_GT, TMP2, KEY, DIGIT_CONST)
    p.if_zero_goto(var(TMP2), f"{label}_air_power_check")
    p.call(SYS_GT, TMP2, BALL_X, x_var)
    p.if_zero_goto(var(TMP2), f"{label}_air_move_left")
    p.emit(assign(input_x_var, num(1)))
    p.emit(p.goto(f"{label}_air_power_check"))

    p.label(f"{label}_air_move_left")
    p.emit(assign(input_x_var, num(-1)))

    p.label(f"{label}_air_power_check")
    call_sub(p, TMP, BALL_X, x_var)
    call_abs(p, KEY, TMP)
    p.emit(assign(DIGIT_CONST, num(AI_AIR_POWER_RANGE_SCREEN)))
    p.call(SYS_LT, TMP2, KEY, DIGIT_CONST)
    p.if_zero_goto(var(TMP2), f"{label}_done")
    call_sub(p, TMP, BALL_Y, y_var)
    call_abs(p, KEY, TMP)
    p.emit(assign(DIGIT_CONST, num(AI_AIR_POWER_RANGE_SCREEN)))
    p.call(SYS_LT, TMP2, KEY, DIGIT_CONST)
    p.if_zero_goto(var(TMP2), f"{label}_done")
    choose_power_hit_input(
        p,
        input_x_var,
        input_y_var,
        power_var,
        other_x_var,
        good_right_side,
        f"{label}_choose_power",
    )
    if_var_nonzero_goto(p, power_var, f"{label}_power_candidate_selected")
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_power_candidate_selected")
    call_sub(p, TMP, other_x_var, x_var)
    call_abs(p, KEY, TMP)
    p.emit(assign(DIGIT_CONST, num(AI_CLOSE_OPPONENT_DISTANCE_SCREEN)))
    p.call(SYS_LT, TMP2, KEY, DIGIT_CONST)
    p.if_zero_goto(var(TMP2), f"{label}_done")
    call_eq(p, TMP2, input_y_var, NEG_ONE)
    if_var_nonzero_goto(p, TMP2, f"{label}_done")
    p.emit(assign(input_y_var, num(-1)))

    p.label(f"{label}_done")


def process_player_movement(
    p: Program,
    x_var: int,
    y_var: int,
    dy_var: int,
    state_var: int,
    frame_var: int,
    input_x_var: int,
    input_y_var: int,
    power_var: int,
    dive_dir_var: int,
    lie_timer_var: int,
    delay_var: int,
    swing_dir_var: int,
    sound_pika_var: int,
    sound_chu_var: int,
    left_bound: int,
    right_bound: int,
    label: str,
) -> None:
    p.emit(assign(DIGIT_CONST, num(PLAYER_STATE_LYING)))
    call_eq(p, TMP, state_var, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{label}_lying")
    p.emit(p.goto(f"{label}_not_lying"))

    p.label(f"{label}_lying")
    call_add_const(p, lie_timer_var, lie_timer_var, -1)
    p.emit(assign(DIGIT_CONST, num(PLAYER_LIE_TIMER_STAND_THRESHOLD)))
    p.call(SYS_LT, TMP, lie_timer_var, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{label}_stand_after_lying")
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_stand_after_lying")
    p.emit(assign(state_var, num(PLAYER_STATE_NORMAL)))
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_not_lying")
    p.emit(assign(DIGIT_CONST, num(PLAYER_STATE_DIVING)))
    p.call(SYS_LT, TMP, state_var, DIGIT_CONST)
    p.if_zero_goto(var(TMP), f"{label}_diving_velocity")
    p.emit(assign(DIGIT_CONST, num(PLAYER_WALK_SPEED_SCREEN)))
    call_mul(p, TMP, input_x_var, DIGIT_CONST)
    p.emit(p.goto(f"{label}_apply_x_velocity"))

    p.label(f"{label}_diving_velocity")
    p.emit(assign(DIGIT_CONST, num(PLAYER_DIVE_SPEED_SCREEN)))
    call_mul(p, TMP, dive_dir_var, DIGIT_CONST)

    p.label(f"{label}_apply_x_velocity")
    call_add(p, x_var, x_var, TMP)
    call_clamp(p, x_var, x_var, left_bound, right_bound)

    p.emit(assign(DIGIT_CONST, num(PLAYER_STATE_DIVING)))
    p.call(SYS_LT, TMP, state_var, DIGIT_CONST)
    p.if_zero_goto(var(TMP), f"{label}_jump_done")
    call_eq(p, TMP, input_y_var, NEG_ONE)
    p.if_zero_goto(var(TMP), f"{label}_jump_done")
    call_eq(p, TMP, y_var, FLOOR_Y)
    p.if_zero_goto(var(TMP), f"{label}_jump_done")
    p.emit(assign(dy_var, num(PLAYER_JUMP_Y_VELOCITY_SCREEN)))
    p.emit(assign(state_var, num(PLAYER_STATE_JUMP)))
    p.emit(assign(frame_var, num(0)))
    p.emit(assign(sound_chu_var, num(1)))
    p.label(f"{label}_jump_done")

    call_add(p, y_var, y_var, dy_var)
    p.call(SYS_LT, TMP, y_var, FLOOR_Y)
    p.if_zero_goto(var(TMP), f"{label}_not_above_floor")
    call_add_const(p, dy_var, dy_var, PLAYER_GRAVITY_SCREEN)
    p.emit(p.goto(f"{label}_after_vertical"))

    p.label(f"{label}_not_above_floor")
    p.call(SYS_GT, TMP, y_var, FLOOR_Y)
    p.if_zero_goto(var(TMP), f"{label}_after_vertical")
    p.emit(assign(dy_var, num(0)))
    p.emit(assign(y_var, var(FLOOR_Y)))
    p.emit(assign(frame_var, num(0)))
    p.emit(assign(DIGIT_CONST, num(PLAYER_STATE_DIVING)))
    call_eq(p, TMP, state_var, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{label}_land_from_dive")
    p.emit(assign(state_var, num(PLAYER_STATE_NORMAL)))
    p.emit(p.goto(f"{label}_after_vertical"))

    p.label(f"{label}_land_from_dive")
    p.emit(assign(state_var, num(PLAYER_STATE_LYING)))
    p.emit(assign(frame_var, num(0)))
    p.emit(assign(lie_timer_var, num(PLAYER_LIE_TIMER_INITIAL)))

    p.label(f"{label}_after_vertical")
    if_var_nonzero_goto(p, power_var, f"{label}_power_pressed")
    p.emit(p.goto(f"{label}_after_power"))

    p.label(f"{label}_power_pressed")
    p.emit(assign(DIGIT_CONST, num(PLAYER_STATE_JUMP)))
    call_eq(p, TMP, state_var, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{label}_start_power_hit")
    p.emit(assign(DIGIT_CONST, num(PLAYER_STATE_NORMAL)))
    call_eq(p, TMP, state_var, DIGIT_CONST)
    p.if_zero_goto(var(TMP), f"{label}_after_power")
    if_var_nonzero_goto(p, input_x_var, f"{label}_start_dive")
    p.emit(p.goto(f"{label}_after_power"))

    p.label(f"{label}_start_power_hit")
    p.emit(assign(delay_var, num(PLAYER_POWER_HIT_START_DELAY)))
    p.emit(assign(frame_var, num(0)))
    p.emit(assign(state_var, num(PLAYER_STATE_POWER_HIT)))
    p.emit(assign(sound_pika_var, num(1)))
    p.emit(p.goto(f"{label}_after_power"))

    p.label(f"{label}_start_dive")
    p.emit(assign(state_var, num(PLAYER_STATE_DIVING)))
    p.emit(assign(frame_var, num(0)))
    p.emit(assign(dive_dir_var, var(input_x_var)))
    p.emit(assign(dy_var, num(PLAYER_DIVE_Y_VELOCITY_SCREEN)))
    p.emit(assign(sound_chu_var, num(1)))

    p.label(f"{label}_after_power")
    p.emit(assign(DIGIT_CONST, num(PLAYER_STATE_JUMP)))
    call_eq(p, TMP, state_var, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{label}_frame_jump")
    p.emit(assign(DIGIT_CONST, num(PLAYER_STATE_POWER_HIT)))
    call_eq(p, TMP, state_var, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{label}_frame_power")
    p.emit(assign(DIGIT_CONST, num(PLAYER_STATE_NORMAL)))
    call_eq(p, TMP, state_var, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{label}_frame_normal")
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_frame_jump")
    call_add_const(p, frame_var, frame_var, 1)
    p.emit(assign(DIGIT_CONST, num(PLAYER_JUMP_FRAME_MODULO)))
    call_mod(p, frame_var, frame_var, DIGIT_CONST)
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_frame_power")
    p.emit(assign(DIGIT_CONST, num(PLAYER_POWER_HIT_DELAY_THRESHOLD)))
    p.call(SYS_LT, TMP, delay_var, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{label}_advance_power_frame")
    call_add_const(p, delay_var, delay_var, -1)
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_advance_power_frame")
    call_add_const(p, frame_var, frame_var, 1)
    p.emit(assign(DIGIT_CONST, num(PLAYER_POWER_HIT_LAST_FRAME)))
    p.call(SYS_GT, TMP, frame_var, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{label}_power_frame_finished")
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_power_frame_finished")
    p.emit(assign(frame_var, num(0)))
    p.emit(assign(state_var, num(PLAYER_STATE_JUMP)))
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_frame_normal")
    call_add_const(p, delay_var, delay_var, 1)
    p.emit(assign(DIGIT_CONST, num(PLAYER_NORMAL_SWING_DELAY_LIMIT)))
    p.call(SYS_GT, TMP, delay_var, DIGIT_CONST)
    p.if_zero_goto(var(TMP), f"{label}_done")
    p.emit(assign(delay_var, num(0)))
    call_add(p, TMP, frame_var, swing_dir_var)
    p.emit(assign(DIGIT_CONST, num(PLAYER_NORMAL_SWING_FRAME_MIN)))
    p.call(SYS_LT, KEY, TMP, DIGIT_CONST)
    if_var_nonzero_goto(p, KEY, f"{label}_reverse_swing")
    p.emit(assign(DIGIT_CONST, num(PLAYER_NORMAL_SWING_FRAME_MAX)))
    p.call(SYS_GT, KEY, TMP, DIGIT_CONST)
    if_var_nonzero_goto(p, KEY, f"{label}_reverse_swing")
    p.emit(p.goto(f"{label}_apply_swing"))

    p.label(f"{label}_reverse_swing")
    call_sub(p, swing_dir_var, ZERO, swing_dir_var)

    p.label(f"{label}_apply_swing")
    call_add(p, frame_var, frame_var, swing_dir_var)
    p.label(f"{label}_done")


def process_ball_world(p: Program) -> None:
    p.emit(assign(BALL_TOUCH_GROUND, num(0)))
    p.emit(assign(BALL_PREV2_X, var(BALL_PREV_X)))
    p.emit(assign(BALL_PREV2_Y, var(BALL_PREV_Y)))
    p.emit(assign(BALL_PREV_X, var(BALL_X)))
    p.emit(assign(BALL_PREV_Y, var(BALL_Y)))

    p.emit(assign(DIGIT_CONST, num(BALL_ROTATION_VELOCITY_DIVISOR_SCREEN)))
    call_div(p, TMP, BALL_DX, DIGIT_CONST)
    call_add(p, BALL_FINE_ROT, BALL_FINE_ROT, TMP)
    p.call(SYS_LT, TMP, BALL_FINE_ROT, ZERO)
    p.if_zero_goto(var(TMP), "ball_world_fine_not_negative")
    call_add_const(p, BALL_FINE_ROT, BALL_FINE_ROT, 50)
    p.label("ball_world_fine_not_negative")
    p.emit(assign(DIGIT_CONST, num(50)))
    p.call(SYS_GT, TMP, BALL_FINE_ROT, DIGIT_CONST)
    p.if_zero_goto(var(TMP), "ball_world_fine_not_high")
    call_add_const(p, BALL_FINE_ROT, BALL_FINE_ROT, -50)
    p.label("ball_world_fine_not_high")
    p.emit(assign(DIGIT_CONST, num(10)))
    call_div(p, BALL_ROTATION, BALL_FINE_ROT, DIGIT_CONST)

    call_add(p, SIM_FUTURE, BALL_X, BALL_DX)
    p.call(SYS_LT, TMP, SIM_FUTURE, LEFT_WALL)
    p.if_zero_goto(var(TMP), "ball_world_not_left_wall")
    call_sub(p, BALL_DX, ZERO, BALL_DX)
    p.label("ball_world_not_left_wall")
    p.call(SYS_GT, TMP, SIM_FUTURE, RIGHT_WALL)
    p.if_zero_goto(var(TMP), "ball_world_not_right_wall")
    call_sub(p, BALL_DX, ZERO, BALL_DX)
    p.label("ball_world_not_right_wall")

    call_add(p, SIM_FUTURE, BALL_Y, BALL_DY)
    p.call(SYS_LT, TMP, SIM_FUTURE, ZERO)
    p.if_zero_goto(var(TMP), "ball_world_not_ceiling")
    p.emit(assign(BALL_DY, num(BALL_CEILING_BOUNCE_DY_SCREEN)))
    p.label("ball_world_not_ceiling")

    call_sub(p, TMP, BALL_X, MID_X)
    call_abs(p, TMP, TMP)
    p.call(SYS_LT, TMP2, TMP, NET_HALF)
    p.if_zero_goto(var(TMP2), "ball_world_net_done")
    p.call(SYS_GT, TMP2, BALL_Y, NET_TOP)
    p.if_zero_goto(var(TMP2), "ball_world_net_done")
    p.call(SYS_GT, TMP2, BALL_Y, NET_BOTTOM)
    if_var_nonzero_goto(p, TMP2, "ball_world_net_side")
    p.call(SYS_GT, TMP2, BALL_DY, ZERO)
    p.if_zero_goto(var(TMP2), "ball_world_net_done")
    call_sub(p, BALL_DY, ZERO, BALL_DY)
    p.emit(p.goto("ball_world_net_done"))

    p.label("ball_world_net_side")
    p.call(SYS_LT, TMP2, BALL_X, MID_X)
    p.if_zero_goto(var(TMP2), "ball_world_net_right_side")
    call_abs(p, BALL_DX, BALL_DX)
    call_sub(p, BALL_DX, ZERO, BALL_DX)
    p.emit(p.goto("ball_world_net_done"))

    p.label("ball_world_net_right_side")
    call_abs(p, BALL_DX, BALL_DX)
    p.label("ball_world_net_done")

    call_add(p, SIM_FUTURE, BALL_Y, BALL_DY)
    p.call(SYS_GT, TMP, SIM_FUTURE, BALL_FLOOR_Y)
    p.if_zero_goto(var(TMP), "ball_world_not_landed")
    p.emit(assign(BALL_TOUCH_GROUND, num(1)))
    call_sub(p, BALL_DY, ZERO, BALL_DY)
    p.emit(assign(BALL_PUNCH_X, var(BALL_X)))
    p.emit(assign(BALL_Y, var(BALL_FLOOR_Y)))
    p.emit(assign(BALL_PUNCH_RADIUS, var(BALL_RADIUS)))
    call_add(p, BALL_PUNCH_Y, BALL_FLOOR_Y, BALL_RADIUS)
    p.emit(assign(BALL_SOUND_GROUND, num(1)))
    p.emit(p.goto("ball_world_done"))

    p.label("ball_world_not_landed")
    p.emit(assign(BALL_Y, var(SIM_FUTURE)))
    call_add(p, BALL_X, BALL_X, BALL_DX)
    call_add_const(p, BALL_DY, BALL_DY, BALL_GRAVITY_SCREEN)
    p.label("ball_world_done")


def apply_winning_score_reset(p: Program) -> None:
    p.call(SYS_LT, TMP, SCORE1, WINNING_SCORE)
    if_var_nonzero_goto(p, TMP, "score1_not_finished")
    p.emit(assign(PHASE, num(PHASE_GAME_END)))
    p.emit(assign(FRAME_COUNTER, num(0)))
    p.emit(assign(WINNER, num(1)))
    p.emit(assign(GAME_ENDED, num(1)))
    p.emit(assign(ROUND_ENDED, num(1)))
    p.emit(assign(SLOW_MOTION_FRAMES_LEFT, num(0)))
    p.emit(assign(SLOW_MOTION_SKIP, num(0)))
    p.emit(assign(P1_WINNER, num(1)))
    p.emit(assign(P2_WINNER, num(0)))
    p.emit(assign(P1_GAME_ENDED, num(1)))
    p.emit(assign(P2_GAME_ENDED, num(1)))
    p.emit(assign(P1_STATE, num(PLAYER_STATE_WIN)))
    p.emit(assign(P2_STATE, num(PLAYER_STATE_LOSE)))
    p.emit(assign(P1_FRAME, num(0)))
    p.emit(assign(P2_FRAME, num(0)))
    p.emit(assign(P1_DELAY, num(0)))
    p.emit(assign(P2_DELAY, num(0)))
    p.emit(assign(P1_SOUND_PIPIKACHU, num(1)))
    p.label("score1_not_finished")

    p.call(SYS_LT, TMP, SCORE2, WINNING_SCORE)
    if_var_nonzero_goto(p, TMP, "score2_not_finished")
    p.emit(assign(PHASE, num(PHASE_GAME_END)))
    p.emit(assign(FRAME_COUNTER, num(0)))
    p.emit(assign(WINNER, num(2)))
    p.emit(assign(GAME_ENDED, num(1)))
    p.emit(assign(ROUND_ENDED, num(1)))
    p.emit(assign(SLOW_MOTION_FRAMES_LEFT, num(0)))
    p.emit(assign(SLOW_MOTION_SKIP, num(0)))
    p.emit(assign(P1_WINNER, num(0)))
    p.emit(assign(P2_WINNER, num(1)))
    p.emit(assign(P1_GAME_ENDED, num(1)))
    p.emit(assign(P2_GAME_ENDED, num(1)))
    p.emit(assign(P1_STATE, num(PLAYER_STATE_LOSE)))
    p.emit(assign(P2_STATE, num(PLAYER_STATE_WIN)))
    p.emit(assign(P1_FRAME, num(0)))
    p.emit(assign(P2_FRAME, num(0)))
    p.emit(assign(P1_DELAY, num(0)))
    p.emit(assign(P2_DELAY, num(0)))
    p.emit(assign(P2_SOUND_PIPIKACHU, num(1)))
    p.label("score2_not_finished")


def emit_sound_flag(
    p: Program, flag_var: int, sound_id: int, side: int, label: str
) -> None:
    if_var_nonzero_goto(p, flag_var, f"{label}_play")
    p.emit(p.goto(f"{label}_done"))
    p.label(f"{label}_play")
    if_var_nonzero_goto(p, SFX_MODE, f"{label}_sound_on")
    p.emit(assign(flag_var, num(0)))
    p.emit(p.goto(f"{label}_done"))
    p.label(f"{label}_sound_on")
    play_sfx_const_side(p, sound_id, side, f"{label}_sfx")
    p.emit(assign(flag_var, num(0)))
    p.label(f"{label}_done")


def emit_ball_sound_flag(p: Program, flag_var: int, sound_id: int, label: str) -> None:
    if_var_nonzero_goto(p, flag_var, f"{label}_play")
    p.emit(p.goto(f"{label}_done"))
    p.label(f"{label}_play")
    if_var_nonzero_goto(p, SFX_MODE, f"{label}_sound_on")
    p.emit(assign(flag_var, num(0)))
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_sound_on")
    p.emit(assign(TMP2, num(0)))
    p.call(SYS_LT, TMP, BALL_X, MID_X)
    if_var_nonzero_goto(p, TMP, f"{label}_left")
    p.call(SYS_GT, TMP, BALL_X, MID_X)
    if_var_nonzero_goto(p, TMP, f"{label}_right")
    p.emit(p.goto(f"{label}_side_ready"))

    p.label(f"{label}_left")
    p.emit(assign(TMP2, num(-1)))
    p.emit(p.goto(f"{label}_side_ready"))

    p.label(f"{label}_right")
    p.emit(assign(TMP2, num(1)))

    p.label(f"{label}_side_ready")
    play_sfx_var_side(p, sound_id, TMP2, f"{label}_sfx")
    p.emit(assign(flag_var, num(0)))
    p.label(f"{label}_done")


def play_bgm_if_enabled(p: Program, label: str) -> None:
    if_var_nonzero_goto(p, BGM_ON, f"{label}_play")
    p.emit(p.goto(f"{label}_done"))
    p.label(f"{label}_play")
    p.call(SYS_PLAY_AUDIO, BGM_AUDIO_SLOT, 1, 35)
    p.label(f"{label}_done")


def emit_sound_flags(p: Program, prefix: str) -> None:
    for event_key, flag_name, sound_id, side in SFX_ROUND_EVENTS:
        label = f"{prefix}_{event_key}"
        flag_var = VARS[flag_name]
        if side == "ball_x":
            emit_ball_sound_flag(p, flag_var, sound_id, label)
        else:
            emit_sound_flag(p, flag_var, sound_id, side, label)


def emit_ui_sound_flags(p: Program, prefix: str) -> None:
    for event_key, flag_name, sound_id, side in SFX_UI_EVENTS:
        emit_sound_flag(p, VARS[flag_name], sound_id, side, f"{prefix}_{event_key}")


def apply_round_slow_motion_gate(p: Program) -> None:
    if_var_nonzero_goto(p, SLOW_MOTION_FRAMES_LEFT, "round_slow_motion_active")
    p.emit(p.goto("round_after_slow_motion_gate"))

    p.label("round_slow_motion_active")
    call_add_const(p, SLOW_MOTION_SKIP, SLOW_MOTION_SKIP, 1)
    p.emit(assign(DIGIT_CONST, num(PLAYER_STATE_WIN)))
    call_mod(p, TMP, SLOW_MOTION_SKIP, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, "round_slow_motion_render_only")
    call_add_const(p, SLOW_MOTION_FRAMES_LEFT, SLOW_MOTION_FRAMES_LEFT, -1)
    p.emit(assign(SLOW_MOTION_SKIP, num(0)))
    p.emit(p.goto("round_after_slow_motion_gate"))

    p.label("round_slow_motion_render_only")
    draw_round_scene(p, "round_slow_motion")
    wait_and_loop(p)

    p.label("round_after_slow_motion_gate")


def update_game_end_player_animation(
    p: Program, state_var: int, frame_var: int, delay_var: int, label: str
) -> None:
    p.emit(assign(DIGIT_CONST, num(5)))
    call_eq(p, TMP, state_var, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{label}_animate")
    p.emit(assign(DIGIT_CONST, num(PLAYER_STATE_LOSE)))
    call_eq(p, TMP, state_var, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{label}_animate")
    p.emit(p.goto(f"{label}_done"))

    p.label(f"{label}_animate")
    p.emit(assign(DIGIT_CONST, num(PLAYER_GAME_END_ANIM_LAST_FRAME)))
    p.call(SYS_LT, TMP, frame_var, DIGIT_CONST)
    p.if_zero_goto(var(TMP), f"{label}_done")
    call_add_const(p, delay_var, delay_var, 1)
    p.emit(assign(DIGIT_CONST, num(PLAYER_GAME_END_ANIM_DELAY_LIMIT)))
    p.call(SYS_GT, TMP, delay_var, DIGIT_CONST)
    p.if_zero_goto(var(TMP), f"{label}_done")
    p.emit(assign(delay_var, num(0)))
    call_add_const(p, frame_var, frame_var, 1)
    p.label(f"{label}_done")


def draw_background_sprites(p: Program) -> None:
    sky_sx, sky_sy, sky_sw, sky_sh, sky_dw, sky_dh = render_values("background_sky_tile", 6)
    sky_y_start, sky_y_end, sky_y_step = render_values("background_sky_y_range", 3)
    for y in range(sky_y_start, sky_y_end, sky_y_step):
        for x in range(0, WINDOW_WIDTH, sky_dw):
            draw_sprite_const(p, sky_sx, sky_sy, sky_sw, sky_sh, x, y, sky_dw, sky_dh)

    draw_render_sprite_const(p, "background_ground")

    grass_sx, grass_sy, grass_sw, grass_sh, grass_dw, grass_dh = render_values(
        "background_top_grass_tile", 6
    )
    grass_y = render_values("background_top_grass_y", 1)[0]
    for x in range(0, WINDOW_WIDTH, grass_dw):
        draw_sprite_const(p, grass_sx, grass_sy, grass_sw, grass_sh, x, grass_y, grass_dw, grass_dh)

    floor_sx, floor_sy, floor_sw, floor_sh, floor_dw, floor_dh = render_values(
        "background_floor_mid_tile", 6
    )
    floor_x_start, floor_x_end, floor_x_step = render_values("background_floor_mid_x_range", 3)
    floor_y = render_values("background_floor_mid_y", 1)[0]
    for x in range(floor_x_start, floor_x_end, floor_x_step):
        draw_sprite_const(p, floor_sx, floor_sy, floor_sw, floor_sh, x, floor_y, floor_dw, floor_dh)
    draw_render_sprite_const(p, "background_floor_left")
    draw_render_sprite_const(p, "background_floor_right")

    front_sx, front_sy, front_sw, front_sh, front_dw, front_dh = render_values(
        "background_front_tile", 6
    )
    for y in render_values("background_front_y_values"):
        for x in range(0, WINDOW_WIDTH, front_dw):
            draw_sprite_const(p, front_sx, front_sy, front_sw, front_sh, x, y, front_dw, front_dh)

    (
        net_sx,
        net_sy,
        net_sw,
        net_sh,
        net_x,
        net_y_start,
        net_y_end,
        net_y_step,
        net_dw,
        net_dh,
    ) = render_values("background_net_tile", 10)
    for y in range(net_y_start, net_y_end, net_y_step):
        draw_sprite_const(p, net_sx, net_sy, net_sw, net_sh, net_x, y, net_dw, net_dh)
    draw_render_sprite_const(p, "background_net_top")


PLAYER_FRAMES = SPRITE_FRAMES["PLAYER_FRAME"]
BALL_FRAMES = SPRITE_FRAMES["BALL_FRAME"]

CLOUDS = [
    (CLOUD1_X, CLOUD1_Y, CLOUD1_VX, CLOUD1_SIZE_TURN),
    (CLOUD2_X, CLOUD2_Y, CLOUD2_VX, CLOUD2_SIZE_TURN),
    (CLOUD3_X, CLOUD3_Y, CLOUD3_VX, CLOUD3_SIZE_TURN),
    (CLOUD4_X, CLOUD4_Y, CLOUD4_VX, CLOUD4_SIZE_TURN),
    (CLOUD5_X, CLOUD5_Y, CLOUD5_VX, CLOUD5_SIZE_TURN),
    (CLOUD6_X, CLOUD6_Y, CLOUD6_VX, CLOUD6_SIZE_TURN),
    (CLOUD7_X, CLOUD7_Y, CLOUD7_VX, CLOUD7_SIZE_TURN),
    (CLOUD8_X, CLOUD8_Y, CLOUD8_VX, CLOUD8_SIZE_TURN),
    (CLOUD9_X, CLOUD9_Y, CLOUD9_VX, CLOUD9_SIZE_TURN),
    (CLOUD10_X, CLOUD10_Y, CLOUD10_VX, CLOUD10_SIZE_TURN),
]

WAVE_Y_COORDS = [
    WAVE1_Y,
    WAVE2_Y,
    WAVE3_Y,
    WAVE4_Y,
    WAVE5_Y,
    WAVE6_Y,
    WAVE7_Y,
    WAVE8_Y,
    WAVE9_Y,
    WAVE10_Y,
    WAVE11_Y,
    WAVE12_Y,
    WAVE13_Y,
    WAVE14_Y,
    WAVE15_Y,
    WAVE16_Y,
    WAVE17_Y,
    WAVE18_Y,
    WAVE19_Y,
    WAVE20_Y,
    WAVE21_Y,
    WAVE22_Y,
    WAVE23_Y,
    WAVE24_Y,
    WAVE25_Y,
    WAVE26_Y,
    WAVE27_Y,
]


def update_player_animation(p: Program, state_var: int, frame_var: int, prefix: str) -> None:
    for state in sorted(PLAYER_ANIM_RULES):
        p.emit(assign(PLAYER_FRAME_CONST, num(state)))
        call_eq(p, TMP, state_var, PLAYER_FRAME_CONST)
        if_var_nonzero_goto(p, TMP, f"{prefix}_state{state}")
    p.emit(assign(frame_var, num(0)))
    p.emit(p.goto(f"{prefix}_anim_done"))

    for state, (frame_divisor, frame_modulo) in sorted(PLAYER_ANIM_RULES.items()):
        p.label(f"{prefix}_state{state}")
        p.emit(assign(ANIM_DIV, num(frame_divisor)))
        call_div(p, ANIM_MOD, FRAME_COUNTER, ANIM_DIV)
        p.emit(assign(PLAYER_FRAME_CONST, num(frame_modulo)))
        call_mod(p, frame_var, ANIM_MOD, PLAYER_FRAME_CONST)
        p.emit(p.goto(f"{prefix}_anim_done"))
    p.label(f"{prefix}_anim_done")


def draw_player_animated(
    p: Program, state_var: int, frame_var: int, x_expr: str, y_expr: str, prefix: str, flip: int
) -> None:
    for state, sprite_indices in sorted(PLAYER_DRAW_STATES.items()):
        p.emit(assign(DIGIT_CONST, num(state)))
        call_eq(p, TMP, state_var, DIGIT_CONST)
        p.if_zero_goto(var(TMP), f"{prefix}_state_{state}_skip")
        for frame, sprite_index in enumerate(sprite_indices):
            p.emit(assign(DIGIT_CONST, num(frame)))
            call_eq(p, TMP2, frame_var, DIGIT_CONST)
            p.if_zero_goto(var(TMP2), f"{prefix}_state_{state}_frame_{frame}_skip")
            sx, sy, sw, sh = PLAYER_FRAMES[sprite_index]
            draw_sprite_values(p, sx, sy, sw, sh, x_expr, y_expr, 128, 128, flip)
            p.label(f"{prefix}_state_{state}_frame_{frame}_skip")
        p.label(f"{prefix}_state_{state}_skip")


def draw_player_with_original_flip(
    p: Program,
    state_var: int,
    frame_var: int,
    dive_dir_var: int,
    x_expr: str,
    y_expr: str,
    prefix: str,
    is_player2: bool,
) -> None:
    p.emit(assign(DIGIT_CONST, num(PLAYER_STATE_DIVING)))
    call_eq(p, TMP, state_var, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{prefix}_check_dive_dir")
    p.emit(assign(DIGIT_CONST, num(PLAYER_STATE_LYING)))
    call_eq(p, TMP, state_var, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{prefix}_check_dive_dir")
    draw_player_animated(
        p,
        state_var,
        frame_var,
        x_expr,
        y_expr,
        f"{prefix}_default_flip",
        1 if is_player2 else 0,
    )
    p.emit(p.goto(f"{prefix}_done"))

    p.label(f"{prefix}_check_dive_dir")
    call_eq(p, TMP, dive_dir_var, ONE if is_player2 else NEG_ONE)
    if_var_nonzero_goto(p, TMP, f"{prefix}_dive_direction_matched")
    draw_player_animated(
        p,
        state_var,
        frame_var,
        x_expr,
        y_expr,
        f"{prefix}_dive_unmatched_flip",
        1 if is_player2 else 0,
    )
    p.emit(p.goto(f"{prefix}_done"))

    p.label(f"{prefix}_dive_direction_matched")
    draw_player_animated(
        p,
        state_var,
        frame_var,
        x_expr,
        y_expr,
        f"{prefix}_dive_matched_flip",
        0 if is_player2 else 1,
    )
    p.label(f"{prefix}_done")


def draw_ball_animated(p: Program, prefix: str) -> None:
    call_clamp(p, TMP2, BALL_ROTATION, 0, 5)
    p.emit(assign(DIGIT_CONST, num(2)))
    call_mul(p, CLOUD_DRAW_W, BALL_RADIUS, DIGIT_CONST)
    p.emit(assign(CLOUD_DRAW_H, var(CLOUD_DRAW_W)))
    for frame, (sx, sy, sw, sh) in enumerate(BALL_FRAMES[:6]):
        p.emit(assign(DIGIT_CONST, num(frame)))
        call_eq(p, TMP, TMP2, DIGIT_CONST)
        p.if_zero_goto(var(TMP), f"{prefix}_ball_frame_{frame}_skip")
        draw_sprite_exprs(
            p,
            sx,
            sy,
            sw,
            sh,
            var(BALL_SPRITE_X),
            var(BALL_SPRITE_Y),
            var(CLOUD_DRAW_W),
            var(CLOUD_DRAW_H),
        )
        p.label(f"{prefix}_ball_frame_{frame}_skip")


def draw_ball_power_trail(p: Program, prefix: str) -> None:
    if_var_nonzero_goto(p, BALL_IS_POWER_HIT, f"{prefix}_ball_power_trail_draw")
    p.emit(p.goto(f"{prefix}_ball_power_trail_done"))

    p.label(f"{prefix}_ball_power_trail_draw")
    p.emit(assign(DIGIT_CONST, num(2)))
    call_mul(p, CLOUD_DRAW_W, BALL_RADIUS, DIGIT_CONST)
    p.emit(assign(CLOUD_DRAW_H, var(CLOUD_DRAW_W)))
    call_sub(p, CLOUD_DRAW_X, BALL_PREV_X, BALL_RADIUS)
    call_sub(p, CLOUD_DRAW_Y, BALL_PREV_Y, BALL_RADIUS)
    draw_sprite_exprs(
        p,
        298,
        158,
        40,
        40,
        var(CLOUD_DRAW_X),
        var(CLOUD_DRAW_Y),
        var(CLOUD_DRAW_W),
        var(CLOUD_DRAW_H),
    )
    call_sub(p, CLOUD_DRAW_X, BALL_PREV2_X, BALL_RADIUS)
    call_sub(p, CLOUD_DRAW_Y, BALL_PREV2_Y, BALL_RADIUS)
    draw_sprite_exprs(
        p,
        382,
        158,
        40,
        40,
        var(CLOUD_DRAW_X),
        var(CLOUD_DRAW_Y),
        var(CLOUD_DRAW_W),
        var(CLOUD_DRAW_H),
    )
    p.label(f"{prefix}_ball_power_trail_done")


def draw_punch_effect(p: Program, prefix: str) -> None:
    if_var_nonzero_goto(p, BALL_PUNCH_RADIUS, f"{prefix}_ball_punch_effect_draw")
    p.emit(p.goto(f"{prefix}_ball_punch_effect_done"))

    p.label(f"{prefix}_ball_punch_effect_draw")
    call_sub(p, CLOUD_DRAW_X, BALL_PUNCH_X, BALL_PUNCH_RADIUS)
    call_sub(p, CLOUD_DRAW_Y, BALL_PUNCH_Y, BALL_PUNCH_RADIUS)
    p.emit(assign(DIGIT_CONST, num(2)))
    call_mul(p, CLOUD_DRAW_W, BALL_PUNCH_RADIUS, DIGIT_CONST)
    p.emit(assign(CLOUD_DRAW_H, var(CLOUD_DRAW_W)))
    draw_sprite_exprs(
        p,
        340,
        158,
        40,
        40,
        var(CLOUD_DRAW_X),
        var(CLOUD_DRAW_Y),
        var(CLOUD_DRAW_W),
        var(CLOUD_DRAW_H),
    )
    call_add_const(p, BALL_PUNCH_RADIUS, BALL_PUNCH_RADIUS, -BALL_PUNCH_EFFECT_DECAY_SCREEN)
    p.call(SYS_LT, TMP, BALL_PUNCH_RADIUS, ZERO)
    p.if_zero_goto(var(TMP), f"{prefix}_ball_punch_effect_done")
    p.emit(assign(BALL_PUNCH_RADIUS, num(0)))
    p.label(f"{prefix}_ball_punch_effect_done")


def init_cloud_values(
    p: Program,
    x_var: int,
    y_var: int,
    vx_var: int,
    size_turn_var: int,
    x: int,
    y: int,
    vx: int,
    size_turn: int,
) -> None:
    p.emit(assign(x_var, num(x)))
    p.emit(assign(y_var, num(y)))
    p.emit(assign(vx_var, num(vx)))
    p.emit(assign(size_turn_var, num(size_turn)))


def init_cloud_from_rng(
    p: Program,
    x_var: int,
    y_var: int,
    vx_var: int,
    size_turn_var: int,
) -> None:
    call_rand_mod(p, x_var, 500)
    p.emit(assign(DIGIT_CONST, num(2)))
    call_mul(p, x_var, x_var, DIGIT_CONST)
    call_add_const(p, x_var, x_var, -136)

    call_rand_mod(p, y_var, 152)
    p.emit(assign(DIGIT_CONST, num(2)))
    call_mul(p, y_var, y_var, DIGIT_CONST)

    call_rand_mod(p, vx_var, 2)
    call_add_const(p, vx_var, vx_var, 1)
    p.emit(assign(DIGIT_CONST, num(2)))
    call_mul(p, vx_var, vx_var, DIGIT_CONST)

    call_rand_mod(p, size_turn_var, 11)


def update_environment_animation(p: Program, prefix: str) -> None:
    for idx, (x_var, y_var, vx_var, size_turn_var) in enumerate(CLOUDS, start=1):
        call_add(p, x_var, x_var, vx_var)
        p.emit(assign(DIGIT_CONST, num(WINDOW_WIDTH)))
        p.call(SYS_GT, TMP, x_var, DIGIT_CONST)
        p.if_zero_goto(var(TMP), f"{prefix}_cloud_{idx}_wrap_done")
        p.emit(assign(x_var, num(-136)))
        call_rand_mod(p, y_var, 152)
        p.emit(assign(DIGIT_CONST, num(2)))
        call_mul(p, y_var, y_var, DIGIT_CONST)
        call_rand_mod(p, vx_var, 2)
        call_add_const(p, vx_var, vx_var, 1)
        p.emit(assign(DIGIT_CONST, num(2)))
        call_mul(p, vx_var, vx_var, DIGIT_CONST)
        p.label(f"{prefix}_cloud_{idx}_wrap_done")

        call_add_const(p, size_turn_var, size_turn_var, 1)
        p.emit(assign(DIGIT_CONST, num(11)))
        call_mod(p, size_turn_var, size_turn_var, DIGIT_CONST)

    call_add(p, WAVE_VERTICAL, WAVE_VERTICAL, WAVE_VELOCITY)
    p.emit(assign(DIGIT_CONST, num(32)))
    p.call(SYS_GT, TMP, WAVE_VERTICAL, DIGIT_CONST)
    p.if_zero_goto(var(TMP), f"{prefix}_wave_not_too_high")
    p.emit(assign(WAVE_VERTICAL, num(32)))
    p.emit(assign(WAVE_VELOCITY, num(-1)))
    p.label(f"{prefix}_wave_not_too_high")

    p.call(SYS_LT, TMP, WAVE_VERTICAL, ZERO)
    p.if_zero_goto(var(TMP), f"{prefix}_wave_not_below_zero")
    p.call(SYS_LT, TMP2, WAVE_VELOCITY, ZERO)
    p.if_zero_goto(var(TMP2), f"{prefix}_wave_not_below_zero")
    p.emit(assign(WAVE_VELOCITY, num(2)))
    call_rand_mod(p, WAVE_VERTICAL, 40)
    call_sub(p, WAVE_VERTICAL, ZERO, WAVE_VERTICAL)
    p.label(f"{prefix}_wave_not_below_zero")

    for y_var in WAVE_Y_COORDS:
        p.emit(assign(DIGIT_CONST, num(2)))
        call_mul(p, TMP, WAVE_VERTICAL, DIGIT_CONST)
        p.emit(assign(DIGIT_CONST, num(628)))
        call_sub(p, y_var, DIGIT_CONST, TMP)
        call_rand_mod(p, TMP, 3)
        p.emit(assign(DIGIT_CONST, num(2)))
        call_mul(p, TMP, TMP, DIGIT_CONST)
        call_add(p, y_var, y_var, TMP)

    p.emit(assign(DIGIT_CONST, num(12)))
    call_mod(p, WAVE_PHASE, FRAME_COUNTER, DIGIT_CONST)


def draw_cloud_sprite(
    p: Program, x_var: int, y_var: int, size_turn_var: int, prefix: str
) -> None:
    call_add_const(p, TMP, size_turn_var, -5)
    call_abs(p, TMP, TMP)
    p.emit(assign(DIGIT_CONST, num(5)))
    call_sub(p, CLOUD_SIZE_DIFF, DIGIT_CONST, TMP)
    call_sub(p, CLOUD_DRAW_X, x_var, CLOUD_SIZE_DIFF)
    call_sub(p, CLOUD_DRAW_Y, y_var, CLOUD_SIZE_DIFF)
    p.emit(assign(DIGIT_CONST, num(2)))
    call_mul(p, TMP, CLOUD_SIZE_DIFF, DIGIT_CONST)
    call_add_const(p, CLOUD_DRAW_W, TMP, 96)
    call_add_const(p, CLOUD_DRAW_H, TMP, 48)
    draw_sprite_exprs(
        p,
        100,
        90,
        48,
        24,
        var(CLOUD_DRAW_X),
        var(CLOUD_DRAW_Y),
        var(CLOUD_DRAW_W),
        var(CLOUD_DRAW_H),
    )


def draw_environment_sprites(p: Program) -> None:
    for idx, (x_var, y_var, _vx_var, size_turn_var) in enumerate(CLOUDS, start=1):
        draw_cloud_sprite(p, x_var, y_var, size_turn_var, f"cloud_draw_{idx}")

    wave_sx, wave_sy, wave_sw, wave_sh, wave_dw, wave_dh = render_values("wave_sprite", 6)
    for idx, y_var in enumerate(WAVE_Y_COORDS):
        call_add_const(p, TMP, y_var, -64)
        x = idx * 32
        draw_sprite_values(p, wave_sx, wave_sy, wave_sw, wave_sh, num(x), var(TMP), wave_dw, wave_dh)


def draw_playfield_sprites(p: Program, prefix: str) -> None:
    call_add_const(p, P1_SPRITE_X, P1_X, -64)
    call_add_const(p, P1_SPRITE_Y, P1_Y, -64)
    call_add_const(p, P2_SPRITE_X, P2_X, -64)
    call_add_const(p, P2_SPRITE_Y, P2_Y, -64)
    call_sub(p, BALL_SPRITE_X, BALL_X, BALL_RADIUS)
    call_sub(p, BALL_SPRITE_Y, BALL_Y, BALL_RADIUS)

    shadow_sx, shadow_sy, shadow_sw, shadow_sh, shadow_y, shadow_dw, shadow_dh = render_values(
        "shadow_sprite", 7
    )
    call_add_const(p, TMP, P1_X, -(shadow_dw // 2))
    draw_sprite_values(
        p, shadow_sx, shadow_sy, shadow_sw, shadow_sh, var(TMP), num(shadow_y), shadow_dw, shadow_dh
    )
    call_add_const(p, TMP, P2_X, -(shadow_dw // 2))
    draw_sprite_values(
        p, shadow_sx, shadow_sy, shadow_sw, shadow_sh, var(TMP), num(shadow_y), shadow_dw, shadow_dh
    )
    call_add_const(p, TMP, BALL_X, -(shadow_dw // 2))
    draw_sprite_values(
        p, shadow_sx, shadow_sy, shadow_sw, shadow_sh, var(TMP), num(shadow_y), shadow_dw, shadow_dh
    )

    draw_player_with_original_flip(
        p,
        P1_STATE,
        P1_FRAME,
        P1_DIVE_DIR,
        var(P1_SPRITE_X),
        var(P1_SPRITE_Y),
        f"{prefix}_p1",
        False,
    )
    draw_player_with_original_flip(
        p,
        P2_STATE,
        P2_FRAME,
        P2_DIVE_DIR,
        var(P2_SPRITE_X),
        var(P2_SPRITE_Y),
        f"{prefix}_p2",
        True,
    )
    draw_ball_power_trail(p, prefix)
    draw_ball_animated(p, prefix)
    draw_punch_effect(p, prefix)


def digit_frame(digit: int) -> tuple[int, int, int, int]:
    if digit <= 7:
        return 204 + 34 * digit, 124, 32, 32
    return 2 + 34 * (digit - 8), 158, 32, 32


def draw_digit_sprite(p: Program, digit_var: int, x: int, y: int, prefix: str) -> None:
    for digit in range(10):
        p.emit(assign(DIGIT_CONST, num(digit)))
        call_eq(p, KEY, digit_var, DIGIT_CONST)
        p.if_zero_goto(var(KEY), f"{prefix}_{digit}_skip")
        sx, sy, sw, sh = digit_frame(digit)
        draw_sprite_const(p, sx, sy, sw, sh, x, y, 64, 64)
        p.label(f"{prefix}_{digit}_skip")


def draw_score_sprites(p: Program, score_var: int, x: int, y: int, prefix: str) -> None:
    call_div(p, DIGIT_TENS, score_var, TEN)
    call_mod(p, DIGIT_ONES, score_var, TEN)
    draw_digit_sprite(p, DIGIT_TENS, x, y, f"{prefix}_tens")
    draw_digit_sprite(p, DIGIT_ONES, x + 64, y, f"{prefix}_ones")


def draw_game_start_message(p: Program, prefix: str) -> None:
    msg_sx, msg_sy, msg_sw, msg_sh = render_values("game_start_message_source", 4)
    p.emit(assign(DIGIT_CONST, num(96)))
    call_mul(p, CLOUD_DRAW_W, DIGIT_CONST, FRAME_COUNTER)
    p.emit(assign(DIGIT_CONST, num(MESSAGE_GROW_FRAMES)))
    call_div(p, CLOUD_DRAW_W, CLOUD_DRAW_W, DIGIT_CONST)
    if_var_nonzero_goto(p, CLOUD_DRAW_W, f"{prefix}_game_start_has_width")
    p.emit(p.goto(f"{prefix}_game_start_done"))

    p.label(f"{prefix}_game_start_has_width")
    p.emit(assign(DIGIT_CONST, num(24)))
    call_mul(p, CLOUD_DRAW_H, DIGIT_CONST, FRAME_COUNTER)
    p.emit(assign(DIGIT_CONST, num(MESSAGE_GROW_FRAMES)))
    call_div(p, CLOUD_DRAW_H, CLOUD_DRAW_H, DIGIT_CONST)
    if_var_nonzero_goto(p, CLOUD_DRAW_H, f"{prefix}_game_start_has_height")
    p.emit(p.goto(f"{prefix}_game_start_done"))

    p.label(f"{prefix}_game_start_has_height")
    p.emit(assign(DIGIT_CONST, num(2)))
    call_mul(p, TMP, CLOUD_DRAW_W, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(432)))
    call_sub(p, CLOUD_DRAW_X, DIGIT_CONST, TMP)
    p.emit(assign(DIGIT_CONST, num(4)))
    call_mul(p, TMP, CLOUD_DRAW_H, DIGIT_CONST)
    call_add_const(p, CLOUD_DRAW_Y, TMP, 100)
    p.emit(assign(DIGIT_CONST, num(4)))
    call_mul(p, CLOUD_DRAW_W, CLOUD_DRAW_W, DIGIT_CONST)
    call_mul(p, CLOUD_DRAW_H, CLOUD_DRAW_H, DIGIT_CONST)
    draw_sprite_exprs(
        p,
        msg_sx,
        msg_sy,
        msg_sw,
        msg_sh,
        var(CLOUD_DRAW_X),
        var(CLOUD_DRAW_Y),
        var(CLOUD_DRAW_W),
        var(CLOUD_DRAW_H),
    )
    p.label(f"{prefix}_game_start_done")


def draw_ready_message(p: Program, prefix: str) -> None:
    p.emit(assign(DIGIT_CONST, num(READY_BLINK_DIVISOR)))
    call_div(p, TMP, FRAME_COUNTER, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(READY_BLINK_MODULO)))
    call_mod(p, TMP, TMP, DIGIT_CONST)
    call_eq(p, TMP2, TMP, ONE)
    if_var_nonzero_goto(p, TMP2, f"{prefix}_ready_draw")
    p.emit(p.goto(f"{prefix}_ready_done"))
    p.label(f"{prefix}_ready_draw")
    draw_render_sprite_const(p, "ready_message")
    p.label(f"{prefix}_ready_done")


def draw_game_end_message(p: Program, prefix: str) -> None:
    p.emit(assign(DIGIT_CONST, num(MESSAGE_GROW_FRAMES)))
    p.call(SYS_LT, TMP, FRAME_COUNTER, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{prefix}_game_end_grow")
    draw_render_sprite_const(p, "game_end_message")
    p.emit(p.goto(f"{prefix}_game_end_done"))

    p.label(f"{prefix}_game_end_grow")
    p.emit(assign(DIGIT_CONST, num(MESSAGE_GROW_FRAMES)))
    call_sub(p, CLOUD_DRAW_W, DIGIT_CONST, FRAME_COUNTER)
    p.emit(assign(DIGIT_CONST, num(96)))
    call_mul(p, CLOUD_DRAW_W, CLOUD_DRAW_W, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(MESSAGE_GROW_FRAMES)))
    call_div(p, CLOUD_DRAW_W, CLOUD_DRAW_W, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(2)))
    call_mul(p, CLOUD_DRAW_W, CLOUD_DRAW_W, DIGIT_CONST)

    p.emit(assign(DIGIT_CONST, num(MESSAGE_GROW_FRAMES)))
    call_sub(p, CLOUD_DRAW_H, DIGIT_CONST, FRAME_COUNTER)
    p.emit(assign(DIGIT_CONST, num(24)))
    call_mul(p, CLOUD_DRAW_H, CLOUD_DRAW_H, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(MESSAGE_GROW_FRAMES)))
    call_div(p, CLOUD_DRAW_H, CLOUD_DRAW_H, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(2)))
    call_mul(p, CLOUD_DRAW_H, CLOUD_DRAW_H, DIGIT_CONST)

    p.emit(assign(DIGIT_CONST, num(2)))
    call_mul(p, TMP, CLOUD_DRAW_W, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(336)))
    call_sub(p, CLOUD_DRAW_X, DIGIT_CONST, TMP)
    p.emit(assign(DIGIT_CONST, num(2)))
    call_mul(p, TMP, CLOUD_DRAW_H, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(100)))
    call_sub(p, CLOUD_DRAW_Y, DIGIT_CONST, TMP)
    p.emit(assign(DIGIT_CONST, num(4)))
    call_mul(p, TMP, CLOUD_DRAW_W, DIGIT_CONST)
    call_add_const(p, CLOUD_DRAW_W, TMP, 192)
    p.emit(assign(DIGIT_CONST, num(4)))
    call_mul(p, TMP, CLOUD_DRAW_H, DIGIT_CONST)
    call_add_const(p, CLOUD_DRAW_H, TMP, 48)
    draw_sprite_exprs(
        p,
        *render_values("game_end_message", 8)[:4],
        var(CLOUD_DRAW_X),
        var(CLOUD_DRAW_Y),
        var(CLOUD_DRAW_W),
        var(CLOUD_DRAW_H),
    )
    p.label(f"{prefix}_game_end_done")


def draw_fade_overlay(p: Program, prefix: str) -> None:
    p.emit(assign(FADE_ALPHA, num(0)))

    p.emit(assign(DIGIT_CONST, num(PHASE_AFTER_MENU_SELECTION)))
    call_eq(p, TMP, PHASE, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{prefix}_fade_after_menu")

    p.emit(assign(DIGIT_CONST, num(PHASE_BEFORE_START_NEW_GAME)))
    call_eq(p, TMP, PHASE, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{prefix}_fade_full")

    p.emit(assign(DIGIT_CONST, num(PHASE_START_NEW_GAME)))
    call_eq(p, TMP, PHASE, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{prefix}_fade_start_new_game")

    p.emit(assign(DIGIT_CONST, num(PHASE_AFTER_END_ROUND)))
    call_eq(p, TMP, PHASE, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{prefix}_fade_after_round")

    p.emit(assign(DIGIT_CONST, num(PHASE_BEFORE_START_NEXT_ROUND)))
    call_eq(p, TMP, PHASE, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{prefix}_fade_before_next")
    p.emit(p.goto(f"{prefix}_fade_maybe_draw"))

    p.label(f"{prefix}_fade_after_menu")
    p.emit(assign(DIGIT_CONST, num(255)))
    call_mul(p, FADE_ALPHA, FRAME_COUNTER, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(PHASE_FADE_AFTER_MENU_FRAMES)))
    call_div(p, FADE_ALPHA, FADE_ALPHA, DIGIT_CONST)
    p.emit(p.goto(f"{prefix}_fade_clamp_high"))

    p.label(f"{prefix}_fade_full")
    p.emit(assign(FADE_ALPHA, num(255)))
    p.emit(p.goto(f"{prefix}_fade_maybe_draw"))

    p.label(f"{prefix}_fade_start_new_game")
    p.emit(assign(DIGIT_CONST, num(PHASE_FADE_START_NEW_GAME_FRAMES)))
    call_sub(p, FADE_ALPHA, DIGIT_CONST, FRAME_COUNTER)
    p.emit(assign(DIGIT_CONST, num(255)))
    call_mul(p, FADE_ALPHA, FADE_ALPHA, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(PHASE_FADE_START_NEW_GAME_FRAMES)))
    call_div(p, FADE_ALPHA, FADE_ALPHA, DIGIT_CONST)
    p.emit(p.goto(f"{prefix}_fade_clamp_low"))

    p.label(f"{prefix}_fade_after_round")
    call_add_const(p, FADE_ALPHA, FRAME_COUNTER, 1)
    p.emit(assign(DIGIT_CONST, num(255)))
    call_mul(p, FADE_ALPHA, FADE_ALPHA, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(PHASE_FADE_AFTER_ROUND_FRAMES)))
    call_div(p, FADE_ALPHA, FADE_ALPHA, DIGIT_CONST)
    p.emit(p.goto(f"{prefix}_fade_clamp_high"))

    p.label(f"{prefix}_fade_before_next")
    p.emit(assign(DIGIT_CONST, num(PHASE_FADE_BEFORE_NEXT_FRAMES)))
    call_sub(p, FADE_ALPHA, DIGIT_CONST, FRAME_COUNTER)
    p.emit(assign(DIGIT_CONST, num(255)))
    call_mul(p, FADE_ALPHA, FADE_ALPHA, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(PHASE_FADE_BEFORE_NEXT_FRAMES)))
    call_div(p, FADE_ALPHA, FADE_ALPHA, DIGIT_CONST)
    p.emit(p.goto(f"{prefix}_fade_clamp_low"))

    p.label(f"{prefix}_fade_clamp_low")
    p.call(SYS_LT, TMP, FADE_ALPHA, ZERO)
    p.if_zero_goto(var(TMP), f"{prefix}_fade_clamp_high")
    p.emit(assign(FADE_ALPHA, num(0)))

    p.label(f"{prefix}_fade_clamp_high")
    p.emit(assign(DIGIT_CONST, num(255)))
    p.call(SYS_GT, TMP, FADE_ALPHA, DIGIT_CONST)
    p.if_zero_goto(var(TMP), f"{prefix}_fade_maybe_draw")
    p.emit(assign(FADE_ALPHA, num(255)))

    p.label(f"{prefix}_fade_maybe_draw")
    if_var_nonzero_goto(p, FADE_ALPHA, f"{prefix}_fade_draw")
    p.emit(p.goto(f"{prefix}_fade_done"))
    p.label(f"{prefix}_fade_draw")
    draw_rect_alpha_expr(p, 0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, 7, var(FADE_ALPHA))
    p.label(f"{prefix}_fade_done")


def clamp_0_255(p: Program, value_var: int, prefix: str) -> None:
    p.call(SYS_LT, TMP, value_var, ZERO)
    p.if_zero_goto(var(TMP), f"{prefix}_not_low")
    p.emit(assign(value_var, num(0)))
    p.label(f"{prefix}_not_low")
    p.emit(assign(DIGIT_CONST, num(255)))
    p.call(SYS_GT, TMP, value_var, DIGIT_CONST)
    p.if_zero_goto(var(TMP), f"{prefix}_done")
    p.emit(assign(value_var, num(255)))
    p.label(f"{prefix}_done")


def draw_intro_scene(p: Program, prefix: str) -> None:
    p.call(SYS_CLEAR, 7)

    p.emit(assign(DIGIT_CONST, num(INTRO_FADE_IN_END)))
    p.call(SYS_LT, TMP, FRAME_COUNTER, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{prefix}_fade_in")

    p.emit(assign(DIGIT_CONST, num(INTRO_FADE_OUT_START)))
    call_sub(p, FADE_ALPHA, DIGIT_CONST, FRAME_COUNTER)
    p.emit(assign(DIGIT_CONST, num(255)))
    call_mul(p, FADE_ALPHA, FADE_ALPHA, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(INTRO_FADE_DENOMINATOR)))
    call_div(p, FADE_ALPHA, FADE_ALPHA, DIGIT_CONST)
    p.emit(p.goto(f"{prefix}_alpha_ready"))

    p.label(f"{prefix}_fade_in")
    p.emit(assign(DIGIT_CONST, num(255)))
    call_mul(p, FADE_ALPHA, FRAME_COUNTER, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(INTRO_FADE_DENOMINATOR)))
    call_div(p, FADE_ALPHA, FADE_ALPHA, DIGIT_CONST)

    p.label(f"{prefix}_alpha_ready")
    clamp_0_255(p, FADE_ALPHA, f"{prefix}_alpha_clamp")
    if_var_nonzero_goto(p, FADE_ALPHA, f"{prefix}_draw_mark")
    p.emit(p.goto(f"{prefix}_done"))

    p.label(f"{prefix}_draw_mark")
    intro_sx, intro_sy, intro_sw, intro_sh, intro_dx, intro_dy, intro_dw, intro_dh = render_values(
        "intro_mark", 8
    )
    draw_sprite_alpha_exprs(
        p,
        intro_sx,
        intro_sy,
        intro_sw,
        intro_sh,
        num(intro_dx),
        num(intro_dy),
        num(intro_dw),
        num(intro_dh),
        var(FADE_ALPHA),
    )
    p.label(f"{prefix}_done")


def draw_menu_sitting_pikachu_tiles(p: Program, prefix: str) -> None:
    p.emit(assign(DIGIT_CONST, num(MENU_FULL_ALPHA_FRAME)))
    p.call(SYS_GT, TMP, FRAME_COUNTER, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{prefix}_full_alpha")

    call_add_const(p, FADE_ALPHA, FRAME_COUNTER, -MENU_FADE_START_FRAME)
    p.emit(assign(DIGIT_CONST, num(255)))
    call_mul(p, FADE_ALPHA, FADE_ALPHA, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(MENU_FADE_DENOMINATOR)))
    call_div(p, FADE_ALPHA, FADE_ALPHA, DIGIT_CONST)
    clamp_0_255(p, FADE_ALPHA, f"{prefix}_partial_alpha")
    p.emit(p.goto(f"{prefix}_alpha_ready"))

    p.label(f"{prefix}_full_alpha")
    p.emit(assign(FADE_ALPHA, num(255)))

    p.label(f"{prefix}_alpha_ready")
    if_var_nonzero_goto(p, FADE_ALPHA, f"{prefix}_draw")
    p.emit(p.goto(f"{prefix}_done"))

    p.label(f"{prefix}_draw")
    sitting_sx, sitting_sy, sitting_sw, sitting_sh, sitting_dw, sitting_dh = render_values(
        "menu_sitting_tile", 6
    )
    p.emit(assign(DIGIT_CONST, num(MENU_SITTING_SCROLL_FRAME_MULTIPLIER)))
    call_mul(p, TMP, FRAME_COUNTER, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(MENU_SITTING_SCROLL_MODULO)))
    call_mod(p, TMP, TMP, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(MENU_SITTING_SCROLL_SCALE)))
    call_mul(p, TMP, TMP, DIGIT_CONST)
    for row in range(MENU_SITTING_ROWS):
        for col in range(MENU_SITTING_COLS):
            p.emit(assign(DIGIT_CONST, num(sitting_dw * col)))
            call_sub(p, CLOUD_DRAW_X, DIGIT_CONST, TMP)
            p.emit(assign(DIGIT_CONST, num(sitting_dh * row)))
            call_sub(p, CLOUD_DRAW_Y, DIGIT_CONST, TMP)
            draw_sprite_alpha_exprs(
                p,
                sitting_sx,
                sitting_sy,
                sitting_sw,
                sitting_sh,
                var(CLOUD_DRAW_X),
                var(CLOUD_DRAW_Y),
                num(sitting_dw),
                num(sitting_dh),
                var(FADE_ALPHA),
            )
    p.label(f"{prefix}_done")


def draw_menu_fight_message(p: Program, prefix: str) -> None:
    p.emit(assign(DIGIT_CONST, num(MENU_FIGHT_GROW_FRAMES)))
    p.call(SYS_LT, TMP, FRAME_COUNTER, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{prefix}_growing")

    call_add_const(p, TMP, FRAME_COUNTER, 1)
    p.emit(assign(DIGIT_CONST, num(len(MENU_FIGHT_SIZE_CYCLE))))
    call_mod(p, TMP, TMP, DIGIT_CONST)
    for idx, size in enumerate(MENU_FIGHT_SIZE_CYCLE):
        p.emit(assign(DIGIT_CONST, num(idx)))
        call_eq(p, TMP2, TMP, DIGIT_CONST)
        p.if_zero_goto(var(TMP2), f"{prefix}_size_{idx}_skip")
        p.emit(assign(CLOUD_DRAW_W, num(size)))
        p.label(f"{prefix}_size_{idx}_skip")
    p.emit(p.goto(f"{prefix}_size_ready"))

    p.label(f"{prefix}_growing")
    p.emit(assign(CLOUD_DRAW_W, var(FRAME_COUNTER)))

    p.label(f"{prefix}_size_ready")
    if_var_nonzero_goto(p, CLOUD_DRAW_W, f"{prefix}_draw")
    p.emit(p.goto(f"{prefix}_done"))

    p.label(f"{prefix}_draw")
    fight_sx, fight_sy, fight_sw, fight_sh = render_values("menu_fight_message_source", 4)
    p.emit(assign(DIGIT_CONST, num(fight_sh)))
    call_mul(p, CLOUD_DRAW_H, CLOUD_DRAW_W, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(MENU_FIGHT_GROW_FRAMES)))
    call_div(p, CLOUD_DRAW_H, CLOUD_DRAW_H, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(MENU_FIGHT_WIDTH_DIVISOR)))
    call_div(p, CLOUD_DRAW_W, CLOUD_DRAW_H, DIGIT_CONST)
    p.emit(assign(CLOUD_DRAW_H, var(CLOUD_DRAW_W)))
    p.emit(assign(DIGIT_CONST, num(2)))
    call_mul(p, TMP, CLOUD_DRAW_W, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(MENU_FIGHT_ANCHOR_X)))
    call_sub(p, CLOUD_DRAW_X, DIGIT_CONST, TMP)
    p.emit(assign(DIGIT_CONST, num(MENU_FIGHT_ANCHOR_Y)))
    call_sub(p, CLOUD_DRAW_Y, DIGIT_CONST, TMP)
    p.emit(assign(DIGIT_CONST, num(MENU_FIGHT_SCALE)))
    call_mul(p, CLOUD_DRAW_W, CLOUD_DRAW_W, DIGIT_CONST)
    call_mul(p, CLOUD_DRAW_H, CLOUD_DRAW_H, DIGIT_CONST)
    draw_sprite_exprs(
        p,
        fight_sx,
        fight_sy,
        fight_sw,
        fight_sh,
        var(CLOUD_DRAW_X),
        var(CLOUD_DRAW_Y),
        var(CLOUD_DRAW_W),
        var(CLOUD_DRAW_H),
    )
    p.label(f"{prefix}_done")


def draw_menu_sachisoft(p: Program, prefix: str) -> None:
    p.emit(assign(DIGIT_CONST, num(MENU_FULL_ALPHA_FRAME)))
    p.call(SYS_GT, TMP, FRAME_COUNTER, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{prefix}_full_alpha")

    p.emit(assign(DIGIT_CONST, num(255)))
    call_mul(p, FADE_ALPHA, FRAME_COUNTER, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(MENU_FADE_DENOMINATOR)))
    call_div(p, FADE_ALPHA, FADE_ALPHA, DIGIT_CONST)
    clamp_0_255(p, FADE_ALPHA, f"{prefix}_alpha_clamp")
    p.emit(p.goto(f"{prefix}_draw"))

    p.label(f"{prefix}_full_alpha")
    p.emit(assign(FADE_ALPHA, num(255)))

    p.label(f"{prefix}_draw")
    sachisoft_sx, sachisoft_sy, sachisoft_sw, sachisoft_sh, sachisoft_dx, sachisoft_dy, sachisoft_dw, sachisoft_dh = render_values(
        "menu_sachisoft", 8
    )
    draw_sprite_alpha_exprs(
        p,
        sachisoft_sx,
        sachisoft_sy,
        sachisoft_sw,
        sachisoft_sh,
        num(sachisoft_dx),
        num(sachisoft_dy),
        num(sachisoft_dw),
        num(sachisoft_dh),
        var(FADE_ALPHA),
    )


def draw_menu_title(p: Program, prefix: str) -> None:
    title_sx, title_sy, title_sw, title_sh, title_x, title_y, title_w, title_h = render_values(
        "menu_title_final", 8
    )
    p.emit(assign(DIGIT_CONST, num(MENU_TITLE_SHOW_FRAME)))
    p.call(SYS_GT, TMP, FRAME_COUNTER, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{prefix}_after_30")
    p.emit(p.goto(f"{prefix}_done"))

    p.label(f"{prefix}_after_30")
    p.emit(assign(DIGIT_CONST, num(MENU_TITLE_SLIDE_END_FRAME)))
    p.call(SYS_GT, TMP, FRAME_COUNTER, DIGIT_CONST)
    p.if_zero_goto(var(TMP), f"{prefix}_slide_in")
    p.emit(assign(DIGIT_CONST, num(MENU_TITLE_SQUASH_END_FRAME)))
    p.call(SYS_GT, TMP, FRAME_COUNTER, DIGIT_CONST)
    p.if_zero_goto(var(TMP), f"{prefix}_squash")
    p.emit(assign(DIGIT_CONST, num(MENU_TITLE_STRETCH_END_FRAME)))
    p.call(SYS_GT, TMP, FRAME_COUNTER, DIGIT_CONST)
    p.if_zero_goto(var(TMP), f"{prefix}_stretch")
    p.emit(assign(CLOUD_DRAW_X, num(title_x)))
    p.emit(assign(CLOUD_DRAW_W, num(title_w)))
    p.emit(p.goto(f"{prefix}_draw"))

    p.label(f"{prefix}_slide_in")
    call_add_const(p, TMP, FRAME_COUNTER, -MENU_TITLE_SHOW_FRAME)
    p.emit(assign(DIGIT_CONST, num(MENU_TITLE_SLIDE_SPEED)))
    call_mul(p, TMP, TMP, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(title_x + MENU_TITLE_SLIDE_OFFSET)))
    call_sub(p, CLOUD_DRAW_X, DIGIT_CONST, TMP)
    p.emit(assign(CLOUD_DRAW_W, num(title_w)))
    p.emit(p.goto(f"{prefix}_draw"))

    p.label(f"{prefix}_squash")
    p.emit(assign(CLOUD_DRAW_X, num(title_x)))
    call_add_const(p, TMP, FRAME_COUNTER, -MENU_TITLE_SLIDE_END_FRAME)
    p.emit(assign(DIGIT_CONST, num(MENU_TITLE_SQUASH_SPEED)))
    call_mul(p, TMP, TMP, DIGIT_CONST)
    p.emit(assign(DIGIT_CONST, num(MENU_TITLE_SQUASH_WIDTH)))
    call_sub(p, CLOUD_DRAW_W, DIGIT_CONST, TMP)
    p.emit(p.goto(f"{prefix}_draw"))

    p.label(f"{prefix}_stretch")
    p.emit(assign(CLOUD_DRAW_X, num(title_x)))
    call_add_const(p, TMP, FRAME_COUNTER, -MENU_TITLE_SQUASH_END_FRAME)
    p.emit(assign(DIGIT_CONST, num(MENU_TITLE_STRETCH_SPEED)))
    call_mul(p, TMP, TMP, DIGIT_CONST)
    call_add_const(p, CLOUD_DRAW_W, TMP, MENU_TITLE_STRETCH_BASE_WIDTH)

    p.label(f"{prefix}_draw")
    draw_sprite_exprs(
        p,
        title_sx,
        title_sy,
        title_sw,
        title_sh,
        var(CLOUD_DRAW_X),
        num(title_y),
        var(CLOUD_DRAW_W),
        num(title_h),
    )
    p.label(f"{prefix}_done")


def draw_menu_with_who_option(
    p: Program,
    sprite_key: str,
    selected_value: int,
    prefix: str,
) -> None:
    option_sx, option_sy, option_sw, option_sh, option_x, option_y, option_w, option_h = render_values(
        sprite_key, 8
    )
    p.emit(assign(CLOUD_DRAW_X, num(option_x)))
    p.emit(assign(CLOUD_DRAW_Y, num(option_y)))
    p.emit(assign(CLOUD_DRAW_W, num(option_w)))
    p.emit(assign(CLOUD_DRAW_H, num(option_h)))

    p.emit(assign(DIGIT_CONST, num(selected_value)))
    call_eq(p, TMP2, MENU_SELECTION, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP2, f"{prefix}_selected")
    p.emit(p.goto(f"{prefix}_draw"))

    p.label(f"{prefix}_selected")
    call_add_const(p, TMP, CLOUD_SIZE_DIFF, MENU_OPTION_EXPAND_BIAS)
    p.emit(assign(DIGIT_CONST, num(MENU_OPTION_X_MULTIPLIER)))
    call_mul(p, TMP2, TMP, DIGIT_CONST)
    call_sub(p, CLOUD_DRAW_X, CLOUD_DRAW_X, TMP2)
    p.emit(assign(DIGIT_CONST, num(MENU_OPTION_WIDTH_MULTIPLIER)))
    call_mul(p, TMP2, TMP, DIGIT_CONST)
    call_add(p, CLOUD_DRAW_W, CLOUD_DRAW_W, TMP2)
    p.emit(assign(DIGIT_CONST, num(MENU_OPTION_Y_MULTIPLIER)))
    call_mul(p, TMP2, CLOUD_SIZE_DIFF, DIGIT_CONST)
    call_sub(p, CLOUD_DRAW_Y, CLOUD_DRAW_Y, TMP2)
    p.emit(assign(DIGIT_CONST, num(MENU_OPTION_HEIGHT_MULTIPLIER)))
    call_mul(p, TMP2, CLOUD_SIZE_DIFF, DIGIT_CONST)
    call_add(p, CLOUD_DRAW_H, CLOUD_DRAW_H, TMP2)

    p.label(f"{prefix}_draw")
    draw_sprite_exprs(
        p,
        option_sx,
        option_sy,
        option_sw,
        option_sh,
        var(CLOUD_DRAW_X),
        var(CLOUD_DRAW_Y),
        var(CLOUD_DRAW_W),
        var(CLOUD_DRAW_H),
    )


def draw_menu_with_who_messages(p: Program, prefix: str) -> None:
    p.emit(assign(DIGIT_CONST, num(MENU_WITH_WHO_FRAME)))
    p.call(SYS_GT, TMP, FRAME_COUNTER, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{prefix}_draw")
    p.emit(p.goto(f"{prefix}_done"))

    p.label(f"{prefix}_draw")
    call_clamp(p, CLOUD_SIZE_DIFF, NO_INPUT_COUNTER, MENU_OPTION_CLAMP_MIN, MENU_OPTION_CLAMP_MAX)
    call_add_const(p, CLOUD_SIZE_DIFF, CLOUD_SIZE_DIFF, MENU_OPTION_SIZE_DIFF_BASE)
    draw_menu_with_who_option(p, "menu_option_computer", 0, f"{prefix}_computer")
    draw_menu_with_who_option(p, "menu_option_friend", 1, f"{prefix}_friend")
    p.label(f"{prefix}_done")


def draw_menu_sprites(p: Program, prefix: str) -> None:
    draw_menu_sitting_pikachu_tiles(p, f"{prefix}_sitting")
    draw_menu_fight_message(p, f"{prefix}_fight")
    draw_menu_sachisoft(p, f"{prefix}_sachisoft")
    draw_menu_title(p, f"{prefix}_title")

    p.emit(assign(DIGIT_CONST, num(MENU_POKEMON_LABEL_FRAME)))
    p.call(SYS_GT, TMP, FRAME_COUNTER, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, f"{prefix}_pokemon")
    p.emit(p.goto(f"{prefix}_after_pokemon"))
    p.label(f"{prefix}_pokemon")
    draw_render_sprite_const(p, "menu_pokemon_label")
    p.label(f"{prefix}_after_pokemon")

    draw_menu_with_who_messages(p, f"{prefix}_with_who")


def draw_gameover_sprites(p: Program, prefix: str) -> None:
    score1_x, score1_y = render_values("score1_origin", 2)
    score2_x, score2_y = render_values("score2_origin", 2)
    draw_background_sprites(p)
    draw_environment_sprites(p)
    draw_score_sprites(p, SCORE1, score1_x, score1_y, f"{prefix}_score1")
    draw_score_sprites(p, SCORE2, score2_x, score2_y, f"{prefix}_score2")
    draw_playfield_sprites(p, prefix)
    draw_game_end_message(p, prefix)


def draw_menu_scene(p: Program, prefix: str) -> None:
    p.call(SYS_CLEAR, 7)
    draw_menu_sprites(p, prefix)


def draw_gameover_scene(p: Program, prefix: str) -> None:
    p.call(SYS_CLEAR, 0)
    draw_gameover_sprites(p, prefix)
    draw_fade_overlay(p, prefix)


def draw_round_scene(p: Program, prefix: str = "round") -> None:
    score1_x, score1_y = render_values("score1_origin", 2)
    score2_x, score2_y = render_values("score2_origin", 2)
    p.call(SYS_CLEAR, 0)
    draw_background_sprites(p)
    draw_environment_sprites(p)
    draw_score_sprites(p, SCORE1, score1_x, score1_y, f"{prefix}_score1")
    draw_score_sprites(p, SCORE2, score2_x, score2_y, f"{prefix}_score2")
    draw_playfield_sprites(p, prefix)
    draw_fade_overlay(p, prefix)


def draw_game_start_scene(p: Program, prefix: str) -> None:
    draw_round_scene(p, prefix)
    draw_game_start_message(p, prefix)


def draw_ready_scene(p: Program, prefix: str) -> None:
    draw_round_scene(p, prefix)
    draw_ready_message(p, prefix)


def draw_paused_current_scene(p: Program) -> None:
    for phase, label in (
        (PHASE_INTRO, "paused_intro"),
        (PHASE_MENU, "paused_menu"),
        (PHASE_START_NEW_GAME, "paused_start_new_game"),
        (PHASE_BEFORE_START_NEXT_ROUND, "paused_before_next_round"),
        (PHASE_GAME_END, "paused_game_end"),
    ):
        p.emit(assign(DIGIT_CONST, num(phase)))
        call_eq(p, TMP, PHASE, DIGIT_CONST)
        if_var_nonzero_goto(p, TMP, label)
    p.emit(p.goto("paused_round_like"))

    p.label("paused_intro")
    draw_intro_scene(p, "paused_intro")
    wait_and_loop(p)

    p.label("paused_menu")
    draw_menu_scene(p, "paused_menu")
    wait_and_loop(p)

    p.label("paused_start_new_game")
    draw_game_start_scene(p, "paused_game_start")
    wait_and_loop(p)

    p.label("paused_before_next_round")
    draw_ready_scene(p, "paused_before_next_round")
    wait_and_loop(p)

    p.label("paused_game_end")
    draw_gameover_scene(p, "paused_gameover")
    wait_and_loop(p)

    p.label("paused_round_like")
    draw_round_scene(p, "paused_round")
    wait_and_loop(p)


def load_persisted_options(p: Program) -> None:
    load_setting(p, SETTING_WINNING_SCORE, WINNING_SCORE, DEFAULT_WINNING_SCORE)
    load_setting(p, SETTING_PRACTICE_MODE, PRACTICE_MODE, DEFAULT_PRACTICE_MODE)
    load_setting(p, SETTING_BGM_ON, BGM_ON, DEFAULT_BGM_ON)
    load_setting(p, SETTING_SFX_MODE, SFX_MODE, DEFAULT_SFX_MODE)
    load_setting(p, SETTING_SOFT_GRAPHICS, SOFT_GRAPHICS, DEFAULT_SOFT_GRAPHICS)
    load_setting(p, SETTING_TARGET_FPS, TARGET_FPS, DEFAULT_TARGET_FPS)

    call_clamp(p, PRACTICE_MODE, PRACTICE_MODE, min(PRACTICE_MODE_VALUES), max(PRACTICE_MODE_VALUES))
    call_clamp(p, BGM_ON, BGM_ON, min(BGM_ON_VALUES), max(BGM_ON_VALUES))
    call_clamp(p, SOFT_GRAPHICS, SOFT_GRAPHICS, min(SOFT_GRAPHICS_VALUES), max(SOFT_GRAPHICS_VALUES))
    call_clamp(p, SFX_MODE, SFX_MODE, min(SFX_MODE_VALUES), max(SFX_MODE_VALUES))

    for value in WINNING_SCORE_VALUES:
        label = f"settings_score_{value}"
        p.emit(assign(DIGIT_CONST, num(value)))
        call_eq(p, TMP, WINNING_SCORE, DIGIT_CONST)
        if_var_nonzero_goto(p, TMP, label)
    p.emit(assign(WINNING_SCORE, num(DEFAULT_WINNING_SCORE)))
    p.emit(p.goto("settings_score_ready"))
    for value in WINNING_SCORE_VALUES:
        p.label(f"settings_score_{value}")
        p.emit(p.goto("settings_score_ready"))
    p.label("settings_score_ready")

    for value in TARGET_FPS_VALUES:
        label = f"settings_fps_{value}"
        p.emit(assign(DIGIT_CONST, num(value)))
        call_eq(p, TMP, TARGET_FPS, DIGIT_CONST)
        if_var_nonzero_goto(p, TMP, label)
    p.emit(assign(TARGET_FPS, num(DEFAULT_TARGET_FPS)))
    p.emit(p.goto("settings_fps_ready"))
    for value in TARGET_FPS_VALUES:
        p.label(f"settings_fps_{value}")
        p.emit(p.goto("settings_fps_ready"))
    p.label("settings_fps_ready")

    p.call_expr(SYS_SET_TARGET_FPS, var(TARGET_FPS))
    p.call_expr(SYS_SET_TEXTURE_FILTER, var(SOFT_GRAPHICS))


def handle_runtime_options(p: Program) -> None:
    call_key_pressed(p, ACTION_RESTART, KEY)
    if_var_nonzero_goto(p, KEY, "runtime_restart")
    p.emit(p.goto("runtime_after_restart"))

    p.label("runtime_restart")
    set_phase(p, PHASE_INTRO)
    p.emit(assign(NO_INPUT_COUNTER, num(0)))
    p.emit(assign(SLOW_MOTION_FRAMES_LEFT, num(0)))
    p.emit(assign(SLOW_MOTION_SKIP, num(0)))
    p.emit(assign(PAUSED, num(0)))
    p.call(SYS_STOP_AUDIO, BGM_AUDIO_SLOT)
    draw_intro_scene(p, "runtime_restart")
    wait_and_loop(p)

    p.label("runtime_after_restart")
    call_key_pressed(p, ACTION_PAUSE, KEY)
    p.if_zero_goto(var(KEY), "runtime_pause_done")
    if_var_nonzero_goto(p, PAUSED, "runtime_pause_turn_off")
    p.emit(assign(PAUSED, num(1)))
    p.emit(p.goto("runtime_pause_done"))
    p.label("runtime_pause_turn_off")
    p.emit(assign(PAUSED, num(0)))
    p.label("runtime_pause_done")

    call_key_pressed(p, ACTION_PRACTICE_TOGGLE, KEY)
    p.if_zero_goto(var(KEY), "runtime_practice_done")
    if_var_nonzero_goto(p, PRACTICE_MODE, "runtime_practice_turn_off")
    p.emit(assign(PRACTICE_MODE, num(1)))
    save_setting_var(p, SETTING_PRACTICE_MODE, PRACTICE_MODE)
    p.emit(p.goto("runtime_practice_done"))
    p.label("runtime_practice_turn_off")
    p.emit(assign(PRACTICE_MODE, num(0)))
    save_setting_var(p, SETTING_PRACTICE_MODE, PRACTICE_MODE)
    p.label("runtime_practice_done")

    call_key_pressed(p, ACTION_BGM_TOGGLE, KEY)
    p.if_zero_goto(var(KEY), "runtime_bgm_done")
    if_var_nonzero_goto(p, BGM_ON, "runtime_bgm_turn_off")
    p.emit(assign(BGM_ON, num(1)))
    save_setting_var(p, SETTING_BGM_ON, BGM_ON)
    p.emit(p.goto("runtime_bgm_done"))
    p.label("runtime_bgm_turn_off")
    p.emit(assign(BGM_ON, num(0)))
    save_setting_var(p, SETTING_BGM_ON, BGM_ON)
    p.call(SYS_STOP_AUDIO, BGM_AUDIO_SLOT)
    p.label("runtime_bgm_done")

    call_key_pressed(p, ACTION_SFX_MODE, KEY)
    p.if_zero_goto(var(KEY), "runtime_sfx_done")
    p.emit(assign(DIGIT_CONST, num(SFX_MODE_STEREO)))
    call_eq(p, TMP, SFX_MODE, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, "runtime_sfx_turn_mono")
    call_eq(p, TMP, SFX_MODE, ONE)
    if_var_nonzero_goto(p, TMP, "runtime_sfx_turn_off")
    p.emit(assign(SFX_MODE, num(SFX_MODE_STEREO)))
    save_setting_var(p, SETTING_SFX_MODE, SFX_MODE)
    p.emit(p.goto("runtime_sfx_done"))
    p.label("runtime_sfx_turn_mono")
    p.emit(assign(SFX_MODE, num(SFX_MODE_MONO)))
    save_setting_var(p, SETTING_SFX_MODE, SFX_MODE)
    p.emit(p.goto("runtime_sfx_done"))
    p.label("runtime_sfx_turn_off")
    p.emit(assign(SFX_MODE, num(SFX_MODE_OFF)))
    save_setting_var(p, SETTING_SFX_MODE, SFX_MODE)
    p.label("runtime_sfx_done")

    call_key_pressed(p, ACTION_GRAPHICS_FILTER, KEY)
    p.if_zero_goto(var(KEY), "runtime_soft_graphics_done")
    if_var_nonzero_goto(p, SOFT_GRAPHICS, "runtime_soft_graphics_turn_off")
    p.emit(assign(SOFT_GRAPHICS, num(1)))
    p.call_expr(SYS_SET_TEXTURE_FILTER, var(SOFT_GRAPHICS))
    save_setting_var(p, SETTING_SOFT_GRAPHICS, SOFT_GRAPHICS)
    p.emit(p.goto("runtime_soft_graphics_done"))
    p.label("runtime_soft_graphics_turn_off")
    p.emit(assign(SOFT_GRAPHICS, num(0)))
    p.call_expr(SYS_SET_TEXTURE_FILTER, var(SOFT_GRAPHICS))
    save_setting_var(p, SETTING_SOFT_GRAPHICS, SOFT_GRAPHICS)
    p.label("runtime_soft_graphics_done")

    call_key_pressed(p, ACTION_FPS_SLOWER, KEY)
    p.if_zero_goto(var(KEY), "runtime_fps_slow_done")
    p.emit(assign(TARGET_FPS, num(TARGET_FPS_SLOW)))
    p.call_expr(SYS_SET_TARGET_FPS, var(TARGET_FPS))
    save_setting_var(p, SETTING_TARGET_FPS, TARGET_FPS)
    p.label("runtime_fps_slow_done")

    call_key_pressed(p, ACTION_FPS_FASTER, KEY)
    p.if_zero_goto(var(KEY), "runtime_fps_fast_done")
    p.emit(assign(TARGET_FPS, num(TARGET_FPS_FAST)))
    p.call_expr(SYS_SET_TARGET_FPS, var(TARGET_FPS))
    save_setting_var(p, SETTING_TARGET_FPS, TARGET_FPS)
    p.label("runtime_fps_fast_done")

    call_key_pressed(p, ACTION_FPS_NORMAL, KEY)
    p.if_zero_goto(var(KEY), "runtime_fps_normal_done")
    p.emit(assign(TARGET_FPS, num(TARGET_FPS_NORMAL)))
    p.call_expr(SYS_SET_TARGET_FPS, var(TARGET_FPS))
    save_setting_var(p, SETTING_TARGET_FPS, TARGET_FPS)
    p.label("runtime_fps_normal_done")

    call_key_pressed(p, ACTION_WIN_SCORE_5, KEY)
    p.if_zero_goto(var(KEY), "runtime_winning_score_5_done")
    p.emit(assign(WINNING_SCORE, num(WINNING_SCORE_1)))
    save_setting_var(p, SETTING_WINNING_SCORE, WINNING_SCORE)
    p.label("runtime_winning_score_5_done")

    call_key_pressed(p, ACTION_WIN_SCORE_10, KEY)
    p.if_zero_goto(var(KEY), "runtime_winning_score_10_done")
    p.emit(assign(WINNING_SCORE, num(WINNING_SCORE_2)))
    save_setting_var(p, SETTING_WINNING_SCORE, WINNING_SCORE)
    p.label("runtime_winning_score_10_done")

    call_key_pressed(p, ACTION_WIN_SCORE_15, KEY)
    p.if_zero_goto(var(KEY), "runtime_winning_score_15_done")
    p.emit(assign(WINNING_SCORE, num(WINNING_SCORE_3)))
    save_setting_var(p, SETTING_WINNING_SCORE, WINNING_SCORE)
    p.label("runtime_winning_score_15_done")


def main() -> None:
    p = Program()

    # Constants and initial game state.
    configure_window(p)
    configure_settings(p)
    define_palette(p)
    define_assets(p)
    p.emit(assign(ZERO, num(0)))
    p.emit(assign(ONE, num(1)))
    p.emit(assign(NEG_ONE, num(-1)))
    p.emit(assign(FLOOR_Y, num(INITIAL_FLOOR_Y)))
    p.emit(assign(BALL_FLOOR_Y, num(INITIAL_BALL_FLOOR_Y)))
    p.emit(assign(LEFT_WALL, num(BALL_LEFT_WALL_SCREEN)))
    p.emit(assign(RIGHT_WALL, num(BALL_RIGHT_WALL_SCREEN)))
    p.emit(assign(BALL_RADIUS, num(BALL_RADIUS_SCREEN)))
    p.emit(assign(SCORE1, num(0)))
    p.emit(assign(SCORE2, num(0)))
    p.emit(assign(COLLISION_RADIUS, num(COLLISION_RADIUS_SCREEN)))
    p.emit(assign(MID_X, num(GROUND_HALF_WIDTH_SCREEN)))
    p.emit(assign(P2_HUMAN, num(0)))
    p.emit(assign(AI_DEADZONE, num(INITIAL_AI_DEADZONE)))
    p.emit(assign(NET_HALF, num(INITIAL_NET_HALF)))
    p.emit(assign(NET_TOP, num(INITIAL_NET_TOP)))
    p.emit(assign(NET_BOTTOM, num(INITIAL_NET_BOTTOM)))
    p.emit(assign(WINNING_SCORE, num(DEFAULT_WINNING_SCORE)))
    p.emit(assign(TEN, num(10)))
    p.emit(assign(PHASE, num(PHASE_INTRO)))
    p.emit(assign(FRAME_COUNTER, num(0)))
    p.emit(assign(MENU_SELECTION, num(0)))
    p.emit(assign(WINNER, num(0)))
    p.emit(assign(P1_STATE, num(PLAYER_STATE_NORMAL)))
    p.emit(assign(P2_STATE, num(PLAYER_STATE_NORMAL)))
    p.emit(assign(P1_FRAME, num(0)))
    p.emit(assign(P2_FRAME, num(0)))
    p.emit(assign(BALL_FRAME, num(0)))
    p.emit(assign(WAVE_PHASE, num(0)))
    init_rng_seed(p)
    call_rand_mod(p, P1_BOLDNESS, 5)
    call_rand_mod(p, P2_BOLDNESS, 5)
    for x_var, y_var, vx_var, size_turn_var in CLOUDS:
        init_cloud_from_rng(p, x_var, y_var, vx_var, size_turn_var)
    p.emit(assign(WAVE_VERTICAL, num(INITIAL_WAVE_VERTICAL)))
    p.emit(assign(WAVE_VELOCITY, num(INITIAL_WAVE_VELOCITY)))
    for y_var in WAVE_Y_COORDS:
        p.emit(assign(y_var, num(INITIAL_WAVE_Y)))
    p.emit(assign(CLOUD_SIZE_DIFF, num(0)))
    p.emit(assign(CLOUD_DRAW_X, num(0)))
    p.emit(assign(CLOUD_DRAW_Y, num(0)))
    p.emit(assign(CLOUD_DRAW_W, num(INITIAL_CLOUD_DRAW_W)))
    p.emit(assign(CLOUD_DRAW_H, num(INITIAL_CLOUD_DRAW_H)))
    p.emit(assign(WAVE_Y_BASE, num(INITIAL_WAVE_Y)))
    p.emit(assign(BALL_PREV_X, num(BALL_P1_SERVE_X_SCREEN)))
    p.emit(assign(BALL_PREV_Y, num(BALL_SERVE_Y_SCREEN)))
    p.emit(assign(BALL_PREV2_X, num(BALL_P1_SERVE_X_SCREEN)))
    p.emit(assign(BALL_PREV2_Y, num(BALL_SERVE_Y_SCREEN)))
    p.emit(assign(BALL_PUNCH_RADIUS, num(0)))
    p.emit(assign(BALL_PUNCH_X, num(BALL_P1_SERVE_X_SCREEN)))
    p.emit(assign(BALL_PUNCH_Y, num(BALL_SERVE_Y_SCREEN)))
    p.emit(assign(BALL_IS_POWER_HIT, num(0)))
    p.emit(assign(BALL_TOUCH_GROUND, num(0)))
    p.emit(assign(ROUND_ENDED, num(0)))
    p.emit(assign(GAME_ENDED, num(0)))
    p.emit(assign(SLOW_MOTION_FRAMES_LEFT, num(0)))
    p.emit(assign(SLOW_MOTION_SKIP, num(0)))
    p.emit(assign(P1_WINNER, num(0)))
    p.emit(assign(P2_WINNER, num(0)))
    p.emit(assign(P1_GAME_ENDED, num(0)))
    p.emit(assign(P2_GAME_ENDED, num(0)))
    reset_sfx_flags(p, ALL_SFX_FLAG_VARS)
    p.emit(assign(FADE_ALPHA, num(0)))
    p.emit(assign(PRACTICE_MODE, num(DEFAULT_PRACTICE_MODE)))
    p.emit(assign(BGM_ON, num(DEFAULT_BGM_ON)))
    p.emit(assign(SFX_MODE, num(DEFAULT_SFX_MODE)))
    p.emit(assign(PAUSED, num(0)))
    p.emit(assign(SOFT_GRAPHICS, num(DEFAULT_SOFT_GRAPHICS)))
    p.emit(assign(TARGET_FPS, num(DEFAULT_TARGET_FPS)))
    p.call_expr(SYS_SET_TARGET_FPS, var(TARGET_FPS))
    load_persisted_options(p)
    p.emit(assign(P1_COMPUTER, num(INITIAL_P1_COMPUTER)))
    p.emit(assign(P2_COMPUTER, num(INITIAL_P2_COMPUTER)))
    p.emit(assign(NO_INPUT_COUNTER, num(0)))
    p.emit(assign(IS_P2_SERVE, num(0)))
    p.emit(assign(P1_X, num(P1_START_X_SCREEN)))
    p.emit(assign(P1_Y, var(FLOOR_Y)))
    p.emit(assign(P1_DY, num(0)))
    p.emit(assign(P1_DIVE_DIR, num(0)))
    p.emit(assign(P1_LIE_TIMER, num(PLAYER_LIE_TIMER_STAND_THRESHOLD)))
    p.emit(assign(P1_COLLIDING, num(0)))
    p.emit(assign(P1_DELAY, num(0)))
    p.emit(assign(P1_SWING_DIR, num(INITIAL_P1_SWING_DIR)))
    p.emit(assign(P2_X, num(P2_START_X_SCREEN)))
    p.emit(assign(P2_Y, var(FLOOR_Y)))
    p.emit(assign(P2_DY, num(0)))
    p.emit(assign(P2_DIVE_DIR, num(0)))
    p.emit(assign(P2_LIE_TIMER, num(PLAYER_LIE_TIMER_STAND_THRESHOLD)))
    p.emit(assign(P2_COLLIDING, num(0)))
    p.emit(assign(P2_DELAY, num(0)))
    p.emit(assign(P2_SWING_DIR, num(INITIAL_P2_SWING_DIR)))
    p.emit(assign(BALL_X, num(BALL_P1_SERVE_X_SCREEN)))
    p.emit(assign(BALL_Y, num(BALL_SERVE_Y_SCREEN)))
    p.emit(assign(BALL_DX, num(BALL_SERVE_DX)))
    p.emit(assign(BALL_DY, num(BALL_SERVE_DY)))
    p.emit(assign(BALL_FINE_ROT, num(0)))
    p.emit(assign(BALL_ROTATION, num(0)))
    p.emit(assign(BALL_EXPECTED_X, num(BALL_P1_SERVE_X_SCREEN)))
    p.emit(assign(SIM_X, num(0)))
    p.emit(assign(SIM_Y, num(0)))
    p.emit(assign(SIM_DX, num(0)))
    p.emit(assign(SIM_DY, num(0)))
    p.emit(assign(SIM_ACTIVE, num(0)))
    p.emit(assign(SIM_FUTURE, num(0)))
    p.emit(assign(P1_STANDBY, num(0)))
    p.emit(assign(P2_STANDBY, num(0)))
    p.emit(assign(AI_TARGET_X, num(BALL_P1_SERVE_X_SCREEN)))
    p.emit(assign(AI_LEFT_BOUND, num(P1_AI_LEFT_BOUND_SCREEN)))
    p.emit(assign(AI_RIGHT_BOUND, num(P2_AI_RIGHT_BOUND_SCREEN)))
    p.emit(assign(POWER_EXPECTED_X, num(BALL_P1_SERVE_X_SCREEN)))
    p.emit(assign(POWER_GOOD, num(0)))
    p.emit(assign(SIM_COUNTER, num(0)))

    p.label("frame")
    handle_runtime_options(p)
    if_var_nonzero_goto(p, PAUSED, "paused_phase")
    call_add_const(p, FRAME_COUNTER, FRAME_COUNTER, 1)
    for phase, label in (
        (PHASE_INTRO, "intro_phase"),
        (PHASE_MENU, "menu_phase"),
        (PHASE_AFTER_MENU_SELECTION, "after_menu_selection_phase"),
        (PHASE_BEFORE_START_NEW_GAME, "before_start_new_game_phase"),
        (PHASE_START_NEW_GAME, "start_new_game_phase"),
        (PHASE_ROUND, "round_phase"),
        (PHASE_AFTER_END_ROUND, "after_end_round_phase"),
        (PHASE_BEFORE_START_NEXT_ROUND, "before_start_next_round_phase"),
        (PHASE_GAME_END, "game_end_phase"),
    ):
        p.emit(assign(DIGIT_CONST, num(phase)))
        call_eq(p, TMP, PHASE, DIGIT_CONST)
        if_var_nonzero_goto(p, TMP, label)
    p.emit(p.goto("round_phase"))

    p.label("paused_phase")
    draw_paused_current_scene(p)

    p.label("intro_phase")
    call_key_pressed(p, ACTION_CONFIRM, KEY)
    call_key_pressed(p, ACTION_P2_CONFIRM, TMP)
    call_add(p, TMP2, KEY, TMP)
    if_var_nonzero_goto(p, TMP2, "intro_to_menu")
    p.emit(assign(DIGIT_CONST, num(INTRO_TO_MENU_FRAME)))
    p.call(SYS_GT, TMP, FRAME_COUNTER, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, "intro_to_menu")
    draw_intro_scene(p, "intro")
    wait_and_loop(p)

    p.label("intro_to_menu")
    set_phase(p, PHASE_MENU)
    p.emit(assign(MENU_SELECTION, num(0)))
    p.call(SYS_STOP_AUDIO, BGM_AUDIO_SLOT)
    draw_menu_scene(p, "intro_to_menu")
    wait_and_loop(p)

    p.label("menu_phase")
    call_key_pressed(p, ACTION_CONFIRM, KEY)
    call_key_pressed(p, ACTION_P2_CONFIRM, TMP)
    call_add(p, TMP2, KEY, TMP)
    p.emit(assign(DIGIT_CONST, num(MENU_OPENING_END_FRAME)))
    p.call(SYS_LT, TMP, FRAME_COUNTER, DIGIT_CONST)
    p.if_zero_goto(var(TMP), "menu_opening_maybe_done")
    if_var_nonzero_goto(p, TMP2, "menu_skip_opening")
    p.emit(p.goto("menu_render"))

    p.label("menu_skip_opening")
    p.emit(assign(FRAME_COUNTER, num(MENU_OPENING_END_FRAME)))
    p.emit(p.goto("menu_render"))

    p.label("menu_opening_maybe_done")
    call_eq(p, TMP, FRAME_COUNTER, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, "menu_render")

    p.label("menu_after_opening")
    call_key(p, ACTION_MENU_UP, KEY)
    call_key(p, ACTION_P2_UP, TMP)
    call_add(p, TMP2, KEY, TMP)
    if_var_nonzero_goto(p, TMP2, "menu_up")
    call_key(p, ACTION_MENU_DOWN, KEY)
    call_key(p, ACTION_P2_DOWN, TMP)
    call_add(p, TMP2, KEY, TMP)
    if_var_nonzero_goto(p, TMP2, "menu_down")
    call_add_const(p, NO_INPUT_COUNTER, NO_INPUT_COUNTER, 1)
    p.emit(p.goto("menu_after_direction"))

    p.label("menu_up")
    call_eq(p, TMP2, MENU_SELECTION, ZERO)
    if_var_nonzero_goto(p, TMP2, "menu_up_no_sound")
    p.emit(assign(UI_SOUND_PI, num(1)))
    p.label("menu_up_no_sound")
    p.emit(assign(MENU_SELECTION, num(0)))
    p.emit(assign(NO_INPUT_COUNTER, num(0)))
    p.emit(p.goto("menu_after_direction"))

    p.label("menu_down")
    call_eq(p, TMP2, MENU_SELECTION, ONE)
    if_var_nonzero_goto(p, TMP2, "menu_down_no_sound")
    p.emit(assign(UI_SOUND_PI, num(1)))
    p.label("menu_down_no_sound")
    p.emit(assign(MENU_SELECTION, num(1)))
    p.emit(assign(NO_INPUT_COUNTER, num(0)))

    p.label("menu_after_direction")
    call_key_pressed(p, ACTION_CONFIRM, KEY)
    call_key_pressed(p, ACTION_P2_CONFIRM, TMP)
    call_add(p, TMP2, KEY, TMP)
    if_var_nonzero_goto(p, TMP2, "menu_power_selected")
    p.emit(assign(DIGIT_CONST, num(MENU_AI_DEMO_NO_INPUT_FRAMES)))
    p.call(SYS_GT, TMP, NO_INPUT_COUNTER, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, "menu_ai_demo")
    p.emit(p.goto("menu_render"))

    p.label("menu_power_selected")
    call_eq(p, TMP2, MENU_SELECTION, ONE)
    if_var_nonzero_goto(p, TMP2, "menu_two_players")
    if_var_nonzero_goto(p, KEY, "menu_one_left")
    p.emit(assign(P1_COMPUTER, num(1)))
    p.emit(assign(P2_COMPUTER, num(0)))
    p.emit(p.goto("menu_begin_selected"))

    p.label("menu_one_left")
    p.emit(assign(P1_COMPUTER, num(0)))
    p.emit(assign(P2_COMPUTER, num(1)))
    p.emit(p.goto("menu_begin_selected"))

    p.label("menu_two_players")
    p.emit(assign(P1_COMPUTER, num(0)))
    p.emit(assign(P2_COMPUTER, num(0)))
    p.emit(p.goto("menu_begin_selected"))

    p.label("menu_ai_demo")
    p.emit(assign(P1_COMPUTER, num(1)))
    p.emit(assign(P2_COMPUTER, num(1)))

    p.label("menu_begin_selected")
    p.emit(assign(NO_INPUT_COUNTER, num(0)))
    p.emit(assign(UI_SOUND_PIKACHU, num(1)))
    set_phase(p, PHASE_AFTER_MENU_SELECTION)
    emit_ui_sound_flags(p, "menu_begin_selected")
    draw_menu_scene(p, "menu_begin_selected")
    wait_and_loop(p)

    p.label("menu_render")
    emit_ui_sound_flags(p, "menu_render")
    draw_menu_scene(p, "menu_render")
    wait_and_loop(p)

    p.label("after_menu_selection_phase")
    p.emit(assign(DIGIT_CONST, num(PHASE_AFTER_MENU_SELECTION_END_FRAME)))
    p.call(SYS_GT, TMP, FRAME_COUNTER, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, "after_menu_selection_done")
    draw_round_scene(p, "after_menu_selection")
    wait_and_loop(p)

    p.label("after_menu_selection_done")
    set_phase(p, PHASE_BEFORE_START_NEW_GAME)
    draw_round_scene(p, "after_menu_selection_done")
    wait_and_loop(p)

    p.label("before_start_new_game_phase")
    p.emit(assign(DIGIT_CONST, num(PHASE_BEFORE_START_NEW_GAME_END_FRAME)))
    p.call(SYS_GT, TMP, FRAME_COUNTER, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, "before_start_new_game_done")
    draw_round_scene(p, "before_start_new_game")
    wait_and_loop(p)

    p.label("before_start_new_game_done")
    set_phase(p, PHASE_START_NEW_GAME)
    draw_round_scene(p, "before_start_new_game_done")
    wait_and_loop(p)

    p.label("start_new_game_phase")
    call_eq(p, TMP, FRAME_COUNTER, ONE)
    if_var_nonzero_goto(p, TMP, "start_new_game_init")
    p.emit(p.goto("start_new_game_after_init"))

    p.label("start_new_game_init")
    p.emit(assign(WINNER, num(0)))
    p.emit(assign(GAME_ENDED, num(0)))
    p.emit(assign(ROUND_ENDED, num(0)))
    p.emit(assign(SLOW_MOTION_FRAMES_LEFT, num(0)))
    p.emit(assign(SLOW_MOTION_SKIP, num(0)))
    p.emit(assign(P1_WINNER, num(0)))
    p.emit(assign(P2_WINNER, num(0)))
    p.emit(assign(P1_GAME_ENDED, num(0)))
    p.emit(assign(P2_GAME_ENDED, num(0)))
    p.emit(assign(SCORE1, num(0)))
    p.emit(assign(SCORE2, num(0)))
    p.emit(assign(IS_P2_SERVE, num(0)))
    reset_players(p)
    reset_ball(p, "new_game")
    play_bgm_if_enabled(p, "start_new_game_bgm")

    p.label("start_new_game_after_init")
    update_environment_animation(p, "start_new_game_env")
    p.emit(assign(DIGIT_CONST, num(PHASE_START_NEW_GAME_END_FRAME)))
    p.call(SYS_GT, TMP, FRAME_COUNTER, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, "start_new_game_done")
    draw_game_start_scene(p, "game_start")
    wait_and_loop(p)

    p.label("start_new_game_done")
    set_phase(p, PHASE_ROUND)
    draw_round_scene(p, "start_new_game_done")
    wait_and_loop(p)

    p.label("round_phase")
    play_bgm_if_enabled(p, "round_bgm")
    apply_round_slow_motion_gate(p)

    read_player_inputs(p)
    call_add(p, TMP2, P1_POWER, P2_POWER)
    if_var_nonzero_goto(p, TMP2, "round_pressed_power")
    p.emit(p.goto("round_after_demo_interrupt"))
    p.label("round_pressed_power")
    if_var_nonzero_goto(p, P1_COMPUTER, "round_pressed_power_p1_computer")
    p.emit(p.goto("round_after_demo_interrupt"))
    p.label("round_pressed_power_p1_computer")
    if_var_nonzero_goto(p, P2_COMPUTER, "round_ai_demo_interrupt")
    p.emit(p.goto("round_after_demo_interrupt"))
    p.label("round_ai_demo_interrupt")
    set_phase(p, PHASE_INTRO)
    p.call(SYS_STOP_AUDIO, BGM_AUDIO_SLOT)
    draw_intro_scene(p, "round_ai_demo_interrupt")
    wait_and_loop(p)
    p.label("round_after_demo_interrupt")
    process_ball_world(p)
    update_expected_landing(p, "landing_prediction")
    apply_simple_ai(
        p,
        P1_COMPUTER,
        P1_X,
        P1_Y,
        P1_STATE,
        P1_INPUT_X,
        P1_INPUT_Y,
        P1_POWER,
        P1_BOLDNESS,
        P1_STANDBY,
        P2_X,
        P1_AI_LEFT_BOUND_SCREEN,
        P1_AI_RIGHT_BOUND_SCREEN,
        P1_AI_STANDBY_X_SCREEN,
        True,
        "p1_ai",
    )
    process_player_movement(
        p,
        P1_X,
        P1_Y,
        P1_DY,
        P1_STATE,
        P1_FRAME,
        P1_INPUT_X,
        P1_INPUT_Y,
        P1_POWER,
        P1_DIVE_DIR,
        P1_LIE_TIMER,
        P1_DELAY,
        P1_SWING_DIR,
        P1_SOUND_PIKA,
        P1_SOUND_CHU,
        P1_LEFT_BOUND_SCREEN,
        P1_RIGHT_BOUND_SCREEN,
        "p1_move",
    )
    update_expected_landing(p, "landing_prediction_after_p1")
    apply_simple_ai(
        p,
        P2_COMPUTER,
        P2_X,
        P2_Y,
        P2_STATE,
        P2_INPUT_X,
        P2_INPUT_Y,
        P2_POWER,
        P2_BOLDNESS,
        P2_STANDBY,
        P1_X,
        P2_AI_LEFT_BOUND_SCREEN,
        P2_AI_RIGHT_BOUND_SCREEN,
        P2_AI_STANDBY_X_SCREEN,
        False,
        "p2_ai",
    )
    process_player_movement(
        p,
        P2_X,
        P2_Y,
        P2_DY,
        P2_STATE,
        P2_FRAME,
        P2_INPUT_X,
        P2_INPUT_Y,
        P2_POWER,
        P2_DIVE_DIR,
        P2_LIE_TIMER,
        P2_DELAY,
        P2_SWING_DIR,
        P2_SOUND_PIKA,
        P2_SOUND_CHU,
        P2_LEFT_BOUND_SCREEN,
        P2_RIGHT_BOUND_SCREEN,
        "p2_move",
    )

    collide_player(
        p,
        P1_X,
        P1_Y,
        P1_STATE,
        P1_INPUT_X,
        P1_INPUT_Y,
        P1_COLLIDING,
        "p1_collision",
    )
    collide_player(
        p,
        P2_X,
        P2_Y,
        P2_STATE,
        P2_INPUT_X,
        P2_INPUT_Y,
        P2_COLLIDING,
        "p2_collision",
    )

    update_environment_animation(p, "round_env")

    # Score only once after the 엄랭 world-physics block reports floor contact.
    if_var_nonzero_goto(p, BALL_TOUCH_GROUND, "floor_touched")
    p.emit(p.goto("floor_done"))
    p.label("floor_touched")
    if_var_nonzero_goto(p, ROUND_ENDED, "floor_done")
    if_var_nonzero_goto(p, GAME_ENDED, "floor_done")
    if_var_nonzero_goto(p, PRACTICE_MODE, "floor_done")
    p.call(SYS_LT, KEY, BALL_PUNCH_X, MID_X)
    if_var_nonzero_goto(p, KEY, "score_p2")
    call_add_const(p, SCORE1, SCORE1, 1)
    p.emit(assign(IS_P2_SERVE, num(0)))
    p.emit(p.goto("after_score"))
    p.label("score_p2")
    call_add_const(p, SCORE2, SCORE2, 1)
    p.emit(assign(IS_P2_SERVE, num(1)))
    p.label("after_score")
    p.emit(assign(ROUND_ENDED, num(1)))
    p.emit(assign(SLOW_MOTION_FRAMES_LEFT, num(6)))
    p.emit(assign(SLOW_MOTION_SKIP, num(0)))
    apply_winning_score_reset(p)
    p.emit(assign(DIGIT_CONST, num(PHASE_GAME_END)))
    call_eq(p, TMP, PHASE, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, "floor_done")
    p.label("floor_done")
    if_var_nonzero_goto(p, ROUND_ENDED, "round_maybe_finish_after_slow")
    p.emit(p.goto("round_after_finish_check"))

    p.label("round_maybe_finish_after_slow")
    if_var_nonzero_goto(p, GAME_ENDED, "round_game_end_now")
    call_eq(p, TMP, SLOW_MOTION_FRAMES_LEFT, ZERO)
    if_var_nonzero_goto(p, TMP, "round_after_end_now")
    p.emit(p.goto("round_after_finish_check"))

    p.label("round_game_end_now")
    set_phase(p, PHASE_GAME_END)
    p.emit(p.goto("round_after_finish_check"))

    p.label("round_after_end_now")
    set_phase(p, PHASE_AFTER_END_ROUND)

    p.label("round_after_finish_check")
    emit_sound_flags(p, "round")

    draw_round_scene(p, "round_main")
    wait_and_loop(p)

    p.label("after_end_round_phase")
    p.emit(assign(DIGIT_CONST, num(PHASE_AFTER_END_ROUND_END_FRAME)))
    p.call(SYS_GT, TMP, FRAME_COUNTER, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, "after_end_round_done")
    draw_round_scene(p, "after_end_round_wait")
    wait_and_loop(p)

    p.label("after_end_round_done")
    set_phase(p, PHASE_BEFORE_START_NEXT_ROUND)
    draw_round_scene(p, "after_end_round_done")
    wait_and_loop(p)

    p.label("before_start_next_round_phase")
    play_bgm_if_enabled(p, "before_start_next_round_bgm")
    call_eq(p, TMP, FRAME_COUNTER, ONE)
    if_var_nonzero_goto(p, TMP, "before_start_next_round_init")
    p.emit(p.goto("before_start_next_round_after_init"))

    p.label("before_start_next_round_init")
    p.emit(assign(GAME_ENDED, num(0)))
    p.emit(assign(SLOW_MOTION_FRAMES_LEFT, num(0)))
    p.emit(assign(SLOW_MOTION_SKIP, num(0)))
    p.emit(assign(BALL_TOUCH_GROUND, num(0)))
    reset_players(p)
    reset_ball(p, "next_round")

    p.label("before_start_next_round_after_init")
    p.emit(assign(DIGIT_CONST, num(PHASE_BEFORE_START_NEXT_ROUND_END_FRAME)))
    p.call(SYS_GT, TMP, FRAME_COUNTER, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, "before_start_next_round_done")
    draw_ready_scene(p, "before_next_round_wait")
    wait_and_loop(p)

    p.label("before_start_next_round_done")
    p.emit(assign(ROUND_ENDED, num(0)))
    set_phase(p, PHASE_ROUND)
    draw_round_scene(p, "before_next_round_done")
    wait_and_loop(p)

    p.label("game_end_phase")
    play_bgm_if_enabled(p, "game_end_bgm")
    update_game_end_player_animation(p, P1_STATE, P1_FRAME, P1_DELAY, "p1_game_end_anim")
    update_game_end_player_animation(p, P2_STATE, P2_FRAME, P2_DELAY, "p2_game_end_anim")
    call_key_pressed(p, ACTION_CONFIRM, KEY)
    call_key_pressed(p, ACTION_P2_CONFIRM, TMP)
    call_add(p, TMP2, KEY, TMP)
    p.emit(assign(DIGIT_CONST, num(GAME_END_POWER_RESTART_FRAME)))
    p.call(SYS_GT, TMP, FRAME_COUNTER, DIGIT_CONST)
    p.if_zero_goto(var(TMP), "game_end_timeout_check")
    if_var_nonzero_goto(p, TMP2, "game_end_restart")

    p.label("game_end_timeout_check")
    p.emit(assign(DIGIT_CONST, num(GAME_END_TIMEOUT_FRAME)))
    p.call(SYS_GT, TMP, FRAME_COUNTER, DIGIT_CONST)
    if_var_nonzero_goto(p, TMP, "game_end_restart")
    draw_gameover_scene(p, "gameover")
    wait_and_loop(p)

    p.label("game_end_restart")
    set_phase(p, PHASE_INTRO)
    p.call(SYS_STOP_AUDIO, BGM_AUDIO_SLOT)
    draw_intro_scene(p, "game_end_restart")
    wait_and_loop(p)

    write_chunked_script(p, MAIN_SCRIPT_PATH)


if __name__ == "__main__":
    main()
