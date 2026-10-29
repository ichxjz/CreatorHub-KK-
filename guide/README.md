# CreatorHub 使用指南维护

公开指南位于 `guide/`，开发署名为 KK-Tiong_Pavelio。平台能力表统一维护在根目录 README；指南保留各平台操作步骤与当前功能限制。

- `index.html`：安装、登录、采集、洞察与导出、发布和故障处理。
- `guide.css`：桌面与手机布局。
- `platforms.json`：四个平台的登录与操作步骤；构建生成各自的指南页。
- 演示素材复用 `assets/kk/` 品牌 GIF，保留 CreatorHub 与“多平台内容工作台·开发：KK-Tiong_Pavelio”两行标识。

## 构建与发布

```sh
python preview/build_preview.py _site
python -m http.server 8081 --bind 127.0.0.1 --directory _site
```

站点首页直接进入 `/guide/`。GitHub Pages 工作流 `.github/workflows/pages-preview.yml` 只发布指南，不再部署交互演示。

公开地址：https://ichxjz.github.io/CreatorHub-KK-/guide/

## 更新检查

维护稳定的章节锚点；更新图片时同步 `preview/build_preview.py` 的 `GUIDE_IMAGES`。运行 `python -m unittest discover -s tests -p test_guide_site.py` 检查链接、图片、发布清单与平台页。公开站点不得包含账号、配置、数据库、日志或浏览器 Profile。
