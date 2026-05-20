# URL routing for the notes app.
from django.urls import path  # URL path helper.

from .views import NoteDetailView, NoteListCreateView  # Notes API views.

# Define app URL patterns.
urlpatterns = [
    # List and create notes.
    path("", NoteListCreateView.as_view(), name="notes_list"),
    # Retrieve, update, or delete a single note.
    path("<int:note_id>/", NoteDetailView.as_view(), name="notes_detail"),
]
