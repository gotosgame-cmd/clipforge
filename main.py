"""
ClipForge Studio — Android
Reescritura completa para máxima compatibilidad
"""
import math, os, shutil, subprocess, sys, tempfile, threading, time
from pathlib import Path
from typing  import List, Optional

# ── Config Kivy ──────────────────────────────────────────────────────────────
from kivy.config import Config
Config.set("graphics", "width",  "420")
Config.set("graphics", "height", "860")
Config.set("input",    "mouse",  "mouse,multitouch_on_demand")
Config.set("kivy",     "exit_on_escape", "0")

from kivy.app            import App
from kivy.clock          import Clock
from kivy.metrics        import dp, sp
from kivy.uix.boxlayout  import BoxLayout
from kivy.uix.button     import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label      import Label
from kivy.uix.popup      import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider     import Slider
from kivy.uix.switch     import Switch
from kivy.uix.textinput  import TextInput
from kivy.uix.widget     import Widget
from kivy.graphics       import Color, Rectangle

# Google Drive (opcional)
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials       import Credentials
    from google_auth_oauthlib.flow       import InstalledAppFlow
    from googleapiclient.discovery       import build as gdrive_build
    from googleapiclient.http            import MediaFileUpload
    DRIVE_ERR = None
except Exception as e:
    Request = Credentials = InstalledAppFlow = gdrive_build = MediaFileUpload = None
    DRIVE_ERR = e

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

C_BG   = (0.051, 0.067, 0.090, 1)
C_CARD = (0.080, 0.110, 0.160, 1)
C_FIELD= (0.122, 0.161, 0.216, 1)
C_TEXT = (0.95,  0.97,  1.00,  1)
C_MUTED= (0.58,  0.63,  0.72,  1)
C_GREEN= (0.13,  0.77,  0.37,  1)
C_BLUE = (0.14,  0.39,  0.92,  1)
C_RED  = (0.94,  0.27,  0.27,  1)
C_DARK = (0.05,  0.07,  0.10,  1)


class UserCancelled(Exception):
    pass


class Card(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(*C_CARD)
            self.rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._u, size=self._u)

    def _u(self, *a):
        self.rect.pos  = self.pos
        self.rect.size = self.size


def lbl(text, color=C_TEXT, size=14, bold=False, height=dp(28)):
    l = Label(text=text, color=color, font_size=sp(size), bold=bold,
              size_hint_y=None, height=height,
              halign="left", valign="middle")
    l.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
    return l


def field(hint="", text=""):
    return TextInput(
        hint_text=hint, text=text, multiline=False,
        background_color=C_FIELD, foreground_color=C_TEXT,
        cursor_color=C_TEXT, hint_text_color=list(C_MUTED),
        font_size=sp(13), size_hint_y=None, height=dp(44),
        padding=[dp(10), dp(12)],
    )


def btn(text, color=C_BLUE, height=dp(46)):
    return Button(text=text, background_color=color, color=C_TEXT,
                  size_hint_y=None, height=height, font_size=sp(13),
                  bold=True, background_normal="")


def sep():
    w = Widget(size_hint_y=None, height=dp(1))
    with w.canvas:
        Color(0.2, 0.25, 0.35, 1)
        r = Rectangle(pos=w.pos, size=w.size)
    w.bind(pos=lambda i, v: setattr(r, "pos", v),
           size=lambda i, v: setattr(r, "size", v))
    return w


class TouchScroll(ScrollView):
    def on_touch_down(self, touch):
        touch.ud["_sy"] = touch.y
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if "_sy" in touch.ud:
            dy = touch.y - touch.ud["_sy"]
            if abs(dy) > 8:
                self.scroll_y = max(0.0, min(1.0,
                    self.scroll_y + dy / max(self.height, 1) * 2.5))
                touch.ud["_sy"] = touch.y
                return True
        return super().on_touch_move(touch)


class DriveUploader:
    def __init__(self, creds, token):
        self.creds   = creds
        self.token   = token
        self.service = None

    def auth(self):
        if DRIVE_ERR:
            raise RuntimeError("Drive no disponible.") from DRIVE_ERR
        c = None
        if self.token.exists():
            c = Credentials.from_authorized_user_file(str(self.token), SCOPES)
        if c and c.expired and c.refresh_token:
            c.refresh(Request())
        elif not c or not c.valid:
            c = InstalledAppFlow.from_client_secrets_file(
                str(self.creds), SCOPES).run_local_server(port=0)
        self.token.parent.mkdir(parents=True, exist_ok=True)
        self.token.write_text(c.to_json())
        self.service = gdrive_build("drive", "v3", credentials=c)

    def upload(self, path, folder_id=None):
        svc = self.service
        meta = {"name": path.name}
        if folder_id:
            meta["parents"] = [folder_id]
        media = MediaFileUpload(str(path), mimetype="video/mp4", resumable=False)
        return svc.files().create(body=meta, media_body=media,
                                  fields="id,name,webViewLink").execute()


class ClipForgeApp(App):

    def build(self):
        self.base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) \
                        else Path(__file__).parent
        self.ffmpeg   = self._bin("ffmpeg")
        self.ffprobe  = self._bin("ffprobe")

        if sys.platform == "android":
            self.out_dir = Path("/storage/emulated/0/Movies/ClipForge")
        elif os.name == "nt":
            self.out_dir = Path(os.getenv("APPDATA", ".")) / "ClipForge"
        else:
            self.out_dir = Path.home() / "ClipForge"
        self.out_dir.mkdir(parents=True, exist_ok=True)

        app_data = self.out_dir / ".data"
        app_data.mkdir(exist_ok=True)
        self.drive = DriveUploader(
            self.base_dir / "credentials.json",
            app_data / "token.json",
        )

        self.cancel_event    = threading.Event()
        self.worker_thread   = None
        self.current_process = None
        self.proc_lock       = threading.Lock()
        self.video_path      = ""
        self.wm_path         = ""
        self.quality         = "Alta"
        self.wm_pos          = "Arriba derecha"

        return self._ui()

    def on_start(self):
        if sys.platform == "android":
            Clock.schedule_once(self._permisos, 1.0)

    def _permisos(self, dt):
        try:
            from android.permissions import request_permissions, Permission  # type: ignore
            perms = [Permission.WRITE_EXTERNAL_STORAGE]
            try:
                perms += [Permission.READ_MEDIA_VIDEO, Permission.READ_MEDIA_IMAGES]
            except AttributeError:
                perms.append(Permission.READ_EXTERNAL_STORAGE)
            request_permissions(perms)
        except Exception as e:
            self._log(f"Permisos: {e}")

    def _bin(self, name):
        suffix = ".exe" if os.name == "nt" else ""
        local  = self.base_dir / (name + suffix)
        if local.exists():
            return local
        found = shutil.which(name + suffix)
        return Path(found) if found else local

    # ── UI ───────────────────────────────────────────────────────────────────
    def _ui(self):
        root = BoxLayout()
        with root.canvas.before:
            Color(*C_BG)
            r = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda i, v: setattr(r, "pos", v),
                  size=lambda i, v: setattr(r, "size", v))

        scroll = TouchScroll(do_scroll_x=False, bar_width=dp(4),
                             bar_color=(*C_MUTED[:3], 0.6))
        main   = BoxLayout(orientation="vertical", size_hint_y=None,
                           spacing=dp(10), padding=[dp(10), dp(12)])
        main.bind(minimum_height=main.setter("height"))
        scroll.add_widget(main)
        root.add_widget(scroll)

        main.add_widget(lbl("✂  ClipForge Studio", C_GREEN, 20, bold=True, height=dp(44)))
        main.add_widget(lbl("Corta y exporta tus videos", C_MUTED, 12, height=dp(20)))
        main.add_widget(Widget(size_hint_y=None, height=dp(4)))

        main.add_widget(self._s_video())
        main.add_widget(self._s_clips())
        main.add_widget(self._s_wm())
        main.add_widget(self._s_salida())
        main.add_widget(self._s_drive())
        main.add_widget(self._s_proceso())
        main.add_widget(self._s_log())
        main.add_widget(Widget(size_hint_y=None, height=dp(24)))
        return root

    def _card(self, title):
        c = Card(orientation="vertical", spacing=dp(8),
                 padding=[dp(10), dp(10)], size_hint_y=None)
        c.bind(minimum_height=c.setter("height"))
        c.add_widget(lbl(title, C_GREEN, 13, bold=True, height=dp(28)))
        c.add_widget(sep())
        return c

    def _menu(self, title, ops, cb):
        content = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        p = Popup(title=title, content=content, size_hint=(0.82, None),
                  height=dp(70 + 52 * len(ops)),
                  background_color=C_CARD, title_color=C_TEXT)
        for op in ops:
            b = btn(op, C_FIELD, height=dp(46))
            def sel(inst, o=op): p.dismiss(); cb(o)
            b.bind(on_release=sel)
            content.add_widget(b)
        p.open()

    # ── Secciones ────────────────────────────────────────────────────────────
    def _s_video(self):
        c = self._card("📹  Video")
        self.video_lbl = lbl("Sin video seleccionado", C_MUTED, 12, height=dp(26))
        c.add_widget(self.video_lbl)
        b = btn("Seleccionar video", C_BLUE)
        b.bind(on_release=lambda *a: self._selector("video", self._set_video))
        c.add_widget(b)
        return c

    def _s_clips(self):
        c = self._card("✂  Clips")

        r1 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        r1.add_widget(lbl("Prefijo:", C_MUTED, 12, height=dp(44)))
        self.prefix = field("Parte", "Parte")
        r1.add_widget(self.prefix)
        c.add_widget(r1)

        r2 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        r2.add_widget(lbl("Calidad:", C_MUTED, 12, height=dp(44)))
        self.q_btn = btn(self.quality, C_FIELD, height=dp(44))
        self.q_btn.bind(on_release=lambda *a: self._menu(
            "Calidad", list(QUALITY_PRESETS), lambda v: (
                setattr(self, "quality", v), setattr(self.q_btn, "text", v))))
        r2.add_widget(self.q_btn)
        c.add_widget(r2)

        dr = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(8))
        dr.add_widget(lbl("Duración:", C_MUTED, 12, height=dp(32)))
        self.dur_lbl = lbl("10 s", C_TEXT, 12, height=dp(32))
        dr.add_widget(self.dur_lbl)
        c.add_widget(dr)
        self.dur_sl = Slider(min=2, max=180, value=10, step=1,
                             size_hint_y=None, height=dp(38))
        self.dur_sl.bind(value=lambda i, v: setattr(self.dur_lbl, "text", f"{int(v)} s"))
        c.add_widget(self.dur_sl)

        c.add_widget(lbl("Inicio (min : seg):", C_MUTED, 11, height=dp(22)))
        tr = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.ini_m = field("0", "0"); self.ini_m.size_hint_x = 0.45
        self.ini_s = field("0", "0"); self.ini_s.size_hint_x = 0.45
        tr.add_widget(self.ini_m)
        tr.add_widget(lbl(":", C_TEXT, 16, height=dp(44)))
        tr.add_widget(self.ini_s)
        c.add_widget(tr)

        c.add_widget(lbl("Fin (min : seg)  — 0:0 = hasta el final:", C_MUTED, 11, height=dp(22)))
        tr2 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.fin_m = field("0", "0"); self.fin_m.size_hint_x = 0.45
        self.fin_s = field("0", "0"); self.fin_s.size_hint_x = 0.45
        tr2.add_widget(self.fin_m)
        tr2.add_widget(lbl(":", C_TEXT, 16, height=dp(44)))
        tr2.add_widget(self.fin_s)
        c.add_widget(tr2)
        return c

    def _s_wm(self):
        c = self._card("💧  Marca de agua (opcional)")
        self.wm_lbl = lbl("Sin marca de agua", C_MUTED, 12, height=dp(26))
        c.add_widget(self.wm_lbl)
        b = btn("Seleccionar imagen", C_BLUE)
        b.bind(on_release=lambda *a: self._selector("image", self._set_wm))
        c.add_widget(b)

        r = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        r.add_widget(lbl("Posición:", C_MUTED, 12, height=dp(44)))
        self.wm_pos_btn = btn(self.wm_pos, C_FIELD, height=dp(44))
        self.wm_pos_btn.bind(on_release=lambda *a: self._menu(
            "Posición", list(WM_POSITIONS), lambda v: (
                setattr(self, "wm_pos", v), setattr(self.wm_pos_btn, "text", v))))
        r.add_widget(self.wm_pos_btn)
        c.add_widget(r)

        for label, attr_lbl, attr_sl, mn, mx, val, step, fmt in [
            ("Tamaño", "wm_sz_lbl", "wm_sz_sl", 40, 500, 120, 10, lambda v: f"{int(v)} px"),
            ("Opacidad", "wm_op_lbl", "wm_op_sl", 0.1, 1.0, 0.8, 0.05, lambda v: f"{int(round(v*100))}%"),
        ]:
            row = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(8))
            row.add_widget(lbl(f"{label}:", C_MUTED, 12, height=dp(32)))
            ll = lbl(fmt(val), C_TEXT, 12, height=dp(32))
            setattr(self, attr_lbl, ll)
            row.add_widget(ll)
            c.add_widget(row)
            sl = Slider(min=mn, max=mx, value=val, step=step,
                        size_hint_y=None, height=dp(36))
            lbl_ref = ll; fmt_ref = fmt
            sl.bind(value=lambda i, v, l=lbl_ref, f=fmt_ref: setattr(l, "text", f(v)))
            setattr(self, attr_sl, sl)
            c.add_widget(sl)
        return c

    def _s_salida(self):
        c = self._card("📁  Salida")
        self.out_input = field("Ruta de salida", str(self.out_dir))
        c.add_widget(self.out_input)
        c.add_widget(lbl(f"Predeterminado: {self.out_dir}", C_MUTED, 10, height=dp(20)))
        return c

    def _s_drive(self):
        c = self._card("☁  Google Drive (opcional)")
        r = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        r.add_widget(lbl("Subir a Drive:", C_TEXT, 12, height=dp(44)))
        self.drive_sw = Switch(active=False, size_hint=(None, None), size=(dp(70), dp(44)))
        r.add_widget(self.drive_sw)
        c.add_widget(r)
        self.drive_id = field("Folder ID (opcional)")
        c.add_widget(self.drive_id)
        return c

    def _s_proceso(self):
        c = self._card("⚙  Proceso")
        self.status_lbl = lbl("Listo", C_MUTED, 12, height=dp(26))
        c.add_widget(self.status_lbl)
        self.progress = ProgressBar(max=100, value=0, size_hint_y=None, height=dp(14))
        c.add_widget(self.progress)
        r = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8))
        self.gen_btn = btn("▶  Generar clips", C_GREEN)
        self.gen_btn.bind(on_release=lambda *a: self.start_generation())
        self.can_btn = btn("✕  Cancelar", C_RED)
        self.can_btn.bind(on_release=lambda *a: self.cancel_generation())
        self.can_btn.disabled = True
        r.add_widget(self.gen_btn)
        r.add_widget(self.can_btn)
        c.add_widget(r)
        return c

    def _s_log(self):
        c = self._card("📋  Registro")
        self.log_txt = TextInput(
            text="", readonly=True, multiline=True,
            background_color=C_DARK, foreground_color=C_TEXT,
            font_size=sp(11), size_hint_y=None, height=dp(160),
        )
        c.add_widget(self.log_txt)
        return c

    # ── Selector de archivos con MediaStore ──────────────────────────────────
    def _selector(self, mime, callback):
        is_video = mime == "video"
        exts     = (".mp4", ".mov", ".mkv", ".avi", ".m4v") if is_video else (".png", ".jpg", ".jpeg")
        title    = "Seleccionar video" if is_video else "Seleccionar imagen"

        layout  = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        st_lbl  = lbl("Buscando...", C_MUTED, 12, height=dp(28))
        scroll  = ScrollView(size_hint_y=1)
        grid    = GridLayout(cols=1, spacing=dp(3), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        c_btn   = btn("Cancelar", C_RED, height=dp(48))

        scroll.add_widget(grid)
        layout.add_widget(st_lbl)
        layout.add_widget(scroll)
        layout.add_widget(c_btn)

        popup = Popup(title=title, content=layout, size_hint=(0.97, 0.93),
                      background_color=C_DARK, title_color=C_TEXT)
        c_btn.bind(on_release=lambda *a: popup.dismiss())
        popup.open()

        def buscar():
            archivos = []

            if sys.platform == "android":
                # MediaStore — no necesita permisos de filesystem
                try:
                    from jnius import autoclass  # type: ignore
                    PythonActivity = autoclass("org.kivy.android.PythonActivity")
                    ctx = PythonActivity.mActivity
                    if is_video:
                        MS = autoclass("android.provider.MediaStore$Video$Media")
                    else:
                        MS = autoclass("android.provider.MediaStore$Images$Media")

                    cursor = ctx.getContentResolver().query(
                        MS.EXTERNAL_CONTENT_URI,
                        ["_data", "_display_name", "date_modified"],
                        None, None, "date_modified DESC"
                    )
                    if cursor:
                        idx_data = cursor.getColumnIndex("_data")
                        while cursor.moveToNext() and len(archivos) < 500:
                            try:
                                p = cursor.getString(idx_data)
                                if p and os.path.exists(p):
                                    archivos.append(p)
                            except Exception:
                                continue
                        cursor.close()
                except Exception as e:
                    self._log(f"MediaStore: {e}")

            # Fallback para desktop o si MediaStore falló
            if not archivos:
                roots = ["/storage/emulated/0/DCIM",
                         "/storage/emulated/0/Movies",
                         "/storage/emulated/0/Download",
                         "/storage/emulated/0"] if sys.platform == "android" \
                        else [str(Path.home() / "Videos"), str(Path.home())]
                for root in roots:
                    try:
                        for dp2, _, fs in os.walk(root):
                            for f in fs:
                                if f.lower().endswith(exts):
                                    archivos.append(os.path.join(dp2, f))
                            if len(archivos) >= 500:
                                break
                    except Exception:
                        continue

            def mostrar(dt):
                grid.clear_widgets()
                if archivos:
                    st_lbl.text = f"{len(archivos)} archivo(s) encontrado(s)"
                    for path in archivos:
                        nombre = os.path.basename(path)
                        b = Button(
                            text=nombre, size_hint_y=None, height=dp(50),
                            background_color=C_CARD, color=C_TEXT,
                            halign="left", font_size=sp(12), background_normal="",
                        )
                        b.bind(size=lambda i, v: setattr(i, "text_size", (v[0]-dp(16), None)))
                        def on_tap(inst, p=path):
                            popup.dismiss()
                            Clock.schedule_once(lambda dt: callback(p), 0.15)
                        b.bind(on_release=on_tap)
                        grid.add_widget(b)
                else:
                    st_lbl.text = "No se encontraron archivos"
                    grid.add_widget(lbl(
                        "Ve a:\nAjustes → Apps → ClipForge\n→ Permisos → Archivos\n→ Permitir acceso",
                        (1, 0.6, 0.2, 1), 13, height=dp(90)
                    ))

            Clock.schedule_once(mostrar)

        threading.Thread(target=buscar, daemon=True).start()

    def _set_video(self, path):
        self.video_path = path
        self.video_lbl.text  = f"✓  {os.path.basename(path)}"
        self.video_lbl.color = C_GREEN
        self._log(f"Video: {path}")

    def _set_wm(self, path):
        self.wm_path = path
        self.wm_lbl.text  = f"✓  {os.path.basename(path)}"
        self.wm_lbl.color = C_GREEN
        self._log(f"Marca de agua: {path}")

    # ── Helpers UI ───────────────────────────────────────────────────────────
    def _log(self, msg):
        def _d(dt):
            self.log_txt.text += f"{msg}\n"
            self.log_txt.cursor = (0, len(self.log_txt.text))
        Clock.schedule_once(_d)

    def _status(self, msg):
        Clock.schedule_once(lambda dt: setattr(self.status_lbl, "text", msg))

    def _pct(self, v):
        Clock.schedule_once(lambda dt: setattr(self.progress, "value", v))

    def _running(self, v):
        def _d(dt):
            self.gen_btn.disabled = v
            self.can_btn.disabled = not v
        Clock.schedule_once(_d)

    def _alert(self, title, msg):
        content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        content.add_widget(lbl(msg, C_TEXT, 13, height=dp(100)))
        ok = btn("OK", C_GREEN, height=dp(46))
        p  = Popup(title=title, content=content, size_hint=(0.88, None),
                   height=dp(220), background_color=C_CARD, title_color=C_TEXT)
        ok.bind(on_release=lambda *a: p.dismiss())
        content.add_widget(ok)
        Clock.schedule_once(lambda dt: p.open())

    # ── Validación ───────────────────────────────────────────────────────────
    def _int(self, v, name):
        try:
            n = int(str(v).strip())
        except ValueError:
            raise ValueError(f"{name} debe ser entero.")
        if n < 0:
            raise ValueError(f"{name} no puede ser negativo.")
        return n

    def _sec(self, m, s, pref):
        mi = self._int(m, f"{pref} min")
        si = self._int(s, f"{pref} seg")
        if si > 59:
            raise ValueError(f"{pref} seg: máximo 59.")
        return mi * 60 + si

    def _validate(self):
        if not self.video_path or not os.path.exists(self.video_path):
            raise ValueError("Selecciona un video primero.")
        if not self.ffmpeg.exists():
            raise FileNotFoundError(f"ffmpeg no encontrado en: {self.base_dir}")
        out = self.out_input.text.strip()
        if not out:
            raise ValueError("Especifica carpeta de salida.")
        Path(out).mkdir(parents=True, exist_ok=True)

        s   = self._sec(self.ini_m.text, self.ini_s.text, "Inicio")
        e   = self._sec(self.fin_m.text, self.fin_s.text, "Fin")
        dur = int(self.dur_sl.value)
        tot = self._probe_dur(Path(self.video_path))

        if s >= tot:
            raise ValueError("Inicio mayor que duración del video.")
        if e == 0 or e > tot:
            e = int(math.ceil(tot))
        if e <= s:
            raise ValueError("Fin debe ser mayor que inicio.")

        clips = math.ceil((e - s) / dur)
        return {
            "video":    Path(self.video_path),
            "out_dir":  Path(out),
            "wm":       Path(self.wm_path) if self.wm_path else None,
            "prefix":   self.prefix.text.strip() or "Parte",
            "start": s, "end": e, "dur": dur, "clips": clips,
            "quality":  self.quality,
            "upload":   self.drive_sw.active,
            "folder":   self.drive_id.text.strip() or None,
            "wm_size":  int(self.wm_sz_sl.value),
            "wm_op":    float(self.wm_op_sl.value),
            "wm_pos":   self.wm_pos,
        }

    # ── FFmpeg ───────────────────────────────────────────────────────────────
    def _probe_dur(self, path):
        out = subprocess.check_output([
            str(self.ffprobe), "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nokey=1:noprint_wrappers=1", str(path)
        ], text=True)
        return float(out.strip())

    def _run_ff(self, cmd):
        with self.proc_lock:
            self.current_process = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace")
            proc = self.current_process
        while proc.poll() is None:
            if self.cancel_event.is_set():
                proc.terminate()
                try: proc.wait(5)
                except subprocess.TimeoutExpired: proc.kill()
                raise UserCancelled()
            time.sleep(0.15)
        _, err = proc.communicate()
        with self.proc_lock:
            if self.current_process is proc:
                self.current_process = None
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg:\n{(err or '')[-600:]}")

    def _cmd(self, cfg, idx, s, d, out):
        q  = QUALITY_PRESETS[cfg["quality"]]
        fc = self._fc(cfg, idx)
        c  = [str(self.ffmpeg), "-hide_banner", "-loglevel", "error",
              "-y", "-ss", f"{s:.3f}", "-i", str(cfg["video"])]
        if cfg["wm"]:
            c += ["-i", str(cfg["wm"])]
        c += ["-t", f"{d:.3f}", "-filter_complex", fc,
              "-map", "[v]", "-map", "0:a?",
              "-c:v", "libx264", "-preset", q["preset"],
              "-crf", str(q["crf"]), "-profile:v", "high",
              "-pix_fmt", "yuv420p", "-movflags", "+faststart",
              "-c:a", "aac", "-b:a", "192k", str(out)]
        return c

    def _fc(self, cfg, idx):
        def esc(t):
            for a, b in [("\\","\\\\"),(":",r"\:"),("'",r"\'"),
                         ("%",r"\%"),("[",r"\["),("]",r"\]")]:
                t = t.replace(a, b)
            return t
        def font():
            for p in [self.base_dir/"arial.ttf",
                      Path("/system/fonts/Roboto-Regular.ttf"),
                      Path("/system/fonts/DroidSans.ttf"),
                      Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                      Path("C:/Windows/Fonts/arial.ttf")]:
                if p.exists():
                    ep = str(p).replace("\\","\\\\").replace(":",r"\:").replace("'",r"\'")
                    return f"fontfile='{ep}':"
            return ""
        dt = (f"drawtext={font()}text='{esc(cfg['prefix']+' '+str(idx))}':"
              "fontcolor=white:fontsize=34:borderw=2:bordercolor=black@0.65:"
              "x=(w-text_w)/2:y=24:alpha='if(lt(t,1),t,1)'")
        chains, base = [], "0:v"
        if cfg["wm"]:
            op = max(0.1, min(1.0, cfg["wm_op"]))
            chains.append(f"[1:v]scale={cfg['wm_size']}:-1,format=rgba,"
                          f"colorchannelmixer=aa={op:.2f}[wm]")
            chains.append(f"[0:v][wm]overlay={WM_POSITIONS[cfg['wm_pos']]}[base]")
            base = "base"
        chains.append(f"[{base}]{dt}[v]")
        return ";".join(chains)

    # ── Generación ───────────────────────────────────────────────────────────
    def start_generation(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self._alert("En progreso", "Ya hay un proceso activo.")
            return
        try:
            cfg = self._validate()
        except Exception as e:
            self._alert("Validación", str(e))
            return
        self.cancel_event.clear()
        self._pct(0)
        self._running(True)
        self._log("─" * 36)
        self._log(f"Generando {cfg['clips']} clip(s)...")
        self.worker_thread = threading.Thread(
            target=self._worker, args=(cfg,), daemon=True)
        self.worker_thread.start()

    def cancel_generation(self):
        self.cancel_event.set()
        self._status("Cancelando...")
        with self.proc_lock:
            if self.current_process and self.current_process.poll() is None:
                try: self.current_process.terminate()
                except Exception: pass

    def _worker(self, cfg):
        created = uploaded = 0
        digits  = max(3, len(str(cfg["clips"])))
        try:
            drv = None
            if cfg["upload"]:
                self._status("Conectando con Drive...")
                self.drive.auth()
                drv = self.drive

            for i in range(cfg["clips"]):
                if self.cancel_event.is_set():
                    raise UserCancelled()
                s = cfg["start"] + i * cfg["dur"]
                d = min(cfg["dur"], cfg["end"] - s)
                if d <= 0:
                    break
                name = f"{cfg['video'].stem}_clip_{i+1:0{digits}d}.mp4"
                out  = cfg["out_dir"] / name
                self._status(f"Clip {i+1}/{cfg['clips']}")
                self._log(f"→ {name}")
                self._run_ff(self._cmd(cfg, i+1, s, d, out))
                created += 1
                if drv:
                    self._status(f"Subiendo {i+1}...")
                    info = drv.upload(out, cfg["folder"])
                    uploaded += 1
                    self._log(f"Drive: {info.get('name')}")
                self._pct(int((i+1)/cfg["clips"]*100))

            msg = f"✓ {created} clip(s) en:\n{cfg['out_dir']}"
            if cfg["upload"]:
                msg += f"\n☁ {uploaded} subido(s) a Drive"
            self._pct(100)
            self._status(f"✓ {created} clip(s) generados")
            self._log(msg)
            self._alert("Completado", msg)

        except UserCancelled:
            self._status("Cancelado")
            self._log("Cancelado.")
            self._pct(0)
        except Exception as e:
            self._status("Error")
            self._log(f"ERROR: {e}")
            self._alert("Error", str(e))
            self._pct(0)
        finally:
            self._running(False)


if __name__ == "__main__":
    ClipForgeApp().run()
