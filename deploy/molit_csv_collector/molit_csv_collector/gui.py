"""tkinter GUI — 기간·유형·거래구분·시도 선택 후 CSV 수집."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .config import (
    DEAL_TYPE_CHOICES,
    DEAL_TYPE_RENT,
    DEAL_TYPE_SALE,
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
        self.geometry("820x760")
        self.minsize(720, 640)

        self._worker: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._log_queue: queue.Queue[tuple[str, str] | None] = queue.Queue()
        self._region_vars: dict[str, tk.BooleanVar] = {}
        self._type_vars: dict[str, tk.BooleanVar] = {}
        self._type_checks: dict[str, ttk.Checkbutton] = {}

        self._build_form()
        self.after(200, self._poll_log)

    def _build_form(self) -> None:
        pad = {"padx": 10, "pady": 4}
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        row = 0
        ttk.Label(frm, text="부동산 유형").grid(row=row, column=0, sticky=tk.W, **pad)
        type_hdr = ttk.Frame(frm)
        type_hdr.grid(row=row, column=1, columnspan=2, sticky=tk.EW, **pad)
        ttk.Button(type_hdr, text="전체 선택", command=self._select_all_types).pack(
            side=tk.LEFT
        )
        ttk.Button(type_hdr, text="전체 해제", command=self._clear_all_types).pack(
            side=tk.LEFT, padx=6
        )
        self.type_hint_var = tk.StringVar()
        ttk.Label(type_hdr, textvariable=self.type_hint_var, foreground="#555").pack(
            side=tk.LEFT, padx=8
        )

        row += 1
        type_box = ttk.Frame(frm)
        type_box.grid(row=row, column=1, columnspan=2, sticky=tk.EW, **pad)
        for i, (key, label) in enumerate(PROPERTY_TYPE_CHOICES):
            var = tk.BooleanVar(value=True)
            self._type_vars[key] = var
            check = ttk.Checkbutton(type_box, text=label, variable=var, width=14)
            self._type_checks[key] = check
            check.grid(row=i // 3, column=i % 3, sticky=tk.W, padx=2, pady=1)

        row += 1
        ttk.Label(frm, text="거래 구분").grid(row=row, column=0, sticky=tk.W, **pad)
        deal_frm = ttk.Frame(frm)
        deal_frm.grid(row=row, column=1, columnspan=2, sticky=tk.W, **pad)
        self.deal_var = tk.StringVar(value="sale")
        self._deal_sale = ttk.Radiobutton(
            deal_frm,
            text=DEAL_TYPE_SALE,
            variable=self.deal_var,
            value="sale",
            command=self._on_type_change,
        )
        self._deal_sale.pack(side=tk.LEFT, padx=(0, 12))
        self._deal_rent = ttk.Radiobutton(
            deal_frm,
            text=DEAL_TYPE_RENT,
            variable=self.deal_var,
            value="rent",
            command=self._on_type_change,
        )
        self._deal_rent.pack(side=tk.LEFT)
        self.deal_hint_var = tk.StringVar()
        ttk.Label(deal_frm, textvariable=self.deal_hint_var, foreground="#555").pack(
            side=tk.LEFT, padx=12
        )

        row += 1
        period_frm = ttk.Frame(frm)
        period_frm.grid(row=row, column=0, columnspan=3, sticky=tk.W, **pad)
        ttk.Label(period_frm, text="시작").pack(side=tk.LEFT)
        self.start_year_var = tk.IntVar(value=2010)
        ttk.Spinbox(
            period_frm, from_=2006, to=2030, textvariable=self.start_year_var, width=6
        ).pack(side=tk.LEFT, padx=(6, 2))
        ttk.Label(period_frm, text="년").pack(side=tk.LEFT)
        self.start_month_var = tk.StringVar(value="1")
        ttk.Spinbox(
            period_frm, from_=1, to=12, textvariable=self.start_month_var, width=4
        ).pack(side=tk.LEFT, padx=(6, 2))
        ttk.Label(period_frm, text="월").pack(side=tk.LEFT, padx=(0, 16))
        ttk.Label(period_frm, text="종료").pack(side=tk.LEFT)
        self.end_year_var = tk.IntVar(value=2020)
        ttk.Spinbox(
            period_frm, from_=2006, to=2030, textvariable=self.end_year_var, width=6
        ).pack(side=tk.LEFT, padx=(6, 2))
        ttk.Label(period_frm, text="년").pack(side=tk.LEFT)
        self.end_month_var = tk.StringVar(value="12")
        ttk.Spinbox(
            period_frm, from_=1, to=12, textvariable=self.end_month_var, width=4
        ).pack(side=tk.LEFT, padx=(6, 2))
        ttk.Label(period_frm, text="월").pack(side=tk.LEFT)

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

        self._on_type_change()

    def _selected_property_types(self):
        return [
            get_property_type(key, deal_type=self.deal_var.get())
            for key, var in self._type_vars.items()
            if var.get()
        ]

    def _on_type_change(self, *_args) -> None:
        if self.deal_var.get() == DEAL_TYPE_RENT:
            unsupported = [
                key for key in self._type_vars
                if not get_property_type(key).supports_rent
            ]
            for key in unsupported:
                self._type_vars[key].set(False)
                self._type_checks[key].config(state=tk.DISABLED)
            self.deal_hint_var.set("전월세 미지원 유형은 자동 제외")
        else:
            for check in self._type_checks.values():
                check.config(state=tk.NORMAL)
            self.deal_hint_var.set("")
        selected = [label for key, label in PROPERTY_TYPE_CHOICES if self._type_vars[key].get()]
        self.type_hint_var.set(f"{len(selected)}개 유형 선택" if selected else "유형을 선택하세요")

    def _select_all_types(self) -> None:
        for key, var in self._type_vars.items():
            if self.deal_var.get() == DEAL_TYPE_RENT and not get_property_type(key).supports_rent:
                continue
            var.set(True)
        self._on_type_change()

    def _clear_all_types(self) -> None:
        for var in self._type_vars.values():
            var.set(False)
        self._on_type_change()

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

    def _resolve_output_dir(self, pt) -> Path:
        base = Path(self.output_var.get().strip()).expanduser()
        return base / pt.output_subdir(
            int(self.start_year_var.get()),
            int(self.start_month_var.get()),
            int(self.end_year_var.get()),
            int(self.end_month_var.get()),
        )

    def _start(self) -> None:
        if self._worker and self._worker.is_alive():
            return

        start_y = int(self.start_year_var.get())
        end_y = int(self.end_year_var.get())
        start_m = int(self.start_month_var.get())
        end_m = int(self.end_month_var.get())
        if (start_y, start_m) > (end_y, end_m):
            messagebox.showerror("입력 오류", "시작 기간이 종료 기간보다 늦습니다.")
            return
        if not (1 <= start_m <= 12 and 1 <= end_m <= 12):
            messagebox.showerror("입력 오류", "월은 1~12 사이여야 합니다.")
            return

        regions = self._selected_regions()
        if not regions:
            messagebox.showerror("입력 오류", "최소 1개 시도를 선택하세요.")
            return

        max_new = int(self.max_var.get())
        if max_new < 1 or max_new > 100:
            messagebox.showerror("입력 오류", "신규 다운로드 상한은 1~100 입니다.")
            return

        try:
            property_types = self._selected_property_types()
        except ValueError as exc:
            messagebox.showerror("입력 오류", str(exc))
            return
        if not property_types:
            messagebox.showerror("입력 오류", "최소 1개 부동산 유형을 선택하세요.")
            return

        self._stop_flag.clear()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self._append_log("info", "=" * 40)
        self._append_log("info", f"작업 시작 → {len(property_types)}개 유형")
        self._append_log("info", f"시도 {len(regions)}개: {', '.join(regions)}")

        def worker() -> None:
            try:
                for pt in property_types:
                    if self._stop_flag.is_set():
                        break
                    output_dir = self._resolve_output_dir(pt)
                    self._log_queue.put(("info", f"{pt.label_ko} → {output_dir}"))
                    job = DownloadJob(
                        property_type=pt,
                        start_year=start_y,
                        start_month=start_m,
                        end_year=end_y,
                        end_month=end_m,
                        output_dir=output_dir,
                        regions=regions,
                        max_new_downloads=max_new,
                        headless=bool(self.headless_var.get()),
                    )
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
