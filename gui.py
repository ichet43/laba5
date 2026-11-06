import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import subprocess, os, sys, threading, queue

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
GEN_SCRIPT = os.path.join(BASE_DIR, "generator.py")
PY_SORT = os.path.join(BASE_DIR, "ext_sort_py.py")
CPP_BIN = os.path.join(BASE_DIR, "ext_sort_cpp" + (".exe" if os.name == "nt" else ""))

class LabGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("External Sort — Исследование алгоритмов")
        self.root.minsize(1100, 750)
        self.root.configure(bg="#f0f0f0") # Мягкий фон окна
        self._apply_style()
        self.q = queue.Queue()
        self._init_vars()
        self._build_ui()
        self._start_polling()

    def _apply_style(self):
        s = ttk.Style()
        s.theme_use("clam") # Более современная тема оформления
        s.configure(".", background="#f0f0f0")
        s.configure("TButton", padding=8, font=("Segoe UI", 11))
        s.configure("TLabel", background="#f0f0f0", font=("Segoe UI", 11))
        s.configure("TLabelframe", background="#f0f0f0", bordercolor="#cccccc", relief="solid", borderwidth=1)
        s.configure("TLabelframe.Label", background="#f0f0f0", font=("Segoe UI", 11, "bold"), foreground="#333333")
        s.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground="#2c3e50")

    def _init_vars(self):
        self.csv_p = tk.StringVar(value="")
        self.k_idx = tk.IntVar(value=2)
        self.ch_sz = tk.IntVar(value=50)
        self.btns = []
        self.working = False

    def _build_ui(self):
        # Главный контейнер с отступами
        main = ttk.Frame(self.root, padding=20)
        main.pack(fill=tk.BOTH, expand=True)

        # Заголовок
        ttk.Label(main, text="Внешняя сортировка данных", style="Header.TLabel").pack(anchor="w", pady=(0, 15))

        # --- Блок конфигурации ---
        cfg = ttk.LabelFrame(main, text=" Параметры ", padding=15)
        cfg.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(cfg, text="Файл CSV:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(cfg, textvariable=self.csv_p, width=70, font=("Segoe UI", 10)).grid(row=0, column=1, padx=10, sticky="w")
        b = ttk.Button(cfg, text="Обзор...", command=self._browse)
        b.grid(row=0, column=2, padx=5)
        self.btns.append(b)

        ttk.Label(cfg, text="Ключ сортировки (0-4):").grid(row=1, column=0, sticky="w", pady=5)
        self.key_box = ttk.Spinbox(cfg, from_=0, to=4, textvariable=self.k_idx, width=5, font=("Segoe UI", 10))
        self.key_box.grid(row=1, column=1, sticky="w", padx=10)
        self.key_box.bind("<Return>", self._wrap_key)
        self.key_box.bind("<FocusOut>", self._wrap_key)
        
        # Обновленная подсказка для ключей
        ttk.Label(cfg, text="0: shipment_id | 1: city | 2: weight | 3: status | 4: row_id", foreground="#666666").grid(row=1, column=1, sticky="w", padx=(60, 0))

        ttk.Label(cfg, text="Размер чанка (МБ):").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Spinbox(cfg, from_=10, to=200, increment=10, textvariable=self.ch_sz, width=5, font=("Segoe UI", 10)).grid(row=2, column=1, sticky="w", padx=10)

        # --- Блок действий ---
        ctrl = ttk.Frame(main)
        ctrl.pack(fill=tk.X, pady=(0, 15))

        b = ttk.Button(ctrl, text="1. Сгенерировать данные", command=self._generate)
        b.pack(side=tk.LEFT, padx=(0, 10), fill=tk.Y, expand=True)
        self.btns.append(b)

        b = ttk.Button(ctrl, text="2. Запустить C++", command=lambda: self._sort("cpp"))
        b.pack(side=tk.LEFT, padx=10, fill=tk.Y, expand=True)
        self.btns.append(b)

        b = ttk.Button(ctrl, text="2. Запустить Python", command=lambda: self._sort("py"))
        b.pack(side=tk.LEFT, padx=(10, 0), fill=tk.Y, expand=True)
        self.btns.append(b)

        # --- Блок предпросмотра ---
        prev_frame = ttk.Frame(main)
        prev_frame.pack(fill=tk.X, pady=(0, 10))

        b = ttk.Button(prev_frame, text="Посмотреть исходный CSV", command=self._preview_csv)
        b.pack(side=tk.LEFT, padx=(0, 10), fill=tk.Y, expand=True)
        self.btns.append(b)

        b = ttk.Button(prev_frame, text="Сравнить отсортированные файлы", command=self._preview_sorted)
        b.pack(side=tk.LEFT, padx=(10, 0), fill=tk.Y, expand=True)
        self.btns.append(b)

        # --- Блок логов и вывода ---
        out = ttk.Frame(main)
        out.pack(fill=tk.BOTH, expand=True)

        self.log_txt = scrolledtext.ScrolledText(out, height=12, state="disabled", wrap=tk.WORD, font=("Consolas", 10), bg="#ffffff", relief="solid", borderwidth=1)
        self.log_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.prev_txt = scrolledtext.ScrolledText(out, height=12, state="disabled", wrap=tk.WORD, font=("Consolas", 10), bg="#ffffff", relief="solid", borderwidth=1)
        self.prev_txt.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # --- Блок прогресса ---
        prog = ttk.Frame(main)
        prog.pack(fill=tk.X, pady=(15, 5))
        
        self.pbar = ttk.Progressbar(prog, mode="determinate", maximum=100)
        self.pbar.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0, 15))
        
        self.pct_lbl = ttk.Label(prog, text="0%", font=("Segoe UI", 12, "bold"), foreground="#2c3e50")
        self.pct_lbl.pack(side=tk.RIGHT)

        # Статус
        self.status_lbl = ttk.Label(main, text="Готов к работе", font=("Segoe UI", 10, "italic"), foreground="#555555")
        self.status_lbl.pack(anchor="w")

    def _wrap_key(self, event=None):
        self.k_idx.set(self.k_idx.get() % 5) # Теперь 5 колонок
        return "break"

    def _browse(self):
        p = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if p: self.csv_p.set(p)

    def _log(self, t):
        self.log_txt.config(state="normal")
        self.log_txt.insert(tk.END, t + "\n")
        self.log_txt.see(tk.END)
        self.log_txt.config(state="disabled")

    def _show_prev(self, t):
        self.prev_txt.config(state="normal")
        self.prev_txt.delete("1.0", tk.END)
        self.prev_txt.insert(tk.END, t)
        self.prev_txt.config(state="disabled")

    def _set_st(self, t): self.status_lbl.config(text=t)

    def _lock(self):
        self.working = True
        for b in self.btns: b.config(state=tk.DISABLED)

    def _unlock(self):
        self.working = False
        for b in self.btns: b.config(state=tk.NORMAL)

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                typ, val = msg[0], msg[1:]
                if typ == "log": self._log(val[0])
                elif typ == "prev": self._show_prev(val[0])
                elif typ == "st": self._set_st(val[0])
                elif typ == "prog":
                    pct = min(100, max(0, val[0]))
                    self.pbar["value"] = pct
                    self.pct_lbl.config(text="%d%%" % pct)
                elif typ == "lock": self._lock()
                elif typ == "unlock": self._unlock()
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _parse_progress(self, line):
        try:
            return int(line.split(":", 1)[1].strip().rstrip("%"))
        except (ValueError, IndexError):
            return None

    def _stream_run(self, cmd, on_progress=None):
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, cwd=BASE_DIR,
                                encoding='utf-8', errors='replace')
        for line in iter(proc.stdout.readline, ""):
            line = line.rstrip()
            if not line: continue
            if line.startswith("PROGRESS:"):
                pct = self._parse_progress(line)
                if pct is not None:
                    if on_progress: on_progress(pct)
                    else: self.q.put(("prog", pct))
            else:
                self.q.put(("log", line))
        proc.wait()
        return proc.returncode

    def _generate(self):
        if self.working: return
        self.q.put(("lock",)); self.root.update_idletasks()
        self.q.put(("st", "Генерация CSV...")); self.q.put(("prog", 0))

        def _run():
            try:
                self.q.put(("log", "Запуск генератора (1.0 GB)..."))
                rc = self._stream_run([PY, GEN_SCRIPT, "1.0", "data.csv"])
                if rc == 0:
                    self.q.put(("prog", 100)); self.q.put(("st", "Генерация завершена"))
                    # Автоматически подставляем путь к сгенерированному файлу
                    self.csv_p.set(os.path.join(BASE_DIR, "data.csv"))
                else:
                    self.q.put(("st", "Ошибка генерации"))
            except Exception as e:
                self.q.put(("log", "Ошибка: %s" % e)); self.q.put(("st", "Сбой"))
            finally:
                self.q.put(("unlock",))

        threading.Thread(target=_run, daemon=True).start()

    def _sort(self, lang):
        if self.working: return
        p = self.csv_p.get()
        if not p or not os.path.exists(p):
            self.q.put(("log", "Файл CSV не найден.")); return

        k = self.k_idx.get()
        ch = self.ch_sz.get()
        abs_p = os.path.abspath(p)
        out_file = os.path.join(os.path.dirname(abs_p), "sorted_%s.txt" % lang)
        
        if os.path.exists(out_file):
            try: os.remove(out_file)
            except OSError: pass

        self.q.put(("lock",)); self.root.update_idletasks()
        self.q.put(("st", "Сортировка (%s)..." % lang.upper())); self.q.put(("prog", 0))
        self.q.put(("log", "Запуск внешней сортировки (%s)..." % lang.upper()))

        def _run():
            try:
                if lang == "cpp":
                    if not os.path.exists(CPP_BIN):
                        self.q.put(("log", "Ошибка: бинарник C++ не найден.")); return
                    cmd = [CPP_BIN, abs_p, str(k), str(ch), "--output", out_file]
                else:
                    cmd = [PY, PY_SORT, abs_p, str(k), str(ch), "--output", out_file]

                rc = self._stream_run(cmd)
                if rc == 0:
                    self.q.put(("prog", 100)); self.q.put(("st", "Сортировка завершена"))
                else:
                    self.q.put(("st", "Ошибка сортировки (rc=%d)" % rc))
            except Exception as e:
                self.q.put(("log", "Ошибка: %s" % e)); self.q.put(("st", "Сбой"))
            finally:
                self.q.put(("unlock",))

        threading.Thread(target=_run, daemon=True).start()

    def _get_preview_data(self, filepath):
        if not os.path.exists(filepath): return None
        try:
            size = os.path.getsize(filepath)
            with open(filepath, "r", encoding="utf-8") as f:
                head = [f.readline() for _ in range(3)]
                f.seek(size // 2); f.readline()
                mid = [f.readline() for _ in range(3)]
                f.seek(0, 2); end = f.tell()
                f.seek(max(0, end - 500))
                tail = f.readlines()[-3:]
            return {"size": size / 1024**2, "head": "".join(head),
                    "mid": "".join(mid), "tail": "".join(tail)}
        except Exception:
            return None

    def _preview_csv(self):
        p = self.csv_p.get()
        if not p or not os.path.exists(p):
            self.q.put(("log", "Файл CSV не найден.")); return
        self.q.put(("lock",)); self.root.update_idletasks()

        def _run():
            d = self._get_preview_data(p)
            if d:
                txt = "=== CSV ===\nРазмер: %.2f MB\n\nНАЧАЛО:\n%s\nСЕРЕДИНА:\n%s\nКОНЕЦ:\n%s" % (
                    d["size"], d["head"], d["mid"], d["tail"])
                self.q.put(("prev", txt)); self.q.put(("st", "Просмотр CSV готов"))
            else:
                self.q.put(("log", "Не удалось прочитать CSV"))
            self.q.put(("unlock",))

        threading.Thread(target=_run, daemon=True).start()

    def _preview_sorted(self):
        abs_p = os.path.abspath(self.csv_p.get()) if self.csv_p.get() else ""
        cpp_f = os.path.join(os.path.dirname(abs_p), "sorted_cpp.txt")
        py_f = os.path.join(os.path.dirname(abs_p), "sorted_py.txt")
        self.q.put(("lock",)); self.root.update_idletasks()

        def _run():
            txt = "=== РЕЗУЛЬТАТЫ СОРТИРОВКИ ===\n\n"
            for name, path in (("C++", cpp_f), ("Python", py_f)):
                d = self._get_preview_data(path)
                if d:
                    txt += "[%s] %s | Размер: %.2f MB\nНАЧАЛО:\n%s\nСЕРЕДИНА:\n%s\nКОНЕЦ:\n%s\n\n" % (
                        name, os.path.basename(path), d["size"], d["head"], d["mid"], d["tail"])
                else:
                    txt += "[%s] %s: файл не найден.\n\n" % (name, os.path.basename(path))
            self.q.put(("prev", txt)); self.q.put(("st", "Просмотр результатов готов"))
            self.q.put(("unlock",))

        threading.Thread(target=_run, daemon=True).start()

    def _start_polling(self): self._poll()


if __name__ == "__main__":
    root = tk.Tk()
    app = LabGUI(root)
    root.mainloop()
