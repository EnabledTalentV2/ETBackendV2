# backend/supabase_storage.py

import os
import uuid
import mimetypes
from typing import Optional

from django.conf import settings
from supabase import create_client, Client


class SupabaseStorageService:
    _client: Optional[Client] = None

    @classmethod
    def _get_client(cls) -> Client:
        if cls._client is None:
            url = settings.SUPABASE_URL
            key = settings.SUPABASE_KEY
            if not url or not key:
                raise RuntimeError("SUPABASE_URL or SUPABASE_KEY not configured")
            cls._client = create_client(url, key)
        return cls._client

    @classmethod
    def upload_file(cls, file_obj, folder: str = ""):
        """
        Uploads a Django InMemoryUploadedFile / TemporaryUploadedFile to Supabase Storage.
        Returns: (public_url, path)
        """
        client = cls._get_client()
        bucket = getattr(settings, "SUPABASE_BUCKET", "media")

        ext = os.path.splitext(file_obj.name)[1]
        filename = f"{uuid.uuid4().hex}{ext}"
        path = f"{folder}/{filename}" if folder else filename

        content_type, _ = mimetypes.guess_type(file_obj.name)
        content_type = content_type or "application/octet-stream"

        # Read bytes from uploaded file
        file_bytes = file_obj.read()

        # Upload to Supabase Storage; this raises if it fails
        client.storage.from_(bucket).upload(
            path=path,
            file=file_bytes,
            file_options={"content-type": content_type},
        )

        # Get public URL (assuming bucket is public)
        public_url = client.storage.from_(bucket).get_public_url(path)
        return public_url, path
