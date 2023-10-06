#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import re
import inquirer
import subprocess
from inquirer import errors


def main() -> None:
    args = parse_arguments()

    code: int = 0
    if args.action == "branch":
        code = branch(args.f)
    elif args.action == "push":
        code = push(args.f)

    exit(code)


def branch(cwd: str) -> int:
    questions = [
        inquirer.List('change_type', message="Type of change", choices=['feature', 'fix'], carousel=True,
                      validate=validate_answer),
        inquirer.Text('ticket_number', message="Ticket number", validate=validate_answer),
        inquirer.Text('ticket_name', message="Ticket name", validate=validate_answer)
    ]
    answers = inquirer.prompt(questions)

    change_type = answers["change_type"]
    ticket_number = sanitize_string_uc(answers["ticket_number"])
    ticket_name = sanitize_string(answers["ticket_name"])

    branch_name = f"{change_type}/{ticket_number}/{ticket_name}"

    code = run_cmd(f"git checkout -b {branch_name}", cwd)
    if code == 0:
        print(f"Switched to the branch {branch_name}")
        code = run_cmd(f"git push --set-upstream origin {branch_name}", cwd)

    if code != 0:
        print("Something was wrong when executing the commands")

    return code


def sanitize_string_uc(value: str) -> str:
    return re.sub(r'[^A-Z0-9_-]', '', re.sub(r'\s+', '-', value.strip().upper()))


def sanitize_string(value: str) -> str:
    return re.sub(r'[^a-z0-9_-]', '', re.sub(r'\s+', '-', value.strip().lower()))


def validate_answer(_, current) -> bool:
    if current.strip() == "":
        raise errors.ValidationError('', reason='The answer should not be empty.')

    return True


def run_cmd(cmd: str, cwd: str) -> int:
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ, cwd=cwd)
    return result.returncode


def push(cwd: str) -> int:
    print("Push!")
    return 0


def parse_arguments():
    parser = argparse.ArgumentParser(prog='Quick Push', description="A helper tool for faster PR creation")

    parser.add_argument("action", choices=["branch", "push"], help="What to do")
    parser.add_argument("--f", type=str, help="Folder to work in")

    return parser.parse_args()


if __name__ == "__main__":
    main()
