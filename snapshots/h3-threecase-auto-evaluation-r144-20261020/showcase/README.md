# R144 结果页生成器

`render.py` 使用 Python 标准库，将显式清单中的本地视频、截图嵌入一个中文 HTML。本次三例置前，历史机舱 R138 置后。缺项显示“待评估”。`manifest.draft.json` 已填入评估计划中的真实 Native / 固定引导事件与 MF，自动结果等待绑定。

所有输出留在本 `showcase/` 目录；已有文件保留，更新时使用新文件名。视频沿用 `prepare_review.py` 已制作的黑底宽幅三列成片。

## 当前可用

```sh
cd /Users/researcher/DevProjects/h3-threecase-auto-evaluation-r144-20261020/showcase
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_render.py
python3 render.py --manifest manifest.draft.json --check
python3 render.py --manifest manifest.draft.json --output preview.html
```

`--check` 校验清单、证据 SHA、媒体 SHA 和帧编号，保持文件原样。`preview.html` 中当前三例显示待评估，历史 R138 使用已完成的真实视频与第 50、72 帧。

## 新成片到齐后

先由根任务用上一级 `prepare_review.py` 验证真实完成链并生成各例 `FRAME_LEDGER.json`。生成器通过 ledger 绑定实际 producer；可消费当前 `_cached_gpu2` 路径，无需修改本脚本。

```sh
python3 render.py --manifest manifest.draft.json \
  --bind-review short_0358=../review/short_0358/FRAME_LEDGER.json \
  --bind-review long_0039=../review/long_0039/FRAME_LEDGER.json \
  --bind-review long_0059=../review/long_0059/FRAME_LEDGER.json \
  --save-manifest manifest.bound.json --check
```

复制 `manifest.bound.json` 为新的 `manifest.results.json`，填入下列真实结果，再渲染：

```sh
python3 render.py --manifest manifest.results.json --check
python3 render.py --manifest manifest.results.json --output results.html
```

输入清单中的 `file` 必须为绝对本地路径，`sha256` 为该文件完整内容的 SHA256。页面仅用本地素材；成片播放、固定对照切换和截图可离线使用。

## 需要填写的字段

每个 `cases[]` 对象沿用 `source_id`：

- `inputs`：参考 / Native / 固定来自计划；`--bind-review` 填自动成片绑定。
- `frame_ledger`、`media.automatic`、`media.fixed`：`--bind-review` 自动填充。三列依次为参考、普通编辑、自动或固定引导。
- `screenshots`：从 ledger 的 `pages[]` 选择截图，保留其 `file`、`sha256`、`physical_frames`；补 `columns: ["source","native","fixed","automatic"]`。这些现有页为四列同帧 contact sheet。可选 `caption`。帧编号与 ledger 精确核对。
- `control`：填写实际执行记录和其证据，格式如下。每个未提供的步骤显示待评估；全部 20 步 OFF 需要提供 20 条明确的 false。
- `events.rows[]`：按既有事件 ID 填 `automatic: [最早帧, 最晚帧]`；未知保持 null。`events.evidence` 追加人工同帧审阅记录的文件绑定。页面计算中点帧差及区间；已缓存的最终 pose 离线 lag 与在线开关分别记录。
- `mf.values.automatic`：填官方 IVEBench MF；`mf.evidence` 追加完成结果文件绑定。Native / 固定值已来自计划。
- `conclusion`：填写本例简短的结果结论，未完成保持 null。

实际开关字段示意（结构示意，具体数值由真实记录填写）：

```json
{
  "control": {
    "evidence": [{"file": "/absolute/path/to/ACTUAL_CONTROL_PROGRESS.json", "sha256": "..."}],
    "decisions": [
      {"step_0based": 0, "on": false, "windows": []}
    ]
  }
}
```

帧域为各例有效物理帧，步骤和帧均从 0 编号。ON 记录必须有窗口，OFF 记录窗口为空。数据证据可多条，SHA 在每次渲染时校验；人工转录的事件、开关和 MF 值由提交清单的评估者核对原始记录。

## 历史机舱

`history` 只需绑定真实 R138 最终 `REPORT_HANDOFF.json`。脚本读取其中原提示词、事件、开关、官方 MF、视频与第 50 / 72 帧。默认展示参考 / 普通编辑 / 自动三列；切换为参考 / 历史固定 / 自动，列名随之更新。

R138 使用 P1 历史完整上下文提示词，历史固定基线为同提示词。R141b 是简短提示词下的固定引导；该结果单独登记，当前页面保留这一区分。当前三个 R144 条目使用各自原始提示词。

重新初始化清单：

```sh
python3 render.py --init manifest.new.json \
  --history-report /Users/researcher/DevProjects/h3-oxygen-online-recovery-metrics-r138-20261020/audit/REPORT_HANDOFF.json
```
