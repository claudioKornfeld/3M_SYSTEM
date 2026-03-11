# =============================================================================
# LANZADOR_3M.pyw  —  Formulario GUI del 3M_SYSTEM
# Ubicacion: C:\EXTERIOR\3M_SYSTEM\LANZADOR_3M.pyw
# Ejecutar con:  pythonw.exe  (sin consola) o  python.exe  (con consola)
# =============================================================================

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import subprocess
import threading
import sys
import os

PYTHON = r"C:\Users\Claudio\AppData\Local\Python\bin\python.exe"
BASE_DIR = r"C:\EXTERIOR\3M_SYSTEM"
MAIN_PY  = os.path.join(BASE_DIR, "main.py")

# ---------------------------------------------------------------------------
# Colores / estilo
# ---------------------------------------------------------------------------
BG          = "#1e1e2e"
BG_PANEL    = "#2a2a3e"
BG_BTN      = "#2563eb"
BG_BTN_HOV  = "#1d4ed8"
BG_REPORT   = "#16a34a"
BG_REPORT_H = "#15803d"
BG_EXIT     = "#dc2626"
BG_EXIT_H   = "#b91c1c"
FG          = "#f1f5f9"
FG_DIM      = "#94a3b8"
ACCENT      = "#38bdf8"
FONT_TITLE  = ("Segoe UI", 13, "bold")
FONT_LBL    = ("Segoe UI", 10)
FONT_BTN    = ("Segoe UI", 10, "bold")
FONT_LOG    = ("Consolas", 9)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_cmd(args: list, log: scrolledtext.ScrolledText):
    """Ejecuta un comando en hilo secundario y vuelca salida en el log."""
    def _worker():
        _log(log, f"\n▶  {' '.join(args)}\n{'─'*60}\n")
        try:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=BASE_DIR,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            for line in proc.stdout:
                _log(log, line)
            proc.wait()
            _log(log, f"\n{'─'*60}\n✔  Proceso finalizado (código {proc.returncode})\n")
        except Exception as e:
            _log(log, f"\n✖  Error al ejecutar: {e}\n")
    threading.Thread(target=_worker, daemon=True).start()


def _log(log: scrolledtext.ScrolledText, text: str):
    log.configure(state="normal")
    log.insert(tk.END, text)
    log.see(tk.END)
    log.configure(state="disabled")


def pick_file(title: str, filetypes: list) -> str | None:
    """Abre diálogo de archivo SIN directorio inicial fijo → navega libremente."""
    return filedialog.askopenfilename(title=title, filetypes=filetypes) or None


def make_btn(parent, text, command, color=BG_BTN, hover=BG_BTN_HOV, width=28):
    btn = tk.Button(
        parent, text=text, command=command,
        bg=color, fg=FG, activebackground=hover, activeforeground=FG,
        font=FONT_BTN, relief="flat", bd=0,
        padx=12, pady=8, width=width, cursor="hand2",
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=hover))
    btn.bind("<Leave>", lambda e: btn.config(bg=color))
    return btn


# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("3M_SYSTEM  |  Lilis S.A.")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(780, 520)

        self._build_header()
        self._build_body()
        self._build_footer()

        # Centrar ventana
        self.update_idletasks()
        w, h = 860, 600
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------------ UI

    def _build_header(self):
        hdr = tk.Frame(self, bg="#0f172a", pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="3M_SYSTEM", font=("Segoe UI", 16, "bold"),
                 bg="#0f172a", fg=ACCENT).pack()
        tk.Label(hdr, text="Lilis S.A.  |  Proveedor 3M / Solventum",
                 font=FONT_LBL, bg="#0f172a", fg=FG_DIM).pack()

    def _build_body(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=(12, 0))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # ── Panel izquierdo: botones ─────────────────────────────────────
        left = tk.Frame(body, bg=BG_PANEL, padx=16, pady=16)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 12))

        tk.Label(left, text="CARGAR DOCUMENTO",
                 font=("Segoe UI", 9, "bold"), bg=BG_PANEL, fg=FG_DIM).pack(anchor="w", pady=(0, 8))

        btns = [
            ("📄  Cargar FIREX.txt",       self.load_firex),
            ("🧾  Cargar Invoice PDF",      self.load_invoice),
            ("📦  Cargar Packing List PDF", self.load_plist),
            ("📋  Cargar PO PDF",           self.load_po),
            ("🛃  Cargar Despacho Aduana",  self.load_aduana),
        ]
        for label, cmd in btns:
            make_btn(left, label, cmd).pack(fill="x", pady=3)

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=14)

        tk.Label(left, text="HERRAMIENTAS",
                 font=("Segoe UI", 9, "bold"), bg=BG_PANEL, fg=FG_DIM).pack(anchor="w", pady=(0, 8))

        make_btn(left, "📊  Ver resumen de tablas",
                 self.run_report, color=BG_REPORT, hover=BG_REPORT_H).pack(fill="x", pady=3)

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=14)

        make_btn(left, "✖   Salir",
                 self.quit_app, color=BG_EXIT, hover=BG_EXIT_H).pack(fill="x", pady=3)

        # ── Panel derecho: log ───────────────────────────────────────────
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        tk.Label(right, text="Consola de salida",
                 font=("Segoe UI", 9, "bold"), bg=BG, fg=FG_DIM).grid(
                 row=0, column=0, sticky="w", pady=(0, 4))

        self.log = scrolledtext.ScrolledText(
            right, bg="#0d1117", fg="#c9d1d9", font=FONT_LOG,
            relief="flat", state="disabled", wrap="word",
            insertbackground=FG,
        )
        self.log.grid(row=1, column=0, sticky="nsew")

        btn_clear = tk.Button(
            right, text="Limpiar log", command=self._clear_log,
            bg=BG_PANEL, fg=FG_DIM, font=("Segoe UI", 8),
            relief="flat", bd=0, cursor="hand2",
        )
        btn_clear.grid(row=2, column=0, sticky="e", pady=(4, 0))

    def _build_footer(self):
        ft = tk.Frame(self, bg="#0f172a", pady=6)
        ft.pack(fill="x")
        tk.Label(ft, text="3M_SYSTEM v1.0.0  |  05/03/2026",
                 font=("Segoe UI", 8), bg="#0f172a", fg=FG_DIM).pack()

    # ------------------------------------------------------------------ Acciones

    def load_firex(self):
        f = pick_file("Seleccionar FIREX.txt", [("Archivos TXT", "*.txt"), ("Todos", "*.*")])
        if f:
            run_cmd([PYTHON, MAIN_PY, "--firex", f], self.log)

    def load_invoice(self):
        f = pick_file("Seleccionar Invoice PDF", [("Archivos PDF", "*.pdf"), ("Todos", "*.*")])
        if f:
            run_cmd([PYTHON, MAIN_PY, "--invoice", f], self.log)

    def load_plist(self):
        f = pick_file("Seleccionar Packing List PDF", [("Archivos PDF", "*.pdf"), ("Todos", "*.*")])
        if f:
            run_cmd([PYTHON, MAIN_PY, "--plist", f], self.log)

    def load_po(self):
        f = pick_file("Seleccionar PO PDF", [("Archivos PDF", "*.pdf"), ("Todos", "*.*")])
        if f:
            run_cmd([PYTHON, MAIN_PY, "--po", f], self.log)

    def load_aduana(self):
        f = pick_file("Seleccionar Despacho de Aduana PDF", [("Archivos PDF", "*.pdf"), ("Todos", "*.*")])
        if f:
            run_cmd([PYTHON, MAIN_PY, "--aduana", f], self.log)

    def run_report(self):
        run_cmd([PYTHON, MAIN_PY, "--report"], self.log)

    def quit_app(self):
        if messagebox.askyesno("Salir", "¿Desea cerrar el 3M_SYSTEM?"):
            self.destroy()

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", tk.END)
        self.log.configure(state="disabled")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = App()
    app.mainloop()
