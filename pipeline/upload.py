"""Stage 8: upload the finished video to YouTube via the Data API v3."""
from pathlib import Path

from .utils import DRY_RUN, load_channel_config, log, require_env


def _get_authenticated_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=require_env("YOUTUBE_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=require_env("YOUTUBE_CLIENT_ID"),
        client_secret=require_env("YOUTUBE_CLIENT_SECRET"),
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds)


def upload_video(
    video_path: Path,
    thumbnail_path: Path,
    title: str,
    description: str,
    tags: list,
) -> str:
    """thumbnail_path may be None -- a YouTube Short (see pipeline/shorts.py) skips a
    custom thumbnail entirely, since the Shorts feed doesn't display one (only the
    long-form video grid/watch page does)."""
    config = load_channel_config()
    yt_cfg = config["youtube"]

    if DRY_RUN:
        thumb_label = thumbnail_path.name if thumbnail_path else "(none)"
        log(f"Would upload '{title}' ({video_path.name}) with thumbnail {thumb_label}")
        log(f"privacy_status={yt_cfg['privacy_status']} tags={tags}")
        return "DRY-RUN-VIDEO-ID"

    from googleapiclient.http import MediaFileUpload

    youtube = _get_authenticated_service()

    log(f"Uploading '{title}' to YouTube")
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": yt_cfg["category_id"],
        },
        "status": {"privacyStatus": yt_cfg["privacy_status"]},
    }
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    video_id = response["id"]
    log(f"Uploaded: https://youtu.be/{video_id}")

    if thumbnail_path:
        log("Setting thumbnail")
        youtube.thumbnails().set(
            videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))
        ).execute()

    return video_id
