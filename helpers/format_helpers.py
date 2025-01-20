

# def format_github_activity_to_slack(github_activity):
#     if isinstance(github_activity, str):
#         return github_activity
#     sections = []
    
#     # Add commits section if there are commits
#     if github_activity.get('commits'):
#         commit_lines = [f"- [{c['repo']}] {c['message']}" for c in github_activity['commits']]
#         sections.append("*Commits:*\n" + "\n".join(commit_lines))
    
#     # Add PRs section if there are PRs
#     if github_activity.get('pull_requests'):
#         pr_lines = [f"- [{pr['repo']}] {pr['title']} ({pr['status']})" for pr in github_activity['pull_requests']]
#         sections.append("*Pull Requests:*\n" + "\n".join(pr_lines))
    
#     return "Here's your GitHub activity from the past 24 hours:\n" + "\n\n".join(sections)

def format_github_activity_to_slack(github_activity):
    if isinstance(github_activity, str):
        return github_activity
    sections = []
    
    # Add commits section if there are commits
    if github_activity.get('commits'):
        commit_lines = [f"- [{c['repo']}] {c['message']}" for c in github_activity['commits']]
        sections.append("*Commits:*\n" + "\n".join(commit_lines))
    
    # Add PRs section if there are PRs
    if github_activity.get('pull_requests'):
        pr_lines = [f"- {pr['repo']} [{pr['title']}] ({pr['state']})" for pr in github_activity['pull_requests']]
        sections.append("*Pull Requests:*\n" + "\n".join(pr_lines))
    
    return "Here's your GitHub activity from the past 24 hours:\n" + "\n\n".join(sections)

# def format_standup_update_to_slack(standup_update):
#     """
#     Format the standup update to be sent to slack given today's standup update. We give today's update of the previous day so that we can use it to find trends in the github activity.
#     """
#     if isinstance(standup_update, str):
#         return standup_update
#     if isinstance(standup_update, dict) and 'today' in standup_update:
#         standup_update = standup_update['today']
#     if not standup_update:
#         return "No standup updates for today."
#     return f"Here's your standup update:\n" + "\n".join([
#         f"- {u['item']} ({u['status']})" for u in standup_update
#     ])

def format_standup_update_to_slack(standup_update):
    if isinstance(standup_update, str):
        return standup_update
    if not standup_update.get('updates'):
        return "No standup updates for today."
        
    return f"Here's your standup update:\n" + "\n".join([
        f"- {u['item']} ({u['status']})" for u in standup_update['updates']
    ])
