<p align="center">
  <img src="docs/images/umkachu-volleyball-banner-ko.png" alt="엄카츄 배구 배너" width="100%">
</p>

<h1 align="center">⚡ 엄카츄 배구 엄랭 ⚡</h1>

<p align="center">
  <strong>피카츄배구를 커밋된 엄랭 게임 패키지로 실행하는 Rust 엄랭 VM 프로젝트.</strong>
</p>

<p align="center">
  <a href="README.md">English README</a>
  ·
  <a href="#-quick-start">Quick Start</a>
  ·
  <a href="#-코어-엄랭">코어 엄랭</a>
  ·
  <a href="#-아키텍처">아키텍처</a>
  ·
  <a href="#-패키지-abi">패키지 ABI</a>
</p>

---

## 📚 Index

| 섹션 | 핵심 |
| --- | --- |
| [이 프로젝트](#-이-프로젝트) | 엄카츄 배구를 엄랭 우선 게임 패키지로 다루는 방식. |
| [엄랭 Context](#-엄랭-context) | 엄랭 밈/언어 배경과 이 실행기의 해석 방식. |
| [Quick Start](#-quick-start) | 전체 `.umm` 패키지와 작은 코어 샘플 실행. |
| [코어 엄랭](#-코어-엄랭) | 전체 게임이 쓰는 최소 실행 패턴. |
| [아키텍처](#-아키텍처) | 엄랭 소스, 패키지 ABI, Rust VM, Host API, macroquad backend. |
| [패키지 ABI](#-패키지-abi) | `package/abi/`로 모은 ABI 파일들. |
| [연구 메모](#-연구-메모) | 난해어 IR, private dialect 보안, agent 최적화 개발. |
| [조작](#-조작) | 키보드 조작. |
| [개발](#-개발) | Rust-only 빌드와 검증 명령. |

## 🟡 이 프로젝트

`umkachu-volleyball-umlang`는 피카츄배구를 **엄랭** 소스 패키지로 실행합니다.

```text
scripts/pikachu.umm
  -> 가져와 scripts/pikachu_parts/pikachu_0000.umm
  -> 가져와 scripts/pikachu_parts/pikachu_0001.umm
  -> ...
```

`.umm` 파일들이 게임 쪽 프로그램입니다. Rust는 언어 실행기입니다. 엄랭을 파싱하고, `가져와`
import를 펼치고, 변수/점프/출력 명령을 실행하고, 창/텍스처/오디오/키보드/설정/타이밍/frame pacing을
Host API로 연결합니다.

```text
엄랭은 게임 패키지를 가진다.
Rust는 그 패키지가 실제 기계와 통신할 수 있게 하는 VM/backend를 가진다.
```

이 레포는 Rust 게임에 밈 문법을 덧씌우는 방향이 아니라, 엄랭을 게임 소스 표면으로 놓는 방향입니다.
게임 상수, 스프라이트 배치, 팔레트, 키 매핑, SFX 정책, 타이밍, 메뉴 커브, VM 변수 슬롯 ABI는
[`package/abi`](package/abi)에 모았습니다.

## 🧠 엄랭 Context

**엄랭**은 `엄준식` 인터넷 밈에서 출발한 난해한 프로그래밍 언어 계열입니다. 이 레포는
[`rycont/umjunsik-lang`](https://github.com/rycont/umjunsik-lang)의 핵심 토큰과 감각을 따르고,
밈 배경은 [`엄준식(인터넷 밈)`](https://namu.wiki/w/%EC%97%84%EC%A4%80%EC%8B%9D%28%EC%9D%B8%ED%84%B0%EB%84%B7%20%EB%B0%88%29)
문서를 연결합니다.

이 실행기에서 중요한 엄랭 모양은 아래와 같습니다.

| 엄랭 | 실행 의미 |
| --- | --- |
| `어떻게` | 프로그램 시작. |
| `이 사람이름이냐ㅋㅋ` | 프로그램 끝. |
| `엄.....` | 변수 슬롯 1에 숫자 저장. |
| `어엄.....` | 변수 슬롯 2에 숫자 저장. |
| `식어!` | 출력 또는 Host API syscall dispatch. |
| `준.....` | 줄 번호로 점프. |
| `동탄...?...` | 조건 실행. |
| `가져와 path.umm` | 실행 전에 다른 엄랭 소스 import. |

겉보기에는 밈이지만, VM 안에서는 실제 실행 가능한 소스입니다.

## 🚀 Quick Start

### 엄카츄 배구 실행

```bash
cargo run
```

`cargo run`은 [`package/abi/umlang-package.txt`](package/abi/umlang-package.txt)를 읽고,
[`scripts/pikachu.umm`](scripts/pikachu.umm)을 로드한 뒤, chunk로 나뉜 엄랭 본체를 펼쳐 실행합니다.

### 작은 엄랭 코트 실행

```bash
cargo run -- examples/umkachu-core.umm
```

이 샘플은 같은 VM과 Host API로 작은 코트를 그리는 짧은 `.umm` 파일입니다.

### 엄랭 entry 보기

```umm
어떻게
가져와 scripts/pikachu_parts/pikachu_0000.umm
가져와 scripts/pikachu_parts/pikachu_0001.umm
가져와 scripts/pikachu_parts/pikachu_0002.umm
이 사람이름이냐ㅋㅋ
```

전체 본체는 커밋된 `.umm` part로 나뉘어 있습니다. GitHub에 올릴 수 있는 크기를 유지하면서도
레포 안에 실제 엄랭 소스 패키지가 남아 있게 한 구조입니다.

## 🧩 코어 엄랭

커밋된 샘플은 [`examples/umkachu-core.umm`](examples/umkachu-core.umm)에 있습니다.

이 샘플은 설명용 pseudocode가 아니라 실제 엄랭 소스입니다.

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

핵심 syscall 패턴은 이렇습니다.

```text
1. 변수 슬롯 1에 Host API opcode를 넣는다.
2. 변수 슬롯 2, 3, 4...에 syscall 인자를 넣는다.
3. `식어!`를 실행한다.
4. Rust VM이 opcode를 Host API로 dispatch한다.
5. 엄랭은 변수, 점프, frame yield로 계속 진행한다.
```

이 샘플은 전체 엄카츄 배구 루프의 가장 작은 버전입니다. 엄랭 변수 슬롯 1에 Host opcode를 넣고,
뒤쪽 슬롯에 인자를 넣고, `식어!`로 실행한 다음 frame loop로 다시 점프합니다.

실제 전체 패키지 entry는 아래처럼 엄랭 본체를 import합니다.

```umm
어떻게
가져와 scripts/pikachu_parts/pikachu_0000.umm
가져와 scripts/pikachu_parts/pikachu_0001.umm
가져와 scripts/pikachu_parts/pikachu_0002.umm
이 사람이름이냐ㅋㅋ
```

## 🏗 아키텍처

```text
┌────────────────────────────────────────────────────────────┐
│ 엄랭 패키지                                                │
│ scripts/pikachu.umm + scripts/pikachu_parts/*.umm          │
└──────────────────────────────┬─────────────────────────────┘
                               │ 가져와/import expansion
┌──────────────────────────────▼─────────────────────────────┐
│ 패키지 ABI                                                  │
│ package/abi/umlang-*.txt                                    │
└──────────────────────────────┬─────────────────────────────┘
                               │ constants, slots, assets, keys
┌──────────────────────────────▼─────────────────────────────┐
│ Rust 엄랭 VM                                                │
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

| 레이어 | 책임 |
| --- | --- |
| `.umm` 패키지 | 게임 쪽 실행 소스와 import되는 본체 chunk. |
| `package/abi` | VM, Host, 테스트, 엄랭 패키지가 공유하는 안정적인 데이터 계약. |
| Rust VM | 엄랭 파서, import expander, lazy bytecode compiler, jump engine, syscall dispatcher. |
| Host API | 그래픽, 입력, 오디오, 설정, 산술 helper, frame yield를 담당하는 device boundary. |
| macroquad | 실제 데스크톱 backend. |

VM은 한국어/엄랭 소스 표면을 보존합니다. 다만 실행 중에 한글 문자열을 영원히 매번 다시 해석할
필요는 없습니다. 소스는 텍스트로 로드하고, 실제 실행된 줄은 한 번만 내부 instruction으로 컴파일해
캐시합니다. 눈에 보이는 언어는 엄랭이고, hot path는 VM bytecode가 됩니다.

## 📦 패키지 ABI

모든 ABI 파일은 [`package/abi`](package/abi)에 있습니다.

| ABI | 소유 데이터 |
| --- | --- |
| `package/abi/umlang-package.txt` | main script path, asset root, VM frame budget, settings prefix, window options. |
| `package/abi/umlang-syscalls.txt` | Rust와 엄랭 패키지가 공유하는 Host opcode 번호. |
| `package/abi/umlang-keycodes.txt`, `package/abi/umlang-keymap.txt` | 물리 key code와 game action binding. |
| `package/abi/umlang-assets.txt` | texture/audio slot, BGM/SFX bank, asset id policy input. |
| `package/abi/umlang-palette.txt` | color id와 RGBA palette. |
| `package/abi/umlang-settings.txt` | runtime setting key, default, allowed values. |
| `package/abi/umlang-vars.txt` | 엄랭 패키지가 쓰는 VM variable slot ABI. |
| `package/abi/umlang-game.txt` | game constants, physics, phase, court/player/ball defaults. |
| `package/abi/umlang-player.txt` | player state id와 movement/power/lying/win-lose transition threshold. |
| `package/abi/umlang-sprites.txt` | player/ball atlas frame 좌표. |
| `package/abi/umlang-rng.txt` | original-style 64-bit LCG seed/multiplier bytes. |
| `package/abi/umlang-render.txt` | background, score, intro, menu, phase message, playfield render layout. |
| `package/abi/umlang-animation.txt` | player state animation rule과 draw-state sprite map. |
| `package/abi/umlang-sfx.txt` | round/UI SFX event flag, sound id, side policy. |
| `package/abi/umlang-timing.txt` | intro/menu/phase fade frame, message growth, ready blink, game-end timing. |
| `package/abi/umlang-menu.txt` | menu sitting tile, fight message pulse, title curve, selected-option pulse. |

## 🧪 연구 메모

엄카츄는 난해어를 project IR처럼 씁니다.

| 관점 | 의미 |
| --- | --- |
| Runtime sovereignty | 프로젝트가 syntax, ABI, VM semantics, syscall, test를 직접 소유합니다. |
| Dialect compression | 게임 개념을 프로젝트 전용 instruction과 data contract로 압축합니다. |
| Agent specialization | Codex/Claude rule을 dialect, ABI invariant, 커밋된 `.umm` 패키지에 맞춰 튜닝할 수 있습니다. |
| Private dialect security | 조직 전용 언어, private VM, signed package, 엄격한 agent rule을 결합하면 허용된 개발 행동 공간을 좁힐 수 있습니다. |

### LLM과 Private Dialect

GPT 계열 모델이 공개된 `umjunsik-lang` 자료 일부를 봤을 가능성은 있습니다. 하지만 특정 기업의
private dialect, ABI, verifier, package format, interpreter behavior까지 알고 있다고 보면 안 됩니다.
이 지점이 쓸모 있습니다. 내부 agent에는 프로젝트 전용 rule을 주고, 외부인은 interpreter, ABI,
runtime policy 없이는 낯선 source surface만 보게 됩니다.

### 보안적 의의

자기 조직만의 언어 자체가 암호학은 아닙니다. 의미가 생기는 지점은 그 언어가 통제 가능한 software
substrate의 일부가 될 때입니다.

```text
organization-specific language
  + private interpreter / verifier
  + signed package ABI
  + sandboxed Host API
  + audit logs
  + dialect에 맞춘 Codex/Claude rules
  = 더 좁고 강제 가능한 개발 표면
```

이 구조는 policy enforcement, review discipline, reproducibility, accidental data-flow control을 강화할 수
있습니다. 그래도 repo 권한, secret 관리, signing, encryption, review, sandboxing, monitoring 같은 기본
보안 장치와 같이 써야 합니다.

## 🎮 조작

| 키 | 동작 |
| --- | --- |
| 방향키 / ABI에 매핑된 이동키 | 플레이어 이동. |
| Power key | phase에 따라 jump, power hit, dive, menu confirm. |
| `Space` | 일시정지/재개. |
| `Backspace` | 인트로 재시작. |
| `P` | 연습모드 토글. |
| `1`, `2`, `3` | 승점 5/10/15. |
| `[`, `]`, `\` | 목표 FPS 20/30/25. |
| `B` | BGM toggle. |
| `S` | SFX Stereo/Mono/Off. |
| `X` | soft/sharp texture filter. |

## 🛠 개발

Rust-only 검증 경로:

```bash
cargo fmt --check
cargo check
cargo test generated_menu_abi_defines_original_menu_animation_curves
cargo test generated_pikachu_script_reaches_first_frame_yield
```

전체 `cargo test`도 가능합니다. 큰 엄랭 패키지를 실행하는 테스트는 시간이 더 걸립니다.

## 🧾 출처

자산 출처와 재배포 메모는 [`docs/attribution.md`](docs/attribution.md)에 분리했습니다.
