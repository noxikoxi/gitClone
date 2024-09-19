import os

from . import data
from . import base

REMOTE_REFS_BASE = os.path.join("refs", "head")
LOCAL_REFS_BASE = os.path.join("refs", "remote")

def fetch(remote_path):
    # Get remote refs
    refs = _get_remote_refs(remote_path, REMOTE_REFS_BASE)

    # fetch missing objects
    for oid in base.iter_objects_in_commits(refs.values()):
        data.fetch_object_if_missing(oid, remote_path)

    # Update local refs
    for remote_name, value in refs.items():
        refname = os.path.relpath(remote_name, REMOTE_REFS_BASE)[3:]
        data.update_ref(os.path.join(LOCAL_REFS_BASE, refname), data.RefValue(symbolic=False, value=value))

def _get_remote_refs(remote_path, prefix=''):
    with data.change_git_dir(remote_path):
        return {refname: ref.value for refname, ref in data.iter_refs(prefix)}
    
def push(remote_path, refname):
    # get refs data
    local_ref = data.get_ref(refname).value
    remote_refs = _get_remote_refs(remote_path)
    remote_ref = remote_refs.get(refname)
    assert local_ref

    # Don't allow force push
    assert not remote_ref or base.is_ancestor_of(local_ref, remote_ref)
    
    # Compute which objects should be pushed
    known_remote_refs = filter(data.objects_exists, remote_refs.values())
    remote_objects = set(base.iter_objects_in_commits(known_remote_refs))
    local_objects = set(base.iter_objects_in_commits({local_ref}))
    objects_to_push = local_objects - remote_objects

    # Push missing objects
    for oid in objects_to_push:
        data.push_object(oid, remote_path)

    # update remote ref
    with data.change_git_dir(remote_path):
        data.update_ref(refname, data.RefValue(symbolic=False, value=local_ref))