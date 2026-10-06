"""
FFmpeg utility wrapper
"""

try:
    import imageio_ffmpeg
    FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()
    FFPROBE_BIN = imageio_ffmpeg.get_ffprobe_exe() if hasattr(imageio_ffmpeg, 'get_ffprobe_exe') else None
except:
    FFMPEG_BIN = "ffmpeg"
    FFPROBE_BIN = "ffprobe"

def get_ffmpeg():
    return FFMPEG_BIN

def get_ffprobe():
    return FFPROBE_BIN
