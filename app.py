from flask import Flask, request, redirect, session, render_template
import requests
import urllib.parse
import os

app = Flask(__name__)
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
    # Vérifie si l'utilisateur est déjà authentifié avec Spotify (token d'accès dans la session)
    if 'access_token' not in session:
        # Si non, redirige l'utilisateur vers la page d'authentification Spotify
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
        res.raise_for_status()  # Cela lève une exception si la réponse n'est pas un code 2xx
        res_data = res.json()

        # Log détaillé pour voir la réponse de Spotify
        app.logger.debug(f"Réponse de Spotify: {res_data}")

        # Vérifie si l'access_token est présent dans la réponse
        if 'access_token' not in res_data:
            return f"❌ Token d'accès manquant. Réponse complète: {res_data}", 500

        # Si la réponse est correcte, enregistre le token d'accès
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
    # Vérifie si l'utilisateur est authentifié (token d'accès présent)
    token = session.get('access_token')
    if not token:
        # Si aucun token, redirige l'utilisateur vers la page d'authentification
        return redirect('/')

    # Récupère le titre + artiste de la chanson envoyée
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
    port = os.getenv("PORT", 5000)  # Utilise le port fourni par Render ou 5000 par défaut
    app.run(host="0.0.0.0", port=port)
