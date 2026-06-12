"""
settings_dialog.py
Modal settings panel for configuring API keys and default model.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFrame, QTabWidget, QWidget,
    QFormLayout, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core import OPENROUTER_MODEL_NAMES, OPENROUTER_MODELS, GEMINI_MODEL_NAMES, GEMINI_MODELS


class SettingsDialog(QDialog):
    """
    Two-tab dialog: one tab per provider (Gemini / OpenRouter).
    Returns updated settings via .get_settings().
    """

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = dict(settings)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._build_ui()
        self._load_values()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 20)

        # Header
        title = QLabel("API Settings")
        title.setFont(QFont("", 15, QFont.Weight.DemiBold))
        layout.addWidget(title)

        subtitle = QLabel(
            "Keys are saved locally to ~/.ai_translator_settings.json "
            "or loaded from environment variables."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)

        # Tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.tabs.addTab(self._gemini_tab(), "Gemini")
        self.tabs.addTab(self._openrouter_tab(), "OpenRouter")

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._on_save)
        save_btn.setDefault(True)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _gemini_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(0, 16, 0, 8)
        form.setLabelAlignment(Qt.AlignRight)

        self.gemini_key_edit = self._key_field("GEMINI_API_KEY")
        form.addRow("API Key:", self.gemini_key_edit)

        self.gemini_model_combo = QComboBox()
        for model_id in GEMINI_MODEL_NAMES:
            label = GEMINI_MODELS[model_id]
            self.gemini_model_combo.addItem(f"{label}  ({model_id})", userData=model_id)
        self.gemini_model_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        form.addRow("Default model:", self.gemini_model_combo)

        note = QLabel(
            'Get a free key at <a href="https://aistudio.google.com/apikey">'
            "aistudio.google.com</a>"
        )
        note.setOpenExternalLinks(True)
        note.setObjectName("linkNote")
        form.addRow("", note)
        return w

    def _openrouter_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(0, 16, 0, 8)
        form.setLabelAlignment(Qt.AlignRight)

        self.or_key_edit = self._key_field("OPENROUTER_API_KEY")
        form.addRow("API Key:", self.or_key_edit)

        self.or_model_combo = QComboBox()
        for model_id in OPENROUTER_MODEL_NAMES:
            label = OPENROUTER_MODELS[model_id]
            self.or_model_combo.addItem(f"{label}  ({model_id})", userData=model_id)
        self.or_model_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        form.addRow("Default model:", self.or_model_combo)

        note = QLabel(
            'Get a key at <a href="https://openrouter.ai/keys">openrouter.ai</a>'
        )
        note.setOpenExternalLinks(True)
        note.setObjectName("linkNote")
        form.addRow("", note)
        return w

    @staticmethod
    def _key_field(placeholder: str) -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setEchoMode(QLineEdit.Password)
        field.setMinimumWidth(300)
        return field

    # ── Data binding ──────────────────────────────────────────────────────────

    def _load_values(self):
        self.gemini_key_edit.setText(self.settings.get("gemini_api_key", ""))

        gemini_model = self.settings.get("gemini_model", GEMINI_MODEL_NAMES[0])
        g_idx = self.gemini_model_combo.findData(gemini_model)
        if g_idx >= 0:
            self.gemini_model_combo.setCurrentIndex(g_idx)

        self.or_key_edit.setText(self.settings.get("openrouter_api_key", ""))
        model = self.settings.get("openrouter_model", OPENROUTER_MODEL_NAMES[0])
        idx = self.or_model_combo.findData(model)
        if idx >= 0:
            self.or_model_combo.setCurrentIndex(idx)

        # Open the relevant tab
        provider = self.settings.get("provider", "Gemini")
        self.tabs.setCurrentIndex(0 if provider == "Gemini" else 1)

    def _on_save(self):
        self.settings["gemini_api_key"] = self.gemini_key_edit.text().strip()
        self.settings["gemini_model"] = self.gemini_model_combo.currentData()
        self.settings["openrouter_api_key"] = self.or_key_edit.text().strip()
        self.settings["openrouter_model"] = self.or_model_combo.currentData()
        self.accept()

    def get_settings(self) -> dict:
        return self.settings
