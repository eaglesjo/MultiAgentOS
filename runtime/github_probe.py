"""Probe VYRELON's local GitHub access."""

from integrations.github.gateway import GitHubGatewayClient


def probe(repository: str) -> dict:
    client = GitHubGatewayClient()
    repo = client.get_repository(repository)
    branch = client.get_branch(repository, repo.default_branch)
    return {
        "repository": repo.full_name,
        "private": repo.private,
        "default_branch": repo.default_branch,
        "default_branch_sha": branch.sha,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("repository")
    args = parser.parse_args()
    print(probe(args.repository))
