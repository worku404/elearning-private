from .services import get_overall_progress, get_top_courses_by_time

def global_progress(request):
    user = request.user
    if not user.is_authenticated:
        return {"overall_progress": 0, "top_courses": []}

    return {
        "overall_progress": get_overall_progress(user),
        "top_courses": get_top_courses_by_time(user, limit=3),
    }
