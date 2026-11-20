from django.test import TestCase
from django.urls import reverse

PROTECTED = [
    'home', 'account-list', 'account-create', 'transaction-list', 'transfer',
    'card-list', 'card-create', 'profile', 'edit-profile',
]


class LoginRequiredTests(TestCase):
    def test_anonymous_users_are_sent_to_the_login_page(self):
        for name in PROTECTED:
            with self.subTest(page=name):
                url = reverse(name)
                response = self.client.get(url)
                self.assertRedirects(response, f"{reverse('login')}?next={url}", fetch_redirect_response=False)

    def test_login_and_register_pages_are_public(self):
        for name in ('login', 'register'):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_home_page_renders_for_a_signed_in_user(self):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user('alice', password='correct-horse-battery')
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'alice')

    def test_forms_are_not_marked_safe(self):
        from pathlib import Path
        from django.conf import settings
        for path in (Path(settings.BASE_DIR) / 'templates' / 'accounts').glob('*.html'):
            self.assertNotIn('|safe', path.read_text(encoding='utf-8'), path.name)
