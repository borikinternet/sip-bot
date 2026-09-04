"""Command-line entrypoint for the runtime preflight."""

from .runtime import main


if __name__ == "__main__":
    raise SystemExit(main())
