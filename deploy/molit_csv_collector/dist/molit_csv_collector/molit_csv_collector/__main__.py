"""python -m molit_csv_collector"""

from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        from .cli import main as cli_main

        raise SystemExit(cli_main(sys.argv[2:]))
    from .gui import main as gui_main

    gui_main()


if __name__ == "__main__":
    main()
