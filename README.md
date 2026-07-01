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
  <a href="#-porting-plan">Porting Plan</a>
  ·
  <a href="#-core-umlang-sample">Core Umlang Sample</a>
  ·
  <a href="#-research-notes">Research Notes</a>
</p>

---

## 📚 Index

| Section | What it tells you |
| --- | --- |
| [What is this?](#-what-is-this) | The repo goal and the honest porting boundary. |
| [Umlang context](#-umlang-context) | Tiny context for how Umlang code is executed here. |
| [Porting plan](#-porting-plan) | How the project keeps moving toward an all-Umlang rewrite. |
| [Quick Start](#-quick-start) | Run the committed full Umlang game package, then inspect/regenerate it. |
| [Core Umlang Sample](#-core-umlang-sample) | A real checked-in `.umm` file that draws a tiny Umkachu court. |
| [Architecture](#-architecture) | Umlang script -> Rust VM -> Host API -> macroquad. |
| [Does it run?](#-does-it-run) | What is verified, and what still depends on local GUI/audio runtime. |
| [Reality check](#-reality-check) | Why this is not a pure Rust-free native Umlang runtime yet. |
| [Research notes](#-research-notes) | Esolang-as-IR, private code dialects, security caveats, and agent rulesets. |
| [Controls](#-controls) | Keyboard controls. |
| [Development](#-development) | Regeneration and test commands. |

## 🟡 What Is This?

`umkachu-volleyball-umlang` is a full-porting experiment: rewrite Pikachu Volleyball into **Umlang**
as the game-facing language, while keeping only unavoidable host-machine responsibilities behind a
generic runner boundary.

The current repo is not pretending that Rust disappeared. Rust is the generic **Umlang VM + Host API**
that lets Umlang talk to the real machine: window, GPU, keyboard, audio, files, settings, and frame pacing.
The game-specific state, render declarations, constants, timing, SFX policy, key bindings, and behavior live
in committed generated Umlang chunks plus `umlang-*.txt` ABI files.

```text
Umlang owns the game vibe and game-specific behavior.
Rust owns the generic runner and the OS/GPU/audio/keyboard bridge.
```

## 🧭 Porting Plan

The direction is not "leave Rust with the game." The direction is:

```text
Every Pikachu-specific rule moves to Umlang.
Every machine-specific primitive stays behind a tiny Host API until Umlang grows a native runtime.
```

| Stage | Current status | Next move |
| --- | --- | --- |
| Game rules | Generated Umlang chunks contain the current loop and behavior. | Keep extracting physics, scoring, AI, animation, and phase rules from generator structure into clearer Umlang modules. |
| Data ownership | `umlang-*.txt` owns constants, variable slots, render layout, timing, SFX policy, assets, keys, and sprites. | Promote ABI tables into more readable `.umm`-side declarations when the VM gains macros/functions. |
| Code shape | `scripts/pikachu.umm` imports 38 generated `.umm` body chunks. | Add real Umlang functions/macros/modules so chunks are semantic modules, not only size-based pieces. |
| Runtime | Rust VM parses Umlang and dispatches negative-output syscalls. | Shrink Host API to a stable device layer: draw, audio, input, storage, clock, random, frame yield. |
| Endgame | Rust remains the runner. | Either keep Rust as the official runtime or build an Umlang-native runtime/bytecode backend later. |

If the project keeps going, the next language feature worth adding is not more memes. It is **functions**:

```text
함수 draw_ball
함수 update_player
함수 collide_with_net
함수 play_round_sfx
가져와 scripts/pikachu_modules/physics.umm
```

That would let this repo stop treating generated Umlang as line-oriented assembly and start treating it as
a weird but real project language.

## 🧠 Umlang Context

In this repository, **Umlang** is the game-facing language. The context comes from the Korean internet
meme around `엄준식`, and from the original [`rycont/umjunsik-lang`](https://github.com/rycont/umjunsik-lang)
project. The meme background is documented by the Namu Wiki article
[`엄준식(인터넷 밈)`](https://namu.wiki/w/%EC%97%84%EC%A4%80%EC%8B%9D%28%EC%9D%B8%ED%84%B0%EB%84%B7%20%EB%B0%88%29).

The original `umjunsik-lang` README describes the language as an esoteric programming language built around
the "person name" meme, and documents the core tokens this project follows: `엄`, `준`, `식`, `동탄`,
`어떻게`, `화이팅!`, punctuation-based integers, `식!` output, `식ㅋ` character output, `동탄?`
conditionals, and `준` jumps.

A `.umm` file starts with `어떻게`, ends with `이 사람이름이냐ㅋㅋ`, stores numbers in `어/엄` variable slots,
prints or calls the host with `식...!`, and jumps with `준...`.

Tiny mental model:

| Umlang shape | Meaning in this runner |
| --- | --- |
| `어떻게` | Program start. |
| `이 사람이름이냐ㅋㅋ` | Program end. |
| `엄.....` | Store a value in variable slot 1. |
| `어엄.....` | Store a value in variable slot 2. |
| `식어!` | Execute output; negative values become Host API syscalls. |
| `준.....` | Jump to a line number. |
| `가져와 ...` | Include another `.umm` file before execution. |

So yes: the code looks cursed on purpose, but the VM treats it as real executable instructions.

## 🚀 Quick Start

### 1. Run the committed Umkachu Volleyball Umlang package

The full game entry is committed as `scripts/pikachu.umm`, and the generated Umlang body is committed
as `scripts/pikachu_parts/*.umm` chunks so GitHub's single-file 100MB limit is not hit.

```bash
cargo run
```

This runs the Rust Umlang VM, expands the `가져와` imports, and executes the generated Umlang game.

### 2. Run the checked-in Umlang mini court

This is the small promotional sample committed in the repo:

```bash
cargo run -- examples/umkachu-core.umm
```

It runs real Umlang through the same runner and draws a tiny Umkachu court using Host API syscalls.

### 3. Regenerate the full generated Umlang package

```bash
python3 tools/gen_pikachu_umm.py
```

The regenerated payload is still cursed, just split into importable chunks:

```umm
어떻게
가져와 scripts/pikachu_parts/pikachu_0000.umm
가져와 scripts/pikachu_parts/pikachu_0001.umm
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
  -> scripts/pikachu.umm                 # committed Umlang entry file
  -> scripts/pikachu_parts/*.umm         # committed generated full game body
  -> examples/umkachu-core.umm           # committed tiny Umlang court sample
  -> umlang-*.txt                        # package ABI owned by game-side data
  -> Rust Umlang VM                      # generic runner, not Pikachu-specific logic
  -> Host API(syscall)                   # graphics/input/audio/settings bridge
  -> macroquad window/GPU/keyboard/audio
```

| Layer | Responsibility |
| --- | --- |
| `examples/umkachu-core.umm` | Small committed Umlang sample that draws a looping mini court. |
| `scripts/pikachu.umm` | Small committed Umlang entry file that imports the full generated game body. |
| `scripts/pikachu_parts/*.umm` | Committed generated Umlang chunks containing the current full game loop and game behavior. |
| `umlang-*.txt` | Package ABI files for constants, render layout, timing, menu curves, SFX policy, variables, keys, assets, RNG, sprites, animation, and settings. |
| Rust VM | Parses and executes Umlang syntax: variables, expressions, jumps, conditions, output, exit, and negative-output syscalls. |
| Host API | Lets Umlang call graphics, input, audio, settings, frame pacing, and arithmetic helpers through syscall opcodes. |
| macroquad | Replaceable backend for the window, GPU drawing, keyboard, and audio. |

### Umlang-Native Porting Architecture

```text
                    ┌──────────────────────────────────────────────┐
                    │              Umlang game package             │
                    │ scripts/pikachu.umm + pikachu_parts/*.umm    │
                    └──────────────────────┬───────────────────────┘
                                           │ 가져와/import expansion
                    ┌──────────────────────▼───────────────────────┐
                    │                 Umlang VM                     │
                    │ parse -> line IR -> variable slots -> jumps   │
                    └──────────────────────┬───────────────────────┘
                                           │ negative 식...! syscall
                    ┌──────────────────────▼───────────────────────┐
                    │                  Host API                     │
                    │ draw/input/audio/settings/random/frame yield  │
                    └──────────────────────┬───────────────────────┘
                                           │ backend calls
                    ┌──────────────────────▼───────────────────────┐
                    │                 macroquad/Rust                │
                    │ window, GPU, keyboard, audio, file settings   │
                    └──────────────────────────────────────────────┘
```

The important boundary is not "Rust vs Umlang" as a vibe argument. The boundary is **semantic ownership**:

| Owned by Umlang | Owned by Host |
| --- | --- |
| Round phases, scoring, serve flow, AI movement, collision decisions, animation frame choice, render declarations, SFX policy. | Window creation, GPU draw calls, keyboard polling, audio playback, persistent settings, frame pacing. |

In compiler terms, this repo is slowly turning Pikachu Volleyball into a domain-specific source program where
Umlang is the high-level game IR and Rust is the VM/backend.

## ✅ Does It Run?

Short answer: **the runner builds, the generated Umlang parses, and the script reaches frame yield in tests.**

What is verified in CI-style commands:

| Check | Meaning |
| --- | --- |
| `python3 -m py_compile tools/gen_pikachu_umm.py` | The generator is syntactically valid Python. |
| `cargo fmt --check` | Rust formatting is clean. |
| `cargo check` | The Rust Umlang VM/Host API builds. |
| `cargo test generated_pikachu_script_reaches_first_frame_yield` | The generated chunked `scripts/pikachu.umm` package parses and reaches the first frame yield. |

What still depends on your local machine:

| Runtime piece | Why |
| --- | --- |
| Window/GPU/audio | macroquad needs a local GUI/audio-capable environment. |
| Full gameplay feel | The generated script is huge, so local runtime performance matters. |

## ⚠️ Reality Check

| Requested pure-Umlang dream | Current honest state |
| --- | --- |
| Graphics/audio/keyboard entirely in Umlang | Umlang has no native OS/GPU/audio/keyboard runtime here, so Rust Host API handles it. |
| Commit the generated Umlang body | Done by splitting the old 901MB single blob into 38 committed `scripts/pikachu_parts/*.umm` files below GitHub's 100MB single-file limit. |
| Hand-write the whole game in pure Umlang | The full generated code is intentionally produced by Python because manual 290k-line Umlang editing is not maintainable. |
| Remove Rust completely | Not possible in this repo yet. Rust is the current Umlang runner and OS/GPU/audio bridge. |

The honest target is therefore:

```text
Move game-specific behavior into Umlang.
Keep host-machine responsibilities behind a generic runner boundary.
```

## 🧪 Research Notes

This project is a joke that accidentally touches serious systems topics.

### Esolang As Project IR

An esolang can act like a domain-specific intermediate representation:

| Angle | Why it is interesting |
| --- | --- |
| Semantic compression | Game concepts can be encoded in a tiny project-specific instruction set instead of a general-purpose language surface. |
| Runtime sovereignty | The team owns the VM, syscalls, ABI, and execution semantics. That makes behavior reproducible and inspectable. |
| Agent specialization | Codex/Claude Code rules can be tuned to the project dialect, ABI files, generated chunks, and VM invariants. |
| Weird portability | If the Host API is stable, the same `.umm` game package can target different backends. |

### Private Dialects And Security

Could a company create its own weird language, keep a private interpreter, add strict AI-agent rules, and gain
security? **Some friction, yes. Real security by itself, no.**

| Claim | Practical answer |
| --- | --- |
| "Nobody understands our code." | That is obfuscation, not cryptographic protection. It slows casual readers but does not stop a determined analyst. |
| "Only our interpreter runs it." | Useful for supply-chain control and policy enforcement, but the interpreter becomes a high-value target. |
| "Codex/Claude rules know the dialect." | Very useful for internal productivity: agents can enforce ABI rules, naming, generation, tests, and threat-model checks. |
| "Can it protect private logic?" | Only when combined with real controls: repo permissions, secret management, signing, review, sandboxing, audit logs, and encryption. |

The geeky research hypothesis:

```text
organization-specific esolang
  + private VM / verifier
  + generated source chunks
  + strict agent rules
  + reproducible tests
  = a controllable software substrate
```

Not a magic shield. But as a project-native DSL/IR, it can encode intent, limit allowed operations, and make
AI-assisted development safer because the assistant has fewer legal moves.

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

Do not hand-edit `scripts/pikachu.umm` or `scripts/pikachu_parts/*.umm`; regenerate them.

```bash
python3 tools/gen_pikachu_umm.py
cargo fmt --check
cargo check
cargo test generated_menu_abi_defines_original_menu_animation_curves
cargo test generated_pikachu_script_reaches_first_frame_yield
```

Full `cargo test` works, but tests that execute the generated game can be slow because the committed
Umlang chunks are large.

## 🧾 Provenance

Asset provenance and redistribution notes are kept out of the README and documented in
[`docs/attribution.md`](docs/attribution.md).
