import os
import subprocess

from collections import defaultdict
from difflib import unified_diff
from tempfile import NamedTemporaryFile as Temp

from . import data

def compare_trees(*trees):
    entries = defaultdict(lambda: [None] * len(trees))
    for i, tree, in enumerate(trees):
        for path, oid in tree.items():
            entries[path][i] = oid
    
    for path, oids in entries.items():
        yield (path, *oids)


def iter_changed_files(t_from, t_to):
    for path, o_from, o_to in compare_trees(t_from, t_to):
        if o_from != o_to:
            action = ('new file' if not o_from else 'deleted' if not o_to else 'modified')
            yield path, action

def diff_trees(tree_from, tree_to):
    output = ""
    for path, o_from, o_to in compare_trees(tree_from, tree_to):
        if o_from != o_to:
            output += diff_blobs(o_from, o_to, path) + '\n'
    return output + "\n"

def diff_blobs (o_from, o_to, path='blob'):
    file_extension = os.path.splitext(path)[1]
    if file_extension.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
        return f'\n\n*** Changed {path}\n\n'
    file_from = data.get_object(o_from).decode() if o_from != None else ""
    file_to = data.get_object(o_to).decode() if o_to != None else ""

    file_from = file_from.splitlines()
    file_to = file_to.splitlines()

    return '\n'.join(unified_diff(file_from, file_to, fromfile=f'Parent: {path}', tofile=f'Child: {path}'))

def merge_blobs(o_base, o_HEAD, o_other):
    with Temp() as f_base, Temp() as f_HEAD, Temp() as f_other:

        # Write blobs to files
        for oid, f in ((o_base, f_base), (o_HEAD, f_HEAD), (o_other, f_other)):
            if oid:
                f.write(data.get_object(oid))
                f.flush()

        with subprocess.Popen(
            # -m -> merge files
            # -L -> create a tag
            ['diff3', '-m', 
             '-L', 'HEAD', f_HEAD.name,
             '-L', 'BASE', f_base.name,
             '-L', 'MERGE_HEAD', f_other.name,
            ], stdout=subprocess.PIPE) as proc:
            output, _ = proc.communicate()
            assert proc.returncode in (0, 1)

        return output

def merge_trees(t_base, t_HEAD, t_other):
    tree = {}
    for path, o_base, o_HEAD, o_other in compare_trees(t_base, t_HEAD, t_other):
        tree[path] = data.hash_object(merge_blobs(o_base, o_HEAD, o_other))
    return tree