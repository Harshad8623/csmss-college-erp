"""
app/utils/cloudinary_upload.py
──────────────────────────────
Cloudinary profile picture upload helper.
Falls back gracefully to local disk storage if Cloudinary is not configured
(i.e., in local development without env vars set).
"""

import os
import cloudinary
import cloudinary.uploader
from flask import current_app


def _cloudinary_configured():
    """Check if Cloudinary env vars are set."""
    return bool(
        os.environ.get('CLOUDINARY_CLOUD_NAME') and
        os.environ.get('CLOUDINARY_API_KEY') and
        os.environ.get('CLOUDINARY_API_SECRET')
    )


def init_cloudinary():
    """Configure the Cloudinary SDK from environment variables."""
    cloudinary.config(
        cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
        api_key    = os.environ.get('CLOUDINARY_API_KEY'),
        api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
        secure     = True   # Always use HTTPS URLs
    )


def upload_profile_picture(file_storage, user_id):
    """
    Upload a profile picture.

    Returns:
        str: Cloudinary URL (production) or local filename (dev fallback).
        None on failure.
    """
    if _cloudinary_configured():
        return _upload_to_cloudinary(file_storage, user_id)
    else:
        return _save_locally(file_storage, user_id)


def _upload_to_cloudinary(file_storage, user_id):
    """Upload to Cloudinary and return the secure URL."""
    # Validate extension — same allowlist as local fallback to prevent SVG/HTML uploads
    allowed = {'.jpg', '.jpeg', '.png', '.webp'}
    ext = os.path.splitext(file_storage.filename or '')[1].lower()
    if ext not in allowed:
        current_app.logger.warning(f'Blocked upload of disallowed file type: {ext} for user {user_id}')
        return None
    try:
        init_cloudinary()
        result = cloudinary.uploader.upload(
            file_storage,
            folder         = 'csmss-erp/profiles',
            public_id      = f'user_{user_id}',
            overwrite      = True,           # Replace existing photo for same user
            resource_type  = 'image',
            transformation = [
                {'width': 400, 'height': 400, 'crop': 'fill', 'gravity': 'face'},
                {'quality': 'auto', 'fetch_format': 'auto'}
            ]
        )
        return result['secure_url']
    except Exception as e:
        current_app.logger.error(f'Cloudinary upload failed for user {user_id}: {e}')
        return None


def _save_locally(file_storage, user_id):
    """Fallback: save to static/uploads/profiles/ for local development."""
    from werkzeug.utils import secure_filename
    allowed = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in allowed:
        return None
    filename = secure_filename(f'{user_id}_profile{ext}')
    upload_dir = os.path.join(current_app.static_folder, 'uploads', 'profiles')
    os.makedirs(upload_dir, exist_ok=True)
    file_storage.save(os.path.join(upload_dir, filename))
    return filename   # Return just filename for local


def get_profile_pic_url(profile_pic_value):
    """
    Resolve a profile_pic value to a full URL for use in templates.
    - If it's already an https:// URL (Cloudinary), return as-is.
    - If it's a local filename, return the static URL path.
    - If None or 'default.png', return None (template shows initials).
    """
    if not profile_pic_value or profile_pic_value == 'default.png':
        return None
    if profile_pic_value.startswith('http'):
        return profile_pic_value
    # Legacy local filename — build static path
    return f'/static/uploads/profiles/{profile_pic_value}'
