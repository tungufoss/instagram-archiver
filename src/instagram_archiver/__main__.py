"""Allow `python -m instagram_archiver`."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
