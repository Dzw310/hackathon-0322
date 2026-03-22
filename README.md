# 一步一步想一想

一个面向儿童的互动式学习原型。用户提出问题后，系统会调用 OpenAI API，把问题拆成多步小问题，让孩子逐步作答：

- 答对了：继续进入下一步。
- 答错了：不给标准答案，先给更具体的提示，鼓励继续思考。
- 全部完成后：输出完整解题步骤、最终答案和学习反馈。

## 适合的场景

- 小学数学、逻辑题、应用题
- 简单科学概念启发
- 写作或阅读理解时的分步引导

## 项目结构

```text
hackathon-0322/
├── run.py
├── src/tutor_app/
│   ├── openai_client.py
│   ├── tutor_service.py
│   ├── server.py
│   ├── models.py
│   ├── schemas.py
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── styles.css
└── tests/
    └── test_tutor_service.py
```

## 核心设计

### 1. 分步拆解

后端先调用 OpenAI Responses API，让模型生成结构化学习计划：

- 问题重述
- 鼓励性开场
- 多个步骤
- 每一步的目标、提问语、判定标准、提示阶梯
- 最终参考答案

### 2. 逐步交互判题

每次孩子提交中间答案，后端都会再次调用模型，对当前步骤进行判断：

- 是否答对
- 当前反馈
- 下一条提示
- 一句简短解释

### 3. 最终总结

全部步骤完成后，再调用一次模型，生成：

- 完整答案
- 每一步回顾
- 做得好的地方
- 下次可以加强的地方

## 环境要求

- Python 3.13+
- OpenAI API Key

项目本地开发不依赖第三方 Python 包，直接使用标准库运行。

## 配置

复制环境变量示例并填写：

```bash
cp .env.example .env
```

需要至少设置：

```bash
export OPENAI_API_KEY="你的 key"
export OPENAI_MODEL="gpt-5.4"
export OPENAI_REASONING_EFFORT="medium"
```

如果你更看重成本和速度，也可以把模型改成 `gpt-5-mini`。

## 运行

```bash
python run.py
```

默认会启动在：

```text
http://127.0.0.1:8000
```

## API

### `POST /api/session`

请求：

```json
{
  "question": "12颗糖分给3个朋友，每人几颗？"
}
```

作用：创建一个新的分步学习会话，并返回第一步。

### `POST /api/session/answer`

请求：

```json
{
  "sessionId": "会话ID",
  "answer": "12颗"
}
```

作用：提交当前步骤的答案，返回继续、重试或完成状态。

## 验证

运行单元测试：

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## OpenAI 接入说明

这个项目使用 Responses API 和结构化输出，让模型稳定返回 JSON。根据 OpenAI 官方文档，Responses API 是新项目推荐接口；截至 2026-03-22，官方模型总览页建议优先从 `gpt-5.4` 开始，若更关注成本和延迟则可使用 `gpt-5-mini`。

参考：

- https://developers.openai.com/api/docs/guides/text
- https://developers.openai.com/api/docs/models
