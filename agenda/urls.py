from django.urls import path

from . import views

app_name = "agenda"

urlpatterns = [
    path("panel/agenda/", views.week, name="week"),
    path("panel/agenda/dia/", views.day, name="day"),
    path("panel/recordatorios/", views.reminders, name="reminders"),
    path("panel/agenda/disponibilidad/", views.availability, name="availability"),
    path(
        "panel/agenda/turnos/<int:pk>/repetir/",
        views.appointment_repeat,
        name="appointment_repeat",
    ),
    path(
        "panel/agenda/turnos/<int:pk>/recordado/",
        views.appointment_reminded,
        name="appointment_reminded",
    ),
    path(
        "panel/agenda/turnos/<int:pk>/pago/",
        views.appointment_payment,
        name="appointment_payment",
    ),
    path(
        "panel/agenda/turnos/nuevo/",
        views.appointment_create,
        name="appointment_create",
    ),
    path(
        "panel/agenda/turnos/<int:pk>/",
        views.appointment_detail,
        name="appointment_detail",
    ),
    path(
        "panel/agenda/turnos/<int:pk>/editar/",
        views.appointment_edit,
        name="appointment_edit",
    ),
    path(
        "panel/agenda/turnos/<int:pk>/completar/",
        views.appointment_complete,
        name="appointment_complete",
    ),
    path(
        "panel/agenda/turnos/<int:pk>/cancelar/",
        views.appointment_cancel,
        name="appointment_cancel",
    ),
    path(
        "panel/agenda/turnos/<int:pk>/no-asistio/",
        views.appointment_no_show,
        name="appointment_no_show",
    ),
    path(
        "panel/agenda/turnos/<int:pk>/reabrir/",
        views.appointment_reopen,
        name="appointment_reopen",
    ),
    path("panel/horarios/", views.schedule, name="schedule"),
    path(
        "panel/horarios/sugerido/",
        views.schedule_suggested,
        name="schedule_suggested",
    ),
    path(
        "panel/horarios/dias-libres/nuevo/",
        views.time_off_create,
        name="time_off_create",
    ),
    path(
        "panel/horarios/dias-libres/<int:pk>/eliminar/",
        views.time_off_delete,
        name="time_off_delete",
    ),
    path("panel/ingresos/", views.income, name="income"),
]
