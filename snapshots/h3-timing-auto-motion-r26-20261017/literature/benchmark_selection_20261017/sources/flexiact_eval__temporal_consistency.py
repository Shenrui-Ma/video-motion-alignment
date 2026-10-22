import os
import cv2
import torch
import clip
import numpy as np
from PIL import Image
from sklearn.metrics.pairwise import cosine_similarity
import subprocess

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

def calculate_pairwise_cosine_similarity(features):
    """
    Compute the pairwise cosine similarity of all frames
    :param features: CLIP feature matrix (n_frames, feature_dim)
    :return: Average pairwise cosine similarity
    """
    if len(features) < 2:
        return 0.0  # If there are less than 2 frames, return 0
    
    # Compute the cosine similarity matrix of all frames
    similarity_matrix = cosine_similarity(features)
    
    # Extract the upper triangle (excluding the diagonal)
    upper_triangle = np.triu(similarity_matrix, k=1)
    
    # Compute the average of non-zero elements
    avg_similarity = np.sum(upper_triangle) / np.count_nonzero(upper_triangle)
    
    return avg_similarity

def process_video(video_path):
    """
    Process a single video, compute the pairwise cosine similarity of all frames
    :param video_path: Path to the video
    :return: Average pairwise cosine similarity
    """
    # Extract video frames
    frames = extract_frames(video_path)
    if not frames:
        print(f"No frames extracted from {video_path}")
        return 0.0
    
    # Compute CLIP features
    features = compute_clip_features(frames)
    
    # Compute the pairwise cosine similarity of all frames
    avg_pairwise_similarity = calculate_pairwise_cosine_similarity(features)
    return avg_pairwise_similarity

def process_videos_in_directory(directory):
    """
    Recursively traverse all videos in the path, compute the pairwise cosine similarity of each video
    :param directory: Path to the target directory
    :return: List of pairwise cosine similarity for all videos
    """
    # Supported video file extensions
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
    
    # Store the pairwise cosine similarity for all videos
    all_similarities = []
    
    # Traverse the directory
    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in video_extensions):
                video_path = os.path.join(root, file)
                print(f"Processing: {video_path}")
                
                try:
                    # Compute the pairwise cosine similarity of the current video
                    avg_pairwise_similarity = process_video(video_path)
                    all_similarities.append(avg_pairwise_similarity)
                    print(f"Average pairwise cosine similarity: {avg_pairwise_similarity:.4f}")
                except Exception as e:
                    print(f"Failed to process {video_path}: {e}")
    
    # Compute the mean of the pairwise cosine similarity of all videos
    if all_similarities:
        overall_avg_similarity = np.mean(all_similarities)
        print(f"Overall average pairwise cosine similarity: {overall_avg_similarity:.4f}")
    else:
        print("No videos processed.")
    
    return all_similarities

# Example call
target_directory = "./FlexiAct_Output/" # change to your own output path
all_similarities = process_videos_in_directory(target_directory)
