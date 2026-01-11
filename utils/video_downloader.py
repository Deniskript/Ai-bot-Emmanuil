"""
Утилиты для скачивания видео по ссылкам
"""
import os
import tempfile
from pathlib import Path
import yt_dlp
import subprocess


async def download_video_from_url(url: str) -> str:
    """
    Скачивает видео по ссылке используя yt-dlp Python модуль
    Поддерживает: TikTok, Instagram Reels, YouTube Shorts
    
    Returns:
        str: Путь к скачанному файлу
    """
    # Создаём временную директорию
    temp_dir = tempfile.mkdtemp(prefix="viral_")
    output_template = os.path.join(temp_dir, "video.%(ext)s")
    
    try:
        # Проверяем платформу
        is_instagram = "instagram.com" in url.lower()
        is_tiktok = "tiktok.com" in url.lower()
        is_youtube = "youtube.com" in url.lower() or "youtu.be" in url.lower()
        
        # Настройки yt-dlp
        ydl_opts = {
            'format': 'best[height<=720][ext=mp4]/best[ext=mp4]/best',
            'outtmpl': output_template,
            'max_filesize': 50 * 1024 * 1024,  # 50MB
            'no_warnings': True,
            'quiet': True,
            'no_color': True,
            'extract_flat': False,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        
        # Дополнительные параметры для Instagram
        if is_instagram:
            ydl_opts.update({
                'extractor_args': {
                    'instagram': {
                        'skip': ['dash']
                    }
                },
                'nocheckcertificate': True,
            })
        
        # Дополнительные параметры для TikTok
        if is_tiktok:
            ydl_opts.update({
                'extractor_args': {
                    'tiktok': {
                        'api_hostname': 'api22-normal-c-useast2a.tiktokv.com'
                    }
                }
            })
        
        # Скачиваем видео
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                
                if not info:
                    raise Exception("Не удалось получить информацию о видео")
                
                # Получаем путь к скачанному файлу
                filename = ydl.prepare_filename(info)
                
                if not os.path.exists(filename):
                    raise Exception("Файл не найден после скачивания")
                
                return filename
                
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e).lower()
                
                # Специфичные ошибки для разных платформ
                if is_instagram and any(word in error_msg for word in ['login', 'private', 'not available', 'unable to extract']):
                    raise Exception("Instagram временно недоступен. Попробуйте загрузить видео напрямую через кнопку '📤 Загрузить видео'")
                elif 'private' in error_msg or 'unavailable' in error_msg:
                    raise Exception("Видео недоступно (приватное или удалено)")
                elif 'unsupported url' in error_msg:
                    raise Exception("Эта платформа не поддерживается. Попробуйте TikTok, YouTube Shorts или загрузите видео напрямую")
                else:
                    raise Exception(f"Ошибка скачивания: {str(e)[:200]}")
        
    except Exception as e:
        # Очищаем временные файлы при ошибке
        if os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise e


async def extract_key_frames(video_path: str, num_frames: int = 8) -> list:
    """
    Извлекает ключевые кадры из видео
    
    Args:
        video_path: Путь к видео файлу
        num_frames: Количество кадров для извлечения
    
    Returns:
        list: Список путей к извлечённым кадрам
    """
    frames_dir = tempfile.mkdtemp(prefix="frames_")
    frame_paths = []
    
    try:
        # Получаем длительность видео
        duration_cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        
        duration_result = subprocess.run(
            duration_cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        try:
            duration = float(duration_result.stdout.strip())
        except:
            duration = 30  # Fallback на 30 секунд
        
        # Вычисляем интервал между кадрами
        interval = duration / (num_frames + 1)
        
        # Извлекаем кадры
        for i in range(1, num_frames + 1):
            timestamp = interval * i
            frame_path = os.path.join(frames_dir, f"frame_{i:02d}.jpg")
            
            cmd = [
                "ffmpeg",
                "-ss", str(timestamp),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",  # Качество JPEG (2 = высокое)
                "-y",  # Перезаписывать если существует
                frame_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=10
            )
            
            if result.returncode == 0 and os.path.exists(frame_path):
                frame_paths.append(frame_path)
        
        if not frame_paths:
            raise Exception("No frames extracted")
        
        return frame_paths
        
    except Exception as e:
        # Очищаем при ошибке
        if os.path.exists(frames_dir):
            import shutil
            shutil.rmtree(frames_dir, ignore_errors=True)
        raise Exception(f"Frame extraction error: {e}")


def cleanup_temp_files(paths: list):
    """Удаляет временные файлы и директории"""
    import shutil
    
    for path in paths:
        try:
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                # Если это файл в директории, удаляем директорию
                parent = os.path.dirname(path)
                if parent and os.path.exists(parent):
                    shutil.rmtree(parent, ignore_errors=True)
        except:
            pass
