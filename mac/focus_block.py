#!/usr/bin/env python3
"""FocusBlock v4 – Responsive UI (se adapta al tamaño de ventana)"""

import tkinter as tk
from tkinter import messagebox
import subprocess, re, json, time, threading, random, string
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

HOSTS_FILE   = "/etc/hosts"
MARKER_START = "# === FOCUSBLOCK START ==="
MARKER_END   = "# === FOCUSBLOCK END ==="
CONFIG_FILE  = Path.home() / ".focusblock_config.json"
SUDOERS_FILE = "/etc/sudoers.d/focusblock"
CODE_FILE    = Path.home() / ".focusblock_code"

# ── Credenciales de envío ─────────────────────────────────────────────────────
import base64 as _b64
_BREVO_SENDER     = _b64.b64decode("ZmJsb2NrYXBwQGdtYWlsLmNvbQ==").decode()
_BREVO_SMTP_LOGIN = _b64.b64decode("YWQ4NzJiMDAxQHNtdHAtYnJldm8uY29t").decode()
_BREVO_KEY        = _b64.b64decode("eHNtdHBzaWItODc5MTM0YmJjN2ZhOGIxNGRlYTAwYjhiY2RkOTVmOGRmYzE0N2EyZDM3MzU4ODI3MjIyZTI1YjYzYmE0ODNlZi1YNTZ3dUdRYmVWTEpaVnBV").decode()


def save_active_code(code):
    import base64
    data = base64.b64encode(code.encode()).decode()
    with open(CODE_FILE, "w") as f: f.write(data)

def load_active_code():
    import base64
    if CODE_FILE.exists() and is_blocking():
        try:
            data = CODE_FILE.read_text().strip()
            return base64.b64decode(data).decode()
        except: pass
    return None

def clear_active_code():
    if CODE_FILE.exists():
        CODE_FILE.unlink()

DEFAULT_SITES = [
    "youtube.com","www.youtube.com",
    "instagram.com","www.instagram.com",
    "twitter.com","www.twitter.com","x.com","www.x.com",
    "facebook.com","www.facebook.com",
    "tiktok.com","www.tiktok.com",
    "reddit.com","www.reddit.com",
    "twitch.tv","www.twitch.tv",
    "netflix.com","www.netflix.com",
    "9gag.com","www.9gag.com",
    "poki.com","www.poki.com",
    "miniclip.com","kongregate.com",
]

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f: return json.load(f)
        except: pass
    return {"sites": DEFAULT_SITES.copy(), "email_to": "", "sudo_configured": False}

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f: json.dump(cfg, f, indent=2)

HELPER_SCRIPT = Path.home() / ".focusblock_helper.sh"

def get_username():
    import os; return os.environ.get("USER", "")

def is_sudo_configured():
    return HELPER_SCRIPT.exists() and Path(SUDOERS_FILE).exists()

def configure_sudo():
    user = get_username()
    helper = str(HELPER_SCRIPT)
    script_content = f"""#!/bin/bash
ACTION=$1
HOSTS={HOSTS_FILE}
if [ "$ACTION" = "enable" ]; then
    cat /tmp/fb_block.txt >> "$HOSTS"
elif [ "$ACTION" = "disable" ]; then
    cp /tmp/fb_clean.txt "$HOSTS"
elif [ "$ACTION" = "flush" ]; then
    dscacheutil -flushcache
    killall -HUP mDNSResponder 2>/dev/null || true
fi
"""
    with open("/tmp/fb_helper.sh", "w") as f: f.write(script_content)
    rule = f"{user} ALL=(ALL) NOPASSWD: {helper}\n"
    with open("/tmp/fb_sudoers.txt", "w") as f: f.write(rule)
    cmd = (
        f"cp /tmp/fb_helper.sh {helper} && "
        f"chmod 755 {helper} && "
        f"chmod 440 /tmp/fb_sudoers.txt && "
        f"cp /tmp/fb_sudoers.txt {SUDOERS_FILE}"
    )
    r = subprocess.run(["osascript", "-e",
        f'do shell script "{cmd}" with administrator privileges'],
        capture_output=True, text=True)
    return r.returncode == 0

def is_blocking():
    try:
        with open(HOSTS_FILE) as f: return MARKER_START in f.read()
    except: return False

def run_privileged(action):
    helper = str(HELPER_SCRIPT)
    if is_sudo_configured():
        r = subprocess.run(["sudo", helper, action], capture_output=True, text=True)
        return r.returncode == 0
    else:
        cmd = f"{helper} {action}" if HELPER_SCRIPT.exists() else ""
        if not cmd: return False
        r = subprocess.run(["osascript", "-e",
            f'do shell script "{cmd}" with administrator privileges'],
            capture_output=True, text=True)
        return r.returncode == 0

def enable_block(sites):
    lines = [MARKER_START] + [f"127.0.0.1  {s}" for s in sites] + [MARKER_END]
    with open("/tmp/fb_block.txt", "w") as f: f.write("\n".join(lines)+"\n")
    ok = run_privileged("enable")
    run_privileged("flush")
    return ok

def disable_block():
    try:
        with open(HOSTS_FILE) as f: content = f.read()
    except: return False
    cleaned = re.sub(
        rf"{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}\n?",
        "", content, flags=re.DOTALL)
    with open("/tmp/fb_clean.txt", "w") as f: f.write(cleaned)
    ok = run_privileged("disable")
    run_privileged("flush")
    return ok

def generate_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def send_brevo_email(email_to, code):
    html = f"""
    <div style="font-family:monospace;background:#0d0d14;color:#ddeeff;padding:36px;border-radius:12px;max-width:480px">
      <div style="font-size:22px;font-weight:bold;color:#b8ff4e;margin-bottom:8px">◈ FOCUSBLOCK</div>
      <div style="color:#6b7f99;margin-bottom:28px;font-size:13px">Sistema de bloqueo de distracciones</div>
      <div style="background:#161624;border:1px solid #1c2a3a;border-radius:8px;padding:24px;margin-bottom:24px">
        <div style="color:#6b7f99;font-size:12px;margin-bottom:12px">CÓDIGO DE DESBLOQUEO</div>
        <div style="font-size:38px;font-weight:900;letter-spacing:8px;color:#b8ff4e;text-align:center;padding:16px 0">
          {code}
        </div>
      </div>
      <div style="color:#6b7f99;font-size:12px;line-height:1.6">
        Introduce este código en FocusBlock para desactivar el bloqueo.<br>
        <span style="color:#ff4e6a">Recuerda: lo activaste para estudiar. ¡No te rindas!</span>
      </div>
    </div>
    """
    plain = f"Tu código de desbloqueo FocusBlock es: {code}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔐 Tu código FocusBlock: {code}"
    msg["From"]    = _BREVO_SENDER
    msg["To"]      = email_to
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html,  "html",  "utf-8"))
    with smtplib.SMTP("smtp-relay.brevo.com", 587) as s:
        s.ehlo(); s.starttls()
        s.login(_BREVO_SMTP_LOGIN, _BREVO_KEY)
        s.sendmail(_BREVO_SENDER, email_to, msg.as_string())

# ── Paleta ────────────────────────────────────────────────────────────────────
C = dict(
    bg="#07090f", panel="#0e1420", panel2="#111827",
    border="#1c2a3a", border2="#243040",
    accent="#b8ff4e", accent_dim="#7ab832",
    red="#ff4e6a",    red_dim="#c0364d",
    orange="#ffaa4e", blue="#4eb8ff",
    text="#ddeeff",   muted="#4a6080", muted2="#6b7f99",
    entry="#0d1520",  white="#ffffff",
)
W, H = 620, 860


def _entry_style(extra=None):
    """Devuelve kwargs comunes para tk.Entry."""
    kw = dict(
        bg=C["entry"], fg=C["text"],
        insertbackground=C["accent"],
        font=("Courier", 11),
        bd=0, relief="flat",
        highlightthickness=1,
        highlightbackground=C["border"],
        highlightcolor=C["accent"],
    )
    if extra:
        kw.update(extra)
    return kw


class _Sep(tk.Frame):
    """Separador horizontal con etiqueta centrada."""
    def __init__(self, parent, text, **kw):
        super().__init__(parent, bg=C["bg"], **kw)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(2, weight=1)
        tk.Frame(self, bg=C["border"], height=1).grid(row=0, column=0, sticky="ew", pady=6)
        tk.Label(self, text=text, font=("Courier", 8, "bold"),
                 bg=C["bg"], fg=C["muted"], padx=10).grid(row=0, column=1)
        tk.Frame(self, bg=C["border"], height=1).grid(row=0, column=2, sticky="ew", pady=6)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg         = load_config()
        self.blocking    = is_blocking()
        self.active_code = load_active_code()
        self.timer_secs  = 0
        self.timer_run   = False

        self.title("FocusBlock")
        self.geometry(f"{W}x{H}")
        self.minsize(480, 640)
        self.resizable(True, True)
        self.configure(bg=C["bg"])

        # Centra la ventana en pantalla
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        self._build()
        self._refresh_status()

        # Escala de fuentes dinámica
        self._last_w = W
        self.bind("<Configure>", self._on_resize)

        if not is_sudo_configured():
            self.after(500, self._setup_sudo_prompt)

    def _font_size(self, base, min_size=7):
        """Devuelve tamaño de fuente proporcional al ancho actual."""
        w = self.winfo_width() or W
        scale = max(0.55, min(2.0, w / W))
        return max(min_size, round(base * scale))

    def _on_resize(self, event):
        # Solo reescalar cuando cambia el ancho de la ventana raíz
        if event.widget is not self:
            return
        if abs(event.width - self._last_w) < 4:
            return
        self._last_w = event.width
        self._apply_fonts()

    def _apply_fonts(self):
        """Actualiza todas las fuentes que deben escalar con la ventana."""
        fs = self._font_size  # atajo

        # Header título
        for lbl, base in zip(self._title_labels, [38, 38]):
            lbl.config(font=("Courier", fs(base, 18), "bold"))

        # Header subtítulo
        self._subtitle_lbl.config(font=("Courier", fs(10, 7)))

        # Status card — escala con el ancho disponible
        w = self.winfo_width() or W
        slbl_size = max(12, min(42, round(16 * (w / W) ** 1.1)))
        tlbl_size = max(8,  min(18, round(10 * (w / W) ** 0.9)))
        self.slbl.config(font=("Courier", slbl_size, "bold"))
        self.tlbl.config(font=("Courier", tlbl_size))

        # Dot — crece proporcionalmente con slbl
        dot_size = max(16, min(52, round(28 * (w / W) ** 1.0)))
        self._dot_canvas.config(width=dot_size, height=dot_size)
        self._dot_canvas.coords(self._dot, 2, 2, dot_size - 2, dot_size - 2)

        # Botón principal
        self.main_btn.config(font=("Courier", fs(14, 9), "bold"))

    # ── Setup sudo ────────────────────────────────────────────────────────────
    def _setup_sudo_prompt(self):
        if messagebox.askyesno("⚡ Configuración rápida",
            "¿Quieres que FocusBlock nunca vuelva a pedir\n"
            "contraseña de administrador?\n\n"
            "Solo necesitarás introducirla esta única vez."):
            if configure_sudo():
                self.cfg["sudo_configured"] = True
                save_config(self.cfg)
                messagebox.showinfo("✓ Listo",
                    "¡Perfecto! A partir de ahora FocusBlock\n"
                    "se activa y desactiva sin contraseña.")
                self.sudo_lbl.config(text="⚡ Sin contraseña admin", fg=C["accent"])
            else:
                messagebox.showwarning("Cancelado",
                    "Sin problema, seguirá pidiendo contraseña cada vez.")

    # ── Construcción UI ───────────────────────────────────────────────────────
    def _build(self):
        PAD = 20

        # ── Raíz: columna única que se expande ──
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)   # header
        self.rowconfigure(1, weight=0)   # status
        self.rowconfigure(2, weight=0)   # duración
        self.rowconfigure(3, weight=0)   # botón principal
        self.rowconfigure(4, weight=0)   # sep brevo
        self.rowconfigure(5, weight=0)   # campos brevo
        self.rowconfigure(6, weight=0)   # sep sitios
        self.rowconfigure(7, weight=1)   # lista sitios (se expande)
        self.rowconfigure(8, weight=0)   # añadir/quitar
        self.rowconfigure(9, weight=0)   # footer

        # ─────────────────────────────────────────
        # HEADER
        # ─────────────────────────────────────────
        hdr = tk.Frame(self, bg="#0a0f18")
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.columnconfigure(0, weight=1)
        hdr.columnconfigure(1, weight=0)

        title_frm = tk.Frame(hdr, bg="#0a0f18")
        title_frm.grid(row=0, column=0, sticky="w", padx=PAD, pady=(18, 4))
        lbl_focus = tk.Label(title_frm, text="FOCUS", font=("Courier", 38, "bold"),
                             bg="#0a0f18", fg=C["accent"])
        lbl_focus.pack(side="left")
        lbl_block = tk.Label(title_frm, text="BLOCK", font=("Courier", 38, "bold"),
                             bg="#0a0f18", fg=C["text"])
        lbl_block.pack(side="left")
        self._title_labels = [lbl_focus, lbl_block]

        tk.Label(hdr, text="v4.0", font=("Courier", 8),
                 bg=C["border2"], fg=C["muted2"],
                 padx=6, pady=2, relief="flat"
                 ).grid(row=0, column=1, padx=(0, PAD), pady=(22, 0), sticky="ne")

        self._subtitle_lbl = tk.Label(hdr, text="Sistema de bloqueo de distracciones",
                 font=("Courier", 10), bg="#0a0f18", fg=C["muted"])
        self._subtitle_lbl.grid(row=1, column=0, sticky="w", padx=PAD, pady=(0, 14))

        tk.Frame(self, bg=C["border"], height=1).grid(row=0, column=0, sticky="sew")

        # ─────────────────────────────────────────
        # STATUS CARD  (centrada, se expande)
        # ─────────────────────────────────────────
        sc = tk.Frame(self, bg=C["panel"],
                      highlightbackground=C["border2"], highlightthickness=1)
        sc.grid(row=1, column=0, sticky="ew", padx=PAD, pady=(14, 6))
        sc.columnconfigure(0, weight=1)

        # Barra de color izquierda via place (no ocupa columna en grid)
        self._status_bar = tk.Frame(sc, bg=C["muted"], width=5)
        self._status_bar.place(relx=0, rely=0, relheight=1, width=5)

        # Contenedor interno — todo el ancho menos la barra
        inner = tk.Frame(sc, bg=C["panel"])
        inner.grid(row=0, column=0, sticky="ew", padx=(18, 12), pady=16)
        inner.columnconfigure(1, weight=1)

        # Dot
        self._dot_canvas = tk.Canvas(inner, width=28, height=28,
                                     bg=C["panel"], highlightthickness=0)
        self._dot_canvas.grid(row=0, column=0, rowspan=2, padx=(6, 14))
        self._dot = self._dot_canvas.create_oval(2, 2, 26, 26,
                                                 fill=C["muted"], outline="")

        # Texto principal
        self.slbl = tk.Label(inner, text="INACTIVO",
                             font=("Courier", 16, "bold"),
                             bg=C["panel"], fg=C["muted"], anchor="w")
        self.slbl.grid(row=0, column=1, sticky="ew")

        # Texto secundario
        self.tlbl = tk.Label(inner, text="Activa el modo foco para comenzar",
                             font=("Courier", 10),
                             bg=C["panel"], fg=C["muted"], anchor="w")
        self.tlbl.grid(row=1, column=1, sticky="ew")

        # ─────────────────────────────────────────
        # DURACIÓN
        # ─────────────────────────────────────────
        dur_frm = tk.Frame(self, bg=C["bg"])
        dur_frm.grid(row=2, column=0, sticky="ew", padx=PAD, pady=(8, 4))
        dur_frm.columnconfigure(1, weight=1)

        tk.Label(dur_frm, text="DURACIÓN DEL BLOQUEO",
                 font=("Courier", 8, "bold"), bg=C["bg"], fg=C["muted2"]
                 ).grid(row=0, column=0, sticky="w")

        self.dur_var = tk.StringVar(value="25 min – Pomodoro")
        om = tk.OptionMenu(dur_frm, self.dur_var,
            "25 min – Pomodoro", "45 min", "1 hora", "2 horas", "4 horas",
            "Sin límite (requiere código)")
        om.config(bg=C["entry"], fg=C["text"], activebackground=C["border2"],
                  font=("Courier", 12), relief="flat", bd=0,
                  highlightthickness=1, highlightbackground=C["border"],
                  highlightcolor=C["accent"])
        om["menu"].config(bg=C["entry"], fg=C["text"], font=("Courier", 11))
        om.grid(row=0, column=1, sticky="ew", padx=(12, 0))

        # ─────────────────────────────────────────
        # BOTÓN PRINCIPAL
        # ─────────────────────────────────────────
        self.main_btn = tk.Button(self,
            text="▶  ACTIVAR MODO FOCO",
            font=("Courier", 14, "bold"),
            bg=C["accent"], fg=C["bg"],
            activebackground=C["accent_dim"], activeforeground=C["bg"],
            relief="flat", bd=0, cursor="hand2", height=2,
            command=self._toggle)
        self.main_btn.grid(row=3, column=0, sticky="ew", padx=PAD, pady=(6, 6))

        # ─────────────────────────────────────────
        # SEPARADOR BREVO
        # ─────────────────────────────────────────
        _Sep(self, "TU EMAIL DE DESBLOQUEO").grid(
            row=4, column=0, sticky="ew", padx=PAD, pady=(4, 0))

        # ─────────────────────────────────────────
        # CAMPOS BREVO
        # ─────────────────────────────────────────
        brevo_frm = tk.Frame(self, bg=C["bg"])
        brevo_frm.grid(row=5, column=0, sticky="ew", padx=PAD)
        brevo_frm.columnconfigure(0, weight=1)

        def field(parent, row_idx, label, var, show=None):
            tk.Label(parent, text=label, font=("Courier", 8, "bold"),
                     bg=C["bg"], fg=C["muted2"]
                     ).grid(row=row_idx*2, column=0, sticky="w", pady=(6, 0))
            kw = _entry_style({"show": show} if show else None)
            kw["textvariable"] = var
            e = tk.Entry(parent, **kw)
            e.grid(row=row_idx*2+1, column=0, sticky="ew", ipady=4)
            return e

        self.email_to_var = tk.StringVar(value=self.cfg.get("email_to", ""))
        self._email_lbl = tk.Label(brevo_frm,
            text="TU EMAIL  (solo necesario para 'Sin límite')",
            font=("Courier", 8, "bold"), bg=C["bg"], fg=C["muted2"])
        self._email_lbl.grid(row=0, column=0, sticky="w", pady=(6, 0))
        kw_e = _entry_style()
        kw_e["textvariable"] = self.email_to_var
        self._email_entry = tk.Entry(brevo_frm, **kw_e)
        self._email_entry.grid(row=1, column=0, sticky="ew", ipady=4)

        def _on_dur_change(*_):
            if self.dur_var.get() == "Sin límite (requiere código)":
                self._email_lbl.grid()
                self._email_entry.grid()
                brevo_frm.grid()
                self.rowconfigure(4, minsize=0)
            else:
                self._email_lbl.grid_remove()
                self._email_entry.grid_remove()
                brevo_frm.grid_remove()
        self.dur_var.trace_add("write", _on_dur_change)
        _on_dur_change()  # estado inicial

        # ─────────────────────────────────────────
        # SEPARADOR SITIOS
        # ─────────────────────────────────────────
        _Sep(self, "SITIOS BLOQUEADOS").grid(
            row=6, column=0, sticky="ew", padx=PAD, pady=(6, 0))

        # ─────────────────────────────────────────
        # LISTA DE SITIOS (se expande verticalmente)
        # ─────────────────────────────────────────
        list_frm = tk.Frame(self, bg=C["panel"],
                            highlightbackground=C["border2"], highlightthickness=1)
        list_frm.grid(row=7, column=0, sticky="nsew", padx=PAD, pady=(0, 4))
        list_frm.columnconfigure(0, weight=1)
        list_frm.rowconfigure(0, weight=1)

        sb = tk.Scrollbar(list_frm, bg=C["border"])
        sb.pack(side="right", fill="y")

        self.site_list = tk.Listbox(list_frm,
            bg=C["panel"], fg=C["text"],
            selectbackground=C["accent"], selectforeground=C["bg"],
            font=("Courier", 10), bd=0, highlightthickness=0,
            yscrollcommand=sb.set, activestyle="none", relief="flat")
        self.site_list.pack(fill="both", expand=True, padx=6, pady=4)
        sb.config(command=self.site_list.yview)
        for s in self.cfg["sites"]:
            self.site_list.insert(tk.END, f"  {s}")

        # ─────────────────────────────────────────
        # AÑADIR / QUITAR
        # ─────────────────────────────────────────
        add_frm = tk.Frame(self, bg=C["bg"])
        add_frm.grid(row=8, column=0, sticky="ew", padx=PAD, pady=(0, 6))
        add_frm.columnconfigure(0, weight=1)

        self.new_site_var = tk.StringVar()
        ne = tk.Entry(add_frm, textvariable=self.new_site_var, **_entry_style())
        ne.bind("<Return>", lambda e: self._add_site())
        ne.grid(row=0, column=0, sticky="ew", ipady=4)

        tk.Button(add_frm, text="＋ Añadir",
            font=("Courier", 10, "bold"), bg=C["accent"], fg=C["bg"],
            activebackground=C["accent_dim"], relief="flat", bd=0,
            cursor="hand2", command=self._add_site, padx=10
        ).grid(row=0, column=1, padx=(6, 0), sticky="ew")

        tk.Button(add_frm, text="✕ Quitar",
            font=("Courier", 10, "bold"), bg=C["entry"], fg=C["red"],
            activebackground=C["border"], relief="flat", bd=0,
            cursor="hand2", command=self._remove_site, padx=10
        ).grid(row=0, column=2, padx=(4, 0), sticky="ew")

        # ─────────────────────────────────────────
        # FOOTER
        # ─────────────────────────────────────────
        footer = tk.Frame(self, bg="#0a0f18")
        footer.grid(row=9, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)

        tk.Frame(footer, bg=C["border"], height=1).pack(fill="x")

        tk.Label(footer,
            text="Desbloqueo protegido por código enviado a tu email",
            font=("Courier", 9), bg="#0a0f18", fg=C["muted2"]
        ).pack(pady=(8, 2))

        sudo_txt = "⚡ Sin contraseña admin" if is_sudo_configured() else "🔑 Pide contraseña admin"
        sudo_col = C["accent"] if is_sudo_configured() else C["orange"]
        self.sudo_lbl = tk.Label(footer, text=sudo_txt,
            font=("Courier", 8), bg="#0a0f18", fg=sudo_col)
        self.sudo_lbl.pack()

        tk.Label(footer,
            text="FocusBlock v4  ·  modifica /etc/hosts",
            font=("Courier", 8), bg="#0a0f18", fg=C["border2"]
        ).pack(pady=(2, 10))

    # ── Lógica ────────────────────────────────────────────────────────────────
    def _save_cfg(self):
        self.cfg["email_to"] = self.email_to_var.get().strip()
        save_config(self.cfg)

    def _toggle(self):
        if self.blocking: self._ask_code()
        else: self._activate()

    def _activate(self):
        self._save_cfg()
        dur        = self.dur_var.get()
        email_to   = self.cfg["email_to"]
        sin_limite = (dur == "Sin límite (requiere código)")

        # Duración fija → no necesita email ni código, se desactiva solo
        if not sin_limite:
            self.active_code = None

        # Sin límite → email obligatorio + código
        else:
            if not email_to:
                messagebox.showwarning("Email requerido",
                    "Para 'Sin límite' introduce tu email.\n"
                    "Te enviaremos el código para poder desactivar.")
                return
            code = generate_code()
            try:
                send_brevo_email(email_to, code)
                self.active_code = code
                save_active_code(code)
                messagebox.showinfo("✓ Código enviado",
                    f"Código enviado a {email_to}\nGuárdalo para poder desactivar.")
            except Exception as ex:
                messagebox.showerror("Error al enviar",
                    f"No se pudo enviar el código:\n{ex}\n\n"
                    "Sin código no puedes usar 'Sin límite'.\n"
                    "Elige una duración fija o revisa tu conexión.")
                return

        self.main_btn.config(state="disabled", text="Activando…")
        self.update()
        if enable_block(self.cfg["sites"]):
            self.blocking = True
            self._start_timer()
        else:
            messagebox.showerror("Error",
                "No se pudo activar.\nIntroduce tu contraseña de administrador.")
        self.main_btn.config(state="normal")
        self._refresh_status()

    def _ask_code(self):
        if not self.active_code:
            self._deactivate(); return

        win = tk.Toplevel(self)
        win.title("Código de desbloqueo")
        win.minsize(400, 260)
        win.configure(bg=C["bg"])
        win.grab_set()
        win.update_idletasks()
        win.geometry(f"460x300+{self.winfo_x()+(self.winfo_width()-460)//2}"
                     f"+{self.winfo_y()+(self.winfo_height()-300)//2}")
        win.columnconfigure(0, weight=1)

        tk.Label(win, text="🔐  CÓDIGO DE DESBLOQUEO",
                 font=("Courier", 14, "bold"), bg=C["bg"], fg=C["accent"]
                 ).grid(row=0, column=0, pady=(28, 4))
        tk.Label(win, text=f"Introduce el código enviado a:\n{self.cfg['email_to']}",
                 font=("Courier", 10), bg=C["bg"], fg=C["muted2"], justify="center"
                 ).grid(row=1, column=0, pady=(0, 14))

        code_var = tk.StringVar()
        e = tk.Entry(win, textvariable=code_var, font=("Courier", 24, "bold"),
                     bg=C["entry"], fg=C["accent"], insertbackground=C["accent"],
                     bd=0, relief="flat", justify="center",
                     highlightthickness=1, highlightbackground=C["border"],
                     highlightcolor=C["accent"])
        e.grid(row=2, column=0, sticky="ew", padx=44, ipady=12)
        e.focus()

        msg = tk.Label(win, text="", font=("Courier", 9), bg=C["bg"], fg=C["red"])
        msg.grid(row=3, column=0, pady=4)

        def check():
            if code_var.get().strip().upper() == self.active_code:
                win.destroy(); self._deactivate()
            else:
                msg.config(text="❌  Código incorrecto. Inténtalo de nuevo.", fg=C["red"])
                code_var.set("")

        def resend():
            try:
                nc = generate_code()
                send_brevo_email(self.cfg["email_to"], nc)
                self.active_code = nc
                save_active_code(nc)
                msg.config(text="✓  Nuevo código enviado.", fg=C["accent"])
            except Exception as ex:
                msg.config(text=f"Error: {ex}", fg=C["red"])

        e.bind("<Return>", lambda ev: check())
        bf = tk.Frame(win, bg=C["bg"])
        bf.grid(row=4, column=0, pady=6)
        tk.Button(bf, text="Verificar", font=("Courier", 12, "bold"),
                  bg=C["accent"], fg=C["bg"], activebackground=C["accent_dim"],
                  relief="flat", bd=0, cursor="hand2", padx=20, pady=8,
                  command=check).pack(side="left", padx=8)
        tk.Button(bf, text="Reenviar código", font=("Courier", 10),
                  bg=C["entry"], fg=C["muted2"], activebackground=C["border"],
                  relief="flat", bd=0, cursor="hand2", padx=14, pady=8,
                  command=resend).pack(side="left", padx=4)

    def _deactivate(self):
        self.main_btn.config(state="disabled", text="Desactivando…")
        self.update()
        if disable_block():
            self.blocking    = False
            self.timer_run   = False
            self.active_code = None
            clear_active_code()
        else:
            messagebox.showerror("Error", "No se pudo desactivar.")
        self.main_btn.config(state="normal")
        self._refresh_status()

    def _refresh_status(self):
        if self.blocking:
            self._status_bar.config(bg=C["accent"])
            self._dot_canvas.itemconfig(self._dot, fill=C["accent"])
            self.slbl.config(text="MODO FOCO ACTIVO", fg=C["accent"])
            # Si hay timer activo (duración fija) → botón bloqueado
            if self.timer_run:
                self.main_btn.config(
                    text="⏳  ESPERANDO FIN DEL TIEMPO",
                    bg=C["muted"], activebackground=C["muted"],
                    fg=C["bg"], state="disabled")
            else:
                self.main_btn.config(
                    text="■  DESACTIVAR BLOQUEO",
                    bg=C["red"], activebackground=C["red_dim"],
                    fg=C["white"], state="normal")
        else:
            self._status_bar.config(bg=C["muted"])
            self._dot_canvas.itemconfig(self._dot, fill=C["muted"])
            self.slbl.config(text="INACTIVO", fg=C["muted"])
            self.tlbl.config(text="Activa el modo foco para comenzar", fg=C["muted"])
            self.main_btn.config(text="▶  ACTIVAR MODO FOCO",
                                 bg=C["accent"], activebackground=C["accent_dim"],
                                 fg=C["bg"], state="normal")

    def _start_timer(self):
        dur_map = {"25 min – Pomodoro": 1500, "45 min": 2700,
                   "1 hora": 3600, "2 horas": 7200, "4 horas": 14400}
        secs = dur_map.get(self.dur_var.get(), 0)
        if secs == 0:
            # Sin límite: botón habilitado (se desactiva con código)
            self.main_btn.config(
                text="■  DESACTIVAR BLOQUEO",
                bg=C["red"], activebackground=C["red_dim"],
                fg=C["white"], state="normal")
            self.tlbl.config(text="Duración: sin límite  —  solo desactivable por código", fg=C["muted"])
            return
        self.timer_secs = secs
        self.timer_run  = True
        # Deshabilitar botón inmediatamente
        self.main_btn.config(
            text="⏳  ESPERANDO FIN DEL TIEMPO",
            bg=C["muted"], activebackground=C["muted"],
            fg=C["bg"], state="disabled")
        def run():
            while self.timer_run and self.timer_secs > 0:
                m, s = divmod(self.timer_secs, 60)
                self.tlbl.config(text=f"Tiempo restante: {m:02d}:{s:02d}", fg=C["accent"])
                time.sleep(1); self.timer_secs -= 1
            if self.timer_run:
                self.timer_run = False
                self.tlbl.config(text="¡Tiempo completado! Desactivando...")
                self.after(0, self._deactivate)
        threading.Thread(target=run, daemon=True).start()

    def _add_site(self):
        if self.blocking:
            messagebox.showwarning("🔒 Bloqueado",
                "No puedes modificar la lista mientras el bloqueo está activo.")
            return
        site = self.new_site_var.get().strip().lower()
        for p in ["https://", "http://", "www."]: site = site.replace(p, "")
        site = site.rstrip("/")
        if not site: return
        for s in [site, f"www.{site}"]:
            if s not in self.cfg["sites"]:
                self.cfg["sites"].append(s)
                self.site_list.insert(tk.END, f"  {s}")
        save_config(self.cfg); self.new_site_var.set("")

    def _remove_site(self):
        if self.blocking:
            messagebox.showwarning("🔒 Bloqueado",
                "No puedes modificar la lista mientras el bloqueo está activo.")
            return
        sel = self.site_list.curselection()
        if not sel:
            messagebox.showinfo("Selecciona", "Haz clic en un sitio primero."); return
        site = self.site_list.get(sel[0]).strip()
        self.site_list.delete(sel[0])
        if site in self.cfg["sites"]: self.cfg["sites"].remove(site)
        save_config(self.cfg)

    def on_close(self):
        if self.blocking:
            messagebox.showwarning("🔒 Bloqueado",
                "No puedes cerrar FocusBlock mientras el bloqueo está activo.\n\n"
                "Desactívalo primero introduciendo el código.")
            return
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.bind_all("<Command-q>", lambda e: app.on_close())
    app.bind_all("<Command-w>", lambda e: app.on_close())
    app.createcommand("::tk::mac::Quit", app.on_close)
    app.mainloop()
