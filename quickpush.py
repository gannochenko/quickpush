#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import re
import inquirer
import subprocess
from inquirer import errors
import json
import base64
from github import Github
from github import Auth

pr_template_file_path = "./.github/pull_request_template.md"

class BranchDescription:
    def __init__(self, change_type: str, issue_number: str, issue_title: str, commit_prefix: str, link_to_rfc: str, link_to_slack_thread: str):
        self.change_type = change_type
        self.issue_number = issue_number
        self.issue_title = issue_title
        self.commit_prefix = commit_prefix
        self.link_to_rfc = link_to_rfc
        self.link_to_slack_thread = link_to_slack_thread


class Remote:
    def __init__(self, repo_name: str, owner: str):
        self.repo_name = repo_name
        self.owner = owner


def main() -> None:
    args = parse_arguments()

    code: int = 0

    try:
        if args.action == "branch":
            code = branch(args.f)
        elif args.action == "pr":
            code = pr(args.f)
    except Exception as e:
        print(f"Error occurred: {e}")
        code = 1

    exit(code)


def branch(cwd: str) -> int:
    questions = [
        inquirer.List('change_type', message="Type of change", choices=['feat', 'fix', 'chore', 'test', 'tmp'], carousel=True,
                      validate=validate_answer),
        inquirer.Text('commit_prefix', message="Commit prefix"),
        inquirer.Text('issue_number', message="Issue number"),
        inquirer.Text('link_to_rfc', message="Link to RFC"),
        inquirer.Text('link_to_slack_thread', message="Link to Slack thread"),
        inquirer.Text('issue_title', message="Issue title", validate=validate_answer)
    ]
    answers = inquirer.prompt(questions)

    change_type = answers["change_type"]

    issue_number: str = ""
    if answers["issue_number"] != "":
        issue_number = sanitize_string(answers["issue_number"].upper())

    issue_title = sanitize_string(answers["issue_title"].lower())

    branch_name = f"{change_type}/{issue_title}"
    if issue_number != "":
        branch_name = f"{change_type}/{issue_number}/{issue_title}"

    code = run_cmd(f"git checkout -b {branch_name}", cwd)
    if code == 0:
        print(f"Switched to the branch {branch_name}")
        code = run_cmd(f"git push --set-upstream origin {branch_name}", cwd)

        if code == 0:
            code = set_branch_description(cwd, branch_name, change_type, issue_number, answers["issue_title"], answers["commit_prefix"], answers["link_to_rfc"], answers["link_to_slack_thread"])

    if code != 0:
        print("Something was wrong when executing the commands")

    return code


def set_branch_description(cwd: str, branch_name: str, change_type: str, issue_number: str, issue_title: str, commit_prefix: str, link_to_rfc: str, link_to_slack_thread: str) -> int:
    branch_description = BranchDescription(change_type, issue_number, issue_title, commit_prefix, link_to_rfc, link_to_slack_thread)
    branch_description_encoded = base64_encode(json.dumps(branch_description.__dict__))

    return run_cmd(f"git config branch.{branch_name}.description {branch_description_encoded}", cwd)


def get_branch_description(cwd: str, branch_name: str) -> BranchDescription:
    branch_description = run_cmd_get_stdout(f"git config \"branch.{branch_name}.description\"", cwd)
    if branch_description == "":
        raise Exception("current branch misses the description")

    branch_description = base64_decore(branch_description.rstrip("\r\n").rstrip("\n"))
    branch_description_json = json.loads(branch_description)

    return BranchDescription(**branch_description_json)


def get_remote(cwd: str) -> Remote:
    remote = run_cmd_get_stdout(f"git config --get remote.origin.url", cwd)
    pattern = r"git@github\.com:([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)\.git"

    matches = re.findall(pattern, remote)

    return Remote(repo_name=matches[0][1], owner=matches[0][0])


def sanitize_string(value: str) -> str:
    return re.sub(r'[^a-zA-Z0-9-]', '', re.sub(r'\s+', '-', re.sub(r'_', '-', value.strip())))


def validate_answer(_, current) -> bool:
    if current.strip() == "":
        raise errors.ValidationError('', reason='The answer should not be empty.')

    return True


def base64_encode(value: str) -> str:
    return base64.b64encode(value.encode('utf-8')).decode('utf-8')


def base64_decore(value: str) -> str:
    return base64.b64decode(value.encode('utf-8')).decode('utf-8')


def run_cmd(cmd: str, cwd: str) -> int:
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ,
                            cwd=cwd)
    return result.returncode


def run_cmd_get_stdout(cmd: str, cwd: str) -> str:
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ,
                            cwd=cwd)
    return result.stdout


def pr(cwd: str) -> int:
    branch_name = run_cmd_get_stdout("git branch --show-current", cwd).rstrip("\r\n").rstrip("\n")
    branch_description = get_branch_description(cwd, branch_name)
    remote = get_remote(cwd)

    body = ""
    pr_description = get_pr_description_template()
    if pr_description != "":
        body = fill_pr_description_template(pr_description, branch_description)

    token = os.getenv("GITHUB_TOKEN")
    if token == "":
        print("No github token found. Make sure the GITHUB_TOKEN is defined")
        return 1

    auth = Auth.Token(os.getenv("GITHUB_TOKEN"))
    gh = Github(auth=auth)

    gh.get_repo(f"{remote.owner}/{remote.repo_name}").create_pull(
        base="master",
        head=branch_name,
        title=branch_description.issue_title,
        body=body,
        draft=True,
    )

    gh.close()

    print("PR has been created")

    return 0


def fill_pr_description_template(template: str, branch_description: BranchDescription) -> str:
    # Replace RFC link
    rfc_link = branch_description.link_to_rfc if branch_description.link_to_rfc != "" else "none"
    template = template.replace("<!-- Link to RFC -->", f"[{rfc_link}]({rfc_link})")

    # Replace Slack thread link
    slack_link = branch_description.link_to_slack_thread if branch_description.link_to_slack_thread != "" else "none"
    template = template.replace("<!-- Link to Slack thread -->", f"[{slack_link}]({slack_link})")

    # Replace issue link
    if branch_description.issue_number != "":
        issue_link = f"https://github.com/framer/company/issues/{branch_description.issue_number}"
        issue_text = branch_description.issue_number
        template = template.replace("<!-- Link to issue -->", f"[{issue_text}]({issue_link})")
    else:
        template = template.replace("<!-- Link to issue -->", "none")


    return template


def get_pr_description_template() -> str:
    current_dir = os.getcwd()
    
    while current_dir != "/":
        template_path = os.path.join(current_dir, pr_template_file_path)
        if os.path.exists(template_path):
            with open(template_path, 'r') as file:
                return file.read()
        current_dir = os.path.dirname(current_dir)
    
    print(f"The PR template file does not exist in any parent directory. Going without description.")
    return ""


def parse_arguments():
    parser = argparse.ArgumentParser(prog='Quick Push', description="A helper tool for faster PR creation")

    parser.add_argument("action", choices=["branch", "pr"], help="What to do")
    parser.add_argument("--f", type=str, help="Folder to work in")

    return parser.parse_args()


if __name__ == "__main__":
    main()
