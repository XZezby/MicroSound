# MicroSound

MicroSound 是一个轻量 soundpad：按下对应键盘按键，播放绑定的 mp4 文件。

## 运行

```bash
cd MicroSound
python3 microsound.py
```

依赖 `PySide6`。当前工作区的 Python 环境已经可以导入 `PySide6`。

## 使用

- 默认按键：`1` 到 `0`，以及 `Q`、`W`。
- 点击 pad 上的“绑定”可以选择一个 mp4 文件。
- 绑定关系会写入 `config/pads.json`。
- 按 `Esc` 或点击“停止”可以停止播放。
- 点击“重播”会重新播放当前 pad。

## 素材放置

建议把 mp4 放到 `MicroSound/media/` 下，然后通过界面绑定；也可以直接编辑 `config/pads.json`：

```json
{
  "key": "1",
  "label": "Intro",
  "file": "media/intro.mp4"
}
```
