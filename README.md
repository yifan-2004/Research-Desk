# Research Desk

**One local workspace for research sources, experiment notes, and next steps.**

A local research workspace with source-linked retrieval, notes, tasks, and optional model-assisted answers. Built with Python's standard library and a small browser interface. The current interface and example research notes are in Chinese; retrieval supports English and Chinese text.

![Research Desk running in a local browser](docs/preview.png)

## Get started

Requires **Python 3.10+**. No third-party Python packages, model downloads, or pretrained weights are needed.

1. Download this repository as a ZIP and extract it.
2. On macOS, double-click `start.command`; on Windows, double-click `start.bat`.
3. In the browser, choose the button for trying example research notes, or add your own sources.

If double-clicking does not work, run this from the project directory:

```sh
python3 app.py --open
```

On Windows, you can also use `py -3 app.py --open`. The default address is `http://127.0.0.1:8765`. If the port is occupied, use `python3 app.py --port 8766 --open`. Press `Ctrl+C` in the terminal to stop the application.

This is a local browser application. The repository includes source code and launch scripts; packaged `.dmg` and `.exe` installers are not available yet.

## Features

- **Source library:** Paste paper abstracts or experiment records, keep original links, and filter by keywords.
- **Research notes:** Save your observations and questions that need verification.
- **Tasks:** Add, complete, and remove concrete next steps.
- **Source retrieval:** Match English words and Chinese bigrams, returning up to five excerpts with source IDs such as `[S1]` or note IDs such as `[N1]`.
- **Optional model-assisted answers:** Connect a Chat Completions-compatible service of your choice, with a data-transfer notice before sending.
- **Local storage:** Persist sources, notes, and tasks in SQLite and export them as JSON.

The default **offline retrieval mode** displays matching source text using rules. It does not generate AI answers. The examples are research-checking plans, with no fabricated experiment results.

## Optional: connect your model service

Model features activate only when both an endpoint and a model name are configured. API keys are read only from server-side environment variables. Remote endpoints require HTTPS; local services may use HTTP. Set `DESK_CHAT_ENDPOINT` to the **complete request URL**.

For macOS or Linux, assuming you already have a compatible local service running:

```sh
export DESK_CHAT_ENDPOINT='http://127.0.0.1:1234/v1/chat/completions'
export DESK_CHAT_MODEL='your-served-model-name'
# Set DESK_CHAT_API_KEY as well if your service requires authentication.
python3 app.py --open
```

PowerShell example:

```powershell
$env:DESK_CHAT_ENDPOINT = 'http://127.0.0.1:1234/v1/chat/completions'
$env:DESK_CHAT_MODEL = 'your-served-model-name'
py -3 app.py --open
```

`.env.example` documents the available fields; the application does not load `.env` automatically. It does not install models, create paid services, or configure API keys for you. The compatible request structure follows the [official OpenAI Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).

Each model request sends **the current question and matching source excerpts**, rather than the entire library or task list. The chat display exists only in the current page and clears on refresh; previous turns are not sent to the model. Model citations can be incorrect, so expand source cards and check the original text.

## Data and scope

Data is stored in `data/desk.sqlite3` by default, and Git ignores that directory. For a complete backup, stop the application and copy this file; restore it to the same location when needed. JSON exports support archiving and migration, but there is currently no JSON import interface.

The application listens only on `127.0.0.1`. It has no telemetry, account system, or automatic web scraping. It stores pasted text and does not parse PDFs, use vector models, execute code, or browse the web automatically. This personal research assistant prototype does not implement autonomous Agent planning or tool execution. Notes, tasks, and retrieval work without sending your sources to a model.

## Development and validation

```sh
python3 -m unittest discover -s tests -v
```

Tests cover SQLite persistence, English and Chinese retrieval, offline operation without network calls, model request stubs, exclusion of API keys from browser data, error handling, HTTP pages and APIs, and Origin, Host, and request-token checks. The model adapter has been tested with a local stub, not a paid model. The screenshot comes from an actual local browser session. The Windows launcher has not been tested on Windows.

```text
app.py          Local server, storage, retrieval, and optional model adapter
static/         Browser interface with no build step
start.command   macOS launcher
start.bat       Windows launcher
tests/          Standard-library unittest tests
```

## Related projects and license

Product inspiration: the personal knowledge library in [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) and research workflows in [GPT Researcher](https://github.com/assafelovic/gpt-researcher). This application is independently implemented; it does not copy code or interface assets from either project.

Code is available under the [MIT License](LICENSE). Papers, images, and other materials you save remain subject to their own licenses.
