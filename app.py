from flask import Flask, jsonify, Response, stream_with_context
from flask_cors import CORS
import yt_dlp
import requests
import click
import ffmpeg

app = Flask(__name__)
CORS(app)  

STREAMS = {
    "1": ("Lofi Girl", "https://www.youtube.com/watch?v=jfKfPfyJRdk"),
    "2": ("Asian Lofi", "https://www.youtube.com/watch?v=Na0w3Mz46GA"),
    "3": ("Dark Ambient Radio", "https://www.youtube.com/watch?v=S_MOd40zlYU"),
    "4": ("Synthwave Radio", "https://www.youtube.com/watch?v=4xDzrJKXOOY"),
    "5": ("Rap", "https://www.youtube.com/watch?v=0DztVOeomsk"),
    "6": ("Chillhop", "https://www.youtube.com/watch?v=5yx6BWlEVcY"),
    "7": ("Coffee Shop Radio", "https://www.youtube.com/watch?v=lP26UCnoH9s"),
    "8": ("Tavern", "https://www.youtube.com/watch?v=vK5VwVyxkbI"),
}

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
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        audio_url = info['url']
        return audio_url

@app.route('/stream/<stream_id>')
def get_stream(stream_id):
    if stream_id not in STREAMS:
        return jsonify({"error": "Invalid stream ID"}), 400
    
    stream_name, youtube_url = STREAMS[stream_id]
    try:
        audio_url = get_audio_url(youtube_url)
        return jsonify({
            "stream_name": stream_name,
            "audio_url": f"/proxy_stream/{stream_id}"  
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/proxy_stream/<stream_id>')
def proxy_stream(stream_id):
    if stream_id not in STREAMS:
        return jsonify({"error": "Invalid stream ID"}), 400
    
    youtube_url = STREAMS[stream_id][1]
    audio_url = get_audio_url(youtube_url)
    
    def generate():
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

    return Response(stream_with_context(generate()), mimetype="audio/mpeg")

@app.route('/streams')
def list_streams():
    return jsonify({k: v[0] for k, v in STREAMS.items()})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
