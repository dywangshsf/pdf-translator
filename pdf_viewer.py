from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import fitz  # PyMuPDF
import sys
import requests  # Ensure requests library is available
import json
import time
from typing import List, Optional
import re
import threading
import os
from PIL import Image, ImageDraw, ImageFont
import openai  # Add this import at the top

class PDFGraphicsView(QGraphicsView):
    """Custom QGraphicsView for handling text selection"""
    textSelected = pyqtSignal(str)  # Signal for selected text

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rubberBand = None  # For visual selection
        self.origin = QPoint()  # Starting point of selection
        self.current_page = None  # Current PDF page
        self.zoom_factor = 1.0  # Zoom level
        self.dpi = 300  # Dots per inch for rendering
        self.main_window = None  # Reference to main window

    def set_main_window(self, main_window):
        """Set reference to main window"""
        self.main_window = main_window

    def mousePressEvent(self, event):
        """Handle mouse press events for selection"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.pos()  # Store the starting point
            if not self.rubberBand:
                self.rubberBand = QRubberBand(QRubberBand.Shape.Rectangle, self)  # Create rubber band for selection
            self.rubberBand.setGeometry(QRect(self.origin, QSize()))  # Set geometry for rubber band
            self.rubberBand.show()  # Show the rubber band
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Update rubber band geometry during mouse movement"""
        if self.rubberBand:
            self.rubberBand.setGeometry(QRect(self.origin, event.pos()).normalized())  # Update selection area
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release events to finalize selection"""
        if event.button() == Qt.MouseButton.LeftButton and self.rubberBand:
            if self.current_page and self.main_window:
                # Convert view coordinates to scene coordinates
                start_pos = self.mapToScene(self.origin)
                end_pos = self.mapToScene(event.pos())
                
                # Convert scene coordinates to PDF coordinates
                dpi_scale = 72.0 / self.dpi
                zoom_scale = 1.0 / self.zoom_factor
                
                rect = fitz.Rect(
                    start_pos.x() * dpi_scale * zoom_scale,
                    start_pos.y() * dpi_scale * zoom_scale,
                    end_pos.x() * dpi_scale * zoom_scale,
                    end_pos.y() * dpi_scale * zoom_scale
                )
                
                # Get text blocks within the selected rectangle
                blocks = self.current_page.get_text("blocks", clip=rect)
                if blocks:
                    # Get current spacing value from main window
                    spacing = self.main_window.spacing_spinbox.value()
                    # Process and join text blocks with current spacing
                    processed_text = self.process_text_blocks(blocks, spacing)
                    if processed_text.strip():
                        self.textSelected.emit(processed_text)  # Emit the selected text
            
            self.rubberBand.hide()  # Hide the rubber band
            self.rubberBand = None  # Reset rubber band
        super().mouseReleaseEvent(event)

    def process_text_blocks(self, blocks, line_spacing_threshold):
        """Process text blocks to properly join lines within paragraphs"""
        if not blocks:
            return ""
        
        print("\n=== Text Block Processing Debug Info ===")
        print(f"Number of blocks: {len(blocks)}")
        print(f"Line spacing threshold: {line_spacing_threshold}")
        
        # Sort blocks by vertical position (top to bottom)
        sorted_blocks = sorted(blocks, key=lambda b: (b[1], b[0]))
        
        print("\nRaw blocks data:")
        for i, block in enumerate(sorted_blocks):
            print(f"\nBlock {i+1}:")
            print(f"Position: x0={block[0]:.2f}, y0={block[1]:.2f}, x1={block[2]:.2f}, y1={block[3]:.2f}")
            print(f"Text: '{block[4]}'")
            print(f"Block height: {block[3] - block[1]:.2f}")
        
        processed_lines = []  # To store processed lines
        current_line = []  # Current line being processed
        last_y = None  # Last y position
        last_height = None  # Last block height
        
        print("\nProcessing decisions:")
        for i, block in enumerate(sorted_blocks):
            text = block[4]  # Extract text from block
            y_pos = block[1]  # Y position of the block
            height = block[3] - block[1]  # Height of the block
            
            print(f"\nAnalyzing block {i+1}:")
            print(f"Text: '{text}'")
            print(f"Y position: {y_pos:.2f}")
            print(f"Height: {height:.2f}")
            
            # Remove hyphenation
            if text.rstrip('-') != text:
                print("Found hyphenation, removing...")
            text = text.rstrip('-')
            
            if last_y is None:
                print("First block - starting new line")
                current_line.append(text)  # Start new line
            else:
                y_diff = abs(y_pos - last_y)  # Calculate distance from last block
                height_ratio = height / last_height if last_height else 1.0  # Calculate height ratio
                
                print(f"Distance from last block: {y_diff:.2f}")
                print(f"Height ratio: {height_ratio:.2f}")
                
                # Check if this might be a title or new paragraph
                is_new_section = (y_diff > line_spacing_threshold * 2.0 or
                                height_ratio > 1.2 or
                                text.strip().endswith(':') or
                                text.isupper())
                
                print("Checks for new section:")
                print(f"- Large spacing (>{line_spacing_threshold * 2.0}): {y_diff > line_spacing_threshold * 2.0}")
                print(f"- Larger height (>1.2): {height_ratio > 1.2}")
                print(f"- Ends with colon: {text.strip().endswith(':')}")
                print(f"- All caps: {text.isupper()}")
                print(f"Is new section: {is_new_section}")
                
                if is_new_section:
                    print("=> Starting new section with extra spacing")
                    processed_lines.append(' '.join(current_line))  # Add current line to processed lines
                    processed_lines.append('')  # Add empty line for spacing
                    current_line = [text]  # Start new section
                elif y_diff > line_spacing_threshold:
                    print("=> Starting new paragraph")
                    processed_lines.append(' '.join(current_line))  # Add current line to processed lines
                    current_line = [text]  # Start new paragraph
                else:
                    print("=> Continuing current paragraph")
                    current_line.append(text)  # Continue current paragraph
            
            last_y = y_pos  # Update last y position
            last_height = height  # Update last height
        
        # Add the last line
        if current_line:
            processed_lines.append(' '.join(current_line))
        
        # Join with appropriate spacing
        result = []
        for line in processed_lines:
            if line.strip():
                result.append(line.strip())
        
        final_text = '\n\n'.join(result)  # Join paragraphs with double newlines
        
        print("\n=== Final Result ===")
        print("Text blocks joined into paragraphs:")
        print("---")
        print(final_text)
        print("---")
        print("Number of paragraphs:", len(result))
        
        return final_text  # Return the final processed text

class PromptEditorDialog(QDialog):
    def __init__(self, current_prompt, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Translation Prompt Editor")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        
        # Prompt editor
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlainText(current_prompt)
        self.prompt_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 8px;
                font-family: monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.prompt_edit)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_prompt(self):
        return self.prompt_edit.toPlainText()

class PDFViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize API settings
        self.load_api_settings()
        
        # Load stylesheet
        self.load_stylesheet()

        # Modify model management
        self.model_sources = {
            "Ollama": {
                "models": self.get_ollama_models()
                },
            "OpenAI": {
                "models": ["gpt-3.5-turbo", "gpt-4"]
            },
        }
        self.default_source = "OpenAI"

        # Set application icon
        self.set_app_icon()
        
        # Get the screen size
        screen = QApplication.primaryScreen().geometry()
        
        # Set window title
        self.setWindowTitle("PDF Translator")
        
        # Set window size to screen size
        self.setGeometry(0, 0, screen.width(), screen.height())
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
               
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create splitter for PDF view and text panel
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Left side: PDF viewer
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Use custom PDF view
        self.pdf_view = PDFGraphicsView(self)
        self.pdf_view.set_main_window(self)  # Set reference to main window
        self.scene = QGraphicsScene()  # Create a scene for rendering PDF
        
        # Enhanced view properties
        self.pdf_view.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform |
            QPainter.RenderHint.TextAntialiasing
        )
        
        self.pdf_view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.pdf_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.pdf_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.pdf_view.setScene(self.scene)  # Set the scene for the PDF view
        
        # Connect text selection signal
        self.pdf_view.textSelected.connect(self.update_selected_text)  # Update text when selected

        left_layout.addWidget(self.pdf_view)  # Add PDF view to layout
        splitter.addWidget(left_widget)  # Add left widget to splitter
        
        # Define target languages
        self.target_languages = {
            "简体中文": "zh-CN",
            "繁体中文": "zh-TW",
            "日本語": "ja",
            "한국어": "ko",
            "Español": "es",
            "Français": "fr",
            "Deutsch": "de"
        }
        self.target_languages_default = "简体中文"

        # Right side panel layout
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(5)
        
        # Selected text section
        self.text_label = QLabel("Selected Text:")
        right_layout.addWidget(self.text_label)
        
        self.text_edit = QTextEdit()
        #self.text_edit.setReadOnly(True)
        self.text_edit.textChanged.connect(self.on_text_changed)
        right_layout.addWidget(self.text_edit)
        
        # Create controls layout
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)  # Space between controls
        
        # Model source selection combo box
        self.source_combo = QComboBox()
        self.source_combo.addItems(self.model_sources.keys())
        self.source_combo.setCurrentText(self.default_source)  # Set default source
        self.source_combo.currentTextChanged.connect(self.on_source_changed)
        controls_layout.addWidget(self.source_combo)
        
        # Model selection combo box
        self.model_combo = QComboBox()
        self.model_combo.addItems(self.get_available_models(self.default_source))
        self.model_combo.currentTextChanged.connect(self.change_model)
        controls_layout.addWidget(self.model_combo)
        
        # Target language combo box
        self.language_combo = QComboBox()
        self.language_combo.addItems(self.target_languages.keys())
        self.language_combo.setCurrentText(self.target_languages_default)  # Set default to Simplified Chinese
        controls_layout.addWidget(self.language_combo)
        
        # Translate button
        self.translate_button = QPushButton("Translate")
        self.translate_button.setObjectName("translate_button")
        self.translate_button.setToolTip("Translate text")
        self.translate_button.clicked.connect(self.translate_selected_text)
        controls_layout.addWidget(self.translate_button)
        
        # Add API settings button
        self.api_settings_btn = QPushButton("🔑")
        self.api_settings_btn.setToolTip("API Settings")
        self.api_settings_btn.clicked.connect(self.show_api_settings)
        controls_layout.addWidget(self.api_settings_btn)
        
        # Add prompt editor button
        self.prompt_button = QPushButton("📝")
        self.prompt_button.setToolTip("Edit Translation Prompt")
        self.prompt_button.clicked.connect(self.edit_prompt)
        controls_layout.addWidget(self.prompt_button)
        
        # Add controls layout to right_layout
        right_layout.addLayout(controls_layout)
        
        # Translation output section
        self.translated_label = QLabel("Translation:")
        right_layout.addWidget(self.translated_label)
        
        self.translated_text = QTextEdit()
        self.translated_text.setReadOnly(True)
        right_layout.addWidget(self.translated_text)
        
        # Add progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()  # Hide initially
        right_layout.addWidget(self.progress_bar)
        
        # Move progress bar between the translate button and translation output
        right_layout.insertWidget(right_layout.indexOf(self.translated_label), self.progress_bar)
        
        splitter.addWidget(right_widget)
        # Set initial splitter sizes (70% left, 30% right)
        screen_width = screen.width()
        splitter.setSizes([int(screen_width * 0.7), int(screen_width * 0.3)])
                
        # Add a settings button
        self.settings_button = QPushButton("Settings", self)  # Button for settings
        self.settings_button.clicked.connect(self.open_settings)  # Connect to settings function

        # Set the layout for the main widget
        self.setLayout(layout)

        # Create toolbar after initializing translate button
        self.create_toolbar()  # Ensure this is called after translate_button is defined

        # PDF document
        self.doc = None  # Current PDF document
        self.current_page = 0  # Current page index
        self.zoom_factor = 1.0  # Current zoom factor
        
        # Status bar
        self.statusBar().showMessage("Ready")  # Initial status message

        # Add default prompt
        self.translation_prompt = (
            "You are a professional translator. Translate the following text to "
            "{target_lang} sentence by sentence. Keep the original structure and "
            "meaning. Output the translation only, don't output any explanation text:\n\n{text}"
        )

    def get_available_models(self, source=None):
        if source is None:
            source = self.default_source
        return self.model_sources[source]["models"]
    
    def load_stylesheet(self):
        """Load the application stylesheet from file"""
        try:
            with open('styles.css', 'r') as f:
                stylesheet = f.read()
                self.setStyleSheet(stylesheet)
                
                # Set object names for specific styling
                if hasattr(self, 'translate_button'):
                    self.translate_button.setObjectName('translate_button')
                    
        except FileNotFoundError:
            print("Warning: styles.qss not found")
        except Exception as e:
            print(f"Error loading stylesheet: {str(e)}")

    def get_ollama_models(self) -> List[str]:
        """Get list of available Ollama models"""
        try:
            response = requests.get("http://localhost:11434/api/tags")
            response.raise_for_status()
            
            models_data = response.json().get('models', [])
            return [model['name'] for model in models_data]
            
        except requests.exceptions.ConnectionError:
            raise Exception("Could not connect to Ollama service. Is it running?")
        except Exception as e:
            raise Exception(f"Failed to get models: {str(e)}")

    def create_toolbar(self):
        """Create the toolbar with various buttons"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Adjust toolbar height
        toolbar.setFixedHeight(40)  # Make toolbar slightly taller
        
        # Add buttons to toolbar
        self.open_btn = QPushButton("Open PDF")  # Button to open PDF
        self.open_btn.setObjectName("QPushButton")   # Add object name
        self.open_btn.clicked.connect(self.open_pdf)  # Connect to open function
        toolbar.addWidget(self.open_btn)  # Add to toolbar
        
        toolbar.addSeparator()  # Add separator
        
        self.prev_btn = QPushButton("◀ Previous")  # Button for previous page
        self.prev_btn.setObjectName("QPushButton")   # Add object name
        self.prev_btn.clicked.connect(self.previous_page)  # Connect to previous page function
        self.prev_btn.setEnabled(False)  # Initially disabled
        toolbar.addWidget(self.prev_btn)  # Add to toolbar
        
        self.next_btn = QPushButton("Next ▶")  # Button for next page
        self.next_btn.setObjectName("QPushButton")   # Add object name
        self.next_btn.clicked.connect(self.next_page)  # Connect to next page function
        self.next_btn.setEnabled(False)  # Initially disabled
        toolbar.addWidget(self.next_btn)  # Add to toolbar
        
        self.page_label = QLabel("Page: 0/0")  # Label for current page
        toolbar.addWidget(self.page_label)  # Add to toolbar
        
        toolbar.addSeparator()  # Add separator
        
        self.zoom_in_btn = QPushButton("Zoom In (+)")  # Button for zooming in
        self.zoom_in_btn.setObjectName("QPushButton")   # Add object name
        self.zoom_in_btn.clicked.connect(self.zoom_in_func)  # Connect to zoom in function
        self.zoom_in_btn.setEnabled(False)  # Initially disabled
        toolbar.addWidget(self.zoom_in_btn)  # Add to toolbar
        
        self.zoom_out_btn = QPushButton("Zoom Out (-)")  # Button for zooming out
        self.zoom_out_btn.setObjectName("QPushButton")   # Add object name
        self.zoom_out_btn.clicked.connect(self.zoom_out_func)  # Connect to zoom out function
        self.zoom_out_btn.setEnabled(False)  # Initially disabled
        toolbar.addWidget(self.zoom_out_btn)  # Add to toolbar
        
        self.fit_btn = QPushButton("Fit Width")  # Button to fit PDF to width
        self.fit_btn.setObjectName("QPushButton")   # Add object name
        self.fit_btn.clicked.connect(self.fit_width)  # Connect to fit width function
        self.fit_btn.setEnabled(False)  # Initially disabled
        toolbar.addWidget(self.fit_btn)  # Add to toolbar
        
        toolbar.addSeparator()  # Add separator
        
        # Add line spacing control
        spacing_label = QLabel("Line Spacing:")  # Label for line spacing
        #spacing_label.setStyleSheet("padding: 0 5px;")  # Style for label
        toolbar.addWidget(spacing_label)  # Add to toolbar
        
        self.spacing_spinbox = QDoubleSpinBox()  # Spin box for line spacing
        self.spacing_spinbox.setRange(0.1, 50.0)  # Allow a wide range of values
        self.spacing_spinbox.setValue(3.0)  # Default value
        self.spacing_spinbox.setSingleStep(0.5)  # Step size
        self.spacing_spinbox.setDecimals(1)  # Show one decimal place
        self.spacing_spinbox.setFixedWidth(70)  # Fixed width for spin box
        self.spacing_spinbox.setToolTip("Adjust line spacing threshold for text selection")  # Tooltip
        toolbar.addWidget(self.spacing_spinbox)  # Add to toolbar
        
        # Add auto-detect button
        detect_spacing_btn = QPushButton("Auto Detect")  # Button for auto-detecting spacing
        detect_spacing_btn.setObjectName("QPushButton")   # Add object name
        detect_spacing_btn.clicked.connect(self.auto_detect_spacing)  # Connect to auto-detect function
        toolbar.addWidget(detect_spacing_btn)  # Add to toolbar

    def update_buttons(self):
        """Update the state of toolbar buttons"""
        has_doc = self.doc is not None  # Check if a document is loaded
        self.prev_btn.setEnabled(has_doc and self.current_page > 0)  # Enable previous button if applicable
        self.next_btn.setEnabled(has_doc and self.current_page < len(self.doc) - 1)  # Enable next button if applicable
        self.zoom_in_btn.setEnabled(has_doc)  # Enable zoom in button if applicable
        self.zoom_out_btn.setEnabled(has_doc)  # Enable zoom out button if applicable
        self.fit_btn.setEnabled(has_doc)  # Enable fit width button if applicable

    def update_selected_text(self, text):
        """Update the text panel with selected text"""
        # Clean up the text
        cleaned_text = self.clean_text(text)  # Clean the selected text
        
        # Set plain text instead of HTML
        self.text_edit.setPlainText(cleaned_text)  # Display cleaned text
        self.statusBar().showMessage(f"Selected {len(cleaned_text)} characters")  # Update status bar

    def clean_text(self, text):
        """Clean up the selected text and preserve paragraph structure"""
        # Split into paragraphs while preserving original structure
        paragraphs = text.split('\n\n')  # Split by double newlines
        
        cleaned_paragraphs = []  # To store cleaned paragraphs
        for p in paragraphs:
            if p.strip():  # Check if paragraph is not empty
                # Remove multiple spaces within paragraph
                cleaned_p = ' '.join(p.split())  # Normalize spaces
                # Remove soft hyphens and other special characters
                cleaned_p = cleaned_p.replace('\u00AD', '')  # Remove soft hyphen
                cleaned_p = cleaned_p.replace('ﬁ', 'fi')  # Replace ligature
                cleaned_p = cleaned_p.replace('��', 'fl')  # Replace ligature
                cleaned_paragraphs.append(cleaned_p)  # Add cleaned paragraph
        
        # Join paragraphs with double newlines
        return '\n\n'.join(cleaned_paragraphs)  # Return cleaned text

    def open_pdf(self):
        """Open a PDF file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF Files (*.pdf)"
        )
        if file_path:
            self.load_pdf(file_path)  # Load the selected PDF file
    
    def load_pdf(self, file_path):
        """Load the PDF document"""
        try:
            self.doc = fitz.open(file_path)  # Open the PDF file
            self.current_page = 0  # Reset current page
            self.zoom_factor = 1.0  # Reset zoom factor
            self.update_page_label()  # Update page label
            self.render_page()  # Render the first page
            self.update_buttons()  # Update button states
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open PDF: {str(e)}")  # Show error message
    
    def render_page(self):
        """Render the current page of the PDF"""
        if not self.doc:
            return  # Exit if no document is loaded
            
        self.scene.clear()  # Clear the scene
        page = self.doc[self.current_page]  # Get the current page
        
        # Update current page in PDF view for text selection
        self.pdf_view.current_page = page
        self.pdf_view.zoom_factor = self.zoom_factor
        
        # Calculate matrix for high-quality rendering
        base_dpi = 72.0
        scale_factor = self.pdf_view.dpi / base_dpi * self.zoom_factor  # Calculate scale factor
        zoom_matrix = fitz.Matrix(scale_factor, scale_factor)  # Create zoom matrix
        
        try:
            pix = page.get_pixmap(
                matrix=zoom_matrix,
                alpha=False,
                colorspace=fitz.csRGB
            )  # Render the page to a pixmap
            
            img = QImage(pix.samples, pix.width, pix.height,
                        pix.stride, QImage.Format.Format_RGB888)  # Create QImage from pixmap
            
            pixmap = QPixmap.fromImage(img)  # Convert QImage to QPixmap
            
            # Add white background
            background = self.scene.addRect(
                QRectF(pixmap.rect()),
                QPen(Qt.PenStyle.NoPen),
                QBrush(Qt.GlobalColor.white)
            )  # Add a white background
            
            self.scene.addPixmap(pixmap)  # Add the pixmap to the scene
            self.scene.setSceneRect(QRectF(pixmap.rect()))  # Set scene rectangle
            
            if self.zoom_factor == 1.0:
                self.fit_width()  # Fit to width if zoom factor is 1.0
            
            self.statusBar().showMessage(f"Page {self.current_page + 1} rendered successfully")  # Update status bar
            
        except Exception as e:
            self.statusBar().showMessage(f"Error rendering page: {str(e)}")  # Show error message
            
        self.update_page_label()  # Update page label
        self.update_buttons()  # Update button states

    def previous_page(self):
        """Go to the previous page"""
        if self.doc and self.current_page > 0:
            self.current_page -= 1  # Decrement current page
            self.render_page()  # Render the new current page
    
    def next_page(self):
        """Go to the next page"""
        if self.doc and self.current_page < len(self.doc) - 1:
            self.current_page += 1  # Increment current page
            self.render_page()  # Render the new current page
    
    def update_page_label(self):
        """Update the page label in the toolbar"""
        if self.doc:
            self.page_label.setText(f"Page: {self.current_page + 1}/{len(self.doc)}")  # Update page label
    
    def zoom_in_func(self):
        """Zoom in on the current page"""
        self.zoom_factor *= 1.2  # Increase zoom factor
        self.render_page()  # Render the page with new zoom factor
    
    def zoom_out_func(self):
        """Zoom out of the current page"""
        self.zoom_factor /= 1.2  # Decrease zoom factor
        self.render_page()  # Render the page with new zoom factor

    def fit_width(self):
        if not self.doc:
            return
        
        # Fit to width while maintaining aspect ratio
        viewport = self.pdf_view.viewport().width()
        scene_width = self.scene.width()
        if scene_width > 0:
            self.pdf_view.resetTransform()
            scale = viewport / scene_width
            self.pdf_view.scale(scale * 0.95, scale * 0.95)

    def auto_detect_spacing(self):
        """Automatically detect line spacing from current page"""
        if not self.doc or self.current_page >= len(self.doc):
            return
            
        page = self.doc[self.current_page]
        blocks = page.get_text("blocks")
        
        if not blocks:
            return
            
        # Get all y-positions
        y_positions = []
        for block in blocks:
            y_positions.append(block[1])  # y0 position
        
        # Sort y-positions
        y_positions.sort()
        
        # Calculate differences between consecutive lines
        differences = []
        for i in range(len(y_positions) - 1):
            diff = abs(y_positions[i+1] - y_positions[i])
            if diff > 0:  # Ignore zero differences
                differences.append(diff)
        
        if differences:
            # Use the median difference as the threshold
            median_spacing = sorted(differences)[len(differences)//2]
            # Add a small buffer
            suggested_spacing = median_spacing * 1.2
            self.spacing_spinbox.setValue(suggested_spacing)
            self.statusBar().showMessage(f"Detected line spacing: {suggested_spacing:.1f}")
        else:
            self.statusBar().showMessage("Could not detect line spacing")

    def get_selected_text(self):
        """Get the selected text from the PDF view"""
        # Implementation of get_selected_text method
        # This should return the text that you want to translate
        return self.text_edit.toPlainText()  # Placeholder for actual selected text retrieval

    def open_settings(self):
        """Open settings dialog for user preferences"""
        settings_dialog = QDialog(self)
        settings_dialog.setWindowTitle("Settings")
        # Add settings options here (e.g., theme selection, font size)
        # ... settings UI code ...
        settings_dialog.exec_()

    def save_translation(self, original_text, translated_text, language):
        """Save the translation to a file or database"""
        with open("translations.txt", "a") as f:
            f.write(f"Original: {original_text}\nTranslated: {translated_text} ({language})\n\n")

    def translate_selected_text(self):
        """Translate the selected text"""
        if not self.current_model:
            QMessageBox.warning(
                self,
                "No Model Selected",
                "Please select a translation model first."
            )
            return

        text = self.text_edit.toPlainText()
        
        # Check if text is empty
        if not text or text.isspace():
            QMessageBox.warning(
                self,
                "No Text Selected",
                "Please select some text to translate."
            )
            return
        
        try:
            # Show translation is starting
            self.statusBar().showMessage("Starting translation...")
            self.translate_button.setEnabled(False)
            QApplication.processEvents()  # Force UI update
            
            # Get current source from source_combo, not stored value
            print(f"Current source: {self.current_source}")  # Debug print
            print(f"Current model: {self.current_model}")  # Debug print
            
            # Perform translation based on source
            if self.current_source == "OpenAI":
                print("Using OpenAI translation")  # Debug print
                translated_text = self.translate_with_openai(text)
            else:
                print("Using Ollama translation")  # Debug print
                translated_text = self.translate_with_ollama(text)
            
            if translated_text:
                self.translated_text.setPlainText(translated_text)
                self.statusBar().showMessage("Translation completed: {}:{}".format(self.current_source, self.current_model))
            else:
                raise Exception("No translation result received")
            
        except Exception as e:
            error_msg = str(e)
            print(f"Translation error: {error_msg}")  # Debug print
            QMessageBox.critical(
                self,
                "Translation Error",
                f"An error occurred during translation:\n{error_msg}"
            )
            self.statusBar().showMessage(f"Translation failed: {error_msg}")
        
        finally:
            # Reset button state
            self.translate_button.setEnabled(True)
            QApplication.processEvents()

    def translate_with_openai(self, text: str) -> str:
        """Translate text using OpenAI API with streaming output"""
        print("Starting OpenAI translation...")
        
        if not self.api_settings.get('openai_api_key'):
            raise Exception("OpenAI API key not configured. Please set it in API Settings (🔑)")

        try:
            # Show progress bar
            self.progress_bar.setVisible(True)
            self.setIndeterminate(True)  # Switch to indeterminate mode
            self.statusBar().showMessage("Starting translation...")
            
            client = openai.OpenAI(api_key=self.api_settings['openai_api_key'])
            target_lang = self.language_combo.currentText()
            
            print(f"Using OpenAI model: {self.current_model}")
            print(f"Target language: {target_lang}")
            
            # Initialize translated text
            translated_text = ""
            self.translated_text.clear()
            
            # Create streaming response
            stream = client.chat.completions.create(
                model=self.current_model,
                messages=[
                    {"role": "system", "content": "You are a professional translator."},
                    {"role": "user", "content": f"Translate the following text to {target_lang}. Output ONLY the translation:\n\n{text}"}
                ],
                temperature=0.3,
                stream=True  # Enable streaming
            )
            
            # Process the stream
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    # Get the new text chunk
                    new_text = chunk.choices[0].delta.content
                    translated_text += new_text
                    
                    # Update the translation text area
                    self.translated_text.setPlainText(translated_text)
                    
                    # Move cursor to end
                    cursor = self.translated_text.textCursor()
                    cursor.movePosition(QTextCursor.MoveOperation.End)
                    self.translated_text.setTextCursor(cursor)
                    
                    # Force UI update
                    QApplication.processEvents()
            
            print("OpenAI translation completed successfully")
            self.statusBar().showMessage("Translation completed!")
            return translated_text
            
        except openai.AuthenticationError:
            raise Exception("Invalid OpenAI API key. Please check your API key in Settings.")
        except openai.RateLimitError:
            raise Exception("OpenAI API rate limit exceeded. Please try again later.")
        except Exception as e:
            print(f"OpenAI translation error: {str(e)}")
            raise
        finally:
            # Hide progress bar and reset to normal mode
            self.setIndeterminate(False)
            self.progress_bar.setVisible(False)
            QApplication.processEvents()

    def translate_with_ollama(self, text: str) -> str:
        """Translate text using Ollama API with progress updates"""
        try:
            print("Starting Ollama translation...")
            
            # Show progress bar
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # Split text into blocks (by paragraphs)
            blocks = [b for b in text.split('\n\n') if b.strip()]
            total_blocks = len(blocks)
            translated_blocks = []
            
            for i, block in enumerate(blocks, 1):
                # Update progress bar
                progress = int((i - 1) / total_blocks * 100)
                self.progress_bar.setValue(progress)
                self.statusBar().showMessage(f"Translating block {i}/{total_blocks}...")
                QApplication.processEvents()  # Allow UI updates
                
                # Skip empty blocks
                if not block.strip():
                    continue
                
                url = f"{self.api_settings['ollama_host']}/api/generate"
                target_lang = self.language_combo.currentText()
                
                prompt = (
                    f"You are a professional translator. Translate the following text to "
                    f"{target_lang}. Output ONLY the translation, without any explanations, "
                    f"notes, or special tokens:\n\n{block}"
                )
                
                payload = {
                    "model": self.current_model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "top_k": 40
                }
                
                response = requests.post(url, json=payload, timeout=30)
                
                if response.status_code != 200:
                    raise Exception(f"Ollama API error: {response.text}")
                    
                result = response.json()
                translated_block = result.get('response', '').strip()
                
                if not translated_block:
                    raise Exception(f"Empty response from Ollama for block {i}")
                
                translated_blocks.append(translated_block)
                
                # Update translation text area with progress
                self.translated_text.setPlainText('\n\n'.join(translated_blocks))
                QApplication.processEvents()  # Allow UI updates
            
            # Set final progress
            self.progress_bar.setValue(100)
            self.statusBar().showMessage("Translation completed!")
            
            # Hide progress bar after a delay
            QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))
            
            return '\n\n'.join(translated_blocks)
            
        except requests.exceptions.Timeout:
            raise Exception("Translation request timed out. Please try again.")
        except requests.exceptions.ConnectionError:
            raise Exception(
                f"Could not connect to Ollama at {self.api_settings['ollama_host']}\n"
                "Please ensure:\n"
                "1. Ollama is installed\n"
                "2. Ollama service is running (run 'ollama serve')\n"
                "3. The host setting is correct"
            )
        except Exception as e:
            print(f"Ollama translation error: {str(e)}")
            raise
        finally:
            # Ensure progress bar is hidden in case of error
            self.progress_bar.setVisible(False)

    def change_model(self, model_name):
        """Handle model change"""
        self.statusBar().showMessage(f"Changed to model: {model_name}")

    def edit_prompt(self):
        """Open the prompt editor dialog"""
        dialog = PromptEditorDialog(self.translation_prompt, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.translation_prompt = dialog.get_prompt()
            self.statusBar().showMessage("Translation prompt updated", 3000)

    def set_app_icon(self):
        """Set the application icon for both window and dock"""
        # Create the icons directory if it doesn't exist
        if not os.path.exists('icons'):
            os.makedirs('icons')
        
        # Create icon file if it doesn't exist
        icon_path = 'icons/app_icon.png'
        if not os.path.exists(icon_path):
            self.create_default_icon(icon_path)
        
        # Set the window icon
        icon = QIcon(icon_path)
        self.setWindowIcon(icon)
        
        # Set dock icon for macOS
        try:
            # Import macOS specific modules
            import AppKit
            
            # Set the dock icon
            icon_path_abs = os.path.abspath(icon_path)
            icon_image = AppKit.NSImage.alloc().initWithContentsOfFile_(icon_path_abs)
            AppKit.NSApplication.sharedApplication().setApplicationIconImage_(icon_image)
            
        except ImportError:
            # Not on macOS, skip dock icon setting
            pass

    def create_default_icon(self, icon_path):
        """Create a default icon if none exists"""
        # Create a simple icon using PIL
        from PIL import Image, ImageDraw, ImageFont
        
        # Create a new image with a white background
        img_size = (128, 128)
        img = Image.new('RGBA', img_size, color=(255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        
        # Draw a rounded rectangle
        radius = 10
        draw.rounded_rectangle(
            [(10, 10), (118, 118)],
            radius=radius,
            fill=(65, 105, 225),  # Royal Blue
            outline=(47, 79, 79),  # Dark Slate Gray
            width=2
        )
        
        # Add "PDF" text
        try:
            # Try to use a system font
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
        except:
            # Fallback to default font
            font = ImageFont.load_default()
        
        # Draw "PDF" text
        text = "PDF"
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]        
        text_height = text_bbox[3] - text_bbox[1]
        
        x = (img_size[0] - text_width) // 2
        y = (img_size[1] - text_height) // 2 - 10
        
        draw.text((x, y), text, fill=(255, 255, 255), font=font)
        
        # Add "Trans" text below
        text = "Trans"
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        
        x = (img_size[0] - text_width) // 2
        y = y + text_height + 5
        
        draw.text((x, y), text, fill=(255, 255, 255), font=font)
        
        # Save the icon
        img.save(icon_path, 'PNG')

    def load_api_settings(self):
        """Load API settings from config file and environment variables"""
        try:
            # Try to load from config file first
            with open('config.json', 'r') as f:
                config = json.load(f)
                self.api_settings = config.get('api_settings', {})
        except FileNotFoundError:
            self.api_settings = {}

        # Set default values if not present
        if 'ollama_host' not in self.api_settings:
            self.api_settings['ollama_host'] = 'http://localhost:11434'

        # Try to get OpenAI API key from environment variable
        openai_key_from_env = os.getenv('OPENAI_API_KEY')
        if openai_key_from_env:
            self.api_settings['openai_api_key'] = openai_key_from_env
        elif 'openai_api_key' not in self.api_settings:
            self.api_settings['openai_api_key'] = ''

        print(f"OpenAI API key loaded: {'Yes' if self.api_settings.get('openai_api_key') else 'No'}")

    def save_api_settings(self):
        """Save API settings to config file"""
        config = {'api_settings': self.api_settings}
        with open('config.json', 'w') as f:
            json.dump(config, f)

    def show_api_settings(self):
        """Show API settings dialog"""
        dialog = APISettingsDialog(self.api_settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.api_settings = dialog.get_settings()
            self.save_api_settings()

    def on_source_changed(self, new_source):
        """Handle source change event"""
        print(f"Source changed to: {new_source}")  # Debug print
        self.model_combo.clear()
        self.model_combo.addItems(self.get_available_models(new_source))

        # Update cost estimate if OpenAI is selected
        if new_source == "OpenAI":
            self.update_cost_estimate()
            # Check for API key
            if not self.api_settings.get('openai_api_key'):
                QMessageBox.warning(
                    self,
                    "OpenAI API Key Required",
                    "Please configure your OpenAI API key in Settings (🔑)"
                )
        else:
            self.statusBar().showMessage(f"Changed to {new_source} models")
                
    def update_cost_estimate(self):
        """Update the cost estimate in the status bar"""
        text = self.text_edit.toPlainText()
        if text and self.current_source == "OpenAI":
            estimated_cost = self.estimate_cost(text)
            self.statusBar().showMessage(f"Estimated cost: ${estimated_cost:.4f} USD")
        else:
            self.statusBar().showMessage("")

    def text_selection_changed(self):
        """Handle text selection changes"""
        selected_text = self.pdf_view.selectedText()
        if selected_text:
            self.text_edit.setPlainText(selected_text)
            # Update cost estimate if OpenAI is selected
            if self.current_source == "OpenAI":
                self.update_cost_estimate()

    def on_text_changed(self):
        """Handle text changes in the text edit"""
        if self.current_source == "OpenAI":
            self.update_cost_estimate()

    def estimate_tokens(self, text: str) -> int:
        """Rough estimate of tokens in text (about 4 chars per token)"""
        return len(text) // 4

    def estimate_cost(self, text: str) -> float:
        """Estimate cost of translation in USD"""
        tokens = self.estimate_tokens(text)
        model = self.current_model
        
        # Pricing per 1K tokens (as of March 2024)
        prices = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015}
        }
        
        if model.startswith("gpt-4"):
            price = prices["gpt-4"]
        else:
            price = prices["gpt-3.5-turbo"]
        
        # Estimate cost (assuming output is similar length to input)
        cost = (tokens * price["input"] + tokens * price["output"]) / 1000
        return cost
    
    @property
    def current_source(self):
        return self.source_combo.currentText()
    
    @property
    def current_model(self):
        return self.model_combo.currentText()

    def setIndeterminate(self, indeterminate: bool):
        """Set progress bar to indeterminate mode"""
        if indeterminate:
            self.progress_bar.setRange(0, 0)  # Makes the progress bar indeterminate
        else:
            self.progress_bar.setRange(0, 100)  # Restore normal range

class APISettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API Settings")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # OpenAI API Key
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("OpenAI API Key:")
        self.api_key_input = QLineEdit()
        self.api_key_input.setText(current_settings.get('openai_api_key', ''))
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_key_layout.addWidget(api_key_label)
        api_key_layout.addWidget(self.api_key_input)
        layout.addLayout(api_key_layout)
        
        # Ollama Host
        ollama_layout = QHBoxLayout()
        ollama_label = QLabel("Ollama Host:")
        self.ollama_input = QLineEdit()
        self.ollama_input.setText(current_settings.get('ollama_host', 'http://localhost:11434'))
        ollama_layout.addWidget(ollama_label)
        ollama_layout.addWidget(self.ollama_input)
        layout.addLayout(ollama_layout)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLabel {
                font-size: 11px;
                min-width: 100px;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QPushButton {
                padding: 5px 15px;
            }
        """)

    def get_settings(self):
        """Return the current settings"""
        return {
            'openai_api_key': self.api_key_input.text(),
            'ollama_host': self.ollama_input.text()
        }

if __name__ == '__main__':
    # Initialize application
    app = QApplication(sys.argv)
    
    # Set application name
    app.setApplicationName("PDF Translator")
    
    # Create and show the viewer
    viewer = PDFViewer()
    viewer.show()
    
    # Set the dock icon for macOS
    if os.path.exists('icons/app_icon.png'):
        try:
            import AppKit
            icon_path = os.path.abspath('icons/app_icon.png')
            icon_image = AppKit.NSImage.alloc().initWithContentsOfFile_(icon_path)
            AppKit.NSApplication.sharedApplication().setApplicationIconImage_(icon_image)
        except ImportError:
            pass
    
    app.exec()
    sys.exit()
    #sys.exit(app.exec())