# 前端开发

FastAPI 直接提供 `app/web/` 下的静态资源。日常启动无需构建；修改前端源码后，在项目根目录执行：

```bash
npm ci
npm run build:ui
```

## 源码与产物

- `workbench.jsx`：React 组件与现有业务表单的连接。
- `ui/primitives.jsx`、`ui/motion.js`：基于 Radix 的组件与动效。
- `brand.svg`：原始 Logo，独立于通用图标。
- `icons.mjs`：生成本地 Lucide 图标集合，保留已有图标 ID。
- `app/web/appearance.css`、`workbench.css`：共享样式。
- `app/web/workbench.js`：随项目提供的构建产物，修改源码后需重新生成。

业务表单移动而不复制，保留字段 ID、事件与提交逻辑。失败保留输入，恢复连接不自动重放写操作。修改弹窗时需保持键盘焦点、内部滚动及减少动态效果的兼容。

标签页通过卡片的 `data-section` 与 `groupSpecs` 中的值绑定，不依赖卡片排列顺序。新增标签页时同步维护这两处，并声明适用的平台。
临时隐藏功能时，在对应卡片上添加 `hidden`，标签入口和内容会一起隐藏；聚合私信目前按此方式保留但不展示。

## 测试

```bash
python -m pytest -q
```

浏览器测试默认跳过。设置 `CREATORHUB_RUN_LOCAL_CDP=1` 后执行：

```bash
python -m pytest tests/test_web_appearance_browser.py tests/test_workbench_sections_browser.py -q
```

浏览器写操作使用隔离的示例接口，不操作真实账号。

## 功能演示素材

公开动图使用 `assets/kk/` 中的品牌版本，保留 CreatorHub 与“多平台内容工作台·开发：KK-Tiong_Pavelio”标识；README 每行两张。仅使用模拟数据，不录入账号、Cookie 和真实采集内容。

本地 UI 回归可运行 `python -m preview.capture_screenshots`，结果保存在被 Git 忽略的 `artifacts/screenshots/`。这些检查截图不发布到项目首页。

GitHub Pages 只发布使用指南；本地模拟接口与截图工具保留用于开发验证。

## 依赖许可证

组件使用 shadcn/ui 的组合方式及 Radix primitives，通用图标使用 Lucide。运行时不依赖 CDN 或远程字体。

`app/web/workbench.js.LEGAL.txt` 和 `app/web/workbench-licenses.txt` 为构建依赖的许可证文件，需与构建产物一起保留。
`licenses/react-remove-scroll-bar.txt` 补充对应 npm 包中缺失的许可证。
