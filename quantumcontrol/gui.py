"""Qt GUI for the PreSonus Quantum ES 2, laid out like the native Universal Control window."""
import math
import sys
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication, QComboBox, QDial, QDialog, QGridLayout, QHBoxLayout,
                               QLabel, QMessageBox, QProgressBar, QPushButton, QSlider,
                               QVBoxLayout, QWidget)

from . import audio
from . import device as dev_mod

METER_FLOOR_DB, FALL_DB_PER_S, CLIP_DB, CLIP_HOLD_S = -60.0, 20.0, -0.5, 2.0
USER_HOLD_S = 0.5  # ignore polled values for a control right after the user touched it

STYLE = """
QWidget { background: #23262b; color: #e6e6e6; font-size: 12px; }
QDialog, QWidget#strip, QWidget#hw { background: #2f3238; }
QWidget#topbar { background: #000; }
QPushButton { background: #3d4148; border: 1px solid #50555d; padding: 6px 4px; border-radius: 2px; }
QPushButton:checked { background: #4a90d9; border-color: #6aa9e8; }
QPushButton:disabled { color: #777; background: #33363b; }
QLabel { background: transparent; }
QLabel#val { color: #4a90d9; font-weight: bold; }
QLabel#dim { color: #8a8f96; }
QLabel#name { font-weight: bold; }
QSlider::groove:vertical { background: #14161a; width: 6px; border-radius: 3px; }
QSlider::handle:vertical { background: #cfd3d8; height: 22px; margin: 0 -8px; border-radius: 2px; }
QSlider::groove:horizontal { background: #14161a; height: 6px; border-radius: 3px; }
QSlider::handle:horizontal { background: #cfd3d8; width: 14px; margin: -6px 0; border-radius: 2px; }
QProgressBar { background: #14161a; border: none; }
QComboBox { background: #3d4148; border: 1px solid #50555d; padding: 4px; }
"""


def fmt_db(v, digits=1):
    return "-oo dB" if v <= -95.9 else f"{v:.{digits}f} dB"


class Dial(QWidget):
    """Knob with a title and blue value read-out. Dial units are 1/scale dB."""

    def __init__(self, title, lo, hi, scale, on_change, fmt=fmt_db):
        super().__init__()
        self.scale, self.on_change, self.fmt, self.touched = scale, on_change, fmt, 0.0
        self.dial = QDial()
        self.dial.setRange(round(lo * scale), round(hi * scale))
        self.dial.setFixedSize(40, 40)
        self.title, self.value = QLabel(title), QLabel()
        self.title.setObjectName("name")
        self.value.setObjectName("val")
        text = QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(self.title)
        text.addWidget(self.value)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(self.dial)
        lay.addLayout(text, 1)
        self.dial.valueChanged.connect(self._changed)
        self._show(self.dial.value())

    def _show(self, raw):
        self.value.setText(self.fmt(raw / self.scale))

    def _changed(self, raw):
        self._show(raw)
        self.touched = time.monotonic()
        self.on_change(raw / self.scale)

    def set_from_device(self, v):
        if self.dial.isSliderDown() or time.monotonic() - self.touched < USER_HOLD_S:
            return
        self.dial.blockSignals(True)
        self.dial.setValue(round(v * self.scale))
        self.dial.blockSignals(False)
        self._show(self.dial.value())


class VMeter(QProgressBar):
    """Vertical peak meter in dBFS: instant attack, slow release, clip flag."""

    def __init__(self):
        super().__init__()
        self.setOrientation(Qt.Vertical)
        self.setRange(0, round(-METER_FLOOR_DB * 10))
        self.setTextVisible(False)
        self.setFixedWidth(10)
        self.db, self.last, self.clip_until = METER_FLOOR_DB, time.monotonic(), 0.0

    def update_level(self, linear):
        now = time.monotonic()
        new = 20 * math.log10(linear) if linear > 1e-6 else METER_FLOOR_DB
        self.db = max(new, self.db - FALL_DB_PER_S * (now - self.last), METER_FLOOR_DB)
        self.last = now
        if new >= CLIP_DB:
            self.clip_until = now + CLIP_HOLD_S
        color = "#d33" if now < self.clip_until else ("#e90" if self.db > -12 else "#3a3")
        self.setValue(round((self.db - METER_FLOOR_DB) * 10))
        self.setStyleSheet(f"QProgressBar::chunk {{ background: {color}; }}")


class VFader(QWidget):
    """Vertical fader with optional level meter and a value label above."""

    def __init__(self, lo, hi, scale, on_change, meter=False, name=""):
        super().__init__()
        self.scale, self.on_change, self.touched = scale, on_change, 0.0
        self.slider = QSlider(Qt.Vertical)
        self.slider.setRange(round(lo * scale), round(hi * scale))
        self.slider.setTickPosition(QSlider.TicksRight)
        self.slider.setTickInterval(round(12 * scale))
        self.slider.setMinimumHeight(220)
        self.meter = VMeter() if meter else None
        self.value = QLabel("—")
        self.value.setObjectName("val")
        self.value.setAlignment(Qt.AlignCenter)
        row = QHBoxLayout()
        if self.meter:
            row.addWidget(self.meter)
        row.addWidget(self.slider)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(self.value)
        lay.addLayout(row, 1)
        label = QLabel(name)
        label.setObjectName("name")
        lay.addWidget(label)
        self.slider.valueChanged.connect(self._changed)

    def set_silent(self, db):
        self.slider.blockSignals(True)
        self.slider.setValue(round(db * self.scale))
        self.slider.blockSignals(False)
        self.value.setText(f"{db:.2f} dB")

    def _changed(self, raw):
        self.value.setText(f"{raw / self.scale:.2f} dB")
        self.touched = time.monotonic()
        self.on_change(raw / self.scale)


class PanSlider(QSlider):
    """Horizontal pan -100..100; double-click recentres."""

    def __init__(self):
        super().__init__(Qt.Horizontal)
        self.setRange(-100, 100)
        self.setTickPosition(QSlider.TicksBelow)
        self.setTickInterval(50)

    def mouseDoubleClickEvent(self, e):
        self.setValue(0)


class InputStrip(QWidget):
    def __init__(self, window, ch):
        super().__init__()
        self.setObjectName("strip")
        self.w, self.ch, self.touched = window, ch, {}
        self.lowcut, self.phantom = QPushButton("HPF"), QPushButton("48V")
        self.auto = QPushButton("Auto\nGain")
        for b in (self.lowcut, self.phantom):
            b.setCheckable(True)
        self.phantom.clicked.connect(self._phantom_clicked)
        self.lowcut.clicked.connect(lambda on: window.call("set_lowcut", ch, on))
        self.auto.clicked.connect(lambda: window.call("start_autogain", ch))
        self.gain = Dial("Gain", dev_mod.GAIN_MIN, dev_mod.GAIN_MAX, 8 / 3,
                         lambda db: window.call("set_gain", ch, db), fmt=lambda v: f"{v:.1f} dB")
        self.pan = PanSlider()
        self.pan_label = QLabel("C")
        self.pan_label.setObjectName("val")
        self.pan_label.setAlignment(Qt.AlignCenter)
        self.pan.valueChanged.connect(self._pan_changed)
        self.pan.setToolTip("Панорама входа в Main (двойной клик - в центр). Положение запоминает программа")
        self.mute, self.solo = QPushButton("M"), QPushButton("S")
        for b in (self.mute, self.solo):
            b.setCheckable(True)
        self.mute.setToolTip("Mute входа в Main. Положение запоминает программа")
        self.solo.setToolTip("Solo: глушит все остальные входы и возвраты DAW в Main")
        self.mute.toggled.connect(lambda on: window.call("set_input_mute", ch, on))
        self.solo.toggled.connect(lambda on: window.call("set_input_solo", ch, on))
        self.fader = VFader(dev_mod.FADER_MIN, dev_mod.FADER_MAX, 4,
                            lambda db: window.input_fader(ch, db), meter=True,
                            name=f"In {ch + 1}")
        self.fader.slider.setToolTip("Уровень входа в Main-микс (не гейн преампа). Устройство его не сообщает, положение запоминает программа")
        self.fader.slider.setValue(round(dev_mod.FADER_MIN * 4))
        self.link = QPushButton("Link")
        self.link.setCheckable(True)
        self.link.setToolTip("Стерео-линк входов 1+2: вход 1 - левый, вход 2 - правый Main, фейдеры вместе")
        self.link.clicked.connect(lambda on: window.set_link(on))
        top = QHBoxLayout()
        top.addWidget(self.lowcut)
        top.addWidget(self.phantom)
        ms = QHBoxLayout()
        ms.addWidget(self.mute)
        ms.addWidget(self.solo)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.auto)
        lay.addWidget(self.gain)
        lay.addWidget(self.pan)
        lay.addWidget(self.pan_label)
        lay.addLayout(ms)
        lay.addWidget(self.fader, 1)
        lay.addWidget(self.link)
        self.setFixedWidth(150)

    def _pan_changed(self, v):
        self.pan_label.setText("C" if v == 0 else (f"L{-v}" if v < 0 else f"R{v}"))
        self.w.call("set_input_pan", self.ch, v / 100)

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
        self.fader.meter.update_level(s["level"])
        for key, btn in (("phantom", self.phantom), ("lowcut", self.lowcut)):
            if time.monotonic() - self.touched.get(key, 0) > USER_HOLD_S:
                btn.setChecked(s[key])
        self.auto.setText("Auto\nGain…" if s["autogain"] else "Auto\nGain")
        if time.monotonic() - self.w.link_touched > USER_HOLD_S:
            self.link.setChecked(s["link"])


class SettingsDialog(QDialog):
    """Sample rate / buffer via PipeWire (the card itself has no such setting on Linux)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Настройки аудио")
        self.rate_box, self.quantum_box = QComboBox(), QComboBox()
        self.rate_box.addItem("Авто", 0)
        for r in audio.RATES:
            self.rate_box.addItem(f"{r / 1000:g} кГц", r)
        self.quantum_box.addItem("Авто", 0)
        for q in audio.QUANTA:
            self.quantum_box.addItem(f"{q} семплов", q)
        self.rate_box.activated.connect(lambda i: self.apply(audio.set_rate, self.rate_box))
        self.quantum_box.activated.connect(lambda i: self.apply(audio.set_quantum, self.quantum_box))
        self.info = QLabel("")
        self.info.setObjectName("dim")
        self.info.setWordWrap(True)
        self.info.setMinimumHeight(48)
        note = QLabel("Настройки PipeWire: действуют для всех звуковых устройств.")
        note.setObjectName("dim")
        grid = QGridLayout(self)
        grid.addWidget(QLabel("Частота"), 0, 0)
        grid.addWidget(self.rate_box, 0, 1)
        grid.addWidget(QLabel("Буфер"), 1, 0)
        grid.addWidget(self.quantum_box, 1, 1)
        grid.addWidget(QLabel("Разрядность"), 2, 0)
        grid.addWidget(QLabel(f"{audio.BITS} бит (единственная, что поддерживает карта)"), 2, 1)
        grid.addWidget(self.info, 3, 0, 1, 2)
        grid.addWidget(note, 4, 0, 1, 2)
        grid.setColumnStretch(1, 1)
        self.setMinimumWidth(420)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)
        self.refresh()

    def apply(self, setter, box):
        try:
            setter(box.currentData())
        except Exception as e:
            self.info.setText(f"Ошибка pw-metadata: {e}")
            return
        self.refresh()

    def refresh(self):
        try:
            st = audio.get_settings()
        except Exception as e:
            self.info.setText(f"PipeWire недоступен: {e}")
            return
        for box, key in ((self.rate_box, "force_rate"), (self.quantum_box, "force_quantum")):
            if not box.view().isVisible():
                box.setCurrentIndex(max(box.findData(st[key]), 0))
        rate = st["force_rate"] or st["rate"]
        quantum = st["force_quantum"] or st["quantum"]
        self.info.setText(
            f"Задержка буфера: {quantum} семплов / {rate} Гц = {quantum / rate * 1000:.2f} мс "
            f"(сейчас у PipeWire: {st['rate']} Гц, {st['quantum']}). Смена применяется, "
            "когда карта играет/пишет.")


class MainWindow(QWidget):
    def __init__(self, factory):
        super().__init__()
        self.setWindowTitle("Quantum ES 2")
        self.factory, self.dev = factory, None
        self.linked, self.link_touched = False, 0.0
        self.settings = SettingsDialog(self)
        self.status = QLabel("Нет соединения")
        self.status.setObjectName("dim")

        self.strips = [InputStrip(self, 0), InputStrip(self, 1)]

        hw = QWidget()
        hw.setObjectName("hw")
        title = QLabel("H/W Controls")
        title.setAlignment(Qt.AlignCenter)
        self.main_knob = Dial("Main Out", dev_mod.VOL_MIN, dev_mod.VOL_MAX, 2,
                              lambda db: self.call("set_monitor_volume", db))
        self.phones = Dial("Phones", dev_mod.VOL_MIN, dev_mod.VOL_MAX, 2,
                           lambda db: self.call("set_phones_volume", db))
        self.dim, self.main_mute, self.to_phones = QPushButton("Dim"), QPushButton("M"), QPushButton("Phones")
        for b in (self.dim, self.main_mute, self.to_phones):
            b.setEnabled(False)
            b.setToolTip("Пока не поддерживается: протокол не расшифрован")
        self.main_fader = VFader(dev_mod.MAIN_MIN, dev_mod.MAIN_MAX, 2,
                                 lambda db: self.call("set_main_volume", db), name="Main L/R")
        self.main_fader.slider.setValue(0)
        self.main_fader.slider.setToolTip("Устройство не сообщает значение, положение запоминает программа")
        row = QHBoxLayout()
        row.addWidget(self.main_mute)
        row.addWidget(self.to_phones)
        hl = QVBoxLayout(hw)
        hl.addWidget(title)
        hl.addWidget(self.main_knob)
        hl.addWidget(self.phones)
        hl.addWidget(self.dim)
        hl.addLayout(row)
        hl.addWidget(self.main_fader, 1)
        hw.setFixedWidth(180)

        gear = QPushButton("Настройки")
        gear.setFixedHeight(28)
        gear.clicked.connect(self.settings.show)
        top = QWidget()
        top.setObjectName("topbar")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(6, 4, 6, 4)
        tl.addStretch(1)
        tl.addWidget(gear)

        body = QHBoxLayout()
        body.setSpacing(2)
        body.setContentsMargins(0, 0, 0, 0)
        for s in self.strips:
            body.addWidget(s)
        body.addStretch(1)
        body.addWidget(hw)
        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(top)
        lay.addLayout(body, 1)
        lay.addWidget(self.status)
        self.setStyleSheet(STYLE)
        self.setMinimumHeight(560)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)
        self.set_enabled(False)

    def input_fader(self, ch, db):
        self.call("set_input_fader", ch, db)
        if self.linked:
            other = 1 - ch
            self.strips[other].fader.set_silent(db)
            self.call("set_input_fader", other, db)

    def set_link(self, on):
        self.link_touched = time.monotonic()
        self.call("set_stereo_link", on)
        self.apply_link(on)

    def apply_link(self, on):
        """Reflect a linked pair in the UI: pans fixed L/R, fader 2 follows fader 1."""
        self.linked = on
        for strip in self.strips:
            strip.link.setChecked(on)
            strip.pan.setEnabled(not on)
        for strip, value in zip(self.strips, ((-100, 100) if on else (0, 0))):
            strip.pan.blockSignals(True)
            strip.pan.setValue(value)
            strip.pan.blockSignals(False)
            strip.pan_label.setText("C" if value == 0 else (f"L{-value}" if value < 0 else f"R{value}"))
        if on:
            self.strips[1].fader.set_silent(self.strips[0].fader.slider.value() / self.strips[0].fader.scale)

    def set_enabled(self, on):
        for w in (*self.strips, self.main_knob, self.phones, self.main_fader):
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
            self.timer.setInterval(50)
            self.set_enabled(True)
        try:
            s = self.dev.state()
        except Exception as e:
            self.lost(e)
            return
        self.status.setText(f"Подключено, прошивка {s['firmware']}")
        for strip, cs in zip(self.strips, s["channels"]):
            strip.update_state(cs)
        if s["channels"][0]["link"] != self.linked and time.monotonic() - self.link_touched > USER_HOLD_S:
            self.apply_link(s["channels"][0]["link"])
        self.main_knob.set_from_device(s["monitor_db"])
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
