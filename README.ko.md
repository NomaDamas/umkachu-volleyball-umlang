<p align="center">
  <img src="docs/images/umkachu-volleyball-banner-ko.png" alt="엄카츄 배구 배너" width="100%">
</p>

# 엄카츄 배구 엄랭 포트

[English README](README.md)

**피카츄배구를 엄랭으로 끌고 가는 프로젝트입니다. 길어져도 됩니다. 돌아가면 됩니다.**

이 레포는 `umkachu-volleyball-umlang` 기준의 전체 포팅 실험입니다. Rust는 게임 언어가 아니라 범용 엄랭 VM, Host API, OS/GPU/오디오
브리지입니다. 피카츄배구 전용 로직과 데이터는 생성된 엄랭 코드와 `umlang-*.txt` ABI 파일로
계속 밀어내는 구조입니다.

## TLDR

```text
umlang-package.txt
  -> scripts/pikachu.umm                 # 289,866줄짜리 생성 엄랭 지옥
  -> umlang-*.txt                        # 엄랭 패키지 ABI
  -> Rust 엄랭 VM                         # 피카츄 전용이 아닌 범용 실행기
  -> Host API(syscall)                   # 그래픽/입력/오디오/설정 브리지
  -> macroquad 창/GPU/키보드/오디오
```

목표는 Rust를 무조건 없애는 게 아닙니다.

```text
Rust는 범용 실행기로 남긴다.
피카츄배구 전용 상태/데이터/타이밍/렌더/입력/로직은 엄랭과 ABI로 계속 옮긴다.
```

## Quick Start

먼저 엄랭 게임 파일을 생성합니다. 생성 파일은 수백 MB이고 GitHub 100MB 제한을 넘기므로 커밋하지 않습니다.

```bash
python3 tools/gen_pikachu_umm.py
```

생성된 엄랭 게임 실행:

```bash
cargo run
```

다른 엄랭 파일 실행:

```bash
cargo run -- path/to/program.umm
```

셸 명령은 평범하지만, payload는 이런 느낌입니다.

```umm
어떻게
엄..........
어엄,,,,,
식어!
준..........
이 사람이름이냐ㅋㅋ
```

실제 로컬 게임 파일은 `scripts/pikachu.umm`입니다. 사람이 직접 쓰는 파일이 아니라 생성 파일입니다.
현재 289,866줄이라 손으로 쓰면 사람 이름이 아닙니다.

## 현재 포팅 구조

| 레이어 | 책임 |
| --- | --- |
| `scripts/pikachu.umm` | 현재 게임 루프와 게임 동작을 담은 로컬 생성 엄랭 프로그램. GitHub에 올리기엔 너무 커서 커밋하지 않습니다. |
| `umlang-*.txt` | 상수, 렌더 배치, 타이밍, 메뉴 커브, SFX 정책, 변수, 키, 자산, RNG, 스프라이트, 애니메이션, 설정 ABI. |
| Rust VM | 엄랭 문법 실행: 변수, 식, 점프, 조건, 출력, 종료, 음수 출력 syscall. |
| Host API | 엄랭이 그래픽, 입력, 오디오, 설정, frame pacing, 산술 helper를 호출하는 경계. |
| macroquad | 창, GPU 렌더링, 키보드, 오디오를 담당하는 교체 가능한 host backend. |

## 패키지 ABI

피카츄배구 전용 값은 Rust/Python 하드코딩에서 계속 빠져나와 text ABI로 이동 중입니다.

| ABI | 소유 데이터 |
| --- | --- |
| `umlang-package.txt` | main script, asset root, VM frame budget, 설정 prefix, 창 옵션. |
| `umlang-syscalls.txt` | Rust와 엄랭 생성기가 공유하는 Host opcode 번호. |
| `umlang-keycodes.txt`, `umlang-keymap.txt` | physical key code와 게임 action 매핑. |
| `umlang-assets.txt` | texture/audio slot, BGM/SFX bank, asset id 정책 입력. |
| `umlang-palette.txt` | color id와 RGBA 팔레트. |
| `umlang-settings.txt` | 런타임 설정 key/default/allowed values. |
| `umlang-vars.txt` | 생성 엄랭 VM 변수 slot ABI. |
| `umlang-game.txt` | 게임 상수, 물리, phase, 코트/플레이어/공 기본값. |
| `umlang-player.txt` | 플레이어 상태 id와 이동/파워/누움/승패 상태 전이 임계값. |
| `umlang-sprites.txt` | player/ball atlas frame 좌표. |
| `umlang-rng.txt` | 원본식 64비트 LCG seed/multiplier byte. |
| `umlang-render.txt` | 배경, 점수, 인트로, 메뉴, phase 메시지, 플레이필드 렌더 배치. |
| `umlang-animation.txt` | 플레이어 상태별 animation rule과 draw-state sprite map. |
| `umlang-sfx.txt` | Round/UI SFX event flag, sound id, side policy. |
| `umlang-timing.txt` | intro/menu/phase fade frame, message growth, ready blink, game-end timing. |
| `umlang-menu.txt` | 메뉴 sitting tile, fight message pulse, title curve, selected option pulse. |

## 조작

| 키 | 동작 |
| --- | --- |
| 방향키 / ABI에 매핑된 이동키 | 플레이어 이동. |
| Power key | phase에 따라 jump/power/dive/menu confirm. |
| `Space` | 일시정지/재개. |
| `Backspace` | 인트로 재시작. |
| `P` | 연습모드 토글. |
| `1`, `2`, `3` | 승점 5/10/15. |
| `[`, `]`, `\` | 목표 FPS 20/30/25. |
| `B` | BGM 토글. |
| `S` | SFX Stereo/Mono/Off 순환. |
| `X` | soft/sharp texture filter. |

## 개발

`scripts/pikachu.umm`는 직접 고치지 말고 재생성하세요.

```bash
python3 tools/gen_pikachu_umm.py
cargo fmt --check
cargo check
cargo test generated_menu_abi_defines_original_menu_animation_curves
cargo test generated_pikachu_script_reaches_first_frame_yield
```

전체 `cargo test`도 가능하지만, 거대한 생성 엄랭 파일을 test binary에 포함해서 느릴 수 있습니다.

## 포팅 방향

전체 포팅으로 계속 확장 가능합니다.

현실적인 경계는 이겁니다.

```text
엄랭 소유: 게임 규칙, 상태 머신, 렌더 선언, 입력 매핑, 타이밍, SFX 정책, 데이터.
Rust 소유: 범용 VM 실행, syscall, OS 연동, GPU/audio/window backend.
```

피카츄배구 전용 값이면 최종적으로 생성 엄랭 또는 `umlang-*.txt` ABI에 있어야 합니다.
컴퓨터가 픽셀을 그리고 소리를 내는 방법이면 Host API 뒤에 남습니다.

## 출처

README에는 다른 이름을 노출하지 않고, 자산 출처와 재배포 주의사항은 [docs/attribution.md](docs/attribution.md)에
분리해 두었습니다.
