#!/usr/bin/env python3
"""
Pengumpul komentar YouTube untuk analisis sentimen karhutla 2026.

Memakai YouTube Data API v3 (resmi). Tidak melakukan scraping.
Username TIDAK disimpan; hanya hash anonim (author_hash).

Contoh:
    export YOUTUBE_API_KEY="isi_api_key_kamu"
    python collect_youtube_comments.py \
        --published-after 2026-08-01 --published-before 2026-10-16 \
        --max-videos 60 --max-comments-per-video 500

Perkiraan kuota (jatah harian gratis 10.000 unit):
    search.list        = 100 unit / halaman (50 video)
    videos.list        = 1 unit / 50 video
    commentThreads.list = 1 unit / halaman (100 komentar)
"""
import argparse
import csv
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

API = "https://www.googleapis.com/youtube/v3"

DEFAULT_QUERIES = [
    "karhutla 2026",
    "kebakaran hutan Raja Juli Antoni",
    "karhutla Prabowo",
    "kabut asap karhutla Kalimantan",
    "kebakaran hutan dan lahan Indonesia 2026",
]


class QuotaExceeded(Exception):
    pass


def api_get(endpoint, params, key, retries=4):
    """GET ke YouTube API dengan retry. Mengembalikan None jika komentar dinonaktifkan."""
    params = dict(params, key=key)
    for attempt in range(retries):
        try:
            resp = requests.get(f"{API}/{endpoint}", params=params, timeout=30)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 200:
            return resp.json()

        try:
            err = resp.json().get("error", {})
        except ValueError:
            err = {}
        reasons = [x.get("reason") for x in err.get("errors", [])]

        if "quotaExceeded" in reasons or "dailyLimitExceeded" in reasons:
            raise QuotaExceeded("Kuota harian API habis. Jalankan lagi besok; data yang sudah terkumpul tetap tersimpan.")
        if "commentsDisabled" in reasons or "videoNotFound" in reasons:
            return None
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        raise RuntimeError(f"HTTP {resp.status_code}: {err.get('message', resp.text[:200])}")
    raise RuntimeError(f"Gagal memanggil {endpoint} setelah {retries} percobaan")


def rfc3339(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def search_videos(query, key, after, before, limit):
    ids, token = [], None
    while len(ids) < limit:
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "relevance",
            "regionCode": "ID",
            "relevanceLanguage": "id",
            "publishedAfter": rfc3339(after),
            "publishedBefore": rfc3339(before),
            "maxResults": 50,
        }
        if token:
            params["pageToken"] = token
        data = api_get("search", params, key)
        if not data:
            break
        ids.extend(item["id"]["videoId"] for item in data.get("items", []))
        token = data.get("nextPageToken")
        if not token:
            break
    return ids[:limit]


def video_details(video_ids, key):
    details = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        data = api_get("videos", {"part": "snippet,statistics", "id": ",".join(chunk)}, key)
        for item in (data or {}).get("items", []):
            stats = item.get("statistics", {})
            snip = item["snippet"]
            details[item["id"]] = {
                "video_id": item["id"],
                "title": snip.get("title", ""),
                "channel": snip.get("channelTitle", ""),
                "published_at": snip.get("publishedAt", ""),
                "view_count": int(stats.get("viewCount", 0)),
                # commentCount tidak ada jika komentar dinonaktifkan
                "comment_count": int(stats.get("commentCount", 0)),
            }
    return details


def fetch_comments(video_id, key, max_comments, order):
    token, got = None, []
    while len(got) < max_comments:
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": 100,
            "order": order,
            "textFormat": "plainText",
        }
        if token:
            params["pageToken"] = token
        data = api_get("commentThreads", params, key)
        if not data:
            break
        got.extend(data.get("items", []))
        token = data.get("nextPageToken")
        if not token:
            break
    return got[:max_comments]


def anonymize(author_channel_id, salt):
    raw = f"{salt}:{author_channel_id or 'unknown'}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser(description="Kumpulkan komentar YouTube tentang karhutla (anonim).")
    ap.add_argument("--api-key", default=os.environ.get("YOUTUBE_API_KEY"))
    ap.add_argument("--queries", nargs="+", default=DEFAULT_QUERIES)
    ap.add_argument("--published-after", default="2026-08-01", help="YYYY-MM-DD")
    ap.add_argument("--published-before", default="2026-10-16", help="YYYY-MM-DD")
    ap.add_argument("--max-videos-per-query", type=int, default=50)
    ap.add_argument("--max-videos", type=int, default=60, help="batas total video yang diambil komentarnya")
    ap.add_argument("--min-comments", type=int, default=20, help="abaikan video dengan komentar lebih sedikit")
    ap.add_argument("--max-comments-per-video", type=int, default=500)
    ap.add_argument("--order", choices=["relevance", "time"], default="relevance")
    ap.add_argument("--salt", default=os.environ.get("HASH_SALT", "karhutla2026"))
    ap.add_argument("--out-dir", default="data")
    args = ap.parse_args()

    if not args.api_key:
        sys.exit("API key belum diisi. Set env YOUTUBE_API_KEY atau pakai --api-key.")

    os.makedirs(args.out_dir, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    log = {"started_at_utc": started, "args": {k: v for k, v in vars(args).items() if k not in ("api_key", "salt")},
           "videos_found_per_query": {}}

    try:
        # 1) Cari video
        all_ids = []
        for q in args.queries:
            ids = search_videos(q, args.api_key, args.published_after, args.published_before, args.max_videos_per_query)
            log["videos_found_per_query"][q] = len(ids)
            print(f"[cari] '{q}': {len(ids)} video")
            all_ids.extend(ids)
        unique_ids = list(dict.fromkeys(all_ids))

        # 2) Detail & filter
        details = video_details(unique_ids, args.api_key)
        selected = [v for v in details.values() if v["comment_count"] >= args.min_comments]
        selected.sort(key=lambda v: v["comment_count"], reverse=True)
        selected = selected[:args.max_videos]
        print(f"[filter] {len(unique_ids)} video unik -> {len(selected)} dipilih (>= {args.min_comments} komentar)")

        with open(os.path.join(args.out_dir, "videos.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["video_id", "title", "channel", "published_at", "view_count", "comment_count"])
            w.writeheader()
            w.writerows(selected)

        # 3) Ambil komentar (ditulis bertahap agar aman bila kuota habis)
        comments_path = os.path.join(args.out_dir, "comments.csv")
        seen, total = set(), 0
        fields = ["comment_id", "video_id", "video_title", "channel", "video_published_at",
                  "author_hash", "text", "like_count", "reply_count", "published_at"]
        with open(comments_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for n, v in enumerate(selected, 1):
                items = fetch_comments(v["video_id"], args.api_key, args.max_comments_per_video, args.order)
                added = 0
                for it in items:
                    cid = it["id"]
                    if cid in seen:
                        continue
                    seen.add(cid)
                    top = it["snippet"]["topLevelComment"]["snippet"]
                    w.writerow({
                        "comment_id": cid,
                        "video_id": v["video_id"],
                        "video_title": v["title"],
                        "channel": v["channel"],
                        "video_published_at": v["published_at"],
                        "author_hash": anonymize((top.get("authorChannelId") or {}).get("value"), args.salt),
                        "text": top.get("textDisplay", "").replace("\r", " ").strip(),
                        "like_count": top.get("likeCount", 0),
                        "reply_count": it["snippet"].get("totalReplyCount", 0),
                        "published_at": top.get("publishedAt", ""),
                    })
                    added += 1
                f.flush()
                total += added
                print(f"[komentar] {n}/{len(selected)} {v['video_id']}: +{added} (total {total})")
        log["videos_selected"] = len(selected)
        log["comments_collected"] = total
    except QuotaExceeded as e:
        print(f"\n[STOP] {e}")
        log["stopped_reason"] = "quota_exceeded"
    finally:
        log["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        with open(os.path.join(args.out_dir, "collection_log.json"), "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        print(f"\nSelesai. File ada di folder '{args.out_dir}/' (comments.csv, videos.csv, collection_log.json)")


if __name__ == "__main__":
    main()
