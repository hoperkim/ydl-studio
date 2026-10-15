# ⚡ YDL Studio (v1.2.0 Universal • 2026-10-15 업데이트)

[![Release](https://img.shields.io/github/v/release/hoperkim/ydl-studio?color=green)](https://github.com/hoperkim/ydl-studio/releases/latest)
[![Download](https://img.shields.io/badge/Download-YDL--Studio--v1.0.exe-brightgreen?logo=windows&logoColor=white)](https://github.com/hoperkim/ydl-studio/releases/download/v1.0.0/YDL-Studio-v1.0.exe)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![yt-dlp](https://img.shields.io/badge/Engine-yt--dlp-FF0000?logo=youtube&logoColor=white)](https://github.com/yt-dlp/yt-dlp)
[![UI](https://img.shields.io/badge/GUI-CustomTkinter-blue)](https://github.com/TomSchimansky/CustomTkinter)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**YDL Studio**는 유튜브, TikTok, X, Instagram뿐 아니라 **보안 세션 잠금 사이트(upload18.org 등), 웹사이트 내 임베드 영상, HLS(.m3u8), DASH(.mpd), 그리고 크롬캐스트로 전송/재생되는 모든 브라우저 미디어 스트림까지 완벽하게 추출하고 다운로드**할 수 있는 만능 Windows 데스크톱 애플리케이션입니다.

---

## 📅 2026-10-15 최신 업데이트 (v1.2.0)
- 🛡️ **보안 브라우저 세션 다운로더 (`BrowserStreamDownloader`) 탑재**:
  - `upload18.org` 등 Cloudflare, 동적 IP 바인딩, 무확장자 HLS 세그먼트, `Range: bytes=0-` 검증 사이트 완벽 지원
  - 브라우저 CDP 내부 병렬 `fetch()` 파이프라인으로 13+ MB/s 초고속 무손실 수집 및 FFmpeg 자동 병합
- 🐞 **안정성 패치**: Tkinter 비동기 예외 콜백 스코프 버그(`NameError: 'e'`) 및 `OSError: [Errno 22]` 완전 차단 패치
- ⌨️ **독립 CLI 스크립트 추가**: 터미널에서 즉시 실행 가능한 `download_upload18.py` 제공

---

## ✨ 핵심 기능 (Key Features)

### 1. 🌐 실시간 브라우저 & 크롬캐스트 스트림 감지기 (CDP Sniffer)
- **크롬 / 엣지 DevTools Protocol(CDP) 실시간 연동**:
  - 버튼 하나로 전용 스니퍼 브라우저를 열고 원하는 사이트(OTT, 뉴스, 스트리밍, 커뮤니티 등)에서 영상을 재생하거나 **크롬캐스트로 전송(Cast)**하면 원본 스트림이 실시간으로 감지됩니다.
- **인증 헤더 자동 주입**:
  - Referer, Origin, User-Agent, Cookie 등 봇 차단 및 403 Forbidden 방지 헤더를 다운로드 엔진에 자동 전달하여 100% 성공률을 보장합니다.

### 2. 🔍 딥 웹페이지 스캐너 (Deep Webpage Scanner)
- 일반 웹사이트 URL을 입력창에 넣기만 해도 `curl_cffi` 기반 Chrome TLS 에뮬레이션을 통해 Cloudflare 방어를 우회하고, 페이지 내부의 iframe, 자바스크립트 플레이어(Hls.js, Video.js, JW Player 등)에서 숨겨진 `.m3u8` / `.mpd` / `.mp4` 주소를 자동 발굴합니다.

### 3. 🔴 실시간 라이브 스트림 녹화 (Live Stream Recorder)
- 유튜브 라이브, 트위치, 치지직, SOOP(아프리카), 맞춤 HLS 라이브 등 실시간 방송 스트림을 감지하여 실시간 녹화 모드를 지원합니다.
- [⏹️ 녹화 종료] 버튼 클릭 시 녹화된 구간을 FFmpeg로 손실 없이 안전하게 MP4 파일로 마무리 저장합니다.

### 4. 🎛️ 다양한 화질 & 프리셋 & FFmpeg Fallback
- **동영상**: 4K (2160p), 2K (1440p), 1080p FHD, 720p HD, 480p 등 (M3U8 마스터 플레이리스트 해상도 자동 분석)
- **오디오**: MP3 (320kbps 최고음질, 192kbps), M4A (무손실 AAC)
- **FFmpeg 직접 스트림 Fallback**: yt-dlp로 처리하기 어려운 특수 스트림도 내장 FFmpeg 파이프라인으로 무결점 병합 다운로드

### 5. 🎨 세련된 CustomTkinter 다크 테마 대시보드
- 개별 카드형 큐 시스템 (진행률 %, 속도 MB/s, 남은 시간 ETA, 실시간 취소, 원클릭 [📂 폴더 열기])
- 클립보드 링크 스마트 자동 감지 및 인앱 yt-dlp 원클릭 업데이트

---

## 🚀 빠른 시작 (Getting Started)

### 1. 소스코드에서 실행

```bash
# 1. 리포지토리 이동
cd ydl-studio

# 2. 가상환경 활성화 (또는 새로 생성)
.\.venv\Scripts\activate

# 3. 필수 패키지 설치
pip install -r requirements.txt

# 4. 앱 실행
python main.py
# 또는 간편 실행
run.bat
```

### 2. 단일 실행 파일(.exe) 빌드

```bash
pyinstaller "YDL Studio.spec"
```
빌드 완료 시 `dist/YDL Studio.exe` 파일 하나로 배포 및 실행 가능합니다.

---

## 🛠️ 사용 시나리오

1. **유튜브 / 인스타 / 틱톡 등 일반 영상**:
   - 주소 복사 후 상단 입력창에 붙여넣고 **[⚡ 영상 추가]** 클릭
2. **다운로드가 안 되는 일반 웹사이트 / 크롬캐스트 전송 영상**:
   - 상단의 **[🌐 브라우저 감지기 (만능 스니퍼)]** 클릭
   - 팝업에서 **[🚀 브라우저 열기]** 클릭 후 해당 웹사이트에서 영상 재생 (또는 크롬캐스트 전송)
   - 실시간 감지 목록에 뜬 항목의 **[📥 대기열 추가]** 클릭 후 다운로드!
3. **실시간 라이브 방송**:
   - 카드가 라이브 방송(`🔴 LIVE`)으로 표시되며 **[🔴 녹화 시작]**을 누르고, 원하는 시점에 **[⏹️ 녹화 종료]**를 누르면 끝!

---

## 📄 라이선스 (License)

이 프로젝트는 [MIT License](LICENSE)에 따라 배포됩니다.  
미디어 다운로드 시 각 플랫폼 및 원작자의 저작권과 서비스 이용약관을 준수해야 합니다.
