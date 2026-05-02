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

- 工作台：预算状态、审批、条目预览，以及从任务直接进入对应 Draft 明细。
- 工作台：已接入真实预算周期任务数据，支持一键分发预算任务。
- 预算编制：预算行、动态模板字段、提交送审、创建修订、粘贴导入、CSV 导出和批量操作。
- 一级总表明细：支持查看来源部门、来源版本、月度计划和动态字段详情。
- 审批中心：通过和退回，并区分二级审批、一级初审、一级终审阶段。
- 预算看板：部门、Category、项目、项目类别、产品线、费用类型和月度聚合，支持部门聚焦、OPEX/CAPEX 过滤、保存视图、默认看板配置和条目下钻。
- 主数据：支持 Project Category、Product Line、Project 关系维护。
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

- `manage.py test`：110 通过
- `manage.py test budget_cycles budgets`：53 通过
- `manage.py test approvals budgets budget_cycles notifications`：60 通过
- `manage.py test budget_cycles`：12 通过
- `manage.py test budget_cycles budgets approvals notifications`：65 通过
- `manage.py test analytics budgets masterdata`：73 通过
- `manage.py test masterdata`：6 通过
- `manage.py test analytics`：19 通过
- `manage.py test budgets`：48 通过
- 后端 check：通过
- 前端构建：通过

### 模块交付节奏

- 当前剩余模块顺序以 `docs/剩余开发模块与执行节奏.md` 为准。
- 每个模块完成后先执行模块级验证，再更新文档，再推送 GitHub。
- GitHub Actions 会自动执行后端 check、后端测试和前端构建。

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
- `primary-reviewer / password`
- `ss-head / password`
