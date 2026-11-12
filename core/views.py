from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render


def landing(request):
    if request.user.is_authenticated:
        return redirect("businesses:dashboard")
    return render(request, "core/landing.html")


def health(request):
    return JsonResponse({"status": "ok"})


def service_worker(request):
    content = (settings.BASE_DIR / "static" / "js" / "sw.js").read_text(encoding="utf-8")
    response = HttpResponse(content, content_type="application/javascript; charset=utf-8")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response
