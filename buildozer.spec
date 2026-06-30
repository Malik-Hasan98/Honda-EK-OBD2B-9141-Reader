[app]

# ============================================
# HONDA OBD2B 9141 READER - BUILD CONFIG
# ============================================

# Application title
title = Honda OBD2 Reader

# Package name
package.name = hondaobdreader

# Package domain
package.domain = com.honda

# Version
version = 1.0.0

# Version code
android.version_code = 1

# Source directory
source.dir = .

# Include these file extensions
source.include_exts = py,png,jpg,kv,atlas,ttf,txt,json

# Python requirements - SIMPLIFIED!
requirements = python3,kivy

# Permissions for WiFi OBD2 connection
android.permissions = INTERNET,ACCESS_WIFI_STATE,ACCESS_NETWORK_STATE

# Landscape orientation for dashboard
orientation = landscape

# Fullscreen mode (no status bar)
fullscreen = 1

# Android SDK versions
android.api = 33
android.minapi = 21

# Hardware features
android.used_features = android.hardware.wifi

# Allow backup
android.allow_backup = True

# Blacklist directories
blacklist_dir = .git,.gradle,.idea,__pycache__,build,dist,venv,env

# ============================================
# BUILDOZER SETTINGS
# ============================================

[buildozer]

# Log level (0=error, 1=info, 2=debug)
log_level = 2

# Warn if running as root
warn_on_root = 1

# Debug build
debug = 1

# Build directory
build.dir = ./build

# Dist directory
dist.dir = ./dist

# Android architecture
android.arch = arm64-v8a

# Build timeout (seconds)
android.timeout = 3600

# Memory for build (MB)
android.memory = 4096

# Java options
android.javac_options = -Xmx4G

# NDK version - STABLE!
android.ndk = 23b

# NDK API level
android.ndk_api = 21

# Gradle plugin version
android.gradle_plugin_version = 7.1.3

# Build tools version
android.build_tools_version = 33.0.0

# Enable multidex
android.enable_multidex = True