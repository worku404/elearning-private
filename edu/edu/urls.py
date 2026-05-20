"""
URL configuration for edu project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from courses.views import SearchResultsView, front_door
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(redirect_authenticated_user=True),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
    path("course/", include("courses.urls")),
    path("", front_door, name="home"),
    path("search/", SearchResultsView.as_view(), name="global_search"),
    path("students/", include("students.urls")),
    path("__debug__/", include("debug_toolbar.urls")),
    path("assistant/", include("assistant.urls", namespace="assistant")),
    path("api/", include("courses.api.urls", namespace="api")),
    path("chat/", include("chat.urls", namespace="chat")),
    # Notes API routes (list/create/detail/update/delete).
    path("notes/", include("notes.urls")),
    path("account/", include("account.urls")),
    path(
        "insights/",
        include(
            ("learning_insights.urls", "learning_insights"),
            namespace="learning_insights",
        ),
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
