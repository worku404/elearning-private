from .motto import get_daily_motto


def daily_motto(request):
    if not request.user.is_authenticated:
        return {}
    return {"daily_motto": get_daily_motto()}
