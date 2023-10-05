#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import inquirer


def main() -> None:
    exit(0)


def parse_arguments():
    parser = argparse.ArgumentParser(prog='Quick Push Ⓡ', description="A helper tool for faster PR creation")

    parser.add_argument("country", type=str, help="The country name or code")
    parser.add_argument("action", choices=["database", "cluster"], help="What to do")
    parser.add_argument("--rw", action="store_true", help="If set to TRUE, the connection will be writable")

    return parser.parse_args()


if __name__ == "__main__":
    main()
