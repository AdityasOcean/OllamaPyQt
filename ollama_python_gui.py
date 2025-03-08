#!/usr/bin/env python3
import sys
import os
import time
import json
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                             QHBoxLayout, QWidget, QComboBox, QTextEdit, QLabel, 
                             QMessageBox, QSplitter, QFileDialog, QProgressBar, 
                             QStatusBar, QToolBar, QAction, QDialog, QLineEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QFont, QTextCursor

# Try to import ollama - provide helpful error if not installed
# Try to import necessary libraries
required_packages = ["ollama", "requests"]
missing_packages = []

for package in required_packages:
    try:
        __import__(package)
    except ImportError:
        missing_packages.append(package)

if missing_packages:
    print(f"Missing required packages: {', '.join(missing_packages)}. Installing...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
        print("Packages installed successfully!")
        # Now import them
        import ollama
        import requests
    except Exception as e:
        print(f"Failed to install packages: {e}")
        print(f"Please install manually with: pip install {' '.join(missing_packages)}")
        sys.exit(1)
else:
    import ollama
    import requests

class StreamingOutputThread(QThread):
    """Thread to handle streaming responses from Ollama"""
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    
    def __init__(self, model, prompt):
        super().__init__()
        self.model = model
        self.prompt = prompt
        self.running = True
        
    def run(self):
        try:
            full_response = ""
            
            # Stream the response
            for response in ollama.generate(model=self.model, prompt=self.prompt, stream=True):
                if not self.running:
                    break
                    
                if 'response' in response:
                    chunk = response['response']
                    full_response += chunk
                    self.update_signal.emit(chunk)
                    
            self.finished_signal.emit()
            
        except Exception as e:
            self.error_signal.emit(str(e))

class ModelLoader(QThread):
    """Thread to load models from Ollama"""
    models_loaded = pyqtSignal(list)
    error_signal = pyqtSignal(str)
    
    def run(self):
        try:
            # First try the command line approach which is most reliable
            import subprocess
            import re
            
            try:
                # Use subprocess to directly call the ollama CLI command
                result = subprocess.check_output(["ollama", "list"], text=True)
                
                # Parse the output which looks like:
                # NAME                    ID              SIZE      MODIFIED
                # model1:latest           abc123def456    1.2 GB    4 minutes ago
                # model2:latest           def456abc123    3.4 GB    2 days ago
                
                model_names = []
                lines = result.strip().split('\n')
                
                # Skip header line
                if len(lines) > 1:
                    for line in lines[1:]:
                        if line.strip():
                            # Get the model name (first column)
                            model_name = line.strip().split()[0]
                            model_names.append(model_name)
                
                if model_names:
                    self.models_loaded.emit(model_names)
                    return
            except (subprocess.SubprocessError, FileNotFoundError) as e:
                # If CLI approach fails, fall back to API
                pass
                
            # API approach as fallback
            try:
                # Method 1: Try using the ollama Python API
                result = ollama.list()
                model_names = []
                
                # Handle different possible return formats
                if isinstance(result, dict) and 'models' in result:
                    # Newer API format
                    for model in result['models']:
                        if isinstance(model, dict) and 'name' in model:
                            model_names.append(model['name'])
                elif isinstance(result, list):
                    # Direct list return
                    for model in result:
                        if isinstance(model, dict) and 'name' in model:
                            model_names.append(model['name'])
                        elif isinstance(model, str):
                            model_names.append(model)
                
                if model_names:
                    self.models_loaded.emit(model_names)
                    return
            except Exception as api_err:
                # Try one more approach
                pass
            
            # Method 3: Use requests to directly query the Ollama API
            try:
                import requests
                response = requests.get('http://localhost:11434/api/tags')
                data = response.json()
                
                model_names = []
                if 'models' in data:
                    for model in data['models']:
                        if 'name' in model:
                            model_names.append(model['name'])
                
                self.models_loaded.emit(model_names)
            except Exception as req_err:
                # If all methods fail, raise the original error
                self.error_signal.emit("Failed to retrieve models. Error: " + str(req_err))
        except Exception as e:
            self.error_signal.emit(str(e))

class PullModelDialog(QDialog):
    """Dialog for pulling new models"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pull New Model")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("Enter model name (e.g., llama2, mistral, tinyllama)")
        layout.addWidget(QLabel("Model Name:"))
        layout.addWidget(self.model_input)
        
        self.status_label = QLabel("Models examples: llama2, mistral, codellama, gemma:2b")
        layout.addWidget(self.status_label)
        
        button_layout = QHBoxLayout()
        self.pull_button = QPushButton("Pull Model")
        self.pull_button.clicked.connect(self.pull_model)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.pull_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        self.setLayout(layout)
        
    def pull_model(self):
        model_name = self.model_input.text().strip()
        if not model_name:
            QMessageBox.warning(self, "Warning", "Please enter a model name")
            return
            
        self.pull_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # Indeterminate progress
        self.status_label.setText(f"Pulling model {model_name}. This may take a while...")
        
        # Pull the model in a separate thread
        self.pull_thread = PullModelThread(model_name)
        self.pull_thread.progress_update.connect(self.update_progress)
        self.pull_thread.finished_signal.connect(self.pull_complete)
        self.pull_thread.error_signal.connect(self.pull_error)
        self.pull_thread.start()
    
    def update_progress(self, text):
        self.status_label.setText(text)
    
    def pull_complete(self):
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.status_label.setText("Model downloaded successfully!")
        self.pull_button.setEnabled(True)
        self.cancel_button.setEnabled(True)
        self.accept()  # Close dialog on success
    
    def pull_error(self, error):
        self.progress.setVisible(False)
        self.status_label.setText(f"Error: {error}")
        self.pull_button.setEnabled(True)
        self.cancel_button.setEnabled(True)

class PullModelThread(QThread):
    """Thread to pull models from Ollama"""
    progress_update = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    
    def __init__(self, model_name):
        super().__init__()
        self.model_name = model_name
        
    def run(self):
        try:
            # Start the pull operation
            self.progress_update.emit(f"Downloading {self.model_name}...")
            ollama.pull(self.model_name)
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))

class OllamaGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ollama AI Interface")
        self.setGeometry(100, 100, 1000, 800)
        self.stream_thread = None
        self.setup_ui()
        
        # Show instruction in the output area on startup
        self.output_text_edit.setPlainText(
            "Welcome to Ollama GUI!\n\n"
            "To get started:\n"
            "1. Click the '🚀 Initialize' button to connect to Ollama and load your models\n"
            "2. If you don't have any models yet, use the '⬇️ Pull New Model' button\n"
            "3. Enter your prompt in the text area above\n"
            "4. Click 'Generate' to run the model\n\n"
            "Make sure the Ollama service is running in the background with 'ollama serve'"
        )

    def setup_ui(self):
        # Create a central widget and main layout
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        
        # Create a toolbar
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setIconSize(QSize(24, 24))
        
        # Add actions to toolbar
        initialize_action = QAction("🚀 Initialize", self)
        initialize_action.triggered.connect(self.initialize_models)
        self.toolbar.addAction(initialize_action)
        
        refresh_action = QAction("🔄 Refresh Models", self)
        refresh_action.triggered.connect(self.load_models)
        self.toolbar.addAction(refresh_action)
        
        pull_action = QAction("⬇️ Pull New Model", self)
        pull_action.triggered.connect(self.show_pull_dialog)
        self.toolbar.addAction(pull_action)
        
        clear_action = QAction("🧹 Clear", self)
        clear_action.triggered.connect(self.clear_content)
        self.toolbar.addAction(clear_action)
        
        # Add About button at the end
        self.toolbar.addSeparator()
        about_action = QAction("ℹ️ About", self)
        about_action.triggered.connect(self.show_about_dialog)
        self.toolbar.addAction(about_action)
        
        self.addToolBar(self.toolbar)
        
        # Model selection area
        model_selection_layout = QHBoxLayout()
        
        model_label = QLabel("Select Model:")
        model_label.setMinimumWidth(100)
        
        self.model_combobox = QComboBox()
        self.model_combobox.setMinimumWidth(200)
        
        self.run_button = QPushButton("Generate")
        self.run_button.setMinimumWidth(120)
        self.run_button.clicked.connect(self.run_ollama)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.setMinimumWidth(80)
        self.stop_button.clicked.connect(self.stop_generation)
        self.stop_button.setEnabled(False)
        
        model_selection_layout.addWidget(model_label)
        model_selection_layout.addWidget(self.model_combobox, 1)
        model_selection_layout.addWidget(self.run_button)
        model_selection_layout.addWidget(self.stop_button)
        
        main_layout.addLayout(model_selection_layout)
        
        # Create a splitter for resizable input/output areas
        splitter = QSplitter(Qt.Vertical)
        
        # Input area
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        
        input_label = QLabel("Enter your prompt:")
        input_label.setFont(QFont("Arial", 10, QFont.Bold))
        
        self.input_text_edit = QTextEdit()
        self.input_text_edit.setPlaceholderText("Enter your prompt here...")
        self.input_text_edit.setMinimumHeight(100)
        self.input_text_edit.setFont(QFont("Monospace", 10))
        
        input_layout.addWidget(input_label)
        input_layout.addWidget(self.input_text_edit)
        
        # Output area
        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        
        output_label = QLabel("Generated Output:")
        output_label.setFont(QFont("Arial", 10, QFont.Bold))
        
        self.output_text_edit = QTextEdit()
        self.output_text_edit.setReadOnly(True)
        self.output_text_edit.setPlaceholderText("Generated text will appear here...")
        self.output_text_edit.setFont(QFont("Monospace", 10))
        
        output_layout.addWidget(output_label)
        output_layout.addWidget(self.output_text_edit)
        
        # Add widgets to splitter
        splitter.addWidget(input_widget)
        splitter.addWidget(output_widget)
        splitter.setSizes([200, 600])  # Set initial sizes
        
        main_layout.addWidget(splitter)
        
        # Buttons for saving content
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Save Output")
        self.save_button.clicked.connect(self.save_content)
        
        self.copy_button = QPushButton("Copy to Clipboard")
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.copy_button)
        
        main_layout.addLayout(button_layout)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Progress bar in status bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setMaximumHeight(16)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Set the central widget
        self.setCentralWidget(central_widget)

    def initialize_models(self):
        """Initialize connection with Ollama and populate models"""
        # Add a big initialize button in the center if no models
        if self.model_combobox.count() == 0:
            # First, make sure Ollama service is running by testing a basic command
            self.status_bar.showMessage("Initializing Ollama connection...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
            
            # Try to ping Ollama in a separate thread
            self.ping_thread = QThread()
            self.ping_thread.run = self._ping_ollama
            self.ping_thread.start()
        else:
            # If models are already loaded, just refresh
            self.load_models()
    
    def _ping_ollama(self):
        """Test connection to Ollama"""
        try:
            # First try using command line
            import subprocess
            try:
                subprocess.check_output(["ollama", "list"], text=True)
                # If successful, load models from the main thread
                self.load_models()
                return
            except (subprocess.SubprocessError, FileNotFoundError):
                # If CLI approach fails, try the API
                pass
                
            # Try direct API connection next
            try:
                response = requests.get('http://localhost:11434/api/tags', timeout=5)
                if response.status_code == 200:
                    # If successful, load models from the main thread
                    self.load_models()
                    return
            except:
                # If that fails, try the Python API
                pass
                
            # Last resort - try the Python API
            ollama.list()
            # If we got here without exception, load models
            self.load_models()
            
        except Exception as e:
            # If Ollama is not running, show a helpful error
            error_msg = str(e)
            if "connection refused" in error_msg.lower():
                QMessageBox.critical(
                    self, 
                    "Ollama Not Running", 
                    "Could not connect to Ollama. Please make sure the Ollama service is running.\n\n"
                    "Start it by opening a terminal and running:\n"
                    "ollama serve"
                )
            else:
                QMessageBox.critical(self, "Ollama Error", f"Error connecting to Ollama: {e}")
            
            self.status_bar.showMessage("Failed to connect to Ollama", 5000)
            self.progress_bar.setVisible(False)
            
    def load_models(self):
        """Load available models from Ollama"""
        self.status_bar.showMessage("Loading models...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        self.model_loader = ModelLoader()
        self.model_loader.models_loaded.connect(self.update_model_list)
        self.model_loader.error_signal.connect(self.show_error)
        self.model_loader.start()

    def update_model_list(self, models):
        """Update the model combobox with available models"""
        self.model_combobox.clear()
        if models:
            self.model_combobox.addItems(models)
            self.status_bar.showMessage(f"Loaded {len(models)} models", 3000)
        else:
            self.status_bar.showMessage("No models found. Use 'Pull New Model' to download one.", 5000)
            # Show a helpful message in the main area
            self.output_text_edit.setPlainText(
                "No Ollama models found.\n\n"
                "To get started:\n"
                "1. Click the '⬇️ Pull New Model' button\n"
                "2. Enter a model name like 'llama2' or 'mistral'\n"
                "3. Wait for the download to complete\n\n"
                "Popular models: llama2, mistral, gemma:2b, tinyllama, phi"
            )
            
        self.progress_bar.setVisible(False)

    def run_ollama(self):
        """Run the selected Ollama model with the input text"""
        selected_model = self.model_combobox.currentText()
        user_input = self.input_text_edit.toPlainText().strip()
        
        if not selected_model:
            QMessageBox.warning(self, "Warning", "Please select a model first. If no models are available, pull one using the 'Pull New Model' button.")
            return
            
        if not user_input:
            QMessageBox.warning(self, "Warning", "Please enter a prompt.")
            return
        
        # Update UI state
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.output_text_edit.clear()
        self.status_bar.showMessage(f"Running {selected_model}...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        # Start streaming thread
        self.stream_thread = StreamingOutputThread(selected_model, user_input)
        self.stream_thread.update_signal.connect(self.update_output)
        self.stream_thread.finished_signal.connect(self.generation_finished)
        self.stream_thread.error_signal.connect(self.show_error)
        self.stream_thread.start()

    def update_output(self, text):
        """Update the output text edit with streamed response"""
        cursor = self.output_text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.output_text_edit.setTextCursor(cursor)
        self.output_text_edit.ensureCursorVisible()

    def generation_finished(self):
        """Handle completion of text generation"""
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_bar.showMessage("Generation complete", 3000)
        self.progress_bar.setVisible(False)

    def stop_generation(self):
        """Stop the current generation"""
        if self.stream_thread and self.stream_thread.isRunning():
            self.stream_thread.running = False
            self.status_bar.showMessage("Generation stopped", 3000)
            self.run_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.progress_bar.setVisible(False)

    def show_error(self, error_message):
        """Display error message"""
        QMessageBox.critical(self, "Error", error_message)
        self.status_bar.showMessage(f"Error: {error_message}", 5000)
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setVisible(False)

    def save_content(self):
        """Save output content to a file"""
        content = self.output_text_edit.toPlainText()
        if not content:
            QMessageBox.warning(self, "Warning", "No content to save.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Output", os.path.expanduser("~/ollama_output.txt"), 
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(content)
                self.status_bar.showMessage(f"Content saved to {file_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save content: {e}")

    def copy_to_clipboard(self):
        """Copy output content to clipboard"""
        content = self.output_text_edit.toPlainText()
        if not content:
            QMessageBox.warning(self, "Warning", "No content to copy.")
            return
            
        clipboard = QApplication.clipboard()
        clipboard.setText(content)
        self.status_bar.showMessage("Content copied to clipboard", 3000)

    def clear_content(self):
        """Clear input and output text areas"""
        self.input_text_edit.clear()
        self.output_text_edit.clear()
        self.status_bar.showMessage("Content cleared", 2000)

    def show_pull_dialog(self):
        """Show dialog to pull a new model"""
        dialog = PullModelDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # Refresh model list after successful pull
            self.load_models()
            
    def show_about_dialog(self):
        """Show the About dialog with license and credits"""
        about_text = """
<h2>Ollama GUI</h2>
<p>Version 1.0</p>
<p>A PyQt5-based graphical user interface for interacting with Ollama AI models.</p>

<h3>MIT License</h3>
<p>Copyright (c) 2025</p>

<p>Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:</p>

<p>The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.</p>

<p>THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.</p>

<h3>Credits</h3>
<ul>
<li>Created by Arun K Eswara, eswara.arun@gmail.com
</ul>
"""
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle("About Ollama GUI")
        about_dialog.setMinimumWidth(550)
        about_dialog.setMinimumHeight(500)
        
        layout = QVBoxLayout()
        
        about_text_browser = QTextEdit()
        about_text_browser.setReadOnly(True)
        about_text_browser.setHtml(about_text)
        layout.addWidget(about_text_browser)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(about_dialog.accept)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)
        
        about_dialog.setLayout(layout)
        about_dialog.exec_()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Use Fusion style for a consistent look across platforms
    window = OllamaGUI()
    window.show()
    sys.exit(app.exec_())
