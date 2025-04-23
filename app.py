from flask import Flask, request, redirect, session, render_template
import requests
import urllib.parse
import os
from flask_cors import CORS  # Assure-toi que cette ligne est présente

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Active CORS pour toutes les origines

app.secret_key = 'secret_for_session'

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
PLAYLIST_ID = os.getenv("SPOTIFY_PLAYLIST_ID")

SPOTIFY_AUTH_URL = 'https://accounts.spotify.com/authorize'
SPOTIFY_TOKEN_URL = 'https://accounts.spotify.com/api/token'
SPOTIFY_API_BASE_URL = 'https://api.spotify.com/v1'
SCOPE = 'playlist-modify-public playlist-modify-private'

@app.route('/')
def index():
    if 'access_token' not in session:
        auth_url = f"{SPOTIFY_AUTH_URL}?response_type=code&client_id={CLIENT_ID}&scope={urllib.parse.quote(SCOPE)}&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
        return redirect(auth_url)
    return "Le backend est prêt. Tu peux accéder au site Netlify."

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "❌ Code manquant dans la requête", 400

    payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }

    try:
        res = requests.post(SPOTIFY_TOKEN_URL, data=payload)
        res.raise_for_status()
        res_data = res.json()

        if 'access_token' not in res_data:
            return f"❌ Token d'accès manquant. Réponse complète: {res_data}", 500

        session['access_token'] = res_data['access_token']
        session['refresh_token'] = res_data.get('refresh_token')

        return redirect('/')
    except requests.exceptions.HTTPError as e:
        return f"❌ Erreur HTTP lors de la demande de token: {e.response.status_code} - {e.response.text}", 500
    except requests.exceptions.RequestException as e:
        return f"❌ Erreur lors de la communication avec Spotify: {str(e)}", 500
    except Exception as e:
        return f"❌ Une erreur inattendue s'est produite: {str(e)}", 500

@app.route('/add_song', methods=['POST'])
def add_song():
    token = session.get('access_token')
    if not token:
        return redirect('/')

    track = request.form.get('track')
    headers = {'Authorization': f'Bearer {token}'}
    search_url = f"{SPOTIFY_API_BASE_URL}/search"
    params = {'q': track, 'type': 'track', 'limit': 1}
    search_res = requests.get(search_url, headers=headers, params=params).json()

    try:
        track_uri = search_res['tracks']['items'][0]['uri']
        add_url = f"{SPOTIFY_API_BASE_URL}/playlists/{PLAYLIST_ID}/tracks"
        add_res = requests.post(add_url, headers=headers, json={"uris": [track_uri]})
        if add_res.status_code == 201:
            return "✅ Morceau ajouté à la playlist !"
        else:
            return f"❌ Erreur Spotify : {add_res.text}", 400
    except (IndexError, KeyError):
        return "❌ Morceau introuvable !", 404

if __name__ == '__main__':
    port = os.getenv("PORT", 5000)
    app.run(host="0.0.0.0", port=port)
