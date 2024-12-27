#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print error messages
error() {
    echo -e "${RED}Error: $1${NC}"
}

# Function to print status messages
status() {
    echo -e "${YELLOW}$1${NC}"
}

# Function to print success messages
success() {
    echo -e "${GREEN}$1${NC}"
}

# Check Python version
status "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
success "Found Python $PYTHON_VERSION"

# Create and activate virtual environment
status "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate || {
    error "Failed to activate virtual environment"
    exit 1
}

# Install required packages with verbose output
status "Installing required packages..."
pip3 install --verbose PyQt6 PyMuPDF Pillow requests pyobjc-framework-Cocoa py2app || {
    error "Failed to install required packages"
    exit 1
}

# Clean previous builds
status "Cleaning previous builds..."
rm -rf build dist *.egg-info

# Create setup.py if it doesn't exist
cat > setup.py << EOL
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
EOL

# First try to build in alias mode for testing
status "Building application in alias mode for testing..."
python3 setup.py py2app -A || {
    error "Alias mode build failed"
    exit 1
}

# If alias mode succeeds, build the full application
status "Building final application..."
rm -rf build dist
python3 setup.py py2app || {
    error "Final build failed"
    cat build/bdist.macosx-*/warn*.txt
    exit 1
}

# Check if build was successful
if [ -d "dist/PDF Translator.app" ]; then
    success "Build successful!"
    success "Application is located at: ${PWD}/dist/PDF Translator.app"
    
    # Optional: Copy to Applications folder
    read -p "Do you want to install the application to /Applications? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        status "Copying to Applications folder..."
        cp -r "dist/PDF Translator.app" /Applications/
        success "Installation complete!"
    fi
else
    error "Build failed!"
    exit 1
fi

# Cleanup
status "Cleaning up..."
deactivate
rm -rf build *.egg-info

success "Build process completed!"