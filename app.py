from flask import Flask, request, redirect, session
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


def is_token_valid(token):
    """
    Vérifie si le token d'accès est valide en effectuant une requête à l'API Spotify.
    """
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get('https://api.spotify.com/v1/me', headers=headers)
    
    if response.status_code == 200:
        return True  # Token valide
    elif response.status_code == 401:
        return False  # Token invalide ou expiré
    else:
        return None  # Autre erreur


def refresh_access_token(refresh_token):
    """
    Rafraîchit le token d'accès à l'aide du refresh token.
    """
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    
    response = requests.post(SPOTIFY_TOKEN_URL, data=payload)
    
    if response.status_code == 200:
        new_data = response.json()
        return new_data.get('access_token')
    else:
        return None  # Le rafraîchissement du token a échoué


def get_valid_access_token():
    """
    Vérifie si le token d'accès est valide et le rafraîchit si nécessaire.
    """
    access_token = session.get('access_token')
    if not access_token:
        return None  # Pas de token d'accès dans la session
    
    if is_token_valid(access_token):
        return access_token  # Token valide
    
    refresh_token = session.get('refresh_token')
    if not refresh_token:
        return None  # Pas de refresh token disponible

    new_access_token = refresh_access_token(refresh_token)
    if new_access_token:
        session['access_token'] = new_access_token
        return new_access_token  # Retourne le nouveau token valide
    
    return None  # Le token d'accès et le refresh token sont tous deux invalides


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
    token = get_valid_access_token()  # Vérifie et récupère un token valide
    if not token:
        return redirect('/')  # Redirige l'utilisateur vers la page d'authentification si aucun token valide
    
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
