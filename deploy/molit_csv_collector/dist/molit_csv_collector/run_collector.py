"""직접 실행용 런처 (py -m 없이 동작)."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        print("tkinter가 없습니다. Python 재설치 시 'tcl/tk' 포함 옵션을 켜세요.")
        input("Enter 키로 종료...")
        return 1

    try:
        from molit_csv_collector.gui import main as gui_main

        gui_main()
        return 0
    except Exception:
        err = traceback.format_exc()
        print(err)
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("실행 오류", err[:2000])
            root.destroy()
        except Exception:
            pass
        input("Enter 키로 종료...")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
