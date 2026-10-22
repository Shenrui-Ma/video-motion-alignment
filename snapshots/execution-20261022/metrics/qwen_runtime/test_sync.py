"""Small local protocol tests; never contacts either server."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import sync_inputs as sync


def call(code,*args,data=None,check=True):
    return subprocess.run([sys.executable,'-c',code,*map(str,args)],input=data,capture_output=True,check=check)


class SyncTest(unittest.TestCase):
    def test_hash_stream_resume_and_partial_exclusion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); source=root/'source'; target=root/'target'
            frames=source/'frames/source/sample';frames.mkdir(parents=True)
            for name in ['000001.png','000002.png']:(frames/name).write_bytes(name.encode())
            (frames/'PREPARED.json').write_text(json.dumps({'frames':2}))
            pending=source/'frames/source/new.partial';pending.mkdir()
            (pending/'PREPARED.json').write_text(json.dumps({'frames':0}))
            (source/'metadata').mkdir();(source/'metadata/sample.json').write_text('[]')
            snapshot=json.loads(call(sync.SNAPSHOT_CODE,source).stdout)
            self.assertEqual(len(snapshot['folders']),1)
            self.assertEqual(len(snapshot['files']),4)
            request={'target':str(target),'snapshot':snapshot}
            before=json.loads(call(sync.CHECK_CODE,data=json.dumps(request).encode()).stdout)
            self.assertEqual(len(before['missing']),4)
            transfer={'source_root':str(source),'target':str(target),'files':before['missing']}
            transfer_file=root/'request.json';transfer_file.write_text(json.dumps(transfer))
            archive=call(sync.ARCHIVE_CODE,data=json.dumps(transfer).encode()).stdout
            result=json.loads(call(sync.RECEIVE_CODE,transfer_file,data=archive).stdout)
            self.assertEqual(result['received_verified'],4)
            after=json.loads(call(sync.CHECK_CODE,data=json.dumps(request).encode()).stdout)
            self.assertEqual(after['missing'],[])
            self.assertEqual(after['verified_existing'],4)
            # A corrupted stream never replaces an already verified destination file.
            altered=bytearray(archive)
            location=archive.find(b'000001.png',archive.find(b'000001.png')+1)
            self.assertGreater(location,0)
            altered[location]=ord('X')
            bad=call(sync.RECEIVE_CODE,transfer_file,data=bytes(altered),check=False)
            self.assertNotEqual(bad.returncode,0)
            self.assertEqual((target/'frames/source/sample/000001.png').read_bytes(),b'000001.png')


if __name__=='__main__':unittest.main(verbosity=2)
