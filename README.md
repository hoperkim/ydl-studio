# YDL Studio

**유튜브, 틱톡, 인스타그램 등 주소 및 링크를 복사해 붙여넣어 영상을 다운로드하는 yt-dlp용 Windows GUI입니다.**  
A Windows GUI for yt-dlp that lets you download videos by copying and pasting URLs or links from YouTube, TikTok, Instagram, and more.

---

## 📦 v0.2.0 업데이트
**배포일:** 2025-08-13  

### ✨ 변경 사항
- **이중 언어 표기 (한글 / 영어)**  
  모든 버튼, 라벨, 메뉴에 **한글(영문)** 동시 표기
- **GUI 크기 확대**  
  기본 창 크기를 키워 재생목록·채널 URL 입력과 표시가 편해짐
- **FFmpeg/FFprobe 자동 다운로드**  
  실행 시 파일이 없으면 다운로드 여부를 묻고, `Yes` 선택 시 gyan.dev에서 essentials 패키지를 받아 exe와 동일 폴더에 배치
- **플레이리스트 / 채널 다운로드 지원**  
  URL 입력 시 yt-dlp 기본 기능을 이용해 전체 다운로드 가능
- **우클릭 붙여넣기 메뉴 추가**
- **프리셋 이름 양언어 지원**  
  예: “비디오 전용 (Video only)”

---

## 🛠 사용 방법
1. **압축 해제** 후 `YDL Studio.exe` 실행  
   (Python 미설치 PC에서도 바로 사용 가능)
2. 필요 시 FFmpeg 다운로드 확인창이 뜨면 **Yes** 선택
3. 동영상 / 재생목록 / 채널 URL을 붙여넣기
4. **시작(Start)** 버튼 클릭

---

## 📂 포함 파일
- `YDL Studio.exe` — 메인 실행 파일
- `user_guide.txt` — 사용 설명서
- `README.md` — 프로젝트 개요

---

## ⚠️ 주의 사항
- Windows SmartScreen이 "알 수 없는 앱" 경고를 표시할 수 있음 → **추가 정보 > 실행** 선택
- 인터넷 연결 필요 (FFmpeg 다운로드, 동영상 URL 처리 시)
- yt-dlp를 기반으로 제작되었으며, 각 사이트의 서비스 약관을 준수해야 함

---

## 📦 What's New in v0.2.0
**Release Date:** 2025-08-13  

### ✨ Updates
- **Bilingual Interface (Korean / English)**  
  All buttons, labels, and menus now display in both Korean and English.
- **Larger GUI Window**  
  Default size increased for easier viewing and editing of playlist or channel URLs.
- **FFmpeg/FFprobe Auto Download**  
  If missing, prompts the user to download from gyan.dev and automatically places the executables in the same folder as the program.
- **Playlist & Channel Download Support**  
  Paste a playlist or channel URL to download all videos sequentially.
- **Right-Click Paste Menu**
- **Preset Name Support in Both Languages**  
  Example: “비디오 전용 (Video only)”

---

## 🛠 How to Use
1. **Extract the zip** and run `YDL Studio.exe`  
   (Works without Python installed)
2. If prompted to download FFmpeg, click **Yes**.
3. Paste your video/playlist/channel URL into the input box.
4. Click **Start (시작)** to begin downloading.

---

## 📂 Included Files
- `YDL Studio.exe` — Main executable
- `user_guide.txt` — User guide
- `README.md` — Project overview

---

## ⚠️ Notes
- Windows SmartScreen may show an "Unknown app" warning. Select **More info > Run anyway**.
- Internet connection required for FFmpeg download and video processing.
- Built with [yt-dlp](https://github.com/yt-dlp/yt-dlp) and requires compliance with each site's terms of service.

