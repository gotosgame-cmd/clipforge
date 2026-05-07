[app]
# Información de la app
title = ClipForge Studio
package.name = clipforge
package.domain = org.clipforge

# Archivos fuente
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,ttf
source.include_patterns = credentials.json,ffmpeg,ffprobe

# Versión
version = 1.0

# ── Dependencias ──────────────────────────────────────────────────────────────
# IMPORTANTE: kivymd debe coincidir con tu versión de kivy
requirements =
    python3,
    kivy==2.3.0,
    kivymd==1.2.0,
    pillow,
    plyer,
    requests,
    certifi,
    urllib3,
    charset-normalizer,
    idna,
    google-auth,
    google-auth-oauthlib,
    google-auth-httplib2,
    google-api-python-client,
    cachetools,
    pyasn1,
    pyasn1-modules,
    rsa

# Orientación
orientation = portrait
fullscreen = 0

# Icono y splash (opcional — agrega tus propios archivos)
# icon.filename = %(source.dir)s/icon.png
# presplash.filename = %(source.dir)s/splash.png

# ── Android ───────────────────────────────────────────────────────────────────
android.permissions =
    INTERNET,
    READ_MEDIA_VIDEO,
    READ_MEDIA_IMAGES,
    READ_MEDIA_AUDIO,
    WRITE_EXTERNAL_STORAGE,
    MANAGE_EXTERNAL_STORAGE

# API mínima recomendada (Android 8+)
android.minapi = 26
android.targetapi = 33

# NDK y SDK
android.ndk = 25b
android.sdk = 33

# Arquitectura (ARM64 cubre la mayoría de dispositivos modernos)
# Para máxima compatibilidad agrega armeabi-v7a también:
# android.archs = arm64-v8a, armeabi-v7a
android.archs = arm64-v8a

android.allow_backup = True

# Gradle
android.gradle_dependencies =

# Habilitar AndroidX
android.enable_androidx = True

# ── Buildozer ─────────────────────────────────────────────────────────────────
[buildozer]
log_level = 2
warn_on_root = 1
