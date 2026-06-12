"""
main_window.py
Main application window — the entire translator UI.
Handles layout, event wiring, threading, and clipboard operations.
"""

import threading

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QPushButton, QComboBox, QFrame,
    QSizePolicy, QApplication, QToolButton, QProgressBar,
    QSpacerItem, QStackedWidget,
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QSize
from PySide6.QtGui import QFont, QIcon, QColor, QPalette, QTextCursor

from core import (
    GeminiTranslator, OpenRouterTranslator, TranslationError,
    LANGUAGE_NAMES,
    GEMINI_MODELS, GEMINI_MODEL_NAMES,
    OPENROUTER_MODELS, OPENROUTER_MODEL_NAMES,
    load_settings, save_settings,
)
from ui.settings_dialog import SettingsDialog


# ── Worker signals (cross-thread communication) ───────────────────────────────

class WorkerSignals(QObject):
    finished = Signal(str)   # translated text
    error = Signal(str)      # error message


# ── Reusable section frame ────────────────────────────────────────────────────

class PanelFrame(QFrame):
    """A card-like frame used for the source and target text areas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panelFrame")
        self.setFrameShape(QFrame.NoFrame)


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self._translation_in_progress = False
        self.setWindowTitle("AI Translator")
        self.resize(
            self.settings.get("window_width", 980),
            self.settings.get("window_height", 680),
        )
        self.setMinimumSize(720, 520)

        self._build_ui()
        self._apply_styles()
        self._restore_settings()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setSpacing(0)
        root_layout.setContentsMargins(0, 0, 0, 0)

        # ── Top bar ──────────────────────────────────────────────────────────
        root_layout.addWidget(self._build_topbar())

        # ── Toolbar row (provider + langs + translate button) ────────────────
        root_layout.addWidget(self._build_toolbar())

        # ── Progress / status strip ──────────────────────────────────────────
        root_layout.addWidget(self._build_status_bar())

        # ── Main panels (source | target) ────────────────────────────────────
        panels = QWidget()
        panels.setObjectName("panelsArea")
        panels_layout = QHBoxLayout(panels)
        panels_layout.setSpacing(12)
        panels_layout.setContentsMargins(16, 12, 16, 16)

        panels_layout.addWidget(self._build_source_panel(), stretch=1)
        panels_layout.addWidget(self._build_target_panel(), stretch=1)

        root_layout.addWidget(panels, stretch=1)

    # ── Top bar ───────────────────────────────────────────────────────────────

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topBar")
        bar.setFixedHeight(52)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 0, 16, 0)
        layout.setSpacing(8)

        # Logo / app name
        logo = QLabel("⟺")
        logo.setObjectName("logoIcon")
        layout.addWidget(logo)

        name = QLabel("AI Translator")
        name.setObjectName("appName")
        layout.addWidget(name)

        layout.addStretch()

        # Settings gear button
        settings_btn = QToolButton()
        settings_btn.setObjectName("iconBtn")
        settings_btn.setText("⚙")
        settings_btn.setToolTip("Open Settings")
        settings_btn.setFixedSize(36, 36)
        settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(settings_btn)

        return bar

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("toolbar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(10)

        # Provider selector
        prov_label = QLabel("Provider")
        prov_label.setObjectName("toolbarLabel")
        layout.addWidget(prov_label)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Gemini", "OpenRouter"])
        self.provider_combo.setFixedWidth(130)
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        layout.addWidget(self.provider_combo)

        # Gemini model selector (visible only when Gemini is selected)
        self.gemini_model_combo = QComboBox()
        for model_id in GEMINI_MODEL_NAMES:
            label = GEMINI_MODELS[model_id]
            self.gemini_model_combo.addItem(label, userData=model_id)
        self.gemini_model_combo.setFixedWidth(230)
        self.gemini_model_combo.setVisible(True)   # shown by default (Gemini is default)
        layout.addWidget(self.gemini_model_combo)

        # OpenRouter model selector (hidden when Gemini selected)
        self.model_combo = QComboBox()
        for model_id in OPENROUTER_MODEL_NAMES:
            label = OPENROUTER_MODELS[model_id]
            self.model_combo.addItem(label, userData=model_id)
        self.model_combo.setFixedWidth(200)
        self.model_combo.setVisible(False)
        layout.addWidget(self.model_combo)

        # Divider
        layout.addWidget(self._vdivider())

        # Source language
        src_label = QLabel("From")
        src_label.setObjectName("toolbarLabel")
        layout.addWidget(src_label)

        self.source_lang_combo = QComboBox()
        self.source_lang_combo.addItems(LANGUAGE_NAMES)
        self.source_lang_combo.setFixedWidth(150)
        layout.addWidget(self.source_lang_combo)

        # Swap button
        swap_btn = QToolButton()
        swap_btn.setObjectName("swapBtn")
        swap_btn.setText("⇄")
        swap_btn.setToolTip("Swap languages")
        swap_btn.setFixedSize(32, 32)
        swap_btn.clicked.connect(self._swap_languages)
        layout.addWidget(swap_btn)

        # Target language
        tgt_label = QLabel("To")
        tgt_label.setObjectName("toolbarLabel")
        layout.addWidget(tgt_label)

        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems(
            [lang for lang in LANGUAGE_NAMES if lang != "Auto-detect"]
        )
        self.target_lang_combo.setFixedWidth(150)
        layout.addWidget(self.target_lang_combo)

        layout.addStretch()

        # Translate button
        self.translate_btn = QPushButton("  Translate  ")
        self.translate_btn.setObjectName("translateBtn")
        self.translate_btn.setFixedHeight(36)
        self.translate_btn.clicked.connect(self._start_translation)
        layout.addWidget(self.translate_btn)

        return bar

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_status_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("statusBar")
        bar.setFixedHeight(28)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(12)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # Char count
        self.char_count_label = QLabel("0 characters")
        self.char_count_label.setObjectName("charCount")
        layout.addWidget(self.char_count_label)

        return bar

    # ── Source panel ──────────────────────────────────────────────────────────

    def _build_source_panel(self) -> QWidget:
        panel = PanelFrame()
        layout = QVBoxLayout(panel)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Panel header
        header = QWidget()
        header.setObjectName("panelHeader")
        hlayout = QHBoxLayout(header)
        hlayout.setContentsMargins(12, 8, 8, 8)

        lbl = QLabel("Source Text")
        lbl.setObjectName("panelTitle")
        hlayout.addWidget(lbl)
        hlayout.addStretch()

        # Clear button
        clear_btn = QToolButton()
        clear_btn.setObjectName("ghostBtn")
        clear_btn.setText("✕ Clear")
        clear_btn.clicked.connect(lambda: self.source_edit.clear())
        hlayout.addWidget(clear_btn)

        layout.addWidget(header)

        # Divider line
        layout.addWidget(self._hdivider())

        # Text area
        self.source_edit = QTextEdit()
        self.source_edit.setObjectName("sourceEdit")
        self.source_edit.setPlaceholderText(
            "Enter text to translate…\n\n"
            "Tip: press Ctrl+Enter to translate quickly."
        )
        self.source_edit.setAcceptRichText(False)
        self.source_edit.textChanged.connect(self._on_source_changed)
        layout.addWidget(self.source_edit, stretch=1)

        return panel

    # ── Target panel ──────────────────────────────────────────────────────────

    def _build_target_panel(self) -> QWidget:
        panel = PanelFrame()
        layout = QVBoxLayout(panel)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Panel header
        header = QWidget()
        header.setObjectName("panelHeader")
        hlayout = QHBoxLayout(header)
        hlayout.setContentsMargins(12, 8, 8, 8)

        lbl = QLabel("Translation")
        lbl.setObjectName("panelTitle")
        hlayout.addWidget(lbl)
        hlayout.addStretch()

        # Copy button
        self.copy_btn = QToolButton()
        self.copy_btn.setObjectName("ghostBtn")
        self.copy_btn.setText("⎘ Copy")
        self.copy_btn.clicked.connect(self._copy_translation)
        hlayout.addWidget(self.copy_btn)

        layout.addWidget(header)
        layout.addWidget(self._hdivider())

        # Output area (read-only)
        self.target_edit = QTextEdit()
        self.target_edit.setObjectName("targetEdit")
        self.target_edit.setReadOnly(True)
        self.target_edit.setPlaceholderText("Translation will appear here…")
        layout.addWidget(self.target_edit, stretch=1)

        return panel

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _vdivider() -> QFrame:
        d = QFrame()
        d.setFrameShape(QFrame.VLine)
        d.setObjectName("divider")
        return d

    @staticmethod
    def _hdivider() -> QFrame:
        d = QFrame()
        d.setFrameShape(QFrame.HLine)
        d.setObjectName("divider")
        return d

    # ── Event handlers ────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        """Ctrl+Enter triggers translation from anywhere in the window."""
        if (
            event.key() == Qt.Key_Return
            and event.modifiers() & Qt.ControlModifier
        ):
            self._start_translation()
        else:
            super().keyPressEvent(event)

    def _on_source_changed(self):
        text = self.source_edit.toPlainText()
        count = len(text)
        self.char_count_label.setText(f"{count:,} character{'s' if count != 1 else ''}")

    def _on_provider_changed(self, provider: str):
        self.gemini_model_combo.setVisible(provider == "Gemini")
        self.model_combo.setVisible(provider == "OpenRouter")
        self.settings["provider"] = provider

    def _swap_languages(self):
        src = self.source_lang_combo.currentText()
        tgt = self.target_lang_combo.currentText()
        # Can't swap if source is Auto-detect
        if src == "Auto-detect":
            return
        src_idx = self.source_lang_combo.findText(tgt)
        tgt_idx = self.target_lang_combo.findText(src)
        if src_idx >= 0:
            self.source_lang_combo.setCurrentIndex(src_idx)
        if tgt_idx >= 0:
            self.target_lang_combo.setCurrentIndex(tgt_idx)
        # Also swap the text content
        src_text = self.source_edit.toPlainText()
        tgt_text = self.target_edit.toPlainText()
        self.source_edit.setPlainText(tgt_text)
        self.target_edit.setPlainText(src_text)

    def _open_settings(self):
        dlg = SettingsDialog(self.settings, parent=self)
        if dlg.exec():
            self.settings.update(dlg.get_settings())
            save_settings(self.settings)
            self._sync_gemini_model_combo()
            self._sync_model_combo()
            self._set_status("Settings saved.", "ok")

    def _copy_translation(self):
        text = self.target_edit.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self._set_status("Copied to clipboard.", "ok")
            # Flash the button label briefly
            self.copy_btn.setText("✓ Copied!")
            QTimer.singleShot(1500, lambda: self.copy_btn.setText("⎘ Copy"))

    def _set_status(self, message: str, kind: str = "info"):
        """
        Update the status strip.
        kind: 'info' | 'ok' | 'error' | 'busy'
        """
        icons = {"info": "●", "ok": "✓", "error": "✕", "busy": "◌"}
        self.status_label.setText(f"{icons.get(kind, '●')}  {message}")
        self.status_label.setProperty("statusKind", kind)
        # Force style re-evaluation
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    # ── Translation flow ──────────────────────────────────────────────────────

    def _start_translation(self):
        if self._translation_in_progress:
            return

        text = self.source_edit.toPlainText().strip()
        if not text:
            self._set_status("Enter some text to translate.", "info")
            return

        source_lang = self.source_lang_combo.currentText()
        target_lang = self.target_lang_combo.currentText()
        provider = self.provider_combo.currentText()

        # Save current choices
        self.settings["source_lang"] = source_lang
        self.settings["target_lang"] = target_lang
        self.settings["provider"] = provider

        # Build translator instance (validates key immediately)
        try:
            if provider == "Gemini":
                gemini_model = self.gemini_model_combo.currentData() or GEMINI_MODEL_NAMES[0]
                self.settings["gemini_model"] = gemini_model
                translator = GeminiTranslator(
                    api_key=self.settings.get("gemini_api_key") or None,
                    model=gemini_model,
                )
            else:
                model = self.model_combo.currentData() or OPENROUTER_MODEL_NAMES[0]
                self.settings["openrouter_model"] = model
                translator = OpenRouterTranslator(
                    api_key=self.settings.get("openrouter_api_key") or None,
                    model=model,
                )
        except TranslationError as exc:
            self._set_status(str(exc).splitlines()[0], "error")
            self.target_edit.setPlainText(f"⚠  Configuration error\n\n{exc}")
            return

        self._set_busy(True)
        signals = WorkerSignals()
        signals.finished.connect(self._on_translation_done)
        signals.error.connect(self._on_translation_error)

        def _worker():
            try:
                result = translator.translate(text, source_lang, target_lang)
                signals.finished.emit(result)
            except TranslationError as exc:
                signals.error.emit(str(exc))

        threading.Thread(target=_worker, daemon=True).start()

    def _set_busy(self, busy: bool):
        self._translation_in_progress = busy
        self.translate_btn.setEnabled(not busy)
        if busy:
            self.translate_btn.setText("  Translating…  ")
            self._set_status("Translating…", "busy")
            self.target_edit.setPlainText("")
        else:
            self.translate_btn.setText("  Translate  ")

    def _on_translation_done(self, result: str):
        self._set_busy(False)
        self.target_edit.setPlainText(result)
        self._set_status("Translation complete.", "ok")
        save_settings(self.settings)

    def _on_translation_error(self, message: str):
        self._set_busy(False)
        short = message.splitlines()[0][:80]
        self._set_status(f"Error: {short}", "error")
        self.target_edit.setPlainText(f"⚠  Translation failed\n\n{message}")

    # ── Settings restoration ──────────────────────────────────────────────────

    def _restore_settings(self):
        provider = self.settings.get("provider", "Gemini")
        idx = self.provider_combo.findText(provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)

        src = self.settings.get("source_lang", "Auto-detect")
        src_idx = self.source_lang_combo.findText(src)
        if src_idx >= 0:
            self.source_lang_combo.setCurrentIndex(src_idx)

        tgt = self.settings.get("target_lang", "English")
        tgt_idx = self.target_lang_combo.findText(tgt)
        if tgt_idx >= 0:
            self.target_lang_combo.setCurrentIndex(tgt_idx)

        self._sync_gemini_model_combo()
        self._sync_model_combo()

    def _sync_gemini_model_combo(self):
        model = self.settings.get("gemini_model", GEMINI_MODEL_NAMES[0])
        idx = self.gemini_model_combo.findData(model)
        if idx >= 0:
            self.gemini_model_combo.setCurrentIndex(idx)

    def _sync_model_combo(self):
        model = self.settings.get("openrouter_model", OPENROUTER_MODEL_NAMES[0])
        idx = self.model_combo.findData(model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

    # ── Stylesheet ────────────────────────────────────────────────────────────

    def _apply_styles(self):
        # Palette: slate-near-black bg, off-white surface, indigo accent
        self.setStyleSheet("""
        /* ── Window & global ──────────────────────────────────────── */
        QMainWindow, QWidget#centralWidget {
            background: #0f1117;
        }

        QWidget {
            font-family: -apple-system, 'Segoe UI', 'SF Pro Text', 'Inter', sans-serif;
            font-size: 13px;
            color: #e2e8f0;
        }

        /* ── Top bar ──────────────────────────────────────────────── */
        QWidget#topBar {
            background: #0f1117;
            border-bottom: 1px solid #1e2433;
        }

        QLabel#logoIcon {
            font-size: 20px;
            color: #6366f1;
            padding-right: 2px;
        }

        QLabel#appName {
            font-size: 15px;
            font-weight: 600;
            color: #f1f5f9;
            letter-spacing: 0.3px;
        }

        /* ── Toolbar ──────────────────────────────────────────────── */
        QWidget#toolbar {
            background: #141720;
            border-bottom: 1px solid #1e2433;
        }

        QLabel#toolbarLabel {
            color: #64748b;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.6px;
        }

        /* ── Status bar ───────────────────────────────────────────── */
        QWidget#statusBar {
            background: #0c0e14;
            border-top: 1px solid #1e2433;
        }

        QLabel#statusLabel {
            font-size: 12px;
            color: #64748b;
        }
        QLabel#statusLabel[statusKind="ok"]   { color: #22c55e; }
        QLabel#statusLabel[statusKind="error"]{ color: #ef4444; }
        QLabel#statusLabel[statusKind="busy"] { color: #6366f1; }

        QLabel#charCount {
            font-size: 11px;
            color: #334155;
        }

        /* ── Panels ───────────────────────────────────────────────── */
        QWidget#panelsArea {
            background: #0f1117;
        }

        QFrame#panelFrame {
            background: #141720;
            border: 1px solid #1e2433;
            border-radius: 10px;
        }

        QWidget#panelHeader {
            background: transparent;
            min-height: 36px;
        }

        QLabel#panelTitle {
            font-size: 11px;
            font-weight: 600;
            color: #475569;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }

        QFrame#divider {
            color: #1e2433;
            background: #1e2433;
            max-height: 1px;
            min-height: 1px;
            max-width: 1px;
            min-width: 1px;
            border: none;
        }

        /* ── Text areas ───────────────────────────────────────────── */
        QTextEdit#sourceEdit,
        QTextEdit#targetEdit {
            background: transparent;
            border: none;
            border-radius: 0px;
            padding: 14px 16px;
            font-size: 14px;
            line-height: 1.6;
            color: #e2e8f0;
            selection-background-color: #3730a3;
        }

        QTextEdit#targetEdit {
            color: #a5b4fc;
        }

        QTextEdit::placeholder {
            color: #334155;
        }

        /* Scrollbar */
        QScrollBar:vertical {
            background: transparent;
            width: 6px;
            margin: 0;
        }
        QScrollBar::handle:vertical {
            background: #2d3748;
            border-radius: 3px;
            min-height: 30px;
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical { height: 0; }

        /* ── Combo boxes ──────────────────────────────────────────── */
        QComboBox {
            background: #1e2433;
            border: 1px solid #2d3748;
            border-radius: 6px;
            padding: 4px 10px;
            color: #cbd5e1;
            min-height: 28px;
        }
        QComboBox:hover {
            border-color: #4f46e5;
        }
        QComboBox:focus {
            border-color: #6366f1;
            outline: none;
        }
        QComboBox::drop-down {
            border: none;
            width: 22px;
        }
        QComboBox::down-arrow {
            image: none;
            width: 0;
            height: 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid #64748b;
            margin-right: 6px;
        }
        QComboBox QAbstractItemView {
            background: #1e2433;
            border: 1px solid #2d3748;
            border-radius: 6px;
            selection-background-color: #3730a3;
            color: #cbd5e1;
            padding: 4px;
        }

        /* ── Buttons ──────────────────────────────────────────────── */
        QPushButton#translateBtn {
            background: #4f46e5;
            color: #fff;
            border: none;
            border-radius: 7px;
            font-size: 13px;
            font-weight: 600;
            padding: 0 20px;
            min-height: 36px;
            letter-spacing: 0.2px;
        }
        QPushButton#translateBtn:hover  { background: #4338ca; }
        QPushButton#translateBtn:pressed { background: #3730a3; }
        QPushButton#translateBtn:disabled {
            background: #2d3748;
            color: #475569;
        }

        QToolButton#iconBtn {
            background: transparent;
            border: none;
            border-radius: 6px;
            color: #64748b;
            font-size: 16px;
        }
        QToolButton#iconBtn:hover {
            background: #1e2433;
            color: #a5b4fc;
        }

        QToolButton#swapBtn {
            background: #1e2433;
            border: 1px solid #2d3748;
            border-radius: 6px;
            color: #64748b;
            font-size: 15px;
        }
        QToolButton#swapBtn:hover {
            background: #2d3748;
            color: #a5b4fc;
        }

        QToolButton#ghostBtn {
            background: transparent;
            border: 1px solid transparent;
            border-radius: 5px;
            color: #475569;
            font-size: 11px;
            padding: 2px 8px;
        }
        QToolButton#ghostBtn:hover {
            border-color: #2d3748;
            color: #94a3b8;
            background: #1e2433;
        }

        /* ── Settings dialog ──────────────────────────────────────── */
        QDialog {
            background: #141720;
        }
        QTabWidget::pane {
            border: 1px solid #1e2433;
            border-radius: 8px;
            background: #0f1117;
        }
        QTabBar::tab {
            background: transparent;
            border: none;
            padding: 8px 20px;
            color: #64748b;
            font-size: 13px;
        }
        QTabBar::tab:selected {
            color: #a5b4fc;
            border-bottom: 2px solid #6366f1;
        }
        QTabBar::tab:hover:!selected {
            color: #94a3b8;
        }
        QLineEdit {
            background: #1e2433;
            border: 1px solid #2d3748;
            border-radius: 6px;
            padding: 6px 10px;
            color: #e2e8f0;
            min-height: 28px;
        }
        QLineEdit:focus {
            border-color: #6366f1;
        }
        QLabel#subtitle {
            color: #475569;
            font-size: 12px;
        }
        QLabel#linkNote {
            color: #475569;
            font-size: 11px;
        }
        QLabel#linkNote a {
            color: #6366f1;
        }
        QPushButton#primaryBtn {
            background: #4f46e5;
            color: #fff;
            border: none;
            border-radius: 6px;
            font-weight: 600;
            padding: 6px 20px;
            min-height: 32px;
        }
        QPushButton#primaryBtn:hover { background: #4338ca; }
        QPushButton#cancelBtn {
            background: #1e2433;
            color: #94a3b8;
            border: 1px solid #2d3748;
            border-radius: 6px;
            padding: 6px 20px;
            min-height: 32px;
        }
        QPushButton#cancelBtn:hover { background: #2d3748; }

        QFormLayout QLabel {
            color: #64748b;
            font-size: 12px;
        }
        """)
