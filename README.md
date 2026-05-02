# 研发预算管理系统

研发部门内部预算编制、版本审批、一级汇总和 Dashboard 管理系统。

## 技术栈

- 后端：Django 4.2 LTS + Django REST Framework
- 前端：Vue 3 + Vite + TypeScript
- 数据库：开发默认 SQLite，生产目标 PostgreSQL

## 项目结构

```text
backend/   Django API 服务
frontend/  Vue3 前端应用
docs/      需求、架构和开发计划
```

详细需求见 `docs/预算管理系统-需求与架构梳理.md`，开发计划见 `docs/开发计划.md`。

当前剩余模块与推荐开发顺序见 `docs/剩余开发模块与执行节奏.md`，模块级测试与 GitHub 提交流程见 `docs/模块开发测试与提交流程.md`。
