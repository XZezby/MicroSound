#!/usr/bin/env python3
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl, Signal, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioDevice, QAudioOutput, QMediaDevices, QMediaPlayer
from audio.device_manager import DeviceManager
from audio.interfaces import IAudioOutput
from audio.outputs import VirtualMicOutput, MonitorOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
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

try:
    import keyboard
except ImportError:  # pragma: no cover - dependency is installed by the helper script
    keyboard = None


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
        Pad(key=key, label=f"Pad {key}", file=f"media/pad_{key.lower()}.mp3")
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


class HotkeyBridge(QObject):
    triggered = Signal(int)


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
        self.active_index = None

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.85)
        self.player.setAudioOutput(self.audio)
        # Use DeviceManager to enumerate outputs and restore previous selection
        self.device_manager = DeviceManager()
        self.audio_devices = self.device_manager.get_output_devices()
        self.audio_output_combo = QComboBox()
        self.audio_output_combo.addItem("默认输出", None)
        for dev in self.audio_devices:
            self.audio_output_combo.addItem(dev.description, dev)
        # try to restore saved primary endpoint
        saved_primary = self.device_manager.load_selected_endpoint("primary_output")
        if saved_primary:
            for i in range(self.audio_output_combo.count()):
                data = self.audio_output_combo.itemData(i)
                try:
                    if data is not None and data.id == saved_primary:
                        self.audio_output_combo.setCurrentIndex(i)
                        break
                except Exception:
                    pass
        self.audio_output_combo.setCurrentIndex(self.audio_output_combo.currentIndex() or 0)
        self.audio_output_combo.currentIndexChanged.connect(self.on_audio_output_changed)

        # 监听（Monitor）输出：UI 选择用，播放逻辑暂不改变（后续步骤接入）
        self.audio_monitor = QAudioOutput(self)
        self.audio_monitor.setVolume(0.85)
        self.monitor_output_combo = QComboBox()
        self.monitor_output_combo.addItem("默认监听输出", None)
        for dev in self.audio_devices:
            self.monitor_output_combo.addItem(dev.description, dev)
        # try to restore saved monitor endpoint
        saved_monitor = self.device_manager.load_selected_endpoint("monitor_output")
        if saved_monitor:
            for i in range(self.monitor_output_combo.count()):
                data = self.monitor_output_combo.itemData(i)
                try:
                    if data is not None and data.id == saved_monitor:
                        self.monitor_output_combo.setCurrentIndex(i)
                        break
                except Exception:
                    pass
        self.monitor_output_combo.setCurrentIndex(self.monitor_output_combo.currentIndex() or 0)
        self.monitor_output_combo.currentIndexChanged.connect(self.on_monitor_output_changed)
        self.monitor_status_label = QLabel("")
        self.virtual_status_label = QLabel("")

        # 监听系统设备变更，自动刷新设备列表
        try:
            QMediaDevices.audioOutputsChanged.connect(self.on_audio_outputs_changed)
        except Exception:
            pass
        # 降阶实现：额外的 QMediaPlayer 用于本地监听（将来替换为单一 AudioEngine）
        self.player_monitor = QMediaPlayer(self)
        self.player_monitor.setAudioOutput(self.audio_monitor)

        self.input_devices = list(QMediaDevices.audioInputs())
        self.input_device_combo = QComboBox()
        self.input_device_combo.addItem("默认输入设备", None)
        for device in self.input_devices:
            self.input_device_combo.addItem(device.description(), device)
        self.input_device_combo.setCurrentIndex(0)
        self.input_device_combo.currentIndexChanged.connect(self.on_input_device_changed)

        self._apply_selected_audio_output()
        self._apply_selected_monitor_output()
        # Create output skeletons
        sel_primary = self.audio_output_combo.currentData()
        sel_monitor = self.monitor_output_combo.currentData()
        self.virtual_output = VirtualMicOutput(device_info=sel_primary)
        self.monitor_output = MonitorOutput(device_info=sel_monitor)
        # wire status callbacks to update UI labels safely on the main thread
        try:
            def make_updater(label):
                return lambda text: QTimer.singleShot(0, lambda: label.setText(text))

            self.virtual_output.set_status_callback(make_updater(self.virtual_status_label))
            self.monitor_output.set_status_callback(make_updater(self.monitor_status_label))
        except Exception:
            pass
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
        self.volume_slider.valueChanged.connect(self.on_volume_changed)

        # 监听音量（独立于主音量）
        self.monitor_volume_slider = QSlider(Qt.Horizontal)
        self.monitor_volume_slider.setRange(0, 100)
        self.monitor_volume_slider.setValue(85)
        self.monitor_volume_slider.valueChanged.connect(self.on_monitor_volume_changed)

        self.local_hear_checkbox = QCheckBox("本地监听")
        self.local_hear_checkbox.setChecked(False)
        self.local_hear_checkbox.toggled.connect(self.on_local_hear_changed)

        self.virtual_out_checkbox = QCheckBox("启用虚拟麦克风输出")
        self.virtual_out_checkbox.setChecked(True)
        self.virtual_out_checkbox.toggled.connect(self.on_virtual_out_changed)

        self.stop_button = QPushButton("停止")
        self.stop_button.clicked.connect(self.stop)
        self.replay_button = QPushButton("重播")
        self.replay_button.clicked.connect(self.replay)

        self.hotkey_bridge = HotkeyBridge(self)
        self.hotkey_bridge.triggered.connect(self.toggle_pad)

        self.setCentralWidget(self.build_ui())
        self.setStatusBar(QStatusBar())
        self._apply_input_device_selection()
        self.on_local_hear_changed(self.local_hear_checkbox.isChecked())
        # default: virtual output enabled, monitor controlled by checkbox
        self.virtual_output_enabled = True
        self.monitor_output_enabled = self.local_hear_checkbox.isChecked()
        self.install_shortcuts()
        self.install_global_shortcuts()
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
        controls.addWidget(QLabel("监听音量"))
        controls.addWidget(self.monitor_volume_slider, 1)
        controls.addWidget(self.local_hear_checkbox)
        controls.addWidget(self.virtual_out_checkbox)
        controls.addWidget(self.replay_button)
        controls.addWidget(self.stop_button)
        side_layout.addLayout(controls)

        output_controls = QHBoxLayout()
        output_controls.addWidget(QLabel("输出设备"))
        output_controls.addWidget(self.audio_output_combo, 1)
        output_controls.addWidget(QLabel("监听设备"))
        output_controls.addWidget(self.monitor_output_combo, 1)
        output_controls.addWidget(self.monitor_status_label)
        output_controls.addWidget(self.virtual_status_label)
        side_layout.addLayout(output_controls)

        input_controls = QHBoxLayout()
        input_controls.addWidget(QLabel("输入设备"))
        input_controls.addWidget(self.input_device_combo, 1)
        side_layout.addLayout(input_controls)

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
        if keyboard is not None:
            return

        for index, pad in enumerate(self.pads):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{pad.key}"), self)
            shortcut.activated.connect(lambda i=index: self.toggle_pad(i))

        pause_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        pause_shortcut.activated.connect(self.pause_current)

    def install_global_shortcuts(self) -> None:
        if keyboard is None:
            return

        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass

        for index, pad in enumerate(self.pads):
            keyboard.add_hotkey(f"ctrl+{pad.key.lower()}", lambda i=index: self.toggle_pad(i))

        keyboard.add_hotkey("ctrl+p", self.pause_current)

    def closeEvent(self, event: object) -> None:
        if keyboard is not None:
            try:
                keyboard.unhook_all_hotkeys()
            except Exception:
                pass
        super().closeEvent(event)

    def play_pad(self, index: int) -> None:
        if index < 0 or index >= len(self.pads):
            return

        pad = self.pads[index]
        path = pad.path
        if not path.exists():
            QMessageBox.warning(self, "文件不存在", f"{pad.label} 对应的文件不存在：\n{path}")
            self.statusBar().showMessage(f"缺少文件: {path}", 4000)
            return

        # switch to AudioMixer-based playback: create FileAudioSource and add to mixer
        from audio.file_source import FileAudioSource
        from audio.mixer import AudioMixer, AudioEngine

        # lazy-init mixer/engine
        if not hasattr(self, "mixer"):
            self.mixer = AudioMixer()
            self.audio_engine = AudioEngine(self.mixer, outputs=[self.virtual_output, self.monitor_output], frame_size=1024)
            self.audio_engine.start()

        src = FileAudioSource(str(path), target_sample_rate=self.mixer.sample_rate, target_channels=self.mixer.channels)
        self.mixer.AddSource(src)
        self.set_active_pad(index)
        self.now_label.setText(f"{pad.key} / {pad.label}")
        self.path_label.setText(str(path))
        self.statusBar().showMessage(f"播放(混音引擎): {path.name}", 2500)

    def bind_pad(self, index: int) -> None:
        pad = self.pads[index]
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            f"为 {pad.key} 选择 mp3",
            str(APP_DIR / "media"),
            "MP3 Audio (*.mp3);;All Files (*)",
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

    def toggle_pad(self, index: int) -> None:
        if index < 0 or index >= len(self.pads):
            return

        state = self.player.playbackState()
        if self.active_index == index and state in {QMediaPlayer.PlayingState, QMediaPlayer.PausedState}:
            self.stop()
            return

        self.play_pad(index)

    def replay(self) -> None:
        if self.active_index is not None:
            self.play_pad(self.active_index)

    def pause_current(self) -> None:
        if self.active_index is None:
            return

        state = self.player.playbackState()
        # 同步控制两个播放器的暂停/继续
        if state == QMediaPlayer.PlayingState:
            self.player.pause()
            try:
                self.player_monitor.pause()
            except Exception:
                pass
            self.now_label.setText(f"{self.pads[self.active_index].key} / {self.pads[self.active_index].label} (已暂停)")
            self.statusBar().showMessage("已暂停", 2000)
        elif state == QMediaPlayer.PausedState:
            self.player.play()
            try:
                if self.local_hear_checkbox.isChecked():
                    self.player_monitor.play()
            except Exception:
                pass
            self.statusBar().showMessage("继续播放", 2000)
        else:
            self.play_pad(self.active_index)

    def stop(self) -> None:
        self.player.stop()
        try:
            self.player_monitor.stop()
        except Exception:
            pass
        self.clear_active_pad()
        self.now_label.setText("已停止")
        self.statusBar().showMessage("已停止播放", 2000)

    def reload_config(self) -> None:
        self.pads = load_pads()
        for index, button in enumerate(self.pad_buttons):
            if index < len(self.pads):
                button.refresh(self.pads[index])
        self.install_global_shortcuts()
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

    def _apply_selected_audio_output(self) -> None:
        selected_device = self.audio_output_combo.currentData()
        if selected_device is None:
            try:
                self.audio.setDevice(QMediaDevices.defaultAudioOutput())
            except Exception:
                pass
            return

        try:
            # selected_device may be a DeviceInfo (from DeviceManager)
            try:
                self.audio.setDevice(selected_device.device)
            except Exception:
                # fallback if it's already a QAudioDevice
                self.audio.setDevice(selected_device)
            # persist selection
            try:
                self.device_manager.save_selected_endpoint("primary_output", getattr(selected_device, "id", None))
            except Exception:
                pass
        except Exception:
            pass
        try:
            # update virtual status label
            desc = getattr(selected_device, "description", None)
            if desc:
                self.virtual_status_label.setText(f"虚拟输出: {desc}")
            else:
                self.virtual_status_label.setText("虚拟输出: 默认输出")
        except Exception:
            pass

    def on_monitor_output_changed(self, *_args: object) -> None:
        self._apply_selected_monitor_output()
        # update monitor output device_info and restart if enabled
        try:
            sel = self.monitor_output_combo.currentData()
            self.monitor_output.device_info = sel
            if self.monitor_output_enabled:
                try:
                    self.monitor_output.Stop()
                except Exception:
                    pass
                try:
                    self.monitor_output.Start()
                except Exception:
                    pass
        except Exception:
            pass

    def _apply_selected_monitor_output(self) -> None:
        selected_device = self.monitor_output_combo.currentData()
        if selected_device is None:
            try:
                self.audio_monitor.setDevice(QMediaDevices.defaultAudioOutput())
            except Exception:
                pass
            self.monitor_status_label.setText("监听: 使用默认输出")
            return

        try:
            try:
                self.audio_monitor.setDevice(selected_device.device)
            except Exception:
                self.audio_monitor.setDevice(selected_device)
            self.monitor_status_label.setText(f"监听: {getattr(selected_device, 'description', str(selected_device))}")
            # persist selection
            try:
                self.device_manager.save_selected_endpoint("monitor_output", getattr(selected_device, "id", None))
            except Exception:
                pass
        except Exception:
            # 设备不可用
            try:
                self.monitor_status_label.setText("监听: 设备不可用")
            except Exception:
                pass
            return

    def on_audio_outputs_changed(self) -> None:
        # 重新获取设备列表并尝试保持用户选择
        try:
            current_primary = self.audio_output_combo.currentData()
            current_monitor = self.monitor_output_combo.currentData()
            primary_desc = current_primary.description() if current_primary is not None else None
            monitor_desc = current_monitor.description() if current_monitor is not None else None

            # rebuild using DeviceInfo
            self.audio_devices = self.device_manager.get_output_devices()

            # 更新 primary 列表
            self.audio_output_combo.blockSignals(True)
            self.audio_output_combo.clear()
            self.audio_output_combo.addItem("默认输出", None)
            for dev in self.audio_devices:
                self.audio_output_combo.addItem(dev.description, dev)
            # 尝试恢复选择
            if primary_desc:
                for i in range(self.audio_output_combo.count()):
                    data = self.audio_output_combo.itemData(i)
                    try:
                        if data is not None and getattr(data, "description", None) == primary_desc:
                            self.audio_output_combo.setCurrentIndex(i)
                            break
                    except Exception:
                        pass
            self.audio_output_combo.blockSignals(False)

            # 更新 monitor 列表
            self.monitor_output_combo.blockSignals(True)
            self.monitor_output_combo.clear()
            self.monitor_output_combo.addItem("默认监听输出", None)
            for dev in self.audio_devices:
                # audio_devices here are DeviceInfo from get_output_devices
                self.monitor_output_combo.addItem(dev.description, dev)
            if monitor_desc:
                for i in range(self.monitor_output_combo.count()):
                    data = self.monitor_output_combo.itemData(i)
                    try:
                        if data is not None and getattr(data, "description", None) == monitor_desc:
                            self.monitor_output_combo.setCurrentIndex(i)
                            break
                    except Exception:
                        pass
            self.monitor_output_combo.blockSignals(False)

            # 重新应用选择并更新状态标签
            self._apply_selected_audio_output()
            self._apply_selected_monitor_output()
        except Exception:
            pass

    def on_audio_output_changed(self, *_args: object) -> None:
        self._apply_selected_audio_output()
        # update virtual output device_info and restart if enabled
        try:
            sel = self.audio_output_combo.currentData()
            self.virtual_output.device_info = sel
            if self.virtual_output_enabled:
                try:
                    self.virtual_output.Stop()
                except Exception:
                    pass
                try:
                    self.virtual_output.Start()
                except Exception:
                    pass
        except Exception:
            pass

    def on_input_device_changed(self, *_args: object) -> None:
        self._apply_input_device_selection()

    def _apply_input_device_selection(self) -> None:
        selected_input = self.input_device_combo.currentData()
        if selected_input is None:
            self.local_hear_checkbox.setEnabled(True)
            self.statusBar().showMessage("已使用默认输入设备。", 3000)
            return

        self.local_hear_checkbox.setEnabled(True)
        self.statusBar().showMessage(f"已选择输入设备：{selected_input.description()}", 3000)

    def on_volume_changed(self, value: int) -> None:
        self._apply_volume(value / 100)

    def on_local_hear_changed(self, enabled: bool) -> None:
        self._apply_volume(self.volume_slider.value() / 100)
        # 监听开关切换时应用监听音量
        self._apply_monitor_volume(self.monitor_volume_slider.value() / 100)
        self.statusBar().showMessage("本地监听已开启" if enabled else "本地监听已关闭", 2000)
        # control monitor output enabled state
        self.monitor_output_enabled = enabled
        try:
            if enabled:
                self.monitor_output.Start()
            else:
                self.monitor_output.Stop()
        except Exception:
            pass

    def on_virtual_out_changed(self, enabled: bool) -> None:
        self.virtual_output_enabled = enabled
        try:
            if enabled:
                self.virtual_output.Start()
            else:
                self.virtual_output.Stop()
        except Exception:
            pass

    def _apply_volume(self, volume: float) -> None:
        # 主输出始终使用配置的音量（用于推送到虚拟线/远端）
        try:
            self.audio.setVolume(volume)
            try:
                if hasattr(self, "virtual_output") and self.virtual_output is not None:
                    self.virtual_output.setVolume(volume)
            except Exception:
                pass
        except Exception:
            pass
        # 监听输出使用独立监听音量（受本地监听开关控制）
        try:
            self._apply_monitor_volume(self.monitor_volume_slider.value() / 100)
        except Exception:
            pass

    def on_monitor_volume_changed(self, value: int) -> None:
        self._apply_monitor_volume(value / 100)

    def _apply_monitor_volume(self, volume: float) -> None:
        try:
            if self.local_hear_checkbox.isChecked():
                self.audio_monitor.setVolume(volume)
                try:
                    if hasattr(self, "monitor_output") and self.monitor_output is not None:
                        self.monitor_output.setVolume(volume)
                except Exception:
                    pass
            else:
                self.audio_monitor.setVolume(0.0)
        except Exception:
            pass

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
                font-size: 14px;
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
