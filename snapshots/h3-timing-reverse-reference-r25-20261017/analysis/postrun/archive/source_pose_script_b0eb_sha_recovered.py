"""CPU-only DWPose diagnostics using existing ComfyUI auxiliary model files.

No synthesis, model installation, GPU allocation, interpolation, or video rewrite.
Preserves every detected person and raw COCO-17 coordinates/scores. One tracked
person is selected independently per clip, never by matching edited/source poses.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

COCO17 = ['nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
          'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
          'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
          'left_knee', 'right_knee', 'left_ankle', 'right_ankle']
DEFAULT_AUX = '/data5/researcher/ComfyUI/custom_nodes/comfyui_controlnet_aux'


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')
    tmp.replace(path)


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def iou(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    return intersection / max(1, area_a + area_b - intersection)


def select_person(detections, previous):
    if not detections:
        return None, [], False
    boxes = [d['box_xyxy'] for d in detections]
    areas = [max(0, b[2]-b[0])*max(0, b[3]-b[1]) for b in boxes]
    if previous is None:
        scores = areas
    else:
        # Continuity is primary; relative area only breaks approximately equal ties.
        scores = [iou(b, previous) + 0.05*a/max(areas) for b, a in zip(boxes, areas)]
    chosen = max(range(len(scores)), key=lambda i: scores[i])
    ordered = sorted(scores, reverse=True)
    ambiguous = len(ordered) > 1 and ordered[0] - ordered[1] < 0.1*max(ordered[0], 0.01)
    return chosen, scores, ambiguous


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video', action='append', required=True)
    p.add_argument('--output-dir', required=True)
    p.add_argument('--aux-root', default=DEFAULT_AUX)
    p.add_argument('--threads', type=int, default=4, choices=range(1, 5))
    p.add_argument('--frame-start', type=int, default=0)
    p.add_argument('--frame-end', type=int, help='inclusive; default whole video')
    p.add_argument('--stride', type=int, default=1)
    p.add_argument('--force', action='store_true')
    p.add_argument('--overlay-frame', type=int, action='append', default=[])
    args = p.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[name] = str(args.threads)
    import cv2
    import numpy as np
    import onnxruntime as ort
    import torch
    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(1)
    cv2.setNumThreads(1)
    root = Path(args.aux_root)
    module_root = root / 'src/custom_controlnet_aux/dwpose'
    det_module = module_root / 'dw_onnx/cv_ox_det.py'
    pose_module = module_root / 'dw_torchscript/jit_pose.py'
    det_path = root / 'ckpts/yzd-v/DWPose/yolox_l.onnx'
    pose_path = root / 'ckpts/hr16/DWPose-TorchScript-BatchSize5/dw-ll_ucoco_384_bs5.torchscript.pt'
    detector = import_file('pose_probe_detector', det_module)
    pose_utils = import_file('pose_probe_pose', pose_module)
    options = ort.SessionOptions()
    options.intra_op_num_threads = args.threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.add_session_config_entry('session.intra_op.allow_spinning', '0')
    options.add_session_config_entry('session.inter_op.allow_spinning', '0')
    session = ort.InferenceSession(str(det_path), sess_options=options, providers=['CPUExecutionProvider'])
    model = torch.jit.load(str(pose_path), map_location='cpu').float().eval()
    assert session.get_providers() == ['CPUExecutionProvider']
    assert next(model.parameters()).device.type == 'cpu'
    provenance = {
        'detector_path': str(det_path), 'detector_sha256': sha256(det_path),
        'pose_path': str(pose_path), 'pose_sha256': sha256(pose_path),
        'detector_code_sha256': sha256(det_module), 'pose_code_sha256': sha256(pose_module),
        'script_sha256': sha256(__file__), 'torch': torch.__version__, 'opencv': cv2.__version__,
        'onnxruntime': ort.__version__, 'providers': session.get_providers(), 'device': 'cpu',
        'threads': args.threads, 'pose_input_wh': [288, 384], 'pose_batch_size': 5,
        'color_order': 'RGB, matching the existing DWPose detector public API',
        'detector_threshold': 0.3, 'nms_threshold': 0.45,
        'pose_confidence_note': 'raw SimCC peak minimum; may exceed 1, not calibrated probability',
        'selection_rule': 'largest box initially; thereafter maximal IoU(previous)+0.05*relative area; reset after 12 missed sampled frames',
    }
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    def detect(rgb):
        data, ratio = detector.preprocess(rgb, (640, 640))
        result = session.run(None, {session.get_inputs()[0].name: data[None].astype(np.float32)})
        predictions = detector.demo_postprocess(result[0], (640, 640))[0]
        boxes = predictions[:, :4]
        xyxy = np.column_stack((boxes[:, 0]-boxes[:, 2]/2, boxes[:, 1]-boxes[:, 3]/2,
                                boxes[:, 0]+boxes[:, 2]/2, boxes[:, 1]+boxes[:, 3]/2)) / ratio
        scores = predictions[:, 4:5] * predictions[:, 5:]
        dets = detector.multiclass_nms(xyxy, scores, nms_thr=0.45, score_thr=0.1)
        if dets is None:
            return []
        return [{'box_xyxy': row[:4].tolist(), 'detector_score': float(row[4]), 'class_id': 0}
                for row in dets if row[4] > 0.3 and row[5] == 0]

    for filename in args.video:
        video = Path(filename)
        destination = output_dir / (video.stem + '.pose.json')
        video_hash = sha256(video)
        if destination.exists() and not args.force:
            existing = json.loads(destination.read_text())
            if (existing['video']['sha256'] == video_hash and
                    existing['extraction'] == {'start': args.frame_start, 'end': args.frame_end, 'stride': args.stride}):
                print(json.dumps({'skipped_existing': str(destination)}), flush=True)
                continue
            raise RuntimeError(f'Existing output differs; use another directory or --force: {destination}')
        started = time.monotonic()
        cap = cv2.VideoCapture(str(video))
        if not cap.isOpened():
            raise RuntimeError(f'Cannot open {video}')
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        metadata = {'path': str(video), 'sha256': video_hash, 'fps': fps,
                    'container_frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                    'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), 'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}
        records, pending, previous, missed = [], [], None, 0
        detector_seconds, pose_seconds = 0.0, 0.0
        overlay_images = {}

        def flush_batch():
            nonlocal pose_seconds
            if not pending:
                return
            t0 = time.monotonic()
            crops = [item['crop'] for item in pending]
            batch = crops + [np.zeros_like(crops[0])] * (5-len(crops))
            data = torch.from_numpy(np.stack(batch).transpose(0, 3, 1, 2)).float()
            with torch.inference_mode():
                result = model(data)
            raw = [x.float().cpu().numpy() for x in result]
            split = [[x[i:i+1] for x in raw] for i in range(len(pending))]
            xy, confidence = pose_utils.postprocess(split, (288, 384),
                          [item['center'] for item in pending], [item['scale'] for item in pending])
            for item, points, scores in zip(pending, xy, confidence):
                item['person']['coco17_xy'] = points[:17].tolist()
                item['person']['coco17_score'] = scores[:17].tolist()
            pending.clear()
            pose_seconds += time.monotonic()-t0

        index = -1
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            index += 1
            if args.frame_end is not None and index > args.frame_end:
                break
            if index < args.frame_start or (index-args.frame_start) % args.stride:
                continue
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            t0 = time.monotonic()
            people = detect(rgb)
            detector_seconds += time.monotonic()-t0
            chosen, scores, ambiguous = select_person(people, previous)
            if chosen is None:
                missed += 1
                if missed >= 12:
                    previous = None
            else:
                previous = people[chosen]['box_xyxy']
                missed = 0
            record = {'frame': index, 'time_s': index/fps, 'decoder_pos_msec': cap.get(cv2.CAP_PROP_POS_MSEC),
                      'persons': people, 'selected_person': chosen, 'selection_scores': scores,
                      'selection_ambiguous': ambiguous}
            records.append(record)
            if people:
                crops, centers, scales = pose_utils.preprocess(rgb, [x['box_xyxy'] for x in people], (288, 384))
                for person, crop, center, scale in zip(people, crops, centers, scales):
                    pending.append({'person': person, 'crop': crop, 'center': center, 'scale': scale})
                    if len(pending) == 5:
                        flush_batch()
            if index in args.overlay_frame:
                overlay_images[index] = bgr
            if len(records) % 25 == 0:
                print(json.dumps({'video': video.name, 'processed': len(records), 'frame': index,
                                  'elapsed_s': round(time.monotonic()-started, 2)}), flush=True)
        flush_batch()
        cap.release()
        selected_scores = [r['persons'][r['selected_person']]['coco17_score']
                           for r in records if r['selected_person'] is not None]
        score_array = np.array(selected_scores)
        stats = {'processed_frames': len(records), 'missing_person_frames': sum(r['selected_person'] is None for r in records),
                 'multiple_person_frames': sum(len(r['persons']) > 1 for r in records),
                 'ambiguous_selection_frames': sum(r['selection_ambiguous'] for r in records),
                 'detector_s': detector_seconds, 'pose_s': pose_seconds, 'elapsed_s': time.monotonic()-started,
                 'joint_valid_fraction_at_0_3': (score_array >= 0.3).mean(0).tolist() if score_array.size else None,
                 'joint_median_raw_score': np.median(score_array, axis=0).tolist() if score_array.size else None}
        result = {'schema': 'h3_cpu_pose_v1', 'video': metadata, 'provenance': provenance,
                  'extraction': {'start': args.frame_start, 'end': args.frame_end, 'stride': args.stride},
                  'joint_order': COCO17, 'statistics': stats, 'frames': records}
        write_json(destination, result)
        edges = [(5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11), (6, 12),
                 (11, 12), (11, 13), (13, 15), (12, 14), (14, 16)]
        for record in records:
            if record['frame'] not in overlay_images:
                continue
            frame = overlay_images[record['frame']]
            for person_index, person in enumerate(record['persons']):
                xy = np.array(person['coco17_xy']).round().astype(int)
                scores = np.array(person['coco17_score'])
                color = (0, 255, 0) if person_index == record['selected_person'] else (0, 180, 255)
                for a, b in edges:
                    if min(scores[a], scores[b]) >= 0.3:
                        cv2.line(frame, tuple(xy[a]), tuple(xy[b]), color, 2)
                for j, point in enumerate(xy):
                    if scores[j] >= 0.3:
                        cv2.circle(frame, tuple(point), 4, color, -1)
                        cv2.putText(frame, str(j), tuple(point+4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            cv2.imwrite(str(output_dir / f'{video.stem}.frame{record["frame"]:03d}.pose.jpg'), frame)
        print(json.dumps({'saved': str(destination), 'statistics': stats}), flush=True)


if __name__ == '__main__':
    main()
