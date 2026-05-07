"""
ClipForge Studio — Versión Android
Migrado de tkinter a Kivy + KivyMD
"""

import math, os, shutil, subprocess, sys, tempfile, threading, time
from pathlib import Path
from typing import List, Optional

# ── Kivy config ANTES de cualquier import de kivy ───────────────────────────
from kivy.config import Config
Config.set("graphics", "width",  "420")
Config.set("graphics", "height", "860")
Config.set("input", "mouse", "mouse,multitouch_on_demand")

from kivy.clock   import Clock
from kivy.lang    import Builder
from kivy.metrics import dp, sp
from kivy.uix.image import Image as KivyImage

from kivymd.app          import MDApp
from kivymd.uix.button   import MDRaisedButton, MDFlatButton
from kivymd.uix.dialog   import MDDialog
from kivymd.uix.label    import MDLabel
from kivymd.uix.menu     import MDDropdownMenu

from PIL import Image as PILImage

try:
    from plyer import filechooser
    PLYER_OK = True
except ImportError:
    PLYER_OK = False

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials       import Credentials
    from google_auth_oauthlib.flow       import InstalledAppFlow
    from googleapiclient.discovery       import build
    from googleapiclient.http            import MediaFileUpload
    DRIVE_ERR = None
except Exception as exc:
    Request = Credentials = InstalledAppFlow = build = MediaFileUpload = None
    DRIVE_ERR = exc


# ── Constantes (sin cambios) ─────────────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

QUALITY_PRESETS = {
    "Alta":       {"preset": "slow",     "crf": 17},
    "Balanceada": {"preset": "medium",   "crf": 20},
    "Rápida":     {"preset": "veryfast", "crf": 23},
}

WM_POSITIONS = {
    "Arriba derecha":   "W-w-20:20",
    "Arriba izquierda": "20:20",
    "Abajo derecha":    "W-w-20:H-h-20",
    "Abajo izquierda":  "20:H-h-20",
    "Centro":           "(W-w)/2:(H-h)/2",
}


# ── Excepciones ──────────────────────────────────────────────────────────────
class UserCancelled(Exception):
    pass


# ── Google Drive Uploader (sin cambios) ──────────────────────────────────────
class DriveUploader:
    def __init__(self, credentials_file: Path, token_file: Path):
        self.credentials_file = credentials_file
        self.token_file       = token_file
        self.service          = None

    def auth(self):
        if DRIVE_ERR is not None:
            raise RuntimeError("Faltan dependencias de Google Drive.") from DRIVE_ERR
        if not self.credentials_file.exists():
            raise FileNotFoundError(f"No se encontró credentials.json en:\n{self.credentials_file}")
        creds = None
        if self.token_file.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif not creds or not creds.valid:
            flow  = InstalledAppFlow.from_client_secrets_file(str(self.credentials_file), SCOPES)
            creds = flow.run_local_server(port=0)
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(creds.to_json(), encoding="utf-8")
        self.service = build("drive", "v3", credentials=creds)
        return self.service

    def upload_file(self, file_path: Path, folder_id: Optional[str] = None) -> dict:
        service  = self.service or self.auth()
        metadata = {"name": file_path.name}
        if folder_id:
            metadata["parents"] = [folder_id]
        media = MediaFileUpload(str(file_path), mimetype="video/mp4", resumable=False)
        return service.files().create(body=metadata, media_body=media, fields="id,name,webViewLink").execute()


# ── KV Layout ────────────────────────────────────────────────────────────────
KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

<SectionCard@MDCard>:
    orientation: 'vertical'
    padding: dp(10)
    spacing: dp(8)
    size_hint_y: None
    height: self.minimum_height
    md_bg_color: app.c_surface
    radius: [dp(8)]
    elevation: 0

<SectionTitle@MDLabel>:
    font_style: 'Subtitle1'
    bold: True
    size_hint_y: None
    height: dp(30)
    theme_text_color: 'Custom'
    text_color: app.c_text

<MutedLabel@MDLabel>:
    theme_text_color: 'Custom'
    text_color: app.c_muted
    font_size: sp(13)
    size_hint: None, None
    size: dp(78), dp(44)
    valign: 'middle'

<DarkField@MDTextField>:
    mode: 'fill'
    size_hint_y: None
    height: dp(52)
    font_size: sp(13)
    fill_color_normal: app.c_field
    fill_color_focus:  app.c_field
    text_color_normal: app.c_text
    text_color_focus:  app.c_text
    hint_text_color_normal: app.c_muted

MDScreen:
    md_bg_color: app.c_bg

    MDScrollView:
        do_scroll_x: False

        MDBoxLayout:
            orientation: 'vertical'
            padding: [dp(12), dp(12)]
            spacing: dp(10)
            size_hint_y: None
            height: self.minimum_height

            # ─── Header ───────────────────────────────────────────────────
            MDBoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: dp(58)
                MDLabel:
                    text: 'ClipForge Studio'
                    font_style: 'H5'
                    bold: True
                    theme_text_color: 'Custom'
                    text_color: app.c_text
                    size_hint_y: None
                    height: dp(38)
                MDLabel:
                    text: 'Versión Android'
                    font_style: 'Caption'
                    theme_text_color: 'Custom'
                    text_color: app.c_muted
                    size_hint_y: None
                    height: dp(20)

            # ─── Archivos ─────────────────────────────────────────────────
            SectionCard:
                SectionTitle:
                    text: 'Archivos'

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(52)
                    spacing: dp(8)
                    DarkField:
                        id: video_field
                        hint_text: 'Selecciona un video'
                        size_hint_x: 1
                    MDRaisedButton:
                        text: 'Buscar'
                        md_bg_color: app.c_button
                        size_hint: None, None
                        size: dp(88), dp(40)
                        pos_hint: {'center_y': .5}
                        on_release: app.pick_video()

                # Vista previa
                MDBoxLayout:
                    id: preview_box
                    size_hint_y: None
                    height: dp(150)
                    md_bg_color: app.c_surface2
                    radius: [dp(6)]
                    padding: dp(4)
                    MDLabel:
                        id: preview_label
                        text: 'Vista previa'
                        halign: 'center'
                        theme_text_color: 'Custom'
                        text_color: app.c_muted

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(52)
                    spacing: dp(8)
                    DarkField:
                        id: out_field
                        hint_text: 'Carpeta de salida'
                        size_hint_x: 1
                    MDRaisedButton:
                        text: 'Carpeta'
                        md_bg_color: app.c_button
                        size_hint: None, None
                        size: dp(88), dp(40)
                        pos_hint: {'center_y': .5}
                        on_release: app.pick_out()

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(52)
                    spacing: dp(8)
                    DarkField:
                        id: wm_field
                        hint_text: 'Marca de agua (opcional)'
                        size_hint_x: 1
                    MDRaisedButton:
                        text: 'Imagen'
                        md_bg_color: app.c_button
                        size_hint: None, None
                        size: dp(88), dp(40)
                        pos_hint: {'center_y': .5}
                        on_release: app.pick_wm()

            # ─── Clips ────────────────────────────────────────────────────
            SectionCard:
                SectionTitle:
                    text: 'Clips'

                DarkField:
                    id: prefix_field
                    hint_text: 'Prefijo de clips'
                    text: 'Parte'

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(8)
                    MutedLabel:
                        text: 'Calidad'
                    MDRaisedButton:
                        id: quality_btn
                        text: 'Alta'
                        md_bg_color: app.c_field
                        size_hint_x: 1
                        on_release: app.show_quality_menu(self)

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(8)
                    MutedLabel:
                        text: 'Duración'
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
                        text: '10 s'
                        size_hint: None, None
                        size: dp(44), dp(44)
                        bold: True
                        valign: 'middle'
                        theme_text_color: 'Custom'
                        text_color: app.c_text

                # Rango de tiempo
                MDBoxLayout:
                    size_hint_y: None
                    height: dp(110)
                    spacing: dp(8)

                    MDCard:
                        md_bg_color: app.c_surface2
                        radius: [dp(6)]
                        padding: dp(8)
                        size_hint_x: 1
                        orientation: 'vertical'
                        spacing: dp(4)
                        MDLabel:
                            text: 'Inicio'
                            bold: True
                            size_hint_y: None
                            height: dp(24)
                            theme_text_color: 'Custom'
                            text_color: app.c_text
                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(52)
                            spacing: dp(4)
                            DarkField:
                                id: ini_m
                                text: '0'
                                hint_text: 'min'
                                input_filter: 'int'
                                size_hint_x: 1
                            MDLabel:
                                text: ':'
                                size_hint: None, None
                                size: dp(16), dp(52)
                                halign: 'center'
                                bold: True
                                theme_text_color: 'Custom'
                                text_color: app.c_text
                            DarkField:
                                id: ini_s
                                text: '0'
                                hint_text: 'seg'
                                input_filter: 'int'
                                size_hint_x: 1

                    MDCard:
                        md_bg_color: app.c_surface2
                        radius: [dp(6)]
                        padding: dp(8)
                        size_hint_x: 1
                        orientation: 'vertical'
                        spacing: dp(4)
                        MDLabel:
                            text: 'Fin (0=total)'
                            bold: True
                            size_hint_y: None
                            height: dp(24)
                            theme_text_color: 'Custom'
                            text_color: app.c_text
                        MDBoxLayout:
                            size_hint_y: None
                            height: dp(52)
                            spacing: dp(4)
                            DarkField:
                                id: fin_m
                                text: '0'
                                hint_text: 'min'
                                input_filter: 'int'
                                size_hint_x: 1
                            MDLabel:
                                text: ':'
                                size_hint: None, None
                                size: dp(16), dp(52)
                                halign: 'center'
                                bold: True
                                theme_text_color: 'Custom'
                                text_color: app.c_text
                            DarkField:
                                id: fin_s
                                text: '0'
                                hint_text: 'seg'
                                input_filter: 'int'
                                size_hint_x: 1

            # ─── Marca de agua ────────────────────────────────────────────
            SectionCard:
                SectionTitle:
                    text: 'Marca de agua'

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(8)
                    MutedLabel:
                        text: 'Posición'
                    MDRaisedButton:
                        id: wm_pos_btn
                        text: 'Arriba derecha'
                        md_bg_color: app.c_field
                        size_hint_x: 1
                        on_release: app.show_wm_pos_menu(self)

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(8)
                    MutedLabel:
                        text: 'Tamaño'
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
                        text: '120 px'
                        size_hint: None, None
                        size: dp(56), dp(44)
                        bold: True
                        valign: 'middle'
                        theme_text_color: 'Custom'
                        text_color: app.c_text

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(8)
                    MutedLabel:
                        text: 'Opacidad'
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
                        text: '80%'
                        size_hint: None, None
                        size: dp(44), dp(44)
                        bold: True
                        valign: 'middle'
                        theme_text_color: 'Custom'
                        text_color: app.c_text

            # ─── Drive y exportación ──────────────────────────────────────
            SectionCard:
                SectionTitle:
                    text: 'Drive y exportación'

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(8)
                    MDCheckbox:
                        id: drive_check
                        size_hint: None, None
                        size: dp(44), dp(44)
                        on_active: app.toggle_drive(self.active)
                    MDLabel:
                        text: 'Subir a Google Drive'
                        theme_text_color: 'Custom'
                        text_color: app.c_text
                        size_hint_y: None
                        height: dp(44)
                        valign: 'middle'

                DarkField:
                    id: drive_id_field
                    hint_text: 'Folder ID de Drive (opcional)'
                    disabled: True

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(8)
                    MDCheckbox:
                        id: open_folder_check
                        size_hint: None, None
                        size: dp(44), dp(44)
                        active: True
                    MDLabel:
                        text: 'Abrir carpeta al terminar'
                        theme_text_color: 'Custom'
                        text_color: app.c_text
                        size_hint_y: None
                        height: dp(44)
                        valign: 'middle'

            # ─── Proceso ──────────────────────────────────────────────────
            SectionCard:
                SectionTitle:
                    text: 'Proceso'

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
                        text: '0%'
                        size_hint: None, None
                        size: dp(40), dp(24)
                        halign: 'right'
                        bold: True
                        theme_text_color: 'Custom'
                        text_color: app.c_muted

                MDLabel:
                    id: status_label
                    text: 'Listo'
                    size_hint_y: None
                    height: dp(34)
                    theme_text_color: 'Custom'
                    text_color: app.c_text

                MDBoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(8)
                    MDRaisedButton:
                        id: generate_btn
                        text: 'Generar'
                        md_bg_color: [0.13, 0.77, 0.37, 1]
                        size_hint_x: 1
                        on_release: app.start_generation()
                    MDRaisedButton:
                        id: cancel_btn
                        text: 'Cancelar'
                        md_bg_color: [0.94, 0.27, 0.27, 1]
                        size_hint_x: 1
                        disabled: True
                        on_release: app.cancel_generation()

            # ─── Registro ────────────────────────────────────────────────
            SectionCard:
                SectionTitle:
                    text: 'Registro'
                MDScrollView:
                    size_hint_y: None
                    height: dp(160)
                    do_scroll_x: False
                    MDLabel:
                        id: log_label
                        text: ''
                        size_hint_y: None
                        height: self.texture_size[1]
                        theme_text_color: 'Custom'
                        text_color: [0.88, 0.91, 0.93, 1]
                        font_size: sp(11)
                        padding: [dp(4), dp(4)]
"""


# ── App principal ────────────────────────────────────────────────────────────
class ClipForgeApp(MDApp):

    # Paleta de colores (mismo esquema que la versión tkinter)
    c_bg      = [0.051, 0.067, 0.090, 1]   # #0d1117
    c_surface = [0.067, 0.094, 0.137, 1]   # #111827
    c_surface2= [0.059, 0.090, 0.102, 1]   # #0f172a
    c_field   = [0.122, 0.161, 0.216, 1]   # #1f2937
    c_text    = [0.973, 0.980, 0.988, 1]   # #f8fafc
    c_muted   = [0.580, 0.635, 0.722, 1]   # #94a3b8
    c_button  = [0.145, 0.388, 0.922, 1]   # #2563eb
    c_accent  = [0.133, 0.773, 0.369, 1]   # #22c55e

    def build(self):
        self.theme_cls.theme_style     = "Dark"
        self.theme_cls.primary_palette = "Green"

        # Directorios base
        if getattr(sys, "frozen", False):
            self.base_dir = Path(sys.executable).parent
        else:
            self.base_dir = Path(__file__).parent

        self.ffmpeg  = self._resolve_binary("ffmpeg")
        self.ffprobe = self._resolve_binary("ffprobe")

        # Ruta de datos de la app
        if sys.platform == "android":
            from android.storage import primary_external_storage_path  # type: ignore
            self.app_data_dir = Path(primary_external_storage_path()) / "ClipForgeStudio"
        elif os.name == "nt":
            self.app_data_dir = Path(os.getenv("APPDATA", str(self.base_dir))) / "ClipForgeStudio"
        else:
            self.app_data_dir = Path.home() / ".clipforge_studio"

        self.credentials_file = self.base_dir / "credentials.json"
        self.token_file       = self.app_data_dir / "token.json"
        self.drive_uploader   = DriveUploader(self.credentials_file, self.token_file)

        # Estado interno
        self.cancel_event    = threading.Event()
        self.worker_thread   = None
        self.current_process = None
        self.process_lock    = threading.Lock()
        self._preview_img_widget = None
        self._quality        = "Alta"
        self._wm_position    = "Arriba derecha"

        return Builder.load_string(KV)

    def on_start(self):
        # En Android, solicitar permisos de almacenamiento
        if sys.platform == "android":
            from android.permissions import request_permissions, Permission  # type: ignore
            request_permissions([
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
            ])

    # ── Resolución de binarios ───────────────────────────────────────────────
    def _resolve_binary(self, name: str) -> Path:
        suffix = ".exe" if os.name == "nt" else ""
        full   = name + suffix
        local  = self.base_dir / full
        if local.exists():
            return local
        found  = shutil.which(full)
        if found:
            return Path(found)
        # Android: busca en la carpeta de datos de la app
        if sys.platform == "android":
            android_bin = self.app_data_dir / full
            if android_bin.exists():
                return android_bin
        return local

    # ── Callbacks de sliders ─────────────────────────────────────────────────
    def on_dur_change(self, value):
        self.root.ids.dur_label.text = f"{int(value)} s"

    def on_wm_size_change(self, value):
        self.root.ids.wm_size_label.text = f"{int(value)} px"

    def on_wm_opacity_change(self, value):
        self.root.ids.wm_opacity_label.text = f"{int(round(value * 100))}%"

    # ── Menús desplegables ───────────────────────────────────────────────────
    def show_quality_menu(self, caller):
        items = [
            {
                "text": k,
                "viewclass": "OneLineListItem",
                "on_release": lambda x=k: (self._set_quality(x), self._close_menu()),
            }
            for k in QUALITY_PRESETS
        ]
        self._menu = MDDropdownMenu(caller=caller, items=items, width_mult=3)
        self._menu.open()

    def _set_quality(self, value):
        self._quality = value
        self.root.ids.quality_btn.text = value

    def show_wm_pos_menu(self, caller):
        items = [
            {
                "text": k,
                "viewclass": "OneLineListItem",
                "on_release": lambda x=k: (self._set_wm_pos(x), self._close_menu()),
            }
            for k in WM_POSITIONS
        ]
        self._menu = MDDropdownMenu(caller=caller, items=items, width_mult=4)
        self._menu.open()

    def _set_wm_pos(self, value):
        self._wm_position = value
        self.root.ids.wm_pos_btn.text = value

    def _close_menu(self):
        if hasattr(self, "_menu") and self._menu:
            self._menu.dismiss()

    # ── Toggle Drive ─────────────────────────────────────────────────────────
    def toggle_drive(self, active):
        self.root.ids.drive_id_field.disabled = not active

    # ── Selectores de archivos ───────────────────────────────────────────────
    def pick_video(self):
        if PLYER_OK:
            filechooser.open_file(
                on_selection=self._on_video_selected,
                filters=["*.mp4", "*.mov", "*.mkv", "*.avi", "*.m4v"],
                multiple=False,
            )
        else:
            self._show_dialog("Error", "plyer no disponible. Instala: pip install plyer")

    def _on_video_selected(self, selection):
        if not selection:
            return
        path = selection[0]
        Clock.schedule_once(lambda dt: setattr(self.root.ids.video_field, "text", path))
        self._log(f"Video: {path}")
        self._update_status("Generando vista previa...")
        threading.Thread(target=self._generate_preview, args=(path,), daemon=True).start()

    def pick_out(self):
        if PLYER_OK:
            filechooser.choose_dir(
                on_selection=self._on_out_selected,
                multiple=False,
            )
        else:
            self._show_dialog("Error", "plyer no disponible.")

    def _on_out_selected(self, selection):
        if not selection:
            return
        path = selection[0]
        Clock.schedule_once(lambda dt: setattr(self.root.ids.out_field, "text", path))
        self._log(f"Salida: {path}")

    def pick_wm(self):
        if PLYER_OK:
            filechooser.open_file(
                on_selection=self._on_wm_selected,
                filters=["*.png", "*.jpg", "*.jpeg"],
                multiple=False,
            )
        else:
            self._show_dialog("Error", "plyer no disponible.")

    def _on_wm_selected(self, selection):
        if not selection:
            return
        path = selection[0]
        Clock.schedule_once(lambda dt: setattr(self.root.ids.wm_field, "text", path))
        self._log(f"Marca de agua: {path}")

    # ── Vista previa ─────────────────────────────────────────────────────────
    def _generate_preview(self, video_path: str):
        try:
            duration     = self._probe_duration(Path(video_path))
            preview_time = min(3.0, max(0.2, duration / 3))

            fd, temp_path = tempfile.mkstemp(prefix="clipforge_preview_", suffix=".jpg")
            os.close(fd)

            cmd = [
                str(self.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{preview_time:.2f}", "-i", video_path,
                "-frames:v", "1", temp_path,
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            Clock.schedule_once(lambda dt: self._show_preview(temp_path))

        except Exception as exc:
            Clock.schedule_once(lambda dt: self._update_status(f"Sin vista previa: {exc}"))

    def _show_preview(self, image_path: str):
        box   = self.root.ids.preview_box
        label = self.root.ids.preview_label

        # Eliminar imagen anterior si existe
        if self._preview_img_widget:
            box.remove_widget(self._preview_img_widget)
            self._preview_img_widget = None

        label.text = ""
        img = KivyImage(source=image_path, allow_stretch=True, keep_ratio=True)
        box.add_widget(img)
        self._preview_img_widget = img
        self._update_status("Vista previa lista")

    # ── Actualizaciones thread-safe de UI ────────────────────────────────────
    def _update_status(self, msg: str):
        Clock.schedule_once(lambda dt: setattr(self.root.ids.status_label, "text", msg))

    def _update_progress(self, pct: int):
        def _set(dt):
            self.root.ids.progress_bar.value  = pct
            self.root.ids.progress_label.text = f"{pct}%"
        Clock.schedule_once(_set)

    def _log(self, msg: str):
        def _append(dt):
            lbl = self.root.ids.log_label
            lbl.text += f"{msg}\n"
        Clock.schedule_once(_append)

    def _set_running(self, running: bool):
        def _set(dt):
            self.root.ids.generate_btn.disabled = running
            self.root.ids.cancel_btn.disabled   = not running
        Clock.schedule_once(_set)

    # ── Diálogos ─────────────────────────────────────────────────────────────
    def _show_dialog(self, title: str, text: str, on_ok=None):
        def _open(dt):
            btn = MDFlatButton(text="OK")
            dlg = MDDialog(title=title, text=text, buttons=[btn])
            btn.bind(on_release=lambda x: dlg.dismiss())
            if on_ok:
                btn.bind(on_release=lambda x: on_ok())
            dlg.open()
        Clock.schedule_once(_open)

    # ── Validación ───────────────────────────────────────────────────────────
    def _safe_int(self, value: str, name: str) -> int:
        try:
            n = int(value.strip())
        except ValueError:
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

        video_path = ids.video_field.text.strip()
        out_path   = ids.out_field.text.strip()
        wm_raw     = ids.wm_field.text.strip()

        if not video_path:
            raise ValueError("Selecciona un video.")
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError("El video seleccionado no existe.")

        if not out_path:
            raise ValueError("Selecciona una carpeta de salida.")
        out_dir = Path(out_path)
        if not out_dir.exists():
            raise FileNotFoundError("La carpeta de salida no existe.")

        wm_path = Path(wm_raw) if wm_raw else None
        if wm_path and not wm_path.exists():
            raise FileNotFoundError("La marca de agua no existe.")

        if not self.ffmpeg.exists():
            raise FileNotFoundError(
                f"ffmpeg no encontrado.\nColoca el binario en: {self.base_dir}\n"
                "Para Android descarga un ffmpeg estático ARM64."
            )
        if not self.ffprobe.exists():
            raise FileNotFoundError(f"ffprobe no encontrado en: {self.base_dir}")

        start_sec = self._time_to_sec(ids.ini_m.text, ids.ini_s.text, "Inicio")
        end_sec   = self._time_to_sec(ids.fin_m.text, ids.fin_s.text, "Fin")

        clip_dur   = int(ids.dur_slider.value)
        total_dur  = self._probe_duration(video_path)

        if start_sec >= total_dur:
            raise ValueError("El tiempo de inicio supera la duración del video.")
        if end_sec == 0 or end_sec > total_dur:
            end_sec = int(math.ceil(total_dur))
        if end_sec <= start_sec:
            raise ValueError("El tiempo final debe ser mayor que el inicial.")

        clips_total = math.ceil((end_sec - start_sec) / clip_dur)
        if clips_total <= 0:
            raise ValueError("No hay clips válidos con ese rango.")

        upload_drive = ids.drive_check.active
        if upload_drive and DRIVE_ERR is not None:
            raise RuntimeError("Faltan dependencias de Google Drive.")

        return {
            "video":           video_path,
            "out_dir":         out_dir,
            "watermark":       wm_path,
            "text_prefix":     ids.prefix_field.text.strip() or "Parte",
            "start_sec":       start_sec,
            "end_sec":         end_sec,
            "clip_duration":   clip_dur,
            "clips_total":     clips_total,
            "quality":         self._quality,
            "upload_drive":    upload_drive,
            "drive_folder_id": ids.drive_id_field.text.strip() or None,
            "wm_size":         int(ids.wm_size_slider.value),
            "wm_opacity":      float(ids.wm_opacity_slider.value),
            "wm_position":     self._wm_position,
            "open_folder":     ids.open_folder_check.active,
        }

    # ── FFmpeg (lógica sin cambios respecto al original) ─────────────────────
    def _probe_duration(self, video_path: Path) -> float:
        cmd = [
            str(self.ffprobe), "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nokey=1:noprint_wrappers=1",
            str(video_path),
        ]
        return float(subprocess.check_output(cmd, text=True).strip())

    def _build_ffmpeg_cmd(self, settings, clip_index, clip_start, clip_duration, output_file) -> List[str]:
        quality = QUALITY_PRESETS[settings["quality"]]
        fc      = self._build_filter_complex(settings, clip_index)

        cmd = [
            str(self.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{clip_start:.3f}",
            "-i", str(settings["video"]),
        ]
        if settings["watermark"]:
            cmd += ["-i", str(settings["watermark"])]

        cmd += [
            "-t",            f"{clip_duration:.3f}",
            "-filter_complex", fc,
            "-map",          "[v]",
            "-map",          "0:a?",
            "-c:v",          "libx264",
            "-preset",       quality["preset"],
            "-crf",          str(quality["crf"]),
            "-profile:v",    "high",
            "-pix_fmt",      "yuv420p",
            "-movflags",     "+faststart",
            "-c:a",          "aac",
            "-b:a",          "192k",
            str(output_file),
        ]
        return cmd

    def _build_filter_complex(self, settings, clip_index) -> str:
        clip_text  = self._escape_drawtext(f"{settings['text_prefix']} {clip_index}")
        font_part  = self._get_font_part()

        drawtext = (
            f"drawtext={font_part}text='{clip_text}':"
            "fontcolor=white:fontsize=34:"
            "borderw=2:bordercolor=black@0.65:"
            "x=(w-text_w)/2:y=24:"
            "alpha='if(lt(t,1),t,1)'"
        )

        chains, base_label = [], "0:v"

        if settings["watermark"]:
            opacity  = max(0.10, min(1.00, settings["wm_opacity"]))
            position = WM_POSITIONS[settings["wm_position"]]
            chains.append(
                f"[1:v]scale={settings['wm_size']}:-1,format=rgba,"
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
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/system/fonts/Roboto-Regular.ttf"),   # Android
            Path("/system/fonts/DroidSans.ttf"),         # Android antiguo
        ]
        for path in candidates:
            if path.exists():
                return f"fontfile='{self._escape_path(str(path))}':"
        return ""

    def _escape_drawtext(self, text: str) -> str:
        return (text.replace("\\", r"\\").replace(":", r"\:")
                    .replace("'", r"\'").replace("%", r"\%")
                    .replace("[", r"\[").replace("]", r"\]")
                    .replace(",", r"\,").replace(";", r"\;"))

    def _escape_path(self, path: str) -> str:
        return path.replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'")

    def _run_ffmpeg(self, cmd: List[str]):
        with self.process_lock:
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
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
            detail = (stderr.strip() or "sin detalle")[-1200:]
            raise RuntimeError(f"FFmpeg error:\n{detail}")

    # ── Generación ───────────────────────────────────────────────────────────
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

        self.root.ids.progress_bar.value  = 0
        self.root.ids.progress_label.text = "0%"
        self.root.ids.log_label.text      = ""

        self.cancel_event.clear()
        self._set_running(True)
        self._update_status("Preparando proceso...")
        self._log("=" * 50)
        self._log("Inicio de generación")
        self._log(f"Video: {settings['video']}")
        self._log(f"Clips: {settings['clips_total']}")

        self.worker_thread = threading.Thread(
            target=self._worker, args=(settings,), daemon=True
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
        created = uploaded = 0
        digits  = max(3, len(str(settings["clips_total"])))

        try:
            drive = None
            if settings["upload_drive"]:
                self._update_status("Conectando con Drive...")
                self._log("Autenticando con Google Drive...")
                drive = self.drive_uploader
                drive.auth()
                self._log("Drive conectado.")

            for index in range(settings["clips_total"]):
                if self.cancel_event.is_set():
                    raise UserCancelled("Cancelado por el usuario.")

                start_t  = settings["start_sec"] + index * settings["clip_duration"]
                actual_d = min(settings["clip_duration"], settings["end_sec"] - start_t)
                if actual_d <= 0:
                    break

                out_name = f"{settings['video'].stem}_clip_{index + 1:0{digits}d}.mp4"
                out_file = settings["out_dir"] / out_name

                self._update_status(f"Clip {index + 1}/{settings['clips_total']}...")
                self._log(f"Creando {out_name} ({actual_d:.1f}s)")

                cmd = self._build_ffmpeg_cmd(settings, index + 1, start_t, actual_d, out_file)
                self._run_ffmpeg(cmd)
                created += 1

                if settings["upload_drive"] and drive:
                    if self.cancel_event.is_set():
                        raise UserCancelled("Cancelado.")
                    self._update_status(f"Subiendo clip {index + 1}...")
                    info = drive.upload_file(out_file, settings["drive_folder_id"])
                    uploaded += 1
                    self._log(f"Drive: {info.get('name')} | {info.get('webViewLink', '')}")

                self._update_progress(int(((index + 1) / settings["clips_total"]) * 100))

            msg = f"Listo: {created} clip(s) creados"
            if settings["upload_drive"]:
                msg += f", {uploaded} subido(s) a Drive"
            self._update_progress(100)
            self._update_status(msg)
            self._log(msg)
            self._show_dialog("Proceso finalizado", msg)

            if settings["open_folder"]:
                self._open_folder(settings["out_dir"])

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

    # ── Abrir carpeta ────────────────────────────────────────────────────────
    def _open_folder(self, path: Path):
        try:
            if sys.platform == "android":
                pass  # No hay apertura directa de carpeta en Android
            elif os.name == "nt":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            self._log(f"No se pudo abrir la carpeta: {exc}")


if __name__ == "__main__":
    ClipForgeApp().run()
