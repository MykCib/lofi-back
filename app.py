from flask import Flask, jsonify, Response, stream_with_context
from flask_cors import CORS
import yt_dlp
import requests
import click
import ffmpeg
import subprocess
import random
import os
import logging

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_streams(channel_url, prefix, remove_last=0):
    try:
        cmd = f"yt-dlp -j --flat-playlist '{channel_url}' | jq -r '[.title, .url] | @tsv'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        streams = {}
        lines = result.stdout.strip().split('\n')
        if remove_last > 0:
            lines = lines[:-remove_last]
        for i, line in enumerate(lines, start=1):
            title, url = line.split('\t')
            streams[f"{prefix}{i}"] = (title, url)
        return streams
    except subprocess.CalledProcessError as e:
        logger.error(f"Error loading streams for {prefix}: {e}")
        return {}

logger.info("Loading streams...")
STREAMS = {}
STREAMS.update(load_streams("https://www.youtube.com/@LofiGirl/streams", "LG", remove_last=2))
STREAMS.update(load_streams("https://www.youtube.com/@ChillhopMusic/streams", "CH"))
STREAMS.update(load_streams("https://www.youtube.com/@IvyStationRecords/streams", "IS"))


logger.info(f"Total number of streams loaded: {len(STREAMS)}")
for key, value in STREAMS.items():
    logger.info(f"Stream {key}: {value[0]}")

def get_audio_url(youtube_url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0'
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            audio_url = info['url']
            return audio_url
    except Exception as e:
        logger.error(f"Error getting audio URL: {e}")
        raise

@app.route('/proxy_stream/<stream_id>')
def proxy_stream(stream_id):
    if stream_id not in STREAMS:
        return jsonify({"error": "Invalid stream ID"}), 400
    
    try:
        youtube_url = STREAMS[stream_id][1]
        
        audio_url = get_audio_url(youtube_url)
        
        def generate():
            try:
                process = (
                    ffmpeg
                    .input(audio_url)
                    .output('pipe:', format='mp3', acodec='libmp3lame', ac=2, ar='44100', loglevel='quiet')
                    .run_async(pipe_stdout=True)
                )
                
                for chunk in iter(lambda: process.stdout.read(4096), b''):
                    yield chunk
                
                process.stdout.close()
                process.wait()
            except Exception as e:
                logger.error(f"Error in generate: {e}")
                raise

        return Response(stream_with_context(generate()), mimetype="audio/mpeg")
    except Exception as e:
        logger.error(f"Error in proxy_stream: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/streams')
def list_streams():
    return jsonify({k: v[0] for k, v in STREAMS.items()})

if __name__ == "__main__":
    logger.info("Starting the application...")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
