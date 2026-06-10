# 🤖 Agentic Web AI - Backend

FastAPI backend for the **Agentic Web AI** browser agent. It orchestrates a web-browsing agent capable of interacting with websites via Playwright, powered by OpenRouter LLMs.

---

## 🚀 Getting Started

Follow these instructions to set up and run the backend server on your local machine.

### 1. Clone the Repository
Clone the repository and navigate into the `backend` directory:
```bash
git clone https://github.com/yashviPayal/Agentic-Web.git
cd Agentic-Web/backend
```

### 2. Environment Configuration
Copy the template environment file to `.env`:

**On Linux/macOS:**
```bash
cp .env.example .env
```

**On Windows (Command Prompt):**
```cmd
copy .env.example .env
```

**On Windows (PowerShell):**
```powershell
Copy-Item .env.example -Destination .env
```

Open the newly created `.env` file and configure the values:
- `OPENROUTER_API_KEY`: Your OpenRouter API Key (required for agent chat features).
- `OPENROUTER_MODEL`: Model to use (defaults to `google/gemini-2.5-flash-lite`).
- `PLAYWRIGHT_HEADED`: Set to `true` to watch the browser work in a GUI window, or `false` (default) for headless background operation.

---

### 3. Installation & Setup

We use **`uv`** for managing dependencies and virtual environments.

#### 1. Install `uv` (if not already installed)
- **macOS / Linux:**
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Windows (PowerShell):**
  ```powershell
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **Via pip (Alternative):**
  ```bash
  pip install uv
  ```

#### 2. Sync Dependencies
Create a virtual environment and install dependencies automatically:
```bash
uv sync
```

#### 3. Install Playwright Browsers
Download the required browser binaries:
```bash
uv run playwright install
```

---

## 🏃 Running the Application

Start the FastAPI development server with live reload:
```bash
uv run uvicorn main:app --reload --port 8000
```

Once running, the backend server will be available at `http://127.0.0.1:8000`.

---

## 📂 Project Structure

```text
backend/
├── app/
│   ├── api/          # FastAPI routes and Pydantic schemas
│   ├── agents/       # LLM orchestration and system prompts
│   ├── tools/        # Tool definitions (e.g., browse_web) and execution registry
│   ├── scraper/      # Playwright browser lifecycle, actions, parser, and screenshots
│   ├── services/     # Application services (e.g. AgentService wrapper)
│   └── utils/        # Shared utility functions
├── main.py           # Application entry point and lifespan hooks
├── pyproject.toml    # Project configuration and dependency specifications
└── README.md         # This documentation
```

---

## 🔌 API Endpoints

### 1. Health Status
Check if the API and browser manager are running.
- **Endpoint:** `GET /`
- **Response:**
  ```json
  {
    "status": "Agentic Web AI is running",
    "browser": "connected"
  }
  ```

- **Endpoint:** `GET /health`
- **Response:**
  ```json
  {
    "status": "ok"
  }
  ```

### 2. Conversational Agent Chat
Interact with the AI browser agent. The agent can automatically decide to use the `browse_web` tool when needed.
- **Endpoint:** `POST /chat/`
- **Request Body:**
  ```json
  {
    "messages": [
      {
        "role": "user",
        "content": "Go to news.ycombinator.com and summarize the top 3 stories."
      }
    ]
  }
  ```
- **Response Body:**
  ```json
  {
    "response": "Here is the summary of the top 3 stories...",
    "tool_used": "browse_web",
    "tool_result": { ... },
    "raw_url": "https://news.ycombinator.com"
  }
  ```

### 3. Direct Scraping
Browse a URL directly with Playwright, extracting text, links, or taking screenshots.
- **Endpoint:** `POST /scrape/`
- **Request Body:**
  ```json
  {
    "url": "https://example.com",
    "extract_content": true,
    "scroll_page": true,
    "take_screenshot": false,
    "max_text_length": 8000
  }
  ```

---

## 📖 Interactive Documentation
FastAPI serves interactive API documentation. Start the server and visit:
- **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
