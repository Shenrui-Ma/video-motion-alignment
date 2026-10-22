"""Transfer four original tensors server-to-server using a short-lived isolated agent."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
binding = json.loads((ROOT / "input_audit/long_0039_BINDING.json").read_text())
source = binding["producer_remote"]
destination = "/data4/researcher/h3_runs/threecase_auto_r144_20261020/original_condition_cache/long_0039"
roles = ("reference_vae_latent", "conditioning_embedding", "conditioning_tags", "conditioning_position")
selected = [row for row in binding["condition_tensor_files"] if len(row["tensor_signature"]["shape"]) != 4]
assert len(selected) == 4
files = [str(Path(row["file"]).relative_to(source)) for row in selected]
files += [
    "audit/r122_long_0039_shared_conditioning.json",
    "audit/r122_long_0039_seed2026101701_native_conditioning.json",
    "audit/r122_long_0039_seed2026101701_native_noise.json",
    "audit/x0/r122_long_0039_seed2026101701_native/manifest.json",
    "logs/r122_long_0039_seed2026101701_native_history.json",
    "logs/r122_long_0039_seed2026101701_native_job.json",
]

with tempfile.TemporaryDirectory(prefix="r144-copy-agent-") as temporary:
    socket = Path(temporary) / "agent.sock"
    agent = subprocess.Popen(["ssh-agent", "-D", "-a", str(socket)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 5
        while not socket.exists() and agent.poll() is None and time.monotonic() < deadline:
            time.sleep(.05)
        if not socket.exists():
            raise RuntimeError("isolated SSH agent did not become ready")
        env = dict(os.environ, SSH_AUTH_SOCK=str(socket), SSH_ASKPASS_REQUIRE="never")
        subprocess.run(["ssh-add", "-t", "300", str(Path.home() / ".ssh/id_ed25519")],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE, env=env, check=True, timeout=10)
        subprocess.run(["ssh", "-A", "H3_SERVER_B",
                        "mkdir -p " + shlex.quote(destination)],
                       env=env, check=True, timeout=15)
        remote_command = shlex.join([
            "rsync", "-a", "--files-from=-", "-e",
            "ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ProxyCommand=none -o ProxyJump=none",
            "researcher@192.0.2.1:" + source + "/", destination + "/",
        ])
        started = time.time()
        subprocess.run(["ssh", "-A", "H3_SERVER_B", remote_command],
                       input="\n".join(files) + "\n", text=True, env=env,
                       check=True, timeout=240)
        verification = (
            "import hashlib,json;from pathlib import Path;"
            f"root=Path({destination!r});files={files!r};"
            "print(json.dumps([{ 'relative':f,'bytes':(root/f).stat().st_size,"
            "'sha256':hashlib.sha256((root/f).read_bytes()).hexdigest()} for f in files]))"
        )
        output = subprocess.check_output(
            ["ssh", "H3_SERVER_B", "python3 -c " + shlex.quote(verification)],
            text=True, env=env, timeout=60)
        rows = json.loads(output)
        actual = {row["relative"]: row for row in rows}
        for row in selected:
            relative = str(Path(row["file"]).relative_to(source))
            assert actual[relative]["sha256"] == row["sha256"], relative
        receipt = {
            "schema": "r144-original-conditioning-direct-transfer-v1", "passed": True,
            "source_host": "192.0.2.1", "destination_host": "192.0.2.1",
            "source_root": source, "destination_root": destination,
            "files": rows, "started_unix": started, "finished_unix": time.time(),
            "bulk_data_route": "Direct private-address SSH initiated on destination server",
            "remote_SSH_ProxyCommand": "none", "remote_SSH_ProxyJump": "none",
            "bulk_data_crossed_local_computer": False, "external_downloads": False,
            "paid_HTTP_proxy_used": False,
            "authentication": "Ephemeral isolated local agent forwarded for this transfer; no private key copied to server",
            "GPU_used": False,
        }
        (ROOT / "audit/BOOK_ORIGINAL_CONDITION_DIRECT_TRANSFER.json").write_text(
            json.dumps(receipt, indent=2) + "\n")
        print(json.dumps({"passed": True, "files": len(rows), "bytes": sum(row["bytes"] for row in rows),
                          "destination_root": destination}))
    finally:
        agent.terminate()
        try:
            agent.wait(timeout=5)
        except subprocess.TimeoutExpired:
            agent.kill()
            agent.wait()
