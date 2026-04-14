# 🪨 Runestone

<img src="res/runestone_logo.jpeg" alt="Runestone Logo" width="200">

A command-line tool and web application for analyzing Swedish textbook pages using OCR and Large Language Models. Transform phone photos of Swedish textbook pages into structured digital study guides with vocabulary, grammar explanations, and learning resources.

## 🎯 Features

- **🔄 Multi-Provider Support**: Choose between OpenAI (GPT-4o) or Google Gemini for LLM processing
- **📸 OCR Processing**: Extract text from Swedish textbook page images using vision-enabled LLMs
- **🎓 Grammar Analysis**: Identify and explain grammatical patterns and rules
- **🔑 Vocabulary Extraction**: Generate word banks with English translations and contextual examples
- **💾 Vocabulary Persistence**: Save vocabulary to SQLite database for long-term learning tracking
- **🔗 Resource Discovery**: Find relevant learning resources from trusted Swedish language sites
- **✨ Rich Output**: Beautiful console output with emojis and formatting
- **📝 Export Options**: Output results to console or markdown format
- **⚙️ Configurable**: Easy provider switching via environment variables or CLI options
- **🌐 Web API**: REST API for programmatic access to image processing functionality
- **🖥️ Web Interface**: Responsive web application for easy image upload and results viewing
- **🧠 Agent Memory**: Structured, user-managed memory items with API + UI support
- **📚 Grammar RAG**: Hybrid search (BM25 + Vector) over Swedish grammar cheatsheets
- **🤖 Rune Recall**: Telegram bot for daily vocabulary recall and command processing

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- Node.js 18+ and npm (for web interface development)
- API key for your chosen LLM provider:
  - **OpenAI**: API key with GPT-4o access (recommended, default)
  - **Gemini**: Google Gemini API key with vision capabilities
- Telegram Bot Token (for Rune Recall feature): Obtain from @BotFather on Telegram
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

   **For Openrouter:**
   ```bash
   export GEMINI_API_KEY="your-openrouter-api-key"
   export LLM_PROVIDER="openrouter"
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

# Use Openrouter provider
runestone process --provider openrouter /path/to/textbook_page.jpg

# Use specific OpenAI model
runestone process --provider openai --model gpt-4o-mini /path/to/textbook_page.jpg

# With verbose output
runestone process /path/to/textbook_page.jpg --verbose

# Export to markdown
runestone process /path/to/textbook_page.jpg --output-format markdown

# Specify API key directly
runestone process --provider openai --api-key YOUR_API_KEY /path/to/textbook_page.jpg

# Load vocabulary from CSV file
runestone load-vocab /path/to/vocabulary.csv

# Load vocabulary with custom database name
runestone load-vocab /path/to/vocabulary.csv --db-name my_vocab.db

# Load vocabulary skipping existence check (allow duplicates)
runestone load-vocab /path/to/vocabulary.csv --skip-existence-check
```

### Web API Usage

Runestone also provides a REST API for programmatic access:

```bash
# Start the API server
make run-backend

# Or run directly
uvicorn runestone.api.main:app --reload
```

The API will be available at `http://localhost:8010` with the following endpoints:

- `POST /api/process`: Upload an image and get analysis results
- `POST /api/vocabulary`: Save vocabulary items to the database
- `GET /api/vocabulary`: Retrieve all saved vocabulary items
- `GET /api/memory`: List memory items (filters + pagination)
- `POST /api/memory`: Create or update a memory item (upsert)
- `PUT /api/memory/{item_id}/status`: Update item status
- `POST /api/memory/{item_id}/promote`: Promote mastered items to knowledge strengths
- `DELETE /api/memory/{item_id}`: Delete a memory item
- `DELETE /api/memory?category=...`: Clear a memory category
- `GET /api/health`: Health check endpoint
- `GET /api/grammar/search`: Search grammar cheatsheets (RAG)
- `GET /api/grammar/page/{path}`: Read a specific grammar cheatsheet

API documentation is available at `http://localhost:8010/docs`.

### Web Interface Usage

Runestone also provides a responsive web interface for easy image upload and results viewing:

```bash
# Start both the backend API and frontend web interface
make run-dev

# Or start them separately
make run-backend    # Backend API server
make run-frontend   # Frontend development server
```

The web interface will be available at `http://localhost:5173` with the following features:

- **📤 File Upload**: Drag and drop or click to select Swedish textbook page images
- **⚙️ Provider Selection**: Choose between OpenAI GPT-4o or Google Gemini
- **📊 Real-time Results**: View formatted analysis results with grammar explanations and vocabulary
- **🔄 Processing Status**: Visual feedback during image processing
- **🧠 Agent Memory Modal**: View, add, edit, and delete memory items by category
- **📱 Responsive Design**: Works on desktop and mobile devices

**Quick Start:**
1. Run `make run-dev` to start both servers
2. Open `http://localhost:5173` in your browser
3. Upload a Swedish textbook page image
4. View the structured analysis results

### Rune Recall Feature

Runestone includes a Telegram bot for automated vocabulary recall and command processing:

```bash
# Start the Rune Recall Telegram Bot Worker
make run-recall

# Or run directly
uv run python recall_main.py
```

The bot will:
- Poll for incoming commands every 5 seconds
- Send vocabulary recall words at configured intervals (default: every 60 minutes)
- Process user interactions via Telegram

### Vocabulary Priority Model

Vocabulary items use a numeric `priority_learn` scale:

- `0` = highest recall priority
- `9` = lowest priority (default for normal/manual saves)

Daily recall selection is deterministic and ordered by:

1. `priority_learn` ascending
2. `updated_at` ascending (oldest first)
3. `id` ascending

Cooldown and exclusion filters are applied before this ordering.

Agent-driven saves (`prioritize_words_for_learning` / WordKeeper) use `priority--` behavior:

- Existing/restored words: `priority_learn = max(priority_learn - 1, 0)`
- Brand-new agent-created words: start at `4`

Telegram `/postpone` lowers urgency:

- Removes the word from today’s selection
- Persists `priority_learn = min(priority_learn + 1, 9)`
- Refills the daily gap using the same deterministic ordering

**Prerequisites:**
- Set `TELEGRAM_BOT_TOKEN` environment variable with your bot token from @BotFather
- Ensure vocabulary data is available in the database

**Configuration:**
- `RECALL_INTERVAL_MINUTES`: Interval between recall messages (default: 60)

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
┌─────────────┬───────────────────────────────────────────────────┬───────────────────────────────────────────────────┐
│   Svenska   │                     English                      │                Example Phrase                 │
├─────────────┼───────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
│ hej         │ hello                                            │ Hej, jag heter Anna.                         │
│ jag heter   │ my name is                                       │ Jag heter Anna.                               │
│ vad         │ what                                             │ Vad heter du?                                 │
│ kommer från │ come from                                        │ Jag kommer från Sverige.                      │
└─────────────┴───────────────────────────────────────────────────┴───────────────────────────────────────────────────┘

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

### UV Cache Location

`make` exports `UV_CACHE_DIR=$(CURDIR)/.uv-cache` so every `uv` command run through project targets uses a repository-local cache instead of `~/.cache/uv`. This keeps cache state local to the workspace and avoids home-directory cache permission issues in sandboxed/dev environments.

Override it for a single run when needed:

```bash
UV_CACHE_DIR=/custom/path make lint-check
```

### Available Make Commands

```bash
# Setup & Installation
make help              # Show all available commands
make setup             # Set up development environment with pre-commit hooks
make install           # Install production dependencies only
make install-dev       # Install all dependencies (production + development)
make install-backend   # Install backend dependencies
make install-frontend  # Install frontend dependencies
make install-all       # Install all dependencies concurrently

# Code Quality
make lint              # Run all linting and formatting (with fixes)
make lint-check        # Run linting checks only (no fixes)
make backend-lint      # Run backend linting and formatting
make frontend-lint     # Run frontend linting

# Testing
make test              # Run all test suites
make test-coverage     # Run tests with coverage report
make backend-test      # Run backend tests only
make frontend-test     # Run frontend tests only

# Running Applications
make run IMAGE_PATH=/path/to/image.jpg GEMINI_API_KEY=your_key  # Run CLI application
make run-backend       # Start FastAPI backend server
make run-frontend      # Start frontend development server
make run-dev           # Start both backend and frontend concurrently
make run-recall        # Start the Rune Recall Telegram Bot Worker
make migrate-memory    # Migrate legacy user memory to memory_items (use ARGS=...)
make test-grammar-search QUERY="comparison" # Test grammar RAG search

# Development Workflows
make dev-test          # Quick development test (install-dev + lint-check + test)
make dev-full          # Full development check (install-dev + lint + test-coverage)

# CI/CD
make ci-lint           # CI linting pipeline
make ci-test           # CI testing pipeline

# Utilities
make clean             # Clean up temporary files and caches
make info              # Show environment information
```

## 🐳 Docker

### Quick Start with Docker

```bash
# Start all services (automatically handles permissions)
make docker-up

# Stop all services
make docker-down

# Rebuild containers
make docker-build
```

### Updating Code in Containers

To update the code running in Docker containers after making changes:

```bash
# Rebuild the images with updated code
docker compose build --no-cache

# Or if containers are already running, restart them
docker compose restart
```

This will rebuild the backend and frontend images with your latest code changes and restart the containers.

### Postgres Resource Profile

The Compose deployment uses a low-resource Postgres and application pool profile to reduce idle memory/connection pressure while preserving burst capacity for parallel backend database work.

See [Postgres Container Tuning](docs/postgres-container-tuning.md) for the current defaults, connection-budget guidance, and the startup-readiness rationale.

### Database Permissions (SQLite)

The Docker setup automatically handles SQLite database permissions to prevent "attempt to write a readonly database" errors:

- **Database in State Directory**: The SQLite database is stored in the `state/` directory (`sqlite:///./state/runestone.db`)
- **Automatic Permissions**: The `init-state.sh` script ensures the state directory has proper permissions (`777`) for container access
- **No Manual Configuration**: Works across all development machines without user ID mapping

**Technical Details:**
- Database file: `./state/runestone.db` (inherits directory permissions)
- State directory permissions: `drwxrwxrwx` (777) - allows container write access
- The `init-state.sh` script automatically sets permissions during `make docker-up`

This clean solution eliminates the need for complex user ID mapping while maintaining security and portability.

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
├── db/                 # Database layer
│   ├── __init__.py
│   ├── database.py     # SQLAlchemy engine and session management
│   ├── models.py       # Database table models
│   ├── memory_item_repository.py # Memory item data access
│   └── vocabulary_repository.py  # Vocabulary data access
├── api/                # REST API layer
│   ├── __init__.py
│   ├── main.py         # FastAPI application setup
│   ├── endpoints.py    # OCR + analysis endpoints
│   ├── memory_endpoints.py # Memory item endpoints
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
├── test_vocabulary.py # Vocabulary database tests
└── test_integration.py # Integration tests
```

### Tool DB access under concurrent LangGraph execution

LangGraph tools may execute concurrently. To keep DB operations safe, use async context-manager DI providers for tools.

- Pattern and Implementation: [`tool-db-di.md`](docs/tool-db-di.md:1)


### Agent Swarm (Coordinator + Specialists)

Design docs:

- Contracts + orchestration flow: [`agent-swarm-architecture.md`](docs/agent-swarm-architecture.md:1)
- Implementation milestones: [`agent-swarm-plan.md`](docs/agent-swarm-plan.md:1)
- Documentation naming convention: [`docs/README.md`](docs/README.md:1)

## 📋 Requirements

- **Python**: 3.13+
- **Database**: SQLite (built-in) or PostgreSQL/MySQL (optional)
- **API Key**: Choose one:
  - OpenAI API key with GPT-4o access (recommended)
  - Google Gemini API key with vision capabilities
- **Image Formats**: `.jpg`, `.png`, `.gif`, `.bmp`, `.webp`
- **Internet**: Required for LLM processing and resource discovery

## ⚙️ Configuration

### Environment Variables

**Provider Selection:**
- `LLM_PROVIDER`: Choose your LLM provider (`openai` or `openrouter`, default: `openai`)

**OpenAI Configuration:**
- `OPENAI_API_KEY`: Your OpenAI API key (required for OpenAI provider)
- `OPENAI_MODEL`: Model to use (default: `gpt-4o-mini`)

**Gemini Configuration:**
- `GEMINI_API_KEY`: Your Google Gemini API key (required for Gemini provider)

**Voice Configuration:**
- `VOICE_TRANSCRIPTION_PROVIDER`: Voice transcription provider (`openai` or `elevenlabs`, default: `openai`)
- `VOICE_TRANSCRIPTION_MODEL`: Transcription model name (default: `whisper-1`)
- `VOICE_ENHANCEMENT_MODEL`: Post-transcription cleanup model (default: `gpt-4o-mini`)
- `TTS_PROVIDER`: Text-to-speech provider (`openai` or `elevenlabs`, default: `openai`)
- `TTS_MODEL`: OpenAI text-to-speech model (default: `gpt-4o-mini-tts`)
- `TTS_VOICE`: OpenAI voice name (default: `onyx`)

**ElevenLabs Voice Configuration:**
- `ELEVENLABS_API_KEY`: ElevenLabs API key (required when a voice provider is `elevenlabs`)
- `ELEVENLABS_TTS_MODEL`: ElevenLabs TTS model name (default: `eleven_multilingual_v2`)
- `ELEVENLABS_TTS_VOICE_ID`: ElevenLabs voice ID
- `ELEVENLABS_TTS_OUTPUT_FORMAT`: Output format (default: `mp3_44100_128`)
- `ELEVENLABS_TTS_STABILITY`: Voice stability tuning (default: `0.5`)
- `ELEVENLABS_TTS_SIMILARITY_BOOST`: Similarity boost tuning (default: `0.75`)
- `ELEVENLABS_TTS_STYLE`: Style tuning (default: `0.0`)
- `ELEVENLABS_TTS_USE_SPEAKER_BOOST`: Enable speaker boost (`true` or `false`, default: `true`)

**Database Configuration:**
- `DATABASE_URL`: Database connection URL (default: `sqlite:///./state/runestone.db`)
- `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`: Application connection pool sizing for Postgres deployments.
- `STARTUP_DB_CHECK`: Enable or disable the application startup table check. Compose disables this because migrations run before backend startup.
- `POSTGRES_MAX_CONNECTIONS`, `POSTGRES_SHARED_BUFFERS`, `POSTGRES_EFFECTIVE_CACHE_SIZE`: Postgres container resource settings. See [Postgres Container Tuning](docs/postgres-container-tuning.md).

**General Settings:**
- `VERBOSE`: Enable verbose logging (`true` or `false`, default: `false`)

**Telegram Configuration:**
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token from @BotFather (required for Rune Recall)
- `RECALL_INTERVAL_MINUTES`: Interval between recall messages in minutes (default: 60)
- `TELEGRAM_OFFSET_FILENAME`: Filename for storing Telegram update offset (default: offset.txt)

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

# Voice settings
VOICE_TRANSCRIPTION_PROVIDER=openai
VOICE_TRANSCRIPTION_MODEL=whisper-1
TTS_PROVIDER=openai
TTS_MODEL=gpt-4o-mini-tts
TTS_VOICE=onyx

# ElevenLabs settings (if using ElevenLabs for voice)
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_TTS_MODEL=eleven_multilingual_v2
ELEVENLABS_TTS_VOICE_ID=your_elevenlabs_voice_id_here

# Database settings
DATABASE_URL=sqlite:///./state/runestone.db

# Telegram settings (for Rune Recall)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
RECALL_INTERVAL_MINUTES=60

# General settings
VERBOSE=false
```
### Frontend Configuration

For the web interface, create a frontend environment file:
```bash
cp frontend/.env.example frontend/.env
```

The frontend `.env` file contains:
```env
# Backend API Configuration
# The URL where the Runestone backend API is running
VITE_API_BASE_URL=http://localhost:8010
```

**Note**: The frontend runs from the `frontend/` directory, so it requires its own `.env` file to access environment variables properly. This ensures the web interface can communicate with the backend API.


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


**Happy Swedish learning!** 🇸🇪✨
