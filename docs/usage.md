# NextGen Academy Client Usage Guide

This guide explains how to use the website after you have cloned or forked the repository and started the app locally or in production.

## Where To Open The Site

### Production

- Main app: `https://e-learning-aae0.onrender.com`
- API root: `https://e-learning-aae0.onrender.com/api/`
- Token dashboard: `https://e-learning-aae0.onrender.com/api/developer/token-ui/`

### Local development

- Main app: `http://127.0.0.1:8000/`
- API root: `http://127.0.0.1:8000/api/`
- Token dashboard: `http://127.0.0.1:8000/api/developer/token-ui/`

This guide assumes the app is started with `edu.settings.local` for local work.

## Who This Guide Is For

- Students learning through the web UI.
- Instructors publishing and managing course content.
- External developers integrating with the API.

## 1) Student Usage

### Account And Login

1. Open the site in your browser.
2. Click `Sign in`.
3. If you do not have an account, use the registration flow at `/students/register/`.
4. After login, you will land on the course area and see your daily insight card, progress snapshot, and navigation links.

### Browse And Enroll

1. Open the homepage and browse the course catalog.
2. Use the subject filter or search box to narrow down the list.
3. Open a course card.
4. Click `Enroll now`.
5. You are redirected into the student workspace for that course.

### Student Workspace

Inside `/students/course/<course_id>/` you can:

- Move between modules from the left navigation.
- Read text lessons.
- Watch embedded videos.
- View images.
- Open files and PDFs.
- Track your time spent in the course.
- Mark content and modules as complete.

### Files, PDFs, And Media

- PDF files can be previewed inline.
- You can open a PDF in a new tab if the inline preview is not practical.
- File downloads use authenticated endpoints, so the file only opens for enrolled users.
- Image and video content also uses authenticated endpoints.

### Course Chat

- Open the course chat room from the course workspace.
- Chat is real time and course-scoped.
- Message history is persisted, so you can reload older messages when needed.
- Read state and notifications are tracked per user.

### AI Assistant

- The AI assistant appears in the course workspace for authenticated users.
- Use it for course-related questions, explanations, and study help.
- The assistant keeps a short history so follow-up questions stay in context.
- Chats can be pinned so you can revisit them later.

### Notes

- The notes feature is personal to each user.
- You can create, edit, filter, and delete notes.
- Notes support tags.
- Search works against the note index, so newly imported notes may need the note rebuild command before search results are complete.

### Learning Insights

The `insights` area provides:

- Overview dashboards.
- Daily, weekly, and monthly summaries.
- Goal creation and quick actions.
- Notification center and notification preferences.
- Telegram connection flow.
- AI review and AI plan generation.

### Daily Insight Card

The home page includes a `Did You Know?` card.

- It shows a practical, source-backed insight.
- It includes a direct link to read the original article.
- The refresh button fetches a new insight without requiring a page reload.
- The feature uses a dedicated `DAILY_QUOTE_API_KEY` and is separate from the assistant API keys.

## 2) Instructor Usage

Instructor entry points are under `/course/`.

### Manage Courses

- `GET /course/mine/` lists your owned courses.
- `GET /course/create/` creates a new course.
- `GET /course/<pk>/edit/` edits a course.
- `GET /course/<pk>/delete/` deletes a course.

### Manage Modules

- `GET /course/<pk>/module/` opens the module formset.
- Add, remove, and reorder modules from there.

### Manage Content

- `GET /course/module/<module_id>/` lists content inside a module.
- Add or update these content types:
  - `text`
  - `video`
  - `image`
  - `file`

### Ordering

- Drag-and-drop ordering is available for module order.
- Drag-and-drop ordering is also available for content order within a module.

### Search And Maintenance

- Course search is backed by a denormalized search index.
- Content search and PDF extraction also use background rebuild commands.
- If you import a lot of data, rebuild the indexes so search remains accurate.

## 3) Developer API Usage

Use the API if you are building a mobile app, SPA, script, or integration.

### Base URL

- Local: `http://127.0.0.1:8000/api/`
- Production: `https://e-learning-aae0.onrender.com/api/`

### Public Endpoints

- `GET /api/subjects/`
- `GET /api/courses/`
- `GET /api/courses/{id}/`

### Authenticated Endpoints

- `POST /api/token-auth/` gets a token.
- `POST /api/courses/{id}/enroll/` enrolls the current user.
- `GET /api/courses/{id}/contents/` returns the full course content tree for enrolled users.
- `GET /api/developer/token-ui/` shows a browser UI for viewing and rotating tokens.

### Token Example

```bash
curl -X POST http://127.0.0.1:8000/api/token-auth/ \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"your_username\",\"password\":\"your_password\"}"
```

### Authenticated Content Example

```bash
curl http://127.0.0.1:8000/api/courses/1/contents/ \
  -H "Authorization: Token your_generated_token_value"
```

### API Notes

- The API currently covers courses and subjects.
- Pagination is enabled on list endpoints.
- Respect `401` and `403` responses when authentication or enrollment is missing.
- The token dashboard is the fastest way to inspect or rotate your token after login.

## 4) Troubleshooting

### Cannot access course content

- Confirm the user is enrolled in the target course.
- Confirm the session or token is valid.

### Chat does not connect

- Confirm Redis is running.
- Confirm the ASGI server is running.
- Make sure the browser is authenticated.

### Daily insight card does not refresh

- Hard refresh the page after restarting the server.
- Confirm `DAILY_QUOTE_API_KEY` is set.
- Confirm the browser is loading the updated site files.

### Notes search looks stale

- Rebuild the note search index after importing or changing note data.

### PDF preview or search does not work

- Rebuild the PDF extraction index.
- Confirm the uploaded file is still present in storage.

### Learning Insights notifications are missing

- Confirm `TELEGRAM_BOT_TOKEN` is set.
- Run the learning insights worker.
- Confirm the user has a saved notification preference.

## 5) Recommended First-Time Flow

1. Open the homepage.
2. Register and sign in.
3. Enroll in one course.
4. Open a module and read one lesson.
5. Open the course chat.
6. Try the AI assistant.
7. Add a note.
8. Open Learning Insights and create a goal.
9. Generate an API token from `/api/developer/token-ui/`.

That sequence confirms the catalog, student workspace, chat, assistant, notes, insights, and API paths are all working.
