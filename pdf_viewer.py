from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import fitz  # PyMuPDF
import sys

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

class PDFViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Viewer with Text Selection")
        self.setGeometry(100, 100, 1200, 800)
        
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
        
        left_layout.addWidget(self.pdf_view)  # Add PDF view to layout
        splitter.addWidget(left_widget)  # Add left widget to splitter
        
        # Right side: Selected text panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        self.text_label = QLabel("Selected Text:")  # Label for selected text
        right_layout.addWidget(self.text_label)
        
        self.text_edit = QTextEdit()  # Text edit for displaying selected text
        self.text_edit.setReadOnly(True)  # Make it read-only
        right_layout.addWidget(self.text_edit)
        
        # Add copy button
        self.copy_button = QPushButton("Copy to Clipboard")  # Button to copy text
        self.copy_button.clicked.connect(self.copy_text)  # Connect to copy function
        right_layout.addWidget(self.copy_button)
        
        splitter.addWidget(right_widget)  # Add right widget to splitter
        
        # Set splitter sizes
        splitter.setSizes([800, 400])  # Set initial sizes for splitter
        
        # Connect text selection signal
        self.pdf_view.textSelected.connect(self.update_selected_text)  # Update text when selected
        
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

    def create_toolbar(self):
        """Create the toolbar with various buttons"""
        toolbar = QToolBar()  # Create a toolbar
        toolbar.setMovable(False)  # Make toolbar non-movable
        self.addToolBar(toolbar)  # Add toolbar to main window
        
        # Style for toolbar buttons
        button_style = """
            QPushButton {
                padding: 6px 12px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: #f8f9fa;
                min-width: 80px;
                margin: 0 2px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
            QPushButton:disabled {
                background-color: #e9ecef;
                color: #adb5bd;
            }
        """
        
        # Add buttons to toolbar
        self.open_btn = QPushButton("Open PDF")  # Button to open PDF
        self.open_btn.setStyleSheet(button_style)  # Apply style
        self.open_btn.clicked.connect(self.open_pdf)  # Connect to open function
        toolbar.addWidget(self.open_btn)  # Add to toolbar
        
        toolbar.addSeparator()  # Add separator
        
        self.prev_btn = QPushButton("◀ Previous")  # Button for previous page
        self.prev_btn.setStyleSheet(button_style)  # Apply style
        self.prev_btn.clicked.connect(self.previous_page)  # Connect to previous page function
        self.prev_btn.setEnabled(False)  # Initially disabled
        toolbar.addWidget(self.prev_btn)  # Add to toolbar
        
        self.next_btn = QPushButton("Next ▶")  # Button for next page
        self.next_btn.setStyleSheet(button_style)  # Apply style
        self.next_btn.clicked.connect(self.next_page)  # Connect to next page function
        self.next_btn.setEnabled(False)  # Initially disabled
        toolbar.addWidget(self.next_btn)  # Add to toolbar
        
        self.page_label = QLabel("Page: 0/0")  # Label for current page
        self.page_label.setStyleSheet("padding: 0 10px; color: #333;")  # Style for label
        toolbar.addWidget(self.page_label)  # Add to toolbar
        
        toolbar.addSeparator()  # Add separator
        
        self.zoom_in_btn = QPushButton("Zoom In (+)")  # Button for zooming in
        self.zoom_in_btn.setStyleSheet(button_style)  # Apply style
        self.zoom_in_btn.clicked.connect(self.zoom_in_func)  # Connect to zoom in function
        self.zoom_in_btn.setEnabled(False)  # Initially disabled
        toolbar.addWidget(self.zoom_in_btn)  # Add to toolbar
        
        self.zoom_out_btn = QPushButton("Zoom Out (-)")  # Button for zooming out
        self.zoom_out_btn.setStyleSheet(button_style)  # Apply style
        self.zoom_out_btn.clicked.connect(self.zoom_out_func)  # Connect to zoom out function
        self.zoom_out_btn.setEnabled(False)  # Initially disabled
        toolbar.addWidget(self.zoom_out_btn)  # Add to toolbar
        
        self.fit_btn = QPushButton("Fit Width")  # Button to fit PDF to width
        self.fit_btn.setStyleSheet(button_style)  # Apply style
        self.fit_btn.clicked.connect(self.fit_width)  # Connect to fit width function
        self.fit_btn.setEnabled(False)  # Initially disabled
        toolbar.addWidget(self.fit_btn)  # Add to toolbar
        
        toolbar.addSeparator()  # Add separator
        
        # Add line spacing control
        spacing_label = QLabel("Line Spacing:")  # Label for line spacing
        spacing_label.setStyleSheet("padding: 0 5px;")  # Style for label
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
        detect_spacing_btn.setStyleSheet(button_style)  # Apply style
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
                cleaned_p = cleaned_p.replace('ﬂ', 'fl')  # Replace ligature
                cleaned_paragraphs.append(cleaned_p)  # Add cleaned paragraph
        
        # Join paragraphs with double newlines
        return '\n\n'.join(cleaned_paragraphs)  # Return cleaned text

    def copy_text(self):
        """Copy selected text to clipboard"""
        text = self.text_edit.toPlainText()  # Get text from text edit
        if text:
            clipboard = QApplication.clipboard()  # Access clipboard
            clipboard.setText(text)  # Set text to clipboard
            self.statusBar().showMessage("Text copied to clipboard")  # Update status bar

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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = PDFViewer()
    viewer.show()
    sys.exit(app.exec()) 