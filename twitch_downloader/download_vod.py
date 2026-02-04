#!/usr/bin/env python3
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
import tqdm

CLIENT_ID = 'ue6666qo983tsx6so1t0vnawi233wa'
API_BASE = 'https://api.twitch.tv'
USHER_BASE = 'https://usher.ttvnw.net'
GQL_URL = 'https://gql.twitch.tv/gql'

# Configuration
DEFAULT_MAX_WORKERS = 16
SEGMENT_DOWNLOAD_TIMEOUT = 30  # seconds
SEGMENT_DOWNLOAD_RETRIES = 3


def download_json(url, headers=None, data=None):
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def get_video_id(url):
    match = re.search(r'/videos/(\d+)', url)
    if match:
        return match.group(1)
    raise ValueError("Invalid Twitch VOD URL")


def download_video_metadata(video_id):
    query = {
        "query": """
        {
          video(id: "%s") {
            id
            title
            description
            lengthSeconds
            publishedAt
            owner {
              displayName
              login
            }
            viewCount
            thumbnailURLs(height: 480, width: 640)
          }
        }
        """ % video_id,
    }
    headers = {'Client-ID': CLIENT_ID}
    data = download_json(GQL_URL, headers=headers, data=query)
    return data['data']['video']


def get_access_token(video_id):
    query = {
        "query": """
        {
          videoPlaybackAccessToken(id: "%s", params: {platform: "web", playerBackend: "mediaplayer", playerType: "site"}) {
            value
            signature
          }
        }
        """ % video_id,
    }
    headers = {'Client-ID': CLIENT_ID}
    data = download_json(GQL_URL, headers=headers, data=query)
    return data['data']['videoPlaybackAccessToken']


def get_m3u8_url(video_id, token, signature):
    params = {
        'allow_source': 'true',
        'allow_audio_only': 'true',
        'allow_spectre': 'true',
        'p': '1000000',  # random
        'platform': 'web',
        'player': 'twitchweb',
        'supported_codecs': 'av1,h265,h264',
        'playlist_include_framerate': 'true',
        'sig': signature,
        'token': token,
    }
    url = f'{USHER_BASE}/vod/{video_id}.m3u8'
    full_url = url + '?' + urllib.parse.urlencode(params)
    return full_url


def is_master_playlist(playlist_text):
    return '#EXT-X-STREAM-INF' in playlist_text


def choose_variant_from_master(master_text, base_url):
    # Parse master playlist, choose variant with highest BANDWIDTH
    lines = master_text.splitlines()
    best_bandwidth = -1
    best_uri = None
    for i, line in enumerate(lines):
        if line.startswith('#EXT-X-STREAM-INF'):
            m = re.search(r'BANDWIDTH=(\d+)', line)
            bw = int(m.group(1)) if m else -1
            # Next non-empty line should be the URI
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            if j < len(lines):
                uri = lines[j].strip()
                if bw > best_bandwidth:
                    best_bandwidth = bw
                    best_uri = urllib.parse.urljoin(base_url, uri)
    return best_uri


def fetch_text(url):
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text


def parse_key_attrs(line):
    # Parse EXT-X-KEY attributes like METHOD=AES-128,URI="https://...",IV=0x...
    attrs = {}
    # Remove prefix
    _, rest = line.split(':', 1)
    parts = re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', rest)
    for p in parts:
        if '=' in p:
            k, v = p.split('=', 1)
            attrs[k.strip()] = v.strip().strip('"')
    return attrs


def download_file(url, path, timeout=SEGMENT_DOWNLOAD_TIMEOUT, retries=SEGMENT_DOWNLOAD_RETRIES):
  last_exc = None
  for attempt in range(1, retries + 1):
    try:
      with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with open(path, 'wb') as f:
          for chunk in r.iter_content(chunk_size=8192):
            if chunk:
              f.write(chunk)
        return
    except Exception as e:
      last_exc = e
      raise last_exc


def prepare_local_playlist_and_files(m3u8_url, tmp_dir, max_workers=DEFAULT_MAX_WORKERS):
    """
    Downloads the media playlist at m3u8_url, downloads keys and segments into tmp_dir,
    writes a local playlist in tmp_dir/local.m3u8 and returns its path.

    Returns:
        local_m3u8_path (str)
    Raises:
        Exception on unrecoverable errors.
    """
    print(f"Fetching playlist: {m3u8_url}")
    playlist_text = fetch_text(m3u8_url)

    # Keep the original m3u8 URL and its query string so we can preserve token/sig when resolving
    parsed_m3u8 = urllib.parse.urlparse(m3u8_url)
    original_query = parsed_m3u8.query  # token/sig etc, may be required by segment requests

    # For resolving relative URIs we use the directory of the playlist (so urljoin works),
    # but we will append the original query to any resolved URL that lacks a query.
    base_dir = urllib.parse.urlunparse(
        (parsed_m3u8.scheme, parsed_m3u8.netloc, os.path.dirname(parsed_m3u8.path) + '/', '', '', '')
    )

    # If this is a master playlist, pick the best variant and fetch it.
    if is_master_playlist(playlist_text):
        print("Master playlist detected; choosing best variant by BANDWIDTH")
        variant_uri = choose_variant_from_master(playlist_text, base_dir)
        if not variant_uri:
            raise RuntimeError("Could not select a variant from master playlist")
        # Resolve variant_uri relative to the original m3u8_url base to handle relative URIs.
        variant_abs = urllib.parse.urljoin(m3u8_url, variant_uri)
        # If variant_abs has no query but the original m3u8_url did, append it.
        parsed_variant = urllib.parse.urlparse(variant_abs)
        if not parsed_variant.query and original_query:
            sep = '&' if variant_abs.find('?') != -1 else '?'
            variant_abs = variant_abs + sep + original_query
        print(f"Selected variant: {variant_abs}")
        playlist_text = fetch_text(variant_abs)
        # Update base_dir so segments are resolved relative to the variant's location
        parsed = urllib.parse.urlparse(variant_abs)
        base_dir = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, os.path.dirname(parsed.path) + '/', '', '', ''))
        # Keep the query we will want to propagate (variant may include query)
        original_query = parsed.query

    lines = playlist_text.splitlines()
    local_lines = []
    segment_infos = []  # list of (index, abs_url, local_filename, local_path)
    key_local_map = {}  # original abs_key_uri -> local_key_path
    segment_index = 0

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXT-X-KEY'):
            attrs = parse_key_attrs(line)
            if 'URI' in attrs:
                key_uri = attrs['URI']
                # Resolve key URI relative to the variant/playlist
                abs_key_uri = urllib.parse.urljoin(base_dir, key_uri)
                parsed_key = urllib.parse.urlparse(abs_key_uri)
                if not parsed_key.query and original_query:
                    sep = '&' if abs_key_uri.find('?') != -1 else '?'
                    abs_key_uri = abs_key_uri + sep + original_query
                local_key_name = f"key_{len(key_local_map)}"
                local_key_path = os.path.join(tmp_dir, local_key_name)
                key_local_map[abs_key_uri] = local_key_path
                # rewrite the key line to point to the local file (URI="<local>")
                new_attrs = []
                for k, v in attrs.items():
                    if k == 'URI':
                        new_attrs.append(f'URI="{os.path.basename(local_key_path)}"')
                    else:
                        new_attrs.append(f'{k}={v}')
                local_lines.append('#EXT-X-KEY:' + ','.join(new_attrs))
            else:
                local_lines.append(line)
            i += 1
            continue

        if line == '' or line.startswith('#'):
            local_lines.append(line)
            i += 1
            continue

        # Non-comment line: likely a segment URI
        seg_uri = line
        abs_seg_uri = urllib.parse.urljoin(base_dir, seg_uri)
        parsed_seg = urllib.parse.urlparse(abs_seg_uri)
        # If the resolved segment URL does not include the query params but the original playlist had them,
        # append the original query so token/sig are preserved.
        if not parsed_seg.query and original_query:
            sep = '&' if abs_seg_uri.find('?') != -1 else '?'
            abs_seg_uri = abs_seg_uri + sep + original_query

        ext = os.path.splitext(seg_uri)[1] or '.ts'
        local_seg_name = f"segment_{segment_index:06d}{ext}"
        local_seg_path = os.path.join(tmp_dir, local_seg_name)
        segment_infos.append((segment_index, abs_seg_uri, local_seg_name, local_seg_path))
        local_lines.append(local_seg_name)
        segment_index += 1
        i += 1

    # Download keys first
    for abs_key_uri, local_key_path in key_local_map.items():
        print(f"Downloading key: {abs_key_uri} -> {local_key_path}")
        try:
            download_file(abs_key_uri, local_key_path)
        except Exception as e:
            raise RuntimeError(f"Failed to download key {abs_key_uri}: {e}")

    # Download segments in parallel (same as before)
    print(f"Downloading {len(segment_infos)} segments to {tmp_dir} using up to {max_workers} workers")
    errors = []
    lock = threading.Lock()

    def _dl_task(info):
        idx, abs_url, local_name, local_path = info
        try:
            download_file(abs_url, local_path)
            return (idx, None)
        except Exception as e:
            return (idx, e)
    pbar = tqdm.tqdm(total=len(segment_infos))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_dl_task, si): si for si in segment_infos}
        for fut in as_completed(futures):
            idx, err = fut.result()
            pbar.update(1)
            if err:
                with lock:
                    errors.append((idx, err))
                print(f"Segment {idx} failed: {err}")
            else:
                if idx % 50 == 0:
                    print(f"Downloaded segment {idx}")
        pbar.close()
    if errors:
        raise RuntimeError(f"{len(errors)} segments failed to download; first error: {errors[0][1]}")

    # Write local playlist
    local_m3u8_path = os.path.join(tmp_dir, "local.m3u8")
    print(f"Writing local playlist to {local_m3u8_path}")
    with open(local_m3u8_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(local_lines))
        f.write('\n')
    return local_m3u8_path

def download_vod(url, output_file=None, max_workers=DEFAULT_MAX_WORKERS):
    video_id = get_video_id(url)
    metadata = download_video_metadata(video_id)
    access_token = get_access_token(video_id)

    m3u8_url = get_m3u8_url(video_id, access_token['value'], access_token['signature'])

    if not output_file:
      title = metadata['title'] or 'Untitled'
      safe_title = title.replace('/', '_')
      output_file = f"{safe_title}.mp4"

    print(f"Downloading {metadata['title']} to {output_file}")

    # Prepare temp dir and download all files
    tmp_dir = tempfile.mkdtemp(prefix="twitch_vod_")
    try:
      try:
          local_playlist = prepare_local_playlist_and_files(m3u8_url, tmp_dir, max_workers=max_workers)
      except Exception as e:
        # If we can't prepare, fall back to streaming ffmpeg with original m3u8
        print(f"Could not prepare local playlist: {e}")
        print("Falling back to streaming ffmpeg (original behavior).")
        cmd = ['ffmpeg', '-i', m3u8_url, '-c', 'copy', '-bsf:a', 'aac_adtstoasc', output_file]
        subprocess.run(cmd, check=True)
        return

      # Run ffmpeg on local playlist
      # Use protocol_whitelist to allow file:// use and local files (some ffmpeg builds require it)
      ffmpeg_cmd = [
        'ffmpeg',
        '-protocol_whitelist', 'file,http,https,tcp,tls',
        '-i', local_playlist,
        '-c', 'copy',
        '-bsf:a', 'aac_adtstoasc',
        output_file
      ]
      print("Running ffmpeg to mux local files into final output...")
      subprocess.run(ffmpeg_cmd, check=True)
      print("Download & mux complete.")
    finally:
      pass
      # Clean up temporary dir if ffmpeg succeeded. If the output file doesn't exist or ffmpeg failed,
      # keep the temp dir for debugging.
      # if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
      #     try:
      #         shutil.rmtree(tmp_dir)
      #     except Exception:
      #         pass
      # else:
      #     print(f"Keeping temporary directory for inspection: {tmp_dir}")


if __name__ == '__main__':
  if len(sys.argv) < 2:
    print("Usage: python download_vod.py <twitch_vod_url> [output_file]")
    sys.exit(1)
  url = sys.argv[1]
  output_file = sys.argv[2] if len(sys.argv) > 2 else None
  download_vod(url, output_file, 32)
