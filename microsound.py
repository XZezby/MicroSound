#!/usr/bin/env python3
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)


APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config" / "pads.json"
DEFAULT_KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "Q", "W"]


@dataclass
class Pad:
    key: str
    label: str
    file: str

    @property
    def path(self) -> Path:
        candidate = Path(self.file).expanduser()
        if candidate.is_absolute():
            return candidate
        return APP_DIR / candidate


def default_pads() -> list[Pad]:
    return [
        Pad(key=key, label=f"Pad {key}", file=f"media/pad_{key.lower()}.mp4")
        for key in DEFAULT_KEYS
    ]


def load_pads() -> list[Pad]:
    if not CONFIG_PATH.exists():
        return default_pads()

    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    pads: list[Pad] = []
    for index, item in enumerate(data):
        key = str(item.get("key", DEFAULT_KEYS[index % len(DEFAULT_KEYS)])).upper()
        label = str(item.get("label", f"Pad {key}"))
        file = str(item.get("file", ""))
        pads.append(Pad(key=key, label=label, file=file))
    return pads


def save_pads(pads: list[Pad]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump([asdict(pad) for pad in pads], handle, ensure_ascii=False, indent=2)
        handle.write("\n")


class PadButton(QFrame):
    def __init__(self, pad: Pad, index: int, parent: "MicroSoundWindow") -> None:
        super().__init__()
        self.pad = pad
        self.index = index
        self.parent_window = parent

        self.setObjectName("padButton")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(130, 94)

        self.key_label = QLabel(pad.key)
        self.key_label.setObjectName("keyLabel")
        self.name_label = QLabel(pad.label)
        self.name_label.setObjectName("nameLabel")
        self.name_label.setWordWrap(True)
        self.file_label = QLabel(self.file_text())
        self.file_label.setObjectName("fileLabel")
        self.file_label.setWordWrap(True)

        play_button = QPushButton("播放")
        play_button.clicked.connect(lambda: parent.play_pad(index))
        bind_button = QPushButton("绑定")
        bind_button.clicked.connect(lambda: parent.bind_pad(index))

        button_row = QHBoxLayout()
        button_row.addWidget(play_button)
        button_row.addWidget(bind_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.key_label)
        layout.addWidget(self.name_label)
        layout.addWidget(self.file_label)
        layout.addStretch(1)
        layout.addLayout(button_row)

    def file_text(self) -> str:
        return self.pad.path.name if self.pad.file else "未绑定"

    def refresh(self, pad: Pad) -> None:
        self.pad = pad
        self.key_label.setText(pad.key)
        self.name_label.setText(pad.label)
        self.file_label.setText(self.file_text())

    def set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)


class MicroSoundWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MicroSound")
        self.resize(1120, 720)
        self.pads = load_pads()
        self.pad_buttons: list[PadButton] = []
        self.active_index: int | None = None

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.85)
        self.player.setAudioOutput(self.audio)
        self.player.mediaStatusChanged.connect(self.on_media_status)
        self.player.errorOccurred.connect(self.on_player_error)

        self.video = QVideoWidget()
        self.video.setMinimumSize(420, 280)
        self.player.setVideoOutput(self.video)

        self.now_label = QLabel("未播放")
        self.now_label.setObjectName("nowLabel")
        self.path_label = QLabel("选择一个 pad，或直接按键盘触发")
        self.path_label.setObjectName("pathLabel")
        self.path_label.setWordWrap(True)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(85)
        self.volume_slider.valueChanged.connect(lambda value: self.audio.setVolume(value / 100))

        self.stop_button = QPushButton("停止")
        self.stop_button.clicked.connect(self.stop)
        self.replay_button = QPushButton("重播")
        self.replay_button.clicked.connect(self.replay)

        self.setCentralWidget(self.build_ui())
        self.setStatusBar(QStatusBar())
        self.install_shortcuts()
        self.build_menu()
        self.apply_styles()

    def build_ui(self) -> QWidget:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(18)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(12)
        for index, pad in enumerate(self.pads):
            button = PadButton(pad, index, self)
            self.pad_buttons.append(button)
            grid.addWidget(button, index // 3, index % 3)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setSpacing(12)
        side_layout.addWidget(self.video, 1)
        side_layout.addWidget(self.now_label)
        side_layout.addWidget(self.path_label)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("音量"))
        controls.addWidget(self.volume_slider, 1)
        controls.addWidget(self.replay_button)
        controls.addWidget(self.stop_button)
        side_layout.addLayout(controls)

        layout.addWidget(grid_widget, 3)
        layout.addWidget(side, 2)
        return root

    def build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        reload_action = QAction("重新加载配置", self)
        reload_action.triggered.connect(self.reload_config)
        file_menu.addAction(reload_action)

        stop_action = QAction("停止播放", self)
        stop_action.setShortcut(QKeySequence(Qt.Key_Escape))
        stop_action.triggered.connect(self.stop)
        file_menu.addAction(stop_action)

    def install_shortcuts(self) -> None:
        for index, pad in enumerate(self.pads):
            shortcut = QShortcut(QKeySequence(pad.key), self)
            shortcut.activated.connect(lambda i=index: self.play_pad(i))

    def play_pad(self, index: int) -> None:
        if index < 0 or index >= len(self.pads):
            return

        pad = self.pads[index]
        path = pad.path
        if not path.exists():
            QMessageBox.warning(self, "文件不存在", f"{pad.label} 对应的文件不存在：\n{path}")
            self.statusBar().showMessage(f"缺少文件: {path}", 4000)
            return

        self.set_active_pad(index)
        self.now_label.setText(f"{pad.key} / {pad.label}")
        self.path_label.setText(str(path))
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.setPosition(0)
        self.player.play()
        self.statusBar().showMessage(f"播放: {path.name}", 2500)

    def bind_pad(self, index: int) -> None:
        pad = self.pads[index]
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            f"为 {pad.key} 选择 mp4",
            str(APP_DIR / "media"),
            "MP4 Video (*.mp4);;All Files (*)",
        )
        if not file_name:
            return

        selected = Path(file_name)
        try:
            stored = selected.relative_to(APP_DIR)
        except ValueError:
            stored = selected

        self.pads[index].file = str(stored)
        self.pad_buttons[index].refresh(self.pads[index])
        save_pads(self.pads)
        self.statusBar().showMessage(f"{pad.key} 已绑定到 {selected.name}", 3000)

    def replay(self) -> None:
        if self.active_index is not None:
            self.play_pad(self.active_index)

    def stop(self) -> None:
        self.player.stop()
        self.clear_active_pad()
        self.now_label.setText("已停止")
        self.statusBar().showMessage("已停止播放", 2000)

    def reload_config(self) -> None:
        self.pads = load_pads()
        for index, button in enumerate(self.pad_buttons):
            if index < len(self.pads):
                button.refresh(self.pads[index])
        self.clear_active_pad()
        self.statusBar().showMessage("配置已重新加载", 2500)

    def set_active_pad(self, index: int) -> None:
        self.clear_active_pad()
        self.active_index = index
        self.pad_buttons[index].set_active(True)

    def clear_active_pad(self) -> None:
        if self.active_index is not None and self.active_index < len(self.pad_buttons):
            self.pad_buttons[self.active_index].set_active(False)
        self.active_index = None

    def on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.EndOfMedia:
            self.clear_active_pad()

    def on_player_error(self, *_args: object) -> None:
        error = self.player.errorString()
        if error:
            QMessageBox.warning(self, "播放失败", error)

    def apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #15171b;
                color: #f4f7fb;
            }
            QWidget {
                font-size: 15px;
            }
            QMenuBar, QMenu {
                background: #20242b;
                color: #f4f7fb;
            }
            QVideoWidget {
                background: #050609;
                border: 1px solid #2f3744;
            }
            #padButton {
                background: #20242b;
                border: 1px solid #343c49;
                border-radius: 8px;
            }
            #padButton[active="true"] {
                background: #26373a;
                border: 2px solid #41d6a4;
            }
            #keyLabel {
                color: #41d6a4;
                font-size: 28px;
                font-weight: 700;
            }
            #nameLabel {
                color: #f4f7fb;
                font-weight: 600;
            }
            #fileLabel, #pathLabel {
                color: #aeb7c6;
                font-size: 13px;
            }
            #nowLabel {
                color: #f4f7fb;
                font-size: 20px;
                font-weight: 700;
            }
            QPushButton {
                background: #303846;
                color: #f4f7fb;
                border: 1px solid #4a5568;
                border-radius: 6px;
                min-height: 30px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background: #3a4555;
            }
            QSlider::groove:horizontal {
                background: #313946;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #41d6a4;
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            """
        )


def main() -> int:
    app = QApplication(sys.argv)
    window = MicroSoundWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
