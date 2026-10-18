# ⚡ YDL Studio (v2.0.0 Smart Zero-Click • 2026-10-19 업데이트)

[![Release](https://img.shields.io/github/v/release/hoperkim/ydl-studio?color=green)](https://github.com/hoperkim/ydl-studio/releases/latest)
[![Download](https://img.shields.io/badge/Download-YDL--Studio--v2.0.0.exe-brightgreen?logo=windows&logoColor=white)](https://github.com/hoperkim/ydl-studio/releases/download/v2.0.0/YDL-Studio-v2.0.0.exe)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![yt-dlp](https://img.shields.io/badge/Engine-yt--dlp-FF0000?logo=youtube&logoColor=white)](https://github.com/yt-dlp/yt-dlp)
[![UI](https://img.shields.io/badge/GUI-CustomTkinter-blue)](https://github.com/TomSchimansky/CustomTkinter)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**YDL Studio v2.0.0**은 **주소만 복사·붙여넣기(`Ctrl+V` 또는 원클릭 복붙)하면 프로그램이 알아서 영상(MP4)인지 음원(MP3/FLAC)인지 의도를 자동 판별하여 클릭 한 번 없이 즉시 다운로드**해 주는 차세대 만능 미디어 & 음원 다운로더입니다.

---

## 🚀 v2.0.0 핵심 업그레이드 (2026-10-19)

1. **⚡ 무클릭 원스톱 자동 다운로드 (Zero-Click Auto-Start)**:
   - 기존처럼 분석 팝업을 기다린 뒤 카드마다 `[다운로드]` 버튼을 또 누를 필요가 없습니다.
   - 주소 입력 또는 **`[📋 원클릭 복붙]` (단축키 `Ctrl+V`)**만 누르면, 화면 멈춤 없는 **인라인 비동기 분석 후 즉시 다운로드가 자동 시작**됩니다.
   - 여러 개의 링크를 한꺼번에 복사해서 붙여넣어도 자동으로 분리하여 동시 큐에 등록합니다.
2. **🤖 스마트 영상·음원 의도 자동 판별 & 음원 브릿지 (Smart Media Intent)**:
   - **음원/뮤직 링크 자동 인식**: YouTube Music, SoundCloud, Bandcamp, Mixcloud 및 **멜론(Melon), 스포티파이(Spotify), 지니, 벅스, Apple Music** 트랙 링크나 `.mp3`/`.flac` 주소를 붙여넣으면 자동으로 **고음질 음원 추출(`MP3 320kbps` + 앨범 커버 아트 & ID3 태그 내장)** 모드로 전환되어 다운로드됩니다!
   - **상단 원클릭 모드 스위치**:
     - `🤖 스마트 자동 (영상·음원 자동)` *(기본값)*
     - `🎬 최고화질 영상 (MP4 고정)`
     - `🎵 최고음질 음원 (MP3 320k)`
     - `🎼 무손실 음원 (FLAC)`
     - `📺 1080p FHD 영상 (MP4)`
   - **유튜브 믹스(Mix/Radio) 자동 정제**: `watch?v=...&list=RD...` 형태의 링크를 붙여넣을 때 원치 않는 50곡 재생목록 전체가 걸리는 현상을 자동으로 차단하여 **의도한 해당 영상/곡만 1초 만에 즉시 추출**합니다.
3. **🛡️ 4단계 만능 스트림 돌파 엔진 (Zero Dead-Ends Pipeline)**:
   - **1단계 (`yt-dlp` 8배속 터보 엔진)**: 8개 세그먼트 동시 병렬 다운로드(`concurrent_fragment_downloads=8`) 및 브라우저 쿠키 충돌 자동 복구.
   - **2단계 (`DeepWebScanner` 난독화 해독기)**: 웹페이지 HTML, `<iframe>`, Base64(`atob`), 그리고 스트리밍 사이트들이 주로 쓰는 **`eval(function(p,a,c,k,e,d))` 패킹 자바스크립트**를 자체 해독하여 숨겨진 `.m3u8` / `.mpd` / `.mp4` / `.mp3` 원본 주소를 추출합니다.
   - **3단계 (`FFmpeg` 다이렉트 스트림 리먹서)**: 특수 HLS/DASH 스트림을 무손실 MP4 또는 고음질 MP3/FLAC으로 직접 변환합니다.
   - **4단계 (`Universal Browser Session` 자동 우회)**: `upload18.org` 등 Cloudflare, 동적 토큰, 세션 잠금이 걸린 모든 웹사이트에서 1~3단계가 막히면 **사용자가 수동으로 스니퍼를 켤 필요 없이 자동으로 백그라운드 브라우저 보안 세션을 가동**하여 마스터 M3U8, 상대 경로 세그먼트, AES-128 암호화 스트림까지 100% 자동 수집·병합합니다!
4. **▶️ 완료 즉시 `[▶️ 바로 재생]` 및 일괄 큐 제어**:
   - 다운로드가 완료된 카드는 `[▶️ 바로 재생]`과 `[📂 폴더 열기]` 버튼을 제공하며, 하단 상태바에서 `[⬇️ 대기항목 전체 시작]`, `[🧹 완료 정리]`, `[📁 저장 폴더 열기]`를 원클릭으로 제어할 수 있습니다.

---

## 💻 빠른 시작 (Getting Started)

### 1. 단일 실행 파일(`.exe`) 다운로드 및 실행
파이썬 설치 없이 [Releases 페이지](https://github.com/hoperkim/ydl-studio/releases/latest)에서 **`YDL-Studio-v2.0.0.exe`**를 다운로드하여 바로 실행하세요.

### 2. 소스 코드에서 실행 및 빌드

```bash
# 가상환경 활성화 및 실행
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py

# 단일 .exe 빌드
pyinstaller "YDL Studio.spec" --noconfirm
```

---

## 📄 라이선스 (License)

이 프로젝트는 [MIT License](LICENSE)에 따라 배포됩니다.  
미디어 다운로드 시 각 플랫폼 및 원작자의 저작권과 서비스 이용약관을 준수해야 합니다.
