<p align="center">
  <img src="docs/images/umkachu-volleyball-banner-en.png" alt="Umkachu Volleyball banner" width="100%">
</p>

# Umkachu Volleyball Umlang

[한국어 README](README.ko.md)

**Pikachu Volleyball, but the game logic is being dragged into 엄랭 until it screams.**

This repository is a full-porting experiment for `umkachu-volleyball-umlang`.
Rust is not the game language here. Rust is the generic 엄랭 VM, Host API, and OS/GPU/audio bridge.
The game-specific behavior is pushed into generated 엄랭 plus package ABI files such as
`umlang-game.txt`, `umlang-render.txt`, `umlang-timing.txt`, and `umlang-menu.txt`.

## TLDR

```text
umlang-package.txt
  -> scripts/pikachu.umm                 # 289,866 lines of generated 엄랭 hell
  -> umlang-*.txt                        # package ABI owned by 엄랭-side data
  -> Rust 엄랭 VM                         # generic runner, not Pikachu logic
  -> Host API(syscall)                   # graphics/input/audio/settings bridge
  -> macroquad window/GPU/keyboard/audio
```

The practical goal is not "delete Rust immediately." The goal is:

```text
Keep Rust generic.
Move Pikachu Volleyball-specific state/data/timing/render/input/logic into 엄랭 and ABI files.
```

## Quick Start

Generate the 엄랭 game first. The generated file is intentionally not committed because it is
hundreds of MB and GitHub rejects files over 100MB:

```bash
python3 tools/gen_pikachu_umm.py
```

Run the generated 엄랭 game:

```bash
cargo run
```

Run a different 엄랭 file with the same runner:

```bash
cargo run -- path/to/program.umm
```

The quick start is boring shell, but the payload is not:

```umm
어떻게
엄..........
어엄,,,,,
식어!
준..........
이 사람이름이냐ㅋㅋ
```

That is the vibe. The real local file is `scripts/pikachu.umm`, and it is generated because
hand-writing nearly 290k lines of 엄랭 would be a war crime against future maintainers.

## Current Port Shape

| Layer | Responsibility |
| --- | --- |
| `scripts/pikachu.umm` | Local generated 엄랭 program containing the current game loop and game behavior. Not committed because it is too large for GitHub. |
| `umlang-*.txt` | Package ABI files for constants, render layout, timing, menu curves, SFX policy, variables, keys, assets, RNG, sprites, animation, and settings. |
| Rust VM | Parses and executes 엄랭 syntax: variables, expressions, jumps, conditions, output, exit, and negative-output syscalls. |
| Host API | Lets 엄랭 call graphics, input, audio, settings, frame pacing, and arithmetic helpers through syscall opcodes. |
| macroquad | The replaceable host backend for the window, GPU drawing, keyboard, and audio. |

## Package ABI

The port keeps pulling game-specific constants out of Rust/Python and into text ABI files:

| ABI | Owned Data |
| --- | --- |
| `umlang-package.txt` | Main script path, asset root, VM frame budget, settings prefix, window options. |
| `umlang-syscalls.txt` | Host opcode numbers shared by Rust and the 엄랭 generator. |
| `umlang-keycodes.txt`, `umlang-keymap.txt` | Physical key codes and game action bindings. |
| `umlang-assets.txt` | Texture/audio slots, BGM/SFX banks, asset id policy inputs. |
| `umlang-palette.txt` | Color id to RGBA palette. |
| `umlang-settings.txt` | Runtime setting keys, defaults, allowed values. |
| `umlang-vars.txt` | VM variable slot ABI used by generated 엄랭. |
| `umlang-game.txt` | Game constants, physics, phases, court/player/ball defaults. |
| `umlang-player.txt` | Player state ids and movement/power/lying/win-lose transition thresholds. |
| `umlang-sprites.txt` | Player and ball atlas frame coordinates. |
| `umlang-rng.txt` | Original-style 64-bit LCG seed/multiplier bytes. |
| `umlang-render.txt` | Background, score, intro, menu, phase message, and playfield render layout. |
| `umlang-animation.txt` | Player state animation rules and draw-state sprite maps. |
| `umlang-sfx.txt` | Round/UI SFX event flags, sound ids, and side policy. |
| `umlang-timing.txt` | Intro/menu/phase fade frames, message growth, ready blink, game-end timing. |
| `umlang-menu.txt` | Menu sitting tiles, fight message pulse, title curve, selected-option pulse. |

## Controls

| Key | Action |
| --- | --- |
| Arrow keys / WASD-style mapped keys | Player movement through package key ABI. |
| Power key | Jump/power/dive/menu confirm depending on phase. |
| `Space` | Pause/resume. |
| `Backspace` | Restart intro. |
| `P` | Practice mode toggle. |
| `1`, `2`, `3` | Winning score 5/10/15. |
| `[`, `]`, `\` | Target FPS 20/30/25. |
| `B` | BGM toggle. |
| `S` | SFX mode Stereo/Mono/Off. |
| `X` | Soft/sharp texture filter. |

## Development

Do not hand-edit `scripts/pikachu.umm`; regenerate it.

```bash
python3 tools/gen_pikachu_umm.py
cargo fmt --check
cargo check
cargo test generated_menu_abi_defines_original_menu_animation_curves
cargo test generated_pikachu_script_reaches_first_frame_yield
```

Full `cargo test` works, but it can be slow because the test binary includes the huge generated
엄랭 script.

## Porting Direction

Yes, this can keep expanding toward a fuller 엄랭 port.

The realistic boundary is:

```text
엄랭 owns: game rules, state machine, render declarations, input mapping, timing, SFX policy, data.
Rust owns: generic VM execution, syscalls, OS integration, GPU/audio/window backend.
```

If a value is Pikachu Volleyball-specific, it should eventually live in generated 엄랭 or an
`umlang-*.txt` ABI file. If a value is "how a host computer draws pixels or plays sound," it stays
behind the Host API.

## Provenance

Asset provenance and redistribution notes are kept out of the README and are documented in
[docs/attribution.md](docs/attribution.md).
