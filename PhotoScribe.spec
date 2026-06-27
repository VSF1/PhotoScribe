# -*- mode: python ; coding: utf-8 -*-
# PhotoScribe macOS App Bundle Spec
# Run: pyinstaller PhotoScribe.spec --noconfirm

from PyInstaller.utils.hooks import collect_all, collect_data_files

# rawpy needs full collection (native libraw extension + data)
rawpy_datas, rawpy_binaries, rawpy_hiddenimports = collect_all('rawpy')

# pillow_heif bundles a native libheif — collect its binaries/data so
# HEIC/HEIF (iPhone photos) work in the frozen app
heif_datas, heif_binaries, heif_hiddenimports = collect_all('pillow_heif')

# Platform plugin data for PySide6 — we only need the macOS cocoa plugin
# and the standard image format plugins; not the full PySide6 data dump.
pyside6_datas = collect_data_files('PySide6', includes=[
    'Qt/plugins/platforms/*',
    'Qt/plugins/imageformats/*',
    'Qt/plugins/styles/*',
])

a = Analysis(
    ['photoscribe.py'],
    pathex=[],
    binaries=rawpy_binaries + heif_binaries,
    datas=pyside6_datas + rawpy_datas + heif_datas + [
        ('logo.png', '.'),
    ],
    hiddenimports=(
        rawpy_hiddenimports
        + heif_hiddenimports
        + [
            # PySide6 modules we actually use
            'PySide6.QtCore',
            'PySide6.QtGui',
            'PySide6.QtWidgets',
            # Pillow formats
            'PIL.Image',
            'PIL.JpegImagePlugin',
            'PIL.TiffImagePlugin',
            'PIL.PngImagePlugin',
            'PIL.WebPImagePlugin',
            # HEIC/HEIF support
            'pillow_heif',
        ]
    ),
    hookspath=[],
    hooksconfig={
        'PySide6': {
            # Only include the Qt modules we actually use.
            # This prevents the hook from dragging in WebEngine, Qml, Quick, etc.
            'include_modules': [
                'QtCore',
                'QtGui',
                'QtWidgets',
                'QtOpenGL',    # needed by QtWidgets on macOS
                'QtPrintSupport',
            ],
        },
    },
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        # Unused PySide6 / Qt modules
        'PySide6.Qt3DAnimation',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DExtras',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic',
        'PySide6.Qt3DRender',
        'PySide6.QtCharts',
        'PySide6.QtDataVisualization',
        'PySide6.QtDesigner',
        'PySide6.QtGraphs',
        'PySide6.QtHelp',
        'PySide6.QtLocation',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtNetwork',
        'PySide6.QtNetworkAuth',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        'PySide6.QtPositioning',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtQuick3D',
        'PySide6.QtQuickControls2',
        'PySide6.QtQuickWidgets',
        'PySide6.QtRemoteObjects',
        'PySide6.QtSensors',
        'PySide6.QtSerialBus',
        'PySide6.QtSerialPort',
        'PySide6.QtShaderTools',
        'PySide6.QtSpatialAudio',
        'PySide6.QtSql',
        'PySide6.QtStateMachine',
        'PySide6.QtSvg',
        'PySide6.QtSvgWidgets',
        'PySide6.QtTest',
        'PySide6.QtTextToSpeech',
        'PySide6.QtUiTools',
        'PySide6.QtVirtualKeyboard',
        'PySide6.QtWebChannel',
        'PySide6.QtWebEngine',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineQuick',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebSockets',
        'PySide6.QtWebView',
        'PySide6.QtXml',
        'PySide6.QtXmlPatterns',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PhotoScribe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,  # signing handled by build_app.sh after collect
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PhotoScribe',
)

app = BUNDLE(
    coll,
    name='PhotoScribe.app',
    icon='PhotoScribe.icns',
    bundle_identifier='com.photoscribe.app',
    version='1.3.2',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'NSHighResolutionCapable': True,
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Image',
                'CFBundleTypeRole': 'Viewer',
                'LSItemContentTypes': [
                    'public.jpeg',
                    'public.tiff',
                    'public.png',
                    'org.webmproject.webp',
                    'com.adobe.raw-image',
                    'com.canon.cr2-raw-image',
                    'com.canon.cr3-raw-image',
                    'com.nikon.nef-raw-image',
                    'com.sony.arw-raw-image',
                    'public.heic',
                    'public.heif',
                ],
            }
        ],
        'LSMinimumSystemVersion': '12.0',
    },
)
