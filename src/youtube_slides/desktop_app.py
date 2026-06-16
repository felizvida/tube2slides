from __future__ import annotations

import sys
from pathlib import Path

from .desktop_workflow import DesktopJobConfig, DesktopJobResult, run_desktop_job
from .openai_narrative import DEFAULT_OPENAI_MODEL


APP_STYLE = """
QMainWindow {
    background: #f7f4ee;
}
QWidget {
    color: #171615;
    font-family: "SF Pro Text", "Inter", "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}
QLabel#AppTitle {
    font-size: 34px;
    font-weight: 700;
    color: #151412;
}
QLabel#Subtitle {
    color: #716b62;
    font-size: 14px;
}
QLabel#PanelTitle {
    color: #171615;
    font-size: 16px;
    font-weight: 650;
}
QLabel#PanelHint {
    color: #837b70;
    font-size: 12px;
}
QLabel#FieldLabel {
    color: #4a453f;
    font-weight: 600;
}
QLabel#StatusPill {
    background: #ebe4d8;
    border: 1px solid #ddd2c2;
    border-radius: 14px;
    color: #5b5147;
    padding: 6px 12px;
    font-weight: 650;
}
QFrame#Panel {
    background: #fffdfa;
    border: 1px solid #e4dace;
    border-radius: 18px;
}
QFrame#DarkPanel {
    background: #181715;
    border-radius: 18px;
}
QFrame#Divider {
    background: #e4dace;
    min-height: 1px;
    max-height: 1px;
}
QLineEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox {
    background: #fffdfa;
    border: 1px solid #d9cfc1;
    border-radius: 10px;
    padding: 9px 11px;
    min-height: 22px;
    selection-background-color: #181715;
}
QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {
    border: 1px solid #171615;
}
QComboBox::drop-down {
    border: 0;
    width: 28px;
}
QCheckBox {
    color: #332f2a;
    spacing: 9px;
}
QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border-radius: 5px;
    border: 1px solid #c9bbaa;
    background: #fffdfa;
}
QCheckBox::indicator:checked {
    background: #171615;
    border: 1px solid #171615;
}
QPushButton {
    border: 1px solid #d8ccbc;
    border-radius: 12px;
    padding: 10px 15px;
    background: #fffdfa;
    color: #171615;
    font-weight: 650;
}
QPushButton:hover {
    background: #f0e8dd;
}
QPushButton:disabled {
    color: #a59a8d;
    background: #eee7dd;
}
QPushButton#PrimaryButton {
    background: #171615;
    border: 1px solid #171615;
    color: #fffdfa;
    padding: 12px 20px;
}
QPushButton#PrimaryButton:hover {
    background: #302d28;
}
QPushButton#GhostButton {
    background: transparent;
}
QTextEdit {
    background: #201f1c;
    border: 1px solid #201f1c;
    border-radius: 14px;
    color: #f4efe7;
    padding: 14px;
    font-family: "SF Mono", "Cascadia Mono", Consolas, monospace;
    font-size: 12px;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #746b5f;
    border-radius: 5px;
}
"""


def main() -> int:
    try:
        from PySide6.QtCore import QThread, Qt, QUrl, Signal
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QFileDialog,
            QFrame,
            QGridLayout,
            QHBoxLayout,
            QInputDialog,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QSizePolicy,
            QSpinBox,
            QDoubleSpinBox,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except Exception as exc:
        print("PySide6 is required for the desktop app. Install with: pip install -e '.[desktop]'", file=sys.stderr)
        print(exc, file=sys.stderr)
        return 1

    class Worker(QThread):
        log_message = Signal(str)
        succeeded = Signal(object)
        failed = Signal(str)

        def __init__(self, config: DesktopJobConfig) -> None:
            super().__init__()
            self.config = config

        def run(self) -> None:
            try:
                result = run_desktop_job(self.config, log=self.log_message.emit)
            except Exception as exc:
                self.failed.emit(str(exc))
            else:
                self.succeeded.emit(result)

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("Slidewright")
            self.setMinimumSize(980, 660)
            self.resize(1060, 720)
            self.worker: Worker | None = None
            self.last_result: DesktopJobResult | None = None

            self.source_input = QLineEdit()
            self.source_input.setPlaceholderText("YouTube URL or local video file")

            self.output_input = QLineEdit(str(Path.home() / "Lecture Slides"))
            self.output_input.setPlaceholderText("Output folder")

            self.sample_interval = QDoubleSpinBox()
            self.sample_interval.setRange(0.5, 20.0)
            self.sample_interval.setSingleStep(0.5)
            self.sample_interval.setValue(2.0)
            self.sample_interval.setSuffix(" sec")

            self.min_stable = QSpinBox()
            self.min_stable.setRange(1, 10)
            self.min_stable.setValue(2)

            self.cookie_browser = QComboBox()
            self.cookie_browser.addItem("None", None)
            self.cookie_browser.addItem("Chrome", "chrome")
            self.cookie_browser.addItem("Edge", "edge")
            self.cookie_browser.addItem("Firefox", "firefox")
            self.cookie_browser.addItem("Safari", "safari")
            self.cookie_browser.addItem("Brave", "brave")

            self.narrative_mode = QComboBox()
            self.narrative_mode.addItem("No notes", "none")
            self.narrative_mode.addItem("Caption notes", "captions")
            self.narrative_mode.addItem("AI narrative", "ai")
            self.narrative_mode.setCurrentIndex(1)
            self.narrative_mode.currentIndexChanged.connect(self.update_narrative_controls)

            self.openai_model_input = QLineEdit(DEFAULT_OPENAI_MODEL)
            self.openai_model_input.setPlaceholderText("OpenAI model")

            self.create_pptx = QCheckBox("PowerPoint deck")
            self.create_pptx.setChecked(True)
            self.create_reading_view = QCheckBox("HTML reading view")
            self.create_reading_view.setChecked(True)

            browse_video = QPushButton("Browse")
            browse_video.setObjectName("GhostButton")
            browse_video.clicked.connect(self.choose_video)
            browse_output = QPushButton("Choose")
            browse_output.setObjectName("GhostButton")
            browse_output.clicked.connect(self.choose_output)

            self.start_button = QPushButton("Extract")
            self.start_button.setObjectName("PrimaryButton")
            self.start_button.clicked.connect(self.start_job)
            self.open_output_button = QPushButton("Open Output")
            self.open_output_button.setEnabled(False)
            self.open_output_button.clicked.connect(self.open_last_output)

            self.status_label = QLabel("Ready")
            self.status_label.setObjectName("StatusPill")
            self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self.log = QTextEdit()
            self.log.setReadOnly(True)
            self.log.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            self.log.setPlaceholderText("Run progress")

            root = QVBoxLayout()
            root.setContentsMargins(30, 28, 30, 28)
            root.setSpacing(22)

            header = QHBoxLayout()
            header.setSpacing(18)
            header_text = QVBoxLayout()
            title = QLabel("Slidewright")
            title.setObjectName("AppTitle")
            subtitle = QLabel("YouTube lectures to crafted PowerPoint decks")
            subtitle.setObjectName("Subtitle")
            header_text.addWidget(title)
            header_text.addWidget(subtitle)
            header.addLayout(header_text, 1)
            header.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignTop)
            root.addLayout(header)

            main_area = QHBoxLayout()
            main_area.setSpacing(18)
            main_area.addLayout(self.build_left_column(browse_video, browse_output), 2)
            main_area.addWidget(self.build_progress_panel(), 3)
            root.addLayout(main_area, 1)

            container = QWidget()
            container.setLayout(root)
            self.setCentralWidget(container)
            self.update_narrative_controls()

        def build_left_column(self, browse_video: QPushButton, browse_output: QPushButton) -> QVBoxLayout:
            column = QVBoxLayout()
            column.setSpacing(16)
            column.addWidget(self.build_source_panel(browse_video, browse_output))
            column.addWidget(self.build_options_panel())
            column.addStretch(1)
            return column

        def build_source_panel(self, browse_video: QPushButton, browse_output: QPushButton) -> QFrame:
            panel, layout = self.panel("Lecture")
            layout.addLayout(self.field_row("Source", self.source_input, browse_video))
            layout.addLayout(self.field_row("Save to", self.output_input, browse_output))
            return panel

        def build_options_panel(self) -> QFrame:
            panel, layout = self.panel("Run Settings")
            grid = QGridLayout()
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(12)
            grid.addWidget(self.field_label("Sample every"), 0, 0)
            grid.addWidget(self.sample_interval, 0, 1)
            grid.addWidget(self.field_label("Stable frames"), 1, 0)
            grid.addWidget(self.min_stable, 1, 1)
            layout.addLayout(grid)
            layout.addLayout(self.field_row("Cookies", self.cookie_browser))
            layout.addWidget(self.divider())
            layout.addLayout(self.field_row("Narrative", self.narrative_mode))
            layout.addLayout(self.field_row("Model", self.openai_model_input))
            layout.addWidget(self.divider())
            layout.addWidget(self.field_label("Outputs"))
            layout.addWidget(self.create_pptx)
            layout.addWidget(self.create_reading_view)
            return panel

        def build_progress_panel(self) -> QFrame:
            panel = QFrame()
            panel.setObjectName("DarkPanel")
            panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(14)
            title = QLabel("Progress")
            title.setStyleSheet("color: #fffdfa; font-size: 17px; font-weight: 700;")
            hint = QLabel("Job details and output paths appear here")
            hint.setStyleSheet("color: #b9ac9b;")
            layout.addWidget(title)
            layout.addWidget(hint)
            layout.addWidget(self.log, 1)
            buttons = QHBoxLayout()
            buttons.addWidget(self.start_button)
            buttons.addWidget(self.open_output_button)
            buttons.addStretch(1)
            layout.addLayout(buttons)
            return panel

        def panel(self, title_text: str) -> tuple[QFrame, QVBoxLayout]:
            panel = QFrame()
            panel.setObjectName("Panel")
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(18, 18, 18, 18)
            layout.setSpacing(13)
            title = QLabel(title_text)
            title.setObjectName("PanelTitle")
            layout.addWidget(title)
            return panel, layout

        def field_row(
            self,
            label_text: str,
            widget: QWidget,
            trailing: QWidget | None = None,
        ) -> QHBoxLayout:
            row = QHBoxLayout()
            row.setSpacing(10)
            label = self.field_label(label_text)
            label.setFixedWidth(76)
            row.addWidget(label)
            row.addWidget(widget, 1)
            if trailing is not None:
                row.addWidget(trailing)
            return row

        def field_label(self, text: str) -> QLabel:
            label = QLabel(text)
            label.setObjectName("FieldLabel")
            return label

        def divider(self) -> QFrame:
            line = QFrame()
            line.setObjectName("Divider")
            line.setFrameShape(QFrame.Shape.NoFrame)
            return line

        def choose_video(self) -> None:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Choose local video",
                str(Path.home()),
                "Video Files (*.mp4 *.mov *.mkv *.webm *.m4v);;All Files (*)",
            )
            if path:
                self.source_input.setText(path)

        def choose_output(self) -> None:
            path = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_input.text())
            if path:
                self.output_input.setText(path)

        def update_narrative_controls(self) -> None:
            ai_selected = self.current_narrative_mode() == "ai"
            self.openai_model_input.setEnabled(ai_selected)

        def current_narrative_mode(self) -> str:
            return str(self.narrative_mode.currentData())

        def current_cookie_browser(self) -> str | None:
            value = self.cookie_browser.currentData()
            return str(value) if value else None

        def start_job(self) -> None:
            source = self.source_input.text().strip()
            output = self.output_input.text().strip()
            if not source:
                QMessageBox.warning(self, "Missing source", "Paste a YouTube URL or choose a local video.")
                return
            if not output:
                QMessageBox.warning(self, "Missing output folder", "Choose an output folder.")
                return
            if not self.create_pptx.isChecked() and not self.create_reading_view.isChecked():
                QMessageBox.warning(self, "No outputs selected", "Choose at least one output format.")
                return

            api_key = None
            if self.current_narrative_mode() == "ai":
                api_key, ok = QInputDialog.getText(
                    self,
                    "OpenAI API Key",
                    "OpenAI API key for this run only:",
                    QLineEdit.EchoMode.Password,
                )
                if not ok:
                    return
                api_key = api_key.strip()
                if not api_key:
                    QMessageBox.warning(self, "Missing API key", "AI narrative generation needs an OpenAI API key.")
                    return

            config = DesktopJobConfig(
                source=source,
                output_root=Path(output).expanduser(),
                sample_interval=float(self.sample_interval.value()),
                min_stable_samples=int(self.min_stable.value()),
                cookie_browser=self.current_cookie_browser(),
                narrative_mode=self.current_narrative_mode(),
                openai_api_key=api_key,
                openai_model=self.openai_model_input.text().strip() or DEFAULT_OPENAI_MODEL,
                create_pptx=self.create_pptx.isChecked(),
                create_reading_view=self.create_reading_view.isChecked(),
            )
            self.log.clear()
            self.append_log("Starting job...")
            self.status_label.setText("Running")
            self.start_button.setEnabled(False)
            self.open_output_button.setEnabled(False)
            self.worker = Worker(config)
            self.worker.log_message.connect(self.append_log)
            self.worker.succeeded.connect(self.job_succeeded)
            self.worker.failed.connect(self.job_failed)
            self.worker.start()

        def append_log(self, message: str) -> None:
            self.log.append(message)
            self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

        def job_succeeded(self, result: DesktopJobResult) -> None:
            self.last_result = result
            self.status_label.setText("Finished")
            self.start_button.setEnabled(True)
            self.open_output_button.setEnabled(True)
            self.append_log("")
            self.append_log(f"Slides: {len(result.extraction.slides)}")
            self.append_log(f"Notes: {result.notes_count}")
            if result.pptx_path:
                self.append_log(f"PowerPoint: {result.pptx_path}")
            if result.reading_view_path:
                self.append_log(f"Reading view: {result.reading_view_path}")
            QMessageBox.information(self, "Finished", f"Saved lecture slides to:\n{result.job_dir}")

        def job_failed(self, message: str) -> None:
            self.status_label.setText("Failed")
            self.start_button.setEnabled(True)
            self.open_output_button.setEnabled(self.last_result is not None)
            self.append_log(f"Error: {message}")
            QMessageBox.critical(self, "Extraction failed", message)

        def open_last_output(self) -> None:
            if self.last_result is None:
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_result.job_dir)))

    if "--smoke-test" in sys.argv:
        print("desktop app smoke test ok")
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName("Slidewright")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
