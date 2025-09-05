# 🪨 Runestone

<img src="res/runestone_logo.jpeg" alt="Runestone Logo" width="200">

A command-line tool and web application for analyzing Swedish textbook pages using OCR and Large Language Models. Transform phone photos of Swedish textbook pages into structured digital study guides with vocabulary, grammar explanations, and learning resources.

## 🎯 Features

- **🔄 Multi-Provider Support**: Choose between OpenAI (GPT-4o) or Google Gemini for LLM processing
- **📸 OCR Processing**: Extract text from Swedish textbook page images using vision-enabled LLMs
- **🎓 Grammar Analysis**: Identify and explain grammatical patterns and rules
- **🔑 Vocabulary Extraction**: Generate word banks with English translations
- **🔗 Resource Discovery**: Find relevant learning resources from trusted Swedish language sites
- **✨ Rich Output**: Beautiful console output with emojis and formatting
- **📝 Export Options**: Output results to console or markdown format
- **⚙️ Configurable**: Easy provider switching via environment variables or CLI options
- **🌐 Web API**: REST API for programmatic access to image processing functionality
- **🖥️ Web Interface**: Planned responsive web application for easy image upload and results viewing (coming soon)

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- Node.js 18+ and npm (for web interface development)
- API key for your chosen LLM provider:
  - **OpenAI**: API key with GPT-4o access (recommended, default)
  - **Gemini**: Google Gemini API key with vision capabilities
- UV package manager (recommended) or pip

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd runestone
   ```

2. **Install dependencies:**
   ```bash
   # Using UV (recommended)
   make install

   # Or using pip
   pip install -e .
   ```

3. **Set up your API key:**

   **For OpenAI (default):**
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   ```

   **For Gemini:**
   ```bash
   export GEMINI_API_KEY="your-gemini-api-key"
   export LLM_PROVIDER="gemini"
   ```

   **Or copy and configure the environment file:**
   ```bash
   cp .env.example .env
   # Edit .env with your preferred settings
   ```

4. **Test the installation:**
   ```bash
   runestone --help
   ```

### Basic Usage

```bash
# Process a Swedish textbook page image (uses OpenAI by default)
runestone process /path/to/textbook_page.jpg

# Use Gemini provider
runestone process --provider gemini /path/to/textbook_page.jpg

# Use specific OpenAI model
runestone process --provider openai --model gpt-4o-mini /path/to/textbook_page.jpg

# With verbose output
runestone process /path/to/textbook_page.jpg --verbose

# Export to markdown
runestone process /path/to/textbook_page.jpg --output-format markdown

# Specify API key directly
runestone process --provider openai --api-key YOUR_API_KEY /path/to/textbook_page.jpg
```

### Web API Usage

Runestone also provides a REST API for programmatic access:

```bash
# Start the API server
make run-backend

# Or run directly
uvicorn runestone.api.main:app --reload
```

The API will be available at `http://localhost:8000` with the following endpoints:

- `POST /api/process`: Upload an image and get analysis results
- `GET /api/health`: Health check endpoint

API documentation is available at `http://localhost:8000/docs`.

## 📖 Example Output

When you process a Swedish textbook page, Runestone will provide:

```
🪨 Runestone - Swedish Textbook Analysis
╔════════════════════════════════════════════════════════════════╗

📖 Full Recognized Text
┌────────────────────────────────────────────────────────────────┐
│ Hej, jag heter Anna. Vad heter du?                             │
│ Jag kommer från Sverige. Varifrån kommer du?                  │
│ ...                                                            │
└────────────────────────────────────────────────────────────────┘

🎓 Grammar Focus
┌────────────────────────────────────────────────────────────────┐
│ Topic: Swedish introductions and questions                     │
│ Type: Inferred Pattern                                         │
│                                                               │
│ Explanation:                                                  │
│ This page covers basic introduction patterns in Swedish...    │
└────────────────────────────────────────────────────────────────┘

🔑 Word Bank
┌─────────────┬───────────────────────────────────────────────────┐
│   Svenska   │                     English                      │
├─────────────┼───────────────────────────────────────────────────┤
│ hej         │ hello                                            │
│ jag heter   │ my name is                                       │
│ vad         │ what                                             │
│ kommer från │ come from                                        │
└─────────────┴───────────────────────────────────────────────────┘

🔗 Extra Resources
┌────────────────────────────────────────────────────────────────┐
│ 1. Swedish Grammar Reference - Svenska.se                     │
│    🔗 https://svenska.se/tre/sprak/grammatik/                 │
│    📝 Official Swedish grammar reference and explanations     │
│                                                               │
│ 2. Swedish Introductions Guide - Clozemaster                 │
│    🔗 https://www.clozemaster.com/blog/swedish-introductions/ │
│    📝 Comprehensive guide to Swedish introductions           │
└────────────────────────────────────────────────────────────────┘

✨ Analysis complete!
```

## 🛠️ Development

### Development Setup

```bash
# Set up development environment
make setup

# Install development dependencies
make install-dev

# Install pre-commit hooks
pre-commit install
```

### Available Make Commands

```bash
make help           # Show all available commands
make install        # Install production dependencies
make install-dev    # Install development dependencies
make setup          # Full development environment setup
make lint           # Run code formatting and linting
make lint-check     # Check code formatting (no fixes)
make test           # Run test suite
make test-coverage  # Run tests with coverage report
make clean          # Clean up temporary files
make run IMAGE_PATH=/path/to/image.jpg  # Run the CLI application
make run-backend    # Start the FastAPI server
make run-dev        # Start both backend and frontend (when available)
```

### Running Tests

```bash
# Run all tests
make test

# Run tests with coverage
make test-coverage

# Run specific test file
pytest tests/test_ocr.py -v

# Run tests with verbose output
pytest tests/ -v -s
```

### Code Quality

The project uses several tools for code quality:

- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **pre-commit**: Git hooks for quality checks
- **pytest**: Testing framework with coverage

## 🏗️ Architecture

```
src/runestone/
├── cli.py              # Command-line interface
├── config.py           # Centralized configuration management
├── api/                # REST API layer
│   ├── __init__.py
│   ├── main.py         # FastAPI application setup
│   ├── endpoints.py    # API endpoints
│   └── schemas.py      # Pydantic models for API
├── core/
│   ├── processor.py    # Main workflow orchestration
│   ├── ocr.py         # OCR processing (provider-agnostic)
│   ├── analyzer.py    # Content analysis and resource discovery
│   ├── formatter.py   # Output formatting (console/markdown)
│   ├── exceptions.py  # Custom exception classes
│   └── clients/       # LLM provider implementations
│       ├── __init__.py
│       ├── base.py    # Abstract base client
│       ├── openai_client.py    # OpenAI implementation
│       ├── gemini_client.py    # Gemini implementation
│       └── factory.py # Client factory
└── __init__.py

tests/
├── test_cli.py        # CLI tests
├── test_api.py        # API tests
├── test_ocr.py        # OCR processing tests
├── test_analyzer.py   # Content analysis tests
└── test_integration.py # Integration tests
```

## 📋 Requirements

- **Python**: 3.13+
- **API Key**: Choose one:
  - OpenAI API key with GPT-4o access (recommended)
  - Google Gemini API key with vision capabilities
- **Image Formats**: `.jpg`, `.png`, `.gif`, `.bmp`, `.webp`
- **Internet**: Required for LLM processing and resource discovery

## ⚙️ Configuration

### Environment Variables

**Provider Selection:**
- `LLM_PROVIDER`: Choose your LLM provider (`openai` or `gemini`, default: `openai`)

**OpenAI Configuration:**
- `OPENAI_API_KEY`: Your OpenAI API key (required for OpenAI provider)
- `OPENAI_MODEL`: Model to use (default: `gpt-4o-mini`)

**Gemini Configuration:**
- `GEMINI_API_KEY`: Your Google Gemini API key (required for Gemini provider)

**General Settings:**
- `VERBOSE`: Enable verbose logging (`true` or `false`, default: `false`)

### Configuration File

Create a `.env` file from the example:
```bash
cp .env.example .env
```

Edit `.env` with your preferred settings:
```env
# Choose your provider
LLM_PROVIDER=openai

# OpenAI settings
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

# Gemini settings (if using Gemini)
GEMINI_API_KEY=your_gemini_api_key_here

# General settings
VERBOSE=false
```

### Supported Image Types

Runestone works best with:
- Clear photos of textbook pages
- Good lighting and minimal shadows
- Images larger than 100x100 pixels
- Standard image formats (JPG, PNG, etc.)

## 🚨 Error Handling

Runestone provides clear error messages for common issues:

- **Missing API Key**: Clear instructions on setting up authentication
- **File Not Found**: Verification that the image path exists
- **OCR Failure**: Graceful handling when text cannot be recognized
- **Network Issues**: Timeout and connection error handling

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`make test`)
5. Run linting (`make lint`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines (enforced by black and flake8)
- Write tests for new functionality
- Update documentation for user-facing changes
- Use meaningful commit messages

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Google Gemini](https://deepmind.google/technologies/gemini/) for vision and language processing
- [Rich](https://github.com/Textualize/rich) for beautiful terminal output
- [Click](https://click.palletsprojects.com/) for CLI framework
- The Swedish language learning community

## 📞 Support

If you encounter issues or have questions:

1. Check the [troubleshooting section](#🚨-error-handling)
2. Search existing [GitHub issues](https://github.com/your-repo/runestone/issues)
3. Create a new issue with:
   - Clear description of the problem
   - Steps to reproduce
   - Sample image (if applicable)
   - Error messages
   - System information

---

## 🚧 Planned Features

- **🖥️ Web Interface**: A responsive React-based frontend for easy image upload and results visualization is currently in development. This will provide a user-friendly alternative to the command-line interface.

**Happy Swedish learning!** 🇸🇪✨
