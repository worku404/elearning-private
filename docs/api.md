# NextGen Academy API Documentation

This document explains the courses API in `edu/courses/api/` so developers can integrate quickly and correctly. The public API currently covers courses, subjects, enrollment, and course-content retrieval; assistant, notes, chat, and learning-insights features are web-app experiences rather than API resources.

## 1. API Purpose

Your API is the programmatic interface for course discovery, enrollment, and learning content retrieval.

It is useful for:
- mobile apps
- SPA frontends (React/Vue/Angular)
- automation scripts
- integrations with external systems

Without the API, consumers would need to parse HTML pages. With the API, they can call stable JSON endpoints.

## 2. Base URL and Route Structure

- Base URL: `/api/`
- Root API route shows registered resources: `/api/`
- Registered resources:
  - `/api/token-auth/`
  - `/api/developer/token-ui/`
  - `/api/courses/`
  - `/api/subjects/`

Implementation references:
- `edu/edu/urls.py`
- `edu/courses/api/urls.py`
- `edu/courses/api/views.py`
- `edu/courses/api/serializers.py`
- `edu/courses/api/permissions.py`

## 3. Authentication and Permissions

This API supports both:
- `TokenAuthentication` (recommended for API clients)
- `BasicAuthentication` (useful for quick testing)

Token generation options:
- UI option: open `/api/developer/token-ui/` while signed in
- Terminal option: call `POST /api/token-auth/` with username/password

### Public vs protected endpoints

Public read endpoints:
- `GET /api/courses/`
- `GET /api/courses/{id}/`
- `GET /api/subjects/`
- `GET /api/subjects/{id}/`

Protected endpoints:
- `POST /api/courses/{id}/enroll/`
  - requires authenticated user via token or basic auth
- `GET /api/courses/{id}/contents/`
  - requires authenticated user via token or basic auth + enrolled in that course

Token login endpoint:
- `POST /api/token-auth/`
- accepts username/password and returns a token

Implementation references:
- `edu/courses/api/views.py`
- `edu/courses/api/permissions.py`
- `edu/courses/api/urls.py`
- `edu/courses/signals.py`
- `edu/edu/settings/base.py`
- `edu/edu/settings/local.py`
- `edu/edu/settings/prod.py`

### Token login example (curl)

```bash
curl -X POST http://127.0.0.1:8000/api/token-auth/ \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"your_username\",\"password\":\"your_password\"}"
```

Example response:

```json
{
  "token": "your_generated_token_value"
}
```

### Use token in authenticated requests

```python
import requests

token = "your_generated_token_value"

resp = requests.get(
    "http://127.0.0.1:8000/api/courses/1/contents/",
    headers={"Authorization": f"Token {token}"},
    timeout=15,
)
print(resp.status_code)
print(resp.json())
```

### Basic auth fallback example (curl)

```bash
curl -u username:password http://127.0.0.1:8000/api/courses/1/contents/
```

## 4. Pagination

Course and subject list endpoints are paginated with page-number pagination.

Defaults:
- `page_size=10`
- max `page_size=50`

Query parameters:
- `page` (page number)
- `page_size` (custom page size, up to 50)

Example:

```bash
curl "http://127.0.0.1:8000/api/courses/?page=2&page_size=20"
```

List response envelope:

```json
{
  "count": 42,
  "next": "http://127.0.0.1:8000/api/courses/?page=3&page_size=20",
  "previous": "http://127.0.0.1:8000/api/courses/?page=1&page_size=20",
  "results": []
}
```

Implementation reference:
- `edu/courses/api/pagination.py`

## 5. Data Model Shape Exposed by API

Logical hierarchy:
- Subject
  - Course
    - Module
      - Content item (`Text`, `Video`, `Image`, `File`)

The API uses serializers in:
- `edu/courses/api/serializers.py`

## 6. Endpoint Reference

### 6.1 GET `/api/subjects/`

Purpose:
- list all subjects with metadata

Auth:
- none required

Response item fields:
- `id` (int)
- `title` (string)
- `slug` (string)
- `total_courses` (int)
- `popular_courses` (array of strings)

Example response item:

```json
{
  "id": 1,
  "title": "Mathematics",
  "slug": "mathematics",
  "total_courses": 7,
  "popular_courses": [
    "Algebra Basics (3 Students)",
    "Calculus I (10 Students)"
  ]
}
```

Notes:
- `popular_courses` is currently built as strings, not structured objects.
- Current implementation orders by ascending enrolled students in code.

### 6.2 GET `/api/subjects/{id}/`

Purpose:
- retrieve one subject by ID

Auth:
- none required

Response fields:
- same shape as list item above

### 6.3 GET `/api/courses/`

Purpose:
- list available courses

Auth:
- none required

Response item fields:
- `id` (int)
- `subject` (subject ID)
- `title` (string)
- `slug` (string)
- `overview` (string)
- `created` (datetime string)
- `owner` (user ID)
- `modules` (array of module string representations)

Example response item:

```json
{
  "id": 12,
  "subject": 1,
  "title": "Linear Algebra",
  "slug": "linear-algebra",
  "overview": "Vectors, matrices, and systems.",
  "created": "2026-02-17T06:42:01.238Z",
  "owner": 2,
  "modules": [
    "1. Vectors",
    "2. Matrix Operations"
  ]
}
```

### 6.4 GET `/api/courses/{id}/`

Purpose:
- retrieve one course summary

Auth:
- none required

Response fields:
- same shape as list item above

### 6.5 POST `/api/courses/{id}/enroll/`

Purpose:
- enroll the authenticated user in the target course

Auth:
- required (`TokenAuthentication` or `BasicAuthentication`)

Body:
- no JSON body required

Success response:

```json
{
  "enrolled": true
}
```

Behavior details:
- Uses `course.students.add(request.user)`.
- Calling it multiple times is effectively idempotent for membership.

### 6.6 GET `/api/courses/{id}/contents/`

Purpose:
- retrieve full course content tree (course -> modules -> contents)

Auth and permission:
- authenticated user required
- user must be enrolled in that specific course (`IsEnrolled`)
- accepts token auth and basic auth

Response fields:
- course summary fields
- `modules` as nested objects:
  - `order`
  - `title`
  - `description`
  - `contents` (array)
    - each item has:
      - `order`
      - `item`

Important implementation detail:
- `item` is rendered HTML from model templates (not raw typed JSON).
- Rendering source is `ItemBase.render()` in `edu/courses/models.py`.

Example snippet:

```json
{
  "id": 12,
  "title": "Linear Algebra",
  "modules": [
    {
      "order": 1,
      "title": "Vectors",
      "description": "",
      "contents": [
        {
          "order": 1,
          "item": "<article class=\"c-reader__content\">...</article>"
        }
      ]
    }
  ]
}
```

### 6.7 POST `/api/token-auth/`

Purpose:
- exchange username/password for an API token

Auth:
- no prior token required

Request body:

```json
{
  "username": "your_username",
  "password": "your_password"
}
```

Success response:

```json
{
  "token": "your_generated_token_value"
}
```

Notes:
- This endpoint is provided by DRF `obtain_auth_token`.
- New users automatically receive a token on creation via signal.
- Existing users get a token the first time they call this endpoint.

### 6.8 GET `/api/developer/token-ui/`

Purpose:
- developer-facing UI page to view/copy token and rotate token

Auth:
- login required (session auth via Django login)

Capabilities:
- view current token for logged-in user
- copy token from browser UI
- rotate token (old token becomes invalid immediately)
- terminal command examples are shown on the same page

## 7. Common Integration Flows

### Flow A: Public course catalog

1. Call `GET /api/subjects/`
2. Call `GET /api/courses/` (optionally paginated)
3. Render course cards in client

### Flow B: Student enrollment and learning

1. Call `POST /api/token-auth/` with username/password.
2. Store returned token securely client-side.
3. Call `POST /api/courses/{id}/enroll/` with `Authorization: Token <token>`.
4. Call `GET /api/courses/{id}/contents/` with same auth header.
5. Render modules and content in learner UI.

### Flow C: Automation script

1. Iterate all pages in `GET /api/courses/`
2. For each course ID, call `POST /api/courses/{id}/enroll/`
3. Log successes and failures

Example script path:
- `api_examples/enroll_all.py`

## 8. Error Handling Guide

Common status codes:
- `200 OK`: successful read/enroll action
- `400 Bad Request`: malformed JSON or missing credentials fields for token endpoint
- `401 Unauthorized`: missing/invalid credentials on protected endpoint
- `403 Forbidden`: authenticated but not allowed (for example not enrolled for `contents`)
- `404 Not Found`: invalid resource ID/path
- `405 Method Not Allowed`: wrong HTTP method for endpoint

Recommended client behavior:
- handle `next` pagination link until `null`
- retry transient failures with backoff
- do not hardcode secrets in source code

## 9. Practical Commands

Apply migrations (required for `authtoken` table):

```bash
cd edu
python manage.py migrate --settings=edu.settings.local
```

Run server:

```bash
cd edu
python manage.py runserver --settings=edu.settings.local
```

Inspect API root:

```bash
curl http://127.0.0.1:8000/api/
```

Open UI token generator in browser:

```text
http://127.0.0.1:8000/api/developer/token-ui/
```

Get a token with username/password:

```bash
curl -X POST http://127.0.0.1:8000/api/token-auth/ \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"your_username\",\"password\":\"your_password\"}"
```

Use token to enroll and fetch protected content:

```bash
curl -X POST http://127.0.0.1:8000/api/courses/1/enroll/ \
  -H "Authorization: Token your_generated_token_value"

curl http://127.0.0.1:8000/api/courses/1/contents/ \
  -H "Authorization: Token your_generated_token_value"
```

Basic auth fallback:

```bash
curl -u username:password -X POST http://127.0.0.1:8000/api/courses/1/enroll/
curl -u username:password http://127.0.0.1:8000/api/courses/1/contents/
```

## 10. Notes for Future API Evolution

Potential improvements:
- consider JWT auth if you need token expiry and refresh flows
- return structured content items (type + fields) in addition to rendered HTML
- add filters/search/sort query params for courses and subjects
- add explicit OpenAPI schema generation for SDK/client generation
