import base64
import hashlib
import json
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth import authenticate
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from google.auth import crypt, jwt
from google.auth.exceptions import TransportError

from .google_login import FLOW_KEY
from .models import GoogleIdentity, User


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False,
    GOOGLE_OAUTH_CLIENT_ID='test-client.apps.googleusercontent.com',
    GOOGLE_OAUTH_CLIENT_SECRET='test-client-secret', GOOGLE_OAUTH_REDIRECT_URI='')
class GoogleLoginTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption())
        public = key.public_key().public_bytes(serialization.Encoding.PEM,
                                               serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        cls.signer = crypt.RSASigner.from_string(private)
        cls.certs = SimpleNamespace(status=200, data=json.dumps({'test-key': public}).encode())

    def setUp(self):
        self.worker = User.objects.create_user(username='worker', email='worker@gmail.com',
            password='worker-pass', allow_email_login=True)

    def begin(self, next_url=''):
        response = self.client.post(reverse('google-login'), {'next': next_url})
        self.assertEqual(response.status_code, 302)
        return self.client.session[FLOW_KEY]

    def signed(self, flow, **changes):
        claims = dict(iss='https://accounts.google.com', aud='test-client.apps.googleusercontent.com',
            iat=int(time.time()) - 60, exp=int(time.time()) + 300, sub='google-worker-123',
            email='worker@gmail.com', email_verified=True, nonce=flow['nonce'])
        claims.update(changes)
        return jwt.encode(self.signer, claims, key_id='test-key').decode()

    def finish(self, flow, token=None, follow=False):
        token = token or self.signed(flow)
        with patch('accounts.google_login._exchange_code', return_value=token), \
                patch('google.auth.transport.requests.Request.__call__', return_value=self.certs):
            return self.client.get(reverse('google-callback'),
                {'state': flow['state'], 'code': 'single-use-test-code'}, follow=follow)

    def test_button_is_opt_in_and_explains_pending_configuration(self):
        self.assertContains(self.client.get(reverse('login')), 'Iniciar sesión con Google')
        self.worker.allow_email_login = False
        self.worker.save()
        self.assertNotContains(self.client.get(reverse('login')), 'Iniciar sesión con Google')
        self.worker.allow_email_login = True
        self.worker.save()
        with override_settings(GOOGLE_OAUTH_CLIENT_SECRET=''):
            response = self.client.get(reverse('login'))
            self.assertContains(response, 'disabled')
            self.assertContains(response, 'El inicio con Google aún no está disponible.')
            self.assertEqual(self.client.post(reverse('google-login')).status_code, 503)

    def test_start_requires_post_and_csrf_and_uses_state_nonce_pkce(self):
        self.assertEqual(self.client.get(reverse('google-login')).status_code, 405)
        self.assertEqual(Client(enforce_csrf_checks=True).post(reverse('google-login')).status_code, 403)
        flow = self.begin('/historial/')
        response = self.client.post(reverse('google-login'))
        new_flow = self.client.session[FLOW_KEY]
        self.assertNotEqual(flow['state'], new_flow['state'])
        parsed = urlsplit(response.url)
        self.assertEqual(parsed.netloc, 'accounts.google.com')
        params = parse_qs(parsed.query)
        self.assertEqual(params['scope'], ['openid email'])
        self.assertNotIn('client_secret', params)
        self.assertEqual(params['nonce'], [new_flow['nonce']])
        expected = base64.urlsafe_b64encode(hashlib.sha256(new_flow['verifier'].encode()).digest()).rstrip(b'=').decode()
        self.assertEqual(params['code_challenge'], [expected])
        self.assertEqual(params['code_challenge_method'], ['S256'])

    def test_signed_google_token_logs_into_existing_account_and_links_subject(self):
        response = self.finish(self.begin('/historial/'))
        self.assertRedirects(response, reverse('task-history'))
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.worker.pk)
        self.assertEqual(GoogleIdentity.objects.get(user=self.worker).subject, 'google-worker-123')
        self.assertNotIn(FLOW_KEY, self.client.session)
        self.assertNotIn('id_token', self.client.session)
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')

    def test_signature_audience_issuer_expiry_nonce_and_verified_email_are_required(self):
        invalid = [dict(aud='other-client'), dict(iss='https://attacker.invalid'),
            dict(exp=int(time.time()) - 600), dict(nonce='wrong'), dict(nonce='ñ'),
            dict(email_verified=False), dict(sub=''), dict(email='not-an-email')]
        for changes in invalid:
            with self.subTest(changes=changes):
                response = self.finish(flow := self.begin(), self.signed(flow, **changes))
                self.assertEqual(response.status_code, 400)
                self.assertNotIn('_auth_user_id', self.client.session)
        flow = self.begin()
        parts = self.signed(flow).split('.')
        parts[2] = ('A' if parts[2][0] != 'A' else 'B') + parts[2][1:]
        self.assertEqual(self.finish(flow, '.'.join(parts)).status_code, 400)
        self.assertFalse(GoogleIdentity.objects.exists())

    def test_authoritative_google_workspace_email_is_supported(self):
        self.worker.email = 'worker@company.example'
        self.worker.save()
        flow = self.begin()
        self.assertEqual(self.finish(flow, self.signed(flow, email=self.worker.email)).status_code, 400)
        flow = self.begin()
        self.assertEqual(self.finish(flow, self.signed(flow, email=self.worker.email,
                                                     hd='company.example')).status_code, 302)

    def test_unknown_email_does_not_register_a_user(self):
        flow = self.begin()
        self.assertEqual(self.finish(flow, self.signed(flow, email='unknown@gmail.com')).status_code, 400)
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(GoogleIdentity.objects.exists())

    def test_disabled_deleted_or_revoked_account_is_rechecked_after_google_return(self):
        for field, value in [('allow_email_login', False), ('is_active', False),
                             ('deletion_due_at', timezone.now()), ('deleted_at', timezone.now())]:
            with self.subTest(field=field):
                flow = self.begin()
                original = getattr(self.worker, field)
                setattr(self.worker, field, value)
                self.worker.save()
                self.assertEqual(self.finish(flow).status_code, 400)
                self.assertNotIn('_auth_user_id', self.client.session)
                setattr(self.worker, field, original)
                self.worker.save()

    def test_duplicate_email_and_subject_collisions_do_not_choose_an_account(self):
        duplicate = User.objects.create_user(username='duplicate', email='WORKER@gmail.com')
        self.assertEqual(self.finish(self.begin()).status_code, 400)
        duplicate.email = 'other@gmail.com'
        duplicate.save()
        GoogleIdentity.objects.create(user=duplicate, subject='google-worker-123')
        self.assertEqual(self.finish(self.begin()).status_code, 400)
        self.assertFalse(GoogleIdentity.objects.filter(user=self.worker).exists())

    def test_linked_google_identity_cannot_be_silently_replaced(self):
        GoogleIdentity.objects.create(user=self.worker, subject='original-subject')
        self.assertEqual(self.finish(self.begin()).status_code, 400)
        flow = self.begin()
        self.assertEqual(self.finish(flow, self.signed(flow, sub='original-subject')).status_code, 302)
        self.assertEqual(GoogleIdentity.objects.get(user=self.worker).subject, 'original-subject')

    def test_state_is_bound_to_browser_expires_and_cannot_be_replayed(self):
        flow = self.begin()
        url = reverse('google-callback')
        with patch('accounts.google_login._exchange_code') as exchange:
            self.assertEqual(Client().get(url, {'state': flow['state'], 'code': 'x'}).status_code, 400)
            self.assertEqual(self.client.get(url, {'state': 'ñ', 'code': 'x'}).status_code, 400)
            exchange.assert_not_called()
        flow = self.begin()
        session = self.client.session
        session[FLOW_KEY] = dict(flow, created=time.time() - 700)
        session.save()
        self.assertEqual(self.finish(flow).status_code, 400)
        flow = self.begin()
        self.assertEqual(self.finish(flow).status_code, 302)
        self.assertEqual(self.finish(flow).status_code, 400)

    def test_cancellation_and_network_errors_are_handled_without_login(self):
        flow = self.begin()
        self.assertEqual(self.client.get(reverse('google-callback'),
            {'state': flow['state'], 'error': 'access_denied'}).status_code, 400)
        flow = self.begin()
        with patch('accounts.google_login._exchange_code', side_effect=requests.Timeout):
            self.assertEqual(self.client.get(reverse('google-callback'),
                {'state': flow['state'], 'code': 'x'}).status_code, 400)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_token_exchange_is_server_side_bounded_and_sends_the_pkce_verifier(self):
        flow = self.begin()
        response = Mock()
        response.json.return_value = {'id_token': self.signed(flow)}
        with patch('accounts.google_login.requests.post', return_value=response) as post, \
                patch('google.auth.transport.requests.Request.__call__', return_value=self.certs) as cert_request:
            result = self.client.get(reverse('google-callback'), {'state': flow['state'], 'code': 'test-code'})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(post.call_args.args[0], 'https://oauth2.googleapis.com/token')
        self.assertEqual(post.call_args.kwargs['data']['code_verifier'], flow['verifier'])
        self.assertEqual(post.call_args.kwargs['data']['client_secret'], 'test-client-secret')
        self.assertEqual(post.call_args.kwargs['timeout'], (3.05, 10))
        self.assertEqual(cert_request.call_args.kwargs['timeout'], (3.05, 10))

    def test_open_redirects_and_wrong_environment_callback_are_rejected(self):
        self.assertRedirects(self.finish(self.begin('https://attacker.invalid/')), reverse('task-list'))
        self.client.logout()
        with override_settings(GOOGLE_OAUTH_REDIRECT_URI='https://other-environment.example/login/google/callback/'):
            self.assertEqual(self.client.post(reverse('google-login')).status_code, 503)

    def test_google_certificate_transport_error_does_not_create_a_session(self):
        flow = self.begin()
        with patch('accounts.google_login._exchange_code', return_value=self.signed(flow)), \
                patch('google.auth.transport.requests.Request.__call__', side_effect=TransportError('unavailable')):
            response = self.client.get(reverse('google-callback'), {'state': flow['state'], 'code': 'x'})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_revoking_permission_invalidates_google_session_but_keeps_password_access(self):
        self.finish(self.begin())
        self.worker.allow_email_login = False
        self.worker.save()
        self.assertRedirects(self.client.get(reverse('profile')), reverse('login') + '?next=' + reverse('profile'))
        self.assertEqual(authenticate(username='worker', password='worker-pass'), self.worker)

    def test_google_cannot_skip_required_profile_or_password_completion(self):
        for field, destination in [('must_change_password', 'password-change'),
                                   ('must_complete_profile', 'complete-profile')]:
            flow = self.begin()
            setattr(self.worker, field, True)
            self.worker.save()
            response = self.finish(flow, follow=True)
            self.assertEqual(response.redirect_chain[-1][0], reverse(destination))
            self.client.logout()
            setattr(self.worker, field, False)
            self.worker.save()
