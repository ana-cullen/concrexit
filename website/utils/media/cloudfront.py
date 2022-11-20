from datetime import datetime

from django.conf import settings
from django.core.files.storage import get_storage_class
from django.http import HttpResponse


class CloudFrontUtil:
    def __init__(self):
        """
        :param private_key_path: str, the path of private key which generated by openssl command line
        :param key_id: str, CloudFront -> Key management -> Public keys
        """
        storage = get_storage_class(settings.PRIVATE_FILE_STORAGE)
        self.cf_signer = storage.get_cloudfront_signer(settings.AWS_CLOUDFRONT_KEY_ID, settings.AWS_CLOUDFRONT_KEY)

    def generate_signed_cookies(self, url: str, expire_at: datetime) -> dict[str, str]:
        policy = self.cf_signer.build_policy(url, expire_at).encode('utf8')
        policy_64 = self.cf_signer._url_b64encode(policy).decode('utf8')

        signature = self.cf_signer.rsa_signer(policy)
        signature_64 = self.cf_signer._url_b64encode(signature).decode('utf8')
        return {
            "CloudFront-Policy": policy_64,
            "CloudFront-Signature": signature_64,
            "CloudFront-Key-Pair-Id": settings.AWS_CLOUDFRONT_KEY_ID,
        }

    def modify_response(self, response: HttpResponse, url, expires: datetime) -> HttpResponse:
        cookies = self.generate_signed_cookies(url, expires)
        for name, value in cookies.items():
            response.set_cookie(name, value=value, secure=True)
        return response
