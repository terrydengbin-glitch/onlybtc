# P5-C30 Evidence 滚动条暗色样式修复

## 状态

DONE

## Phase

P5 Dashboard 与可视化层

## 背景

Evidence 页面列表区域使用内部滚动容器，浏览器默认滚动条在暗色主题下显示为白色，和 Dashboard 视觉风格不一致。

## 实施内容

- 为 `.evidence-list` 增加暗色滚动条样式。
- 为 `.evidence-modal` 增加暗色滚动条样式。
- 同时覆盖 Firefox 的 `scrollbar-color/scrollbar-width` 和 WebKit 的 `::-webkit-scrollbar`。
- hover 状态使用项目青色强调色。

## DoD

- Evidence 列表右侧不再出现白色滚动条。
- 弹窗滚动条与暗色主题一致。
- 不修改业务逻辑。
- `npm run build` 通过。

## 验收记录

- `npm run build` 通过。
