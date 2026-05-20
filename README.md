# NextGen Academy E-Learning Platform

NextGen Academy is a Django-based learning management system with a public course catalog, student enrollment and progress tracking, instructor content management, real-time course chat, an AI study assistant, learning insights dashboards, personal notes, and a developer API.

The current website also includes a source-backed daily insight card on the home page. That card uses a dedicated `DAILY_QUOTE_API_KEY` and pulls from ThoughtWorks Radar, DZone Refcards, and InfoQ. It is no longer a joke or placeholder feature.

## What The Site Does

- Visitors can browse the public course catalog, filter by subject, and search courses.
- Students can register, enroll, open a course workspace, track progress, preview files, stream video, and join course chat.
- Instructors can create courses, manage modules and content blocks, and reorder content through the UI.
- Authenticated users get the AI assistant sidebar, personal notes, learning insights, and the daily insight card.
- Developers can use the token dashboard and the DRF API to integrate with course and subject data.

## Application Map

| App | Purpose | Main area |
| --- | --- | --- |
| `courses` | Public catalog, course detail pages, instructor CMS, ordering, search, daily insight card | `/`, `/course/`, `/search/` |
| `students` | Registration, enrollment, student course view, progress tracking, file/video/image access | `/students/` |
| `chat` | WebSocket course chat, message history, read-state tracking, notifications | `/chat/` |
| `assistant` | Streaming AI study assistant, chat history, pinned chats | `/assistant/` |
| `learning_insights` | Overview dashboards, daily/weekly/monthly summaries, goals, notifications, Telegram, AI review | `/insights/` |
| `notes` | Personal notes, tags, note search index, CRUD endpoints | `/notes/` |
| `api` | Public JSON API, token auth, token dashboard | `/api/` |

## Key Dependencies

The exact pinned versions live in [requirements.txt](requirements.txt). The main runtime pieces are:

- Django 6 for the main web app and templating.
- Django REST Framework for the course and subject API.
- Channels, Daphne, and Redis for WebSockets and live notifications.
- PostgreSQL via `psycopg` for the relational database.
- `requests` for outbound HTTP calls, including the daily insight source fetch and Gemini calls.
- `python-decouple` and `python-dotenv` for configuration loading.
- `pillow`, `pypdf`, `bleach`, `Markdown`, and `django-embed-video` for content rendering and media handling.
- `django-debug-toolbar` and `django-redisboard` for development and Redis inspection.
- `uwsgi` for the containerized HTTP worker path.

## Repository Layout

```text
e-learning/
|- edu/
|  |- manage.py
|  |- courses/
|  |- students/
|  |- chat/
|  |- assistant/
|  |- notes/
|  |- learning_insights/
|  |- edu/
|     |- settings/
|- docs/
|- api_examples/
|- requirements.txt
|- Dockerfile
|- docker-compose.yml
|- start.ps1
|- stop.ps1
```

## Fork Or Clone

If you are starting from GitHub, fork the repository first if you want your own copy on GitHub, then clone that fork locally.

```powershell
git clone https://github.com/<your-username>/<your-fork>.git
cd e-learning
git remote add upstream https://github.com/worku404/worku-lms.git
```

If you only need a local copy, cloning the upstream repository is enough.

## Prerequisites

- Python 3.12 or newer.
- Git.
- PostgreSQL.
- Redis.
- Docker Desktop if you want to use the container stack.

On Windows, the included `start.ps1` and `stop.ps1` scripts are the easiest way to run the local stack because they start Django, Redis, and the learning insights worker for you.

## Install Dependencies

Create a virtual environment, activate it, and install the pinned packages from `requirements.txt`.

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Settings And Environment

The project has three settings entry points:

- `edu.settings` imports the shared base settings.
- `edu.settings.local` is the local development configuration.
- `edu.settings.prod` is the container/production configuration.

For local development, set `DJANGO_SETTINGS_MODULE=edu.settings.local` or pass `--settings=edu.settings.local` to Django commands. The base settings module does not define the database connection on its own, so the local settings file is the safest choice for day-to-day work.

Create `edu/.env` or a root `.env` file with values similar to these:

```env
DB_NAME=e_learning_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=127.0.0.1
POSTGRES_PORT=5432

REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0

API1_KEY=
API2_KEY=
API3_KEY=
API4_KEY=
ASSISTANT_MAX_OUTPUT_TOKENS=65536
DAILY_QUOTE_API_KEY=

TELEGRAM_BOT_TOKEN=
TELEGRAM_BOT_USERNAME=

DJANGO_SUPERUSER_USERNAME=
DJANGO_SUPERUSER_EMAIL=
DJANGO_SUPERUSER_PASSWORD=
```

## First Run

From the `edu/` directory, apply migrations, load the base subjects, and create a superuser.

```powershell
cd edu
python manage.py migrate --settings=edu.settings.local
python manage.py loaddata courses/fixtures/subjects.json
python manage.py createsuperuser --settings=edu.settings.local
```

If you prefer the environment-driven superuser helper, set the three `DJANGO_SUPERUSER_*` variables and run:

```powershell
python manage.py create_superuser --settings=edu.settings.local
```

## Run The Website

The standard local launch command is:

```powershell
python manage.py runserver --settings=edu.settings.local
```

The site is then available at `http://127.0.0.1:8000/`.

If you need the ASGI/WebSocket server directly, use Daphne:

```powershell
daphne -b 0.0.0.0 -p 8000 edu.asgi:application
```

On Windows, `start.ps1` automates the common local flow, and `stop.ps1` stops the Python and Redis processes that the launcher starts.

## Container Stack

The repository also includes `Dockerfile`, `docker-compose.yml`, `config/nginx/`, and `config/uwsgi/` for a containerized deployment stack.

That stack includes:

- PostgreSQL for persistent data.
- Redis for cache and Channels.
- uWSGI for the HTTP worker.
- Daphne for WebSocket traffic.
- Nginx as the front reverse proxy.

If you use the container stack, make sure the settings and environment variables match the container network names in your environment before you expose it publicly.

## How The Website Is Organized

### Courses

The `courses` app powers the public homepage, catalog, subject filters, search, course detail pages, instructor CRUD screens, module/content ordering, and the daily insight card.

Content types supported by the course workspace are text, image, video, and file.

The daily card now shows sourced knowledge, a direct link to the source article, and a refresh button that forces a new fetch.

### Students

The `students` app covers account registration, enrollment, the enrolled course list, the student course workspace, module completion, time tracking, file download, PDF preview/search, image rendering, and video streaming.

### Chat

The `chat` app provides a course-scoped WebSocket room with persisted messages, history pagination, unread preview bootstrap data, and read-state tracking.

### Assistant

The `assistant` app provides the streaming Gemini-powered sidebar, per-user chat history, chat pinning, and chat state management.

### Learning Insights

The `learning_insights` app provides the overview page, daily/weekly/monthly summaries, goal management, quick actions, notification center, notification preferences, Telegram connection flow, AI review generation, and AI plan application views.

### Notes

The `notes` app provides per-user note CRUD, tags, note filtering, and a searchable notes index.

## Management Commands

Useful commands in the current codebase:

- `python manage.py create_superuser --settings=edu.settings.local` - create or promote a superuser from environment variables.
- `python manage.py rebuild_course_search_index` - rebuild the denormalized search index for courses.
- `python manage.py rebuild_content_search_index` - rebuild the denormalized search index for course content.
- `python manage.py rebuild_pdf_extraction_index` - rebuild extracted PDF text for uploaded files.
- `python manage.py rebuild_note_search_index` - rebuild the denormalized search index for notes.
- `python manage.py enroll_reminder --days 7` - send reminder emails to users who have not enrolled.
- `python manage.py poll_telegram_updates` - poll Telegram `getUpdates` and link subscriptions.
- `python manage.py learning_insights_worker` - run Telegram polling plus scheduled Learning Insights notifications.

If you import new subject, course, note, or PDF data, rerun the corresponding rebuild command so search results stay current.

## Developer API

The JSON API lives under `/api/` and is documented in [docs/api.md](docs/api.md).

Main endpoints:

- `GET /api/subjects/`
- `GET /api/courses/`
- `POST /api/token-auth/`
- `POST /api/courses/{id}/enroll/`
- `GET /api/courses/{id}/contents/`
- `GET /api/developer/token-ui/`

The token dashboard is the quickest way for a signed-in user to copy or rotate their API token.

## Security And Access Control

- Course content is restricted to enrolled users.
- Instructor actions are owner-scoped server-side.
- The chat room rejects unauthenticated users and non-enrolled users.
- The assistant and notes are per-user features.
- Markdown content is sanitized before it is rendered.
- The daily insight feature uses its own `DAILY_QUOTE_API_KEY` and is isolated from the assistant key flow.

## Documentation

- [docs/usage.md](docs/usage.md) - step-by-step user guide for students, instructors, and developers.
- [docs/api.md](docs/api.md) - API endpoint reference and integration examples.
- [docs/index.md](docs/index.md) - short documentation index.

## Troubleshooting

- If the site shows stale daily insight text, hard refresh the page after restarting the server.
- If chat does not connect, confirm Redis and the ASGI server are running.
- If PDFs or extracted text do not show up, rebuild the PDF extraction index.
- If notes search is empty after importing content, rebuild the notes search index.
- If Learning Insights notifications do not appear, confirm the Telegram token and run the worker command.

## License

This project is licensed under the terms of the `LICENSE` file in this repository.
