from django.test import TestCase
from django.urls import reverse

from .models import User


class UserManagerTests(TestCase):
    def test_create_user_normalizes_email(self):
        user = User.objects.create_user(
            email="  Profesional@Example.COM ",
            password="ClaveSegura123!",
        )

        self.assertEqual(user.email, "profesional@example.com")
        self.assertTrue(user.check_password("ClaveSegura123!"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser_sets_flags(self):
        user = User.objects.create_superuser(
            email="admin@example.com",
            password="ClaveSegura123!",
        )

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)


class AuthViewTests(TestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ingresar a Elaris")

    def test_signup_page_renders(self):
        response = self.client.get(reverse("accounts:signup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Creá tu cuenta")

    def test_signup_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "email": "nueva@example.com",
                "password1": "ClaveSegura123!",
                "password2": "ClaveSegura123!",
            },
        )

        self.assertRedirects(response, reverse("businesses:onboarding"))
        user = User.objects.get(email="nueva@example.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_signup_rejects_duplicate_email_case_insensitive(self):
        User.objects.create_user(
            email="repetida@example.com",
            password="ClaveSegura123!",
        )

        response = self.client.post(
            reverse("accounts:signup"),
            {
                "email": "REPETIDA@example.com",
                "password1": "ClaveSegura123!",
                "password2": "ClaveSegura123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya existe una cuenta con este email.")
        self.assertEqual(User.objects.filter(email__iexact="repetida@example.com").count(), 1)

    def test_login_uses_email(self):
        user = User.objects.create_user(
            email="login@example.com",
            password="ClaveSegura123!",
        )

        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "login@example.com",
                "password": "ClaveSegura123!",
            },
        )

        self.assertRedirects(
            response,
            reverse("businesses:dashboard"),
            fetch_redirect_response=False,
        )
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_login_normalizes_email_case(self):
        user = User.objects.create_user(
            email="login-case@example.com",
            password="ClaveSegura123!",
        )

        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "  LOGIN-CASE@EXAMPLE.COM ",
                "password": "ClaveSegura123!",
            },
        )

        self.assertRedirects(
            response,
            reverse("businesses:dashboard"),
            fetch_redirect_response=False,
        )
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_admin_add_user_page_renders(self):
        admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="ClaveSegura123!",
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("admin:accounts_user_add"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email")

    def test_admin_can_create_user(self):
        admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="ClaveSegura123!",
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("admin:accounts_user_add"),
            {
                "email": "creada@example.com",
                "usable_password": "true",
                "password1": "ClaveSegura123!",
                "password2": "ClaveSegura123!",
                "_save": "Guardar",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="creada@example.com").exists())

    def test_admin_change_user_page_renders(self):
        admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="ClaveSegura123!",
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("admin:accounts_user_change", args=[admin_user.pk]))

        self.assertEqual(response.status_code, 200)

    def test_logout_is_post_only(self):
        user = User.objects.create_user(
            email="logout@example.com",
            password="ClaveSegura123!",
        )
        self.client.force_login(user)

        response = self.client.post(reverse("accounts:logout"))

        self.assertRedirects(response, reverse("core:landing"))
        self.assertNotIn("_auth_user_id", self.client.session)
