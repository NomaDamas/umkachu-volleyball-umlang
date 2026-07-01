<p align="center">
  <img src="docs/images/umkachu-volleyball-banner-en.png" alt="Umkachu Volleyball banner" width="100%">
</p>

<h1 align="center">⚡ Umkachu Volleyball Umlang ⚡</h1>

<p align="center">
  <strong>Pikachu Volleyball as a committed Umlang game package, executed by a Rust Umlang VM.</strong>
</p>

<p align="center">
  <a href="README.ko.md">한국어 README</a>
  ·
  <a href="#-quick-start">Quick Start</a>
  ·
  <a href="#-core-umlang">Core Umlang</a>
  ·
  <a href="#-architecture">Architecture</a>
  ·
  <a href="#-package-abi">Package ABI</a>
</p>

---

## 📚 Index

| Section | Signal |
| --- | --- |
| [What is this?](#-what-is-this) | The project identity: Umkachu Volleyball as an Umlang-first game package. |
| [Umlang context](#-umlang-context) | Where the language/meme comes from and how this runner executes it. |
| [Quick Start](#-quick-start) | Run the full `.umm` package and the small core sample. |
| [Core Umlang](#-core-umlang) | The tiny executable pattern behind the full game. |
| [Architecture](#-architecture) | Umlang source, package ABI, Rust VM, Host API, macroquad backend. |
| [Package ABI](#-package-abi) | The ABI files now live in `package/abi/`. |
| [Research Notes](#-research-notes) | Esolang-as-IR, private dialect security, and agent-tuned development. |
| [Controls](#-controls) | Keyboard actions. |
| [Development](#-development) | Rust-only build and validation commands. |

## 🟡 What Is This?

`umkachu-volleyball-umlang` packages Pikachu Volleyball as **Umlang** source:

```text
scripts/pikachu.umm
  -> 가져와 scripts/pikachu_parts/pikachu_0000.umm
  -> 가져와 scripts/pikachu_parts/pikachu_0001.umm
  -> ...
```

The `.umm` files are the game-facing program. Rust is the language runtime: it parses Umlang, expands
`가져와` imports, executes variable/jump/output instructions, and exposes a Host API for windowing,
textures, audio, keyboard input, settings, timing, and frame pacing.

```text
Umlang owns the game package.
Rust owns the VM/backend that lets that package touch the machine.
```

The repository is intentionally shaped like a language port, not like a Rust game with a mascot skin.
Game constants, sprite layout, palette, key bindings, SFX policy, timing, menu curves, and VM variable slots
are moved into package ABI files under [`package/abi`](package/abi).

## 🧠 Umlang Context

**Umlang** is an esoteric language inspired by the Korean internet meme around `엄준식`. This repository
follows the spirit and core tokens documented by [`rycont/umjunsik-lang`](https://github.com/rycont/umjunsik-lang)
and links the meme context through
[`엄준식(인터넷 밈)`](https://namu.wiki/w/%EC%97%84%EC%A4%80%EC%8B%9D%28%EC%9D%B8%ED%84%B0%EB%84%B7%20%EB%B0%88%29).

In this runner, the important shapes are:

| Umlang | Runtime meaning |
| --- | --- |
| `어떻게` | Program start. |
| `이 사람이름이냐ㅋㅋ` | Program end. |
| `엄.....` | Store a number in variable slot 1. |
| `어엄.....` | Store a number in variable slot 2. |
| `식어!` | Output or Host API syscall dispatch. |
| `준.....` | Jump to a line number. |
| `동탄...?...` | Conditional statement. |
| `가져와 path.umm` | Import another Umlang source file before execution. |

It looks like a meme. The VM treats it as executable source.

## 🚀 Quick Start

### Run Umkachu Volleyball

```bash
cargo run
```

`cargo run` reads [`package/abi/umlang-package.txt`](package/abi/umlang-package.txt), loads
[`scripts/pikachu.umm`](scripts/pikachu.umm), expands the chunked Umlang body, and starts the game.

### Run The Small Umlang Court

```bash
cargo run -- examples/umkachu-core.umm
```

This sample is a compact `.umm` file that draws a small court through the same VM and Host API.

### Inspect The Umlang Entry

```umm
어떻게
가져와 scripts/pikachu_parts/pikachu_0000.umm
가져와 scripts/pikachu_parts/pikachu_0001.umm
가져와 scripts/pikachu_parts/pikachu_0002.umm
이 사람이름이냐ㅋㅋ
```

The full body is split into committed `.umm` parts so the package remains GitHub-friendly while staying
inside the repository as actual Umlang source.

## 🧩 Core Umlang

The checked-in sample lives at [`examples/umkachu-core.umm`](examples/umkachu-core.umm).

It is intentionally written as Umlang source, not pseudocode:

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

The core syscall pattern is:

```text
1. Put a Host API opcode into variable slot 1.
2. Put syscall arguments into variable slots 2, 3, 4...
3. Execute `식어!`.
4. The Rust VM dispatches the opcode to the Host API.
5. Umlang continues with jumps, variables, and frame yields.
```

That sample is the smallest readable version of the full Umkachu Volleyball loop: put a Host opcode in
Umlang variable slot 1, put arguments in later slots, execute `식어!`, then jump back into the frame loop.

Another excerpt from the full package entry shows how the real body is imported:

```umm
어떻게
가져와 scripts/pikachu_parts/pikachu_0000.umm
가져와 scripts/pikachu_parts/pikachu_0001.umm
가져와 scripts/pikachu_parts/pikachu_0002.umm
이 사람이름이냐ㅋㅋ
```

## 🏗 Architecture

```text
┌────────────────────────────────────────────────────────────┐
│ Umlang package                                             │
│ scripts/pikachu.umm + scripts/pikachu_parts/*.umm          │
└──────────────────────────────┬─────────────────────────────┘
                               │ 가져와/import expansion
┌──────────────────────────────▼─────────────────────────────┐
│ Package ABI                                                 │
│ package/abi/umlang-*.txt                                    │
└──────────────────────────────┬─────────────────────────────┘
                               │ constants, slots, assets, keys
┌──────────────────────────────▼─────────────────────────────┐
│ Rust Umlang VM                                              │
│ parse -> line IR -> variable slots -> jumps -> syscall      │
└──────────────────────────────┬─────────────────────────────┘
                               │ negative/output dispatch
┌──────────────────────────────▼─────────────────────────────┐
│ Host API                                                    │
│ draw, texture, audio, input, settings, timing, frame yield   │
└──────────────────────────────┬─────────────────────────────┘
                               │ backend calls
┌──────────────────────────────▼─────────────────────────────┐
│ macroquad/Rust backend                                      │
│ window, GPU, keyboard, audio, filesystem settings           │
└────────────────────────────────────────────────────────────┘
```

| Layer | Responsibility |
| --- | --- |
| `.umm` package | Game-facing executable source and imported body chunks. |
| `package/abi` | Stable data contract shared by the VM, host, tests, and Umlang package. |
| Rust VM | Umlang parser, import expander, lazy bytecode compiler, jump engine, syscall dispatcher. |
| Host API | Device boundary for graphics, input, audio, settings, arithmetic helpers, frame yield. |
| macroquad | Concrete desktop backend. |

The VM preserves the Korean/Umlang source surface. It does not need to re-interpret Hangul strings forever:
the source is loaded as text, then each executed line is compiled once into a small internal instruction and
cached. The visible language stays Umlang; the hot path becomes VM bytecode.

## 📦 Package ABI

All ABI files are grouped under [`package/abi`](package/abi):

| ABI | Owned data |
| --- | --- |
| `package/abi/umlang-package.txt` | Main script path, asset root, VM frame budget, settings prefix, window options. |
| `package/abi/umlang-syscalls.txt` | Host opcode numbers shared by Rust and the Umlang package. |
| `package/abi/umlang-keycodes.txt`, `package/abi/umlang-keymap.txt` | Physical key codes and game action bindings. |
| `package/abi/umlang-assets.txt` | Texture/audio slots, BGM/SFX banks, asset id policy inputs. |
| `package/abi/umlang-palette.txt` | Color id to RGBA palette. |
| `package/abi/umlang-settings.txt` | Runtime setting keys, defaults, allowed values. |
| `package/abi/umlang-vars.txt` | VM variable slot ABI used by the Umlang package. |
| `package/abi/umlang-game.txt` | Game constants, physics, phases, court/player/ball defaults. |
| `package/abi/umlang-player.txt` | Player state ids and movement/power/lying/win-lose transition thresholds. |
| `package/abi/umlang-sprites.txt` | Player and ball atlas frame coordinates. |
| `package/abi/umlang-rng.txt` | Original-style 64-bit LCG seed/multiplier bytes. |
| `package/abi/umlang-render.txt` | Background, score, intro, menu, phase message, and playfield render layout. |
| `package/abi/umlang-animation.txt` | Player state animation rules and draw-state sprite maps. |
| `package/abi/umlang-sfx.txt` | Round/UI SFX event flags, sound ids, and side policy. |
| `package/abi/umlang-timing.txt` | Intro/menu/phase fade frames, message growth, ready blink, game-end timing. |
| `package/abi/umlang-menu.txt` | Menu sitting tiles, fight message pulse, title curve, selected-option pulse. |

## 🧪 Research Notes

Umkachu treats an esolang as a project IR:

| Angle | Geek value |
| --- | --- |
| Runtime sovereignty | The project owns syntax, ABI, VM semantics, syscalls, and tests. |
| Dialect compression | Game concepts become project-specific instructions and data contracts. |
| Agent specialization | Codex/Claude rules can target the dialect, ABI invariants, and checked-in `.umm` package. |
| Private dialect security | A company can pair a custom language, private VM, signed packages, and strict agent rules to narrow the legal move space. |

### LLMs And Private Dialects

GPT-class models may have seen public `umjunsik-lang` material, but they should not be assumed to know a
company's private dialect, ABI, verifier, package format, or interpreter behavior. That is useful: the model
can be given project-specific rules, while outsiders only see an unfamiliar source surface unless they also
obtain the interpreter, ABI, and runtime policy.

### Security Significance

A private language is not cryptography by itself. The real security value appears when the dialect is part of
a controlled software substrate:

```text
organization-specific language
  + private interpreter / verifier
  + signed package ABI
  + sandboxed Host API
  + audit logs
  + Codex/Claude rules tuned to the dialect
  = narrower and more enforceable development surface
```

That can improve policy enforcement, review discipline, reproducibility, and accidental data-flow control.
It should still be paired with normal security controls: permissions, secrets management, signing, encryption,
review, sandboxing, and monitoring.

## 🎮 Controls

| Key | Action |
| --- | --- |
| Arrow keys / mapped movement keys | Player movement through package key ABI. |
| Power key | Jump, power hit, dive, or menu confirm depending on phase. |
| `Space` | Pause/resume. |
| `Backspace` | Restart intro. |
| `P` | Practice mode toggle. |
| `1`, `2`, `3` | Winning score 5/10/15. |
| `[`, `]`, `\` | Target FPS 20/30/25. |
| `B` | BGM toggle. |
| `S` | SFX mode Stereo/Mono/Off. |
| `X` | Soft/sharp texture filter. |

## 🛠 Development

Rust-only validation path:

```bash
cargo fmt --check
cargo check
cargo test generated_menu_abi_defines_original_menu_animation_curves
cargo test generated_pikachu_script_reaches_first_frame_yield
```

Full `cargo test` also works, though tests that execute the large committed Umlang package take longer.

## 🧾 Provenance

Asset provenance and redistribution notes are kept in [`docs/attribution.md`](docs/attribution.md).
