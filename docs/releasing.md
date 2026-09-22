# 发布流程

简体中文 · [English](releasing.en.md)

发布分为三步：整理文件、验证安装包、上传 GitHub。本地工具负责前两步。

## 构建和检查

更新 `VERSION`、中英文 README 和 CHANGELOG，再检查 `release-files.txt`。新文档应同时列入两种语言版本，根目录和 Skill 内的 MIT 许可证应保持一致。

```bash
python3 -B -m unittest discover -s tests -v
python3 -B tools/build_release.py --output dist
python3 -B tools/verify_release.py dist/ddd-python-skill-0.1.1.zip
```

命令中的版本号应与 `VERSION` 一致。ZIP 包含仓库文件和生成的 `RELEASE-MANIFEST.json`，后者记录每个文件的 SHA-256。旁边的 `.sha256` 文件校验整个压缩包。文件顺序和时间戳固定，相同输入在同一 Python/zlib 环境下可重复构建。

验证器先检查路径、文件清单和摘要，再解包到临时目录，实际运行安装器、工具自测、订单示例和发布工具测试。它也会确认重复安装不会覆盖已有文件，最终输出 PASS/FAIL。摘要用于检查内容完整性，不提供发布者身份认证；验证过程会执行包内代码，请只运行自己构建或信任的包。

## 上传 GitHub

创建仓库后，可以上传解压目录里的文件，或推送本地仓库。先用 `git status` 确认提交范围：`benchmarks/`、`validation/` 和 `dist/` 应被忽略。标签与版本对应，例如 `v0.1.1`。

等待 CI 通过后创建 Release，附上 ZIP 和 `.sha256`。工作流按 [GitHub 的 Python 矩阵方式](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)配置，Actions 固定到具体提交。通过状态以实际远程运行记录为准。

## 保留实验记录

大型 benchmark 的本机配置、源码和原始日志继续放在开发工作区。要单独发布可复现实验，需要补齐下载、环境构建和许可证处理流程，并在新环境重新固定基线。
