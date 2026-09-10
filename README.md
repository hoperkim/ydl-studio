# ⚡ YDL Studio (v1.0.0 Modern)

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![yt-dlp](https://img.shields.io/badge/Engine-yt--dlp-FF0000?logo=youtube&logoColor=white)](https://github.com/yt-dlp/yt-dlp)
[![UI](https://img.shields.io/badge/GUI-CustomTkinter-blue)](https://github.com/TomSchimansky/CustomTkinter)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**YDL Studio**는 유튜브를 비롯한 다양한 미디어 플랫폼(TikTok, X, Instagram, Bilibili 등)의 고화질 영상과 오디오를 가장 쉽고 편리하게 다운로드할 수 있도록 설계된 현대적인 Windows 데스크톱 애플리케이션입니다.

기존의 투박한 Tkinter 인터페이스를 완전히 탈피하여, **CustomTkinter 기반의 세련된 다크 테마 대시보드**와 **카드형 작업 큐(Queue) 시스템**을 탑재하였습니다.

---

## ✨ 핵심 기능 (Key Features)

- 🎨 **모던 다크 UI (Modern Dark Theme)**: 세련되고 눈이 편안한 카드형 대시보드 디자인
- 🔍 **실시간 메타데이터 미리보기**: URL 입력 시 다운로드 전 **썸네일, 제목, 채널명, 재생 시간, 사용 가능한 해상도**를 즉시 추출
- 🎛️ **다양한 화질 & 오디오 프리셋**:
  - 동영상: 4K (2160p), 2K (1440p), 1080p FHD, 720p HD, 480p 등
  - 오디오 추출: MP3 (320kbps 최고음질, 192kbps 표준), M4A (무손실 AAC)
- 📋 **클립보드 스마트 자동 감지**: 브라우저에서 유튜브 링크를 복사하면 프로그램이 자동으로 인식하여 입력창에 반영
- 🍪 **브라우저 쿠키 원클릭 연동**: Chrome, Edge, Brave, Firefox 등의 로그인 세션을 연동하여 **유튜브 봇 감지(Sign-in Required) 및 연령 제한 완벽 우회**
- 📊 **카드형 개별 큐 시스템**:
  - 영상마다 개별 다운로드 진행률(%), 속도(MB/s), 남은 시간(ETA) 표시
  - 다운로드 도중 언제든지 개별 **[취소]** 가능
  - 다운로드 완료 시 **[📂 폴더 열기]** 원클릭 지원
- ⚡ **인앱 원클릭 엔진 업데이트**: 유튜브 정책 변경 시 앱 설정 창에서 `yt-dlp` 최신 버전을 바로 업데이트 가능

---

## 🚀 빠른 시작 (Getting Started)

### 1. 소스코드에서 실행

```bash
# 1. 리포지토리 클론
git clone https://github.com/hoperkim/ydl-studio.git
cd ydl-studio

# 2. 가상환경 생성 및 활성화
python -m venv .venv
.\.venv\Scripts\activate

# 3. 필수 패키지 설치
pip install -r requirements.txt

# 4. 실행
python main.py
```

### 2. 단일 실행 파일(.exe) 빌드

```bash
pip install pyinstaller
pyinstaller "YDL Studio.spec"
```
빌드가 완료되면 `dist/YDL Studio.exe` 파일 하나로 모든 PC에서 바로 실행할 수 있습니다.

---

## 🛠️ 사용 방법 (How to Use)

1. **URL 추가**: 유튜브 링크를 복사하여 상단 입력창에 넣고 **[⚡ 영상 추가]** 버튼을 누릅니다. (클립보드 자동 감지가 켜져 있으면 복사 시 자동 감지)
2. **옵션 선택**: 추가된 카드에서 원하는 화질(4K, 1080p, MP3 등)을 선택합니다.
3. **다운로드**: **[⬇️ 다운로드]** 버튼을 누르면 실시간 진행률과 다운로드 속도가 표시됩니다.
4. **완료**: 다운로드가 완료되면 **[📂 폴더 열기]** 버튼을 눌러 저장된 파일을 확인합니다.
5. **설정**: 우측 상단 **[⚙️ 환경 설정]**에서 기본 저장 폴더 변경, 브라우저 쿠키 연동, yt-dlp 엔진 업데이트를 수행할 수 있습니다.

---

## 📄 라이선스 (License)

이 프로젝트는 [MIT License](LICENSE)에 따라 배포됩니다.  
미디어 다운로드 시 각 플랫폼 및 원작자의 저작권과 서비스 이용약관을 준수해야 합니다.
