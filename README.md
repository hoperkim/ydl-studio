# ydl-studio
유튜브 주소를 복사 붙여넣기 하여 영상을 다운로드 하는 yt-dlp프로그램을 윈도우UI 실행 버전으로 제작해 보았습니다.
디렉토리에 ffmpeg.exe와 ffprobe.exe를 함께 넣고 실행화일을 누르면 UI가 나타납니다.
자세한 사항은 사용법에 적어 두었습니다.

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
