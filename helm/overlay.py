# OWNER: P2
"""Independent Windows overlay viewer. Start Helm first; closing this never stops it."""
import argparse
import sys
import webbrowser
from urllib.parse import urlencode


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Helm camera and controller overlay (start Helm first)")
    parser.add_argument("--port", type=int, default=8000, help="running Helm server port")
    parser.add_argument("--width", type=int, default=400, help="window width in logical pixels")
    parser.add_argument("--height", type=int, default=780, help="window height in logical pixels")
    parser.add_argument("--browser", action="store_true", help="open in the default browser on any OS")
    parser.add_argument("--mock", action="store_true", help="show the UI's simulated inputs")
    parser.add_argument("--no-top", action="store_true", help="use an ordinary window instead of always on top")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.width < 320 or args.height < 540:
        parser.error("minimum window size is --width 320 --height 540")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    query = {"overlay": "1"}
    if args.mock:
        query["mock"] = "1"
    url = f"http://127.0.0.1:{args.port}/?{urlencode(query)}"
    if args.browser:
        return 0 if webbrowser.open(url) else 1
    if sys.platform != "win32":
        print("The native overlay requires Windows. Use --browser on this OS.", file=sys.stderr)
        return 1
    try:
        import webview
    except ImportError:
        print('Install the overlay dependency: python -m pip install pywebview', file=sys.stderr)
        return 1
    try:
        webview.create_window(
            "Helm · Live inputs", url, width=args.width, height=args.height,
            min_size=(320, 540), resizable=True, on_top=not args.no_top,
            background_color="#f6f4ef",
        )
        # GUI owns this separate process's main thread; no camera, pad or Python bridge here.
        webview.start(gui="edgechromium")
    except Exception as exc:
        print(f"Cannot open overlay: {exc}\nInstall Microsoft Edge WebView2 Runtime, or use --browser.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
