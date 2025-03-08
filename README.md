# OllamaPyQt
Graphical Front End to Ollama for Linux systems

# Ollama GUI

A desktop application for interacting with local AI models using Ollama.

## Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.7 or higher
- Ollama
- pip (Python package manager)

### System Requirements

- Operating System: Windows, macOS, or Linux
- Minimum RAM: 8GB (16GB recommended)
- Disk Space: At least 30GB for model downloads

## Installation

### 1. Install Ollama

```bash
# For macOS/Linux
curl https://ollama.ai/install.sh | sh

# For Windows
# Download and run the installer from the official Ollama website
```

### 2. Clone the Repository

```bash
git clone https://github.com/AdityasOcean/OllamaPyQt/tree/main
cd OllamaPyQt
```

### 3. Install Python Dependencies

```bash
pip install PyQt5 ollama requests
```

## Usage

### Starting the Application

```bash
python ollama_python_gui.py
```

### Using the GUI

1. Click "Initialize" to connect to Ollama
2. Use "Pull New Model" to download AI models
3. Select a model from the dropdown
4. Enter your prompt in the input area
5. Click "Generate" to interact with the AI

## Features

- Interactive AI model interaction
- Real-time text generation
- Multiple model support
- Model download and management
- Save and copy generated content
- Stop generation mid-process

## Functionality

### Model Management
- List available Ollama models
- Pull and download new models
- Select models for interaction

### Text Generation
- Streaming text output
- Customizable prompts
- Real-time generation tracking

### User Interface
- Resizable input and output areas
- Toolbar for quick actions
- Status bar with progress indicators

## Recommended Models

- llama2
- mistral
- gemma:2b
- tinyllama
- phi

## Troubleshooting

- Ensure Ollama service is running
- Check internet connection when pulling models
- Verify Python and package dependencies

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Contact

Arun K Eswara
- Email: eswara.arun@gmail.com
- Project Link: https://github.com/yourusername/ollama-gui

## Acknowledgements

- [Ollama](https://ollama.ai/) - Local AI model platform
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - Python GUI framework
- Open-source AI and development community
- ClaudeAI
