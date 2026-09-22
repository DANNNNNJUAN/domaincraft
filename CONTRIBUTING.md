# 参与开发

简体中文 · [English](CONTRIBUTING.en.md)

开发环境需要 Python 3.9+，工具和自测使用标准库。

## 修改什么，怎样验证

从一条业务需求或一个能复现的问题开始。说明规则由谁维护，再决定对象、接口和模式。注释重点解释业务原因、契约和一致性要求。

调整检查器时，补充正常用例和能触发问题的用例。保留原断言与验收条件，跳过的测试也应如实报告。测试在临时目录运行；历史实验记录保持原样，新结果另存。

提交前运行：

```bash
python3 -B ddd-python/scripts/check.py --self-test
python3 -B ddd-python/scripts/check.py --all
python3 -B -m unittest discover -s tests -v
python3 -B tools/build_release.py --output dist
python3 -B tools/verify_release.py dist/ddd-python-skill-0.1.0.zip
```

## 文档和发布文件

中英文文档成对维护：中文使用原文件名，英文使用 `.en.md`。两版的命令、配置字段和验收结论应一致；说明文字按各自语言自然表达。MIT 许可证保留英文原文。

新增发布文件时更新 `release-files.txt`。安装后的 Skill 应能独立使用，所需脚本、参考资料和示例都放在 `ddd-python/` 内。临时目录、API Key 和本机实验文件留在发布清单之外。

PR 描述写清问题、修改后的行为，以及实际跑过的验证。如果某个环境尚未测试，直接说明即可。提交贡献表示同意按本仓库 MIT 许可证发布该贡献；第三方内容需具备相应分发权限。
