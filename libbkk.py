import argparse
import collections
import configparser
from datetime import datetime
import grp, pwd
from fnmatch import fnmatch
import hashlib
from math import ceil
import os
import re
import sys
import zlib

argparser = argparse.ArgumentParser(description="The simple content tracker")
argsubparsers = argparser.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True

def main(argv=sys.argv[1:]):
    args = argparser.parse_args(argv)
    match args.command:
        case "add" : cmd_add(args)
        case "cat-file" : cmd_cat_file(args)
        case "check-ignore" : cmd_check_ignore(args)
        case "checkout" : cmd_checkout(args)
        case "commit" : cmd_commit(args)
        case "hash-object" : cmd_hash_object(args)
        case "init" : cmd_init(args)
        case "log" : cmd_log(args)
        case "ls-files" : cmd_ls_files(args)
        case "ls-tree" : cmd_ls_tree(args)
        case "rev-parse" : cmd_rev_parse(args)
        case "rm" : cmd_rm(args)
        case "show-ref" : cmd_show_ref(args)
        case "status" : cmd_status(args)
        case "tag" : cmd_tag(args)
        case _ : print("Bad command.")

class GitRepository(object):
    """A git repository"""

    worktree = None
    gitdir = None
    conf = None

    def __init__(self, path, force=False):
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception(f"Not a git repository {path}")

        # Read configuration file in .git/config
        self.conf = configparser.ConfigParser()
        cf = GitRepository.repo_file(self, "config")

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Configuration file missing")

        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception(f"Unsupported repositoryformatversion {vers}")

    @staticmethod
    def repo_path(repo, *path):
        """Compute path under repo's gitdir."""
        return os.path.join(repo.gitdir, *path)

    @staticmethod
    def repo_file(repo, *path, mkdir=False):
        """Same as repo_path but create dirname (*path) if absent."""
        if GitRepository.repo_dir(repo, *path[:-1], mkdir=mkdir):
            return GitRepository.repo_path(repo, *path)

    @staticmethod
    def repo_dir(repo, *path, mkdir=False):
        """Same as repo_path, but mkdir *path if absent if mkdir."""
        path = GitRepository.repo_path(repo, *path)

        if os.path.exists(path):
            if os.path.isdir(path):
                return path
            else:
                raise Exception(f"Not a directory {path}")

        if mkdir:
            os.makedirs(path)
            return path
        else:
            return None

    @staticmethod
    def repo_create(path):
        """Create a new repository at path."""
        repo = GitRepository(path, True)

        # First, we make sure the path either doesn't exist or is an empty dir.
        if os.path.exists(repo.worktree):
            if not os.path.isdir(repo.worktree):
                raise Exception(f"{path} is not a directory")
            if os.path.exists(repo.gitdir) and os.listdir(repo.gitdir):
                raise Exception(f"{path} is not empty!")
        else:
            os.makedirs(repo.worktree)

        assert GitRepository.repo_dir(repo, "branches", mkdir=True)
        assert GitRepository.repo_dir(repo, "objects", mkdir=True)
        assert GitRepository.repo_dir(repo, "refs", "tags", mkdir=True)
        assert GitRepository.repo_dir(repo, "refs", "heads", mkdir=True)

        # .git/description
        with open(GitRepository.repo_file(repo, "description"), "w") as f:
            f.write("Unnamed repository; edit this file 'description' to name the repository.\n")

        # .git/HEAD
        with open(GitRepository.repo_file(repo, "HEAD"), "w") as f:
            f.write("ref: refs/heads/master\n")

        with open(GitRepository.repo_file(repo, "config"), "w") as f:
            config = GitRepository.repo_default_config()
            config.write(f)

        return repo

    @staticmethod
    def repo_default_config():
        ret = configparser.ConfigParser()

        ret.add_section("core")
        ret.set("core", "repositoryformatversion", "0")
        ret.set("core", "filemode", "false")
        ret.set("core", "bare", "false")

        return ret

# Argument parser for 'init' command
argsp = argsubparsers.add_parser("init", help="Initialize a new, empty repository")
argsp.add_argument("path",
                    metavar="directory",
                    nargs="?",
                    default=".",
                    help="Where to create the repository.")

def cmd_init(args):
    GitRepository.repo_create(args.path)

