"""Fetch a channel's recent uploads and enrich them with video metadata.

Usage:
    export YT_KEY="your-key"
    python fetch_channel.py @3blue1brown 50

Quota used: ~1 (channel) + 1 per 50 playlist items + 1 per 50 videos.
"""
import json
import os
import re
import sys
from pathlib import Path

import requests

API = "https://www.googleapis.com/youtube/v3"
KEY = KEY = os.environ["YT_KEY"]


def get(endpoint, **params):
    r = requests.get(f"{API}/{endpoint}", params={**params, "key": KEY}, timeout=20)
    if not r.ok:
        err = r.json().get("error", {})
        sys.exit(f"{r.status_code}: {err.get('message')}")
    return r.json()

def uploads_playlist_id(handle):
    data = get("channels", part="contentDetails", forHandle=handle)
    return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]


def list_video_ids(playlist_id, limit):
    ids, token = [], None
    while len(ids) < limit:
        data = get(
            "playlistItems",
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=token,
        )
        ids += [i["contentDetails"]["videoId"] for i in data["items"]]
        token = data.get("nextPageToken")
        if not token:
            break
    return ids[:limit]


def duration_seconds(iso):
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def enrich(video_ids):
    videos = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        data = get(
            "videos",
            part="snippet,contentDetails,status,statistics",
            id=",".join(batch),
        )
        videos += data["items"]
    return videos


def main():
    handle = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    playlist_id = uploads_playlist_id(handle)
    ids = list_video_ids(playlist_id, limit)
    videos = enrich(ids)

    out = Path("data/raw")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{handle.lstrip('@')}.json").write_text(json.dumps(videos, indent=2))

    for v in videos:
        secs = duration_seconds(v["contentDetails"]["duration"])
        embeddable = v["status"].get("embeddable", False)
        lang = v["snippet"].get("defaultAudioLanguage", "?")
        print(f"{v['id']}  {secs // 60:>4} min  {lang:<5} embed={embeddable}  {v['snippet']['title']}")


if __name__ == "__main__":
    main()