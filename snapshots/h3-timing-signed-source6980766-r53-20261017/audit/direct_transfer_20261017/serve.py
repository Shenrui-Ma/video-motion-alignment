import http.server,json,pathlib,os,hashlib,time,signal,threading
root=pathlib.Path(__file__).resolve().parent
cfg=json.loads((root/'private.json').read_text())
for r in cfg['files'].values():
 p=pathlib.Path(r['path']);assert p.stat().st_size==r['bytes'];assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  prefix='/'+cfg['token']+'/'
  name=self.path[len(prefix):] if self.path.startswith(prefix) else ''
  if name not in cfg['files']:self.send_error(404);return
  r=cfg['files'][name];self.send_response(200);self.send_header('Content-Length',str(r['bytes']));self.end_headers()
  try:
   with open(r['path'],'rb') as f:
    while b:=f.read(1048576):self.wfile.write(b)
  except (BrokenPipeError,ConnectionResetError):pass
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer((cfg['bind'],0),Handler)
pid=os.getpid();identity={'pid':pid,'uid':os.getuid(),'start_ticks':int(pathlib.Path('/proc/self/stat').read_text().split(') ')[1].split()[19]),'cmdline_sha256':hashlib.sha256(pathlib.Path('/proc/self/cmdline').read_bytes()).hexdigest()}
(root/'ready.json').write_text(json.dumps({'identity':identity,'port':server.server_port,'bind':cfg['bind'],'files':{k:{'sha256':v['sha256'],'bytes':v['bytes']} for k,v in cfg['files'].items()}}))
threading.Timer(600,server.shutdown).start()
server.serve_forever();server.server_close()
