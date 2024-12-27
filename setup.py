from setuptools import setup

APP = ['pdf_viewer.py']
DATA_FILES = [
    ('icons', ['icons/app_icon.png']),
]
OPTIONS = {
    'argv_emulation': True,
    'packages': ['PyQt6', 'fitz', 'PIL', 'requests'],
    'includes': ['PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets'],
    'iconfile': 'icons/app_icon.png',
    'plist': {
        'CFBundleName': 'PDF Translator',
        'CFBundleDisplayName': 'PDF Translator',
        'CFBundleIdentifier': 'com.pdftranslator.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
    }
}

setup(
    name='PDF Translator',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
