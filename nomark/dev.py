import argparse
from pathlib import Path

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Run NoMark on the local network.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(
        "nomark.app:app",
        host=args.host,
        port=args.port,
        reload=True,
        reload_dirs=[str(Path(__file__).resolve().parent)],
        access_log=False,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
