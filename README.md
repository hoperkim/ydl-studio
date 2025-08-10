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
- Windows 릴리스 패키지(essentials.zip)를 내려받고, `bin` 폴더의 `ffmpeg.exe`와 `ffprobe.exe`만 실행파일 폴더에 함께 두세요.
- 다운로드: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip

## How to Use
프로그램 실행 → URL 붙여넣기(우클릭 Paste 또는 Ctrl+V)

프리셋 선택(영상/오디오/자막)

Start 클릭

진행 상황은 하단 Log에서 확인

## 참고/감사
- 본 프로젝트는 [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Unlicense)을 기반으로 작동합니다.
- UI는 Python(Tkinter)로 구현되었습니다.
- 고화질 병합/오디오 추출을 위해 FFmpeg가 필요하며, 바이너리는 포함하지 않습니다.

⚠️ **Legal Notice / 법적 안내**

이 프로그램은 yt-dlp와 FFmpeg를 기반으로 제작된 GUI입니다.
유튜브 및 기타 플랫폼의 콘텐츠를 다운로드할 경우, 해당 서비스의 이용약관과
현지 저작권법을 준수해야 합니다.
저작권자의 허락 없이 콘텐츠를 다운로드·배포하는 것은 법적으로 금지될 수 있습니다.
본 소프트웨어의 제작자는 사용자의 불법 행위에 대해 어떠한 책임도 지지 않습니다.
