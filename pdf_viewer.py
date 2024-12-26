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
        self.rubberBand = None
        self.origin = QPoint()
        self.current_page = None
        self.zoom_factor = 1.0
        self.dpi = 300
        self.main_window = None  # Reference to main window

    def set_main_window(self, main_window):
        """Set reference to main window"""
        self.main_window = main_window

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.pos()
            if not self.rubberBand:
                self.rubberBand = QRubberBand(QRubberBand.Shape.Rectangle, self)
            self.rubberBand.setGeometry(QRect(self.origin, QSize()))
            self.rubberBand.show()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.rubberBand:
            self.rubberBand.setGeometry(QRect(self.origin, event.pos()).normalized())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
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
                
                # Get text blocks
                blocks = self.current_page.get_text("blocks", clip=rect)
                if blocks:
                    # Get current spacing value from main window
                    spacing = self.main_window.spacing_spinbox.value()
                    # Process and join text blocks with current spacing
                    processed_text = self.process_text_blocks(blocks, spacing)
                    if processed_text.strip():
                        self.textSelected.emit(processed_text)
            
            self.rubberBand.hide()
            self.rubberBand = None
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
        
        processed_lines = []
        current_line = []
        last_y = None
        last_height = None
        
        print("\nProcessing decisions:")
        for i, block in enumerate(sorted_blocks):
            text = block[4]
            y_pos = block[1]
            height = block[3] - block[1]
            
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
                current_line.append(text)
            else:
                y_diff = abs(y_pos - last_y)
                height_ratio = height / last_height if last_height else 1.0
                
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
                    processed_lines.append(' '.join(current_line))
                    processed_lines.append('')
                    current_line = [text]
                elif y_diff > line_spacing_threshold:
                    print("=> Starting new paragraph")
                    processed_lines.append(' '.join(current_line))
                    current_line = [text]
                else:
                    print("=> Continuing current paragraph")
                    current_line.append(text)
            
            last_y = y_pos
            last_height = height
        
        # Add the last line
        if current_line:
            processed_lines.append(' '.join(current_line))
        
        # Join with appropriate spacing
        result = []
        for line in processed_lines:
            if line.strip():
                result.append(line.strip())
        
        final_text = '\n\n'.join(result)
        
        print("\n=== Final Result ===")
        print("Text blocks joined into paragraphs:")
        print("---")
        print(final_text)
        print("---")
        print("Number of paragraphs:", len(result))
        
        return final_text

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
        self.scene = QGraphicsScene()
        
        # Enhanced view properties
        self.pdf_view.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform |
            QPainter.RenderHint.TextAntialiasing
        )
        
        self.pdf_view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.pdf_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.pdf_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.pdf_view.setScene(self.scene)
        
        left_layout.addWidget(self.pdf_view)
        splitter.addWidget(left_widget)
        
        # Right side: Selected text panel
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        self.text_label = QLabel("Selected Text:")
        right_layout.addWidget(self.text_label)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        right_layout.addWidget(self.text_edit)
        
        # Add copy button
        self.copy_button = QPushButton("Copy to Clipboard")
        self.copy_button.clicked.connect(self.copy_text)
        right_layout.addWidget(self.copy_button)
        
        splitter.addWidget(right_widget)
        
        # Set splitter sizes
        splitter.setSizes([800, 400])
        
        # Connect text selection signal
        self.pdf_view.textSelected.connect(self.update_selected_text)
        
        # Create toolbar
        self.create_toolbar()
        
        # PDF document
        self.doc = None
        self.current_page = 0
        self.zoom_factor = 1.0
        
        # Status bar
        self.statusBar().showMessage("Ready")

    def create_toolbar(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
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
        self.open_btn = QPushButton("Open PDF")
        self.open_btn.setStyleSheet(button_style)
        self.open_btn.clicked.connect(self.open_pdf)
        toolbar.addWidget(self.open_btn)
        
        toolbar.addSeparator()
        
        self.prev_btn = QPushButton("◀ Previous")
        self.prev_btn.setStyleSheet(button_style)
        self.prev_btn.clicked.connect(self.previous_page)
        self.prev_btn.setEnabled(False)
        toolbar.addWidget(self.prev_btn)
        
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.setStyleSheet(button_style)
        self.next_btn.clicked.connect(self.next_page)
        self.next_btn.setEnabled(False)
        toolbar.addWidget(self.next_btn)
        
        self.page_label = QLabel("Page: 0/0")
        self.page_label.setStyleSheet("padding: 0 10px; color: #333;")
        toolbar.addWidget(self.page_label)
        
        toolbar.addSeparator()
        
        self.zoom_in_btn = QPushButton("Zoom In (+)")
        self.zoom_in_btn.setStyleSheet(button_style)
        self.zoom_in_btn.clicked.connect(self.zoom_in_func)
        self.zoom_in_btn.setEnabled(False)
        toolbar.addWidget(self.zoom_in_btn)
        
        self.zoom_out_btn = QPushButton("Zoom Out (-)")
        self.zoom_out_btn.setStyleSheet(button_style)
        self.zoom_out_btn.clicked.connect(self.zoom_out_func)
        self.zoom_out_btn.setEnabled(False)
        toolbar.addWidget(self.zoom_out_btn)
        
        self.fit_btn = QPushButton("Fit Width")
        self.fit_btn.setStyleSheet(button_style)
        self.fit_btn.clicked.connect(self.fit_width)
        self.fit_btn.setEnabled(False)
        toolbar.addWidget(self.fit_btn)
        
        toolbar.addSeparator()
        
        # Add line spacing control
        spacing_label = QLabel("Line Spacing:")
        spacing_label.setStyleSheet("padding: 0 5px;")
        toolbar.addWidget(spacing_label)
        
        self.spacing_spinbox = QDoubleSpinBox()
        self.spacing_spinbox.setRange(0.1, 50.0)  # Allow a wide range of values
        self.spacing_spinbox.setValue(3.0)  # Default value
        self.spacing_spinbox.setSingleStep(0.5)  # Step size
        self.spacing_spinbox.setDecimals(1)  # Show one decimal place
        self.spacing_spinbox.setFixedWidth(70)
        self.spacing_spinbox.setToolTip("Adjust line spacing threshold for text selection")
        toolbar.addWidget(self.spacing_spinbox)
        
        # Add auto-detect button
        detect_spacing_btn = QPushButton("Auto Detect")
        detect_spacing_btn.setStyleSheet(button_style)
        detect_spacing_btn.clicked.connect(self.auto_detect_spacing)
        toolbar.addWidget(detect_spacing_btn)

    def update_buttons(self):
        """Update the state of toolbar buttons"""
        has_doc = self.doc is not None
        self.prev_btn.setEnabled(has_doc and self.current_page > 0)
        self.next_btn.setEnabled(has_doc and self.current_page < len(self.doc) - 1)
        self.zoom_in_btn.setEnabled(has_doc)
        self.zoom_out_btn.setEnabled(has_doc)
        self.fit_btn.setEnabled(has_doc)

    def update_selected_text(self, text):
        """Update the text panel with selected text"""
        # Clean up the text
        cleaned_text = self.clean_text(text)
        
        # Convert paragraphs to HTML with styling
        paragraphs = cleaned_text.split('\n\n')
        
        html_text = '''
            <html>
            <head>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    line-height: 1.4;
                    margin: 0;
                    padding: 10px;
                }
                .paragraph {
                    margin: 0;
                    padding: 0;
                }
                .paragraph + .paragraph {
                    margin-top: 1.5em;  /* Space between paragraphs */
                }
                .title {
                    font-weight: bold;
                    font-size: 1.1em;
                    margin-bottom: 0.8em;
                }
            </style>
            </head>
            <body>
        '''
        
        for p in paragraphs:
            if p.strip():
                # Check if this might be a title (you can adjust these conditions)
                if len(p.split()) <= 7 or p.isupper() or p.endswith(':'):
                    html_text += f'<div class="paragraph title">{p}</div>'
                else:
                    html_text += f'<div class="paragraph">{p}</div>'
        
        html_text += '</body></html>'
        
        # Set HTML text
        self.text_edit.setHtml(html_text)
        self.statusBar().showMessage(f"Selected {len(cleaned_text)} characters")

    def clean_text(self, text):
        """Clean up the selected text and preserve paragraph structure"""
        # Split into paragraphs while preserving original structure
        paragraphs = text.split('\n\n')
        
        cleaned_paragraphs = []
        for p in paragraphs:
            if p.strip():
                # Remove multiple spaces within paragraph
                cleaned_p = ' '.join(p.split())
                # Remove soft hyphens and other special characters
                cleaned_p = cleaned_p.replace('\u00AD', '')
                cleaned_p = cleaned_p.replace('ﬁ', 'fi')
                cleaned_p = cleaned_p.replace('ﬂ', 'fl')
                cleaned_paragraphs.append(cleaned_p)
        
        # Join paragraphs with double newlines
        return '\n\n'.join(cleaned_paragraphs)

    def copy_text(self):
        """Copy selected text to clipboard"""
        text = self.text_edit.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self.statusBar().showMessage("Text copied to clipboard")

    def open_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF Files (*.pdf)"
        )
        if file_path:
            self.load_pdf(file_path)
    
    def load_pdf(self, file_path):
        try:
            self.doc = fitz.open(file_path)
            self.current_page = 0
            self.zoom_factor = 1.0
            self.update_page_label()
            self.render_page()
            self.update_buttons()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open PDF: {str(e)}")
    
    def render_page(self):
        if not self.doc:
            return
            
        self.scene.clear()
        page = self.doc[self.current_page]
        
        # Update current page in PDF view for text selection
        self.pdf_view.current_page = page
        self.pdf_view.zoom_factor = self.zoom_factor
        
        # Calculate matrix for high-quality rendering
        base_dpi = 72.0
        scale_factor = self.pdf_view.dpi / base_dpi * self.zoom_factor
        zoom_matrix = fitz.Matrix(scale_factor, scale_factor)
        
        try:
            pix = page.get_pixmap(
                matrix=zoom_matrix,
                alpha=False,
                colorspace=fitz.csRGB
            )
            
            img = QImage(pix.samples, pix.width, pix.height,
                        pix.stride, QImage.Format.Format_RGB888)
            
            pixmap = QPixmap.fromImage(img)
            
            # Add white background
            background = self.scene.addRect(
                QRectF(pixmap.rect()),
                QPen(Qt.PenStyle.NoPen),
                QBrush(Qt.GlobalColor.white)
            )
            
            self.scene.addPixmap(pixmap)
            self.scene.setSceneRect(QRectF(pixmap.rect()))
            
            if self.zoom_factor == 1.0:
                self.fit_width()
            
            self.statusBar().showMessage(f"Page {self.current_page + 1} rendered successfully")
            
        except Exception as e:
            self.statusBar().showMessage(f"Error rendering page: {str(e)}")
            
        self.update_page_label()
        self.update_buttons()

    def previous_page(self):
        if self.doc and self.current_page > 0:
            self.current_page -= 1
            self.render_page()
    
    def next_page(self):
        if self.doc and self.current_page < len(self.doc) - 1:
            self.current_page += 1
            self.render_page()
    
    def update_page_label(self):
        if self.doc:
            self.page_label.setText(f"Page: {self.current_page + 1}/{len(self.doc)}")
    
    def zoom_in_func(self):
        self.zoom_factor *= 1.2
        self.render_page()
    
    def zoom_out_func(self):
        self.zoom_factor /= 1.2
        self.render_page()

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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = PDFViewer()
    viewer.show()
    sys.exit(app.exec()) 