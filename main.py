# main.py
# ClipForge Studio - APK Android estable
# Corregido: usa kivy.utils.platform para detectar Android
# Boton Buscar abre selector nativo Android, no escanea carpetas.

import os
import sys
import math
import time
import shutil
import traceback
import threading
import subprocess
from pathlib import Path


# ============================================================
# GUARDAR ERRORES SI LA APK SE CIERRA
# ============================================================

def guardar_error(exc_type, exc_value, exc_tb):
    try:
        texto = "ERROR EN CLIPFORGE\n\n"
        texto += "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

        rutas = [
            "/storage/emulated/0/ClipForge_error.txt",
            os.path.join(os.getcwd(), "ClipForge_error.txt"),
        ]

        for ruta in rutas:
            try:
                with open(ruta, "w", encoding="utf-8") as f:
                    f.write(texto)
                break
            except Exception:
                pass
    except Exception:
        pass


sys.excepthook = guardar_error


# ============================================================
# KIVY
# ============================================================

from kivy.config import Config

Config.set("graphics", "width", "420")
Config.set("graphics", "height", "860")
Config.set("input", "mouse", "mouse,multitouch_on_demand")
Config.set("kivy", "exit_on_escape", "0")

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.utils import platform

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.slider import Slider
from kivy.uix.progressbar import ProgressBar
from kivy.uix.popup import Popup


# ============================================================
# CONFIG
# ============================================================

QUALITY_PRESETS = {
    "Alta": {"preset": "slow", "crf": "17"},
    "Balanceada": {"preset": "medium", "crf": "20"},
    "Rapida": {"preset": "veryfast", "crf": "23"},
}

WM_POSITIONS = {
    "Arriba derecha": "W-w-20:20",
    "Arriba izquierda": "20:20",
    "Abajo derecha": "W-w-20:H-h-20",
    "Abajo izquierda": "20:H-h-20",
    "Centro": "(W-w)/2:(H-h)/2",
}


class UserCancelled(Exception):
    pass


class ClipForgeApp(App):
    def build(self):
        Window.clearcolor = (0.05, 0.07, 0.10, 1)

        self.bg = (0.05, 0.07, 0.10, 1)
        self.card = (0.08, 0.11, 0.16, 1)
        self.field = (0.12, 0.16, 0.22, 1)
        self.text = (0.95, 0.97, 1, 1)
        self.muted = (0.62, 0.67, 0.74, 1)
        self.blue = (0.12, 0.38, 0.90, 1)
        self.green = (0.10, 0.68, 0.30, 1)
        self.red = (0.85, 0.20, 0.20, 1)

        self.cancel_event = threading.Event()
        self.worker_thread = None
        self.current_process = None
        self.process_lock = threading.Lock()

        self.quality = "Balanceada"
        self.wm_position = "Arriba derecha"

        self.base_dir = self.safe_base_dir()
        self.app_data_dir = self.safe_data_dir()

        self.ffmpeg = None
        self.ffprobe = None

        self._android_picker_callback = None
        self._android_picker_mime = None

        return self.crear_interfaz()

    def on_start(self):
        Clock.schedule_once(lambda dt: self.post_inicio(), 0.5)

    def post_inicio(self):
        try:
            self.app_data_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        self.set_default_output()
        self.status("App lista")
        self.log("ClipForge iniciado correctamente")
        self.log(f"Plataforma detectada: {platform}")
        self.log("Toca Buscar para seleccionar un video")
        self.log("En Android se abrira el selector nativo de archivos")

    # ========================================================
    # RUTAS
    # ========================================================

    def safe_base_dir(self):
        try:
            return Path(__file__).parent
        except Exception:
            return Path(os.getcwd())

    def safe_data_dir(self):
        try:
            if platform == "android":
                return Path("/storage/emulated/0/ClipForgeStudio")
            return Path.home() / ".clipforge_studio"
        except Exception:
            return Path(os.getcwd()) / "ClipForgeStudio"

    def resolve_binary(self, name):
        suffix = ".exe" if os.name == "nt" else ""
        full = name + suffix

        candidates = [
            self.base_dir / full,
            self.app_data_dir / full,
            Path(os.getcwd()) / full,
        ]

        found = shutil.which(full)
        if found:
            candidates.append(Path(found))

        for path in candidates:
            try:
                if path.exists():
                    if platform == "android":
                        try:
                            os.chmod(str(path), 0o755)
                        except Exception:
                            pass
                    return path
            except Exception:
                pass

        return self.base_dir / full

    # ========================================================
    # INTERFAZ
    # ========================================================

    def crear_interfaz(self):
        scroll = ScrollView(do_scroll_x=False)

        main = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(12),
            size_hint_y=None,
        )
        main.bind(minimum_height=main.setter("height"))
        scroll.add_widget(main)

        main.add_widget(Label(
            text="ClipForge Studio",
            color=self.text,
            font_size=dp(26),
            bold=True,
            size_hint_y=None,
            height=dp(40),
        ))

        main.add_widget(Label(
            text="Cortar videos para APK Android",
            color=self.muted,
            font_size=dp(14),
            size_hint_y=None,
            height=dp(28),
        ))

        main.add_widget(self.titulo("Archivos"))

        row_video = self.fila()
        self.video_field = self.input("Video seleccionado")
        row_video.add_widget(self.video_field)
        row_video.add_widget(self.boton("Buscar", self.pick_video, self.blue, dp(95)))
        main.add_widget(row_video)

        row_out = self.fila()
        self.out_field = self.input("Carpeta de salida")
        row_out.add_widget(self.out_field)
        row_out.add_widget(self.boton("Carpeta", self.pick_output, self.blue, dp(95)))
        main.add_widget(row_out)

        row_wm = self.fila()
        self.wm_field = self.input("Marca de agua opcional")
        row_wm.add_widget(self.wm_field)
        row_wm.add_widget(self.boton("Imagen", self.pick_watermark, self.blue, dp(95)))
        main.add_widget(row_wm)

        main.add_widget(self.titulo("Tiempos"))

        self.prefix_field = self.input("Prefijo de clips")
        self.prefix_field.text = "Parte"
        main.add_widget(self.prefix_field)

        row_dur = self.fila()
        row_dur.add_widget(self.label_peq("Duracion"))
        self.duration_slider = Slider(min=2, max=180, value=10, step=1)
        self.duration_slider.bind(value=self.on_duration_change)
        row_dur.add_widget(self.duration_slider)
        self.duration_label = self.label_peq("10 s", dp(60))
        row_dur.add_widget(self.duration_label)
        main.add_widget(row_dur)

        grid_tiempo = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(120))

        box_inicio = BoxLayout(orientation="vertical", spacing=dp(5))
        box_inicio.add_widget(self.label_normal("Inicio"))
        fila_inicio = self.fila()
        self.ini_m = self.input("min")
        self.ini_s = self.input("seg")
        self.ini_m.text = "0"
        self.ini_s.text = "0"
        fila_inicio.add_widget(self.ini_m)
        fila_inicio.add_widget(self.label_peq(":", dp(20)))
        fila_inicio.add_widget(self.ini_s)
        box_inicio.add_widget(fila_inicio)

        box_fin = BoxLayout(orientation="vertical", spacing=dp(5))
        box_fin.add_widget(self.label_normal("Fin 0=total"))
        fila_fin = self.fila()
        self.fin_m = self.input("min")
        self.fin_s = self.input("seg")
        self.fin_m.text = "0"
        self.fin_s.text = "0"
        fila_fin.add_widget(self.fin_m)
        fila_fin.add_widget(self.label_peq(":", dp(20)))
        fila_fin.add_widget(self.fin_s)
        box_fin.add_widget(fila_fin)

        grid_tiempo.add_widget(box_inicio)
        grid_tiempo.add_widget(box_fin)
        main.add_widget(grid_tiempo)

        main.add_widget(self.titulo("Calidad y marca de agua"))

        row_quality = self.fila()
        row_quality.add_widget(self.label_peq("Calidad"))
        self.quality_btn = self.boton("Balanceada", self.popup_quality, self.field)
        row_quality.add_widget(self.quality_btn)
        main.add_widget(row_quality)

        row_pos = self.fila()
        row_pos.add_widget(self.label_peq("Posicion"))
        self.position_btn = self.boton("Arriba derecha", self.popup_position, self.field)
        row_pos.add_widget(self.position_btn)
        main.add_widget(row_pos)

        row_size = self.fila()
        row_size.add_widget(self.label_peq("Tamano"))
        self.wm_size_slider = Slider(min=40, max=500, value=120, step=10)
        self.wm_size_slider.bind(value=self.on_wm_size_change)
        row_size.add_widget(self.wm_size_slider)
        self.wm_size_label = self.label_peq("120 px", dp(75))
        row_size.add_widget(self.wm_size_label)
        main.add_widget(row_size)

        row_opacity = self.fila()
        row_opacity.add_widget(self.label_peq("Opacidad"))
        self.wm_opacity_slider = Slider(min=0.10, max=1.0, value=0.80, step=0.05)
        self.wm_opacity_slider.bind(value=self.on_wm_opacity_change)
        row_opacity.add_widget(self.wm_opacity_slider)
        self.wm_opacity_label = self.label_peq("80%", dp(60))
        row_opacity.add_widget(self.wm_opacity_label)
        main.add_widget(row_opacity)

        main.add_widget(self.titulo("Proceso"))

        row_progress = self.fila(dp(32))
        self.progress = ProgressBar(max=100, value=0)
        self.progress_label = self.label_peq("0%", dp(55))
        row_progress.add_widget(self.progress)
        row_progress.add_widget(self.progress_label)
        main.add_widget(row_progress)

        self.status_label = Label(
            text="Cargando...",
            color=self.text,
            font_size=dp(15),
            size_hint_y=None,
            height=dp(34),
        )
        main.add_widget(self.status_label)

        row_buttons = self.fila(dp(50))
        self.generate_btn = self.boton("Generar", self.start_generation, self.green)
        self.cancel_btn = self.boton("Cancelar", self.cancel_generation, self.red)
        self.cancel_btn.disabled = True
        row_buttons.add_widget(self.generate_btn)
        row_buttons.add_widget(self.cancel_btn)
        main.add_widget(row_buttons)

        main.add_widget(self.titulo("Registro"))

        self.log_label = Label(
            text="",
            color=(0.88, 0.91, 0.93, 1),
            font_size=dp(12),
            size_hint_y=None,
            halign="left",
            valign="top",
        )
        self.log_label.bind(texture_size=lambda inst, val: setattr(inst, "height", val[1] + dp(20)))
        self.log_label.bind(size=lambda inst, val: setattr(inst, "text_size", (inst.width, None)))

        log_scroll = ScrollView(size_hint_y=None, height=dp(180), do_scroll_x=False)
        log_scroll.add_widget(self.log_label)
        main.add_widget(log_scroll)

        return scroll

    def titulo(self, text):
        return Label(
            text=text,
            color=self.text,
            font_size=dp(18),
            bold=True,
            size_hint_y=None,
            height=dp(35),
        )

    def label_normal(self, text):
        return Label(
            text=text,
            color=self.muted,
            font_size=dp(14),
            size_hint_y=None,
            height=dp(28),
        )

    def label_peq(self, text, width=dp(82)):
        return Label(
            text=text,
            color=self.muted,
            font_size=dp(14),
            size_hint=(None, 1),
            width=width,
        )

    def fila(self, height=dp(52)):
        return BoxLayout(
            orientation="horizontal",
            spacing=dp(8),
            size_hint_y=None,
            height=height,
        )

    def input(self, hint):
        return TextInput(
            text="",
            hint_text=hint,
            multiline=False,
            background_color=self.field,
            foreground_color=self.text,
            cursor_color=self.text,
            hint_text_color=self.muted,
            padding=[dp(8), dp(12), dp(8), dp(8)],
            font_size=dp(14),
            size_hint_y=None,
            height=dp(48),
        )

    def boton(self, text, callback, color, width=None):
        btn = Button(
            text=text,
            background_normal="",
            background_color=color,
            color=(1, 1, 1, 1),
            font_size=dp(14),
            bold=True,
        )

        if width:
            btn.size_hint_x = None
            btn.width = width

        btn.bind(on_release=lambda *a: callback())
        return btn

    # ========================================================
    # SLIDERS Y POPUPS
    # ========================================================

    def on_duration_change(self, instance, value):
        self.duration_label.text = f"{int(value)} s"

    def on_wm_size_change(self, instance, value):
        self.wm_size_label.text = f"{int(value)} px"

    def on_wm_opacity_change(self, instance, value):
        self.wm_opacity_label.text = f"{int(round(value * 100))}%"

    def popup_quality(self):
        self.popup_opciones("Calidad", list(QUALITY_PRESETS.keys()), self.set_quality)

    def popup_position(self):
        self.popup_opciones("Posicion", list(WM_POSITIONS.keys()), self.set_position)

    def set_quality(self, value):
        self.quality = value
        self.quality_btn.text = value

    def set_position(self, value):
        self.wm_position = value
        self.position_btn.text = value

    def popup_opciones(self, title, options, callback):
        layout = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))

        popup = Popup(
            title=title,
            content=layout,
            size_hint=(0.85, None),
            height=dp(90 + len(options) * 55),
        )

        for opt in options:
            btn = Button(
                text=opt,
                size_hint_y=None,
                height=dp(48),
                background_normal="",
                background_color=self.blue,
                color=(1, 1, 1, 1),
            )

            def choose(instance, value=opt):
                callback(value)
                popup.dismiss()

            btn.bind(on_release=choose)
            layout.add_widget(btn)

        popup.open()

    # ========================================================
    # SELECTOR NATIVO ANDROID
    # ========================================================

    def pick_video(self):
        if platform == "android":
            self.log("Abriendo selector Android para video...")
            self.android_file_picker("video/*", self.on_video_selected)
        else:
            self.scan_popup(
                "Seleccionar video",
                (".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"),
                self.on_video_selected,
            )

    def pick_watermark(self):
        if platform == "android":
            self.log("Abriendo selector Android para imagen...")
            self.android_file_picker("image/*", self.on_watermark_selected)
        else:
            self.scan_popup(
                "Seleccionar imagen",
                (".png", ".jpg", ".jpeg", ".webp"),
                self.on_watermark_selected,
            )

    def android_file_picker(self, mime_type, callback):
        try:
            from android import activity
            from jnius import autoclass

            Intent = autoclass("android.content.Intent")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")

            self._android_picker_callback = callback
            self._android_picker_mime = mime_type

            intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.setType(mime_type)

            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            intent.addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)

            activity.bind(on_activity_result=self._on_android_file_selected)

            PythonActivity.mActivity.startActivityForResult(
                Intent.createChooser(intent, "Seleccionar archivo"),
                1001,
            )

        except Exception as exc:
            self.dialog("Error", f"No se pudo abrir el selector Android:\n{exc}")
            self.log(f"Error selector Android: {exc}")

    def _on_android_file_selected(self, request_code, result_code, data):
        try:
            from android import activity
            activity.unbind(on_activity_result=self._on_android_file_selected)

            if request_code != 1001:
                return

            if result_code != -1:
                self.log("Selector cancelado")
                return

            if data is None:
                self.dialog("Error", "El selector no devolvio ningun archivo")
                return

            uri = data.getData()

            if uri is None:
                self.dialog("Error", "No se pudo obtener la URI del archivo")
                return

            self.log(f"Archivo seleccionado URI: {uri.toString()}")
            self.status("Copiando archivo seleccionado...")

            def copiar():
                try:
                    path = self.copy_android_uri_to_file(uri)
                    callback = getattr(self, "_android_picker_callback", None)

                    if path and callback:
                        Clock.schedule_once(lambda dt: callback(path), 0)
                    else:
                        Clock.schedule_once(
                            lambda dt: self.dialog("Error", "No se pudo copiar el archivo seleccionado"),
                            0,
                        )

                except Exception:
                    err = traceback.format_exc()
                    Clock.schedule_once(lambda dt: self.dialog("Error copiando archivo", err), 0)

            threading.Thread(target=copiar, daemon=True).start()

        except Exception:
            self.dialog("Error", traceback.format_exc())

    def copy_android_uri_to_file(self, uri):
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        FileOutputStream = autoclass("java.io.FileOutputStream")

        context = PythonActivity.mActivity
        resolver = context.getContentResolver()

        try:
            Intent = autoclass("android.content.Intent")
            resolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION,
            )
        except Exception:
            pass

        input_stream = resolver.openInputStream(uri)

        if input_stream is None:
            raise RuntimeError("No se pudo abrir el archivo seleccionado")

        mime = resolver.getType(uri) or ""

        if "image" in mime:
            if "png" in mime:
                ext = ".png"
            elif "webp" in mime:
                ext = ".webp"
            else:
                ext = ".jpg"
        else:
            if "quicktime" in mime:
                ext = ".mov"
            elif "x-matroska" in mime:
                ext = ".mkv"
            elif "webm" in mime:
                ext = ".webm"
            else:
                ext = ".mp4"

        try:
            self.app_data_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        temp_name = "clipforge_selected_" + str(int(time.time())) + ext
        temp_path = self.app_data_dir / temp_name

        output_stream = FileOutputStream(str(temp_path))

        buffer = bytearray(1024 * 1024)

        while True:
            n = input_stream.read(buffer)

            if n == -1 or n < 0:
                break

            output_stream.write(buffer, 0, n)

        output_stream.flush()
        output_stream.close()
        input_stream.close()

        return str(temp_path)

    # ========================================================
    # FALLBACK PARA PC
    # ========================================================

    def scan_popup(self, title, extensions, callback):
        layout = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8))

        status = Label(
            text="Buscando archivos...",
            color=self.text,
            size_hint_y=None,
            height=dp(34),
        )

        scroll = ScrollView(do_scroll_x=False)
        grid = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        scroll.add_widget(grid)

        cancel_btn = Button(
            text="Cancelar",
            size_hint_y=None,
            height=dp(48),
            background_normal="",
            background_color=(0.30, 0.30, 0.30, 1),
            color=(1, 1, 1, 1),
        )

        layout.add_widget(status)
        layout.add_widget(scroll)
        layout.add_widget(cancel_btn)

        popup = Popup(title=title, content=layout, size_hint=(0.96, 0.92))
        cancel_btn.bind(on_release=lambda *a: popup.dismiss())
        popup.open()

        def scan_thread():
            files = self.scan_files(extensions)

            def update(dt):
                grid.clear_widgets()

                if not files:
                    status.text = "No se encontraron archivos"
                    grid.add_widget(Label(
                        text="No se encontraron archivos.",
                        color=(1, 0.45, 0.45, 1),
                        size_hint_y=None,
                        height=dp(100),
                    ))
                    return

                status.text = f"{len(files)} archivo(s) encontrado(s)"

                for path in files:
                    name = os.path.basename(path)

                    btn = Button(
                        text=name,
                        size_hint_y=None,
                        height=dp(54),
                        background_normal="",
                        background_color=self.field,
                        color=(1, 1, 1, 1),
                    )

                    def elegir(instance, p=path):
                        popup.dismiss()
                        callback(p)

                    btn.bind(on_release=elegir)
                    grid.add_widget(btn)

            Clock.schedule_once(update, 0)

        threading.Thread(target=scan_thread, daemon=True).start()

    def scan_files(self, extensions):
        roots = [
            str(Path.home() / "Videos"),
            str(Path.home() / "Downloads"),
            str(Path.home() / "Pictures"),
        ]

        found = []

        for root in roots:
            if not os.path.exists(root):
                continue

            try:
                for dirpath, dirnames, filenames in os.walk(root):
                    for name in filenames:
                        if name.lower().endswith(extensions):
                            found.append(os.path.join(dirpath, name))

                    if len(found) >= 200:
                        break
            except Exception:
                pass

        found = list(dict.fromkeys(found))

        try:
            found.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        except Exception:
            pass

        return found[:200]

    # ========================================================
    # ARCHIVOS
    # ========================================================

    def set_default_output(self):
        try:
            if platform == "android":
                out = Path("/storage/emulated/0/Movies/ClipForge")
            else:
                out = Path.home() / "Videos" / "ClipForge"

            try:
                out.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

            self.out_field.text = str(out)
        except Exception:
            self.out_field.text = str(self.app_data_dir)

    def pick_output(self):
        self.set_default_output()
        self.dialog("Carpeta de salida", f"Los clips se guardaran en:\n{self.out_field.text}")

    def on_video_selected(self, path):
        self.video_field.text = path
        self.status("Video seleccionado")
        self.log(f"Video copiado: {path}")

    def on_watermark_selected(self, path):
        self.wm_field.text = path
        self.status("Marca de agua seleccionada")
        self.log(f"Marca de agua copiada: {path}")

    # ========================================================
    # VALIDACION Y FFMPEG
    # ========================================================

    def safe_int(self, value, name):
        try:
            n = int(str(value).strip())
        except Exception:
            raise ValueError(f"{name} debe ser un numero entero")

        if n < 0:
            raise ValueError(f"{name} no puede ser negativo")

        return n

    def time_to_seconds(self, minutes, seconds, label):
        m = self.safe_int(minutes, f"{label} minutos")
        s = self.safe_int(seconds, f"{label} segundos")

        if s > 59:
            raise ValueError(f"{label} segundos debe estar entre 0 y 59")

        return m * 60 + s

    def check_ffmpeg_now(self):
        self.ffmpeg = self.resolve_binary("ffmpeg")
        self.ffprobe = self.resolve_binary("ffprobe")

        if not self.ffmpeg.exists():
            raise FileNotFoundError(
                "ffmpeg no encontrado.\n\n"
                f"Ruta esperada:\n{self.ffmpeg}\n\n"
                "La app abre, pero para generar clips debes incluir ffmpeg."
            )

        if not self.ffprobe.exists():
            raise FileNotFoundError(
                "ffprobe no encontrado.\n\n"
                f"Ruta esperada:\n{self.ffprobe}\n\n"
                "La app abre, pero para generar clips debes incluir ffprobe."
            )

    def probe_duration(self, video_path):
        cmd = [
            str(self.ffprobe),
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nokey=1:noprint_wrappers=1",
            str(video_path),
        ]

        out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip()
        return float(out)

    def validate_settings(self):
        self.check_ffmpeg_now()

        video_raw = self.video_field.text.strip()
        out_raw = self.out_field.text.strip()
        wm_raw = self.wm_field.text.strip()

        if not video_raw:
            raise ValueError("Selecciona un video")

        video = Path(video_raw)

        if not video.exists():
            raise FileNotFoundError("El video seleccionado no existe")

        if not out_raw:
            raise ValueError("Selecciona carpeta de salida")

        out_dir = Path(out_raw)
        out_dir.mkdir(parents=True, exist_ok=True)

        wm = Path(wm_raw) if wm_raw else None

        if wm and not wm.exists():
            raise FileNotFoundError("La marca de agua no existe")

        start = self.time_to_seconds(self.ini_m.text, self.ini_s.text, "Inicio")
        end = self.time_to_seconds(self.fin_m.text, self.fin_s.text, "Fin")
        clip_duration = int(self.duration_slider.value)

        total = self.probe_duration(video)

        if start >= total:
            raise ValueError("El inicio supera la duracion del video")

        if end == 0 or end > total:
            end = int(math.ceil(total))

        if end <= start:
            raise ValueError("El final debe ser mayor que el inicio")

        clips_total = math.ceil((end - start) / clip_duration)

        if clips_total <= 0:
            raise ValueError("No hay clips para generar")

        return {
            "video": video,
            "out_dir": out_dir,
            "watermark": wm,
            "prefix": self.prefix_field.text.strip() or "Parte",
            "start": start,
            "end": end,
            "clip_duration": clip_duration,
            "clips_total": clips_total,
            "quality": self.quality,
            "wm_position": self.wm_position,
            "wm_size": int(self.wm_size_slider.value),
            "wm_opacity": float(self.wm_opacity_slider.value),
        }

    def build_filter_complex(self, settings, clip_index):
        txt = self.escape_drawtext(f"{settings['prefix']} {clip_index}")

        drawtext = (
            f"drawtext=text='{txt}':"
            "fontcolor=white:"
            "fontsize=34:"
            "borderw=2:"
            "bordercolor=black@0.70:"
            "x=(w-text_w)/2:"
            "y=24"
        )

        chains = []
        base = "0:v"

        if settings["watermark"]:
            pos = WM_POSITIONS[settings["wm_position"]]
            opacity = max(0.10, min(1.0, settings["wm_opacity"]))

            chains.append(
                f"[1:v]scale={settings['wm_size']}:-1,"
                f"format=rgba,"
                f"colorchannelmixer=aa={opacity:.2f}[wm]"
            )
            chains.append(f"[0:v][wm]overlay={pos}[base]")
            base = "base"

        chains.append(f"[{base}]{drawtext}[v]")
        return ";".join(chains)

    def build_ffmpeg_cmd(self, settings, index, clip_start, clip_duration, output_file):
        quality = QUALITY_PRESETS[settings["quality"]]
        fc = self.build_filter_complex(settings, index)

        cmd = [
            str(self.ffmpeg),
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-ss", f"{clip_start:.3f}",
            "-i", str(settings["video"]),
        ]

        if settings["watermark"]:
            cmd += ["-i", str(settings["watermark"])]

        cmd += [
            "-t", f"{clip_duration:.3f}",
            "-filter_complex", fc,
            "-map", "[v]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", quality["preset"],
            "-crf", quality["crf"],
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-c:a", "aac",
            "-b:a", "160k",
            str(output_file),
        ]

        return cmd

    def escape_drawtext(self, text):
        return (
            str(text)
            .replace("\\", r"\\")
            .replace(":", r"\:")
            .replace("'", r"\'")
            .replace("%", r"\%")
            .replace("[", r"\[")
            .replace("]", r"\]")
            .replace(",", r"\,")
            .replace(";", r"\;")
        )

    def run_ffmpeg(self, cmd):
        with self.process_lock:
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            proc = self.current_process

        while proc.poll() is None:
            if self.cancel_event.is_set():
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                raise UserCancelled("Cancelado por el usuario")

            time.sleep(0.2)

        stderr = proc.stderr.read() if proc.stderr else ""

        with self.process_lock:
            if self.current_process is proc:
                self.current_process = None

        if proc.returncode != 0:
            raise RuntimeError((stderr.strip() or "FFmpeg fallo sin detalle")[-1500:])

    # ========================================================
    # GENERACION
    # ========================================================

    def start_generation(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self.dialog("En progreso", "Ya hay un proceso ejecutandose")
            return

        try:
            settings = self.validate_settings()
        except Exception as exc:
            self.dialog("Validacion", str(exc))
            self.log(f"Validacion: {exc}")
            return

        self.progress.value = 0
        self.progress_label.text = "0%"
        self.log_label.text = ""

        self.cancel_event.clear()
        self.set_running(True)
        self.status("Preparando...")

        self.worker_thread = threading.Thread(
            target=self.worker,
            args=(settings,),
            daemon=True,
        )
        self.worker_thread.start()

    def worker(self, settings):
        created = 0
        digits = max(3, len(str(settings["clips_total"])))

        try:
            for i in range(settings["clips_total"]):
                if self.cancel_event.is_set():
                    raise UserCancelled("Cancelado por el usuario")

                num = i + 1
                clip_start = settings["start"] + i * settings["clip_duration"]
                actual = min(settings["clip_duration"], settings["end"] - clip_start)

                if actual <= 0:
                    break

                out_name = f"{settings['video'].stem}_clip_{num:0{digits}d}.mp4"
                out_file = settings["out_dir"] / out_name

                self.status(f"Creando clip {num}/{settings['clips_total']}")
                self.log(f"Creando {out_name}")

                cmd = self.build_ffmpeg_cmd(settings, num, clip_start, actual, out_file)
                self.run_ffmpeg(cmd)

                created += 1
                pct = int((num / settings["clips_total"]) * 100)
                self.progress_update(pct)

            self.progress_update(100)
            msg = f"Listo: {created} clip(s) creados"
            self.status(msg)
            self.log(msg)
            self.dialog("Finalizado", msg)

        except UserCancelled as exc:
            self.progress_update(0)
            self.status("Cancelado")
            self.log(str(exc))
            self.dialog("Cancelado", str(exc))

        except Exception as exc:
            self.progress_update(0)
            self.status("Error")
            self.log(f"ERROR: {exc}")
            self.dialog("Error", str(exc))

            try:
                with open("/storage/emulated/0/ClipForge_error.txt", "w", encoding="utf-8") as f:
                    f.write(traceback.format_exc())
            except Exception:
                pass

        finally:
            with self.process_lock:
                self.current_process = None

            self.set_running(False)

    def cancel_generation(self):
        self.cancel_event.set()
        self.status("Cancelando...")

        with self.process_lock:
            if self.current_process and self.current_process.poll() is None:
                try:
                    self.current_process.terminate()
                except Exception:
                    pass

    # ========================================================
    # UI HELPERS
    # ========================================================

    def status(self, msg):
        Clock.schedule_once(lambda dt: setattr(self.status_label, "text", str(msg)), 0)

    def log(self, msg):
        def append(dt):
            self.log_label.text += str(msg) + "\n"
        Clock.schedule_once(append, 0)

    def progress_update(self, pct):
        def update(dt):
            self.progress.value = pct
            self.progress_label.text = f"{pct}%"
        Clock.schedule_once(update, 0)

    def set_running(self, running):
        def update(dt):
            self.generate_btn.disabled = running
            self.cancel_btn.disabled = not running
        Clock.schedule_once(update, 0)

    def dialog(self, title, text):
        def open_popup(dt):
            layout = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))

            lbl = Label(
                text=str(text),
                color=(1, 1, 1, 1),
                font_size=dp(14),
            )

            btn = Button(
                text="OK",
                size_hint_y=None,
                height=dp(48),
                background_normal="",
                background_color=self.blue,
                color=(1, 1, 1, 1),
            )

            layout.add_widget(lbl)
            layout.add_widget(btn)

            popup = Popup(
                title=title,
                content=layout,
                size_hint=(0.90, None),
                height=dp(270),
            )

            btn.bind(on_release=lambda *a: popup.dismiss())
            popup.open()

        Clock.schedule_once(open_popup, 0)


if __name__ == "__main__":
    try:
        ClipForgeApp().run()
    except Exception:
        try:
            with open("/storage/emulated/0/ClipForge_error.txt", "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
        except Exception:
            pass
        raise
