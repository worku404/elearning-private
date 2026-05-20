from django.urls import path, include
from rest_framework import routers
from rest_framework.authtoken.views import obtain_auth_token
from . import views
from .code_execution import ExecuteCodeView

app_name = 'courses'

router = routers.DefaultRouter()
router.register('courses', views.CourseViewSet)
router.register('subjects', views.SubjectViewSet)
urlpatterns = [
    # path(
    #     'subjects/',
    #     views.SubjectListView.as_view(),
    #     name='subject_list'
    # ),
    # path(
    #     'subjects/<pk>/',
    #     views.SubjectDetailView.as_view(),
    #     name='subject_detail'
    # ),
    # path(
    #         'courses/<pk>/enroll/',
    #         views.CourseEnrollView.as_view(),
    #         name='course_enroll'
    #     ),
    path('token-auth/', obtain_auth_token, name='token_auth'),
    path('developer/token-ui/', views.TokenDashboardView.as_view(), name='token_ui'),
    path('', include(router.urls)),
    
    path("execute-code/", ExecuteCodeView.as_view(), name='execute-code'),
]
