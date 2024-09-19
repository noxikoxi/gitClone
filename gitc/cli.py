import argparse
import os
import sys
import textwrap
import subprocess

from . import base
from . import data
from . import diff
from . import remote


GRAPH_OUTPUT_FILE = "commits_history.png"

def main():
    with data.change_git_dir('.'):
        args = parse_args()
        args.func(args)

def parse_args():
    parser = argparse.ArgumentParser()

    commands = parser.add_subparsers(dest='command')
    commands.required = True

    oid = base.get_oid

    init_parser = commands.add_parser("init")
    init_parser.set_defaults(func=init)

    hash_object_parser = commands.add_parser("hash-object")
    hash_object_parser.set_defaults(func=hash_object)
    hash_object_parser.add_argument('file')

    cat_file_parser = commands.add_parser('cat-file')
    cat_file_parser.set_defaults(func=cat_file)
    cat_file_parser.add_argument("object", type=oid)

    write_tree_parser = commands.add_parser('write-tree')
    write_tree_parser.set_defaults(func=write_tree)

    read_tree_parser = commands.add_parser('read-tree')
    read_tree_parser.set_defaults(func=read_tree)
    read_tree_parser.add_argument('tree', type=oid)

    commit_parser = commands.add_parser('commit')
    commit_parser.set_defaults(func=commit)
    commit_parser.add_argument('-m', '--message', required=True)

    log_parser = commands.add_parser('log')
    log_parser.set_defaults(func=log)
    log_parser.add_argument('oid', nargs='?', default='@', type=oid)

    show_parser = commands.add_parser('show')
    show_parser.set_defaults(func=show)
    show_parser.add_argument('oid', default='@', type=oid, nargs='?')

    diff_parser = commands.add_parser("diff")
    diff_parser.set_defaults(func=_diff)
    diff_parser.add_argument('--cached', action="store_true")
    diff_parser.add_argument('commit', nargs='?')

    checkout_parser = commands.add_parser('checkout')
    checkout_parser.set_defaults(func=checkout)
    checkout_parser.add_argument('commit')

    tag_parser = commands.add_parser('tag')
    tag_parser.set_defaults(func=tag)
    tag_parser.add_argument('name')
    tag_parser.add_argument('oid', nargs="?", default='@', type=oid)

    k_parser = commands.add_parser('k')
    k_parser.set_defaults(func=k)

    branch_parser = commands.add_parser('branch')
    branch_parser.set_defaults(func=branch)
    branch_parser.add_argument('name', nargs='?')
    branch_parser.add_argument('start_point', default='@', type=oid, nargs='?')

    status_parser = commands.add_parser('status')
    status_parser.set_defaults(func=status)

    reset_parser = commands.add_parser('reset')
    reset_parser.set_defaults(func=reset)
    reset_parser.add_argument('commit', type=oid)

    merge_parser = commands.add_parser('merge')
    merge_parser.set_defaults(func=merge)
    merge_parser.add_argument('commit', type=oid)

    merge_base_parser = commands.add_parser('merge-base')
    merge_base_parser.set_defaults(func=merge_base)
    merge_base_parser.add_argument('commit1', type=oid)
    merge_base_parser.add_argument('commit2', type=oid)

    fetch_parser = commands.add_parser('fetch')
    fetch_parser.set_defaults(func=fetch)
    fetch_parser.add_argument('remote')

    push_parser = commands.add_parser('push')
    push_parser.set_defaults(func=push)
    push_parser.add_argument('remote')
    push_parser.add_argument('branch')

    add_parser = commands.add_parser('add')
    add_parser.set_defaults(func=add)
    add_parser.add_argument('files', nargs='+')

    return parser.parse_args()

def init(args):
    if os.path.isdir(os.path.join(os.getcwd(), data.GIT_DIR)): # Repository already initialised
        base.init(reinit=True)
        print(f'Reinitialized empty gitc repository in {os.path.join(os.getcwd(),data.GIT_DIR)}')
    else:
        base.init()
        print(f'Initialized empty gitc repository in {os.path.join(os.getcwd(),data.GIT_DIR)}')

def status(args):
    HEAD = base.get_oid("@")
    branch = base.get_branch_name()
    if branch:
        print(f'On branch {branch}')
    else:
        print(f"HEAD detached at {HEAD[:10]}")

    MERGE_HEAD = data.get_ref("MERGE_HEAD").value
    if MERGE_HEAD:
        print(f'Merging with {MERGE_HEAD[:10]}')

    

    print('\nChanges to be committed:\n')
    HEAD_tree = HEAD and base.get_commit(HEAD).tree
    added_files = set()
    for path, action in diff.iter_changed_files(base.get_tree(HEAD_tree), base.get_index_tree()):
        added_files.add(path)
        print(f'{action:>12}: {path}')

    print ('\nChanges not staged for commit:\n')
    for path, action in diff.iter_changed_files(base.get_tree(HEAD_tree), base.get_working_tree()):
        if path not in added_files:
            print(f'{action:>12}: {path}')



def reset(args):
    base.reset(args.commit)

def merge(args):
    base.merge(args.commit)

def merge_base(args):
    print(base.get_merge_base(args.commit1, args.commit2))

def fetch(args):
    remote.fetch(args.remote)

def push(args):
    remote.push(args.remote, os.path.join('refs', 'heads', args.branch))

def add(args):
    base.add(args.files)

def commit(args):
    print(base.commit(args.message))

def _print_commit(oid, commit, refs=None):
    refs_str = f'({", ".join(refs)})' if refs else ''
    print(f'commit {oid} {refs_str}\n')
    print(textwrap.indent(commit.message, "     "))
    print('')

def log(args):
    refs = {}
    for refname, ref in data.iter_refs():
        refs.setdefault(ref.value, []).append(refname)

    for oid in base.iter_commits_and_parents({args.oid}):
        commit = base.get_commit(oid)
        _print_commit(oid, commit, refs.get(oid))

def show(args):
    if not args.oid:
        return
    commit = base.get_commit(args.oid)
    parent_tree = None
    if commit.parents:
        parent_tree = base.get_commit(commit.parents[0]).tree
    _print_commit(args.oid, commit)

    result = diff.diff_trees(base.get_tree(parent_tree), base.get_tree(commit.tree))
    sys.stdout.flush()
    sys.stdout.write(result)

def _diff(args):
    oid = args.commit and base.get_commit(args.commit)

    if args.commit:
        tree_from = base.get_tree(oid and base.get_commit(oid).tree)

    if args.cached:
        tree_to = base.get_index_tree()
        if not args.commit:
            # No commit provided diff from HEAD
            oid = base.get_oid('@')
            tree_from = base.get_tree(oid and base.get_commit(oid).tree)
    else:
        tree_to = base.get_working_tree()
        if not args.commit:
            # Diff from index
            tree_to = base.get_index_tree()

    result = diff.diff_trees(tree_from, tree_to)
    sys.stdout.flush()
    sys.stdout.write(result)

def checkout(args):
    base.checkout(args.commit)

def tag(args):
    oid = args.oid
    base.create_tag(args.name, oid)

def branch(args):
    if not args.name:
        current = base.get_branch_name()
        for branch in base.iter_branch_names():
            prefix = '*' if branch == current else ' '
            print(f'{prefix} {branch}')
    else:
        base.create_branch(args.name, args.start_point)
        print(f'Branch {args.name} created at {args.start_point[:10]}')

def k(args):
    dot = 'digraph commits {\n'
    oids = set()
    for refname, ref in data.iter_refs(deref=False):
        value = ref.value
        if ref.value.startswith('refs'):
            value = ref.value[5:].replace("\\", "\\\\")
        if refname != "HEAD":
            refname = refname[5:].replace("\\", "\\\\")
        
        dot += f'"{refname}" [shape=note]\n'
        dot += f'"{refname}" -> "{value}"\n'
        if not ref.symbolic:
            oids.add(value)

    for oid in base.iter_commits_and_parents(oids):
        commit = base.get_commit(oid)
        dot += f'"{oid}" [shape=box style=filled label="{oid[:10]}...\\n{commit.message}"]\n'
        for parent in commit.parents:
            dot += f'"{oid}" -> "{parent}"\n'
    
    dot += "}"

    with subprocess.Popen(['dot', "-Tpng", '-o', os.path.join(data.GIT_DIR, GRAPH_OUTPUT_FILE)], stdin=subprocess.PIPE) as proc:
        proc.communicate(dot.encode())

    if proc.returncode == 0:
        print(f"Succesfully saved commits history to file: {os.path.join(data.GIT_DIR, GRAPH_OUTPUT_FILE)}")
    else:
        print(f"Error occured while saving commits history.")

def read_tree(args):
    base.read_tree(args.tree)

def hash_object (args):
    with open (args.file, 'rb') as f:
        print(data.hash_object(f.read()))

def cat_file(args):
    sys.stdout.flush()
    sys.stdout.buffer.write(data.get_object(args.object, expected=None))

def write_tree(args):
    print(base.write_tree())