import requests

class GithubAgent:
    def __init__(self, token: str):
        self.token = token
        self.headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        
    def create_pull_request(self, repo: str, title: str, body: str, head: str, base="main"):
        url = f"https://api.github.com/repos/{repo}/pulls"
        payload = {"title": title, "body": body, "head": head, "base": base}
        resp = requests.post(url, headers=self.headers, json=payload)
        return resp.json()
