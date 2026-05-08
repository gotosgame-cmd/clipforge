"""
ClipForge Studio — Versión Android corregida
Selector de videos corregido para abrir galería / archivos en Android.
"""

import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import List, Optional

from kivy.config import Config
Config.set("graphics", "width", "420")
Config.set("graphics", "height", "860")
Config.set("input", "mouse", "mouse,multitouch_on_demand")
Config.set("kivy", "exit_on_escape", "0")

from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.uix.image import Image as KivyImage
from kivy.uix.scrollview import ScrollView
from kivy.factory import Factory

from kivymd.app import MDApp
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.menu import MDDropdownMenu


QUALITY_PRESETS = {
    "Alta": {"preset": "slow", "crf": 17},
    "Balanceada": {"preset": "medium", "crf": 20},
    "Rápida": {"preset": "veryfast", "crf": 23},
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


class TouchScrollView(ScrollView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.do_scroll_x = False
        self.do_scroll_y = True
        self.scroll_type = ["bars", "content"]
        self.bar_width = dp(3)

    def on_touch_down(self, touch):
        touch.ud["scroll_start_y"] = touch.y
        touch.ud["scroll_start_x"] = touch.x
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if "scroll_start_y" in touch.ud:
            dy = abs(touch.y - touch.ud["scroll_start_y"])
            dx = abs(touch.x - touch.ud["scroll_start_x"])
            if dy > 10 and dy > dx:
                if self.collide_point(*touch.pos):
                    self.scroll_y -= touch.dy / self.height
                    self.scroll_y = max(0, min(1, self.scroll_y))
                    return True
        return super().on_touch_move(touch)


Factory.register("TouchScrollView", cls=TouchScrollView)


KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

<SectionCard@MDCard>:
    orientation: "vertical"
    padding: dp(10)
    spacing: dp(8)
    size_hint_y: None
    height: self.minimum_height
    md_bg_color: app.c_surface
    radius: [dp(8)]
    elevation: 0

<SectionTitle@MDLabel>:
    font_style: "Subtitle1"
    bold: True
    size_hint_y: None
    height: dp(30)
    theme_text_color: "Custom"
    text_color: app.c_text

<MutedLabel@MDLabel>:
    theme_text_color: "Custom"
    text_color: app.c_muted
    font_size: sp(13)
    size_hint: None, None
    size: dp(78), dp(44)
    valign: "middle"

<DarkField@MDTextField>:
    mode: "fill"
    size_hint_y: None
    height: dp(52)
    font_size: sp(13)
    fill_color_normal: app.c_field
    fill_color_focus: app.c_field
    text_color_normal: app.c_text
    text_color_focus: app.c_text
    hint_text_color_normal: app.c_muted

MDScreen:
    md_bg_color: app.c_bg

    TouchScrollView:
        id: main_scroll

        MDBoxLayout:
            orientation: "vertical"
            padding: [dp(12), dp(12)]
            spacing: dp(10)
            size_hint_y: None
            height: self.minimum_height

            MDBoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: dp(58)

                MDLabel:
                    text: "ClipForge Studio"
                    font_style: "H5"
                    bold: True
                    theme_text_color: "Custom"
                    text_color: app.c_text
                    size_hint_y: None
                    height: dp(38)

                MDLabel:
                    text: "Versión Android"
                    font_style: "Caption"
                    theme_text_color: "Custom"
                    text_color: app.c_muted
                    size_hint_y: None
                    height: dp(20)

            SectionCard:
                SectionTitle:
                    text: "Archivos"

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(52)
                    spacing: dp(8)

                    DarkField:
                        id: video_field
                        hint_text: "Selecciona un video"
                        size_hint_x: 1

                    MDRaisedButton:
                        text: "Buscar"
                        md_bg_color: app.c_button
                        size_hint: None, None
                        size: dp(88), dp(40)
                        pos_hint: {"center_y": .5}
                        on_release: app.pick_video()

                MDBoxLayout:
                    id: preview_box
                    size_hint_y: None
                    height: dp(150)
                    md_bg_color: app.c_surface2
                    radius: [dp(6)]
                    padding: dp(4)

                    MDLabel:
                        id: preview_label
                        text: "Vista previa"
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: app.c_muted

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(52)
                    spacing: dp(8)

                    DarkField:
                        id: out_field
                        hint_text: "Carpeta de salida"
                        size_hint_x: 1

                    MDRaisedButton:
                        text: "Carpeta"
                        md_bg_color: app.c_button
                        size_hint: None, None
                        size: dp(88), dp(40)
                        pos_hint: {"center_y": .5}
                        on_release: app.pick_out()

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(52)
                    spacing: dp(8)

                    DarkField:
                        id: wm_field
                        hint_text: "Marca de agua opcional"
                        size_hint_x: 1

                    MDRaisedButton:
                        text: "Imagen"
                        md_bg_color: app.c_button
                        size_hint: None, None
                        size: dp(88), dp(40)
                        pos_hint: {"center_y": .5}
                        on_release: app.pick_wm()

            SectionCard:
                SectionTitle:
                    text: "Clips"

                DarkField:
                    id: prefix_field
                    hint_text: "Prefijo de clips"
                    text: "Parte"

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(8)

                    MutedLabel:
                        text: "Calidad"

                    MDRaisedButton:
                        id: quality_btn
                        text: "Alta"
                        md_bg_color: app.c_field
                        size_hint_x: 1
                        on_release: app.show_quality_menu(self)

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(8)

                    MutedLabel:
                        text: "Duración"

                    MDSlider:
                        id: dur_slider
                        min: 2
                        max: 180
                        value: 10
                        step: 1
                        size_hint_x: 1
                        on_value: app.on_dur_change(self.value)

                    MDLabel:
                        id: dur_label
                        text: "10 s"
                        size_hint: None, None
                        size: dp(44), dp(44)
                        bold: True
                        valign: "middle"
                        theme_text_color: "Custom"
                        text_color: app.c_text

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(110)
                    spacing: dp(8)

                    MDCard:
                        md_bg_color: app.c_surface2
                        radius: [dp(6)]
                        padding: dp(8)
                        size_hint_x: 1
                        orientation: "vertical"
                        spacing: dp(4)

                        MDLabel:
                            text: "Inicio"
                            bold: True
                            size_hint_y: None
                            height: dp(24)
                            theme_text_color: "Custom"
                            text_color: app.c_text

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(52)
                            spacing: dp(4)

                            DarkField:
                                id: ini_m
                                text: "0"
                                hint_text: "min"
                                input_filter: "int"

                            MDLabel:
                                text: ":"
                                size_hint: None, None
                                size: dp(16), dp(52)
                                halign: "center"
                                bold: True
                                theme_text_color: "Custom"
                                text_color: app.c_text

                            DarkField:
                                id: ini_s
                                text: "0"
                                hint_text: "seg"
                                input_filter: "int"

                    MDCard:
                        md_bg_color: app.c_surface2
                        radius: [dp(6)]
                        padding: dp(8)
                        size_hint_x: 1
                        orientation: "vertical"
                        spacing: dp(4)

                        MDLabel:
                            text: "Fin 0=total"
                            bold: True
                            size_hint_y: None
                            height: dp(24)
                            theme_text_color: "Custom"
                            text_color: app.c_text

                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(52)
                            spacing: dp(4)

                            DarkField:
                                id: fin_m
                                text: "0"
                                hint_text: "min"
                                input_filter: "int"

                            MDLabel:
                                text: ":"
                                size_hint: None, None
                                size: dp(16), dp(52)
                                halign: "center"
                                bold: True
                                theme_text_color: "Custom"
                                text_color: app.c_text

                            DarkField:
                                id: fin_s
                                text: "0"
                                hint_text: "seg"
                                input_filter: "int"

            SectionCard:
                SectionTitle:
                    text: "Marca de agua"

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(8)

                    MutedLabel:
                        text: "Posición"

                    MDRaisedButton:
                        id: wm_pos_btn
                        text: "Arriba derecha"
                        md_bg_color: app.c_field
                        size_hint_x: 1
                        on_release: app.show_wm_pos_menu(self)

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(8)

                    MutedLabel:
                        text: "Tamaño"

                    MDSlider:
                        id: wm_size_slider
                        min: 40
                        max: 500
                        value: 120
                        step: 10
                        size_hint_x: 1
                        on_value: app.on_wm_size_change(self.value)

                    MDLabel:
                        id: wm_size_label
                        text: "120 px"
                        size_hint: None, None
                        size: dp(56), dp(44)
                        bold: True
                        valign: "middle"
                        theme_text_color: "Custom"
                        text_color: app.c_text

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(8)

                    MutedLabel:
                        text: "Opacidad"

                    MDSlider:
                        id: wm_opacity_slider
                        min: 0.10
                        max: 1.0
                        value: 0.80
                        step: 0.05
                        size_hint_x: 1
                        on_value: app.on_wm_opacity_change(self.value)

                    MDLabel:
                        id: wm_opacity_label
                        text: "80%"
                        size_hint: None, None
                        size: dp(44), dp(44)
                        bold: True
                        valign: "middle"
                        theme_text_color: "Custom"
                        text_color: app.c_text

            SectionCard:
                SectionTitle:
                    text: "Proceso"

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(24)
                    spacing: dp(8)

                    MDProgressBar:
                        id: progress_bar
                        value: 0
                        max: 100
                        size_hint_x: 1

                    MDLabel:
                        id: progress_label
                        text: "0%"
                        size_hint: None, None
                        size: dp(40), dp(24)
                        halign: "right"
                        bold: True
                        theme_text_color: "Custom"
                        text_color: app.c_muted

                MDLabel:
                    id: status_label
                    text: "Listo"
                    size_hint_y: None
                    height: dp(34)
                    theme_text_color: "Custom"
                    text_color: app.c_text

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(8)

                    MDRaisedButton:
                        id: generate_btn
                        text: "Generar"
                        md_bg_color: [0.13, 0.77, 0.37, 1]
                        size_hint_x: 1
                        on_release: app.start_generation()

                    MDRaisedButton:
                        id: cancel_btn
                        text: "Cancelar"
                        md_bg_color: [0.94, 0.27, 0.27, 1]
                        size_hint_x: 1
                        disabled: True
                        on_release: app.cancel_generation()

            SectionCard:
                SectionTitle:
                    text: "Registro"

                MDScrollView:
                    size_hint_y: None
                    height: dp(160)
                    do_scroll_x: False

                    MDLabel:
                        id: log_label
                        text: ""
                        size_hint_y: None
                        height: self.texture_size[1]
                        theme_text_color: "Custom"
                        text_color: [0.88, 0.91, 0.93, 1]
                        font_size: sp(11)
                        padding: [dp(4), dp(4)]
"""


class ClipForgeApp(MDApp):
    c_bg = [0.051, 0.067, 0.090, 1]
    c_surface = [0.067, 0.094, 0.137, 1]
    c_surface2 = [0.059, 0.090, 0.102, 1]
    c_field = [0.122, 0.161, 0.216, 1]
    c_text = [0.973, 0.980, 0.988, 1]
    c_muted = [0.580, 0.635, 0.722, 1]
    c_button = [0.145, 0.388, 0.922, 1]

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Green"

        if getattr(sys, "frozen", False):
            self.base_dir = Path(sys.executable).parent
        else:
            self.base_dir = Path(__file__).parent

        if sys.platform == "android":
            try:
                from android.storage import primary_external_storage_path  # type: ignore
                self.app_data_dir = Path(primary_external_storage_path()) / "ClipForgeStudio"
            except Exception:
                self.app_data_dir = Path.home() / "ClipForgeStudio"
        elif os.name == "nt":
            self.app_data_dir = Path(os.getenv("APPDATA", str(self.base_dir))) / "ClipForgeStudio"
        else:
            self.app_data_dir = Path.home() / ".clipforge_studio"

        self.app_data_dir.mkdir(parents=True, exist_ok=True)

        self.ffmpeg = self._resolve_binary("ffmpeg")
        self.ffprobe = self._resolve_binary("ffprobe")

        self.cancel_event = threading.Event()
        self.worker_thread = None
        self.current_process = None
        self.process_lock = threading.Lock()

        self._preview_img_widget = None
        self._quality = "Alta"
        self._wm_position = "Arriba derecha"
        self._pending_callback = None

        return Builder.load_string(KV)

    def on_start(self):
        if sys.platform == "android":
            Clock.schedule_once(lambda dt: self._request_android_permissions(), 1)

    def _request_android_permissions(self):
        try:
            from android.permissions import request_permissions, Permission  # type: ignore

            perms = []

            try:
                perms.append(Permission.READ_MEDIA_VIDEO)
                perms.append(Permission.READ_MEDIA_IMAGES)
            except AttributeError:
                perms.append(Permission.READ_EXTERNAL_STORAGE)
                perms.append(Permission.WRITE_EXTERNAL_STORAGE)

            def on_result(permissions, grants):
                self._log(f"Permisos media: {all(grants)}")

            request_permissions(perms, on_result)

        except Exception as exc:
            self._log(f"Error permisos: {exc}")

    def _resolve_binary(self, name: str) -> Path:
        suffix = ".exe" if os.name == "nt" else ""
        full = name + suffix

        local = self.base_dir / full
        if local.exists():
            return local

        found = shutil.which(full)
        if found:
            return Path(found)

        if sys.platform == "android":
            android_bin = self.app_data_dir / full
            if android_bin.exists():
                return android_bin

        return local

    def on_dur_change(self, value):
        self.root.ids.dur_label.text = f"{int(value)} s"

    def on_wm_size_change(self, value):
        self.root.ids.wm_size_label.text = f"{int(value)} px"

    def on_wm_opacity_change(self, value):
        self.root.ids.wm_opacity_label.text = f"{int(round(value * 100))}%"

    def show_quality_menu(self, caller):
        items = []
        for key in QUALITY_PRESETS:
            items.append({
                "text": key,
                "viewclass": "OneLineListItem",
                "on_release": lambda x=key: self._select_quality(x),
            })

        self._menu = MDDropdownMenu(caller=caller, items=items, width_mult=3)
        self._menu.open()

    def _select_quality(self, value):
        self._quality = value
        self.root.ids.quality_btn.text = value
        self._close_menu()

    def show_wm_pos_menu(self, caller):
        items = []
        for key in WM_POSITIONS:
            items.append({
                "text": key,
                "viewclass": "OneLineListItem",
                "on_release": lambda x=key: self._select_wm_pos(x),
            })

        self._menu = MDDropdownMenu(caller=caller, items=items, width_mult=4)
        self._menu.open()

    def _select_wm_pos(self, value):
        self._wm_position = value
        self.root.ids.wm_pos_btn.text = value
        self._close_menu()

    def _close_menu(self):
        if hasattr(self, "_menu") and self._menu:
            self._menu.dismiss()

    def pick_video(self):
        if sys.platform == "android":
            self._pick_android("video/*", self._on_video_selected)
        else:
            self._open_desktop_file(
                self._on_video_selected,
                ["*.mp4", "*.mov", "*.mkv", "*.avi", "*.m4v"],
                "Seleccionar video"
            )

    def pick_wm(self):
        if sys.platform == "android":
            self._pick_android("image/*", self._on_wm_selected)
        else:
            self._open_desktop_file(
                self._on_wm_selected,
                ["*.png", "*.jpg", "*.jpeg"],
                "Seleccionar imagen"
            )

    def _open_desktop_file(self, callback, filters, title):
        try:
            from kivy.uix.popup import Popup
            from kivy.uix.boxlayout import BoxLayout
            from kivy.uix.button import Button
            from kivy.uix.filechooser import FileChooserListView

            layout = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(6))
            chooser = FileChooserListView(path=str(Path.home()), filters=filters)
            buttons = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))

            popup = Popup(
                title=title,
                content=layout,
                size_hint=(0.97, 0.92),
            )

            def select_file(*args):
                selection = chooser.selection
                popup.dismiss()
                if selection:
                    callback([selection[0]])

            cancel = Button(text="Cancelar")
            ok = Button(text="Seleccionar")
            cancel.bind(on_release=lambda *a: popup.dismiss())
            ok.bind(on_release=select_file)

            buttons.add_widget(cancel)
            buttons.add_widget(ok)
            layout.add_widget(chooser)
            layout.add_widget(buttons)
            popup.open()

        except Exception:
            import traceback
            self._show_dialog("Error", traceback.format_exc())

    def _pick_android(self, mime_type, callback):
        """
        Selector corregido:
        abre galería / archivos nativos de Android usando ACTION_OPEN_DOCUMENT.
        """
        try:
            from android import activity  # type: ignore
            from jnius import autoclass  # type: ignore

            Intent = autoclass("android.content.Intent")

            self._pending_callback = callback

            intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.setType(mime_type)
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            intent.addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)

            activity.bind(on_activity_result=self._on_activity_result)

            title = "Seleccionar video" if "video" in mime_type else "Seleccionar imagen"
            chooser = Intent.createChooser(intent, title)

            activity.startActivityForResult(chooser, 1001)

        except Exception:
            import traceback
            self._show_dialog("Error abriendo galería", traceback.format_exc())

    def _on_activity_result(self, request_code, result_code, data):
        try:
            from android import activity  # type: ignore
            activity.unbind(on_activity_result=self._on_activity_result)

            if result_code != -1:
                self._log("Selector cancelado")
                return

            if data is None:
                self._show_dialog("Error", "El selector no devolvió datos.")
                return

            uri = data.getData()
            if uri is None:
                self._show_dialog("Error", "No se obtuvo URI.")
                return

            try:
                from jnius import autoclass  # type: ignore
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                Intent = autoclass("android.content.Intent")

                PythonActivity.mActivity.getContentResolver().takePersistableUriPermission(
                    uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION
                )
            except Exception as e:
                self._log(f"No se pudo guardar permiso persistente: {e}")

            self._log(f"URI recibido: {uri.toString()}")

            def copy_thread():
                try:
                    path = self._copy_uri_to_temp(uri)
                    if not path:
                        Clock.schedule_once(
                            lambda dt: self._show_dialog(
                                "Error",
                                "No se pudo leer el archivo seleccionado."
                            )
                        )
                        return

                    cb = self._pending_callback
                    if cb:
                        Clock.schedule_once(lambda dt: cb([path]))

                except Exception:
                    import traceback
                    msg = traceback.format_exc()
                    Clock.schedule_once(lambda dt: self._show_dialog("Error", msg))

            threading.Thread(target=copy_thread, daemon=True).start()

        except Exception:
            import traceback
            self._show_dialog("Error", traceback.format_exc())

    def _copy_uri_to_temp(self, uri) -> Optional[str]:
        """
        Copia el video/imagen del URI de Android a un archivo local.
        FFmpeg no puede leer content:// directamente, por eso se copia.
        """
        try:
            from jnius import autoclass  # type: ignore

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            FileOutputStream = autoclass("java.io.FileOutputStream")

            context = PythonActivity.mActivity
            resolver = context.getContentResolver()
            input_stream = resolver.openInputStream(uri)

            if input_stream is None:
                self._log("No se pudo abrir el stream del URI.")
                return None

            mime = resolver.getType(uri)

            ext = ".mp4"
            if mime:
                if "image" in mime:
                    if "jpeg" in mime or "jpg" in mime:
                        ext = ".jpg"
                    elif "png" in mime:
                        ext = ".png"
                    else:
                        ext = ".img"
                elif "video" in mime:
                    if "mp4" in mime:
                        ext = ".mp4"
                    elif "quicktime" in mime:
                        ext = ".mov"
                    elif "x-matroska" in mime:
                        ext = ".mkv"
                    else:
                        ext = ".mp4"

            self.app_data_dir.mkdir(parents=True, exist_ok=True)

            fd, temp_path = tempfile.mkstemp(
                prefix="clipforge_selected_",
                suffix=ext,
                dir=str(self.app_data_dir)
            )
            os.close(fd)

            output_stream = FileOutputStream(temp_path)
            buffer = bytearray(131072)

            while True:
                n = input_stream.read(buffer)
                if n < 0:
                    break
                output_stream.write(buffer, 0, n)

            output_stream.flush()
            output_stream.close()
            input_stream.close()

            return temp_path

        except Exception:
            import traceback
            self._log(f"Error copiando URI:\n{traceback.format_exc()}")
            return None

    def _on_video_selected(self, selection):
        if not selection:
            return

        path = selection[0]
        self.root.ids.video_field.text = path
        self._log(f"Video: {path}")
        self._update_status("Video seleccionado")

        if self.ffmpeg.exists():
            self._update_status("Generando vista previa...")
            threading.Thread(
                target=self._generate_preview,
                args=(path,),
                daemon=True
            ).start()
        else:
            self._log("ffmpeg no encontrado. No se genera vista previa.")

    def _on_wm_selected(self, selection):
        if not selection:
            return

        path = selection[0]
        self.root.ids.wm_field.text = path
        self._log(f"Marca de agua: {path}")

    def pick_out(self):
        if sys.platform == "android":
            try:
                from jnius import autoclass  # type: ignore
                Environment = autoclass("android.os.Environment")
                movies_dir = Environment.getExternalStoragePublicDirectory(
                    Environment.DIRECTORY_MOVIES
                ).getAbsolutePath()

                out = str(Path(movies_dir) / "ClipForge")
                Path(out).mkdir(parents=True, exist_ok=True)

                self.root.ids.out_field.text = out
                self._log(f"Salida: {out}")
                self._show_dialog("Carpeta de salida", f"Los clips se guardarán en:\n{out}")

            except Exception as exc:
                fallback = str(self.app_data_dir / "output")
                Path(fallback).mkdir(parents=True, exist_ok=True)
                self.root.ids.out_field.text = fallback
                self._log(f"Salida fallback: {fallback}")
                self._show_dialog("Carpeta de salida", f"Los clips se guardarán en:\n{fallback}")

        else:
            from kivy.uix.popup import Popup
            from kivy.uix.boxlayout import BoxLayout
            from kivy.uix.button import Button
            from kivy.uix.filechooser import FileChooserListView

            layout = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(6))
            chooser = FileChooserListView(path=str(Path.home()), dirselect=True)
            buttons = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))

            popup = Popup(
                title="Seleccionar carpeta",
                content=layout,
                size_hint=(0.97, 0.92)
            )

            def select_dir(*args):
                selection = chooser.selection
                popup.dismiss()
                if selection:
                    self.root.ids.out_field.text = selection[0]
                    self._log(f"Salida: {selection[0]}")

            cancel = Button(text="Cancelar")
            ok = Button(text="Seleccionar")
            cancel.bind(on_release=lambda *a: popup.dismiss())
            ok.bind(on_release=select_dir)

            buttons.add_widget(cancel)
            buttons.add_widget(ok)
            layout.add_widget(chooser)
            layout.add_widget(buttons)
            popup.open()

    def _generate_preview(self, video_path: str):
        try:
            duration = self._probe_duration(Path(video_path))
            preview_time = min(3.0, max(0.2, duration / 3))

            fd, temp_path = tempfile.mkstemp(
                prefix="clipforge_preview_",
                suffix=".jpg"
            )
            os.close(fd)

            cmd = [
                str(self.ffmpeg),
                "-hide_banner",
                "-loglevel", "error",
                "-y",
                "-ss", f"{preview_time:.2f}",
                "-i", video_path,
                "-frames:v", "1",
                temp_path,
            ]

            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            Clock.schedule_once(lambda dt: self._show_preview(temp_path))

        except Exception as exc:
            Clock.schedule_once(
                lambda dt: self._update_status(f"Sin vista previa: {exc}")
            )

    def _show_preview(self, image_path: str):
        box = self.root.ids.preview_box
        label = self.root.ids.preview_label

        if self._preview_img_widget:
            box.remove_widget(self._preview_img_widget)
            self._preview_img_widget = None

        label.text = ""
        img = KivyImage(source=image_path, allow_stretch=True, keep_ratio=True)
        box.add_widget(img)
        self._preview_img_widget = img

        self._update_status("Vista previa lista")

    def _update_status(self, msg: str):
        def set_status(dt):
            self.root.ids.status_label.text = msg

        Clock.schedule_once(set_status)

    def _update_progress(self, pct: int):
        def set_progress(dt):
            self.root.ids.progress_bar.value = pct
            self.root.ids.progress_label.text = f"{pct}%"

        Clock.schedule_once(set_progress)

    def _log(self, msg: str):
        def append_log(dt):
            try:
                self.root.ids.log_label.text += f"{msg}\n"
            except Exception:
                pass

        Clock.schedule_once(append_log)

    def _set_running(self, running: bool):
        def set_ui(dt):
            self.root.ids.generate_btn.disabled = running
            self.root.ids.cancel_btn.disabled = not running

        Clock.schedule_once(set_ui)

    def _show_dialog(self, title: str, text: str):
        def open_dialog(dt):
            btn = MDFlatButton(text="OK")
            dlg = MDDialog(title=title, text=text, buttons=[btn])
            btn.bind(on_release=lambda *a: dlg.dismiss())
            dlg.open()

        Clock.schedule_once(open_dialog)

    def _safe_int(self, value: str, name: str) -> int:
        try:
            n = int(value.strip())
        except Exception:
            raise ValueError(f"{name} debe ser un número entero.")

        if n < 0:
            raise ValueError(f"{name} no puede ser negativo.")

        return n

    def _time_to_sec(self, m: str, s: str, prefix: str) -> int:
        mins = self._safe_int(m, f"{prefix} minutos")
        secs = self._safe_int(s, f"{prefix} segundos")

        if secs > 59:
            raise ValueError(f"{prefix} segundos debe estar entre 0 y 59.")

        return mins * 60 + secs

    def _validate(self) -> dict:
        ids = self.root.ids

        video_raw = ids.video_field.text.strip()
        out_raw = ids.out_field.text.strip()
        wm_raw = ids.wm_field.text.strip()

        if not video_raw:
            raise ValueError("Selecciona un video.")

        video_path = Path(video_raw)
        if not video_path.exists():
            raise FileNotFoundError("El video seleccionado no existe.")

        if not out_raw:
            raise ValueError("Selecciona una carpeta de salida.")

        out_dir = Path(out_raw)
        out_dir.mkdir(parents=True, exist_ok=True)

        wm_path = Path(wm_raw) if wm_raw else None
        if wm_path and not wm_path.exists():
            raise FileNotFoundError("La marca de agua no existe.")

        if not self.ffmpeg.exists():
            raise FileNotFoundError(
                f"ffmpeg no encontrado.\n"
                f"Coloca el binario ffmpeg en:\n{self.base_dir}\n\n"
                "En Android necesitas incluir ffmpeg compatible con ARM64."
            )

        if not self.ffprobe.exists():
            raise FileNotFoundError(
                f"ffprobe no encontrado.\n"
                f"Coloca el binario ffprobe en:\n{self.base_dir}"
            )

        start_sec = self._time_to_sec(ids.ini_m.text, ids.ini_s.text, "Inicio")
        end_sec = self._time_to_sec(ids.fin_m.text, ids.fin_s.text, "Fin")
        clip_dur = int(ids.dur_slider.value)

        total_dur = self._probe_duration(video_path)

        if start_sec >= total_dur:
            raise ValueError("El tiempo de inicio supera la duración del video.")

        if end_sec == 0 or end_sec > total_dur:
            end_sec = int(math.ceil(total_dur))

        if end_sec <= start_sec:
            raise ValueError("El tiempo final debe ser mayor que el inicial.")

        clips_total = math.ceil((end_sec - start_sec) / clip_dur)

        if clips_total <= 0:
            raise ValueError("No hay clips válidos con ese rango.")

        return {
            "video": video_path,
            "out_dir": out_dir,
            "watermark": wm_path,
            "text_prefix": ids.prefix_field.text.strip() or "Parte",
            "start_sec": start_sec,
            "end_sec": end_sec,
            "clip_duration": clip_dur,
            "clips_total": clips_total,
            "quality": self._quality,
            "wm_size": int(ids.wm_size_slider.value),
            "wm_opacity": float(ids.wm_opacity_slider.value),
            "wm_position": self._wm_position,
        }

    def _probe_duration(self, video_path: Path) -> float:
        cmd = [
            str(self.ffprobe),
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nokey=1:noprint_wrappers=1",
            str(video_path),
        ]

        output = subprocess.check_output(cmd, text=True).strip()
        return float(output)

    def _build_ffmpeg_cmd(
        self,
        settings: dict,
        clip_index: int,
        clip_start: float,
        clip_duration: float,
        output_file: Path
    ) -> List[str]:

        quality = QUALITY_PRESETS[settings["quality"]]
        filter_complex = self._build_filter_complex(settings, clip_index)

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
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", quality["preset"],
            "-crf", str(quality["crf"]),
            "-profile:v", "high",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_file),
        ]

        return cmd

    def _build_filter_complex(self, settings: dict, clip_index: int) -> str:
        text = self._escape_drawtext(f"{settings['text_prefix']} {clip_index}")
        font_part = self._get_font_part()

        drawtext = (
            f"drawtext={font_part}"
            f"text='{text}':"
            "fontcolor=white:"
            "fontsize=34:"
            "borderw=2:"
            "bordercolor=black@0.65:"
            "x=(w-text_w)/2:"
            "y=24:"
            "alpha='if(lt(t,1),t,1)'"
        )

        chains = []
        base_label = "0:v"

        if settings["watermark"]:
            opacity = max(0.10, min(1.00, settings["wm_opacity"]))
            position = WM_POSITIONS[settings["wm_position"]]

            chains.append(
                f"[1:v]scale={settings['wm_size']}:-1,"
                f"format=rgba,"
                f"colorchannelmixer=aa={opacity:.2f}[wm]"
            )

            chains.append(f"[0:v][wm]overlay={position}[base]")
            base_label = "base"

        chains.append(f"[{base_label}]{drawtext}[v]")

        return ";".join(chains)

    def _get_font_part(self) -> str:
        candidates = [
            self.base_dir / "arial.ttf",
            self.base_dir / "segoeui.ttf",
            Path("/system/fonts/Roboto-Regular.ttf"),
            Path("/system/fonts/DroidSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
        ]

        for path in candidates:
            if path.exists():
                return f"fontfile='{self._escape_path(str(path))}':"

        return ""

    def _escape_drawtext(self, text: str) -> str:
        return (
            text.replace("\\", r"\\")
            .replace(":", r"\:")
            .replace("'", r"\'")
            .replace("%", r"\%")
            .replace("[", r"\[")
            .replace("]", r"\]")
            .replace(",", r"\,")
            .replace(";", r"\;")
        )

    def _escape_path(self, path: str) -> str:
        return path.replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'")

    def _run_ffmpeg(self, cmd: List[str]):
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
                except subprocess.TimeoutExpired:
                    proc.kill()

                raise UserCancelled("Cancelado por el usuario.")

            time.sleep(0.15)

        _, stderr = proc.communicate()

        with self.process_lock:
            if self.current_process is proc:
                self.current_process = None

        if proc.returncode != 0:
            detail = stderr.strip() or "sin detalle"
            raise RuntimeError(f"FFmpeg error:\n{detail[-1200:]}")

    def start_generation(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self._show_dialog("En progreso", "Ya hay un proceso ejecutándose.")
            return

        try:
            settings = self._validate()
        except Exception as exc:
            self._show_dialog("Validación", str(exc))
            self._log(f"Validación fallida: {exc}")
            return

        self.root.ids.progress_bar.value = 0
        self.root.ids.progress_label.text = "0%"
        self.root.ids.log_label.text = ""

        self.cancel_event.clear()
        self._set_running(True)

        self._update_status("Preparando proceso...")
        self._log("=" * 40)
        self._log("Inicio de generación")
        self._log(f"Video: {settings['video']}")
        self._log(f"Clips: {settings['clips_total']}")

        self.worker_thread = threading.Thread(
            target=self._worker,
            args=(settings,),
            daemon=True
        )
        self.worker_thread.start()

    def cancel_generation(self):
        if not self.worker_thread or not self.worker_thread.is_alive():
            return

        self.cancel_event.set()
        self._update_status("Cancelando...")
        self._log("Cancelación solicitada...")

        with self.process_lock:
            if self.current_process and self.current_process.poll() is None:
                try:
                    self.current_process.terminate()
                except Exception:
                    pass

    def _worker(self, settings: dict):
        created = 0
        digits = max(3, len(str(settings["clips_total"])))

        try:
            for index in range(settings["clips_total"]):
                if self.cancel_event.is_set():
                    raise UserCancelled("Cancelado por el usuario.")

                start_t = settings["start_sec"] + index * settings["clip_duration"]
                actual_d = min(
                    settings["clip_duration"],
                    settings["end_sec"] - start_t
                )

                if actual_d <= 0:
                    break

                out_name = (
                    f"{settings['video'].stem}_clip_"
                    f"{index + 1:0{digits}d}.mp4"
                )
                out_file = settings["out_dir"] / out_name

                self._update_status(
                    f"Clip {index + 1}/{settings['clips_total']}..."
                )
                self._log(f"Creando {out_name} ({actual_d:.1f}s)")

                cmd = self._build_ffmpeg_cmd(
                    settings,
                    index + 1,
                    start_t,
                    actual_d,
                    out_file
                )

                self._run_ffmpeg(cmd)
                created += 1

                pct = int(((index + 1) / settings["clips_total"]) * 100)
                self._update_progress(pct)

            self._update_progress(100)
            msg = f"Listo: {created} clip(s) creados"
            self._update_status(msg)
            self._log(msg)
            self._show_dialog("Proceso finalizado", msg)

        except UserCancelled as exc:
            self._update_progress(0)
            self._update_status("Cancelado")
            self._log(str(exc))
            self._show_dialog("Cancelado", str(exc))

        except Exception as exc:
            self._update_progress(0)
            self._update_status("Error")
            self._log(f"ERROR: {exc}")
            self._show_dialog("Error", str(exc))

        finally:
            with self.process_lock:
                self.current_process = None

            self._set_running(False)


if __name__ == "__main__":
    ClipForgeApp().run()
