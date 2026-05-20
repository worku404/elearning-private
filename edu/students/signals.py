from __future__ import annotations

from django.dispatch import Signal

# Emitted when canonical module study time is recorded.
# Payload:
# - user
# - module
# - seconds
# - recorded_at
module_time_tracked = Signal()

# Emitted when content progress is updated.
# Payload:
# - user
# - content
# - seconds_delta
# - completed_now
# - recorded_at
content_progress_recorded = Signal()

# Emitted when a site presence heartbeat is received.
# Payload:
# - user_id
# - recorded_at
presence_ping_recorded = Signal()

# Emitted when a course becomes completed for a user.
# Payload:
# - user
# - course
# - completed_at
course_completed = Signal()
