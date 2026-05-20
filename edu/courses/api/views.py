from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.authentication import BasicAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.authtoken.models import Token

from courses.api.serializers import SubjectSerializer, CourseSerializer, CourseWithContentsSerializer
from courses.api.pagination import StandardPagination
from courses.api.permissions import IsEnrolled
from courses.search import search_courses

from courses.models import Subject, Course

from django.db.models import Count
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.urls import reverse


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    pagination_class = StandardPagination
    authentication_classes = [TokenAuthentication, BasicAuthentication]

    def get_queryset(self):
        return Course.objects.select_related("subject", "owner").prefetch_related("modules")

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        query = (request.GET.get("q") or "").strip()
        if query:
            queryset = search_courses(queryset, query)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=['get'],
        serializer_class=CourseWithContentsSerializer,
        permission_classes=[IsAuthenticated, IsEnrolled]
    )
    def contents(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)
    
    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsAuthenticated]

    )
    def enroll(self, request, *args, **kwargs):
        course = self.get_object()
        course.students.add(request.user)
        return Response({'enrolled': True})

# class SubjectListView(generics.ListAPIView):
#     queryset = Subject.objects.annotate(total_courses=Count('courses'))
#     serializer_class = SubjectSerializer
#     pagination_class = StandardPagination
    
# class SubjectDetailView(generics.RetrieveAPIView):
#     queryset = Subject.objects.annotate(total_courses=Count('courses'))
#     serializer_class = SubjectSerializer
    
    
class SubjectViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Subject.objects.annotate(total_courses=Count('courses'))
    serializer_class = SubjectSerializer
    pagination_class = StandardPagination


class TokenDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'courses/api/token_dashboard.html'

    def _get_user_token(self):
        token, _ = Token.objects.get_or_create(user=self.request.user)
        return token

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        token = self._get_user_token()
        context['api_root_url'] = self.request.build_absolute_uri(reverse('api:api-root'))
        context['token_auth_url'] = self.request.build_absolute_uri(reverse('api:token_auth'))
        context['token_ui_url'] = self.request.build_absolute_uri(reverse('api:token_ui'))
        context['courses_url'] = self.request.build_absolute_uri(reverse('api:course-list'))
        context['subjects_url'] = self.request.build_absolute_uri(reverse('api:subject-list'))
        context['sample_enroll_url'] = self.request.build_absolute_uri(
            reverse('api:course-enroll', kwargs={'pk': 'course_id'})
        )
        context['sample_contents_url'] = self.request.build_absolute_uri(
            reverse('api:course-contents', kwargs={'pk': 'course_id'})
        )
        context['token'] = token.key
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        if action == 'rotate':
            Token.objects.filter(user=request.user).delete()
            token = Token.objects.create(user=request.user)
            status_message = 'Created a new token. The previous token is now invalid.'
        else:
            token = self._get_user_token()
            status_message = 'Token is ready.'

        context = self.get_context_data()
        context['token'] = token.key
        context['status_message'] = status_message
        return self.render_to_response(context)


# class CourseEnrollView(APIView):
#     authentication_classes = [BasicAuthentication]
#     permission_classes = [IsAuthenticated]
    
#     def post(self, request, pk, format=None):
#         course = get_object_or_404(Course, pk=pk)
#         course.students.add(request.user)
#         return Response({'enrolled': True})
