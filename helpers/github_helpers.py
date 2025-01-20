import os
from datetime import datetime, timedelta
import requests
from urllib.parse import urlencode
from dotenv import load_dotenv, find_dotenv
from .mongo_db_helpers import get_github_token

load_dotenv(find_dotenv())

GITHUB_CLIENT_ID = os.environ["GITHUB_CLIENT_ID"]
GITHUB_REDIRECT_URI = os.environ["GITHUB_REDIRECT_URI"]

def generate_github_oauth_url(state, channel_id):
    """Generate GitHub OAuth URL with state parameter."""
    params = {
        'client_id': GITHUB_CLIENT_ID,
        'redirect_uri': GITHUB_REDIRECT_URI,
        'scope': 'repo user',
        'state': state,
        'channel_id': channel_id
    }
    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"

def get_github_activity(slack_user_id, date=None):
    """Get GitHub activity for a connected user."""
    github_token = get_github_token(slack_user_id)
    if not github_token:
        return "GitHub account not connected. Use /connect-github to connect your account."
    
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # Get user information
    user_response = requests.get('https://api.github.com/user', headers=headers)
    if user_response.status_code != 200:
        return "Error accessing GitHub account"
    
    user_data = user_response.json()
    username = user_data['login']
    
    # Get user's repositories
    repos_response = requests.get('https://api.github.com/user/repos', headers=headers)
    if repos_response.status_code != 200:
        return "Error accessing repositories"
    
    recent_commits = []
    recent_prs = []
    since_date = date if date else (datetime.now() - timedelta(hours=24)).isoformat()
    
    for repo in repos_response.json():
        repo_name = repo['name']
        repo_full_name = repo['full_name']
        
        # Get commits
        commits_url = f'https://api.github.com/repos/{repo_full_name}/commits'
        commits_params = {
            'author': username,
            'since': since_date
        }
        commits_response = requests.get(commits_url, headers=headers, params=commits_params)
        
        if commits_response.status_code == 200:
            for commit in commits_response.json():
                recent_commits.append({
                    'repo': repo_name,
                    'message': commit['commit']['message'],
                    'timestamp': commit['commit']['author']['date']
                })
        
        # Get PRs
        prs_url = f'https://api.github.com/repos/{repo_full_name}/pulls'
        prs_params = {
            'state': 'all',
            'sort': 'updated',
            'direction': 'desc'
        }
        prs_response = requests.get(prs_url, headers=headers, params=prs_params)
        
        if prs_response.status_code == 200:
            for pr in prs_response.json():
                pr_updated = datetime.strptime(pr['updated_at'], '%Y-%m-%dT%H:%M:%SZ')
                if pr_updated > datetime.now() - timedelta(days=1):
                    recent_prs.append({
                        'repo': repo_name,
                        'title': pr['title'],
                        'state': pr['state'],
                        'url': pr['html_url']
                    })
    
    return {
        'commits': recent_commits,
        'pull_requests': recent_prs
    }