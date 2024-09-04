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
        """Same as repo_path, but mkdir *path if absent."""
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

def repo_find(path=".", required=True):
    path = os.path.realpath(path)
    
    if os.path.isdir(os.path.join(path, ".git")):
        return GitRepository(path)
    
    parent = os.path.realpath(os.path.join(path, ".."))
    
    if parent == path:
        if required:
            raise Exception("No git directory")
        else:
            return None
        
    return repo_find(parent, required)

class GitObject(object):
    def __init__(self, data=None):
        if data is not None:
            self.deserialize(data)
        else:
            self.init()
    
    def serialize(self):
        """This function Must be implemented by subclasses.
        It must read the object's contents from self.data, a byte string, and do whatever it takes to convert it into a meaningful representation. What exactly that means depends on each subclass.
        """
        raise Exception("Unimplemented!")
    
    def deserialize(self, data):
        raise Exception("Unimplemented!")
    
    def init(self):
        pass  # Just do nothing. This is a reasonable default!
    
def object_read(repo, sha):
    """
    Read object sha from Git repository repo. Return a GitObject whose exact type depends on the object.
    """
    path = GitRepository.repo_file(repo, "objects", sha[0:2], sha[2:])
    
    if not os.path.isfile(path):
        return None
    
    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())
        
        # Read object type
        x = raw.find(b' ')
        fmt = raw[0:x]
        
        # Read and validate object size
        y = raw.find(b'\x00', x)
        size = int(raw[x:y].decode("ascii"))
        if size != len(raw) - y - 1:
            raise Exception(f"Malformed object {sha}: bad length")
        
        match fmt:
            case b'commit': c = GitCommit
            case b'tree': c = GitTree
            case b'tag': c = GitTag
            case b'blob': c = GitBlob
            case _:
                raise Exception(f"Unknown type {fmt.decode('ascii')} for object {sha}")
            
        return c(raw[y + 1:])
    
def object_write(obj, repo=None):
    # Serialize object data
    data = obj.serialize()
    # Add header
    result = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data
    # Compute hash
    sha = hashlib.sha1(result).hexdigest()
    
    if repo:
        # Compute path
        path = GitRepository.repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)
        
        if not os.path.exists(path):
            with open(path, 'wb') as f:
                # Compress and write
                f.write(zlib.compress(result))
    
    return sha

class GitBlob(GitObject):
    fmt = b'blob'
    
    def serialize(self):
        return self.blobdata
    
    def deserialize(self, data):
        self.blobdata = data
        
argsp = argsubparsers.add_parser("cat-file", help="Provide content of repository objects")

argsp.add_argument("type",
                   metavar="type",
                   choices=["blob", "commit", "tag", "tree"],
                   help="Specify the type")

argsp.add_argument("object", 
                   metavar="object",
                   help="The object to display")

def cmd_cat_file(args):
    repo = repo_find()
    cat_file(repo, args.object, fmt=args.type.encode())
    
def cat_file(repo, obj, fmt=None):
    obj = object_read(repo, object_find(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialize())
    
def object_find(repo, name, fmt=None, follow=True):
    return name

argsp = argsubparsers.add_parser(
    "hash-object",
    help="Compute object ID and optionally creates a blob from a file")

argsp.add_argument("-t",
                   metavar="type",
                   dest="type",
                   choices=["blob", "commit", "tag", "tree"],
                   default="blob",
                   help="Specify the type")

argsp.add_argument("-w",
                   dest="write",
                   action="store_true",
                   help="Actually write the object into the database")

argsp.add_argument("path",
                   help="Read object from <file>")

def cmd_hash_object(args):
    if args.write:
        repo = repo_find()
    else:
        repo = None
        
    with open(args.path, "rb") as fd:
        sha = object_hash(fd, args.type.encode(), repo)
        print(sha)
        
def object_hash(fd, fmt, repo=None):
    """
    Hash object, writing it to repo if provided.
    """
    data = fd.read()
    
    match fmt:
        case b'commit': obj = GitCommit(data)
        case b'tree': obj = GitTree(data)
        case b'tag': obj = GitTag(data)
        case b'blob': obj = GitBlob(data)
        case _: raise Exception(f"Unknown type {fmt}!")
        
    return object_write(obj, repo)

def kvlm_parse(raw, start=0, dct=None):
    if not dct:
        dct = collections.OrderedDict()
        # You CANNOT declare the argument as dct=OrderedDict() or all
        # call to the functions will endlessly grow the same dict.

    # This function is recursive: it reads a key/value pair, then call
    # itself back with the new position.  So we first need to know
    # where we are: at a keyword, or already in the messageQ
    
    # We search for the next space and the next newline
    spc = raw.find(b' ', start)
    nl = raw.find(b'\n', start)
    
    # If space appears before newline, we have a keyword. Otherwise, its the final message, which we jest read to the end of the file.
    
    # Base case
    # =========
    # If newline appears first(or there's no space at all, in which case find returns -1), we assume a blank line. A blank line means the ramainder of the data is the message. We store it in the dictionary, with None as the key, and return.
    if(spc < 0) or (nl < spc):
        assert nl == start
        dct[None] = raw[start+1:]
        return dct
    
    # Recursive case
    # ==============
    # We read a key value pair and recurse for the next.
    key = raw[start:spc]
    
    # Find the end of the value, Continuation lines begin with a space, so we loop until we find a "\n" not followed by a space.
    
    end = start
    while True:
        end = raw.find(b'\n', end+1)
        if raw[end+1] != ord(' ') : break
        
    # Grab the value
    # Also, drop the leading space on continuation lines
    value = raw[spc+1:end].replace(b'\n', b'\n')
    
    # Don't overwrite existing data contents
    if key in dct:
        if type(dct[key]) == list:
            dct[key].append(value)
        else:
            dct[key] = [ dct[key], value ]
    else:
        dct[key] = value
        
    return kvlm_parse(raw, start=end+1, dct=dct)

def kvlm_serialize(kvlm):
    ret = b''
    
    # Output fields
    for k in kvlm.keys():
        # Skip the message itself
        if k == None: continue
        val = kvlm[k]
        # Normalize to a list
        if type(val) != list:
            val = [ val ]
            
        for v in val:
            ret += k + b' ' + (v.replace(b'\n',b'\n')) + b'\n'
            
    # Append message
    ret += b'\n' + kvlm[None] + b'\n'
        
    return ret
    
class GitCommit(GitObject):
    fmt=b'commit'
    
    def deserialize(self, data):
        self.kvlm = kvlm_parse(data)
    
    def serialize(self):
        return kvlm_serialize(self.kvlm)
    
    def init(self):
        self.kvlm = dict()
        

argsp = argsubparsers.add_parser("log", help="Display history of a given commmit.")
argsp.add_argument("commit",
                   default="HEAD",
                   nargs="?",
                   help="Commit to start at.")

def cmd_log(args):
    repo = repo_find()
    
    print("digraph bkklog{")
    print("  node[shape=rect]")
    log_graphviz(repo, object_find(repo,args.commit), set())
    print("}")
    
def log_graphviz(repo, sha, seen):
    if sha in seen:
        return
    seen.add(sha)
    
    commit = object_read(repo, sha)
    short_hash = sha[0:8]
    message = commit.kvlm[None].decode("utf8").strip()
    message = message.replace("\\", "\\\\")
    message = message.replace("\"","\\\"")
    
    if "\n" in message: # Keep only the first line
        message = message[:message.index("\n")]
        
    print("   c_{0} [label=\"{1}: {2}\"]".format(sha, sha[0:7], message))
    assert commit.fmt==b'commit'
    
    if not b'parent' in commit.kvlm.keys():
        # Base case: the initial commit.
        return
    
    parents = commit.kvlm[b'parent']
    
    if type(parents) != list:
        parents = [ parents ]
        
    for p in parents:
        p = p.decode("ascii")
        print("  c_{0} -> c_{1};".format(sha, p))
        log_graphviz(repo, p, seen) 
        
class GitTreeLeaf(object):
    def __init__(self,mode, path,sha):
        self.mode = mode
        self.path = path
        self.sha = sha
        
def tree_parse_one(raw, start=0):
    # Find the space terminator of the mode
    x = raw.find(b' ', start)
    assert x-start == 5 or x-start == 6
    
    # Read the mode
    mode = raw[start:x]
    if len(mode) == 5:
        # Normalize to six bytes
        mode = b" " + mode
    
    # Find the NULL terminator of the path
    y = raw.find(b'\x00',x)
    # and read the path
    path = raw[x+1:y]
    
    # Read the SHA and convert to a hex string
    sha = format(int.from_bytes(raw[y+1:y+21],"big"),"040x")
    return y+21, GitTreeLeaf(mode, path.decode("utf8"), sha)

def tree_parse(raw):
    pos = 0 
    max = len(raw)
    ret = list()
    while pos < max:
        pos, data = tree_parse_one(raw, pos)
        ret.append(data)
        
    return ret

# Notice this isn't a comparison function, but a conversion function.
# Python's default sort doesn't accept a custom comparison function,
# like in most languages, but a `key` arguments that returns a new
# value, which is compared using the default rules.  So we just return
# the leaf name, with an extra / if it's a directory.
def tree_leaf_sort_key(leaf):
    if leaf.mode.startswith(b"10"):
        return leaf.path
    else:
        return leaf.path + "/"
    
def tree_serialize(obj):
    obj.items.sort(key=tree_leaf_sort_key)
    ret = b''
    for i in obj.items:
        ret += i.mode
        ret += b' '
        ret += i.path.encode("utf8")
        ret += b'\x00'
        sha = int(i.sha, 16)
        ret += sha.to_bytes(20, byteorder="big")
    return ret

class GitTree(GitObject):
    fmt = b'tree'
    
    def deserialize(self, data):
        self.items = tree_parse(data)
    
    def serialize(self):
        return tree_serialize(self)
    
    def init(self):
        self.items = list()
        
argsp = argsubparsers.add_parser("ls-tree", help = "Print a tree object")
argsp.add_argument("-r",
                   dest="recursive",
                   action="store_true",
                   help="Recurse into sub-trees")

argsp.add_argument("tree",
                   help="A tree-ish object")

def cmd_ls_tree(args):
    repo = repo_find()
    ls_tree(repo, args.tree, args.recursive)
    
def ls_tree(repo, ref, recursive=None, prefix=""):
    sha = object_find(repo, ref, fmt=b'tree')
    obj = object_read(repo, sha)
    for item in obj.items:
        if len(item.mode) == 5:
            type = item.mode[0:1]
        else:
            type = item.mode[0:2]
        
        match type:
            case b'04' : type = "tree"
            case b'10' : type = "blob" # Regular file
            case b'12' : type = "blob" # Symlink
            case b'16' : type = "commit"
            case _:
                raise Exception("Weird tree leaf mode {}".format(item.mode))
            
        if not (recursive and type == 'tree'):
            print("{0} {1} {2}\t{3}".format(
                "0" * (6 - len(item.mode)) + item.mode.decode("ascii"),
                type,
                item.sha,
                os.path.join(prefix, item.path)))
            
        else:
            ls_tree(repo, item.sha, recursive, os.path.join(prefix, item.path))
            
argsp = argsubparsers.add_parser("checkout", help="Checkout a commit inside of a directory.")

argsp.add_argument("commit", help="The commit or tree to checkout.")

argsp.add_argument("path", help="The EMPTY directory to checkout on.")

def cmd_checkout(args):
    repo = repo_find()
    
    obj = object_read(repo, object_find(repo, args.commit))
    
    # If the object is in commit, we grab its tree
    if obj.fmt == b'commit':
        obj = object_read(repo, obj.kvlm[b'tree'].decode("ascii"))
        
    # Verify that path is an empty directory
    if os.path.exists(args.path):
        if not os.path.isdir(args.path):
            raise Exception("Not a directory {0}!".format(args.path))
        if os.listdir(args.path):
            raise Exception("Not empty {0}!".format(args.path))
        
    else:
        os.makedirs(args.path)
        
    tree_checkout(repo, obj, os.path.realpath(args.path))
    
def tree_checkout(repo, tree, path):
    for item in tree.items:
        obj = object_read(repo, item.sha)
        dest = os.path.join(path, item.path)
        
        if obj.fmt == b'tree':
            os.mkdir(dest)
            tree_checkout(repo, obj, dest)
        elif obj.fmt == b'blob':
            # @TODO Support symlinks (identified by mode 12 ****)
            with open(dest, 'wb') as f:
                f.write(obj.bl)