import pytest
import werkzeug.exceptions

from flasquelistan import util


class TestIsSafeUrl:
    def test_relative_path_is_safe(self, app):
        with app.test_request_context('/'):
            assert util.is_safe_url('/profile/1') is True

    def test_absolute_url_same_host_is_safe(self, app):
        with app.test_request_context('/'):
            assert util.is_safe_url('http://localhost/quotes/') is True

    def test_absolute_url_other_host_is_unsafe(self, app):
        with app.test_request_context('/'):
            assert util.is_safe_url('https://evil.tld/x') is False

    def test_protocol_relative_url_is_unsafe(self, app):
        # '//evil.tld' inherits the scheme but changes the host.
        with app.test_request_context('/'):
            assert util.is_safe_url('//evil.tld/x') is False

    def test_javascript_scheme_is_unsafe(self, app):
        with app.test_request_context('/'):
            assert util.is_safe_url('javascript:alert(1)') is False


class TestGetRedirectTarget:
    def test_returns_safe_next_argument(self, app):
        with app.test_request_context('/login?next=/quotes/'):
            assert util.get_redirect_target() == '/quotes/'

    def test_skips_unsafe_next_argument(self, app):
        with app.test_request_context('/login?next=https://evil.tld/x'):
            assert util.get_redirect_target() is None

    def test_unsafe_next_falls_back_to_safe_referrer(self, app):
        with app.test_request_context(
                '/login?next=//evil.tld/x',
                headers={'Referer': 'http://localhost/quotes/'}):
            assert util.get_redirect_target() == 'http://localhost/quotes/'

    def test_no_next_and_no_referrer_returns_none(self, app):
        with app.test_request_context('/login'):
            assert util.get_redirect_target() is None


class TestFormatPhoneNumber:
    def test_valid_swedish_number_international(self, app):
        assert util.format_phone_number('074-345 32 10') == '+46 74 345 32 10'

    def test_valid_swedish_number_e164(self, app):
        assert util.format_phone_number('074-345 32 10', e164=True) \
            == '+46743453210'

    def test_invalid_number_returns_false(self, app):
        # Invalid numbers are not returned as-is, the function returns
        # False so callers can decide what to do.
        invalid_number = '+4674-876 543 226 189 416 854 65'
        assert util.format_phone_number(invalid_number) is False

    def test_empty_string_returns_false(self, app):
        assert util.format_phone_number('') is False


class TestGenerateSecurePathHash:
    def test_deterministic_for_same_input(self, app):
        with app.test_request_context('/'):
            hash1 = util.generate_secure_path_hash(1000, '/img/a.jpg', 's3cr3t')
            hash2 = util.generate_secure_path_hash(1000, '/img/a.jpg', 's3cr3t')
            assert hash1 == hash2

    def test_differs_for_different_paths(self, app):
        with app.test_request_context('/'):
            hash1 = util.generate_secure_path_hash(1000, '/img/a.jpg', 's3cr3t')
            hash2 = util.generate_secure_path_hash(1000, '/img/b.jpg', 's3cr3t')
            assert hash1 != hash2

    def test_differs_for_different_secrets(self, app):
        with app.test_request_context('/'):
            hash1 = util.generate_secure_path_hash(1000, '/img/a.jpg', 's3cr3t')
            hash2 = util.generate_secure_path_hash(1000, '/img/a.jpg', 'other')
            assert hash1 != hash2


class TestUrlForImage:
    def test_profilepicture_url(self, app):
        app.config['IMAGE_SECRET'] = 'not a secret'
        app.config['IMAGE_EXPIRY'] = 3600

        with app.test_request_context('/'):
            url = util.url_for_image('monty.jpg', 'profilepicture')

        assert 'profilepictures/monty.jpg' in url
        assert 'md5=' in url
        assert 'expires=' in url

    def test_image_url(self, app):
        app.config['IMAGE_SECRET'] = 'not a secret'
        app.config['IMAGE_EXPIRY'] = 3600

        with app.test_request_context('/'):
            url = util.url_for_image('gallery.jpg', 'image')

        assert 'images/gallery.jpg' in url
        assert 'md5=' in url

    def test_invalid_image_type_aborts(self, app):
        with app.test_request_context('/'):
            with pytest.raises(werkzeug.exceptions.InternalServerError):
                util.url_for_image('monty.jpg', 'not-a-type')
