# GitHub OAuth configuration
GITHUB_CLIENT_ID = os.environ["GITHUB_CLIENT_ID"]
GITHUB_CLIENT_SECRET = os.environ["GITHUB_CLIENT_SECRET"]
GITHUB_REDIRECT_URI = "https://your-domain.com/github/oauth/callback"

# Command to start GitHub connection process
@app.command("/connect-github")
def connect_github(ack, body, say):
    ack()
    slack_user_id = body["user_id"]
    
    # Generate GitHub OAuth URL
    params = {
        'client_id': GITHUB_CLIENT_ID,
        'redirect_uri': GITHUB_REDIRECT_URI,
        'scope': 'read:user repo',
        'state': slack_user_id  # Pass slack_user_id as state
    }
    oauth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    
    say({
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Please <{oauth_url}|click here> to connect your GitHub account."
                }
            }
        ]
    })

# OAuth callback handler (needs to be implemented in your web framework)
def handle_github_callback(code, state):
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
    
    access_token = response.json().get('access_token')
    
    # Get GitHub username
    user_response = requests.get(
        'https://api.github.com/user',
        headers={
            'Authorization': f'token {access_token}',
            'Accept': 'application/json'
        }
    )
    github_username = user_response.json().get('login')
    
    # Store in database
    conn = sqlite3.connect('user_connections.db')
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO user_connections
        (slack_user_id, github_access_token, github_username)
        VALUES (?, ?, ?)
    ''', (state, access_token, github_username))
    conn.commit()
    conn.close()

# Function to get GitHub activity for a user
def get_github_activity(slack_user_id):
    conn = sqlite3.connect('user_connections.db')
    c = conn.cursor()
    c.execute('SELECT github_access_token FROM user_connections WHERE slack_user_id = ?',
              (slack_user_id,))
    result = c.fetchone()
    conn.close()
    
    if not result:
        return None
    
    access_token = result[0]
    
    # Get user's events from GitHub
    response = requests.get(
        'https://api.github.com/user/events',
        headers={
            'Authorization': f'token {access_token}',
            'Accept': 'application/json'
        }
    )
    
    # Filter events from the last 24 hours
    events = response.json()
    recent_events = [
        event for event in events
        if (datetime.now() - datetime.strptime(event['created_at'], '%Y-%m-%dT%H:%M:%SZ')).days < 1
    ]
    
    return recent_events

# Command to test GitHub connection
@app.command("/test-github-connection")
def test_connection(ack, body, say):
    ack()
    slack_user_id = body["user_id"]
    
    activity = get_github_activity(slack_user_id)
    if activity is None:
        say("You haven't connected your GitHub account yet. Use /connect-github to get started!")
    else:
        say(f"Successfully retrieved {len(activity)} events from your GitHub account!")