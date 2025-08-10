# ydl-studio
유튜브 주소를 복사해 붙여넣어 영상을 다운로드하는 yt-dlp용 Windows GUI입니다
# YDL Studio (yt-dlp Windows GUI)

## Quick Start
1) Python 3.10+ 설치
2) `pip install -r requirements.txt`
3) `python main.py`

## Build EXE (Windows)
pyinstaller --noconfirm --onefile --windowed `
    --name "YDL Studio" `
    --add-data "user_guide.txt;." `
    --log-level ERROR `
    main.py

## FFmpeg
- FFmpeg은 exe에 포함하지 않습니다.
- Windows 릴리스 패키지(essentials.zip)를 내려받고, `bin` 폴더의 `ffmpeg.exe`와 `ffprobe.exe`만 실행파일 옆 폴더에 두세요.
- 다운로드: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip

## How to Use
프로그램 실행 → URL 붙여넣기(우클릭 Paste 또는 Ctrl+V)

프리셋 선택(영상/오디오/자막)

Start 클릭

진행 상황은 하단 Log에서 확인
