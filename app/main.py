import os
import sys
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QProcess, Signal
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QComboBox, QSlider, QLineEdit, QProgressBar, QGroupBox, QSplitter,
    QCheckBox, QFrame, QStyle
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget


APP_NAME = "JASS Creator Studio"
VERSION = "0.1.0"

PRESETS = {
    "YouTube Shorts": {"width": 1080, "height": 1920},
    "Facebook Stories": {"width": 1080, "height": 1920},
    "Instagram Stories": {"width": 1080, "height": 1920},
    "Keep original size": {"width": 0, "height": 0},
}


def find_ffmpeg():
    return shutil.which("ffmpeg")


def format_time(ms):
    seconds = max(0, int(ms / 1000))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


class CreatorStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{VERSION}")
        self.resize(1280, 820)
        self.setMinimumSize(980, 650)

        self.video_paths = []
        self.current_path = None
        self.duration_ms = 0
        self.ffmpeg_process = None

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)

        self._build_ui()
        self._connect_signals()
        self._apply_theme()
        self._check_ffmpeg()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(12)

        header = QHBoxLayout()
        brand = QVBoxLayout()
        title = QLabel("JASS Creator Studio")
        title.setObjectName("appTitle")
        subtitle = QLabel("Cut • Join • Create vertical videos")
        subtitle.setObjectName("subtitle")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        header.addLayout(brand)
        header.addStretch()
        self.ffmpeg_status = QLabel("Checking FFmpeg…")
        self.ffmpeg_status.setObjectName("statusPill")
        header.addWidget(self.ffmpeg_status)
        outer.addLayout(header)

        top_split = QSplitter(Qt.Horizontal)
        top_split.setChildrenCollapsible(False)

        # Preview
        preview_panel = QFrame()
        preview_panel.setObjectName("panel")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_header = QHBoxLayout()
        preview_header.addWidget(QLabel("PREVIEW"))
        preview_header.addStretch()
        self.preview_format = QLabel("9:16 · 1080 × 1920")
        self.preview_format.setObjectName("muted")
        preview_header.addWidget(self.preview_format)
        preview_layout.addLayout(preview_header)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(260, 360)
        self.video_widget.setAspectRatioMode(Qt.KeepAspectRatio)
        self.video_widget.setObjectName("videoWidget")
        self.player.setVideoOutput(self.video_widget)
        preview_layout.addWidget(self.video_widget, 1)

        playback = QHBoxLayout()
        self.play_button = QPushButton("▶  Play")
        self.play_button.setObjectName("primaryButton")
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setObjectName("muted")
        playback.addWidget(self.play_button)
        playback.addStretch()
        playback.addWidget(self.time_label)
        preview_layout.addLayout(playback)

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 0)
        preview_layout.addWidget(self.seek_slider)
        top_split.addWidget(preview_panel)

        # Controls and clip list
        right_panel = QFrame()
        right_panel.setObjectName("panel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(10)

        right_layout.addWidget(QLabel("EXPORT PRESET"))
        self.platform_combo = QComboBox()
        self.platform_combo.addItems(PRESETS.keys())
        right_layout.addWidget(self.platform_combo)

        self.fit_combo = QComboBox()
        self.fit_combo.addItems(["Crop to fill (9:16)", "Fit with blurred background"])
        right_layout.addWidget(self.fit_combo)

        right_layout.addWidget(QLabel("CLIPS"))
        clip_buttons = QHBoxLayout()
        self.add_button = QPushButton("+ Import videos")
        self.remove_button = QPushButton("Remove selected")
        clip_buttons.addWidget(self.add_button)
        clip_buttons.addWidget(self.remove_button)
        right_layout.addLayout(clip_buttons)

        self.clip_list = QListWidget()
        self.clip_list.setMinimumWidth(270)
        right_layout.addWidget(self.clip_list, 1)

        trim_group = QGroupBox("Trim selected clip")
        trim_layout = QGridLayout(trim_group)
        trim_layout.addWidget(QLabel("Start (HH:MM:SS)"), 0, 0)
        self.start_edit = QLineEdit("00:00:00")
        trim_layout.addWidget(self.start_edit, 0, 1)
        trim_layout.addWidget(QLabel("End (HH:MM:SS)"), 1, 0)
        self.end_edit = QLineEdit("00:00:00")
        trim_layout.addWidget(self.end_edit, 1, 1)
        self.trim_help = QLabel("Select a clip to load its duration.")
        self.trim_help.setObjectName("muted")
        trim_layout.addWidget(self.trim_help, 2, 0, 1, 2)
        right_layout.addWidget(trim_group)

        top_split.addWidget(right_panel)
        top_split.setSizes([700, 430])
        outer.addWidget(top_split, 1)

        bottom = QHBoxLayout()
        self.output_edit = QLineEdit(str(Path.home() / "Videos" / "JASS-Short.mp4"))
        self.output_edit.setPlaceholderText("Output MP4 path")
        self.browse_output_button = QPushButton("Browse…")
        self.export_button = QPushButton("Export MP4")
        self.export_button.setObjectName("primaryButton")
        bottom.addWidget(QLabel("Save to"))
        bottom.addWidget(self.output_edit, 1)
        bottom.addWidget(self.browse_output_button)
        bottom.addWidget(self.export_button)
        outer.addLayout(bottom)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFormat("Ready")
        outer.addWidget(self.progress)

        self.statusBar().showMessage("Ready")

        file_menu = self.menuBar().addMenu("&File")
        import_action = QAction("Import videos…", self)
        import_action.triggered.connect(self.import_videos)
        file_menu.addAction(import_action)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _connect_signals(self):
        self.add_button.clicked.connect(self.import_videos)
        self.remove_button.clicked.connect(self.remove_selected)
        self.browse_output_button.clicked.connect(self.browse_output)
        self.export_button.clicked.connect(self.export_video)
        self.play_button.clicked.connect(self.toggle_playback)
        self.clip_list.currentRowChanged.connect(self.select_clip)
        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.seek_slider.sliderMoved.connect(self.player.setPosition)
        self.platform_combo.currentTextChanged.connect(self.update_preset_label)

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #11131a; color: #eef0f6; font-size: 13px; }
            QMenuBar, QMenu { background: #191c26; color: #eef0f6; }
            QMenuBar::item:selected, QMenu::item:selected { background: #343b52; }
            #appTitle { font-size: 25px; font-weight: 700; color: #ffffff; }
            #subtitle, #muted { color: #9ba3b8; }
            #panel { background: #191c26; border: 1px solid #2d3242; border-radius: 12px; }
            #videoWidget { background: #08090d; border-radius: 8px; }
            #statusPill { background: #252b3a; border: 1px solid #363d52; border-radius: 10px; padding: 7px 10px; }
            QPushButton { background: #292e3d; border: 1px solid #3b4256; padding: 9px 12px; border-radius: 7px; }
            QPushButton:hover { background: #363d51; }
            QPushButton:disabled { color: #73798a; background: #20232d; }
            #primaryButton { background: #7667f5; color: white; border: none; font-weight: 600; }
            #primaryButton:hover { background: #887bff; }
            QLineEdit, QComboBox, QListWidget { background: #10131b; border: 1px solid #34394a; border-radius: 6px; padding: 7px; }
            QListWidget::item { padding: 8px; border-radius: 4px; }
            QListWidget::item:selected { background: #373353; }
            QGroupBox { border: 1px solid #34394a; border-radius: 8px; margin-top: 8px; padding-top: 8px; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QSlider::groove:horizontal { height: 5px; background: #34394a; border-radius: 2px; }
            QSlider::handle:horizontal { background: #9387ff; width: 14px; margin: -5px 0; border-radius: 7px; }
            QProgressBar { background: #1b1f2b; border: 1px solid #34394a; border-radius: 5px; text-align: center; height: 18px; }
            QProgressBar::chunk { background: #7667f5; border-radius: 4px; }
        """)

    def _check_ffmpeg(self):
        ffmpeg = find_ffmpeg()
        if ffmpeg:
            self.ffmpeg_status.setText("FFmpeg ready")
            self.ffmpeg_status.setStyleSheet("color: #91e2b0;")
        else:
            self.ffmpeg_status.setText("FFmpeg not found")
            self.ffmpeg_status.setStyleSheet("color: #ffbf80;")
            self.statusBar().showMessage("Install FFmpeg and ensure ffmpeg.exe is on PATH to export video.")

    def import_videos(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import videos", str(Path.home()),
            "Video files (*.mp4 *.mov *.mkv *.avi *.webm *.m4v);;All files (*.*)"
        )
        if not paths:
            return
        for path in paths:
            if path not in self.video_paths:
                self.video_paths.append(path)
                self.clip_list.addItem(QListWidgetItem(Path(path).name))
        if self.clip_list.currentRow() < 0 and self.clip_list.count():
            self.clip_list.setCurrentRow(0)
        self.statusBar().showMessage(f"Loaded {len(paths)} selected file(s).")

    def remove_selected(self):
        row = self.clip_list.currentRow()
        if row < 0:
            return
        self.player.stop()
        self.video_paths.pop(row)
        self.clip_list.takeItem(row)
        self.current_path = None
        if self.clip_list.count():
            self.clip_list.setCurrentRow(min(row, self.clip_list.count() - 1))
        else:
            self.player.setSource(QUrl())
            self.start_edit.setText("00:00:00")
            self.end_edit.setText("00:00:00")

    def select_clip(self, row):
        if row < 0 or row >= len(self.video_paths):
            return
        self.current_path = self.video_paths[row]
        self.player.setSource(QUrl.fromLocalFile(self.current_path))
        self.player.pause()
        self.start_edit.setText("00:00:00")
        self.end_edit.setText("00:00:00")
        self.trim_help.setText("Reading duration…")
        self.statusBar().showMessage(f"Previewing {Path(self.current_path).name}")

    def position_changed(self, position):
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(position)
        self.time_label.setText(f"{format_time(position)} / {format_time(self.player.duration())}")

    def duration_changed(self, duration):
        self.duration_ms = duration
        self.seek_slider.setRange(0, duration)
        self.end_edit.setText(self.ms_to_hms(duration))
        self.time_label.setText(f"{format_time(self.player.position())} / {format_time(duration)}")
        self.trim_help.setText(f"Clip duration: {format_time(duration)}")

    @staticmethod
    def ms_to_hms(ms):
        total = max(0, int(ms / 1000))
        return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"

    @staticmethod
    def parse_time(value):
        parts = value.strip().split(":")
        if len(parts) not in (2, 3):
            raise ValueError("Use HH:MM:SS or MM:SS format.")
        nums = [int(p) for p in parts]
        if any(n < 0 for n in nums):
            raise ValueError("Time values cannot be negative.")
        if len(nums) == 2:
            minutes, seconds = nums
            return minutes * 60 + seconds
        hours, minutes, seconds = nums
        if minutes >= 60 or seconds >= 60:
            raise ValueError("Minutes and seconds must be below 60 in HH:MM:SS format.")
        return hours * 3600 + minutes * 60 + seconds

    def browse_output(self):
        current = self.output_edit.text().strip() or str(Path.home() / "Videos" / "JASS-Short.mp4")
        path, _ = QFileDialog.getSaveFileName(self, "Save exported video", current, "MP4 video (*.mp4)")
        if path:
            if not path.lower().endswith(".mp4"):
                path += ".mp4"
            self.output_edit.setText(path)

    def update_preset_label(self, preset):
        dims = PRESETS[preset]
        if dims["width"]:
            self.preview_format.setText(f"9:16 · {dims['width']} × {dims['height']}")
        else:
            self.preview_format.setText("Original dimensions")

    def export_video(self):
        if not self.video_paths:
            QMessageBox.information(self, "No video", "Import at least one video first.")
            return
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            QMessageBox.warning(
                self, "FFmpeg required",
                "FFmpeg was not found. Install it from https://ffmpeg.org/download.html "
                "and make sure ffmpeg.exe is available on PATH."
            )
            return
        if self.ffmpeg_process and self.ffmpeg_process.state() != QProcess.NotRunning:
            QMessageBox.information(self, "Export in progress", "An export is already running.")
            return

        row = self.clip_list.currentRow()
        start = 0
        end = None
        if row >= 0:
            try:
                start = self.parse_time(self.start_edit.text())
                end = self.parse_time(self.end_edit.text())
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid trim time", str(exc))
                return
            if end <= start:
                QMessageBox.warning(self, "Invalid trim range", "End time must be after start time.")
                return

        output = Path(self.output_edit.text().strip()).expanduser()
        if not str(output):
            QMessageBox.warning(self, "Output required", "Choose an output file path.")
            return
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "Output folder error", str(exc))
            return
        if output.exists():
            answer = QMessageBox.question(self, "Overwrite file?", f"{output} already exists. Replace it?")
            if answer != QMessageBox.Yes:
                return

        preset = PRESETS[self.platform_combo.currentText()]
        input_path = self.video_paths[row] if row >= 0 else self.video_paths[0]
        args = ["-y", "-hide_banner", "-i", input_path]
        if start:
            args += ["-ss", str(start)]
        if end is not None:
            args += ["-t", str(end - start)]

        if preset["width"]:
            if self.fit_combo.currentIndex() == 0:
                vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
            else:
                vf = (
                    "split[fg][bg];"
                    "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
                    "crop=1080:1920,boxblur=20:10[blur];"
                    "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fit];"
                    "[blur][fit]overlay=(W-w)/2:(H-h)/2,setsar=1"
                )
            args += ["-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
        else:
            args += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
        args += ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output)]

        self.ffmpeg_process = QProcess(self)
        self.ffmpeg_process.setProgram(ffmpeg)
        self.ffmpeg_process.setArguments(args)
        self.ffmpeg_process.readyReadStandardError.connect(self.read_export_output)
        self.ffmpeg_process.finished.connect(lambda code, status: self.export_finished(code, status, str(output)))
        self.progress.setRange(0, 0)
        self.progress.setFormat("Exporting…")
        self.export_button.setEnabled(False)
        self.statusBar().showMessage("Export in progress…")
        self.ffmpeg_process.start()

    def read_export_output(self):
        if not self.ffmpeg_process:
            return
        data = bytes(self.ffmpeg_process.readAllStandardError()).decode(errors="replace")
        if data.strip():
            last = data.strip().splitlines()[-1]
            self.statusBar().showMessage(last[-160:])

    def export_finished(self, code, status, output):
        self.progress.setRange(0, 100)
        self.progress.setValue(100 if code == 0 else 0)
        self.progress.setFormat("Export complete" if code == 0 else "Export failed")
        self.export_button.setEnabled(True)
        if code == 0:
            self.statusBar().showMessage(f"Saved: {output}")
            QMessageBox.information(self, "Export complete", f"Video saved successfully:\n{output}")
        else:
            self.statusBar().showMessage("Export failed. Check FFmpeg and the selected video.")
            QMessageBox.warning(self, "Export failed", "FFmpeg could not export this video. Check the output path and video file.")
        self.ffmpeg_process = None

    def toggle_playback(self):
        if not self.current_path:
            QMessageBox.information(self, "Choose a video", "Import and select a clip first.")
            return
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.play_button.setText("▶  Play")
        else:
            self.player.play()
            self.play_button.setText("Ⅱ  Pause")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setFont(QFont("Segoe UI", 10))
    window = CreatorStudio()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
