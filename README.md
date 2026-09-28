# monalisa-film

Agnes Video 2.5 Flash 生成《蒙娜丽莎失窃案》约 3 分钟动画成片。

## GitHub Actions

1. 仓库 **Settings → Secrets and variables → Actions** 新建 `AGNES_API_KEY`
2. 在分支 `arena/01a0e83e-monalisa-film` 运行 workflow **Generate Mona Lisa film (Agnes)**
3. 成功后 `clips/*.mp4` 与 `out/monalisa_theft.mp4` 会推回该分支
