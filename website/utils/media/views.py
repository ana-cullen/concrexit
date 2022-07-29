"""Utility views."""
from datetime import timedelta

import sentry_sdk
from PIL import Image, ImageOps
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.core.files.storage import get_storage_class
from django.core.signing import BadSignature
from django.http import Http404
from django.shortcuts import redirect
from django.utils import timezone
from django_sendfile import sendfile

from utils.media.services import save_image


def _get_signature_info(request):
    if "sig" in request.GET:
        signature = request.GET.get("sig")
        try:
            return signing.loads(signature, max_age=timedelta(hours=3))
        except BadSignature:
            pass
    raise PermissionDenied


def private_media(request, request_path):
    """Serve private media files.

    :param request: the request
    :return: the media file
    """
    # Get image information from signature
    # raises PermissionDenied if bad signature
    sig_info = _get_signature_info(request)
    storage = get_storage_class(sig_info["storage"])()

    if (
        not storage.exists(sig_info["serve_path"])
        or not sig_info["serve_path"] == request_path
    ):
        # 404 if the file does not exist
        raise Http404("Media not found.")

    # Serve the file, or redirect to a signed bucket url in the case of S3
    if hasattr(storage, "bucket"):
        serve_url = storage.url(sig_info["serve_path"])
        return redirect(
            f"{serve_url}",
            permanent=False,
        )
    return sendfile(
        request,
        sig_info["serve_path"],
        attachment=bool(sig_info.get("attachment", False)),
        attachment_filename=sig_info.get("attachment", None),
    )


def get_thumbnail(request, request_path):
    """Generate thumbnail and redirect user to new location.

    The thumbnails are generated with this route. Because the
    thumbnails will be generated in parallel, it will not block
    page load when many thumbnails need to be generated.
    After it is done, the user is redirected to the new location
    of the thumbnail.

    :param HttpRequest request: the request
    :return: HTTP Redirect to thumbnail
    """
    # Get image information from signature
    # raises PermissionDenied if bad signature
    with sentry_sdk.start_span(op="thumbnails", description="Get signature info"):
        sig_info = _get_signature_info(request)
    storage = get_storage_class(sig_info["storage"])()

    if not sig_info["thumb_path"].endswith(request_path):
        # 404 if the file does not exist
        raise Http404("Media not found.")

    with sentry_sdk.start_span(op="thumbnails", description="Obtain modified times"):
        original_modified_time = timezone.datetime.min
        thumb_modified_time = original_modified_time
        # noinspection PyBroadException
        try:
            original_modified_time = storage.modified_time(sig_info["name"])
            thumb_modified_time = storage.modified_time(sig_info["thumb_path"])
        except:
            # One of the files probably does not exist
            pass

        if original_modified_time.timestamp() == 0:
            raise Http404

    # Check if directory for thumbnail exists, if not create it
    # os.makedirs(os.path.dirname(full_thumb_path), exist_ok=True)
    # Skip generating the thumbnail if it exists
    if original_modified_time > thumb_modified_time:
        storage.delete(sig_info["thumb_path"])

        # Create a thumbnail from the original_path, saved to thumb_path
        with sentry_sdk.start_span(op="thumbnails", description="Generate thumbnail image"):
            with storage.open(sig_info["name"], "rb") as original_file:
                image = Image.open(original_file)
                format = image.format
                size = tuple(int(dim) for dim in sig_info["size"].split("x"))
                if not sig_info["fit"]:
                    ratio = min([a / b for a, b in zip(size, image.size)])
                    size = tuple(int(ratio * x) for x in image.size)

                if size[0] != image.size[0] and size[1] != image.size[1]:
                    image = ImageOps.fit(image, size, Image.ANTIALIAS)

                save_image(storage, image, sig_info["thumb_path"], format)

    # Redirect to the serving url of the image
    # for public images this goes via a static file server (i.e. nginx)
    # for private images this is a call to private_media
    return redirect(storage.url(sig_info["thumb_path"]))
