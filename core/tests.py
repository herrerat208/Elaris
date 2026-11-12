from django.test import TestCase
from django.urls import reverse

from accounts.models import User


class PublicPagesTests(TestCase):
    def test_landing_renders_for_anonymous_user(self):
        response = self.client.get(reverse("core:landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Elaris")
        self.assertContains(response, "Crear mi cuenta")
        self.assertContains(response, "Cómo funciona")
        self.assertContains(response, "Tu menú de servicios")

    def test_landing_redirects_authenticated_user(self):
        user = User.objects.create_user(
            email="landing@example.com",
            password="ClaveSegura123!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("core:landing"))

        self.assertRedirects(
            response,
            reverse("businesses:dashboard"),
            fetch_redirect_response=False,
        )

    def test_health_check(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
