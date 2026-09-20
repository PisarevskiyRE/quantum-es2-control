"""Qt GUI for the PreSonus Quantum ES 2."""
import sys
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QSlider, QVBoxLayout, QWidget, QGridLayout)

from . import device as dev_mod

USER_HOLD_S = 0.5  # ignore polled values for a control right after the user touched it


class Row(QWidget):
    """Labelled horizontal slider with a dB read-out. Slider units are `1/scale` dB."""

    def __init__(self, title, lo, hi, scale, on_change, parent=None):
        super().__init__(parent)
        self.scale, self.on_change, self.touched = scale, on_change, 0.0
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(round(lo * scale), round(hi * scale))
        self.value_label = QLabel()
        self.value_label.setMinimumWidth(70)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        name = QLabel(title)
        name.setMinimumWidth(110)
        lay.addWidget(name)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.value_label)
        self.slider.valueChanged.connect(self._changed)
        self._show(self.slider.value())

    def _show(self, raw):
        self.value_label.setText(f"{raw / self.scale:+.1f} dB")

    def _changed(self, raw):
        self._show(raw)
        self.touched = time.monotonic()
        self.on_change(raw / self.scale)

    def set_from_device(self, db):
        if self.slider.isSliderDown() or time.monotonic() - self.touched < USER_HOLD_S:
            return
        self.slider.blockSignals(True)
        self.slider.setValue(round(db * self.scale))
        self.slider.blockSignals(False)
        self._show(self.slider.value())


class InputStrip(QGroupBox):
    def __init__(self, window, ch):
        super().__init__(f"Вход {ch + 1}")
        self.w, self.ch = window, ch
        self.gain = Row("Гейн", dev_mod.GAIN_MIN, dev_mod.GAIN_MAX, 8 / 3,
                        lambda db: window.call("set_gain", ch, db))
        self.phantom = QPushButton("+48V")
        self.lowcut = QPushButton("Low Cut")
        self.auto = QPushButton("Авто-гейн")
        self.link = QLabel("")
        for b in (self.phantom, self.lowcut):
            b.setCheckable(True)
        self.phantom.clicked.connect(self._phantom_clicked)
        self.lowcut.clicked.connect(lambda on: window.call("set_lowcut", ch, on))
        self.auto.clicked.connect(lambda: window.call("start_autogain", ch))
        buttons = QHBoxLayout()
        for b in (self.phantom, self.lowcut, self.auto):
            buttons.addWidget(b)
        buttons.addStretch(1)
        buttons.addWidget(self.link)
        lay = QVBoxLayout(self)
        lay.addWidget(self.gain)
        lay.addLayout(buttons)
        self.touched = {}

    def _phantom_clicked(self, on):
        if on:
            ok = QMessageBox.question(
                self, "Фантомное питание",
                f"Включить +48V на входе {self.ch + 1}?\nНекоторые микрофоны (ленточные) "
                "могут выйти из строя.") == QMessageBox.Yes
            if not ok:
                self.phantom.setChecked(False)
                return
        self.touched["phantom"] = time.monotonic()
        self.w.call("set_phantom", self.ch, on)

    def update_state(self, s):
        self.gain.set_from_device(s["gain_db"])
        for key, btn in (("phantom", self.phantom), ("lowcut", self.lowcut)):
            if time.monotonic() - self.touched.get(key, 0) > USER_HOLD_S:
                btn.setChecked(s[key])
        self.auto.setText("Авто-гейн…" if s["autogain"] else "Авто-гейн")
        self.link.setText("стерео-линк" if s["link"] else "")


class MainWindow(QWidget):
    def __init__(self, factory):
        super().__init__()
        self.setWindowTitle("Quantum ES 2")
        self.factory, self.dev = factory, None
        self.status = QLabel("Нет соединения")
        self.strips = [InputStrip(self, 0), InputStrip(self, 1)]
        outs = QGroupBox("Выходы")
        self.monitor = Row("Мониторы", dev_mod.VOL_MIN, dev_mod.VOL_MAX, 2,
                           lambda db: self.call("set_monitor_volume", db))
        self.phones = Row("Наушники", dev_mod.VOL_MIN, dev_mod.VOL_MAX, 2,
                          lambda db: self.call("set_phones_volume", db))
        self.main = Row("Main out", dev_mod.MAIN_MIN, dev_mod.MAIN_MAX, 2,
                        lambda db: self.call("set_main_volume", db))
        self.main.slider.setValue(0)
        note = QLabel("Main out: устройство не сообщает значение, положение запоминает программа.")
        note.setStyleSheet("color: gray")
        ol = QVBoxLayout(outs)
        for r in (self.monitor, self.phones, self.main):
            ol.addWidget(r)
        ol.addWidget(note)
        lay = QVBoxLayout(self)
        for s in self.strips:
            lay.addWidget(s)
        lay.addWidget(outs)
        lay.addWidget(self.status)
        self.setMinimumWidth(560)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(100)
        self.set_enabled(False)

    def set_enabled(self, on):
        for w in (*self.strips, self.monitor, self.phones, self.main):
            w.setEnabled(on)

    def call(self, name, *args):
        if self.dev is None:
            return
        try:
            getattr(self.dev, name)(*args)
        except Exception as e:
            self.lost(e)

    def lost(self, err):
        try:
            self.dev.close()
        except Exception:
            pass
        self.dev = None
        self.set_enabled(False)
        self.status.setText(f"Нет соединения: {err}")

    def tick(self):
        if self.dev is None:
            try:
                self.dev = self.factory()
            except Exception as e:
                self.status.setText(f"Нет соединения: {e}")
                self.timer.setInterval(1000)
                return
            self.timer.setInterval(100)
            self.set_enabled(True)
        try:
            s = self.dev.state()
        except Exception as e:
            self.lost(e)
            return
        self.status.setText(f"Подключено, прошивка {s['firmware']}")
        for strip, cs in zip(self.strips, s["channels"]):
            strip.update_state(cs)
        self.monitor.set_from_device(s["monitor_db"])
        self.phones.set_from_device(s["phones_db"])

    def closeEvent(self, e):
        if self.dev:
            self.dev.close()
        super().closeEvent(e)


def main():
    factory = dev_mod.QuantumES2
    if "--demo" in sys.argv:
        from .fake import FakeDevice
        factory = FakeDevice
    app = QApplication(sys.argv)
    win = MainWindow(factory)
    win.show()
    if "--screenshot" in sys.argv:
        QTimer.singleShot(600, lambda: (win.grab().save(sys.argv[sys.argv.index("--screenshot") + 1]),
                                        app.quit()))
    sys.exit(app.exec())
