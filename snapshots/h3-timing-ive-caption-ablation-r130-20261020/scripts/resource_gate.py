"""Single-GPU resource admission; process caps apply to this UID, not other users."""
from pathlib import Path
import json
from r130_contract import ROOT,read as read_json,sha,require
class ResourceUnavailable(RuntimeError):
 def __init__(self,message,snapshot):super().__init__(message);self.snapshot=snapshot

def inside(path,root):
 path=Path(path);require(path.is_absolute() and not path.is_symlink() and path.resolve().is_relative_to(Path(root).resolve()),'outside owned evidence');return path

def admission_document(approved=True):
 value=read_json(ROOT/'configs/admission.json');require(value['scope']=='own_user_video_jobs','resource scope differs')
 if approved:require(value.get('ready_for_launch') is True,'root live admission pending')
 return value
