# Identity overlay: exited children may remain visible as zombies until reaped.
def identity(record, required_text, proc_root=Path('/proc'), uid=None):
 if not record:return {'state':'missing_record'}
 proc=proc_root/str(record['pid'])
 try:
  fields=(proc/'stat').read_text().rsplit(')',1)[1].split();ticks=fields[19];actual_uid=proc.stat().st_uid
  matched=actual_uid==(os.getuid() if uid is None else uid) and ticks==str(record['start_ticks'])
  if matched and fields[0]=='Z':
   if proc_root==Path('/proc') and int(fields[1])==os.getpid():
    try:os.waitpid(record['pid'],os.WNOHANG)
    except ChildProcessError:pass
   return {'state':'exited','pid':record['pid'],'uid':actual_uid,'start_ticks':ticks,'zombie':True}
  command=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  return {'state':'owned_alive' if matched and required_text in command else 'identity_mismatch','pid':record['pid'],'uid':actual_uid,'start_ticks':ticks}
 except FileNotFoundError:return {'state':'exited','pid':record['pid']}

def reap_finished_children():
 while True:
  try:pid,_=os.waitpid(-1,os.WNOHANG)
  except ChildProcessError:return
  if pid==0:return
