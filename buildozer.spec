[app]

# Prompt Architect — Android Build Configuration
# Build with: buildozer android debug
# Requires: pip install buildozer

title = Prompt Architect
package.name = promptarchitect
package.domain = com.promptarchitect
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 4.0

# Main entry point
entrypoint = prompt_architect_android.py

# Requirements (Python packages to include in APK)
requirements = python3,kivy,plyer

# Android settings
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.arch = arm64-v8a

# App appearance
orientation = portrait
fullscreen = 0

# Icon (create a 512x512 icon.png in this directory)
# icon.filename = icon.png

# Presplash (loading screen)
# presplash.filename = presplash.png

# Build settings
android.accept_sdk_license = True
log_level = 2

[buildozer]
log_level = 2
warn_on_root = 1
