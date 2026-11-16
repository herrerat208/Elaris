import re

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

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


class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="reset@example.com",
            password="ClaveVieja123!",
        )
        self.reset_url = reverse("accounts:password_reset")

    def _reset_path_from_email(self):
        body = mail.outbox[0].body
        match = re.search(r"http://testserver(/cuenta/recuperar/\S+)", body)
        self.assertIsNotNone(match)
        return match.group(1)

    def _request_reset(self, email=None):
        return self.client.post(
            self.reset_url,
            {"email": email or self.user.email},
        )

    def test_login_page_links_to_password_reset(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertContains(response, reverse("accounts:password_reset"))
        self.assertContains(response, "¿Olvidaste tu contraseña?")

    def test_password_reset_pages_render(self):
        for url, text in (
            (self.reset_url, "Olvidé mi contraseña"),
            (reverse("accounts:password_reset_done"), "Revisá tu email"),
            (reverse("accounts:password_reset_complete"), "Contraseña actualizada"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, text)

    def test_password_reset_sends_email_with_link(self):
        response = self._request_reset("RESET@example.com")

        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["reset@example.com"])
        self.assertIn("Recuperá tu contraseña de Elaris", message.subject)
        self.assertIn("http://testserver/cuenta/recuperar/", message.body)
        self.assertIn("24 horas", message.body)

    def test_password_reset_does_not_reveal_unknown_email(self):
        response = self._request_reset("nadie@example.com")

        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_ignores_inactive_users(self):
        self.user.is_active = False
        self.user.save(update_fields=("is_active",))

        response = self._request_reset()

        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_rejects_invalid_email_format(self):
        response = self._request_reset("no-es-un-email")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_confirm_changes_password(self):
        self._request_reset()
        response = self.client.get(self._reset_path_from_email(), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Creá una contraseña nueva")

        response = self.client.post(
            response.request["PATH_INFO"],
            {
                "new_password1": "ClaveNueva123!",
                "new_password2": "ClaveNueva123!",
            },
        )

        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ClaveNueva123!"))
        self.assertFalse(self.user.check_password("ClaveVieja123!"))

        login_response = self.client.post(
            reverse("accounts:login"),
            {"username": self.user.email, "password": "ClaveNueva123!"},
        )
        self.assertRedirects(
            login_response,
            reverse("businesses:dashboard"),
            fetch_redirect_response=False,
        )

    def test_password_reset_confirm_rejects_invalid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        response = self.client.get(
            reverse(
                "accounts:password_reset_confirm",
                kwargs={"uidb64": uid, "token": "token-invalido"},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "El link no es válido")
        self.assertContains(response, reverse("accounts:password_reset"))

    def test_password_reset_confirm_rejects_weak_password(self):
        self._request_reset()
        response = self.client.get(self._reset_path_from_email(), follow=True)

        response = self.client.post(
            response.request["PATH_INFO"],
            {"new_password1": "123", "new_password2": "123"},
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ClaveVieja123!"))

    def test_password_reset_link_cannot_be_reused(self):
        self._request_reset()
        reset_path = self._reset_path_from_email()
        response = self.client.get(reset_path, follow=True)
        self.client.post(
            response.request["PATH_INFO"],
            {
                "new_password1": "ClaveNueva123!",
                "new_password2": "ClaveNueva123!",
            },
        )

        response = self.client.get(reset_path)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "El link no es válido")
