# backend/storage.py

import uuid
from django.conf import settings

SUPABASE = settings.SUPABASE
BUCKET = settings.SUPABASE_BUCKET


def upload_to_supabase(file_obj, folder="uploads"):
    """
    Upload any file to Supabase Storage and return the public URL.
    Works for images, PDFs, docs, videos, etc.
    """

    if not file_obj:
        return None

    # Extract extension safely
    original_name = file_obj.name
    ext = original_name.split(".")[-1].lower()

    # Generate unique path
    unique_filename = f"{folder}/{uuid.uuid4()}.{ext}"

    # Upload file (bytes + proper content type)
    response = SUPABASE.storage.from_(BUCKET).upload(
        unique_filename,
        file_obj.read(),
        {
            "content-type": file_obj.content_type or "application/octet-stream",
            "upsert": True
        }
    )

    # Validate response
    if response is None or (isinstance(response, dict) and response.get("error")):
        raise Exception(f"Supabase upload error: {response}")

    # Generate public URL
    public_url = SUPABASE.storage.from_(BUCKET).get_public_url(unique_filename)

    return public_url
