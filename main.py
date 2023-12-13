#!/usr/bin/env python3
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
    def __init__(self, change_type: str, ticket_number: str, ticket_name: str):
        self.change_type = change_type
        self.ticket_number = ticket_number
        self.ticket_name = ticket_name


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
        inquirer.List('change_type', message="Type of change", choices=['feature', 'fix'], carousel=True,
                      validate=validate_answer),
        inquirer.Text('ticket_number', message="Ticket number (leave empty for NO-TICKET)"),
        inquirer.Text('ticket_name', message="Ticket name", validate=validate_answer)
    ]
    answers = inquirer.prompt(questions)

    change_type = answers["change_type"]

    ticket_number: str = "NO-TICKET"
    if answers["ticket_number"] != "":
        ticket_number = sanitize_string(answers["ticket_number"].upper())

    ticket_name = sanitize_string(answers["ticket_name"].lower())

    branch_name = f"{change_type}/{ticket_number}/{ticket_name}"

    code = run_cmd(f"git checkout -b {branch_name}", cwd)
    if code == 0:
        print(f"Switched to the branch {branch_name}")
        code = run_cmd(f"git push --set-upstream origin {branch_name}", cwd)

        if code == 0:
            code = set_branch_description(cwd, branch_name, change_type, ticket_number, answers["ticket_name"])

    if code != 0:
        print("Something was wrong when executing the commands")

    return code


def set_branch_description(cwd: str, branch_name: str, change_type: str, ticket_number: str, ticket_name: str) -> int:
    branch_description = BranchDescription(change_type, ticket_number, ticket_name)
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
        title=f"{branch_description.change_type}/{branch_description.ticket_number}/{branch_description.ticket_name}",
        body=body,
        draft=True,
    )

    gh.close()

    print("PR has been created")

    return 0


def fill_pr_description_template(template: str, branch_description: BranchDescription) -> str:
    return template.replace("SUP-xxxx", branch_description.ticket_number).replace("{Summary-of-changes}", branch_description.ticket_name)


def get_pr_description_template() -> str:
    if os.path.exists(pr_template_file_path):
        with open(pr_template_file_path, 'r') as file:
            return file.read()
    else:
        print(f"The PR template file does not exist. Going without description.")

    return ""


def parse_arguments():
    parser = argparse.ArgumentParser(prog='Quick Push', description="A helper tool for faster PR creation")

    parser.add_argument("action", choices=["branch", "pr"], help="What to do")
    parser.add_argument("--f", type=str, help="Folder to work in")

    return parser.parse_args()


if __name__ == "__main__":
    main()
