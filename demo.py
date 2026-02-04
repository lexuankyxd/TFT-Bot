import yt_dlp

# Replace with the actual Twitch VOD URL
url = 'https://www.twitch.tv/videos/2686951727'

ydl_opts = {
  'outtmpl': '%(title)s.%(ext)s',  # Output filename template
  'format': 'best',  # Download best quality
  'concurrent_fragments': 64,  # Use 4 threads for downloading fragments (for HLS/DASH streams)
}
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
  ydl.download([url])
