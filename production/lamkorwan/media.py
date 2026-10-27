"""Cloud-side media inspection. Only small QA JPEGs/JSON are published to Git."""
import json
import importlib.util
from fractions import Fraction
from pathlib import Path
import shutil
import subprocess
import sys


def run(command):
    subprocess.run([str(x) for x in command], check=True)


def ensure_tools():
    if not shutil.which('ffmpeg') or (not shutil.which('ffprobe') and not importlib.util.find_spec('av')):
        if not shutil.which('sudo'):
            raise RuntimeError('ffmpeg and ffprobe are required')
        run(['sudo', 'apt-get', 'update', '-qq'])
        run(['sudo', 'apt-get', 'install', '-y', '-qq', 'ffmpeg'])


def probe(path):
    if not shutil.which('ffprobe'):
        # Equivalent metadata inspection for local tests; Actions uses native ffprobe.
        import av
        with av.open(str(path)) as container:
            result = {'duration': container.duration / av.time_base, 'bytes': Path(path).stat().st_size,
                      'probe_backend': 'pyav'}
            for stream in container.streams:
                if stream.type == 'video':
                    result.update(width=stream.width, height=stream.height, fps=float(stream.average_rate),
                                  frames=stream.frames, video_codec=stream.codec_context.name)
                elif stream.type == 'audio':
                    result.update(audio_codec=stream.codec_context.name, sample_rate=stream.sample_rate,
                                  audio_channels=stream.codec_context.channels)
            return result
    data = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)
    ], text=True))
    video = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
    audio = next((s for s in data['streams'] if s['codec_type'] == 'audio'), None)
    result = {'duration': float(data['format']['duration']), 'bytes': Path(path).stat().st_size}
    if video:
        rate = video.get('avg_frame_rate', '0/1')
        result.update(width=video['width'], height=video['height'],
                      fps=float(Fraction(rate)), video_codec=video['codec_name'],
                      frames=int(video.get('nb_frames', 0)))
    if audio:
        result.update(audio_codec=audio['codec_name'], sample_rate=int(audio['sample_rate']),
                      audio_channels=audio['channels'])
    return result


def inspect_clip(path, qa_dir, sid):
    ensure_tools()
    info = probe(path)
    if not 6 <= info['duration'] <= 20 or info.get('width', 0) < 640 or info.get('fps', 0) <= 0:
        raise RuntimeError(f'{sid}: returned video is unsuitable: {info}')
    run(['ffmpeg', '-v', 'error', '-threads', '2', '-i', path, '-map', '0:v:0', '-f', 'null', '-'])
    qa_dir = Path(qa_dir); qa_dir.mkdir(parents=True, exist_ok=True)
    contact = qa_dir / f'{sid}.jpg'
    run(['ffmpeg', '-y', '-v', 'error', '-threads', '2', '-i', path,
         '-vf', 'fps=2,scale=384:216:force_original_aspect_ratio=decrease,pad=384:216:(ow-iw)/2:(oh-ih)/2,tile=4x4',
         '-frames:v', '1', '-q:v', '3', contact])
    if not contact.exists():
        raise RuntimeError('QA contact sheet was not produced')
    info.update(decoded_ok=True, contact_sheet=f'production/lamkorwan/qa/{sid}.jpg',
                contact_sampling_fps=2, visual_review='pending')
    (qa_dir / f'{sid}.json').write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n')
    return info


def render_python(root):
    """Install dependencies inside the disposable Actions environment, not in Git."""
    root = Path(root)
    fonts = list(Path('/usr/share/fonts').rglob('*CJK*')) if Path('/usr/share/fonts').exists() else []
    if not fonts and not (root / '.cache/fonts/NotoSansCJKsc-Regular.otf').exists():
        run(['sudo', 'apt-get', 'update', '-qq'])
        run(['sudo', 'apt-get', 'install', '-y', '-qq', 'fonts-noto-cjk', 'python3-venv'])
    env = root / 'work/lamkorwan/render-env'
    python = env / 'bin/python'
    if not python.exists():
        run([sys.executable, '-m', 'venv', env])
    run([python, '-m', 'pip', 'install', '--quiet', '--disable-pip-version-check', 'pillow>=10,<13', 'numpy>=1.26,<3', 'faster-whisper>=1.1,<2'])
    return python
