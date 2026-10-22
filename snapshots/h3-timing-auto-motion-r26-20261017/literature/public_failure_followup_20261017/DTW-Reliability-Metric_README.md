# Reliability Metric for DTW Alignments

This repository contains a framework for assessing the reliability of Dynamic Time Warping (DTW) alignments. Given a DTW alignment path, we propose a metric that indicates how reliable a local segment of the alignment path is. 

The intuition for our metric is based on the idea of circumstantial evidence.  If DTW has found a very prominent path, then if we re-run the alignment with relaxed boundary conditions, it will still pick the same path. If, on the other hand, DTW has found a “weak” path, then re-running the alignment with relaxed boundary conditions will likely yield a different path. Accordingly, our reliability metric is computed by picking a local section of the DTW alignment path, re-estimating the alignment with FlexDTW (which allows flexibility in the boundary conditions), and then measuring how well the DTW and FlexDTW paths agree.

## Core Workflow

To reproduce the results, follow these steps in order:

### 1. Generate Benchmark Features
Build the benchmarks by creating tampered audio pairs and extracting their chroma features.

```bash
python generate_confidence_benchmarks.py -n 10 --mazurkas Chopin_Op017No4 Chopin_Op063No3 --out_dir results/my_experiment
```
- `-n`: Number of recordings per Mazurka (e.g., `10`, `64`).
- `--mazurkas`: Space-separated list of Mazurka sets to use.
- `--out_dir`: Directory to save features and `ground_truth.json`.
- `--workers`: (Optional) Number of parallel workers (default: `20`).
- `--save_clips`: (Optional) Save the tampered audio clips as `.wav` for inspection.

### 2. Run Confidence Experiments
Run the confidence estimation systems (Percent Agreement) on the generated benchmarks.

```bash
python evaluation/run_confidence_experiments.py -n 10 --gt_dir results/my_experiment --output_dir results/my_experiment/experiments -y 5,10
```
- `-n`: N from the previous step (used for metadata/logging).
- `--gt_dir`: Directory containing `ground_truth.json`.
- `--output_dir`: Directory to save system-level CSV results.
- `-y`: (Optional) Comma-separated frame tolerances to evaluate against (default: `5,10`).

### 3. Run Baseline Experiment
Run the baseline metric (raw cost matrix values) for comparison.

```bash
python evaluation/run_baseline_experiment.py -n 10 --gt_dir results/my_experiment --output_dir results/my_experiment/experiments -y 5,10
```

### 4. Evaluate Metrics
Aggregate and summarize the results using binary classification metrics (EER, TPR@1%FA, AUROC).

```bash
python evaluation/evaluate_metrics.py --input_dir results/my_experiment/experiments --output_dir results/my_experiment/evaluation --mvns_column MvsN_Y5
```
- `--input_dir`: Directory containing `*_results.csv` files from steps 2 and 3.
- `--output_dir`: Directory to save the final `experiment_summary.csv`.
- `--mvns_column`: The ground truth column to evaluate against (e.g., `MvsN_Y5` or `MvsN_Y10`).
- `--invert_distance`: (Optional) Use this flag if evaluating a distance-based metric instead of confidence.

## Repository Structure

- `alignment/`: Core DTW logic, FlexDTW implementation, and alignment error utilities.
- `benchmarks/`: Logic for generating tampered pairs and loading audio/beats.
- `confidence/`: Implementation of confidence metrics (e.g., Percent Agreement).
- `evaluation/`: Scripts for running experiments and computing metrics.
- `generate_confidence_benchmarks.py`: Entry point for benchmark creation and feature extraction.
- `environment.yaml`: Conda environment definition.

## Requirements
The environment can be set up using:
```bash
conda env create -f environment.yaml
conda activate dtw-confidence
```
Main dependencies include `librosa`, `numpy`, `pandas`, `scipy`, `scikit-learn`, and `numba`.

## Reference

Aanya Pratapneni, Alice Yuan, and TJ Tsai.  "Estimating the Reliability of Dynamic Time Warping Alignments Using Circumstantial Evidence."  Proceedings of the International Society for Music Information Retrieval Conference (ISMIR), 2026.

The paper can be found [here](https://drive.google.com/file/d/1dBqjQBtOv6IykikSM_Tyekjm1YAS4SnK/view).
