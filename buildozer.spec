[app]
title = ClipForge Studio
package.name = clipforge
package.domain = org.clipforge

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,ttf
source.include_patterns = credentials.json,ffmpeg,ffprobe

version = 1.0

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

orientation = portrait
fullscreen = 0

android.permissions =
    INTERNET,
    READ_MEDIA_VIDEO,
    READ_MEDIA_IMAGES,
    READ_MEDIA_AUDIO,
    WRITE_EXTERNAL_STORAGE,
    MANAGE_EXTERNAL_STORAGE

android.minapi = 26
android.targetapi = 36
android.ndk = 26b
android.sdk = 36
android.archs = arm64-v8a
android.allow_backup = True
android.wakelock = False
android.extra_manifest_application_arguments = android:configChanges="orientation|keyboardHidden|keyboard|screenSize|locale|layoutDirection|fontScale|screenLayout|density|uiMode" android:windowSoftInputMode="adjustResize"
android.gradle_dependencies =
android.enable_androidx = True

[buildozer]
log_level = 2
warn_on_root = 1
