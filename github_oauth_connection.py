import os
from datetime import datetime, timedelta
import requests
from urllib.parse import urlencode, urlparse, parse_qs
from http.server import BaseHTTPRequestHandler
import json
from dotenv import load_dotenv, find_dotenv
from helpers.mongo_db_helpers import save_github_token
from helpers.slack_helpers import send_github_oauth_message

load_dotenv(find_dotenv())

GITHUB_CLIENT_ID = os.environ["GITHUB_CLIENT_ID"]
GITHUB_CLIENT_SECRET = os.environ["GITHUB_CLIENT_SECRET"]
GITHUB_REDIRECT_URI = os.environ["GITHUB_REDIRECT_URI"]

class GitHubCallbackHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        """Handle GitHub OAuth callback."""
        # Parse URL and query parameters
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/github/callback':
            params = parse_qs(parsed_path.query)
            code = params.get('code', [None])[0]
            state = params.get('state', [None])[0]
            channel_id = params.get('channel_id', [None])[0]

            if code and state:
                # Exchange code for access token
                response = requests.post(
                    'https://github.com/login/oauth/access_token',
                    headers={'Accept': 'application/json'},
                    data={
                        'client_id': GITHUB_CLIENT_ID,
                        'client_secret': GITHUB_CLIENT_SECRET,
                        'code': code,
                        'redirect_uri': GITHUB_REDIRECT_URI
                    }
                )
                
                token_data = response.json()

                print("token data is: ", token_data)
                if 'access_token' in token_data:
                    # Store the token
                    save_github_token(state, token_data['access_token'])
                    
                    # Notify user in Slack
                    try:
                        send_github_oauth_message(channel_id=channel_id, user_id=state)
                    except Exception as e:
                        print(f"Error sending Slack message: {e}")
                    
                    # Send success response
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b"Successfully connected GitHub account! You can close this window.")
                    return

            # If we get here, something went wrong
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Error connecting GitHub account")