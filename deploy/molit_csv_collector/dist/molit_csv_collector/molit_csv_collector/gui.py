"""tkinter GUI — 연도·유형·시도 선택 후 CSV 수집."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .config import (
    DEFAULT_MAX_NEW_DOWNLOADS,
    DEFAULT_SIDO_LIST,
    PROPERTY_TYPE_CHOICES,
    get_property_type,
)
from .downloader import DownloadJob, run_download


class CollectorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("국토부 실거래 CSV 수집기")
        self.geometry("820x720")
        self.minsize(720, 600)

        self._worker: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._log_queue: queue.Queue[tuple[str, str] | None] = queue.Queue()
        self._region_vars: dict[str, tk.BooleanVar] = {}

        self._build_form()
        self.after(200, self._poll_log)

    def _build_form(self) -> None:
        pad = {"padx": 10, "pady": 4}
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        row = 0
        ttk.Label(frm, text="부동산 유형").grid(row=row, column=0, sticky=tk.W, **pad)
        self._type_labels = [label for _, label in PROPERTY_TYPE_CHOICES]
        self._type_keys = [key for key, _ in PROPERTY_TYPE_CHOICES]
        self.type_var = tk.StringVar(value=self._type_labels[0])
        type_combo = ttk.Combobox(
            frm,
            textvariable=self.type_var,
            values=self._type_labels,
            state="readonly",
            width=28,
        )
        type_combo.grid(row=row, column=1, sticky=tk.W, **pad)
        type_combo.bind("<<ComboboxSelected>>", self._on_type_change)
        self.type_hint_var = tk.StringVar()
        ttk.Label(frm, textvariable=self.type_hint_var, foreground="#555").grid(
            row=row, column=2, sticky=tk.W, **pad
        )
        self._on_type_change()

        row += 1
        ttk.Label(frm, text="시작 연도").grid(row=row, column=0, sticky=tk.W, **pad)
        self.start_year_var = tk.IntVar(value=2010)
        ttk.Spinbox(frm, from_=2006, to=2030, textvariable=self.start_year_var, width=10).grid(
            row=row, column=1, sticky=tk.W, **pad
        )

        row += 1
        ttk.Label(frm, text="종료 연도").grid(row=row, column=0, sticky=tk.W, **pad)
        self.end_year_var = tk.IntVar(value=2020)
        ttk.Spinbox(frm, from_=2006, to=2030, textvariable=self.end_year_var, width=10).grid(
            row=row, column=1, sticky=tk.W, **pad
        )

        row += 1
        ttk.Label(frm, text="신규 다운로드 상한").grid(row=row, column=0, sticky=tk.W, **pad)
        self.max_var = tk.IntVar(value=DEFAULT_MAX_NEW_DOWNLOADS)
        ttk.Spinbox(frm, from_=1, to=100, textvariable=self.max_var, width=10).grid(
            row=row, column=1, sticky=tk.W, **pad
        )
        ttk.Label(frm, text="(일일 약 100건 · 검증 실패는 failed/ 보관)", foreground="#555").grid(
            row=row, column=2, sticky=tk.W, **pad
        )

        row += 1
        ttk.Label(frm, text="저장 폴더").grid(row=row, column=0, sticky=tk.W, **pad)
        self.output_var = tk.StringVar(value=str(Path.home() / "MolitCSV"))
        ttk.Entry(frm, textvariable=self.output_var, width=52).grid(
            row=row, column=1, columnspan=2, sticky=tk.EW, **pad
        )

        row += 1
        ttk.Button(frm, text="찾아보기", command=self._pick_output).grid(
            row=row, column=1, sticky=tk.W, **pad
        )

        row += 1
        self.headless_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frm,
            text="Headless (Chrome 창 숨김 — 문제 시 해제)",
            variable=self.headless_var,
        ).grid(row=row, column=0, columnspan=3, sticky=tk.W, **pad)

        row += 1
        region_hdr = ttk.Frame(frm)
        region_hdr.grid(row=row, column=0, columnspan=3, sticky=tk.EW, **pad)
        ttk.Label(region_hdr, text="수집 시도 (기본: 전국)").pack(side=tk.LEFT)
        ttk.Button(region_hdr, text="전체 선택", command=self._select_all_regions).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(region_hdr, text="전체 해제", command=self._clear_all_regions).pack(side=tk.LEFT)
        ttk.Label(
            region_hdr,
            text="실패 시 해당 시도만 선택 후 재실행",
            foreground="#555",
        ).pack(side=tk.LEFT, padx=8)

        row += 1
        region_box = ttk.Frame(frm)
        region_box.grid(row=row, column=0, columnspan=3, sticky=tk.EW, **pad)
        cols = 3
        for i, region in enumerate(DEFAULT_SIDO_LIST):
            var = tk.BooleanVar(value=True)
            self._region_vars[region] = var
            ttk.Checkbutton(
                region_box,
                text=region,
                variable=var,
                width=16,
            ).grid(row=i // cols, column=i % cols, sticky=tk.W, padx=2, pady=1)

        row += 1
        btn_row = ttk.Frame(frm)
        btn_row.grid(row=row, column=0, columnspan=3, sticky=tk.W, **pad)
        self.start_btn = ttk.Button(btn_row, text="수집 시작", command=self._start)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.stop_btn = ttk.Button(btn_row, text="중지", command=self._stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)

        row += 1
        ttk.Label(frm, text="로그").grid(row=row, column=0, sticky=tk.NW, **pad)
        self.log_box = scrolledtext.ScrolledText(frm, height=16, wrap=tk.WORD)
        self.log_box.grid(row=row, column=1, columnspan=2, sticky=tk.NSEW, **pad)
        self.log_box.tag_configure("fail", foreground="#c0392b")
        self.log_box.tag_configure("info", foreground="#222222")
        frm.rowconfigure(row, weight=1)
        frm.columnconfigure(2, weight=1)

    def _selected_type_key(self) -> str:
        label = self.type_var.get()
        try:
            idx = self._type_labels.index(label)
        except ValueError:
            idx = 0
        return self._type_keys[idx]

    def _on_type_change(self, *_args) -> None:
        pt = get_property_type(self._selected_type_key())
        self.type_hint_var.set(f"{{시도}}_{pt.label_ko}_{pt.deal_type}_{{연도}}.csv")

    def _select_all_regions(self) -> None:
        for var in self._region_vars.values():
            var.set(True)

    def _clear_all_regions(self) -> None:
        for var in self._region_vars.values():
            var.set(False)

    def _selected_regions(self) -> list[str]:
        return [r for r, v in self._region_vars.items() if v.get()]

    def _pick_output(self) -> None:
        path = filedialog.askdirectory(title="CSV 저장 폴더")
        if path:
            self.output_var.set(path)

    def _append_log(self, level: str, message: str) -> None:
        tag = "fail" if level == "fail" else "info"
        self.log_box.insert(tk.END, message + "\n", tag)
        self.log_box.see(tk.END)

    def _poll_log(self) -> None:
        while True:
            try:
                item = self._log_queue.get_nowait()
            except queue.Empty:
                break
            if item is None:
                self._on_worker_done()
                continue
            level, message = item
            self._append_log(level, message)
        self.after(200, self._poll_log)

    def _resolve_output_dir(self) -> Path:
        base = Path(self.output_var.get().strip()).expanduser()
        pt = get_property_type(self._selected_type_key())
        return base / pt.output_subdir(int(self.start_year_var.get()), int(self.end_year_var.get()))

    def _start(self) -> None:
        if self._worker and self._worker.is_alive():
            return

        start_y = int(self.start_year_var.get())
        end_y = int(self.end_year_var.get())
        if start_y > end_y:
            messagebox.showerror("입력 오류", "시작 연도가 종료 연도보다 큽니다.")
            return

        regions = self._selected_regions()
        if not regions:
            messagebox.showerror("입력 오류", "최소 1개 시도를 선택하세요.")
            return

        max_new = int(self.max_var.get())
        if max_new < 1 or max_new > 100:
            messagebox.showerror("입력 오류", "신규 다운로드 상한은 1~100 입니다.")
            return

        pt = get_property_type(self._selected_type_key())
        output_dir = self._resolve_output_dir()
        job = DownloadJob(
            property_type=pt,
            start_year=start_y,
            end_year=end_y,
            output_dir=output_dir,
            regions=regions,
            max_new_downloads=max_new,
            headless=bool(self.headless_var.get()),
        )

        self._stop_flag.clear()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self._append_log("info", "=" * 40)
        self._append_log("info", f"작업 시작 → {output_dir}")
        self._append_log("info", f"시도 {len(regions)}개: {', '.join(regions)}")

        def worker() -> None:
            try:
                run_download(
                    job,
                    log_level=lambda lvl, msg: self._log_queue.put((lvl, msg)),
                    should_stop=self._stop_flag.is_set,
                )
            except Exception as exc:
                self._log_queue.put(("fail", f"치명적 오류: {exc}"))
            finally:
                self._log_queue.put(None)

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()

    def _stop(self) -> None:
        self._stop_flag.set()
        self._append_log("info", "중지 요청 — 현재 파일 처리 후 종료합니다.")

    def _on_worker_done(self) -> None:
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self._worker = None


def main() -> None:
    app = CollectorApp()
    app.mainloop()
