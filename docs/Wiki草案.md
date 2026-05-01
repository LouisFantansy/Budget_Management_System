# Budget Management System Wiki

本文件用于同步 GitHub Wiki 的初版内容。

## Home

研发预算管理系统面向 SS 一级部门及其二级部门，用于年度预算编制、模板管理、版本审批、Dashboard 分析和版本差异追踪。

### 组织结构

- 一级部门：SS
- 二级部门：Arch、PVE、PE、STE、PHE、FTE、cSSD_FW、eSSD_FW、Embedded_FW、PDT

### 技术栈

- 后端：Django 4.2 LTS + Django REST Framework
- 前端：Vue 3 + Vite + TypeScript + Pinia
- 开发数据库：SQLite
- 生产目标数据库：PostgreSQL

## Backend Guide

### 常用命令

```bash
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py seed_demo
../.venv/bin/python manage.py test
../.venv/bin/python manage.py runserver
```

### 主要 App

- `accounts`：用户、角色、数据范围。
- `orgs`：部门组织。
- `masterdata`：Category、项目、供应商、历史采购。
- `budget_cycles`：预算周期和任务。
- `budget_templates`：模板和字段。
- `budgets`：预算表、版本、预算行、月度计划、Diff。
- `approvals`：审批请求和审批节点。
- `analytics`：Dashboard 聚合。

## Frontend Guide

### 常用命令

```bash
cd frontend
npm install
npm run dev
npm run build
```

### 本地认证

开发阶段支持 session 登录，也保留 Basic Auth：

```js
localStorage.setItem('budget_basic_auth', btoa('primary-admin:password'))
```

### 页面

- 工作台：预算状态、审批和条目预览。
- 预算编制：预算行、动态模板字段、提交送审、创建修订。
- 审批中心：通过和退回。
- 预算看板：部门、Category、月度聚合。
- 模板管理：字段查看、新增、重命名、必填切换和删除。
- 版本分析：版本链路和 Diff。

## Testing Guide

### 回归门禁

每轮开发至少执行：

```bash
cd backend
../.venv/bin/python manage.py test
../.venv/bin/python manage.py check
```

```bash
cd frontend
npm run build
```

### 当前测试基线

- 后端测试数：36
- 前端构建：通过

## Demo Data

生成演示数据：

```bash
cd backend
../.venv/bin/python manage.py seed_demo
```

默认用户：

- `primary-admin / password`
- `budget-owner / password`
- `dept-head / password`
