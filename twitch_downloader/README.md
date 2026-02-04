# Twitch VOD Downloader

This is a simple reimplementation of yt-dlp's Twitch VOD downloading functionality.

## Installation

1. Install Python 3.x
2. Install dependencies: `pip install -r requirements.txt`
3. Install FFmpeg (required for downloading HLS streams)

## Usage

```bash
python download_vod.py <twitch_vod_url> [output_file]
```

Example:

```bash
python download_vod.py https://www.twitch.tv/videos/123456789
```

This will download the VOD to a file named after the title.

## How it works

- Extracts video ID from URL
- Fetches metadata via Twitch GraphQL API
- Obtains access token
- Constructs M3U8 URL for the stream
- Uses FFmpeg to download and mux the stream into MP4

## Notes

- This is a basic implementation and may not handle all edge cases like yt-dlp does.
- For subscriber-only VODs, you may need to provide authentication (not implemented here).
- Ensure FFmpeg is in your PATH.
