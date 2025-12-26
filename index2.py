import yt_dlp

# URL of the video or playlist
video_url = 'https://youtu.be/rZ_e-s6VvR4?si=QBUzaUQ0zgb8VegY'

# Options for the downloader
ydl_opts = {
    'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best', # Best quality up to 1080p
    'outtmpl': 'downloaded_video_yt_dlp.mp4', # Output filename
    'noplaylist': True, # Set to True if you don't want to download a whole playlist
    'merge_output_format': 'mp4', # Ensure output is MP4
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([video_url])

print("Download complete!")
