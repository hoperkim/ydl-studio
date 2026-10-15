"""
Standalone CLI Downloader for upload18.org and session-locked streaming sites.
Usage:
    python download_upload18.py "<URL>" [--out <dir>]
"""
import argparse
import asyncio
import os
import sys

# Ensure root dir is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.core.browser_fetcher import BrowserStreamDownloader


def main():
    parser = argparse.ArgumentParser(description="upload18.org 및 보안 스트림 영상 다운로더")
    parser.add_argument("url", help="다운로드할 영상 웹페이지 URL (예: https://upload18.org/play/index/...)")
    parser.add_argument("--out", default=os.path.join(os.path.expanduser("~"), "Downloads"), help="저장할 디렉토리 경로 (기본: 다운로드 폴더)")
    parser.add_argument("--max", type=int, default=None, help="최대 다운로드 세그먼트 수 (테스트용, 기본값: 전체)")
    args = parser.parse_args()

    url = args.url.strip()
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 60)
    print("🎬 YDL Studio - 보안 스트림 다운로더")
    print(f"🔗 대상 URL: {url}")
    print(f"📁 저장 위치: {out_dir}")
    print("=" * 60)

    last_status = ""

    def on_status(status_code, msg):
        nonlocal last_status
        if msg != last_status:
            print(f"\n[{status_code}] {msg}")
            last_status = msg

    def on_progress(percent, speed, eta):
        sys.stdout.write(f"\r진행률: [{percent:5.1f}%] | 속도: {speed:>9} | {eta:>12}")
        sys.stdout.flush()

    dl = BrowserStreamDownloader(
        page_url=url,
        output_dir=out_dir,
        on_progress=on_progress,
        on_status=on_status
    )

    try:
        final_path = asyncio.run(dl.run_async(max_segments=args.max))
        print("\n" + "=" * 60)
        print(f"🎉 다운로드 및 무손실 MP4 변환 성공!")
        print(f"💾 파일 경로: {final_path}")
        print(f"📊 파일 크기: {os.path.getsize(final_path) / 1024 / 1024:.2f} MB")
        print("=" * 60)
    except KeyboardInterrupt:
        print("\n\n⏹️ 사용자에 의해 다운로드가 중단되었습니다.")
        dl.cancel()
    except Exception as e:
        print(f"\n\n❌ 다운로드 오류 발생: {e}")


if __name__ == "__main__":
    main()
