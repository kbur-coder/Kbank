from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

PASSWORD = 'correct-horse-battery'
FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
User = get_user_model()


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class WebAccountTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('alice', 'alice@example.com', PASSWORD, first_name='Alice', last_name='K')

    def register_data(self, **extra):
        data = {
            'username': 'newuser', 'email': 'new@example.com', 'first_name': 'New', 'last_name': 'User',
            'password1': PASSWORD, 'password2': PASSWORD,
        }
        data.update(extra)
        return data

    def test_register_signs_the_user_in(self):
        response = self.client.post(reverse('register'), self.register_data())
        self.assertRedirects(response, reverse('profile'))
        self.assertEqual(self.client.get(reverse('profile')).status_code, 200)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_register_rejects_a_weak_password(self):
        response = self.client.post(reverse('register'), self.register_data(password1='12345678', password2='12345678'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='newuser').exists())

    def test_register_requires_names_and_email(self):
        response = self.client.post(reverse('register'), self.register_data(email='', first_name=''))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='newuser').exists())

    def test_login_and_logout(self):
        response = self.client.post(reverse('login'), {'username': 'alice', 'password': PASSWORD})
        self.assertRedirects(response, reverse('profile'))
        self.assertContains(self.client.get(reverse('logout')), 'form')
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
        self.assertEqual(self.client.get(reverse('profile')).status_code, 302)

    def test_login_with_a_wrong_password(self):
        response = self.client.post(reverse('login'), {'username': 'alice', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_profile_pages_need_a_login(self):
        for name in ('profile', 'edit-profile', 'logout'):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 302)

    def test_edit_profile(self):
        self.client.login(username='alice', password=PASSWORD)
        response = self.client.post(reverse('edit-profile'), {
            'first_name': 'Alice', 'last_name': 'Karimova', 'email': 'alice@example.com',
            'phone': '+998901234567', 'address': 'Tashkent', 'date_of_birth': '', 'passport_number': '',
        })
        self.assertRedirects(response, reverse('profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, 'Karimova')
        self.assertEqual(self.user.phone, '+998901234567')

    def test_edit_profile_only_changes_my_own_row(self):
        other = User.objects.create_user('bob', 'bob@example.com', PASSWORD, first_name='Bob')
        self.client.login(username='alice', password=PASSWORD)
        self.client.post(reverse('edit-profile'), {
            'first_name': 'Hacked', 'last_name': 'X', 'email': 'x@example.com',
        })
        other.refresh_from_db()
        self.assertEqual(other.first_name, 'Bob')
