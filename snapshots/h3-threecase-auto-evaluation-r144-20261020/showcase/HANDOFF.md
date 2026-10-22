# 结果页生成器交接

目录：`/Users/researcher/DevProjects/h3-threecase-auto-evaluation-r144-20261020/showcase/`

- `render.py`：标准库生成器；显式 JSON 清单、文件 SHA、review ledger 绑定；全部视频和图片内嵌。
- `manifest.draft.json`：三例的真实历史 Native / 固定数据，自动结果待评估；另绑定真实历史 R138/P1。
- `preview.html`：13.71 MB，三例待评估及历史 R138 三列视频、帧 50/72。历史固定切换列为参考 / 固定 / 自动。
- `README.md`：绑定、填结果及导出命令。`test_render.py`、`VALIDATION.json`：12 项 CPU 测试、Ruff、Python AST、JavaScript 语法、4 个内嵌媒体 SHA 均通过。

完成实际成片审核后：

```sh
cd /Users/researcher/DevProjects/h3-threecase-auto-evaluation-r144-20261020/showcase
python3 render.py --manifest manifest.draft.json \
  --bind-review short_0358=../review/short_0358/FRAME_LEDGER.json \
  --bind-review long_0039=../review/long_0039/FRAME_LEDGER.json \
  --bind-review long_0059=../review/long_0059/FRAME_LEDGER.json \
  --save-manifest manifest.bound.json --check
```

将真实自动开关、事件区间、MF 及证据填入新清单 `manifest.results.json`，执行：

```sh
python3 render.py --manifest manifest.results.json --output results.html
```

当前工具的浏览器清单为空；尚待浏览器视觉与播放核验。人工填入的开关、事件和 MF 数值由评估者按原始记录核对。现有用户手工报告和生产文件保持原状；未调用 GPU、下载或安装。
