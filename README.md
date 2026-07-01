<p align="center">
  <img src="docs/images/umkachu-volleyball-banner-en.png" alt="Umkachu Volleyball banner" width="100%">
</p>

<h1 align="center">⚡ Umkachu Volleyball Umlang ⚡</h1>

<p align="center">
  <strong>Pikachu Volleyball, dragged into Umlang until the game loop speaks in 엄.</strong>
</p>

<p align="center">
  <a href="README.ko.md">한국어 README</a>
  ·
  <a href="#-quick-start">Quick Start</a>
  ·
  <a href="#-core-umlang-sample">Core Umlang Sample</a>
  ·
  <a href="#-does-it-run">Does It Run?</a>
</p>

---

## 📚 Index

| Section | What it tells you |
| --- | --- |
| [What is this?](#-what-is-this) | The repo goal and the honest porting boundary. |
| [Umlang context](#-umlang-context) | Tiny context for how Umlang code is executed here. |
| [Quick Start](#-quick-start) | Run a small Umlang sample, then generate and run the full game script. |
| [Core Umlang Sample](#-core-umlang-sample) | A real checked-in `.umm` file that draws a tiny Umkachu court. |
| [Architecture](#-architecture) | Umlang script -> Rust VM -> Host API -> macroquad. |
| [Does it run?](#-does-it-run) | What is verified, and what still depends on local GUI/audio runtime. |
| [Reality check](#-reality-check) | Why this is not a pure Rust-free native Umlang runtime yet. |
| [Controls](#-controls) | Keyboard controls. |
| [Development](#-development) | Regeneration and test commands. |

## 🟡 What Is This?

`umkachu-volleyball-umlang` is a full-porting experiment: move as much Pikachu Volleyball-specific
behavior as possible into **Umlang** code and text ABI files.

The current repo is not pretending that Rust disappeared. Rust is the generic **Umlang VM + Host API**
that lets Umlang talk to the real machine: window, GPU, keyboard, audio, files, settings, and frame pacing.
The game-specific state, render declarations, constants, timing, SFX policy, key bindings, and behavior are
being pulled into generated Umlang and `umlang-*.txt` ABI files.

```text
Umlang owns the game vibe and game-specific behavior.
Rust owns the generic runner and the OS/GPU/audio/keyboard bridge.
```

## 🧠 Umlang Context

In this repository, **Umlang** is the game-facing language. A `.umm` file starts with `어떻게`,
ends with `이 사람이름이냐ㅋㅋ`, stores numbers in `어/엄` variable slots, prints or calls the host with
`식...!`, and jumps with `준...`.

Tiny mental model:

| Umlang shape | Meaning in this runner |
| --- | --- |
| `어떻게` | Program start. |
| `이 사람이름이냐ㅋㅋ` | Program end. |
| `엄.....` | Store a value in variable slot 1. |
| `어엄.....` | Store a value in variable slot 2. |
| `식어!` | Execute output; negative values become Host API syscalls. |
| `준.....` | Jump to a line number. |

So yes: the code looks cursed on purpose, but the VM treats it as real executable instructions.

## 🚀 Quick Start

### 1. Run the checked-in Umlang mini court

This is the small promotional sample committed in the repo:

```bash
cargo run -- examples/umkachu-core.umm
```

It runs real Umlang through the same runner and draws a tiny Umkachu court using Host API syscalls.

### 2. Generate the full generated Umlang game script

The full `scripts/pikachu.umm` file is generated locally. It is intentionally not committed because it is
about 901MB on disk and GitHub rejects files over 100MB.

```bash
python3 tools/gen_pikachu_umm.py
```

### 3. Run Umkachu Volleyball

```bash
cargo run
```

The boring shell command launches the cursed payload:

```umm
어떻게
엄..........
어엄,,,,,
식어!
준..........
이 사람이름이냐ㅋㅋ
```

## 🧩 Core Umlang Sample

The checked-in sample lives at [`examples/umkachu-core.umm`](examples/umkachu-core.umm).

It demonstrates the core loop used by the big generated game:

```text
1. Put a negative Host API opcode into variable 1.
2. Put syscall arguments into variables 2, 3, 4...
3. Run `식어!`.
4. The Rust Umlang VM sees the negative value and calls the Host API.
5. The Host API draws rectangles, circles, text, or yields a frame.
6. `준...` jumps back to the draw loop.
```

Example excerpt:

```umm
어떻게
엄,,,,,,,,,,
어엄....................
어어엄.... .........................................................................
어어어엄............. ....
어어어어엄................ ..
어어어어어엄..
식어!
엄,,,,,,,,,
식어!
준................. ..
이 사람이름이냐ㅋㅋ
```

That excerpt calls `SYS_DRAW_NUMBER`, then `SYS_WAIT_FRAME`, then jumps back into the render loop.

## 🏗 Architecture

```text
umlang-package.txt
  -> scripts/pikachu.umm                 # generated full Umlang game, local only
  -> examples/umkachu-core.umm           # committed tiny Umlang court sample
  -> umlang-*.txt                        # package ABI owned by game-side data
  -> Rust Umlang VM                      # generic runner, not Pikachu-specific logic
  -> Host API(syscall)                   # graphics/input/audio/settings bridge
  -> macroquad window/GPU/keyboard/audio
```

| Layer | Responsibility |
| --- | --- |
| `examples/umkachu-core.umm` | Small committed Umlang sample that draws a looping mini court. |
| `scripts/pikachu.umm` | Local generated Umlang program containing the current full game loop and game behavior. |
| `umlang-*.txt` | Package ABI files for constants, render layout, timing, menu curves, SFX policy, variables, keys, assets, RNG, sprites, animation, and settings. |
| Rust VM | Parses and executes Umlang syntax: variables, expressions, jumps, conditions, output, exit, and negative-output syscalls. |
| Host API | Lets Umlang call graphics, input, audio, settings, frame pacing, and arithmetic helpers through syscall opcodes. |
| macroquad | Replaceable backend for the window, GPU drawing, keyboard, and audio. |

## ✅ Does It Run?

Short answer: **the runner builds, the generated Umlang parses, and the script reaches frame yield in tests.**

What is verified in CI-style commands:

| Check | Meaning |
| --- | --- |
| `python3 -m py_compile tools/gen_pikachu_umm.py` | The generator is syntactically valid Python. |
| `cargo fmt --check` | Rust formatting is clean. |
| `cargo check` | The Rust Umlang VM/Host API builds. |
| `cargo test generated_pikachu_script_reaches_first_frame_yield` | The generated `scripts/pikachu.umm` parses and reaches the first frame yield. |

What still depends on your local machine:

| Runtime piece | Why |
| --- | --- |
| Window/GPU/audio | macroquad needs a local GUI/audio-capable environment. |
| Full gameplay feel | The generated script is huge, so local runtime performance matters. |

## ⚠️ Reality Check

| Requested pure-Umlang dream | Current honest state |
| --- | --- |
| Graphics/audio/keyboard entirely in Umlang | Umlang has no native OS/GPU/audio/keyboard runtime here, so Rust Host API handles it. |
| Commit `scripts/pikachu.umm` directly | The generated file is about 901MB, so it is generated locally instead of committed. |
| Hand-write the whole game in pure Umlang | The full generated code is intentionally produced by Python because manual 290k-line Umlang editing is not maintainable. |
| Remove Rust completely | Not possible in this repo yet. Rust is the current Umlang runner and OS/GPU/audio bridge. |

The honest target is therefore:

```text
Move game-specific behavior into Umlang.
Keep host-machine responsibilities behind a generic runner boundary.
```

## 📦 Package ABI

| ABI | Owned data |
| --- | --- |
| `umlang-package.txt` | Main script path, asset root, VM frame budget, settings prefix, window options. |
| `umlang-syscalls.txt` | Host opcode numbers shared by Rust and the Umlang generator. |
| `umlang-keycodes.txt`, `umlang-keymap.txt` | Physical key codes and game action bindings. |
| `umlang-assets.txt` | Texture/audio slots, BGM/SFX banks, asset id policy inputs. |
| `umlang-palette.txt` | Color id to RGBA palette. |
| `umlang-settings.txt` | Runtime setting keys, defaults, allowed values. |
| `umlang-vars.txt` | VM variable slot ABI used by generated Umlang. |
| `umlang-game.txt` | Game constants, physics, phases, court/player/ball defaults. |
| `umlang-player.txt` | Player state ids and movement/power/lying/win-lose transition thresholds. |
| `umlang-sprites.txt` | Player and ball atlas frame coordinates. |
| `umlang-rng.txt` | Original-style 64-bit LCG seed/multiplier bytes. |
| `umlang-render.txt` | Background, score, intro, menu, phase message, and playfield render layout. |
| `umlang-animation.txt` | Player state animation rules and draw-state sprite maps. |
| `umlang-sfx.txt` | Round/UI SFX event flags, sound ids, and side policy. |
| `umlang-timing.txt` | Intro/menu/phase fade frames, message growth, ready blink, game-end timing. |
| `umlang-menu.txt` | Menu sitting tiles, fight message pulse, title curve, selected-option pulse. |

## 🎮 Controls

| Key | Action |
| --- | --- |
| Arrow keys / mapped movement keys | Player movement through package key ABI. |
| Power key | Jump/power/dive/menu confirm depending on phase. |
| `Space` | Pause/resume. |
| `Backspace` | Restart intro. |
| `P` | Practice mode toggle. |
| `1`, `2`, `3` | Winning score 5/10/15. |
| `[`, `]`, `\` | Target FPS 20/30/25. |
| `B` | BGM toggle. |
| `S` | SFX mode Stereo/Mono/Off. |
| `X` | Soft/sharp texture filter. |

## 🛠 Development

Do not hand-edit `scripts/pikachu.umm`; regenerate it.

```bash
python3 tools/gen_pikachu_umm.py
cargo fmt --check
cargo check
cargo test generated_menu_abi_defines_original_menu_animation_curves
cargo test generated_pikachu_script_reaches_first_frame_yield
```

Full `cargo test` works, but it can be slow because the test binary includes the huge generated
Umlang script.

## 🧾 Provenance

Asset provenance and redistribution notes are kept out of the README and documented in
[`docs/attribution.md`](docs/attribution.md).
