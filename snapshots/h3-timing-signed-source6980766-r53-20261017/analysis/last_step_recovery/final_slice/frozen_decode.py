import hashlib,os,subprocess,tempfile
from pathlib import Path
FALLBACK={"calls":0,"installed":[]}

def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def assert_idle_gpu(uuid):
    if not uuid or not uuid.startswith("GPU-") or any(c.isspace() for c in uuid):
        raise ValueError("an explicit full GPU UUID is required")
    text = subprocess.check_output([
        "nvidia-smi", "--id=" + uuid,
        "--query-gpu=uuid,memory.used,utilization.gpu", "--format=csv,noheader,nounits"], text=True)
    rows = [row.strip().split(",") for row in text.splitlines() if row.strip()]
    if len(rows) != 1 or rows[0][0].strip() != uuid:
        raise RuntimeError("GPU UUID did not resolve exactly")
    if int(rows[0][1]) > 64 or int(rows[0][2]) != 0:
        raise RuntimeError("GPU is not idle; refusing offline decode")
    processes = subprocess.check_output([
        "nvidia-smi", "--id=" + uuid, "--query-compute-apps=pid",
        "--format=csv,noheader,nounits"], text=True).strip()
    if processes:
        raise RuntimeError("GPU has a compute process; refusing offline decode")
    return {"uuid": uuid, "memory_used_mib": int(rows[0][1]), "utilization_percent": int(rows[0][2])}

def install_fallback_guard(vae_class):
    installed=[]
    def forbidden(*args,**kwargs):
        FALLBACK['calls']+=1
        raise RuntimeError('R19 rejects OOM spatial tiled fallback')
    for name in ('decode_tiled','decode_tiled_','decode_tiled_1d','decode_tiled_3d','_decode_tiled_owned'):
        if hasattr(vae_class,name):
            setattr(vae_class,name,forbidden);installed.append(name)
    if not installed or 'decode_tiled_3d' not in installed:
        raise ValueError('Unable to guard actual 3D fallback entry')
    FALLBACK['installed']=installed

def write_video(images, output, ffmpeg):
    """Fixed 24 fps, no geometry conversion/interpolation; only encode RGB frames."""
    fd, temporary = tempfile.mkstemp(prefix=".x0-decode-", suffix=".mp4", dir=output.parent)
    os.close(fd)
    height, width = images.shape[1:3]
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
               "-pixel_format", "rgb24", "-video_size", f"{width}x{height}",
               "-framerate", "24", "-i", "pipe:0", "-an", "-c:v", "libx264",
               "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
               "-movflags", "+faststart", temporary]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    stream_hash = hashlib.sha256()
    decoded_tensor_hash = hashlib.sha256()
    frame_hashes = []
    try:
        for frame in images:
            # Exact 8-bit conversion used by native VideoFromComponents.save_to.
            # Hash native VAE values a frame at a time to avoid a full-clip copy.
            decoded_tensor_hash.update(frame.contiguous().view(__import__("torch").uint8).numpy().tobytes())
            pixels = (frame * 255).clamp(0, 255).byte().contiguous()
            frame_bytes = pixels.numpy().tobytes()
            stream_hash.update(frame_bytes)
            frame_hashes.append(hashlib.sha256(frame_bytes).hexdigest())
            process.stdin.write(frame_bytes)
        process.stdin.close()
        error = process.stderr.read().decode(errors="replace")
        if process.wait() != 0:
            raise RuntimeError("ffmpeg failed: " + error[-2000:])
        if output.exists():
            raise FileExistsError(str(output))
        os.replace(temporary, output)
        return {"preencode_rgb24_sha256": stream_hash.hexdigest(),
                "preencode_rgb24_frame_sha256": frame_hashes,
                "preencode_quantization": "native SaveVideo: (frame * 255).clamp(0, 255).byte(); truncate, no rounding",
                "decoded_tensor_sha256": decoded_tensor_hash.hexdigest(),
                "decoded_tensor_hash_layout": "contiguous FHWC raw dtype bytes, streamed one frame at a time"}
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        if process.stderr:
            process.stderr.close()
        if os.path.exists(temporary):
            os.unlink(temporary)
