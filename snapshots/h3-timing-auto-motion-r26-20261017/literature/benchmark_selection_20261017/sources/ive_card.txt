---
license: mit
configs:
  - config_name: Default
    data_files:
      - split: short_prompt
        path: ivebenchdb_prompt_short.json
      - split: long_prompt
        path: livebenchdb_prompt_long.json
pretty_name: IVEBench
---

<p align="center">
    <a href="">
<img width="765" alt="image" src="assets/title.png">
     </a>
   <p align="center">
<p align="center">
    <a href="https://scholar.google.com.hk/citations?user=-WKfgd0AAAAJ&hl=zh-CN"><strong>Yinan Chen <sup>1★</sup></strong></a>
    ·
    <a href="https://zhangzjn.github.io/"><strong>Jiangning Zhang <sup>1,2★</sup></strong></a>
    ·
    <a href="https://sjtuplayer.github.io/"><strong>Teng Hu <sup>3</sup></strong></a>
    ·
    <a href=""><strong>Yuxiang Zeng <sup>4</sup></strong></a>
    ·
    <a href="https://scholar.google.com/citations?hl=zh-CN&user=m3KDreEAAAAJ"><strong>Zhucun Xue <sup>1</sup></strong></a>
    ·
    <br><a href="https://scholar.google.com/citations?user=gUJWww0AAAAJ"><strong>Qingdong He <sup>2</sup></strong></a>
    ·
    <a href="https://scholar.google.com/citations?user=fqte5H4AAAAJ"><strong>Chengjie Wang <sup>2,3</sup></strong></a>
    ·
    <a href="https://scholar.google.com/citations?user=qYcgBbEAAAAJ"><strong>Yong Liu <sup>1</sup></strong></a>
    ·
    <a href="https://huuxiaobin.github.io/"><strong>Xiaobin Hu <sup>2</sup></strong></a>
    ·
    <a href="https://yanshuicheng.info/"><strong>Shuicheng Yan <sup>5</sup></strong></a>
</p>
<p align="center">
    <strong><sup>1</sup>Zhejiang University</strong> &nbsp;&nbsp;&nbsp; 
    <strong><sup>2</sup>YouTu Lab, Tencent</strong> &nbsp;&nbsp;&nbsp; 
    <strong><sup>3</sup>Shanghai Jiao Tong University</strong>
    <br>
    <strong><sup>4</sup>University of Auckland</strong> &nbsp;&nbsp;&nbsp;
    <strong><sup>5</sup>National University of Singapore</strong>
</p>
<p align="center">
    <a href=''>
      <img src='https://img.shields.io/badge/arXiv-PDF-red?style=flat&logo=arXiv&logoColor=red' alt='arXiv PDF'>
         </a>
<a href="https://huggingface.co/datasets/Coraxor/IVEBench-DB"><img src="https://img.shields.io/static/v1?label=%F0%9F%A4%97%20Hugging%20Face&message=Dataset&color=yellow"></a>
    <a href='https://ryanchenyn.github.io/projects/IVEBench/'>
      <img src='https://img.shields.io/badge/IVEBench-Website-green?style=flat&logo=googlechrome&logoColor=green' alt='webpage-Web'>
         </a>
</p>




# 😊 Dataset Introduction

**IVEBench DB** is the official dataset accompanying  
[🎞️ IVEBench: Modern Benchmark Suite for Instruction-Guided Video Editing Assessment](https://ryanchenyn.github.io/projects/IVEBench/).

This repository provides the **metadata ** for the IVEBench, and the files and description are as follows:

| File | Description |
|------|--------------|
| `IVEBench-DB_name_mapping.csv` | Maps source video names to their ordered names and original download URLs. |
| `ivebench_prompt_short.json` | Metadata for the short subset (32–128 frames). |
| `ivebench_prompt_long.json` | Metadata for the long subset (129–1024 frames). |
| `ivebenchdb_mp4_short` | the collection of `.mp4` videos for the short subset (32–128 frames). |
| `ivebenchdb_mp4_long` | the collection of `.mp4` videos for the long subset (129–1024 frames). |

Before using this dataset as the source video for IVEBench Metrics calculation, you need to convert the `.mp4` video file into a folder of video frames using the provided script. Additionally, if your method has constraints on the resolution or total number of frames of the source video, you can use the given script to downscale the resolution and perform frame sampling on the frame-based source video. You can refer to [IVEBench](https://github.com/RyanChenYN/IVEBench?tab=readme-ov-file#usage) for the detailed conversion scripts and steps.


# 🎥 Data Pipeline

<img src="assets/pipeline.png" width.="1000px">

**Data acquisition and processing pipeline of IVEBench.** **1)** Curation process to 600 high-quality diverse videos. **2)** Well-designed pipeline for comprehensive editing prompts.

The playback of the source videos can be viewed on [IVEBench website](https://ryanchenyn.github.io/projects/IVEBench/#results-carousel).

<a name="benchmark-statistics"></a>

# 🌈 Benchmark Statistics

<img src="assets/data_fig1.png" width.="1000px">

Statistical distributions of IVEBench DB



# ⚙️ Usage

- 🥰You can easily download IVEBench DB to your local path using the following command:

  ```bash
  huggingface-cli download --repo-type dataset --resume-download Coraxor/IVEBench --local-dir $YOUR_LOCAL_PATH
  ```

  
------

# ⚠️ Disclaimer

- This dataset **contains only publicly accessible video URLs and metadata**, not the raw video content.
- All original videos belong to their respective copyright holders and hosting platforms.
- The dataset is released solely for **academic research and educational purposes** under the terms of the MIT license.
- Users must follow the licenses and usage terms of original video sources if re-downloading or redistributing content.


# 🖊️ Citation

If you If you find o [IVEBench](https://ryanchenyn.github.io/projects/IVEBench)  useful for your research, please consider giving a like❤️ and citation📝 :)

```bibtex
@article{chen2025ivebench,
  title={IVEBench: Modern Benchmark Suite for Instruction-Guided Video Editing Assessment},
  author={Chen, Yinan and Zhang, Jiangning and Hu, Teng and Zeng, Yuxiang and Xue, Zhucun and He, Qingdong and Wang, Chengjie and Liu, Yong and Hu, Xiaobin and Yan, Shuicheng},
  journal={arXiv preprint arXiv:2510.11647},
  year={2025}
}
```

------

# ✉️ Contact

```
yinanchencs@outlook.com
186368@zju.edu.cn
```

