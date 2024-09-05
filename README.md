**Veda: A Git Implementation**
=============================

**Overview**
------------

Veda is a Python implementation of the Git version control system. This project is an exercise in understanding the inner workings of Git and is not intended to be a production-ready replacement for the official Git implementation.

**Implementation**
-----------------

Veda is implemented in two parts:

* `libveda.py`: This is the core library that provides the functionality for managing Git repositories. It includes functions for creating and managing commits, trees, and blobs.
* `veda`: This is the command-line interface to the Veda library. It provides the following commands:
    + add
    + cat-file
    + check-ignore
    + checkout
    + commit
    + hash-object
    + init
    + log
    + ls-files
    + ls-tree
    + rev-parse
    + rm
    + show-ref
    + status
    + tag

**Requirements**
---------------

* Unix-like operating system (e.g. Linux, macOS)
* Python 3.x

**Note for Windows Users**
-------------------------

To use Veda on Windows, you will need to install the Windows Subsystem for Linux (WSL). This will allow you to run Veda on a Unix-like environment within Windows. The test suite requires a bash-compatible shell.

**Usage**
---------

To use Veda, you can use the following commands:

### Initialization

* `veda init`: Initialize a new repository.

### Basic snapshotting

* `veda add <path>`: Add file(s) at `<path>` to the index.
* `veda commit [-m <msg>]`: Record changes to the repository.
* `veda rm <path>`: Remove file(s) at `<path>` from the index.

### Examining the commit history

* `veda log`: Display commits in the repository.
* `veda log <commit>`: Display information about `<commit>`.
* `veda log <start>..<end>`: Display commits between `<start>` and `<end>`.
* `veda log --all`: Display all commits in the repository.

### Growing your project

* `veda branch <name>`: Create a new branch named `<name>`.
* `veda checkout <name>`: Switch to branch `<name>`.
* `veda merge <commit>`: Merge changes from `<commit>` into the current branch.
* `veda tag <name>`: Create a new tag named `<name>`.

### Examining and comparing your project

* `veda status`: Display paths that have differences between the index file and the current HEAD commit.
* `veda diff`: Display differences between the index file and the current HEAD commit.
* `veda show <commit>`: Display information about `<commit>`.

**Note:** 
To use Veda from the command line, you need to be in the same directory as the `veda` file and add the current directory to your system's PATH.

To add `veda` to your PATH, you can add the following line to your shell configuration file:

For Bash:

```bash
echo 'export PATH="$PATH:$(pwd)"' >> ~/.bashrc
source ~/.bashrc
```

For Zsh:

```bash
echo 'export PATH="$PATH:$(pwd)"' >> ~/.zshrc
source ~/.zshrc
``` 

After doing this, you should be able to run `veda` from any directory in your terminal.

**Limitations**
---------------

Veda is a simplified implementation of Git and does not support many of the features of the official Git implementation, including:

* Branching and merging
* Remote repositories
* Git hooks
* Submodules

**License**
----------

Veda is licensed under the GNU General Public License, version 3 or later.

