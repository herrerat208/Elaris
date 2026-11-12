from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from agenda.models import Appointment
from businesses.utils import business_required

from .forms import ClientForm
from .models import Client


@business_required
def client_list(request):
    business = request.business
    show_archived = request.GET.get("archivadas") == "1"
    query = request.GET.get("q", "").strip()

    clients = (
        business.clients.filter(is_active=not show_archived)
        .annotate(appointment_count=Count("appointments"))
        .order_by("name", "id")
    )
    if query:
        clients = clients.filter(
            Q(name__icontains=query) | Q(phone__icontains=query) | Q(email__icontains=query)
        )

    paginator = Paginator(clients, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "clients/client_list.html",
        {
            "business": business,
            "page_obj": page_obj,
            "query": query,
            "show_archived": show_archived,
            "active_count": business.clients.filter(is_active=True).count(),
            "archived_count": business.clients.filter(is_active=False).count(),
        },
    )


@business_required
def client_create(request):
    business = request.business
    form = ClientForm(request.POST or None, business=business)

    if request.method == "POST" and form.is_valid():
        client = form.save(commit=False)
        client.business = business
        client.save()
        messages.success(request, "Cliente agregado.")
        return redirect("clients:detail", pk=client.pk)

    return render(
        request,
        "clients/client_form.html",
        {
            "business": business,
            "form": form,
            "client": None,
        },
    )


@business_required
def client_detail(request, pk):
    business = request.business
    client = get_object_or_404(Client, pk=pk, business=business)
    now = timezone.now()

    upcoming = (
        client.appointments.filter(
            start_at__gte=now,
            status=Appointment.STATUS_SCHEDULED,
        )
        .select_related("service")
        .order_by("start_at")
    )
    history = (
        client.appointments.filter(start_at__lt=now).select_related("service").order_by("-start_at")
    )
    completed = client.appointments.filter(
        status=Appointment.STATUS_COMPLETED,
        start_at__lt=now,
    )
    last_visit = completed.order_by("-start_at").first()
    completed_count = completed.count()
    no_show_count = client.appointments.filter(status=Appointment.STATUS_NO_SHOW).count()
    total_spent = completed.aggregate(total=Sum("price"))["total"] or 0

    return render(
        request,
        "clients/client_detail.html",
        {
            "business": business,
            "client": client,
            "upcoming": upcoming,
            "history": history,
            "last_visit": last_visit,
            "completed_count": completed_count,
            "no_show_count": no_show_count,
            "total_spent": total_spent,
        },
    )


@business_required
def client_edit(request, pk):
    business = request.business
    client = get_object_or_404(Client, pk=pk, business=business)
    form = ClientForm(request.POST or None, instance=client, business=business)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Cliente actualizado.")
        return redirect("clients:detail", pk=client.pk)

    return render(
        request,
        "clients/client_form.html",
        {
            "business": business,
            "form": form,
            "client": client,
        },
    )


@business_required
@require_POST
def client_archive(request, pk):
    client = get_object_or_404(Client, pk=pk, business=request.business)
    client.is_active = False
    client.save(update_fields=("is_active", "updated_at"))
    messages.success(request, "Cliente archivado. Su historial queda guardado.")
    return redirect("clients:detail", pk=client.pk)


@business_required
@require_POST
def client_activate(request, pk):
    client = get_object_or_404(Client, pk=pk, business=request.business)
    client.is_active = True
    client.save(update_fields=("is_active", "updated_at"))
    messages.success(request, "Cliente reactivado.")
    return redirect("clients:detail", pk=client.pk)
