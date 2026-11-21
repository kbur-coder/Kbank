from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

PASSWORD = 'correct-horse-battery'
User = get_user_model()


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AccountsAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.api = APIClient()

    def register(self, **extra):
        data = {'username': 'carol', 'password': PASSWORD, 'email': 'carol@example.com'}
        data.update(extra)
        return self.api.post(reverse('api-register'), data)

    def test_register_login_and_read_profile(self):
        response = self.register(first_name='Carol', phone='+998900000000')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertNotIn('password', response.data)
        self.assertTrue(User.objects.get(username='carol').check_password(PASSWORD))

        token = self.api.post(reverse('token_obtain_pair'), {'username': 'carol', 'password': PASSWORD})
        self.assertEqual(token.status_code, 200)
        self.api.credentials(HTTP_AUTHORIZATION='Bearer ' + token.data['access'])
        me = self.api.get(reverse('api-me'))
        self.assertEqual(me.data['username'], 'carol')
        self.assertEqual(me.data['first_name'], 'Carol')

    def test_register_validates_the_password(self):
        self.assertEqual(self.register(password='123').status_code, 400)
        self.assertEqual(self.register(password='password').status_code, 400)
        self.assertFalse(User.objects.filter(username='carol').exists())

    def test_username_must_be_unique(self):
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.register().status_code, 400)

    def test_profile_can_be_updated_but_not_the_username(self):
        self.register()
        token = self.api.post(reverse('token_obtain_pair'), {'username': 'carol', 'password': PASSWORD})
        self.api.credentials(HTTP_AUTHORIZATION='Bearer ' + token.data['access'])
        response = self.api.patch(reverse('api-me'), {'address': 'Tashkent', 'username': 'root'})
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username='carol')
        self.assertEqual(user.address, 'Tashkent')
        self.assertFalse(User.objects.filter(username='root').exists())
