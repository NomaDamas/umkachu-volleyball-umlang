# Package ABI

`package/abi` is the data contract between the committed Umlang package and the Rust VM/Host runtime.

| File | Owns |
| --- | --- |
| `umlang-package.txt` | Main `.umm` entry, asset root, VM frame budget, settings prefix, window options. |
| `umlang-syscalls.txt` | Host opcode numbers. |
| `umlang-keycodes.txt`, `umlang-keymap.txt` | Physical keys and game action bindings. |
| `umlang-assets.txt` | Texture/audio slots, BGM/SFX banks, asset id inputs. |
| `umlang-palette.txt` | Color id to RGBA palette. |
| `umlang-settings.txt` | Runtime setting keys, defaults, allowed values. |
| `umlang-vars.txt` | VM variable slot ABI used by `.umm` source. |
| `umlang-game.txt` | Game constants, physics, phases, court/player/ball defaults. |
| `umlang-player.txt` | Player state ids and movement/power/lying/win-lose thresholds. |
| `umlang-sprites.txt` | Player and ball atlas frame coordinates. |
| `umlang-rng.txt` | Original-style 64-bit LCG seed/multiplier bytes. |
| `umlang-render.txt` | Background, score, intro, menu, phase message, playfield layout. |
| `umlang-animation.txt` | Player animation rules and sprite maps. |
| `umlang-sfx.txt` | Round/UI SFX flags, sound ids, side policy. |
| `umlang-timing.txt` | Intro/menu/phase fade frames, message growth, ready blink, game-end timing. |
| `umlang-menu.txt` | Menu sitting tiles, fight message pulse, title curve, selected-option pulse. |
