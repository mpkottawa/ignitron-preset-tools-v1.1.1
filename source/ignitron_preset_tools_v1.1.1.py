#!/usr/bin/env python3
"""Ignitron Preset Tools v1.1.1 - modern desktop UI."""

import contextlib
import importlib.util
import io
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


APP_NAME = "Ignitron Preset Tools"
APP_VERSION = "1.1.1"

BG = "#0d0e12"
SURFACE = "#15171d"
CARD = "#1c1f27"
CARD_ALT = "#232731"
BORDER = "#343946"
TEXT = "#f4f1ea"
MUTED = "#9ba1ad"
GOLD = "#f5a623"
GOLD_HOVER = "#ffbd4a"
ORANGE = "#e66a1f"
GREEN = "#37c878"
RED = "#e35050"


def app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_path(name):
    roots = [app_dir(), app_dir().parent, Path(getattr(sys, "_MEIPASS", app_dir()))]
    for root in roots:
        candidate = root / name
        if candidate.exists():
            return candidate
    return roots[0] / name


def settings_file():
    return app_dir() / "data" / "settings.json"


def load_saved_project_dir():
    try:
        data = json.loads(settings_file().read_text(encoding="utf-8"))
        folder = Path(data.get("ignitron_folder", ""))
        if (folder / "data").exists():
            return folder
    except Exception:
        pass
    return default_project_dir()


def save_project_dir(folder):
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ignitron_folder": str(folder)}, indent=2), encoding="utf-8")


def open_folder(path):
    path = str(Path(path).resolve())
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def default_project_dir():
    candidates = [
        Path(r"T:\ignitron"),
        app_dir().parent,
        app_dir(),
    ]
    for candidate in candidates:
        if (candidate / "platformio.ini").exists() and (candidate / "data").exists():
            return candidate
    return candidates[0]


def default_platformio():
    candidates = [
        Path.home() / ".platformio" / "penv" / "Scripts" / "platformio.exe",
        Path.home() / ".platformio" / "penv" / "Scripts" / "pio.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "platformio"


def parse_platformio_envs(platformio_ini):
    if not platformio_ini.exists():
        return ["esp32dev"]
    envs = []
    for line in platformio_ini.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"\[env:([^\]]+)\]", line.strip())
        if match:
            envs.append(match.group(1))
    return envs or ["esp32dev"]


def parse_platformio_upload_port(platformio_ini, env_name):
    if not platformio_ini.exists():
        return ""
    current_section = ""
    inherited_port = ""
    env_port = ""
    for raw_line in platformio_ini.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1]
            continue
        if "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        if key != "upload_port":
            continue
        if current_section == "env":
            inherited_port = value
        elif current_section == f"env:{env_name}":
            env_port = value
    return env_port or inherited_port


def parse_platformio_env_value(platformio_ini, env_name, option_name, fallback=""):
    if not platformio_ini.exists():
        return fallback
    current_section = ""
    inherited_value = ""
    env_value = ""
    for raw_line in platformio_ini.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1]
            continue
        if "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        if key != option_name:
            continue
        if current_section == "env":
            inherited_value = value
        elif current_section == f"env:{env_name}":
            env_value = value
    return env_value or inherited_value or fallback


def preset_list_missing_files(data_dir):
    preset_list = data_dir / "PresetList.txt"
    if not preset_list.exists():
        return ["PresetList.txt is missing"]
    missing = []
    for raw_line in preset_list.read_text(encoding="utf-8", errors="replace").splitlines():
        name = raw_line.strip()
        if not name or name.startswith("--"):
            continue
        if not (data_dir / name).exists():
            missing.append(name)
    return missing


def generate_preset_chart(data_dir):
    def write_simple_pdf(output_path, rows):
        def pdf_escape(value):
            return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

        lines = ["BT", "/F1 18 Tf", "50 750 Td", "(Ignitron Preset Chart) Tj", "/F1 8 Tf", "0 -24 Td"]
        for row in rows:
            text = "   |   ".join(row)
            lines.append(f"({pdf_escape(text)}) Tj")
            lines.append("0 -14 Td")
        lines.append("ET")
        stream = "\n".join(lines).encode("latin-1", errors="replace")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        ]
        content = bytearray(b"%PDF-1.4\n")
        offsets = []
        for index, obj in enumerate(objects, start=1):
            offsets.append(len(content))
            content.extend(f"{index} 0 obj\n".encode("ascii"))
            content.extend(obj)
            content.extend(b"\nendobj\n")
        xref = len(content)
        content.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
        for offset in offsets:
            content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        content.extend(
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
        )
        output_path.write_bytes(content)

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        colors = letter = getSampleStyleSheet = Paragraph = SimpleDocTemplate = Spacer = Table = TableStyle = None

    data_dir = Path(data_dir)
    preset_list = data_dir / "PresetList.txt"
    output_path = data_dir / "PresetList.pdf"
    if not preset_list.exists():
        raise FileNotFoundError(f"PresetList.txt was not found at {preset_list}")

    banks = []
    current_bank = None
    for raw_line in preset_list.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("-- Bank"):
            current_bank = [line.replace("--", "").strip(), []]
            banks.append(current_bank)
            continue
        if current_bank is None:
            current_bank = ["Bank 1", []]
            banks.append(current_bank)
        preset_name = Path(line).stem.replace("_", " ")
        current_bank[1].append(preset_name)

    table_data = [["Bank", "Slot 1", "Slot 2", "Slot 3", "Slot 4"]]
    for bank_name, presets in banks:
        row = list(presets[:4])
        while len(row) < 4:
            row.append("-")
        table_data.append([bank_name] + row)

    if SimpleDocTemplate is None:
        write_simple_pdf(output_path, table_data)
        return output_path

    doc = SimpleDocTemplate(str(output_path), pagesize=letter, rightMargin=24, leftMargin=24)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("<font color='#f5a623'><b>Ignitron Preset Chart</b></font>", styles["Title"]),
        Spacer(1, 12),
    ]
    table = Table(table_data, colWidths=[64, 112, 112, 112, 112], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.black),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#f5a623")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f7f1e5"), colors.HexColor("#ead7b7")]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#6d5d42")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)
    doc.build(elements)
    return output_path


class StdoutQueue(io.TextIOBase):
    def __init__(self, callback):
        self.callback = callback

    def write(self, value):
        if value:
            self.callback(value)
        return len(value)

    def flush(self):
        return None


class IgnitronApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.configure(bg=BG)
        self.geometry("1320x820")
        self.minsize(1060, 680)
        self.current_page = None
        self.pages = {}
        self.project_dir_var = tk.StringVar(value=str(load_saved_project_dir()))
        self._configure_window()
        self._configure_styles()
        self._build_shell()
        self.show_page("home")
        self.after_idle(self._maximize_window)
        self.bind("<F11>", self._toggle_fullscreen)
        self.bind("<Escape>", self._exit_fullscreen)

    def _configure_window(self):
        icon = resource_path("IPT.ico")
        if icon.exists():
            try:
                self.iconbitmap(default=str(icon))
            except tk.TclError:
                pass

    def _maximize_window(self):
        try:
            self.state("zoomed")
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                self.geometry(f"{screen_width}x{screen_height}+0+0")

    def _toggle_fullscreen(self, _event=None):
        current = bool(self.attributes("-fullscreen"))
        self.attributes("-fullscreen", not current)

    def _exit_fullscreen(self, _event=None):
        if bool(self.attributes("-fullscreen")):
            self.attributes("-fullscreen", False)
            self.after_idle(self._maximize_window)

    def _configure_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=SURFACE)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 24), foreground=TEXT)
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground=MUTED)
        style.configure("Section.TLabel", font=("Segoe UI Semibold", 14), foreground=TEXT)
        style.configure("Gold.TButton", background=GOLD, foreground="#16120b", borderwidth=0,
                        padding=(18, 10), font=("Segoe UI Semibold", 10))
        style.map("Gold.TButton", background=[("active", GOLD_HOVER), ("pressed", ORANGE)])
        style.configure("Dark.TButton", background=CARD_ALT, foreground=TEXT, borderwidth=1,
                        padding=(14, 9), font=("Segoe UI Semibold", 9))
        style.map("Dark.TButton", background=[("active", BORDER)])
        style.configure("Danger.TButton", background="#402326", foreground="#ffb4b4", borderwidth=0,
                        padding=(10, 7))
        style.map("Danger.TButton", background=[("active", "#5b292d")])
        style.configure("TEntry", fieldbackground=CARD_ALT, foreground=TEXT, insertcolor=TEXT,
                        bordercolor=BORDER, padding=9)
        style.configure("TCombobox", fieldbackground=CARD_ALT, background=CARD_ALT,
                        foreground=TEXT, arrowcolor=GOLD, padding=7)
        style.configure("Vertical.TScrollbar", background=CARD_ALT, troughcolor=SURFACE,
                        bordercolor=SURFACE, arrowcolor=MUTED)

    def _build_shell(self):
        sidebar = tk.Frame(self, bg="#111319", width=224)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand = tk.Frame(sidebar, bg="#111319")
        brand.pack(fill="x", padx=20, pady=(24, 28))
        tk.Label(brand, text="IGNITRON", bg="#111319", fg=GOLD,
                 font=("Segoe UI Semibold", 20)).pack(anchor="w")
        tk.Label(brand, text="PRESET TOOLS", bg="#111319", fg=TEXT,
                 font=("Segoe UI Semibold", 11)).pack(anchor="w")
        tk.Label(brand, text=f"VERSION {APP_VERSION}", bg="#111319", fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(5, 0))

        self.nav_buttons = {}
        for key, label, glyph in (
            ("home", "Dashboard", "HOME"),
            ("builder", "Preset Builder", "01"),
            ("firmware", "Firmware", "02"),
            ("uploader", "Upload FS", "03"),
            ("puller", "Pedal Puller", "04"),
            ("capture", "Spark Capture", "05"),
            ("library", "Library Tools", "06"),
            ("reference", "Reference", "07"),
        ):
            button = tk.Button(sidebar, text=f"  {glyph}   {label}", anchor="w",
                               bg="#111319", fg=MUTED, activebackground=CARD,
                               activeforeground=TEXT, relief="flat", bd=0,
                               font=("Segoe UI Semibold", 10), padx=15, pady=13,
                               command=lambda name=key: self.show_page(name))
            button.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = button

        tk.Frame(sidebar, bg=BORDER, height=1).pack(side="bottom", fill="x", padx=18, pady=(0, 15))
        tk.Label(sidebar, text="Tone organized. Presets protected.", bg="#111319", fg=MUTED,
                 wraplength=170, justify="left", font=("Segoe UI", 8)).pack(side="bottom", anchor="w", padx=20, pady=18)

        main = tk.Frame(self, bg=BG)
        main.pack(side="left", fill="both", expand=True)
        self.page_host = tk.Frame(main, bg=BG)
        self.page_host.pack(fill="both", expand=True)
        self.status_var = tk.StringVar(value="Ready")
        status = tk.Frame(main, bg="#111319", height=34)
        status.pack(fill="x", side="bottom")
        tk.Label(status, textvariable=self.status_var, bg="#111319", fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=18, pady=8)

    def set_status(self, text):
        self.status_var.set(text)

    @property
    def project_dir(self):
        return Path(self.project_dir_var.get()).expanduser().resolve()

    @property
    def data_dir(self):
        return self.project_dir / "data"

    def set_project_dir(self, folder):
        self.project_dir_var.set(str(Path(folder).expanduser().resolve()))
        save_project_dir(self.project_dir)
        for page in self.pages.values():
            refresh = getattr(page, "on_project_changed", None)
            if refresh:
                refresh()
        self.set_status(f"Ignitron folder set to {self.project_dir}")

    def show_page(self, name):
        if self.current_page:
            self.current_page.pack_forget()
        if name not in self.pages:
            page_class = {
                "home": HomePage,
                "builder": BuilderPage,
                "uploader": FilesystemUploaderPage,
                "firmware": FirmwareUploadPage,
                "puller": PullerPage,
                "capture": CapturePage,
                "library": LibraryToolsPage,
                "reference": ReferencePage,
            }[name]
            self.pages[name] = page_class(self.page_host, self)
        self.current_page = self.pages[name]
        self.current_page.pack(fill="both", expand=True)
        for key, button in self.nav_buttons.items():
            button.configure(bg=CARD if key == name else "#111319", fg=TEXT if key == name else MUTED)


class Page(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app

    def heading(self, title, subtitle, action=None, action_text=None):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=34, pady=(28, 20))
        copy = tk.Frame(header, bg=BG)
        copy.pack(side="left")
        ttk.Label(copy, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(copy, text=subtitle, style="Subtitle.TLabel").pack(anchor="w", pady=(5, 0))
        if action:
            ttk.Button(header, text=action_text, style="Gold.TButton", command=action).pack(side="right")
        return header


class HomePage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")

        self.content = tk.Frame(self.canvas, bg=BG)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(self.canvas_window, width=event.width))
        self.canvas.bind("<MouseWheel>", self.mousewheel)
        self.content.bind("<MouseWheel>", self.mousewheel)

        header = tk.Frame(self.content, bg=BG)
        header.pack(fill="x", padx=34, pady=(28, 18))
        ttk.Label(header, text="Your tone workspace", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Build banks, protect pedal presets, and capture tones from the Spark app.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(5, 0))

        project = tk.Frame(self.content, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        project.pack(fill="x", padx=34, pady=(0, 14), ipady=8)
        tk.Label(project, text="IGNITRON FOLDER", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left", padx=(18, 10))
        ttk.Entry(project, textvariable=app.project_dir_var).pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(project, text="Browse", style="Dark.TButton",
                   command=self.choose_ignitron_folder).pack(side="left", padx=(0, 10))
        ttk.Button(project, text="Load data", style="Gold.TButton",
                   command=self.load_project_data).pack(side="left", padx=(0, 18))
        self.project_status = tk.StringVar()
        tk.Label(self.content, textvariable=self.project_status, bg=BG, fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=34, pady=(0, 12))
        self.refresh_project_status()

        hero = tk.Frame(self.content, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        hero.pack(fill="x", padx=34, pady=(0, 18), ipady=16)
        hero_copy = tk.Frame(hero, bg=SURFACE)
        hero_copy.pack(side="left", fill="both", expand=True, padx=28, pady=10)
        tk.Label(hero_copy, text="IGNITRON", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 28)).pack(anchor="w")
        tk.Label(hero_copy, text="Put every preset exactly where your foot expects it.", bg=SURFACE,
                 fg=TEXT, font=("Segoe UI Semibold", 16)).pack(anchor="w", pady=(4, 8))
        tk.Label(hero_copy, text="A cleaner workflow for arranging, backing up, and capturing your guitar tones.",
                 bg=SURFACE, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w")
        tk.Label(hero, text="IPT", bg=GOLD, fg="#17120a", width=6, height=3,
                 font=("Segoe UI Black", 18)).pack(side="right", padx=30)

        grid = tk.Frame(self.content, bg=BG)
        grid.pack(fill="both", expand=True, padx=34, pady=(0, 34))
        for col in range(2):
            grid.grid_columnconfigure(col, weight=1, uniform="tools")
        cards = (
            ("BUILD", "Preset Bank Builder", "Search your library and arrange four-slot banks with drag and double-click controls.", "builder"),
            ("FIRMWARE", "Firmware Upload", "Build and upload firmware with port, speed, clean build, and filesystem options.", "firmware"),
            ("UPLOAD", "Filesystem Uploader", "Build and upload the data folder to Ignitron without reflashing firmware.", "uploader"),
            ("BACK UP", "Pedal Preset Puller", "Choose a connected Ignitron and save its active bank or full preset library.", "puller"),
            ("CAPTURE", "Spark App Capture", "Listen for presets sent by the Spark app and save clean Ignitron JSON files.", "capture"),
            ("MANAGE", "Ignitron Library Tools", "Scan and manage your main preset library separately from the pedal data folder.", "library"),
            ("REFERENCE", "ESP32 Reference", "Interactive ESP32 Dev pinout and Ignitron wiring notes.", "reference"),
        )
        for index, (eyebrow, title, body, page) in enumerate(cards):
            row, col = divmod(index, 2)
            card = tk.Frame(grid, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
            card.grid(row=row, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 8 if col == 0 else 0),
                      pady=(0 if row == 0 else 8, 8 if row == 0 else 0))
            tk.Label(card, text=eyebrow, bg=CARD, fg=GOLD,
                     font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=22, pady=(20, 8))
            tk.Label(card, text=title, bg=CARD, fg=TEXT, wraplength=260, justify="left",
                     font=("Segoe UI Semibold", 15)).pack(anchor="w", padx=22)
            tk.Label(card, text=body, bg=CARD, fg=MUTED, wraplength=270, justify="left",
                     font=("Segoe UI", 9), pady=10).pack(anchor="w", padx=22)
            ttk.Button(card, text="Open tool", style="Dark.TButton",
                       command=lambda p=page: app.show_page(p)).pack(anchor="w", padx=22, pady=(6, 20))

        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)
        self._bind_mousewheel_tree(self.content)

    def mousewheel(self, event):
        if not self.winfo_ismapped():
            return None

        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is self.canvas or widget is self.content:
                delta = -1 * int(event.delta / 120) if event.delta else 0
                if delta:
                    self.canvas.yview_scroll(delta, "units")
                return "break"
            widget = getattr(widget, "master", None)
        return None

    def _bind_mousewheel_tree(self, widget):
        widget.bind("<MouseWheel>", self.mousewheel)
        for child in widget.winfo_children():
            self._bind_mousewheel_tree(child)

    def choose_ignitron_folder(self):
        folder = filedialog.askdirectory(
            title="Select main Ignitron project folder",
            initialdir=str(self.app.project_dir if self.app.project_dir.exists() else Path.home()),
        )
        if folder:
            self.app.set_project_dir(folder)
            self.refresh_project_status()

    def load_project_data(self):
        self.app.set_project_dir(self.app.project_dir)
        self.refresh_project_status()
        self.app.show_page("builder")
        builder = self.app.pages.get("builder")
        if isinstance(builder, BuilderPage):
            builder.load_project_data()

    def refresh_project_status(self):
        data_dir = self.app.data_dir
        if data_dir.exists():
            count = len(list(data_dir.glob("*.json")))
            self.project_status.set(f"Using data folder: {data_dir}  |  {count} JSON preset file(s)")
        else:
            self.project_status.set(f"Data folder not found yet: {data_dir}")

    def on_project_changed(self):
        self.refresh_project_status()


class BuilderPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.library_folder = None
        self.output_folder = self.app.data_dir
        self.presets = []
        self.filtered = []
        self.bank_count = 30
        self.bank_count_var = tk.IntVar(value=self.bank_count)
        self.slots = {(b, s): None for b in range(1, self.bank_count + 1) for s in range(1, 5)}
        self.slot_widgets = {}
        self.dragging = None
        self.drag_ghost = None
        self.drag_target = None
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_library())
        self.library_count = tk.StringVar(value="Load Ignitron data to begin")
        self.usage_var = tk.StringVar(value=f"0 / {self.bank_count * 4} slots filled")
        self.heading("Preset Bank Builder", "Uses the data folder inside the selected Ignitron project.",
                     self.load_project_data, "Load Ignitron data")
        self._build()
        self.load_project_data(show_message=False)

    def _build(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=34, pady=(0, 26))
        body.grid_columnconfigure(0, weight=0, minsize=310)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        library = tk.Frame(body, bg=SURFACE, width=310, highlightbackground=BORDER, highlightthickness=1)
        library.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        library.grid_propagate(False)
        tk.Label(library, text="PRESET LIBRARY", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=18, pady=(18, 4))
        tk.Label(library, textvariable=self.library_count, bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=18, pady=(0, 12))
        ttk.Entry(library, textvariable=self.search_var).pack(fill="x", padx=18, pady=(0, 12))

        list_wrap = tk.Frame(library, bg=SURFACE)
        list_wrap.pack(fill="both", expand=True, padx=18)
        scroll = ttk.Scrollbar(list_wrap, orient="vertical")
        self.preset_list = tk.Listbox(list_wrap, bg=CARD, fg=TEXT, selectbackground=ORANGE,
                                      selectforeground="white", relief="flat", bd=0,
                                      highlightthickness=1, highlightbackground=BORDER,
                                      font=("Segoe UI", 9), activestyle="none", yscrollcommand=scroll.set)
        scroll.configure(command=self.preset_list.yview)
        self.preset_list.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.preset_list.bind("<Double-Button-1>", self.add_selected)
        self.preset_list.bind("<ButtonPress-1>", self.start_drag)
        self.preset_list.bind("<B1-Motion>", self.drag_motion)
        self.preset_list.bind("<ButtonRelease-1>", self.drop_drag)

        tk.Label(library, text="Double-click or drag a preset into a slot.", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=18, pady=12)
        actions = tk.Frame(library, bg=SURFACE)
        actions.pack(fill="x", padx=18, pady=(0, 18))
        ttk.Button(actions, text="Load Ignitron data folder", style="Gold.TButton",
                   command=self.load_project_data).pack(fill="x", pady=(0, 5))
        ttk.Button(actions, text="Choose other library", style="Dark.TButton",
                   command=self.choose_library_folder).pack(fill="x", pady=3)
        ttk.Button(actions, text="Fill empty", style="Dark.TButton", command=self.fill_empty).pack(fill="x", pady=3)
        ttk.Button(actions, text="Clear all", style="Dark.TButton", command=self.clear_all).pack(fill="x", pady=3)

        workspace = tk.Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        workspace.grid(row=0, column=1, sticky="nsew")
        toolbar = tk.Frame(workspace, bg=SURFACE)
        toolbar.pack(fill="x", padx=20, pady=16)
        tk.Label(toolbar, text="BANK LAYOUT", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left")
        tk.Label(toolbar, textvariable=self.usage_var, bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=14)
        bank_selector = tk.Frame(toolbar, bg=SURFACE)
        bank_selector.pack(side="left", padx=(8, 0))
        tk.Label(bank_selector, text="BANKS", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI Semibold", 8)).pack(side="left", padx=(0, 7))
        self.bank_spinbox = ttk.Spinbox(
            bank_selector, from_=1, to=30, width=4, justify="center",
            textvariable=self.bank_count_var, command=self.apply_bank_count
        )
        self.bank_spinbox.pack(side="left")
        self.bank_spinbox.bind("<Return>", self.apply_bank_count)
        self.bank_spinbox.bind("<FocusOut>", self.apply_bank_count)
        ttk.Button(toolbar, text="Export + select port", style="Gold.TButton",
                   command=self.export_and_upload_filesystem).pack(side="right")
        ttk.Button(toolbar, text="Export files", style="Dark.TButton", command=self.export).pack(side="right", padx=8)
        ttk.Button(toolbar, text="Add bank", style="Dark.TButton", command=self.add_bank).pack(side="right", padx=8)

        canvas_wrap = tk.Frame(workspace, bg=SURFACE)
        canvas_wrap.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.canvas = tk.Canvas(canvas_wrap, bg=SURFACE, highlightthickness=0)
        scroll = ttk.Scrollbar(canvas_wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.bank_host = tk.Frame(self.canvas, bg=SURFACE)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.bank_host, anchor="nw")
        self.bank_host.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.canvas_window, width=e.width))
        self.canvas.bind_all("<MouseWheel>", self.mousewheel)
        self.render_banks()

    def choose_library_folder(self):
        folder = filedialog.askdirectory(title="Select your main preset library")
        if not folder:
            return
        self.load_library_folder(Path(folder))

    def load_project_data(self, show_message=True):
        self.output_folder = self.app.data_dir
        if not self.output_folder.exists():
            self.presets = []
            self.filtered = []
            self.library_count.set(f"Data folder not found: {self.output_folder}")
            self.refresh_library()
            self.app.set_status(f"Data folder not found: {self.output_folder}")
            if show_message:
                messagebox.showerror("Data folder not found", f"No data folder exists at:\n{self.output_folder}")
            return False
        self.load_library_folder(self.output_folder)
        self.app.set_status(f"Using Ignitron data folder: {self.output_folder}")
        return True

    def on_project_changed(self):
        self.load_project_data(show_message=False)

    def load_library_folder(self, folder):
        self.library_folder = Path(folder)
        self.presets = []
        for path in sorted(self.library_folder.rglob("*.json"), key=lambda p: p.name.lower()):
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                data = {}
            self.presets.append({
                "filename": path.name,
                "name": str(data.get("Name", path.stem)),
                "uuid": str(data.get("UUID", "UNKNOWN")).upper(),
                "description": str(data.get("Description", "")),
                "bpm": data.get("BPM", ""),
                "version": str(data.get("Version", "")),
                "path": path,
                "data": data,
            })
        self.library_count.set(f"{len(self.presets)} presets  |  {self.library_folder.name}")
        self.refresh_library()
        self.app.set_status(f"Loaded {len(self.presets)} presets from main library: {self.library_folder}")

    def choose_output_folder(self):
        folder = filedialog.askdirectory(title="Select Ignitron data folder for PresetList files")
        if not folder:
            return
        self.output_folder = Path(folder)
        json_files = list(self.output_folder.rglob("*.json"))
        if json_files:
            self.load_library_folder(self.output_folder)
            self.app.set_status(
                f"Loaded {len(self.presets)} presets and set data output folder: {self.output_folder}")
        else:
            self.app.set_status(
                f"Data output folder selected, but no JSON presets were found: {self.output_folder}")

    def refresh_library(self):
        query = self.search_var.get().strip().lower()
        self.filtered = [p for p in self.presets if query in p["name"].lower() or query in p["filename"].lower()]
        self.preset_list.delete(0, "end")
        used = {value for value in self.slots.values() if value}
        for index, preset in enumerate(self.filtered):
            self.preset_list.insert("end", preset["name"])
            self.preset_list.itemconfig(index, fg=GREEN if preset["filename"] in used else TEXT,
                                        bg=CARD_ALT if index % 2 else CARD)

    def render_banks(self):
        for child in self.bank_host.winfo_children():
            child.destroy()
        self.slot_widgets.clear()
        for bank in range(1, self.bank_count + 1):
            card = tk.Frame(self.bank_host, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
            card.pack(fill="x", padx=8, pady=7)
            header = tk.Frame(card, bg=CARD)
            header.pack(fill="x", padx=16, pady=(13, 5))
            tk.Label(header, text=f"BANK {bank:02d}", bg=CARD, fg=TEXT,
                     font=("Segoe UI Semibold", 12)).pack(side="left")
            ttk.Button(header, text="Remove", style="Danger.TButton",
                       command=lambda b=bank: self.remove_bank(b)).pack(side="right")
            slots = tk.Frame(card, bg=CARD)
            slots.pack(fill="x", padx=10, pady=(0, 13))
            for column in range(4):
                slots.grid_columnconfigure(column, weight=1, uniform="slot")
            for slot in range(1, 5):
                value = self.slots.get((bank, slot))
                text = self.display_name(value) if value else f"SLOT {slot}\nDrop preset here"
                widget = tk.Label(slots, text=text, bg="#24352e" if value else CARD_ALT,
                                  fg=TEXT if value else MUTED, height=4, justify="center",
                                  wraplength=150, relief="flat", bd=0,
                                  highlightthickness=1,
                                  highlightbackground=GREEN if value else BORDER,
                                  font=("Segoe UI Semibold", 9) if value else ("Segoe UI", 8))
                widget.grid(row=0, column=slot - 1, sticky="nsew", padx=5, pady=5)
                widget.bank, widget.slot = bank, slot
                widget.bind("<Button-3>", self.clear_slot)
                widget.bind("<Double-Button-1>", self.clear_slot)
                widget.bind("<Enter>", lambda e: e.widget.configure(highlightbackground=GOLD))
                widget.bind("<Leave>", lambda e, filled=bool(value): e.widget.configure(
                    highlightbackground=GREEN if filled else BORDER))
                self.slot_widgets[(bank, slot)] = widget
        self.update_usage()

    def display_name(self, filename):
        preset = next((p for p in self.presets if p["filename"] == filename), None)
        return preset["name"] if preset else (Path(filename).stem if filename else "")

    def selected_filename(self):
        selection = self.preset_list.curselection()
        if not selection or selection[0] >= len(self.filtered):
            return None
        return self.filtered[selection[0]]["filename"]

    def add_selected(self, _event=None):
        filename = self.selected_filename()
        if not filename:
            return
        for key, value in self.slots.items():
            if value is None:
                self.slots[key] = filename
                self.render_banks()
                self.refresh_library()
                return
        self.app.set_status("Every bank slot is already filled")

    def add_filename_to_next_slot(self, filename):
        for key, value in self.slots.items():
            if value is None:
                self.slots[key] = filename
                self.render_banks()
                self.refresh_library()
                self.app.set_status(f"Added {self.display_name(filename)} to Bank {key[0]:02d}, Slot {key[1]}")
                return True
        self.app.set_status("Every bank slot is already filled")
        return False

    def start_drag(self, event):
        index = self.preset_list.nearest(event.y)
        if 0 <= index < len(self.filtered):
            self.preset_list.selection_clear(0, "end")
            self.preset_list.selection_set(index)
            self.dragging = self.filtered[index]["filename"]
            self.drag_target = None

    def drag_motion(self, event):
        if not self.dragging:
            return
        if self.drag_ghost is None:
            self.drag_ghost = tk.Toplevel(self)
            self.drag_ghost.overrideredirect(True)
            try:
                self.drag_ghost.attributes("-topmost", True)
                self.drag_ghost.attributes("-alpha", 0.94)
            except tk.TclError:
                pass
            tk.Label(
                self.drag_ghost,
                text=self.display_name(self.dragging),
                bg=GOLD,
                fg="#17120a",
                padx=14,
                pady=8,
                relief="flat",
                font=("Segoe UI Semibold", 9),
            ).pack()

        x_root = event.x_root
        y_root = event.y_root
        self.drag_ghost.geometry(f"+{x_root + 16}+{y_root + 16}")
        self._set_drag_target(self._slot_at_pointer(x_root, y_root))

    def drop_drag(self, event):
        if not self.dragging:
            return
        target = self._slot_at_pointer(event.x_root, event.y_root)
        if target is not None:
            self.slots[(target.bank, target.slot)] = self.dragging
            self.render_banks()
            self.refresh_library()
            self.app.set_status(
                f"Dropped {self.display_name(self.dragging)} into Bank {target.bank:02d}, Slot {target.slot}")
        else:
            self._restore_slot_highlight(self.drag_target)
        self.dragging = None
        self.drag_target = None
        if self.drag_ghost is not None:
            self.drag_ghost.destroy()
            self.drag_ghost = None

    def _slot_at_pointer(self, x_root, y_root):
        widget = self.winfo_containing(x_root, y_root)
        while widget is not None and widget is not self:
            if hasattr(widget, "bank") and hasattr(widget, "slot"):
                return widget
            widget = getattr(widget, "master", None)
        return None

    def _set_drag_target(self, target):
        if target is self.drag_target:
            return
        self._restore_slot_highlight(self.drag_target)
        self.drag_target = target
        if target is not None:
            target.configure(highlightbackground=GOLD, highlightthickness=2)

    def _restore_slot_highlight(self, widget):
        if widget is None or not widget.winfo_exists():
            return
        value = self.slots.get((widget.bank, widget.slot))
        widget.configure(highlightbackground=GREEN if value else BORDER, highlightthickness=1)

    def clear_slot(self, event):
        self.slots[(event.widget.bank, event.widget.slot)] = None
        self.render_banks()
        self.refresh_library()

    def fill_empty(self):
        if not self.presets:
            self.app.set_status("Choose a preset folder first")
            return
        filenames = [p["filename"] for p in self.presets]
        unused = [name for name in filenames if name not in self.slots.values()]
        random.shuffle(unused)
        for key in self.slots:
            if self.slots[key] is None:
                self.slots[key] = unused.pop() if unused else random.choice(filenames)
        self.render_banks()
        self.refresh_library()

    def clear_all(self):
        if any(self.slots.values()) and not messagebox.askyesno("Clear layout", "Clear every preset slot?"):
            return
        for key in self.slots:
            self.slots[key] = None
        self.render_banks()
        self.refresh_library()

    def add_bank(self):
        if self.bank_count >= 30:
            self.app.set_status("The maximum is 30 banks")
            return
        self.bank_count += 1
        self.bank_count_var.set(self.bank_count)
        for slot in range(1, 5):
            self.slots[(self.bank_count, slot)] = None
        self.render_banks()

    def apply_bank_count(self, _event=None):
        try:
            requested = int(self.bank_count_var.get())
        except (TypeError, ValueError, tk.TclError):
            requested = self.bank_count
        requested = max(1, min(30, requested))
        self.bank_count_var.set(requested)
        if requested == self.bank_count:
            return

        if requested < self.bank_count:
            removed_values = [
                self.slots.get((bank, slot))
                for bank in range(requested + 1, self.bank_count + 1)
                for slot in range(1, 5)
            ]
            if any(removed_values) and not messagebox.askyesno(
                    "Reduce bank count",
                    f"Changing to {requested} bank(s) will remove assigned presets from the final "
                    f"{self.bank_count - requested} bank(s). Continue?"):
                self.bank_count_var.set(self.bank_count)
                return
            self.slots = {
                key: value for key, value in self.slots.items()
                if key[0] <= requested
            }
        else:
            for bank in range(self.bank_count + 1, requested + 1):
                for slot in range(1, 5):
                    self.slots[(bank, slot)] = None

        self.bank_count = requested
        self.render_banks()
        self.refresh_library()
        self.app.set_status(f"Bank layout changed to {self.bank_count} bank(s)")

    def remove_bank(self, bank):
        if self.bank_count == 1:
            self.app.set_status("At least one bank is required")
            return
        if any(self.slots.get((bank, slot)) for slot in range(1, 5)):
            if not messagebox.askyesno("Remove bank", f"Remove Bank {bank:02d} and its assigned presets?"):
                return
        new_slots = {}
        new_bank = 1
        for old_bank in range(1, self.bank_count + 1):
            if old_bank == bank:
                continue
            for slot in range(1, 5):
                new_slots[(new_bank, slot)] = self.slots.get((old_bank, slot))
            new_bank += 1
        self.bank_count -= 1
        self.bank_count_var.set(self.bank_count)
        self.slots = new_slots
        self.render_banks()
        self.refresh_library()

    def update_usage(self):
        filled = sum(value is not None for value in self.slots.values())
        self.usage_var.set(f"{filled} / {self.bank_count * 4} slots filled")

    def mousewheel(self, event):
        if not self.winfo_ismapped():
            return None

        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is self.canvas or widget is self.bank_host:
                delta = -1 * int(event.delta / 120) if event.delta else 0
                if delta:
                    self.canvas.yview_scroll(delta, "units")
                return "break"
            widget = getattr(widget, "master", None)
        return None

    def export(self, show_message=True, open_pdf=True):
        if not self.output_folder:
            self.choose_output_folder()
        if not self.output_folder:
            return False
        lines, uuid_lines = [], []
        lookup = {p["filename"]: p for p in self.presets}
        for bank in range(1, self.bank_count + 1):
            lines.append(f"-- Bank {bank}")
            assigned = [self.slots[(bank, slot)] for slot in range(1, 5) if self.slots[(bank, slot)]]
            if assigned:
                while len(assigned) < 4:
                    assigned.append(assigned[-1])
                for filename in assigned:
                    lines.append(filename)
                    uuid_lines.append(f"{filename} {lookup.get(filename, {}).get('uuid', 'UNKNOWN')}")
        (self.output_folder / "PresetList.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (self.output_folder / "PresetListUUIDs.txt").write_text("\n".join(uuid_lines) + "\n", encoding="utf-8")
        pdf_message = ""
        pdf_path = None
        try:
            pdf_path = generate_preset_chart(self.output_folder)
            pdf_message = f"\n\nUpdated {pdf_path.name}."
            self.app.set_status(f"Exported PresetList files and PDF to {self.output_folder}")
        except Exception as exc:
            pdf_message = f"\n\nPresetList.pdf was not updated: {exc}"
            self.app.set_status(f"Exported PresetList files, but PDF update failed: {exc}")
        if show_message:
            messagebox.showinfo(
                "Export complete",
                "PresetList.txt and PresetListUUIDs.txt were created." + pdf_message,
            )
        if open_pdf and pdf_path and pdf_path.exists():
            open_folder(pdf_path)
        return True

    def export_and_upload_filesystem(self):
        if not self.export(show_message=False, open_pdf=False):
            return
        self.app.show_page("uploader")
        uploader = self.app.pages.get("uploader")
        if isinstance(uploader, FilesystemUploaderPage):
            if self.output_folder and self.output_folder.name.lower() == "data":
                project = self.output_folder.parent
                if (project / "platformio.ini").exists():
                    self.app.set_project_dir(project)
                    uploader.load_project_defaults()
            uploader.open_pdf_after_success = self.output_folder / "PresetList.pdf"
            uploader.prepare_upload_after_builder_export()


class PresetLibraryBrowser(tk.Toplevel):
    def __init__(self, builder):
        super().__init__(builder)
        self.builder = builder
        self.title("Ignitron Preset Library Browser")
        self.configure(bg=BG)
        self.geometry("1120x720")
        self.minsize(900, 580)
        self.transient(builder.winfo_toplevel())
        self.search_var = tk.StringVar()
        self.filter_var = tk.StringVar(value="All presets")
        self.sort_column = "name"
        self.sort_reverse = False
        self.visible_presets = []
        self.detail_title = tk.StringVar(value="Select a preset")
        self.detail_meta = tk.StringVar(value="Preset details will appear here.")
        self._build()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        self.filter_var.trace_add("write", lambda *_: self.refresh())
        self.refresh()

    def _build(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=26, pady=(22, 16))
        tk.Label(header, text="Preset Library", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 22)).pack(anchor="w")
        tk.Label(header, text="Browse metadata, inspect JSON, and send presets directly to the bank layout.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))

        controls = tk.Frame(self, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        controls.pack(fill="x", padx=26, pady=(0, 14))
        tk.Label(controls, text="SEARCH", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 8)).pack(side="left", padx=(16, 8), pady=14)
        ttk.Entry(controls, textvariable=self.search_var, width=36).pack(side="left", pady=10)
        tk.Label(controls, text="SHOW", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 8)).pack(side="left", padx=(18, 8))
        ttk.Combobox(controls, textvariable=self.filter_var, state="readonly", width=14,
                     values=("All presets", "Unused only", "Used only")).pack(side="left")
        self.result_label = tk.Label(controls, text="", bg=SURFACE, fg=MUTED,
                                     font=("Segoe UI", 9))
        self.result_label.pack(side="right", padx=16)

        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True, padx=26, pady=(0, 16))
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)

        table_panel = tk.Frame(content, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        table_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        columns = ("name", "filename", "bpm", "status")
        self.tree = ttk.Treeview(table_panel, columns=columns, show="headings", selectmode="browse")
        headings = {"name": "Preset name", "filename": "Filename", "bpm": "BPM", "status": "Usage"}
        widths = {"name": 190, "filename": 220, "bpm": 58, "status": 75}
        for column in columns:
            self.tree.heading(column, text=headings[column],
                              command=lambda col=column: self.sort_by(col))
            self.tree.column(column, width=widths[column], minwidth=50,
                             anchor="center" if column in ("bpm", "status") else "w")
        scroll = ttk.Scrollbar(table_panel, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scroll.pack(side="right", fill="y", padx=(0, 10), pady=10)
        self.tree.bind("<<TreeviewSelect>>", self.show_selected)
        self.tree.bind("<Double-Button-1>", self.add_selected)

        details = tk.Frame(content, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        details.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        tk.Label(details, text="PRESET DETAILS", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=18, pady=(17, 7))
        tk.Label(details, textvariable=self.detail_title, bg=SURFACE, fg=TEXT,
                 wraplength=360, justify="left", font=("Segoe UI Semibold", 15)).pack(anchor="w", padx=18)
        tk.Label(details, textvariable=self.detail_meta, bg=SURFACE, fg=MUTED,
                 wraplength=360, justify="left", font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(6, 12))
        self.description_label = tk.Label(details, text="", bg=SURFACE, fg=TEXT,
                                          wraplength=360, justify="left", font=("Segoe UI", 9))
        self.description_label.pack(anchor="w", padx=18, pady=(0, 12))
        self.json_preview = tk.Text(details, bg="#0b0d11", fg="#cbd0d8", relief="flat",
                                    highlightthickness=1, highlightbackground=BORDER,
                                    font=("Consolas", 8), wrap="none", state="disabled")
        self.json_preview.pack(fill="both", expand=True, padx=18, pady=(0, 14))

        footer = tk.Frame(self, bg=BG)
        footer.pack(fill="x", padx=26, pady=(0, 22))
        ttk.Button(footer, text="Open preset folder", style="Dark.TButton",
                   command=lambda: open_folder(self.builder.folder)).pack(side="left")
        ttk.Button(footer, text="Close", style="Dark.TButton", command=self.destroy).pack(side="right")
        ttk.Button(footer, text="Add to next empty slot", style="Gold.TButton",
                   command=self.add_selected).pack(side="right", padx=9)

    def refresh(self, preserve_selection=False):
        selected_filename = self.selected_filename() if preserve_selection else None
        query = self.search_var.get().strip().lower()
        used = {value for value in self.builder.slots.values() if value}
        filter_name = self.filter_var.get()
        presets = []
        for preset in self.builder.presets:
            searchable = " ".join((preset["name"], preset["filename"], preset["uuid"],
                                   preset.get("description", ""))).lower()
            is_used = preset["filename"] in used
            if query and query not in searchable:
                continue
            if filter_name == "Unused only" and is_used:
                continue
            if filter_name == "Used only" and not is_used:
                continue
            presets.append(preset)
        presets.sort(key=self.sort_key, reverse=self.sort_reverse)
        self.visible_presets = presets
        self.tree.delete(*self.tree.get_children())
        selected_item = None
        for index, preset in enumerate(presets):
            status = "Used" if preset["filename"] in used else "Unused"
            item = self.tree.insert("", "end", iid=f"preset-{index}", values=(
                preset["name"], preset["filename"], preset.get("bpm", ""), status))
            if preset["filename"] == selected_filename:
                selected_item = item
        self.result_label.configure(text=f"{len(presets)} of {len(self.builder.presets)} presets")
        if selected_item:
            self.tree.selection_set(selected_item)
            self.tree.see(selected_item)
        elif presets and not preserve_selection:
            self.tree.selection_set("preset-0")
            self.show_selected()

    def sort_key(self, preset):
        if self.sort_column == "status":
            return preset["filename"] in self.builder.slots.values()
        value = preset.get(self.sort_column, "")
        if self.sort_column == "bpm":
            try:
                return float(value)
            except (TypeError, ValueError):
                return -1
        return str(value).lower()

    def sort_by(self, column):
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self.refresh(preserve_selection=True)

    def selected_preset(self):
        selection = self.tree.selection()
        if not selection:
            return None
        try:
            index = int(selection[0].split("-", 1)[1])
            return self.visible_presets[index]
        except (IndexError, ValueError):
            return None

    def selected_filename(self):
        preset = self.selected_preset()
        return preset["filename"] if preset else None

    def show_selected(self, _event=None):
        preset = self.selected_preset()
        if not preset:
            return
        used_count = sum(value == preset["filename"] for value in self.builder.slots.values())
        bpm = preset.get("bpm", "Not specified") or "Not specified"
        version = preset.get("version", "Not specified") or "Not specified"
        self.detail_title.set(preset["name"])
        self.detail_meta.set(
            f"{preset['filename']}\nBPM: {bpm}   Version: {version}\n"
            f"Used in {used_count} slot(s)\nUUID: {preset['uuid']}")
        self.description_label.configure(text=preset.get("description", "") or "No description provided.")
        raw = json.dumps(preset.get("data", {}), indent=2, ensure_ascii=False)
        self.json_preview.configure(state="normal")
        self.json_preview.delete("1.0", "end")
        self.json_preview.insert("1.0", raw)
        self.json_preview.configure(state="disabled")

    def add_selected(self, _event=None):
        preset = self.selected_preset()
        if preset and self.builder.add_filename_to_next_slot(preset["filename"]):
            self.refresh(preserve_selection=True)
            self.show_selected()


class LibraryToolsPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.library_folder = None
        self.presets = []
        self.filtered = []
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_list())
        self.summary_var = tk.StringVar(value="Choose your main preset library to begin")
        self.detail_title = tk.StringVar(value="No preset selected")
        self.detail_meta = tk.StringVar(value="")
        self.heading("Ignitron Library Tools", "Manage the main preset collection separately from each pedal's data folder.",
                     self.choose_library, "Choose main library")
        self._build()

    def _build(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=34, pady=(0, 28))
        body.grid_columnconfigure(0, weight=2)
        body.grid_columnconfigure(1, weight=3)
        body.grid_rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(left, text="MAIN PRESET LIBRARY", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=18, pady=(18, 4))
        tk.Label(left, textvariable=self.summary_var, bg=SURFACE, fg=MUTED,
                 wraplength=370, justify="left", font=("Segoe UI", 8)).pack(anchor="w", padx=18, pady=(0, 12))
        ttk.Entry(left, textvariable=self.search_var).pack(fill="x", padx=18, pady=(0, 12))
        list_frame = tk.Frame(left, bg=SURFACE)
        list_frame.pack(fill="both", expand=True, padx=18)
        scroll = ttk.Scrollbar(list_frame, orient="vertical")
        self.preset_list = tk.Listbox(list_frame, bg=CARD, fg=TEXT, selectbackground=ORANGE,
                                      selectforeground="white", relief="flat", highlightthickness=1,
                                      highlightbackground=BORDER, font=("Segoe UI", 9),
                                      activestyle="none", yscrollcommand=scroll.set)
        scroll.configure(command=self.preset_list.yview)
        self.preset_list.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.preset_list.bind("<<ListboxSelect>>", self.show_selected)

        buttons = tk.Frame(left, bg=SURFACE)
        buttons.pack(fill="x", padx=18, pady=16)
        ttk.Button(buttons, text="Use in Preset Builder", style="Gold.TButton",
                   command=self.use_in_builder).pack(fill="x", pady=(0, 5))
        ttk.Button(buttons, text="Find duplicates", style="Dark.TButton",
                   command=self.show_duplicates).pack(fill="x", pady=3)
        ttk.Button(buttons, text="Setlist builder", style="Dark.TButton",
                   command=self.open_setlist_builder).pack(fill="x", pady=3)
        ttk.Button(buttons, text="Open library folder", style="Dark.TButton",
                   command=self.open_library_folder).pack(fill="x", pady=3)
        ttk.Button(buttons, text="GitHub sync (not implemented)", style="Dark.TButton",
                   state="disabled").pack(fill="x", pady=3)

        right = tk.Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        stats = tk.Frame(right, bg=CARD)
        stats.pack(fill="x", padx=18, pady=18)
        self.total_stat = self._stat(stats, "PRESETS", "0")
        self.name_stat = self._stat(stats, "DUPLICATE NAMES", "0")
        self.uuid_stat = self._stat(stats, "DUPLICATE UUIDS", "0")

        details = tk.Frame(right, bg=SURFACE)
        details.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        tk.Label(details, textvariable=self.detail_title, bg=SURFACE, fg=TEXT,
                 font=("Segoe UI Semibold", 17)).pack(anchor="w")
        tk.Label(details, textvariable=self.detail_meta, bg=SURFACE, fg=MUTED,
                 justify="left", font=("Segoe UI", 9)).pack(anchor="w", pady=(5, 12))
        notebook = ttk.Notebook(details)
        notebook.pack(fill="both", expand=True)
        self.overview = self._detail_text(notebook, wrap="word")
        self.raw_json = self._detail_text(notebook, wrap="none")
        self.file_info = self._detail_text(notebook, wrap="word")
        notebook.add(self.overview, text="Overview")
        notebook.add(self.raw_json, text="Raw JSON")
        notebook.add(self.file_info, text="File Info")

    def _detail_text(self, parent, wrap):
        return tk.Text(parent, bg="#0b0d11", fg="#cbd0d8", relief="flat",
                       highlightthickness=1, highlightbackground=BORDER,
                       font=("Consolas", 9), wrap=wrap, state="disabled")

    def _stat(self, parent, label, value):
        frame = tk.Frame(parent, bg=CARD)
        frame.pack(side="left", fill="x", expand=True, padx=12, pady=13)
        value_var = tk.StringVar(value=value)
        tk.Label(frame, textvariable=value_var, bg=CARD, fg=GOLD,
                 font=("Segoe UI Semibold", 21)).pack(anchor="w")
        tk.Label(frame, text=label, bg=CARD, fg=MUTED,
                 font=("Segoe UI Semibold", 8)).pack(anchor="w")
        return value_var

    def choose_library(self):
        folder = filedialog.askdirectory(title="Select main Ignitron preset library")
        if folder:
            self.scan_library(Path(folder))

    def scan_library(self, folder):
        self.library_folder = Path(folder)
        self.presets = []
        for path in sorted(self.library_folder.rglob("*.json"), key=lambda item: item.name.lower()):
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            self.presets.append({
                "name": str(data.get("Name", path.stem)),
                "filename": path.name,
                "uuid": str(data.get("UUID", "")).upper(),
                "path": path,
                "data": data,
            })
        self.update_stats()
        self.refresh_list()
        self.app.set_status(f"Scanned {len(self.presets)} presets in {self.library_folder}")

    def update_stats(self):
        names = {}
        uuids = {}
        for preset in self.presets:
            names[preset["name"].casefold()] = names.get(preset["name"].casefold(), 0) + 1
            if preset["uuid"]:
                uuids[preset["uuid"]] = uuids.get(preset["uuid"], 0) + 1
        duplicate_names = sum(count > 1 for count in names.values())
        duplicate_uuids = sum(count > 1 for count in uuids.values())
        self.total_stat.set(str(len(self.presets)))
        self.name_stat.set(str(duplicate_names))
        self.uuid_stat.set(str(duplicate_uuids))
        self.summary_var.set(f"{self.library_folder}  |  {len(self.presets)} presets")

    def refresh_list(self):
        query = self.search_var.get().strip().casefold()
        self.filtered = [
            preset for preset in self.presets
            if query in preset["name"].casefold()
            or query in preset["filename"].casefold()
            or query in preset["uuid"].casefold()
        ]
        self.preset_list.delete(0, "end")
        for preset in self.filtered:
            self.preset_list.insert("end", preset["name"])

    def selected_preset(self):
        selection = self.preset_list.curselection()
        if not selection or selection[0] >= len(self.filtered):
            return None
        return self.filtered[selection[0]]

    def show_selected(self, _event=None):
        preset = self.selected_preset()
        if not preset:
            return
        data = preset["data"]
        self.detail_title.set(preset["name"])
        self.detail_meta.set(
            f"{preset['filename']}\nUUID: {preset['uuid'] or 'Not specified'}\n"
            f"BPM: {data.get('BPM', 'Not specified')}\n{preset['path']}")
        lines = []
        description = data.get("Description", "")
        if description:
            lines.extend([description, "", "PEDALS"])
        for pedal in data.get("Pedals", []):
            lines.append(f"{pedal.get('Name', 'Unknown'):<24} {'ON' if pedal.get('IsOn') else 'OFF'}")
        if not lines:
            lines.append(json.dumps(data, indent=2, ensure_ascii=False))
        self.overview.configure(state="normal")
        self.overview.delete("1.0", "end")
        self.overview.insert("1.0", "\n".join(lines))
        self.overview.configure(state="disabled")
        self._set_text(self.raw_json, json.dumps(data, indent=2, ensure_ascii=False))
        try:
            stat = preset["path"].stat()
            modified = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
            info = f"Path:\n{preset['path']}\n\nSize:\n{stat.st_size / 1024:.2f} KB\n\nModified:\n{modified}"
        except OSError as exc:
            info = f"Could not read file information:\n{exc}"
        self._set_text(self.file_info, info)

    def _set_text(self, widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def duplicate_groups(self, field):
        groups = {}
        for preset in self.presets:
            value = preset[field]
            if value:
                key = value.casefold() if field == "name" else value
                groups.setdefault(key, []).append(preset)
        return {key: values for key, values in groups.items() if len(values) > 1}

    def show_duplicates(self):
        if not self.presets:
            messagebox.showinfo("No library", "Choose and scan a preset library first.")
            return
        window = tk.Toplevel(self)
        window.title("Ignitron Duplicate Finder")
        window.configure(bg=BG)
        window.geometry("1000x700")
        notebook = ttk.Notebook(window)
        notebook.pack(fill="both", expand=True, padx=20, pady=20)

        names_text = tk.Text(notebook, bg="#0b0d11", fg="#cbd0d8", font=("Consolas", 9))
        uuid_page = tk.Frame(notebook, bg=SURFACE)
        uuid_text = tk.Text(uuid_page, bg="#0b0d11", fg="#cbd0d8", font=("Consolas", 9))
        uuid_text.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Button(uuid_page, text="Delete duplicate UUID files", style="Danger.TButton",
                   command=lambda: self.delete_duplicate_uuids(window)).pack(pady=(0, 14))
        notebook.add(names_text, text="Duplicate Names")
        notebook.add(uuid_page, text="Duplicate UUIDs")

        name_groups = self.duplicate_groups("name")
        for presets in sorted(name_groups.values(), key=lambda group: group[0]["name"].casefold()):
            names_text.insert("end", f"{len(presets)}x  {presets[0]['name']}\n")
            for preset in sorted(presets, key=lambda item: str(item["path"]).casefold()):
                names_text.insert("end", f"    {preset['path']}\n")
            names_text.insert("end", "\n")
        if not name_groups:
            names_text.insert("end", "No duplicate names found.\n")

        uuid_groups = self.duplicate_groups("uuid")
        for uuid, presets in sorted(uuid_groups.items()):
            uuid_text.insert("end", f"{len(presets)}x  {uuid}\n")
            for preset in sorted(presets, key=lambda item: str(item["path"]).casefold()):
                uuid_text.insert("end", f"    {preset['path']}\n")
            uuid_text.insert("end", "\n")
        if not uuid_groups:
            uuid_text.insert("end", "No duplicate UUIDs found.\n")

    def delete_duplicate_uuids(self, duplicate_window):
        groups = self.duplicate_groups("uuid")
        deletions = []
        for presets in groups.values():
            ordered = sorted(presets, key=lambda item: str(item["path"]).casefold())
            deletions.extend(ordered[1:])
        if not deletions:
            messagebox.showinfo("No duplicates", "No duplicate UUID files were found.")
            return
        preview = "\n".join(str(item["path"]) for item in deletions[:10])
        if len(deletions) > 10:
            preview += f"\n...and {len(deletions) - 10} more"
        confirmed = messagebox.askyesno(
            "Delete duplicate UUID files",
            f"This permanently deletes {len(deletions)} file(s). The alphabetically first path "
            f"for each UUID will be kept.\n\nFiles to delete:\n{preview}\n\nContinue?",
            icon="warning",
        )
        if not confirmed:
            return
        deleted, errors = 0, []
        for preset in deletions:
            try:
                preset["path"].unlink()
                deleted += 1
            except FileNotFoundError:
                continue
            except OSError as exc:
                errors.append(f"{preset['path']}: {exc}")
        self.scan_library(self.library_folder)
        duplicate_window.destroy()
        if errors:
            messagebox.showwarning("Cleanup partially complete",
                                   f"Deleted {deleted} file(s).\n\n" + "\n".join(errors[:10]))
        else:
            messagebox.showinfo("Cleanup complete", f"Deleted {deleted} duplicate file(s).")

    def open_setlist_builder(self):
        if not self.presets:
            messagebox.showinfo("No library", "Choose and scan a preset library first.")
            return
        SetlistBuilder(self, self.presets)

    def use_in_builder(self):
        if not self.library_folder:
            self.choose_library()
            if not self.library_folder:
                return
        self.app.show_page("builder")
        self.app.pages["builder"].load_library_folder(self.library_folder)

    def open_library_folder(self):
        if self.library_folder:
            open_folder(self.library_folder)
        else:
            self.choose_library()


class ReferencePage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.pin_items = {}
        self.pin_detail_var = tk.StringVar(value="Click a pin on the ESP32 Dev board to see wiring notes.")
        self.reference_dir = resource_path("reference")
        self.heading("ESP32 Reference", "Interactive ESP32 Dev pinout, Ignitron hardware docs, and firmware setting notes.")
        self._build()

    def _build(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=34, pady=(0, 28))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        pinout = tk.Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        pinout.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(pinout, text="ESP32 DEV MODULE", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=18, pady=(18, 4))
        tk.Label(pinout, text="Click a GPIO to view Ignitron usage and boot-safety notes.",
                 bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(0, 12))
        self.canvas = tk.Canvas(pinout, bg="#0b0d11", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self.canvas.bind("<Configure>", lambda _event: self.draw_pinout())

        side = tk.Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        side.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        tk.Label(side, text="PIN DETAIL", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=18, pady=(18, 4))
        tk.Label(side, textvariable=self.pin_detail_var, bg=SURFACE, fg=TEXT,
                 justify="left", wraplength=460, font=("Segoe UI Semibold", 12)).pack(
                     anchor="w", fill="x", padx=18, pady=(0, 18))

        tk.Label(side, text="REFERENCE FILES", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=18, pady=(0, 8))
        files = tk.Frame(side, bg=SURFACE)
        files.pack(fill="x", padx=18, pady=(0, 18))
        files.grid_columnconfigure(0, weight=1)
        files.grid_columnconfigure(1, weight=1)
        reference_files = self.reference_files()
        for index, (label, filename) in enumerate(reference_files):
            path = self.reference_dir / filename
            ttk.Button(files, text=label, style="Dark.TButton",
                       command=lambda item=path: self.open_reference(item)).grid(
                           row=index // 2, column=index % 2, sticky="ew", padx=(0, 6), pady=3)
        ttk.Button(files, text="Folder", style="Dark.TButton",
                   command=lambda: self.open_reference(self.reference_dir)).grid(
                       row=(len(reference_files) + 1) // 2, column=0, columnspan=2,
                       sticky="ew", padx=(0, 6), pady=3)

        notes = tk.Text(side, bg="#0b0d11", fg="#cbd0d8", relief="flat",
                        highlightthickness=1, highlightbackground=BORDER,
                        font=("Segoe UI", 9), wrap="word")
        notes.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        notes.insert("1.0", self.reference_text())
        notes.configure(state="disabled")

    def reference_text(self):
        return (
            "IGNITRON DEFAULTS\n"
            "- Amp mode rocker: GPIO35 with external 10k pull-up to 3.3V, switch to GND.\n"
            "- Battery ADC: GPIO36. Keep battery voltage divided before it reaches the ESP32.\n"
            "- OLED I2C: SDA GPIO21, SCL GPIO22.\n"
            "- Filesystem upload only updates the data folder and presetlist; it does not flash firmware.\n\n"
            "BOOT / SAFETY NOTES\n"
            "- GPIO34 to GPIO39 are input-only. They are good for switches or ADC, not LEDs.\n"
            "- GPIO35 has no internal pull-up, so the rocker needs the physical 10k pull-up.\n"
            "- GPIO0, GPIO2, GPIO4, GPIO5, GPIO12, and GPIO15 affect ESP32 boot strapping. Avoid adding switches "
            "or pull resistors there unless you know the boot-state requirement.\n"
            "- GPIO6 to GPIO11 are normally connected to flash memory and should not be used.\n\n"
            "FIRMWARE OPTIONS\n"
            "- Use the Firmware Settings tab to change OLED driver, battery display, LED mode, firmware version, "
            "and whether the amp mode rocker is installed.\n"
            "- When the rocker is installed, LOW means amp mode on boot and HIGH means normal app boot."
            "\n\nREFERENCE FOLDER MATERIAL\n"
            "- Ignitron-Schematics.pdf: main PCB schematic reference.\n"
            "- Ignitron-Battery-Indicator-Schematics.pdf: battery divider and power reference.\n"
            "- Ignitron-UV-Print.pdf: Tayda UV print template. Use a PDF viewer with layer support.\n"
            "- ignitron-cheatsheet.pdf: quick reference sheet.\n"
            "- README.md: hardware BOM, PCB assembly, enclosure drill locations, battery notes, 3D case notes, "
            "and optional preset LED wiring."
            "\n\nMAIN SCHEMATIC PIN MAP\n"
            "- SW1 P1/Drive: GPIO25. D1 P1/Drive LED: GPIO27.\n"
            "- SW2 P2/Mod: GPIO26. D2 P2/Mod LED: GPIO13.\n"
            "- SW3 P3/Delay: GPIO32. D3 P3/Delay LED: GPIO16.\n"
            "- SW4 P4/Reverb: GPIO33. D4 P4/Reverb LED: GPIO14.\n"
            "- SW5 Bank Down/Noise Gate: GPIO19. D5 Bank Down/Noise Gate LED: GPIO23.\n"
            "- SW6 Bank Up/Comp: GPIO18. D6 Bank Up/Comp LED: GPIO17.\n"
            "- J2 OLED: VCC, SCL GPIO22, SDA GPIO21, GND.\n"
            "- J1 PowerIn: 9V and GND into the PCB power input."
        )

    def reference_files(self):
        files = [
            ("Cheatsheet", "ignitron-cheatsheet.pdf"),
            ("Schematics", "Ignitron-Schematics.pdf"),
            ("Battery", "Ignitron-Battery-Indicator-Schematics.pdf"),
            ("UV Print", "Ignitron-UV-Print.pdf"),
            ("README", "README.md"),
        ]
        return [(label, filename) for label, filename in files if (self.reference_dir / filename).exists()]

    def open_reference(self, path):
        path = Path(path)
        if not path.exists():
            messagebox.showwarning("Missing reference", f"Could not find:\n{path}")
            return
        open_folder(path)
        self.app.set_status(f"Opened reference: {path.name}")

    def pin_data(self):
        return [
            {"pin": "3V3", "side": "left", "kind": "power", "note": "3.3V power rail. The schematic uses this for switch pull-ups and OLED VCC. Use it for the amp rocker 10k pull-up too."},
            {"pin": "EN", "side": "left", "kind": "control", "note": "Reset enable pin. Usually left alone."},
            {"pin": "GPIO36", "side": "left", "kind": "adc", "note": "Battery voltage ADC input in firmware. Used with the battery indicator divider schematic, not on the original main PCB schematic."},
            {"pin": "GPIO39", "side": "left", "kind": "input", "note": "Input-only ADC-capable pin. Available if firmware is changed."},
            {"pin": "GPIO34", "side": "left", "kind": "input", "note": "Input-only. Usable for switches with an external pull-up or pull-down."},
            {"pin": "GPIO35", "label": "GPIO35 - Amp SW", "side": "left", "kind": "rocker", "note": "Optional amp mode rocker switch input. Add-on mod, not on the original main PCB schematic. External 10k pull-up to 3.3V, SPST switch to GND. LOW at boot forces AMP mode."},
            {"pin": "GPIO32", "label": "GPIO32 - SW3", "side": "left", "kind": "button", "note": "SW3 on the schematic: P3 / Delay footswitch. Firmware names: BUTTON_PRESET3_GPIO and BUTTON_DELAY_GPIO."},
            {"pin": "GPIO33", "label": "GPIO33 - SW4", "side": "left", "kind": "button", "note": "SW4 on the schematic: P4 / Reverb footswitch. Firmware names: BUTTON_PRESET4_GPIO and BUTTON_REVERB_GPIO."},
            {"pin": "GPIO25", "label": "GPIO25 - SW1", "side": "left", "kind": "button", "note": "SW1 on the schematic: P1 / Drive footswitch. Firmware names: BUTTON_PRESET1_GPIO and BUTTON_DRIVE_GPIO."},
            {"pin": "GPIO26", "label": "GPIO26 - SW2", "side": "left", "kind": "button", "note": "SW2 on the schematic: P2 / Mod footswitch. Firmware names: BUTTON_PRESET2_GPIO and BUTTON_MOD_GPIO."},
            {"pin": "GPIO27", "label": "GPIO27 - D1", "side": "left", "kind": "led", "note": "D1 LED on the schematic through R1: P1 / Drive LED. Firmware names: LED_PRESET1_GPIO and LED_DRIVE_GPIO when dedicated preset LEDs are off."},
            {"pin": "GPIO14", "label": "GPIO14 - D4", "side": "left", "kind": "led", "note": "D4 LED on the schematic through R4: P4 / Reverb LED. Firmware names: LED_PRESET4_GPIO and LED_REVERB_GPIO when dedicated preset LEDs are off."},
            {"pin": "GPIO12", "label": "GPIO12 - Optional P3 LED", "side": "left", "kind": "strap", "note": "Optional dedicated preset LED 3 from the 3D case docs and firmware DEDICATED_PRESET_LEDS mode. Boot strap pin; avoid pulling it into the wrong state at reset."},
            {"pin": "GND", "side": "left", "kind": "power", "note": "Ground reference. Rocker switch closes to GND."},
            {"pin": "VIN", "side": "right", "kind": "power", "note": "5V/VIN supply depending on board. Do not connect directly to GPIO."},
            {"pin": "GND", "side": "right", "kind": "power", "note": "Ground reference."},
            {"pin": "GPIO13", "label": "GPIO13 - D2", "side": "right", "kind": "led", "note": "D2 LED on the schematic through R2: P2 / Mod LED. Firmware names: LED_PRESET2_GPIO and LED_MOD_GPIO when dedicated preset LEDs are off."},
            {"pin": "GPIO9", "side": "right", "kind": "flash", "note": "Usually connected to module flash. Do not use."},
            {"pin": "GPIO10", "side": "right", "kind": "flash", "note": "Usually connected to module flash. Do not use."},
            {"pin": "GPIO11", "side": "right", "kind": "flash", "note": "Usually connected to module flash. Do not use."},
            {"pin": "GPIO6", "side": "right", "kind": "flash", "note": "Usually connected to module flash. Do not use."},
            {"pin": "GPIO7", "side": "right", "kind": "flash", "note": "Usually connected to module flash. Do not use."},
            {"pin": "GPIO8", "side": "right", "kind": "flash", "note": "Usually connected to module flash. Do not use."},
            {"pin": "GPIO15", "label": "GPIO15 - Optional P4 LED", "side": "right", "kind": "strap", "note": "Optional dedicated preset LED 4 from the 3D case docs and firmware DEDICATED_PRESET_LEDS mode. Boot strap pin; avoid pulling it into the wrong state at reset."},
            {"pin": "GPIO2", "side": "right", "kind": "strap", "note": "Boot strap pin. Often tied to onboard LED; avoid for switches."},
            {"pin": "GPIO0", "label": "GPIO0 - Optional P1 LED", "side": "right", "kind": "strap", "note": "Optional dedicated preset LED 1 from the 3D case docs and firmware DEDICATED_PRESET_LEDS mode. Boot/program strap pin; LOW at reset enters bootloader."},
            {"pin": "GPIO4", "label": "GPIO4 - Optional P2 LED", "side": "right", "kind": "strap", "note": "Optional dedicated preset LED 2 from the 3D case docs and firmware DEDICATED_PRESET_LEDS mode. Boot strap pin; wire carefully."},
            {"pin": "GPIO16", "label": "GPIO16 - D3", "side": "right", "kind": "led", "note": "D3 LED on the schematic through R3: P3 / Delay LED. Firmware names: LED_PRESET3_GPIO and LED_DELAY_GPIO when dedicated preset LEDs are off."},
            {"pin": "GPIO17", "label": "GPIO17 - D6", "side": "right", "kind": "led", "note": "D6 LED on the schematic through R6: Bank Up / Comp LED. Firmware names: LED_BANK_UP_GPIO and LED_COMP_GPIO."},
            {"pin": "GPIO5", "side": "right", "kind": "strap", "note": "Boot strap pin. Avoid for add-on switches."},
            {"pin": "GPIO18", "label": "GPIO18 - SW6", "side": "right", "kind": "button", "note": "SW6 on the schematic: Bank Up / Comp footswitch. Firmware names: BUTTON_BANK_UP_GPIO and BUTTON_COMP_GPIO."},
            {"pin": "GPIO19", "label": "GPIO19 - SW5", "side": "right", "kind": "button", "note": "SW5 on the schematic: Bank Down / Noise Gate footswitch. Firmware names: BUTTON_BANK_DOWN_GPIO and BUTTON_NOISEGATE_GPIO."},
            {"pin": "GPIO21", "label": "GPIO21 - J2 SDA", "side": "right", "kind": "i2c", "note": "J2 OLED connector pin 3: SDA for the SSD1306/SH1106 display."},
            {"pin": "GPIO22", "label": "GPIO22 - J2 SCL", "side": "right", "kind": "i2c", "note": "J2 OLED connector pin 2: SCL for the SSD1306/SH1106 display."},
            {"pin": "GPIO23", "label": "GPIO23 - D5", "side": "right", "kind": "led", "note": "D5 LED on the schematic through R5: Bank Down / Noise Gate LED. Firmware names: LED_BANK_DOWN_GPIO and LED_NOISEGATE_GPIO."},
        ]

    def draw_pinout(self):
        self.canvas.delete("all")
        self.pin_items = {}
        width = max(self.canvas.winfo_width(), 620)
        height = max(self.canvas.winfo_height(), 660)
        board_w = max(220, min(320, width - 300))
        board_h = height - 48
        x1 = (width - board_w) / 2
        y1 = 24
        x2 = x1 + board_w
        y2 = y1 + board_h

        self.canvas.create_rectangle(x1, y1, x2, y2, fill="#18202b", outline=BORDER, width=2)
        self.canvas.create_rectangle(x1 + 74, y1 + 22, x2 - 74, y1 + 88, fill="#263141", outline="#4a5668")
        self.canvas.create_text((x1 + x2) / 2, y1 + 55, text="USB", fill=TEXT, font=("Segoe UI Semibold", 11))
        self.canvas.create_text((x1 + x2) / 2, y1 + 122, text="ESP32 DEVKIT", fill=GOLD,
                                font=("Segoe UI Semibold", 16))
        self.canvas.create_text((x1 + x2) / 2, y2 - 28, text="Click any labeled pin", fill=MUTED,
                                font=("Segoe UI", 9))

        pins = self.pin_data()
        left = [pin for pin in pins if pin["side"] == "left"]
        right = [pin for pin in pins if pin["side"] == "right"]
        self._draw_pin_column(left, x1, y1 + 138, y2 - 58, "left")
        self._draw_pin_column(right, x2, y1 + 138, y2 - 58, "right")

        legend = [
            ("rocker", "Amp rocker"),
            ("button", "Button"),
            ("led", "LED"),
            ("i2c", "OLED"),
            ("adc", "Battery ADC"),
            ("strap", "Boot strap"),
            ("flash", "Flash"),
        ]
        lx, ly = 18, 18
        for kind, label in legend:
            self.canvas.create_rectangle(lx, ly, lx + 12, ly + 12, fill=self.pin_color(kind), outline="")
            self.canvas.create_text(lx + 18, ly + 6, text=label, fill=MUTED, anchor="w", font=("Segoe UI", 8))
            ly += 18

    def _draw_pin_column(self, pins, board_edge, top, bottom, side):
        spacing = (bottom - top) / max(len(pins) - 1, 1)
        for index, pin in enumerate(pins):
            y = top + index * spacing
            if side == "left":
                pad_x = board_edge - 10
                label_x = pad_x - 8
                anchor = "e"
                pin_x1, pin_x2 = board_edge - 20, board_edge
            else:
                pad_x = board_edge + 10
                label_x = pad_x + 8
                anchor = "w"
                pin_x1, pin_x2 = board_edge, board_edge + 20

            color = self.pin_color(pin["kind"])
            tag = f"pin_{pin['pin']}_{side}"
            items = [
                self.canvas.create_rectangle(pin_x1, y - 6, pin_x2, y + 6, fill=color, outline=""),
                self.canvas.create_oval(pad_x - 4, y - 4, pad_x + 4, y + 4, fill="#050608", outline=color),
                self.canvas.create_text(label_x, y, text=pin.get("label", pin["pin"]), fill=TEXT, anchor=anchor, font=("Segoe UI", 9)),
            ]
            self.pin_items[tag] = {"pin": pin, "items": items}
            for item in items:
                self.canvas.itemconfigure(item, tags=(tag,))
            self.canvas.tag_bind(tag, "<Button-1>", lambda _event, item=pin: self.select_pin(item))
            self.canvas.tag_bind(tag, "<Enter>", lambda _event, tag=tag: self.canvas.itemconfigure(tag, fill=GOLD))
            self.canvas.tag_bind(tag, "<Leave>", lambda _event: self.draw_pinout())

    def pin_color(self, kind):
        colors = {
            "rocker": GOLD,
            "button": "#67b7dc",
            "led": "#8dd37e",
            "i2c": "#c792ea",
            "adc": "#ffcb6b",
            "strap": "#ff6f61",
            "flash": "#6f7785",
            "power": "#f07178",
            "input": "#82aaff",
            "control": "#89ddff",
        }
        return colors.get(kind, "#cbd0d8")

    def select_pin(self, pin):
        self.pin_detail_var.set(f"{pin['pin']}\n{pin['note']}")
        self.app.set_status(f"Reference selected: {pin['pin']}")


class SetlistBuilder:
    def __init__(self, parent, presets):
        self.parent = parent
        self.presets = presets
        self.filtered = list(presets)
        self.storage_file = app_dir() / "data" / "setlists.json"
        self.setlists = self.load_setlists()
        self.current_name = None
        self.current_items = []
        self.window = tk.Toplevel(parent)
        self.window.title("Ignitron Live Setlist Builder")
        self.window.configure(bg=BG)
        self.window.geometry("1200x740")
        self.window.minsize(900, 560)
        self._build()
        self.refresh_names()
        self.refresh_library()

    def load_setlists(self):
        try:
            data = json.loads(self.storage_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def save_setlists(self):
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.storage_file.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(self.setlists, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.storage_file)

    def _build(self):
        toolbar = tk.Frame(self.window, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        toolbar.pack(fill="x", padx=20, pady=20)
        tk.Label(toolbar, text="SETLIST", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left", padx=(14, 8), pady=14)
        self.name_var = tk.StringVar()
        self.name_combo = ttk.Combobox(toolbar, textvariable=self.name_var, state="readonly", width=30)
        self.name_combo.pack(side="left")
        self.name_combo.bind("<<ComboboxSelected>>", self.load_selected)
        ttk.Button(toolbar, text="New", style="Dark.TButton", command=self.new).pack(side="left", padx=(10, 3))
        ttk.Button(toolbar, text="Save", style="Dark.TButton", command=self.save).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Save As", style="Dark.TButton", command=self.save_as).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Delete", style="Danger.TButton", command=self.delete).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Live Mode", style="Gold.TButton", command=self.open_live_mode).pack(side="right", padx=12)
        self.status_var = tk.StringVar(value="Unsaved setlist")
        tk.Label(toolbar, textvariable=self.status_var, bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="right", padx=12)

        content = tk.Frame(self.window, bg=BG)
        content.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(2, weight=1)
        content.grid_rowconfigure(1, weight=1)
        tk.Label(content, text="PRESET LIBRARY", bg=BG, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=0, column=0, sticky="w", pady=(0, 8))
        tk.Label(content, text="SETLIST ORDER", bg=BG, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=0, column=2, sticky="w", pady=(0, 8))

        left = tk.Frame(content, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        left.grid(row=1, column=0, sticky="nsew")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.filter_library())
        ttk.Entry(left, textvariable=self.search_var).pack(fill="x", padx=12, pady=12)
        self.library_list = tk.Listbox(left, bg=CARD, fg=TEXT, selectbackground=ORANGE,
                                       selectforeground="white", relief="flat", exportselection=False)
        self.library_list.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.library_list.bind("<Double-Button-1>", lambda _event: self.add_preset())

        controls = tk.Frame(content, bg=BG)
        controls.grid(row=1, column=1, padx=14)
        ttk.Button(controls, text="Add  >", style="Dark.TButton", command=self.add_preset).pack(fill="x", pady=4)
        ttk.Button(controls, text="<  Remove", style="Dark.TButton", command=self.remove_preset).pack(fill="x", pady=4)
        ttk.Button(controls, text="Move Up", style="Dark.TButton", command=lambda: self.move(-1)).pack(fill="x", pady=(24, 4))
        ttk.Button(controls, text="Move Down", style="Dark.TButton", command=lambda: self.move(1)).pack(fill="x", pady=4)

        right = tk.Frame(content, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        right.grid(row=1, column=2, sticky="nsew")
        self.setlist_list = tk.Listbox(right, bg=CARD, fg=TEXT, selectbackground=ORANGE,
                                       selectforeground="white", relief="flat", exportselection=False)
        self.setlist_list.pack(fill="both", expand=True, padx=12, pady=12)
        self.setlist_list.bind("<Double-Button-1>", lambda _event: self.remove_preset())

    def refresh_names(self):
        self.name_combo["values"] = sorted(self.setlists, key=str.casefold)

    def refresh_library(self):
        self.library_list.delete(0, "end")
        for preset in self.filtered:
            self.library_list.insert("end", preset["name"])

    def filter_library(self):
        query = self.search_var.get().casefold()
        self.filtered = [preset for preset in self.presets if query in preset["name"].casefold()]
        self.refresh_library()

    def refresh_items(self, selected=None):
        self.setlist_list.delete(0, "end")
        for index, item in enumerate(self.current_items, 1):
            self.setlist_list.insert("end", f"{index:02d}.  {item['name']}")
        if selected is not None and self.current_items:
            selected = min(selected, len(self.current_items) - 1)
            self.setlist_list.selection_set(selected)
            self.setlist_list.see(selected)
        self.status_var.set(f"{len(self.current_items)} preset(s)")

    def add_preset(self):
        selection = self.library_list.curselection()
        if not selection:
            return
        preset = self.filtered[selection[0]]
        self.current_items.append({"name": preset["name"], "uuid": preset["uuid"], "path": str(preset["path"])})
        self.refresh_items(len(self.current_items) - 1)

    def remove_preset(self):
        selection = self.setlist_list.curselection()
        if selection:
            index = selection[0]
            del self.current_items[index]
            self.refresh_items(index)

    def move(self, direction):
        selection = self.setlist_list.curselection()
        if not selection:
            return
        old = selection[0]
        new = old + direction
        if 0 <= new < len(self.current_items):
            item = self.current_items.pop(old)
            self.current_items.insert(new, item)
            self.refresh_items(new)

    def new(self):
        if self.current_items and not messagebox.askyesno("New setlist", "Clear the current setlist?"):
            return
        self.current_name = None
        self.current_items = []
        self.name_var.set("")
        self.refresh_items()

    def load_selected(self, _event=None):
        name = self.name_var.get()
        if name:
            self.current_name = name
            self.current_items = [dict(item) for item in self.setlists.get(name, [])]
            self.refresh_items()

    def save(self):
        if not self.current_name:
            self.save_as()
            return
        self.setlists[self.current_name] = [dict(item) for item in self.current_items]
        self._write()

    def save_as(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("Save setlist", "Setlist name:",
                                      initialvalue=self.current_name or "", parent=self.window)
        if not name or not name.strip():
            return
        name = name.strip()
        if name in self.setlists and name != self.current_name:
            if not messagebox.askyesno("Replace setlist", f'Replace the existing setlist "{name}"?'):
                return
        self.current_name = name
        self.name_var.set(name)
        self.setlists[name] = [dict(item) for item in self.current_items]
        self._write()

    def _write(self):
        try:
            self.save_setlists()
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self.refresh_names()
        self.status_var.set(f"Saved: {self.current_name}")

    def delete(self):
        if not self.current_name or not messagebox.askyesno("Delete setlist", f'Delete "{self.current_name}"?'):
            return
        del self.setlists[self.current_name]
        try:
            self.save_setlists()
        except OSError as exc:
            messagebox.showerror("Delete failed", str(exc))
            return
        self.current_name = None
        self.current_items = []
        self.name_var.set("")
        self.refresh_names()
        self.refresh_items()

    def open_live_mode(self):
        if not self.current_items:
            messagebox.showinfo("Empty setlist", "Add at least one preset first.")
            return
        LiveMode(self.window, self.current_name or "Unsaved Setlist", self.current_items)


class LiveMode:
    def __init__(self, parent, name, items):
        self.items = items
        self.index = 0
        self.window = tk.Toplevel(parent)
        self.window.title(f"Live Mode - {name}")
        self.window.geometry("1000x650")
        self.window.configure(bg="#08090c")
        self.window.bind("<Right>", lambda _event: self.next())
        self.window.bind("<Down>", lambda _event: self.next())
        self.window.bind("<space>", lambda _event: self.next())
        self.window.bind("<Left>", lambda _event: self.previous())
        self.window.bind("<Up>", lambda _event: self.previous())
        self.window.bind("<Escape>", lambda _event: self.window.destroy())
        self.window.bind("<F11>", lambda _event: self.toggle_fullscreen())
        self.position = tk.Label(self.window, bg="#08090c", fg=MUTED, font=("Segoe UI", 18))
        self.position.pack(pady=(35, 15))
        self.current = tk.Label(self.window, bg="#08090c", fg=TEXT,
                                font=("Segoe UI Semibold", 48), wraplength=900)
        self.current.pack(fill="both", expand=True, padx=30)
        self.up_next = tk.Label(self.window, bg="#08090c", fg=GOLD,
                                font=("Segoe UI Semibold", 22), wraplength=900)
        self.up_next.pack(pady=(10, 25))
        controls = tk.Frame(self.window, bg="#08090c")
        controls.pack(pady=(0, 30))
        ttk.Button(controls, text="Previous", style="Dark.TButton", command=self.previous).pack(side="left", padx=8)
        ttk.Button(controls, text="Next", style="Gold.TButton", command=self.next).pack(side="left", padx=8)
        self.update()
        self.window.focus_set()

    def update(self):
        self.position.configure(text=f"{self.index + 1} of {len(self.items)}")
        self.current.configure(text=self.items[self.index]["name"])
        next_text = f"NEXT: {self.items[self.index + 1]['name']}" if self.index + 1 < len(self.items) else "END OF SETLIST"
        self.up_next.configure(text=next_text)

    def next(self):
        if self.index < len(self.items) - 1:
            self.index += 1
            self.update()

    def previous(self):
        if self.index > 0:
            self.index -= 1
            self.update()

    def toggle_fullscreen(self):
        self.window.attributes("-fullscreen", not bool(self.window.attributes("-fullscreen")))


class FilesystemUploaderPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.running = False
        self.project_var = self.app.project_dir_var
        self.platformio_var = tk.StringVar(value=default_platformio())
        self.env_var = tk.StringVar(value="esp32dev")
        self.port_var = tk.StringVar()
        self.allow_missing_var = tk.BooleanVar(value=True)
        self.open_pdf_after_success = None
        self.heading("Filesystem Uploader", "Build and upload the Ignitron data folder without reflashing firmware.")
        self._build()
        self.load_project_defaults()

    @property
    def project_dir(self):
        return Path(self.project_var.get()).expanduser().resolve()

    @property
    def platformio_ini(self):
        return self.project_dir / "platformio.ini"

    @property
    def data_dir(self):
        return self.project_dir / "data"

    def _build(self):
        panel = tk.Frame(self, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True, padx=34, pady=(0, 30))

        controls = tk.Frame(panel, bg=SURFACE)
        controls.pack(fill="x", padx=22, pady=20)
        controls.grid_columnconfigure(1, weight=1)

        tk.Label(controls, text="PROJECT", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        ttk.Entry(controls, textvariable=self.project_var).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Button(controls, text="Browse", style="Dark.TButton",
                   command=self.choose_project).grid(row=0, column=2, padx=(10, 0), pady=5)

        tk.Label(controls, text="PLATFORMIO", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        ttk.Entry(controls, textvariable=self.platformio_var).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Button(controls, text="Browse", style="Dark.TButton",
                   command=self.choose_platformio).grid(row=1, column=2, padx=(10, 0), pady=5)

        tk.Label(controls, text="ENV", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=2, column=0, sticky="w", padx=(0, 10), pady=5)
        row = tk.Frame(controls, bg=SURFACE)
        row.grid(row=2, column=1, sticky="w", pady=5)
        self.env_combo = ttk.Combobox(row, textvariable=self.env_var, state="readonly", width=22)
        self.env_combo.pack(side="left")
        self.env_combo.bind("<<ComboboxSelected>>", lambda _event: self.load_env_port())
        tk.Label(row, text="PORT", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left", padx=(18, 8))
        self.port_combo = ttk.Combobox(row, textvariable=self.port_var, width=24)
        self.port_combo.pack(side="left")
        ttk.Button(row, text="Refresh ports", style="Dark.TButton",
                   command=self.refresh_ports).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="Use ini port", style="Dark.TButton",
                   command=self.load_env_port).pack(side="left", padx=(8, 0))

        options = tk.Frame(panel, bg=CARD)
        options.pack(fill="x", padx=22, pady=(0, 16))
        tk.Checkbutton(options, text="Allow upload when PresetList.txt references missing JSON files",
                       variable=self.allow_missing_var, bg=CARD, fg=TEXT, selectcolor=CARD_ALT,
                       activebackground=CARD, activeforeground=TEXT,
                       font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=12)

        actions = tk.Frame(panel, bg=SURFACE)
        actions.pack(fill="x", padx=22, pady=(0, 16))
        self.validate_button = ttk.Button(actions, text="Validate data", style="Dark.TButton",
                                          command=self.validate_data)
        self.validate_button.pack(side="left")
        self.build_button = ttk.Button(actions, text="Build filesystem", style="Dark.TButton",
                                       command=lambda: self.run_targets(["buildfs"]))
        self.build_button.pack(side="left", padx=(8, 0))
        self.upload_button = ttk.Button(actions, text="Upload filesystem", style="Dark.TButton",
                                        command=lambda: self.run_targets(["uploadfs"]))
        self.upload_button.pack(side="left", padx=(8, 0))
        self.both_button = ttk.Button(actions, text="Build + upload", style="Gold.TButton",
                                      command=lambda: self.run_targets(["buildfs", "uploadfs"]))
        self.both_button.pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Open data folder", style="Dark.TButton",
                   command=self.open_data_folder).pack(side="right")

        log_header = tk.Frame(panel, bg=SURFACE)
        log_header.pack(fill="x", padx=22)
        tk.Label(log_header, text="PLATFORMIO OUTPUT", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left")
        ttk.Button(log_header, text="Clear log", style="Dark.TButton", command=self.clear_log).pack(side="right")
        self.log = tk.Text(panel, bg="#0b0d11", fg="#cbd0d8", insertbackground=TEXT,
                           relief="flat", highlightthickness=1, highlightbackground=BORDER,
                           font=("Consolas", 9), wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, padx=22, pady=(10, 22))

    def choose_project(self):
        folder = filedialog.askdirectory(title="Select Ignitron PlatformIO project", initialdir=self.project_var.get())
        if folder:
            self.app.set_project_dir(folder)
            self.load_project_defaults()

    def choose_platformio(self):
        filename = filedialog.askopenfilename(
            title="Select platformio.exe",
            initialdir=str(Path.home()),
            filetypes=(("Executables", "*.exe"), ("All files", "*.*")),
        )
        if filename:
            self.platformio_var.set(filename)

    def load_project_defaults(self):
        envs = parse_platformio_envs(self.platformio_ini)
        self.env_combo.configure(values=envs)
        if self.env_var.get() not in envs:
            self.env_var.set(envs[0])
        self.refresh_ports(select_first=False)
        self.load_env_port()
        self.app.set_status(f"Filesystem uploader ready: {self.project_dir}")

    def on_project_changed(self):
        self.load_project_defaults()

    def load_env_port(self):
        port = parse_platformio_upload_port(self.platformio_ini, self.env_var.get())
        if port:
            self.port_var.set(port)

    def refresh_ports(self, select_first=True):
        current = self.port_var.get().strip()
        values = []
        try:
            import serial.tools.list_ports
            ports = list(serial.tools.list_ports.comports())
            values = [f"{port.device}  |  {port.description}" for port in ports]
        except ImportError:
            values = []
        self.port_combo.configure(values=values)
        devices = [value.split("  |  ", 1)[0].strip() for value in values]
        if current in devices:
            self.port_var.set(current)
        elif select_first and values:
            self.port_var.set(devices[0])
        self.app.set_status(f"Found {len(values)} serial port(s)" if values else "No serial ports found")

    def selected_port(self):
        return self.port_var.get().split("  |  ", 1)[0].strip()

    def prepare_upload_after_builder_export(self):
        self.refresh_ports(select_first=True)
        if self.selected_port():
            self.app.set_status("Preset files exported. Choose the COM port, then click Upload filesystem.")
        else:
            self.app.set_status("Preset files exported. Connect Ignitron, refresh ports, then click Upload filesystem.")
            messagebox.showinfo(
                "Select COM port",
                "Preset files were exported.\n\nConnect Ignitron, choose its COM port on the Upload FS page, "
                "then click Upload filesystem or Build + upload.",
            )

    def open_data_folder(self):
        if self.data_dir.exists():
            open_folder(self.data_dir)
        else:
            messagebox.showerror("Data folder not found", f"No data folder exists at:\n{self.data_dir}")

    def append_log(self, text):
        self.after(0, self._append_log, text)

    def _append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def set_busy(self, busy):
        self.running = busy
        state = "disabled" if busy else "normal"
        for button in (self.validate_button, self.build_button, self.upload_button, self.both_button):
            button.configure(state=state)

    def validate_data(self, show_success=True):
        if not self.project_dir.exists():
            messagebox.showerror("Project not found", f"Project folder does not exist:\n{self.project_dir}")
            return False
        if not self.platformio_ini.exists():
            messagebox.showerror("platformio.ini not found", f"Missing file:\n{self.platformio_ini}")
            return False
        if not self.data_dir.exists():
            messagebox.showerror("Data folder not found", f"Missing folder:\n{self.data_dir}")
            return False

        json_count = len(list(self.data_dir.glob("*.json")))
        missing = preset_list_missing_files(self.data_dir)
        if missing:
            message = (
                f"Data folder: {self.data_dir}\n"
                f"JSON presets: {json_count}\n\n"
                "PresetList.txt references missing files:\n"
                + "\n".join(missing[:45])
            )
            if len(missing) > 45:
                message += f"\n...and {len(missing) - 45} more"
            if not self.allow_missing_var.get():
                messagebox.showerror("PresetList check failed", message)
                return False
            if show_success:
                messagebox.showwarning("PresetList warning", message)
            self.app.set_status(f"Data warning: {len(missing)} missing referenced file(s)")
            return True

        if show_success:
            messagebox.showinfo(
                "Data looks good",
                f"Data folder: {self.data_dir}\nJSON presets: {json_count}\n\nPresetList.txt references all required files.",
            )
        self.app.set_status(f"Data validated: {json_count} JSON preset file(s)")
        return True

    def run_targets(self, targets):
        if self.running:
            messagebox.showinfo("PlatformIO running", "A filesystem task is already running.")
            return
        if not self.validate_data(show_success=False):
            return
        if "uploadfs" in targets and not self.selected_port():
            self.refresh_ports(select_first=True)
            if not self.selected_port():
                messagebox.showinfo("Select COM port", "Choose the Ignitron COM port before uploading the filesystem.")
                return
        if self.open_pdf_after_success is None and "uploadfs" in targets:
            self.open_pdf_after_success = self.data_dir / "PresetList.pdf"
        self.set_busy(True)
        self.append_log("\n")
        self.app.set_status("Running PlatformIO filesystem task...")
        threading.Thread(target=self._run_targets_worker, args=(targets,), daemon=True).start()

    def _run_targets_worker(self, targets):
        try:
            for target in targets:
                code = self._run_platformio_target(target)
                if code != 0:
                    self.append_log(f"\n{target} failed with exit code {code}\n")
                    self.after(0, lambda t=target: self.app.set_status(f"{t} failed"))
                    return
            self.append_log("\nFilesystem task complete.\n")
            self.after(0, lambda: self.app.set_status("Filesystem upload workflow complete"))
            pdf_path = self.open_pdf_after_success
            self.open_pdf_after_success = None
            if pdf_path and Path(pdf_path).exists():
                self.after(0, lambda path=pdf_path: open_folder(path))
        finally:
            self.after(0, lambda: self.set_busy(False))

    def _run_platformio_target(self, target):
        cmd = [
            self.platformio_var.get(),
            "run",
            "-e",
            self.env_var.get(),
            "-t",
            target,
        ]
        port = self.selected_port()
        if target == "uploadfs" and port:
            cmd.extend(["--upload-port", port])

        self.append_log(f"> {' '.join(cmd)}\n")
        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(self.project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                bufsize=1,
            )
        except Exception as exc:
            self.append_log(f"Could not start PlatformIO: {exc}\n")
            return 1

        assert process.stdout is not None
        for line in process.stdout:
            self.append_log(line)
        return process.wait()


class FirmwareUploadPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.running = False
        self.project_var = self.app.project_dir_var
        self.platformio_var = tk.StringVar(value=default_platformio())
        self.env_var = tk.StringVar(value="esp32dev")
        self.port_var = tk.StringVar()
        self.speed_var = tk.StringVar(value="921600")
        self.clean_var = tk.BooleanVar(value=False)
        self.erase_var = tk.BooleanVar(value=False)
        self.build_only_var = tk.BooleanVar(value=False)
        self.upload_fs_after_var = tk.BooleanVar(value=False)
        self.fw_version_var = tk.StringVar()
        self.oled_driver_var = tk.StringVar(value="OLED_DRIVER_SH1106")
        self.battery_enabled_var = tk.BooleanVar(value=True)
        self.battery_type_var = tk.StringVar(value="BATTERY_TYPE_LI_ION")
        self.battery_cells_var = tk.StringVar(value="2")
        self.battery_adc_pin_var = tk.StringVar(value="36")
        self.battery_r1_var = tk.StringVar(value="22")
        self.battery_r2_var = tk.StringVar(value="10")
        self.fx_blink_var = tk.BooleanVar(value=False)
        self.amp_mode_rocker_switch_var = tk.BooleanVar(value=True)
        self.amp_mode_rocker_pin_var = tk.StringVar(value="35")
        self.dedicated_leds_var = tk.BooleanVar(value=False)
        self.long_press_var = tk.StringVar(value="1000")
        self.heading("Firmware Upload", "Build and upload Ignitron firmware with common PlatformIO options.")
        self._build()
        self.load_project_defaults()

    @property
    def project_dir(self):
        return Path(self.project_var.get()).expanduser().resolve()

    @property
    def platformio_ini(self):
        return self.project_dir / "platformio.ini"

    @property
    def firmware_config_path(self):
        return self.project_dir / "src" / "Config_Definitions.h"

    def _build(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=34, pady=(0, 30))

        upload_tab = tk.Frame(notebook, bg=BG)
        settings_tab = tk.Frame(notebook, bg=BG)
        notebook.add(upload_tab, text="Upload")
        notebook.add(settings_tab, text="Firmware Settings")

        panel = tk.Frame(upload_tab, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True)

        controls = tk.Frame(panel, bg=SURFACE)
        controls.pack(fill="x", padx=22, pady=20)
        controls.grid_columnconfigure(1, weight=1)

        tk.Label(controls, text="PROJECT", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        ttk.Entry(controls, textvariable=self.project_var).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Button(controls, text="Browse", style="Dark.TButton",
                   command=self.choose_project).grid(row=0, column=2, padx=(10, 0), pady=5)

        tk.Label(controls, text="PLATFORMIO", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        ttk.Entry(controls, textvariable=self.platformio_var).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Button(controls, text="Browse", style="Dark.TButton",
                   command=self.choose_platformio).grid(row=1, column=2, padx=(10, 0), pady=5)

        tk.Label(controls, text="ENV", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=2, column=0, sticky="w", padx=(0, 10), pady=5)
        row = tk.Frame(controls, bg=SURFACE)
        row.grid(row=2, column=1, sticky="w", pady=5)
        self.env_combo = ttk.Combobox(row, textvariable=self.env_var, state="readonly", width=20)
        self.env_combo.pack(side="left")
        self.env_combo.bind("<<ComboboxSelected>>", lambda _event: self.load_env_defaults())
        tk.Label(row, text="PORT", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left", padx=(18, 8))
        ttk.Entry(row, textvariable=self.port_var, width=16).pack(side="left")
        tk.Label(row, text="SPEED", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left", padx=(18, 8))
        ttk.Combobox(
            row,
            textvariable=self.speed_var,
            values=("115200", "460800", "921600"),
            width=10,
        ).pack(side="left")

        options = tk.Frame(panel, bg=CARD)
        options.pack(fill="x", padx=22, pady=(0, 16))
        for label, var in (
            ("Clean before build", self.clean_var),
            ("Build only, do not upload", self.build_only_var),
            ("Upload filesystem after firmware", self.upload_fs_after_var),
            ("Erase flash before upload", self.erase_var),
        ):
            tk.Checkbutton(options, text=label, variable=var, bg=CARD, fg=TEXT, selectcolor=CARD_ALT,
                           activebackground=CARD, activeforeground=TEXT,
                           font=("Segoe UI", 9)).pack(side="left", padx=(16, 6), pady=12)

        actions = tk.Frame(panel, bg=SURFACE)
        actions.pack(fill="x", padx=22, pady=(0, 16))
        self.build_button = ttk.Button(actions, text="Build firmware", style="Dark.TButton",
                                       command=lambda: self.run_workflow(build_only=True))
        self.build_button.pack(side="left")
        self.upload_button = ttk.Button(actions, text="Upload firmware", style="Gold.TButton",
                                        command=lambda: self.run_workflow(build_only=False))
        self.upload_button.pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Open project", style="Dark.TButton",
                   command=lambda: open_folder(self.project_dir)).pack(side="right")

        info = tk.Frame(panel, bg=CARD)
        info.pack(fill="x", padx=22, pady=(0, 16))
        tk.Label(
            info,
            text="Upload speed is saved to platformio.ini for the selected environment. Erase flash removes firmware and filesystem data before upload.",
            bg=CARD,
            fg=MUTED,
            justify="left",
            wraplength=950,
            font=("Segoe UI", 9),
            padx=16,
            pady=12,
        ).pack(anchor="w")

        log_header = tk.Frame(panel, bg=SURFACE)
        log_header.pack(fill="x", padx=22)
        tk.Label(log_header, text="PLATFORMIO OUTPUT", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left")
        ttk.Button(log_header, text="Clear log", style="Dark.TButton", command=self.clear_log).pack(side="right")
        self.log = tk.Text(panel, bg="#0b0d11", fg="#cbd0d8", insertbackground=TEXT,
                           relief="flat", highlightthickness=1, highlightbackground=BORDER,
                           font=("Consolas", 9), wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, padx=22, pady=(10, 22))

        self._build_settings_tab(settings_tab)

    def _build_settings_tab(self, parent):
        panel = tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True)

        top = tk.Frame(panel, bg=SURFACE)
        top.pack(fill="x", padx=22, pady=20)
        tk.Label(top, text="CONFIG FILE", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left")
        self.config_path_var = tk.StringVar(value=str(self.firmware_config_path))
        ttk.Entry(top, textvariable=self.config_path_var).pack(side="left", fill="x", expand=True, padx=12)
        ttk.Button(top, text="Reload", style="Dark.TButton", command=self.load_firmware_settings).pack(side="left")
        ttk.Button(top, text="Open config", style="Dark.TButton",
                   command=lambda: open_folder(self.firmware_config_path.parent)).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="Save settings", style="Gold.TButton",
                   command=self.save_firmware_settings).pack(side="right")

        grid = tk.Frame(panel, bg=SURFACE)
        grid.pack(fill="x", padx=22, pady=(0, 16))
        for column in range(4):
            grid.grid_columnconfigure(column, weight=1)

        self._setting_label(grid, "Firmware version", 0, 0)
        ttk.Entry(grid, textvariable=self.fw_version_var, width=18).grid(row=1, column=0, sticky="w", padx=(0, 18), pady=(0, 12))

        self._setting_label(grid, "OLED driver", 0, 1)
        ttk.Combobox(
            grid,
            textvariable=self.oled_driver_var,
            state="readonly",
            values=("OLED_DRIVER_SSD1306", "OLED_DRIVER_SH1106", "OLED_DRIVER_SH1107"),
            width=24,
        ).grid(row=1, column=1, sticky="w", padx=(0, 18), pady=(0, 12))

        self._setting_label(grid, "Long press ms", 0, 2)
        ttk.Entry(grid, textvariable=self.long_press_var, width=12).grid(row=1, column=2, sticky="w", padx=(0, 18), pady=(0, 12))

        tk.Checkbutton(grid, text="FX blink", variable=self.fx_blink_var,
                       bg=SURFACE, fg=TEXT, selectcolor=CARD_ALT,
                       activebackground=SURFACE, activeforeground=TEXT,
                       font=("Segoe UI", 9)).grid(row=1, column=3, sticky="w", pady=(0, 12))

        tk.Checkbutton(grid, text="AMP mode rocker switch installed", variable=self.amp_mode_rocker_switch_var,
                       bg=SURFACE, fg=TEXT, selectcolor=CARD_ALT,
                       activebackground=SURFACE, activeforeground=TEXT,
                       font=("Segoe UI", 9)).grid(row=2, column=1, columnspan=2, sticky="w", pady=(0, 12))
        self._setting_label(grid, "Rocker GPIO", 2, 3)
        ttk.Entry(grid, textvariable=self.amp_mode_rocker_pin_var, width=10).grid(
            row=3, column=3, sticky="w", padx=(0, 18), pady=(0, 12)
        )

        battery = tk.Frame(panel, bg=CARD)
        battery.pack(fill="x", padx=22, pady=(0, 16))
        tk.Label(battery, text="BATTERY", bg=CARD, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 8))
        tk.Checkbutton(battery, text="Enable battery status", variable=self.battery_enabled_var,
                       bg=CARD, fg=TEXT, selectcolor=CARD_ALT,
                       activebackground=CARD, activeforeground=TEXT,
                       font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 12))
        tk.Label(battery, text="Type", bg=CARD, fg=MUTED,
                 font=("Segoe UI Semibold", 8)).grid(row=0, column=1, sticky="w", padx=8, pady=(14, 8))
        ttk.Combobox(
            battery,
            textvariable=self.battery_type_var,
            state="readonly",
            values=("BATTERY_TYPE_LI_ION", "BATTERY_TYPE_LI_FE_PO4", "BATTERY_TYPE_AMP"),
            width=24,
        ).grid(row=1, column=1, sticky="w", padx=8, pady=(0, 12))
        for label, var, col, width in (
            ("Cells", self.battery_cells_var, 2, 8),
            ("ADC pin", self.battery_adc_pin_var, 3, 8),
            ("R1 kohm", self.battery_r1_var, 4, 10),
            ("R2 kohm", self.battery_r2_var, 5, 10),
        ):
            tk.Label(battery, text=label, bg=CARD, fg=MUTED,
                     font=("Segoe UI Semibold", 8)).grid(row=0, column=col, sticky="w", padx=8, pady=(14, 8))
            ttk.Entry(battery, textvariable=var, width=width).grid(row=1, column=col, sticky="w", padx=8, pady=(0, 12))

        leds = tk.Frame(panel, bg=CARD)
        leds.pack(fill="x", padx=22, pady=(0, 16))
        tk.Checkbutton(leds, text="Dedicated preset LEDs", variable=self.dedicated_leds_var,
                       bg=CARD, fg=TEXT, selectcolor=CARD_ALT,
                       activebackground=CARD, activeforeground=TEXT,
                       font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=12)

        note = tk.Frame(panel, bg=CARD)
        note.pack(fill="x", padx=22, pady=(0, 16))
        tk.Label(
            note,
            text="These settings modify src\\Config_Definitions.h. Save before building firmware. Only one OLED driver is enabled at a time.",
            bg=CARD,
            fg=MUTED,
            justify="left",
            wraplength=950,
            font=("Segoe UI", 9),
            padx=16,
            pady=12,
        ).pack(anchor="w")

    def _setting_label(self, parent, text, row, column):
        tk.Label(parent, text=text.upper(), bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=row, column=column, sticky="w", padx=(0, 18), pady=(0, 6))

    def choose_project(self):
        folder = filedialog.askdirectory(title="Select Ignitron PlatformIO project", initialdir=self.project_var.get())
        if folder:
            self.app.set_project_dir(folder)
            self.load_project_defaults()

    def choose_platformio(self):
        filename = filedialog.askopenfilename(
            title="Select platformio.exe",
            initialdir=str(Path.home()),
            filetypes=(("Executables", "*.exe"), ("All files", "*.*")),
        )
        if filename:
            self.platformio_var.set(filename)

    def load_project_defaults(self):
        envs = parse_platformio_envs(self.platformio_ini)
        self.env_combo.configure(values=envs)
        if self.env_var.get() not in envs:
            self.env_var.set(envs[0])
        self.load_env_defaults()
        self.config_path_var.set(str(self.firmware_config_path))
        self.load_firmware_settings(show_errors=False)

    def load_env_defaults(self):
        self.port_var.set(parse_platformio_upload_port(self.platformio_ini, self.env_var.get()))
        self.speed_var.set(parse_platformio_env_value(self.platformio_ini, self.env_var.get(), "upload_speed", "921600"))
        self.app.set_status(f"Firmware uploader ready: {self.project_dir}")

    def on_project_changed(self):
        self.load_project_defaults()

    def _config_text(self):
        return self.firmware_config_path.read_text(encoding="utf-8", errors="replace")

    def _is_define_enabled(self, text, name):
        return re.search(rf"^\s*#define\s+{re.escape(name)}\b", text, re.MULTILINE) is not None

    def _extract_define_value(self, text, name, default=""):
        match = re.search(rf"^\s*#define\s+{re.escape(name)}\s+([^\r\n/]+)", text, re.MULTILINE)
        return match.group(1).strip() if match else default

    def _extract_const_value(self, text, ctype, name, default=""):
        match = re.search(rf"^\s*const\s+{ctype}\s+{re.escape(name)}\s*=\s*([^;\r\n]+);", text, re.MULTILINE)
        return match.group(1).strip() if match else default

    def load_firmware_settings(self, show_errors=True):
        path = self.firmware_config_path
        if not path.exists():
            if show_errors:
                messagebox.showerror("Config not found", f"Missing firmware config:\n{path}")
            return False
        text = self._config_text()
        self.config_path_var.set(str(path))
        self.fw_version_var.set(self._extract_const_value(text, "string", "VERSION", "\"\"").strip('"'))
        for driver in ("OLED_DRIVER_SSD1306", "OLED_DRIVER_SH1106", "OLED_DRIVER_SH1107"):
            if self._is_define_enabled(text, driver):
                self.oled_driver_var.set(driver)
                break
        self.battery_enabled_var.set(self._is_define_enabled(text, "ENABLE_BATTERY_STATUS_INDICATOR"))
        self.battery_type_var.set(self._extract_define_value(text, "BATTERY_TYPE", "BATTERY_TYPE_LI_ION"))
        self.battery_cells_var.set(self._extract_const_value(text, "int", "BATTERY_CELLS", "2"))
        self.battery_adc_pin_var.set(self._extract_const_value(text, "int", "BATTERY_VOLTAGE_ADC_PIN", "36"))
        self.battery_r1_var.set(self._resistor_to_kohm(self._extract_const_value(text, "float", "VOLTAGE_DIVIDER_R1", "(22 * 1000)")))
        self.battery_r2_var.set(self._resistor_to_kohm(self._extract_const_value(text, "float", "VOLTAGE_DIVIDER_R2", "(10 * 1000)")))
        self.fx_blink_var.set(self._extract_const_value(text, "bool", "ENABLE_FX_BLINK", "false").lower() == "true")
        self.amp_mode_rocker_switch_var.set(self._is_define_enabled(text, "ENABLE_AMP_MODE_ROCKER_SWITCH"))
        self.amp_mode_rocker_pin_var.set(self._extract_const_value(text, "int", "AMP_MODE_SWITCH_PIN", "35"))
        self.dedicated_leds_var.set(self._is_define_enabled(text, "DEDICATED_PRESET_LEDS"))
        self.long_press_var.set(self._extract_const_value(text, "int", "LONG_BUTTON_PRESS_TIME", "1000"))
        self.app.set_status(f"Loaded firmware settings from {path}")
        return True

    def _resistor_to_kohm(self, value):
        match = re.search(r"([0-9.]+)\s*\*\s*1000", value)
        if match:
            return match.group(1)
        try:
            return str(float(value.strip("()")) / 1000.0)
        except Exception:
            return value

    def _validate_number(self, label, value, allow_float=False):
        try:
            number = float(value) if allow_float else int(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be a number") from exc
        if number <= 0:
            raise ValueError(f"{label} must be greater than zero")
        return number

    def save_firmware_settings(self):
        path = self.firmware_config_path
        if not path.exists():
            messagebox.showerror("Config not found", f"Missing firmware config:\n{path}")
            return False
        try:
            self._validate_number("Battery cells", self.battery_cells_var.get())
            self._validate_number("Battery ADC pin", self.battery_adc_pin_var.get())
            self._validate_number("R1 kohm", self.battery_r1_var.get(), allow_float=True)
            self._validate_number("R2 kohm", self.battery_r2_var.get(), allow_float=True)
            self._validate_number("Long press time", self.long_press_var.get())
            self._validate_number("Rocker GPIO", self.amp_mode_rocker_pin_var.get())
        except ValueError as exc:
            messagebox.showerror("Invalid firmware setting", str(exc))
            return False

        text = self._config_text()
        text = self._set_string_const(text, "VERSION", self.fw_version_var.get().strip() or "1.9.4")
        text = self._set_define_enabled(text, "ENABLE_BATTERY_STATUS_INDICATOR", self.battery_enabled_var.get())
        for driver in ("OLED_DRIVER_SSD1306", "OLED_DRIVER_SH1106", "OLED_DRIVER_SH1107"):
            text = self._set_define_enabled(text, driver, driver == self.oled_driver_var.get())
        text = self._set_define_value(text, "BATTERY_TYPE", self.battery_type_var.get())
        text = self._set_const_value(text, "int", "BATTERY_CELLS", self.battery_cells_var.get().strip())
        text = self._set_const_value(text, "int", "BATTERY_VOLTAGE_ADC_PIN", self.battery_adc_pin_var.get().strip())
        text = self._set_const_value(text, "float", "VOLTAGE_DIVIDER_R1", f"({self.battery_r1_var.get().strip()} * 1000)")
        text = self._set_const_value(text, "float", "VOLTAGE_DIVIDER_R2", f"({self.battery_r2_var.get().strip()} * 1000)")
        text = self._set_const_value(text, "bool", "ENABLE_FX_BLINK", "true" if self.fx_blink_var.get() else "false")
        text = self._set_define_enabled(text, "ENABLE_AMP_MODE_ROCKER_SWITCH", self.amp_mode_rocker_switch_var.get())
        text = self._set_const_value(text, "int", "AMP_MODE_SWITCH_PIN", self.amp_mode_rocker_pin_var.get().strip())
        text = self._set_define_enabled(text, "DEDICATED_PRESET_LEDS", self.dedicated_leds_var.get())
        text = self._set_const_value(text, "int", "LONG_BUTTON_PRESS_TIME", self.long_press_var.get().strip())

        backup = path.with_suffix(path.suffix + ".bak")
        backup.write_text(self._config_text(), encoding="utf-8")
        path.write_text(text, encoding="utf-8")
        self.app.set_status(f"Saved firmware settings to {path}")
        messagebox.showinfo("Firmware settings saved", f"Updated:\n{path}\n\nBackup:\n{backup}")
        return True

    def _set_define_enabled(self, text, name, enabled):
        pattern = rf"^(\s*)(//\s*)?#define\s+{re.escape(name)}\b(.*)$"
        replacement = rf"\1#define {name}\3" if enabled else rf"\1// #define {name}\3"
        new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
        if count:
            return new_text
        line = f"#define {name}" if enabled else f"// #define {name}"
        return text.rstrip() + "\n" + line + "\n"

    def _set_define_value(self, text, name, value):
        pattern = rf"^(\s*#define\s+{re.escape(name)}\s+)([^\r\n/]+)(.*)$"
        new_text, count = re.subn(pattern, rf"\g<1>{value}\3", text, count=1, flags=re.MULTILINE)
        if count:
            return new_text
        return text.rstrip() + f"\n#define {name} {value}\n"

    def _set_const_value(self, text, ctype, name, value):
        pattern = rf"^(\s*const\s+{ctype}\s+{re.escape(name)}\s*=\s*)([^;\r\n]+)(;.*)$"
        new_text, count = re.subn(pattern, rf"\g<1>{value}\3", text, count=1, flags=re.MULTILINE)
        if count:
            return new_text
        return text.rstrip() + f"\nconst {ctype} {name} = {value};\n"

    def _set_string_const(self, text, name, value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return self._set_const_value(text, "string", name, f'"{escaped}"')

    def append_log(self, text):
        self.after(0, self._append_log, text)

    def _append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def set_busy(self, busy):
        self.running = busy
        state = "disabled" if busy else "normal"
        self.build_button.configure(state=state)
        self.upload_button.configure(state=state)

    def validate_project(self):
        if not self.project_dir.exists():
            messagebox.showerror("Project not found", f"Project folder does not exist:\n{self.project_dir}")
            return False
        if not self.platformio_ini.exists():
            messagebox.showerror("platformio.ini not found", f"Missing file:\n{self.platformio_ini}")
            return False
        if self.erase_var.get() and not messagebox.askyesno(
                "Erase flash",
                "Erase flash will remove firmware and filesystem data before upload. Continue?"):
            return False
        return True

    def run_workflow(self, build_only):
        if self.running:
            messagebox.showinfo("PlatformIO running", "A firmware task is already running.")
            return
        if not self.validate_project():
            return
        if not build_only and not self.build_only_var.get():
            self.write_env_upload_speed()
        self.set_busy(True)
        self.append_log("\n")
        self.app.set_status("Running PlatformIO firmware task...")
        threading.Thread(target=self._run_workflow_worker, args=(build_only,), daemon=True).start()

    def _run_workflow_worker(self, build_only):
        try:
            targets = []
            if self.clean_var.get():
                targets.append("clean")
            if self.erase_var.get() and not build_only:
                targets.append("erase")
            targets.append(None if build_only or self.build_only_var.get() else "upload")
            if self.upload_fs_after_var.get() and not build_only and not self.build_only_var.get():
                targets.append("uploadfs")

            for target in targets:
                code = self._run_platformio_target(target)
                if code != 0:
                    label = target or "build"
                    self.append_log(f"\n{label} failed with exit code {code}\n")
                    self.after(0, lambda name=label: self.app.set_status(f"Firmware {name} failed"))
                    return
            self.append_log("\nFirmware workflow complete.\n")
            self.after(0, lambda: self.app.set_status("Firmware workflow complete"))
        finally:
            self.after(0, lambda: self.set_busy(False))

    def _run_platformio_target(self, target):
        cmd = [self.platformio_var.get(), "run", "-e", self.env_var.get()]
        if target:
            cmd.extend(["-t", target])

        port = self.port_var.get().strip()
        if target in ("upload", "uploadfs", "erase") and port:
            cmd.extend(["--upload-port", port])

        self.append_log(f"> {' '.join(cmd)}\n")
        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(self.project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                bufsize=1,
            )
        except Exception as exc:
            self.append_log(f"Could not start PlatformIO: {exc}\n")
            return 1

        assert process.stdout is not None
        for line in process.stdout:
            self.append_log(line)
        return process.wait()

    def write_env_upload_speed(self):
        speed = self.speed_var.get().strip()
        if not speed:
            return
        path = self.platformio_ini
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        section = f"[env:{self.env_var.get()}]"
        section_index = None
        next_section_index = len(lines)
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped == section:
                section_index = index
                continue
            if section_index is not None and index > section_index and stripped.startswith("[") and stripped.endswith("]"):
                next_section_index = index
                break
        if section_index is None:
            lines.extend(["", section, f"upload_speed = {speed}"])
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.append_log(f"Set upload_speed = {speed} in {section}\n")
            return

        for index in range(section_index + 1, next_section_index):
            raw = lines[index]
            code = raw.split(";", 1)[0].strip()
            if code.startswith("upload_speed") and "=" in code:
                prefix = raw[:len(raw) - len(raw.lstrip())]
                comment = ""
                if ";" in raw:
                    comment = "  ;" + raw.split(";", 1)[1]
                lines[index] = f"{prefix}upload_speed = {speed}{comment}"
                path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                self.append_log(f"Set upload_speed = {speed} in {section}\n")
                return

        insert_at = next_section_index
        lines.insert(insert_at, f"upload_speed = {speed}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.append_log(f"Set upload_speed = {speed} in {section}\n")


class SerialPage(Page):
    tool_title = "Serial tool"
    tool_subtitle = "Connect to Ignitron over USB."

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.running = False
        self.stop_event = threading.Event()
        self.port_var = tk.StringVar()
        self.heading(self.tool_title, self.tool_subtitle)
        self._build_serial_ui()
        self.refresh_ports()

    def _build_serial_ui(self):
        panel = tk.Frame(self, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True, padx=34, pady=(0, 30))
        controls = tk.Frame(panel, bg=SURFACE)
        controls.pack(fill="x", padx=22, pady=20)
        tk.Label(controls, text="USB PORT", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left")
        self.port_combo = ttk.Combobox(controls, textvariable=self.port_var, state="readonly", width=42)
        self.port_combo.pack(side="left", padx=12)
        ttk.Button(controls, text="Refresh", style="Dark.TButton", command=self.refresh_ports).pack(side="left")
        self.start_button = ttk.Button(controls, text=self.start_text, style="Gold.TButton", command=self.start)
        self.start_button.pack(side="right")

        info = tk.Frame(panel, bg=CARD)
        info.pack(fill="x", padx=22, pady=(0, 16))
        tk.Label(info, text=self.instructions, bg=CARD, fg=MUTED, justify="left",
                 wraplength=850, font=("Segoe UI", 9), padx=16, pady=13).pack(anchor="w")

        log_header = tk.Frame(panel, bg=SURFACE)
        log_header.pack(fill="x", padx=22)
        tk.Label(log_header, text="ACTIVITY", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left")
        ttk.Button(log_header, text="Clear log", style="Dark.TButton", command=self.clear_log).pack(side="right")
        self.log = tk.Text(panel, bg="#0b0d11", fg="#cbd0d8", insertbackground=TEXT,
                           relief="flat", highlightthickness=1, highlightbackground=BORDER,
                           font=("Consolas", 9), wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, padx=22, pady=(10, 22))

    def refresh_ports(self):
        try:
            import serial.tools.list_ports
            ports = list(serial.tools.list_ports.comports())
            values = [f"{port.device}  |  {port.description}" for port in ports]
        except ImportError:
            values = []
            self.append_log("PySerial is not installed. Install requirements.txt first.\n")
        self.port_combo["values"] = values
        if values:
            self.port_combo.current(0)
            self.app.set_status(f"Found {len(values)} serial port(s)")
        else:
            self.port_var.set("")
            self.app.set_status("No serial ports found")

    def selected_port(self):
        return self.port_var.get().split("  |  ", 1)[0].strip()

    def append_log(self, text):
        self.after(0, self._append_log, text)

    def _append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def start(self):
        port = self.selected_port()
        if not port:
            messagebox.showinfo("Select a port", "Connect Ignitron and select its USB port.")
            return
        if self.running:
            return
        self.running = True
        self.stop_event.clear()
        self.start_button.configure(state="disabled")
        threading.Thread(target=self.run_tool, args=(port,), daemon=True).start()

    def finish(self):
        self.running = False
        self.stop_event.set()
        self.start_button.configure(state="normal")


class PullerPage(SerialPage):
    tool_title = "Pedal Preset Puller"
    tool_subtitle = "Back up presets currently stored on your Ignitron pedal."
    start_text = "Start backup"
    instructions = "Put the pedal in AMP mode before starting. The backup saves all presets into a new timestamped folder beside this application."

    def _build_serial_ui(self):
        self.active_only = tk.BooleanVar(value=True)
        super()._build_serial_ui()
        option = tk.Checkbutton(self.start_button.master, text="Only active bank presets", variable=self.active_only,
                                bg=SURFACE, fg=TEXT, selectcolor=CARD_ALT, activebackground=SURFACE,
                                activeforeground=TEXT, font=("Segoe UI", 9))
        option.pack(side="right", padx=16)

    def run_tool(self, port):
        self.append_log(f"Starting backup from {port}...\n")
        try:
            backup_root = self.app.project_dir / "backups"
            backup_root.mkdir(parents=True, exist_ok=True)
            self.append_log(f"Saving backups to {backup_root}\n")
            module_path = app_dir() / "preset_puller.py"
            spec = importlib.util.spec_from_file_location("ignitron_puller", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            stream = StdoutQueue(self.append_log)
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                module.pull_presets(port, 115200, self.active_only.get(), False, backup_root)
            self.append_log("\nBackup complete.\n")
            open_folder(backup_root)
            self.app.set_status("Pedal backup completed")
        except Exception as exc:
            self.append_log(f"\nBackup failed: {exc}\n")
            self.app.set_status("Pedal backup failed")
        finally:
            self.after(0, self.finish)


class CapturePage(SerialPage):
    tool_title = "Spark App Capture"
    tool_subtitle = "Capture presets streamed from the Spark app through Ignitron."
    start_text = "Start capture"
    instructions = "Connect Ignitron by USB and keep it connected to the Spark app over Bluetooth. Send presets from the app; each unique preset is saved automatically. Use End connection to stop capture."

    def _build_serial_ui(self):
        super()._build_serial_ui()
        self.stop_button = ttk.Button(
            self.start_button.master,
            text="End connection",
            style="Danger.TButton",
            command=self.stop_capture,
            state="disabled",
        )
        self.stop_button.pack(side="right", padx=(0, 10))

    def start(self):
        super().start()
        if self.running:
            self.stop_button.configure(state="normal")

    def stop_capture(self):
        if not self.running:
            return
        self.append_log("\nEnding Spark capture connection...\n")
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self.app.set_status("Stopping Spark capture...")

    def finish(self):
        super().finish()
        self.stop_button.configure(state="disabled")

    def run_tool(self, port):
        self.append_log(f"Listening on {port} at 115200 baud...\n")
        session = self.app.project_dir / "captures" / time.strftime("presets_%Y%m%d_%H%M%S")
        session.mkdir(parents=True, exist_ok=True)
        self.append_log(f"Saving captures to {session}\n\n")
        connection = None
        try:
            import serial
            connection = serial.Serial(port, 115200, timeout=0.5)
            buffer = ""
            capturing = False
            last_uuid = None
            while self.winfo_exists() and not self.stop_event.is_set():
                line = connection.readline().decode(errors="ignore").rstrip()
                if not line:
                    continue
                self.append_log(line + "\n")
                if line.startswith("received from app:") or line.startswith("JSON STRING:"):
                    buffer = ""
                    capturing = True
                    continue
                if capturing:
                    buffer += line + "\n"
                    if line.strip().endswith("}"):
                        capturing = False
                        try:
                            preset = json.loads(buffer)
                            uuid = preset.get("UUID")
                            if uuid == last_uuid:
                                continue
                            last_uuid = uuid
                            name = re.sub(r"[^A-Za-z0-9_-]+", "", str(preset.get("Name", "preset"))) or "preset"
                            output = session / f"{name}.json"
                            output.write_text(json.dumps(preset, indent=2), encoding="utf-8")
                            self.append_log(f"SAVED: {output.name}\n")
                            self.app.set_status(f"Captured {output.name}")
                        except Exception as exc:
                            self.append_log(f"Could not parse preset: {exc}\n")
            self.append_log("\nSpark capture connection ended.\n")
            self.app.set_status("Spark capture stopped")
        except Exception as exc:
            self.append_log(f"\nCapture failed: {exc}\n")
            self.app.set_status("Spark capture failed")
        finally:
            try:
                if connection:
                    connection.close()
            except Exception:
                pass
            self.after(0, self.finish)


if __name__ == "__main__":
    IgnitronApp().mainloop()
