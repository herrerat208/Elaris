from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def ars(value):
    if value is None or value == "":
        return "—"
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return value
    if amount == amount.to_integral():
        return "$" + f"{amount:,.0f}".replace(",", ".")
    return "$" + f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
