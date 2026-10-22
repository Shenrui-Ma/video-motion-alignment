from diffusers.utils import export_to_video, load_video
from decord import VideoReader, cpu
import numpy as np
import os
import random

action_name = "camera4" # your action name, same with the reference video name
subject_type = "camera" # camera, human, animal
start_second = 3 # start second of the action
end_second = 9 # end second of the action

crop_ratio = 0.8
video_path = f"benchmark/reference_videos/{subject_type}/{action_name}.mp4" # path to the reference video
video = load_video(video_path)

# fps
cpu_idx = random.randint(0, os.cpu_count() - 1)
vr = VideoReader(video_path, ctx=cpu(cpu_idx))
first_frame = vr[0]
height, width = first_frame.shape[:2]
fps = int(round(vr.get_avg_fps()))
print(f"fps: {fps}")
print(f"height: {height}, width: {width}, length: {len(video)}")

# video = video[::fps//8]
video = video[round(start_second*fps):round(end_second*fps)]
# uniformly sample 49 frames
video = [video[int(i*len(video)/49)] for i in range(49)]
name, postfix = video_path.split(".")

cur_dir = f"benchmark/reference_videos/{subject_type}"
os.makedirs(f"{cur_dir}/{action_name}_crop", exist_ok=True)
top_left = (0, 0, int(height * crop_ratio), int(width * crop_ratio))
top_center = (0, int(width * ((1 - crop_ratio) / 2)), int(height * crop_ratio), int(width * crop_ratio))
top_right = (0, int(width * (1 - crop_ratio)), int(height * crop_ratio), int(width * crop_ratio))
center_left = (int(height * ((1 - crop_ratio) / 2)), 0, int(height * crop_ratio), int(width * crop_ratio))
center_center = (int(height * ((1 - crop_ratio) / 2)), int(width * ((1 - crop_ratio) / 2)), int(height * crop_ratio), int(width * crop_ratio))
center_right = (int(height * ((1 - crop_ratio) / 2)), int(width * (1 - crop_ratio)), int(height * crop_ratio), int(width * crop_ratio))
bottom_left = (int(height * (1 - crop_ratio)), 0, int(height * crop_ratio), int(width * crop_ratio))
bottom_center = (int(height * (1 - crop_ratio)), int(width * ((1 - crop_ratio) / 2)), int(height * crop_ratio), int(width * crop_ratio))
bottom_right = (int(height * (1 - crop_ratio)), int(width * (1 - crop_ratio)), int(height * crop_ratio), int(width * crop_ratio))
ori = (0, 0, height, width)

crop_areas = [top_left, top_center, top_right, 
              center_left, center_center, center_right, 
              bottom_left, bottom_center, bottom_right,
              ori, ori, ori]
# Random Crop
video = np.array(video)
for crop_area in crop_areas:
    video_crop = [frame[crop_area[0]:crop_area[0]+crop_area[2], crop_area[1]:crop_area[1]+crop_area[3]] / 255.0 for frame in video]
    idx = 0
    while os.path.exists(f"{cur_dir}/{action_name}_crop/{idx}.{postfix}"):
        idx += 1
    export_to_video(video_crop, f"{cur_dir}/{action_name}_crop/{idx}.{postfix}")