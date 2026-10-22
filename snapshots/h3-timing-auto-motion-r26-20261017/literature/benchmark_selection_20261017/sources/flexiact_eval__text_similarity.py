import os
import csv
import torch
import clip
import numpy as np
from PIL import Image
from sklearn.metrics.pairwise import cosine_similarity
import subprocess
import cv2

# Load CLIP model
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)

def extract_frames(video_path, max_frames=None):
    """
    Extract frames from a video
    :param video_path: Path to the video
    :param max_frames: Maximum number of frames to extract (None for all frames)
    :return: List of frames (PIL images)
    """
    cap = cv2.VideoCapture(video_path)
    frames = []
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if max_frames is not None and frame_count >= max_frames:
            break

        # Convert OpenCV BGR image to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Convert to PIL image
        frame_pil = Image.fromarray(frame_rgb)
        frames.append(frame_pil)
        frame_count += 1

    cap.release()
    return frames

def compute_clip_features(images):
    """
    Compute CLIP image features
    :param images: List of PIL images
    :return: CLIP feature matrix (n_frames, feature_dim)
    """
    # Preprocess images and stack into a tensor
    images_preprocessed = torch.stack([preprocess(img) for img in images]).to(device)
    
    # Compute CLIP features
    with torch.no_grad():
        features = model.encode_image(images_preprocessed)
    
    return features.cpu().numpy()

def compute_text_clip_features(text):
    """
    Compute CLIP text features
    :param text: Text
    :return: CLIP text feature (1, feature_dim)
    """
    # Clip text length (CLIP's maximum length is 77)
    text = text[:77]
    
    # Compute CLIP text features
    with torch.no_grad():
        text_tokens = clip.tokenize([text]).to(device)
        text_features = model.encode_text(text_tokens)
    
    return text_features.cpu().numpy()

def calculate_text_clip_similarity(video_path, ori_prompt):
    """
    Compute the CLIP similarity between video frames and text
    :param video_path: Path to the video
    :param ori_prompt: Original text prompt
    :return: Average CLIP similarity
    """
    # Extract video frames
    frames = extract_frames(video_path)
    if not frames:
        print(f"No frames extracted from {video_path}")
        return 0.0
    
    # Compute the CLIP features of the video frames
    frame_features = compute_clip_features(frames)
    
    # Compute the CLIP features of the text
    text_features = compute_text_clip_features(ori_prompt)
    
    # Compute the cosine similarity between the video frames and the text
    similarities = cosine_similarity(text_features, frame_features)
    
    # Return the average similarity
    return np.mean(similarities)

def process_video(video_path, motion, name_prompt):
    """
    Process a single video, compute the CLIP similarity with the matching ori_prompt
    :param video_path: Path to the video
    :param motion: Motion name
    :param name_prompt: Text prompt corresponding to the video name
    :return: Average CLIP similarity
    """
    # Check the CSV file path
    csv_path = f"./data/motioninversion/{motion}/val_image.csv" # change to your own csv path
    if not os.path.exists(csv_path):
        csv_path = f"./data/motioninversion/animal/{motion}/val_image.csv" # change to your own csv path
        if not os.path.exists(csv_path):
            print(f"No CSV file found for motion: {motion}")
            return 0.0
    
    # Read the CSV file
    with open(csv_path, 'r') as file:
        reader = csv.reader(file)
        next(reader)  # Skip the header
        for row in reader:
            ori_prompt = row[1]  # The second column is ori_prompt
            if ori_prompt.startswith(name_prompt):
                # Compute the CLIP similarity between the video and the ori_prompt
                avg_similarity = calculate_text_clip_similarity(video_path, ori_prompt)
                return avg_similarity
    
    print(f"No matching ori_prompt found for {name_prompt}")
    return 0.0

def process_videos_in_directory(directory):
    """
    Recursively traverse all videos in the path, compute the CLIP similarity with the matching ori_prompt
    :param directory: Path to the target directory
    :return: List of CLIP similarity for all videos
    """
    # Supported video file extensions
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
    
    # Store the CLIP similarity for all videos
    all_similarities = []
    
    # Traverse the directory
    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in video_extensions):
                video_path = os.path.join(root, file)
                print(f"Processing: {video_path}")
                
                # Get name_prompt
                name_prompt = file.split('.')[0]  # Remove the extension
                name_prompt = ' '.join(name_prompt.split('_')[:-3])  # Join words with spaces
                
                # Get motion
                motion = os.path.basename(root)
                
                try:
                    # Compute the CLIP similarity of the current video
                    avg_similarity = process_video(video_path, motion, name_prompt)
                    all_similarities.append(avg_similarity)
                    print(f"Average CLIP similarity: {avg_similarity:.4f}")
                except Exception as e:
                    print(f"Failed to process {video_path}: {e}")
    
    # Compute the mean of the CLIP similarity of all videos
    if all_similarities:
        overall_avg_similarity = np.mean(all_similarities)
        print(f"Overall average CLIP similarity: {overall_avg_similarity:.4f}")
    else:
        print("No videos processed.")
    
    return all_similarities

# Example call
target_directory = "./FlexiAct_Output/" # change to your own output path
all_similarities = process_videos_in_directory(target_directory)