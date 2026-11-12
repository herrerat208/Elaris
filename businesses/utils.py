from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import Business


def get_business_for(user):
    return Business.objects.filter(owner=user).first()


def business_required(view_func):
    """Require a logged-in professional with an existing business."""

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        business = get_business_for(request.user)
        if business is None:
            return redirect("businesses:onboarding")
        request.business = business
        return view_func(request, *args, **kwargs)

    return wrapper
