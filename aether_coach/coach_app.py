from __future__ import annotations

import json
import os
import platform
import queue
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Optional

import customtkinter as ctk
import cv2
import mss
import numpy as np
import ollama
import pyautogui
import pyperclip
import pytesseract
from PIL import Image, ImageTk

try:
    import speech_recognition as sr
except Exception:  # optional runtime feature
    sr = None

APP_NAME = "Aether Coach"
APP_VERSION = "1.0.0"
DATA_DIR = Path.home() / ".aether_coach"
DATA_DIR.mkdir(exist_ok=True)
CONFIG_PATH = DATA_DIR / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "model": "llama3.2:latest",
    "style": "Interview Prep",
    "interval_seconds": 5.0,
    "monitor_index": 1,
    "ocr_min_chars": 40,
    "max_context_chars": 2400,
    "privacy_redaction": True,
    "always_on_top": False,
    "transparent_overlay": False,
    "ollama_host": "http://localhost:11434",
}

STYLE_PROMPTS = {
    "Encouraging Coach": "Be warm, concise, confidence-building, and practical.",
    "Direct Feedback": "Be blunt, concise, strategic, and action-oriented. No fluff.",
    "Interview Prep": "Help the user answer clearly, use STAR framing, sound credible, and avoid rambling.",
    "Study Buddy": "Explain the visible content, quiz lightly, and suggest the next learning step.",
    "Meeting Copilot": "Extract decisions, risks, action items, and useful things to say next.",
    "Sales / Pitch Coach": "Improve positioning, objection handling, benefits, and closing language.",
    "Confidence Builder": "Reduce anxiety and provide one next sentence or action the user can use now.",
}

SENSITIVE_PATTERNS = [
    (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN_REDACTED]"),
    (r"\b(?:\d[ -]*?){13,16}\b", "[CARD_REDACTED]"),
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[EMAIL_REDACTED]"),
]

@dataclass
class SessionEntry:
    timestamp: str
    style: str
    model: str
    context_excerpt: str
    feedback: str
    ocr_chars: int


def load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            return {**DEFAULT_CONFIG, **loaded}
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config: dict[str, Any]) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def detect_tesseract() -> Optional[str]:
    env_path = os.environ.get("TESSERACT_CMD")
    candidates = [
        env_path,
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        "/usr/bin/tesseract",
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def redact_sensitive(text: str) -> str:
    import re
    redacted = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        redacted = re.sub(pattern, replacement, redacted)
    return redacted


def preprocess_for_ocr(image: Image.Image) -> np.ndarray:
    arr = np.array(image)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 50, 50)
    gray = cv2.convertScaleAbs(gray, alpha=1.25, beta=8)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh


class AetherCoach(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.title(f"{APP_NAME} — Private Local AI Coach")
        self.geometry("1320x880")
        self.minsize(1120, 720)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.is_monitoring = False
        self.is_paused = False
        self.stop_event = threading.Event()
        self.feedback_queue: queue.Queue[str] = queue.Queue()
        self.session_log: list[SessionEntry] = []
        self.monitor_thread: Optional[threading.Thread] = None
        self.preview_ref: Optional[ImageTk.PhotoImage] = None
        self.available_models: list[str] = [self.config["model"]]
        self.last_ocr_hash: Optional[int] = None

        tesseract_path = detect_tesseract()
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

        self.setup_ui()
        self.after(250, self.process_queue)
        threading.Thread(target=self.bootstrap_services, daemon=True).start()

    def setup_ui(self) -> None:
        self.configure(fg_color="#090b10")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self, width=300, corner_radius=0, fg_color="#0c1018")
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(sidebar, text="AETHER", font=ctk.CTkFont(size=36, weight="bold"), text_color="#38d9ff").pack(pady=(34, 0))
        ctk.CTkLabel(sidebar, text="LOCAL REAL-TIME COACH", font=ctk.CTkFont(size=13, weight="bold"), text_color="#7f8ea3").pack(pady=(0, 26))

        self.model_var = ctk.StringVar(value=self.config["model"])
        self.style_var = ctk.StringVar(value=self.config["style"])
        self.privacy_var = ctk.BooleanVar(value=bool(self.config["privacy_redaction"]))
        self.top_var = ctk.BooleanVar(value=bool(self.config["always_on_top"]))

        self._side_label(sidebar, "Ollama Model")
        self.model_menu = ctk.CTkOptionMenu(sidebar, values=self.available_models, variable=self.model_var, width=245)
        self.model_menu.pack(padx=25, pady=(0, 12))

        self._side_label(sidebar, "Coaching Mode")
        self.style_menu = ctk.CTkOptionMenu(sidebar, values=list(STYLE_PROMPTS), variable=self.style_var, width=245)
        self.style_menu.pack(padx=25, pady=(0, 12))

        self._side_label(sidebar, "Capture Interval")
        self.interval_slider = ctk.CTkSlider(sidebar, from_=2, to=20, number_of_steps=18, command=self.update_interval)
        self.interval_slider.set(float(self.config["interval_seconds"]))
        self.interval_slider.pack(padx=25, fill="x")
        self.interval_label = ctk.CTkLabel(sidebar, text=f"{self.config['interval_seconds']:.1f} seconds", text_color="#aeb8c8")
        self.interval_label.pack(pady=(4, 14))

        self.start_btn = ctk.CTkButton(sidebar, text="START MONITORING", height=52, font=ctk.CTkFont(size=15, weight="bold"), fg_color="#00a878", hover_color="#008f67", command=self.toggle_monitoring)
        self.start_btn.pack(pady=(18, 8), padx=25, fill="x")
        self.pause_btn = ctk.CTkButton(sidebar, text="PAUSE", height=38, state="disabled", command=self.toggle_pause)
        self.pause_btn.pack(pady=6, padx=25, fill="x")
        ctk.CTkButton(sidebar, text="Manual Analyze Now", command=self.manual_analyze).pack(pady=6, padx=25, fill="x")
        ctk.CTkButton(sidebar, text="Copy Latest Feedback", command=self.copy_latest_feedback).pack(pady=6, padx=25, fill="x")
        ctk.CTkButton(sidebar, text="Clear Log", command=self.clear_log).pack(pady=6, padx=25, fill="x")
        ctk.CTkButton(sidebar, text="Export JSON Session", command=self.export_log).pack(pady=6, padx=25, fill="x")

        ctk.CTkSwitch(sidebar, text="Redact emails/cards/SSNs", variable=self.privacy_var, command=self.persist_settings).pack(anchor="w", padx=25, pady=(20, 4))
        ctk.CTkSwitch(sidebar, text="Always on top", variable=self.top_var, command=self.toggle_topmost).pack(anchor="w", padx=25, pady=4)

        ctk.CTkLabel(sidebar, text=f"v{APP_VERSION} • Local only", text_color="#657083").pack(side="bottom", pady=18)

        main = ctk.CTkFrame(self, fg_color="#10141d", corner_radius=18)
        main.grid(row=0, column=1, sticky="nsew", padx=14, pady=14)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 6))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Private Contextual Feedback", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, sticky="w")
        self.status_badge = ctk.CTkLabel(header, text="Booting", fg_color="#303848", corner_radius=14, padx=14, pady=6)
        self.status_badge.grid(row=0, column=1, sticky="e")

        preview_frame = ctk.CTkFrame(main, height=270, fg_color="#151b27", corner_radius=16)
        preview_frame.grid(row=1, column=0, sticky="ew", padx=18, pady=10)
        preview_frame.grid_propagate(False)
        ctk.CTkLabel(preview_frame, text="Live Screen Preview", font=ctk.CTkFont(size=16, weight="bold"), text_color="#d9e2f1").pack(anchor="w", padx=16, pady=(12, 4))
        self.preview_label = ctk.CTkLabel(preview_frame, text="Preview appears here after monitoring starts", height=205, fg_color="#0a0d13", corner_radius=12)
        self.preview_label.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        self.feedback_text = ctk.CTkTextbox(main, wrap="word", font=ctk.CTkFont(size=15), fg_color="#090d14", border_width=1, border_color="#222a38")
        self.feedback_text.grid(row=2, column=0, sticky="nsew", padx=18, pady=(8, 18))
        self.log("Ready. Start monitoring or run a manual analysis.", "System")

        self.status_bar = ctk.CTkLabel(self, text="Ready", anchor="w", height=28, fg_color="#080a0e", text_color="#9aa8bd")
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

    @staticmethod
    def _side_label(parent: ctk.CTkFrame, text: str) -> None:
        ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=13, weight="bold"), text_color="#c6d2e1").pack(anchor="w", padx=25, pady=(10, 5))

    def bootstrap_services(self) -> None:
        self.check_tesseract()
        self.check_ollama()

    def check_tesseract(self) -> None:
        try:
            version = pytesseract.get_tesseract_version()
            self.queue_status(f"OCR ready • Tesseract {version}")
        except Exception:
            self.queue_status("OCR not found. Install Tesseract or set TESSERACT_CMD.", warn=True)

    def check_ollama(self) -> None:
        try:
            client = ollama.Client(host=self.config["ollama_host"])
            listing = client.list()
            models = []
            for item in listing.get("models", []):
                name = item.get("name") or item.get("model")
                if name:
                    models.append(name)
            if models:
                self.available_models = models
                if self.model_var.get() not in models:
                    self.model_var.set(models[0])
                self.after(0, lambda: self.model_menu.configure(values=models))
            self.queue_status("Connected to local Ollama")
            self.after(0, lambda: self.status_badge.configure(text="Ollama Online", fg_color="#116149"))
        except Exception as exc:
            self.queue_status(f"Ollama offline. Run `ollama serve`. {exc}", warn=True)
            self.after(0, lambda: self.status_badge.configure(text="Ollama Offline", fg_color="#7a4a12"))

    def queue_status(self, text: str, warn: bool = False) -> None:
        self.after(0, lambda: self.status_bar.configure(text=text, text_color="#ffcc66" if warn else "#9ee6c6"))

    def update_interval(self, value: float) -> None:
        self.config["interval_seconds"] = round(float(value), 1)
        self.interval_label.configure(text=f"{self.config['interval_seconds']:.1f} seconds")
        self.persist_settings()

    def persist_settings(self) -> None:
        self.config.update({
            "model": self.model_var.get(),
            "style": self.style_var.get(),
            "privacy_redaction": bool(self.privacy_var.get()),
            "always_on_top": bool(self.top_var.get()),
        })
        save_config(self.config)

    def toggle_topmost(self) -> None:
        self.attributes("-topmost", bool(self.top_var.get()))
        self.persist_settings()

    def toggle_monitoring(self) -> None:
        if self.is_monitoring:
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def start_monitoring(self) -> None:
        self.persist_settings()
        self.is_monitoring = True
        self.is_paused = False
        self.stop_event.clear()
        self.start_btn.configure(text="STOP MONITORING", fg_color="#d94f4f", hover_color="#b83f3f")
        self.pause_btn.configure(state="normal", text="PAUSE")
        self.status_badge.configure(text="Monitoring", fg_color="#116149")
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.log("Monitoring started. Screen OCR is processed locally.", "System")

    def stop_monitoring(self) -> None:
        self.is_monitoring = False
        self.stop_event.set()
        self.start_btn.configure(text="START MONITORING", fg_color="#00a878", hover_color="#008f67")
        self.pause_btn.configure(state="disabled", text="PAUSE")
        self.status_badge.configure(text="Stopped", fg_color="#303848")
        self.log("Monitoring stopped.", "System")

    def toggle_pause(self) -> None:
        self.is_paused = not self.is_paused
        self.pause_btn.configure(text="RESUME" if self.is_paused else "PAUSE")
        self.status_badge.configure(text="Paused" if self.is_paused else "Monitoring")

    def manual_analyze(self) -> None:
        threading.Thread(target=self.capture_analyze_once, daemon=True).start()

    def monitor_loop(self) -> None:
        while not self.stop_event.is_set():
            if not self.is_paused:
                self.capture_analyze_once()
            self.stop_event.wait(float(self.config["interval_seconds"]))

    def capture_analyze_once(self) -> None:
        try:
            image = self.capture_screen()
            self.update_preview_async(image)
            text = self.extract_text(image)
            if self.privacy_var.get():
                text = redact_sensitive(text)
            compact = " ".join(text.split())
            if len(compact) < int(self.config["ocr_min_chars"]):
                self.queue_status("OCR saw too little readable text; waiting for clearer content.", warn=True)
                return
            h = hash(compact[:1200])
            if h == self.last_ocr_hash and self.is_monitoring:
                self.queue_status("Context unchanged; skipped duplicate LLM call.")
                return
            self.last_ocr_hash = h
            feedback = self.get_ai_feedback(compact[: int(self.config["max_context_chars"])])
            self.feedback_queue.put(feedback)
            self.session_log.append(SessionEntry(
                timestamp=datetime.now().isoformat(timespec="seconds"),
                style=self.style_var.get(),
                model=self.model_var.get(),
                context_excerpt=compact[:500],
                feedback=feedback,
                ocr_chars=len(compact),
            ))
        except Exception as exc:
            self.feedback_queue.put(f"Capture/analyze error: {exc}")

    def capture_screen(self) -> Image.Image:
        with mss.mss() as sct:
            monitor_index = int(self.config.get("monitor_index", 1))
            monitor_index = max(1, min(monitor_index, len(sct.monitors) - 1))
            shot = sct.grab(sct.monitors[monitor_index])
            return Image.frombytes("RGB", shot.size, shot.rgb)

    def update_preview_async(self, image: Image.Image) -> None:
        preview = image.copy()
        preview.thumbnail((900, 210))
        photo = ImageTk.PhotoImage(preview)
        self.after(0, lambda p=photo: self.update_preview(p))

    def update_preview(self, photo: ImageTk.PhotoImage) -> None:
        self.preview_ref = photo
        self.preview_label.configure(image=photo, text="")

    def extract_text(self, image: Image.Image) -> str:
        processed = preprocess_for_ocr(image)
        custom_config = "--oem 3 --psm 6"
        return pytesseract.image_to_string(processed, config=custom_config).strip()

    def get_ai_feedback(self, screen_text: str) -> str:
        style = self.style_var.get()
        style_instruction = STYLE_PROMPTS.get(style, STYLE_PROMPTS["Direct Feedback"])
        prompt = f"""You are Aether Coach, a private real-time local AI coach running on the user's own machine.

Mode: {style}
Style instruction: {style_instruction}

Visible OCR context:
---
{screen_text}
---

Return only useful coaching. Keep it short: 2-5 sentences.
Prefer specific next actions, exact phrasing the user can say, or a concise study/interview tactic.
Do not mention OCR unless text is unreadable. Do not claim to see images beyond the text provided.
"""
        try:
            client = ollama.Client(host=self.config["ollama_host"])
            response = client.chat(
                model=self.model_var.get(),
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.35, "num_ctx": 4096},
            )
            return response["message"]["content"].strip()
        except Exception as exc:
            return f"[Ollama Error] {exc}"

    def process_queue(self) -> None:
        while not self.feedback_queue.empty():
            self.log(self.feedback_queue.get(), "Coach")
        self.after(350, self.process_queue)

    def log(self, message: str, source: str = "Coach") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.feedback_text.insert("end", f"[{timestamp}] {source}\n{message}\n\n")
        self.feedback_text.see("end")

    def copy_latest_feedback(self) -> None:
        if not self.session_log:
            messagebox.showinfo("No feedback", "No coach feedback has been generated yet.")
            return
        pyperclip.copy(self.session_log[-1].feedback)
        self.queue_status("Latest feedback copied to clipboard.")

    def clear_log(self) -> None:
        self.feedback_text.delete("1.0", "end")
        self.log("Feedback log cleared.", "System")

    def export_log(self) -> None:
        if not self.session_log:
            messagebox.showinfo("Empty", "No session data to export.")
            return
        default_name = f"aether_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile=default_name, filetypes=[("JSON", "*.json")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump([asdict(entry) for entry in self.session_log], f, indent=2, ensure_ascii=False)
        messagebox.showinfo("Export complete", f"Session saved to:\n{path}")

    def on_close(self) -> None:
        self.stop_event.set()
        self.persist_settings()
        self.destroy()


if __name__ == "__main__":
    if platform.system() == "Windows":
        try:
            pyautogui.FAILSAFE = True
        except Exception:
            pass
    app = AetherCoach()
    app.mainloop()
