import os
import hashlib
import shutil
import json

from collections import namedtuple
from contextlib import contextmanager

# Will be updated in cli.main()
GIT_DIR = None
GIT_DIR_NAME = ".gitc"

@contextmanager
def change_git_dir(new_dir):
    global GIT_DIR
    old_dir = GIT_DIR
    GIT_DIR = os.path.join(new_dir, GIT_DIR_NAME)
    yield
    GIT_DIR = old_dir
    

def _delete_non_empty_dir(pathname):
    for root, dirnames, filenames in os.walk(pathname, topdown=False):
        for name in filenames:
            os.remove(os.path.join(root, name))
        for name in dirnames:
            os.rmdir(os.path.join(root, name))

def init(reinit=False):
    if reinit:
        _delete_non_empty_dir(os.path.join(os.getcwd(), GIT_DIR))
    else:
        os.makedirs(GIT_DIR)
    os.makedirs(f'{GIT_DIR}/objects')

RefValue = namedtuple('RefValue', ['symbolic', 'value'])

def update_ref(ref, value, deref=True):
    ref = _get_ref_internal(ref, deref)[0]

    assert value.value
    if value.symbolic:
        value = f'ref: {value.value}'
    else:
        value = value.value
    ref_path = os.path.join(GIT_DIR, ref)
    os.makedirs(os.path.dirname(ref_path), exist_ok=True)
    with open(ref_path, 'w') as f:
        f.write(value)

def get_ref(ref, deref=True):
    return _get_ref_internal(ref, deref)[1]

def delete_ref(ref, deref=True):
    ref = _get_ref_internal(ref, deref)[0]
    os.remove(os.path.join(GIT_DIR, ref))

def _get_ref_internal (ref, deref):
    ref_path = os.path.join(GIT_DIR, ref)
    value = None
    if os.path.isfile (ref_path):
        with open (ref_path) as f:
            value = f.read ().strip ()
  
    symbolic = bool (value) and value.startswith ('ref:')
    if symbolic:
        value = value.split (':', 1)[1].strip ()
        if deref:
            return _get_ref_internal (value, deref=True)

    return ref, RefValue (symbolic=symbolic, value=value)
        
def iter_refs(prefix='', deref=True):
    refs = ['HEAD', 'MERGE_HEAD']

    for root, _, filenames in os.walk(os.path.join(GIT_DIR, "refs", "")):
        refs.extend(os.path.join(root[len(GIT_DIR)+1:], name) for name in filenames)

    for refname in refs:
        if not refname.startswith(prefix):
            continue
        ref = get_ref(refname, deref=deref)
        if ref.value:
            yield refname, ref

@contextmanager
def get_index():
    index = {}
    if os.path.isfile(os.path.join(GIT_DIR, 'index')):
        with open(os.path.join(GIT_DIR, 'index')) as f:
            index = json.load(f)

    yield index

    with open(os.path.join(GIT_DIR, "index"), 'w') as f:
        json.dump(index, f)

def hash_object(data, type_='blob'):
    obj = type_.encode() + b'\x00' + data
    oid = hashlib.sha1(data).hexdigest()
    with open(os.path.join(GIT_DIR,"objects",oid), 'wb') as out:
        out.write(obj)
    return oid

def get_object(oid, expected='blob'):
    try:
        with open(os.path.join(GIT_DIR,"objects",oid), 'rb') as f:
            obj = f.read()
    except(FileNotFoundError):
        return b''

    type_, _, content = obj.partition(b'\x00')
    type_ = type_.decode()

    if expected is not None:
        assert type_ == expected, f'Expected {expected}, got{type_}'
    return content

def objects_exists(oid):
    return os.path.isfile(os.path.join(GIT_DIR, "objects", oid))

def fetch_object_if_missing(oid, remote_git_dir):
    if objects_exists(oid):
        return
    remote_git_dir += os.path.join(".", ".gitc")
    shutil.copy(os.path.join(remote_git_dir, "objects", oid),
                os.path.join(GIT_DIR, "objects", oid))
    
def push_object(oid, remote_git_dir):
    shutil.copy(os.path.join(GIT_DIR, "objects", oid), os.path.join(remote_git_dir, ".gitc", "objects", oid))