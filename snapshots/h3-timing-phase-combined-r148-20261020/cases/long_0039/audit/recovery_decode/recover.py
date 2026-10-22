#!/usr/bin/env python3
"""Recover the book's saved Euler endpoint with the original native AV decoders."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("x") as f:
        json.dump(value, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def binding():
    d = json.loads((HERE / "BINDING.json").read_text())
    for item in [*d["files"].values(), *d["native_code"].values()]:
        p = Path(item["file"])
        require(p.stat().st_size == item["bytes"] and sha(p) == item["sha256"],
                "bound source changed: " + str(p))
    for item in d["models"]:
        p = Path(item["file"])
        s = p.stat()
        require(str(p.resolve()) == item["resolved"] and
                (s.st_size, s.st_mtime_ns, s.st_ino, s.st_dev) ==
                (item["bytes"], item["mtime_ns"], item["inode"], item["device"]),
                "VAE file identity changed")
    return d


def validate_records(d, meta, manifest, router):
    run = d["run_id"]
    require(meta["snapshot_kind"] == "sampler_final" and
            meta["sigma_video"] == meta["sigma_audio"] == 0 and
            meta["normalization_stage"] == "after_process_latent_out",
            "recovery requires the normalized true sigma-zero endpoint")
    require(meta["run_id"] == run and meta["geometry"] == d["geometry"] and
            meta["seed"] == 2026101701 and meta["total_steps"] == 20,
            "endpoint identity mismatch")
    require(manifest["status"] == "complete" and manifest["callback_count"] == 20 and
            [c["step_zero_based"] for c in manifest["captures"]] == list(range(20)),
            "incomplete sampler")
    require({k: v for k, v in manifest["final_sampler_result"].items() if k != "file"} == meta,
            "endpoint metadata mismatch")
    require(router["run_id"] == run and router["completed_forward_calls"] == 20 and
            router["completed_calls"] == router["native_override_calls"] == 1000 and
            router["routed_calls"] == 450 and router["calls_by_forward"] == [50] * 20 and
            router["routed_by_forward"] == [0] * 6 + [50] * 9 + [0] * 5,
            "original runtime execution incomplete")


def payload_and_proof(d):
    import torch
    torch.set_num_threads(4)
    root = Path(d["case_root"])
    directory = root / "audit/x0" / d["run_id"]
    payload = torch.load(directory / "sampler_final.pt", map_location="cpu", weights_only=True)
    require(set(payload) == {"video", "audio", "metadata"}, "unexpected endpoint payload")
    manifest = json.loads((directory / "manifest.json").read_text())
    router = json.loads((root / "audit/router" / (d["run_id"] + ".json")).read_text())
    validate_records(d, payload["metadata"], manifest, router)
    for name in ("video", "audio"):
        t, info = payload[name], payload["metadata"][name]
        require(t.device.type == "cpu" and t.dtype == torch.float32 and
                list(t.shape) == info["shape"] and bool(torch.isfinite(t).all()) and
                hashlib.sha256(t.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest() ==
                info["sha256"], "invalid endpoint " + name)
    return payload, {"snapshot": d["files"]["audit/x0/" + d["run_id"] + "/sampler_final.pt"],
                     "manifest": d["files"]["audit/x0/" + d["run_id"] + "/manifest.json"],
                     "router": d["files"]["audit/router/" + d["run_id"] + ".json"],
                     "original_nfe": 20, "original_routed_calls": 450,
                     "original_attention_calls": 1000, "new_dit_forwards": 0,
                     "metadata": payload["metadata"]}


def imports(d, cpu):
    cfg = d["runtime"]
    sys.path[:0] = [str(Path(d["case_root"]) / "scripts"), cfg["dependencies"], cfg["core"]]
    from compatibility_bootstrap import install, install_video_compat
    install()
    install_video_compat()
    import comfy.cli_args
    args = comfy.cli_args.args
    args.cpu = cpu
    args.disable_dynamic_vram = True
    args.disable_cuda_malloc = True
    args.use_pytorch_cross_attention = True
    args.reserve_vram = 8
    import folder_paths
    folder_paths.folder_names_and_paths["vae"] = (
        [str(Path(cfg["models"]) / "vae")], folder_paths.supported_pt_extensions)
    import nodes
    from comfy_extras.nodes_audio import vae_decode_audio
    from comfy_extras.nodes_video import CreateVideo
    from comfy_api.latest import Types
    from comfy.nested_tensor import NestedTensor
    return nodes, vae_decode_audio, CreateVideo, Types, NestedTensor


def encode(images, audio, graph, output, CreateVideo, Types):
    """Exactly node13 plus the native node14 save_to call; preserve audio and frames."""
    args = graph["13"]["inputs"]
    video = CreateVideo.execute(images, fps=args["fps"], audio=audio,
                                bit_depth=args["bit_depth"]).result[0]
    save = graph["14"]["inputs"]
    video.save_to(str(output), format=Types.VideoContainer(save["format"]),
                  codec=Types.VideoCodec(save["codec"]), metadata={"prompt": graph},
                  crf=save["codec.encoding.crf"])


def video_properties(path):
    raw = subprocess.check_output([
        "ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format",
        "-of", "json", str(path)], text=True)
    data = json.loads(raw)
    video = [x for x in data["streams"] if x["codec_type"] == "video"]
    audio = [x for x in data["streams"] if x["codec_type"] == "audio"]
    require(len(video) == len(audio) == 1, "native AV output must have video and audio")
    v = video[0]
    return {"width": int(v["width"]), "height": int(v["height"]),
            "frames": int(v["nb_read_frames"]), "fps": v["avg_frame_rate"],
            "video_codec": v["codec_name"], "audio_codec": audio[0]["codec_name"],
            "audio_sample_rate": int(audio[0]["sample_rate"]),
            "duration": float(data["format"]["duration"])}


def identity(pid):
    from process_identity import snapshot, hashed_record
    row = hashed_record(snapshot(pid), include_pid=True)
    if row:
        row["boot_id"] = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    return row


def gpu(uuid, idle=False):
    from gpu_query import parse_compute
    lines = subprocess.check_output([
        "nvidia-smi", "--id=" + uuid,
        "--query-gpu=uuid,memory.free,memory.used,utilization.gpu",
        "--format=csv,noheader,nounits"], text=True).strip().splitlines()
    require(len(lines) == 1, "GPU did not resolve uniquely")
    x = [v.strip() for v in lines[0].split(",")]
    require(len(x) == 4 and x[0] == uuid and all(v.isdecimal() for v in x[1:]),
            "selected GPU is not healthy")
    raw = subprocess.check_output([
        "nvidia-smi", "--query-compute-apps=gpu_uuid,pid,used_gpu_memory",
        "--format=csv,noheader,nounits"], text=True)
    rows, excluded = parse_compute(raw, uuid)
    selected = [r for r in rows if r["gpu_uuid"] == uuid]
    if idle:
        require(int(x[1]) >= 40000 and int(x[2]) <= 64 and int(x[3]) == 0 and not selected,
                "wait for the selected 48GB GPU to be fully released")
    return {"uuid": uuid, "free_mib": int(x[1]), "used_mib": int(x[2]),
            "utilization": int(x[3]), "processes": selected, "unavailable_other_gpus": excluded}


def child(args):
    d = binding()
    sys.path.insert(0, str(Path(d["case_root"]) / "scripts"))
    out = HERE / args.attempt
    owner = identity(os.getpid())
    write(out / "READY.json", owner)
    deadline = time.monotonic() + 30
    while not (out / "GO.json").exists():
        require(time.monotonic() < deadline and os.getppid() != 1, "parent authorization expired")
        time.sleep(.05)
    go = json.loads((out / "GO.json").read_text())
    require(go["child"] == owner and identity(go["parent"]["pid"]) == go["parent"],
            "parent/child generation mismatch")
    def parent_guard():
        while True:
            time.sleep(1)
            if identity(go["parent"]["pid"]) != go["parent"]:
                os.kill(os.getpid(), signal.SIGTERM)
                return
    threading.Thread(target=parent_guard, daemon=True).start()
    admission = gpu(args.gpu_uuid, idle=True)
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu_uuid
    payload, proof = payload_and_proof(d)
    import torch
    require(not torch.cuda.is_initialized(), "early CUDA initialization")
    nodes, decode_audio, CreateVideo, Types, NestedTensor = imports(d, cpu=False)
    graph = json.loads(Path(d["files"]["configs/graphs/" + d["run_id"] + ".json"]["file"]).read_text())
    output = out / (d["run_id"] + "_recovered.mp4")
    partial = out / (d["run_id"] + "_encoding.mp4")
    require(not output.exists() and not partial.exists(), "recovery output already exists")
    started = time.time()
    samples = {"samples": NestedTensor([payload["video"], payload["audio"]])}
    video_vae = audio_vae = images = audio = None
    try:
        with torch.inference_mode():
            video_vae = nodes.VAELoader().load_vae(graph["3"]["inputs"]["vae_name"])[0]
            images = nodes.VAEDecode().decode(video_vae, samples)[0]
            require(tuple(images.shape) == (107, 736, 1312, 3), "native decode geometry changed")
            require(bool(torch.isfinite(images).all()), "nonfinite decoded video")
            audio_vae = nodes.VAELoader().load_vae(graph["4"]["inputs"]["vae_name"])[0]
            audio = decode_audio(audio_vae, samples)
            require(bool(torch.isfinite(audio["waveform"]).all()), "nonfinite decoded audio")
            encode(images, audio, graph, partial, CreateVideo, Types)
        properties = video_properties(partial)
        require((properties["width"], properties["height"], properties["frames"], properties["fps"]) ==
                (1312, 736, 107, "24/1"), "encoded geometry differs from original graph")
        with partial.open("rb") as f:
            os.fsync(f.fileno())
        os.replace(partial, output)
        record = {"schema": "r148-book-final-decode-result-v1", "passed": True,
                  "run_id": d["run_id"], "role": "fixed_phase", "decoder_owner": owner,
                  "gpu_admission": admission, "source": proof, "producer_seal_sha256": d["producer_seal_sha256"],
                  "binding_sha256": sha(HERE / "BINDING.json"),
                  "recovery_script_sha256": sha(__file__), "video": {
                      "file": str(output), "bytes": output.stat().st_size,
                      "sha256": sha(output), "properties": properties},
                  "valid_frames": 106, "crop": None, "native_audio_preserved": True,
                  "decoder_methods": ["VAELoader", "VAEDecode", "vae_decode_audio",
                                      "CreateVideo.execute", "VideoFromComponents.save_to"],
                  "started_unix": started, "finished_unix": time.time(),
                  "torch_version": torch.__version__, "video_vae_dtype": str(video_vae.vae_dtype),
                  "audio_vae_dtype": str(audio_vae.vae_dtype)}
    finally:
        images = audio = video_vae = audio_vae = samples = None
        import comfy.model_management
        comfy.model_management.unload_all_models()
        gc.collect()
        comfy.model_management.soft_empty_cache()
    write(out / "DECODE_RESULT.json", record)


def run(args):
    d = binding()
    sys.path.insert(0, str(Path(d["case_root"]) / "scripts"))
    require(args.gpu_uuid in ("GPU-REDACTED",
                              "GPU-REDACTED"), "use GPU1 or GPU2")
    gpu(args.gpu_uuid, idle=True)
    out = HERE / args.attempt
    out.mkdir()
    parent = identity(os.getpid())
    command = [sys.executable, "-u", str(Path(__file__).resolve()), "child",
               "--attempt", args.attempt, "--gpu-uuid", args.gpu_uuid]
    process = None
    owner = None
    failure = None
    try:
        with (out / "decode.log").open("x") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            from process_identity import bind_or_reap
            bind_or_reap(process, command)
            owner = identity(process.pid)
            write(out / "DECODER_PROCESS.json", {"owner": owner, "parent": parent, "command": command})
            deadline = time.monotonic() + 30
            while not (out / "READY.json").exists():
                require(process.poll() is None and time.monotonic() < deadline, "decoder ready timeout")
                time.sleep(.05)
            require(json.loads((out / "READY.json").read_text()) == owner, "decoder ready owner mismatch")
            write(out / "GO.json", {"child": owner, "parent": parent})
            require(process.wait(timeout=900) == 0, "decoder failed; inspect decode.log")
    except BaseException as e:
        failure = repr(e)
    finally:
        if process is not None and process.poll() is None:
            # Popen owns this unreaped direct child; never signal an old stored PID.
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=15)
        process_absent = owner is not None and identity(owner["pid"]) != owner
        cuda_absent = False
        release_gpu = None
        try:
            for _ in range(30):
                release_gpu = gpu(args.gpu_uuid)
                cuda_absent = owner is not None and not any(
                    p["pid"] == owner["pid"] for p in release_gpu["processes"])
                if cuda_absent:
                    break
                time.sleep(1)
        except BaseException as e:
            failure = failure or repr(e)
        released = process_absent and cuda_absent
        release = {"schema": "r148-book-decode-release-v1", "decoder_owner": owner,
                   "controller_owner": parent, "exit_code": process.returncode if process else None,
                   "process_absent": process_absent, "own_cuda_absent": cuda_absent,
                   "gpu": release_gpu, "released": released, "failure": failure,
                   "finished_unix": time.time()}
        write(out / "RELEASE.json", release)
    require(failure is None and released, "recovery failed or release unconfirmed: " + str(failure))
    result = json.loads((out / "DECODE_RESULT.json").read_text())
    require(result["decoder_owner"] == owner and result["passed"], "result owner mismatch")
    gate = {"schema": "r148-book-final-decode-recovery-gate-v1", "passed": True,
            "run_id": d["run_id"], "role": "fixed_phase", "source_attempt_complete": False,
            "source_attempt": d["source_attempt"], "producer_seal_sha256": d["producer_seal_sha256"],
            "binding_sha256": sha(HERE / "BINDING.json"), "decoder_owner": owner,
            "video": result["video"], "valid_frames": 106, "new_dit_forwards": 0,
            "source": result["source"], "decode_result": {
                "file": str(out / "DECODE_RESULT.json"), "sha256": sha(out / "DECODE_RESULT.json")},
            "release": {"file": str(out / "RELEASE.json"), "sha256": sha(out / "RELEASE.json")}}
    write(out / "RECOVERY_GATE.json", gate)
    print(json.dumps({"gate": str(out / "RECOVERY_GATE.json"), "video": gate["video"]}, indent=2))


def check(args):
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    d = binding()
    payload, proof = payload_and_proof(d)
    nodes, decode_audio, CreateVideo, Types, NestedTensor = imports(d, cpu=True)
    import torch
    # Tiny CPU encode exercises the exact native muxer API, including audio.
    graph = json.loads(Path(d["files"]["configs/graphs/" + d["run_id"] + ".json"]["file"]).read_text())
    output = HERE / "CPU_NATIVE_MUX_SMOKE.mp4"
    require(not output.exists(), "CPU smoke already exists; preserve it")
    encode(torch.zeros((2, 16, 16, 3)), {"waveform": torch.zeros((1, 2, 4000)),
           "sample_rate": 48000}, graph, output, CreateVideo, Types)
    props = video_properties(output)
    require(props["frames"] == 2 and props["fps"] == "24/1" and not torch.cuda.is_initialized(),
            "CPU native mux smoke failed")
    write(HERE / "CPU_PROOF.json", {"passed": True, "source": proof,
          "CUDA_initialized": torch.cuda.is_initialized(), "VAE_weights_loaded": False,
          "native_mux_smoke": {"file": str(output), "sha256": sha(output), "properties": props}})
    print("CPU endpoint, native decode API imports and native AV mux smoke passed; CUDA uninitialized.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("check", "run", "child"))
    p.add_argument("--attempt", default="attempt1")
    p.add_argument("--gpu-uuid")
    args = p.parse_args()
    require(args.attempt.isalnum(), "attempt must be one new alphanumeric directory")
    {"check": check, "run": run, "child": child}[args.mode](args)


if __name__ == "__main__":
    main()
