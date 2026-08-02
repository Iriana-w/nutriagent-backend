# NutriAgent — 产品架构设计文档

> **产品定位**：面向程序员群体的 AI 健康饮食推荐系统
>
> **文档版本**：v1.0
>
> **日期**：2026-07-30

---

## 目录

1. [产品需求分析](#1-产品需求分析)
2. [技术选型](#2-技术选型)
3. [系统架构设计](#3-系统架构设计)
4. [项目目录设计](#4-项目目录设计)

---

## 1. 产品需求分析

### 1.1 目标用户画像

| 维度 | 描述 |
|------|------|
| **人群** | 22–40 岁程序员 / 科技从业者 |
| **工作特征** | 久坐 8–12h，高强度脑力劳动，作息不规律，996/大小周常见 |
| **饮食痛点** | 外卖依赖、三餐不规律、夜宵频繁、咖啡因过量、没时间做饭 |
| **健康焦虑** | 脱发、肥胖、颈椎病、视疲劳、胃病、脂肪肝、"过劳肥" |
| **技术偏好** | 习惯效率工具，愿意为便利付费，对 AI 接受度高 |

### 1.2 核心功能模块

#### 模块一：智能推荐引擎 ⭐

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **今日吃什么** | 基于用户画像 + 当前时间/天气/工作状态，一键推荐三餐 + 加餐 | P0 |
| **外卖智能匹配** | 输入预算，推荐附近外卖中最健康的选项（对接外卖平台） | P0 |
| **场景化推荐** | "熬夜加班餐""防脱发套餐""护眼食谱""提神醒脑餐"等场景标签 | P1 |
| **多样性轮转** | 避免连续推荐同类食物，保证营养均衡 | P1 |

#### 模块二：个人健康画像

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **基础信息采集** | 年龄、性别、身高、体重、体脂率 | P0 |
| **饮食偏好** | 口味偏好、忌口、过敏源、宗教禁忌、饮食类型（低碳/生酮/素食） | P0 |
| **健康目标** | 减脂/增肌/维持体重/控糖/护发/护眼 | P1 |
| **健康数据同步** | 对接 Apple Health / 小米手环 / 华为健康，获取活动量数据 | P2 |

#### 模块三：营养追踪与分析

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **饮食记录** | 文字描述 / 拍照识别 / 外卖订单导入，三种方式记录饮食 | P1 |
| **营养仪表盘** | 每日热量、三大宏量营养素、微量元素摄入可视化 | P1 |
| **周报生成** | AI 生成的每周饮食健康报告，指出不足和改进建议 | P2 |
| **作弊日管理** | 识别偏离计划的饮食，动态调整后续推荐 | P2 |

#### 模块四：智能规划

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **周食谱规划** | 提前一周生成饮食计划，支持一键采购清单 | P1 |
| **meal prep 指南** | 周末备餐攻略，适合没时间每天做饭的程序员 | P2 |
| **零食建议** | 健康零食推荐 + 办公室囤货清单 | P2 |

#### 模块五：社区与激励（P2 远期）

| 功能 | 描述 |
|------|------|
| **饮食打卡** | 程序员饮食打卡社区 |
| **好友 PK** | 健康饮食积分排行榜 |
| **成就系统** | "连续 7 天健康饮食""蔬菜达人"等徽章 |

### 1.3 程序员特有场景深度分析

| 场景 | 痛点 | NutriAgent 解法 |
|------|------|-----------------|
| **赶项目/加班** | 深夜外卖油腻、泡面充饥 | 推荐 24h 营业的健康外卖 + 便利店健康速食清单 |
| **会议连轴转** | 错过饭点、低血糖 | 推送"快速补给"方案：即食蛋白棒/水果/坚果配比 |
| **咖啡依赖** | 每天 3+ 杯，心悸失眠 | 咖啡因摄入追踪 + 递减计划 + 替代饮品推荐 |
| **团建/聚餐** | 被迫高油高盐 | "聚餐生存指南"：如何在外食场景做出最不坏的选择 |
| **出差** | 饮食完全失控 | 出差地快速健康选择 + 酒店附近推荐 |
| **颈椎/视疲劳** | 程序员职业病 | 推荐富含 Omega-3 / 叶黄素 / 维生素 A 的食物组合 |

### 1.4 非功能需求

| 类别 | 要求 |
|------|------|
| **性能** | 推荐接口响应 < 2s；首页加载 < 3s |
| **可用性** | 99.5% uptime；支持 PWA 离线基础功能 |
| **安全** | 健康数据加密存储；符合个保法/数据安全法 |
| **扩展性** | 支持未来接入更多外卖平台、可穿戴设备 |
| **国际化** | 初期中文市场，架构预留多语言/多地区支持 |
| **数据隐私** | 用户健康数据不出境；支持数据导出与删除 |

---

## 2. 技术选型

### 2.1 总体原则

- **AI-Native**：以 LLM 为核心驱动推荐逻辑，而非传统规则引擎
- **渐进式架构**：MVP 快速验证 → 逐步微服务化 → 高并发支撑
- **类型安全**：全栈 TypeScript 覆盖，减少运行时错误
- **成本可控**：LLM 调用做缓存/降级，控制 token 消耗

### 2.2 前端技术栈

| 技术 | 版本 | 选型理由 |
|------|------|----------|
| **Vue 3** | 3.5+ | 团队技术栈一致；Composition API 适合复杂交互逻辑 |
| **TypeScript** | 5.x | 类型安全，提升代码可维护性 |
| **Vite** | 6.x | 极速 HMR，开发体验好 |
| **Pinia** | 2.x | Vue 3 官方状态管理，轻量且类型友好 |
| **Vue Router** | 4.x | SPA 路由 |
| **TailwindCSS** | 4.x | 原子化 CSS，适合快速迭代 UI |
| **shadcn-vue** | - | 无头组件库，风格统一且可定制 |
| **ECharts** | 5.x | 营养仪表盘、周报数据可视化 |
| **VueUse** | - | 常用组合式工具函数 |
| **PWA (vite-plugin-pwa)** | - | 离线可用 + 桌面安装 |

### 2.3 后端技术栈

| 技术 | 版本 | 选型理由 |
|------|------|----------|
| **Python + FastAPI** | 3.12 / 0.115+ | AI/ML 生态最佳；异步高性能；自动生成 OpenAPI 文档 |
| **SQLAlchemy 2.0** | 2.x | 异步 ORM，成熟稳定 |
| **Alembic** | - | 数据库迁移管理 |
| **Celery** | 5.x | 异步任务队列（周报生成、数据同步） |
| **Redis** | 7.x | 缓存 + 任务队列 Broker + 会话存储 |
| **Pydantic** | 2.x | 数据校验，与 FastAPI 深度集成 |
| **FastAPI Users** | - | 开箱即用的用户认证体系 |
| **httpx** | - | 异步 HTTP 客户端（对接外部 API） |

### 2.4 AI / LLM 层

| 技术 | 选型理由 |
|------|----------|
| **LangChain** | LLM 应用编排框架；RAG 链 + Agent 调度 |
| **LangGraph** | 多步骤 AI 工作流（如：理解需求 → 查询知识库 → 生成推荐 → 校验合理性） |
| **OpenAI API / Claude API** | 主力推理模型，按场景选用 |
| **本地模型（Ollama / vLLM）** | 对延迟敏感或高频调用的场景做降级替代 |
| **ChromaDB / Qdrant** | 向量数据库，存储营养学知识做 RAG |
| **jieba / pkuseg** | 中文分词，食物名称识别 |
| **OpenFoodFacts / 中国食物成分表** | 食物营养数据库基础 |

### 2.5 数据层

| 技术 | 用途 |
|------|------|
| **PostgreSQL 16 + pgvector** | 主数据库；利用 pgvector 做轻量向量检索（减少额外组件） |
| **Redis 7** | 热点缓存 + 推荐结果缓存 + 限流 + Session |
| **MinIO / 阿里云 OSS** | 图片存储（食物拍照识别、用户头像） |
| **Elasticsearch**（远期） | 食物搜索、日志分析 |

### 2.6 DevOps / 基础设施

| 技术 | 用途 |
|------|------|
| **Docker + Docker Compose** | 本地开发环境 |
| **Kubernetes（远期）** | 生产环境编排 |
| **Nginx** | 反向代理 + 静态资源 |
| **GitHub Actions / GitLab CI** | CI/CD |
| **Prometheus + Grafana** | 监控告警 |
| **Sentry** | 错误追踪 |

---

## 3. 系统架构设计

### 3.1 架构全景图

```
┌─────────────────────────────────────────────────────────────────┐
│                        客户端层                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │   Web    │  │   PWA    │  │ 小程序   │  │  移动端(远期) │   │
│  │ (Vue 3)  │  │ (离线)    │  │ (微信)   │  │  Flutter     │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
└───────┼─────────────┼─────────────┼───────────────┼────────────┘
        │             │             │               │
        └─────────────┴──────┬──────┴───────────────┘
                             │
                    ┌────────▼────────┐
                    │   API Gateway    │  ← Nginx / Traefik
                    │  (限流/认证/日志) │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼───────┐  ┌────────▼────────┐  ┌───────▼───────┐
│  BFF 层       │  │  业务服务层     │  │  AI 服务层    │
│  (Backend     │  │  (FastAPI)      │  │  (LangChain)  │
│   For Front)  │  │                 │  │               │
│               │  │ ┌─────────────┐ │  │ ┌───────────┐ │
│  • 聚合数据   │  │ │ 用户服务     │ │  │ │ 推荐引擎  │ │
│  • 页面适配   │  │ │ 饮食记录     │ │  │ │ RAG 检索  │ │
│  • SSR 首屏   │  │ │ 推荐服务     │ │  │ │ Agent 调度 │ │
│               │  │ │ 营养分析     │ │  │ │ 意图识别  │ │
│               │  │ │ 社区服务     │ │  │ └───────────┘ │
│               │  │ │ 通知服务     │ │  │               │
│               │  │ │ 积分服务     │ │  │               │
│               │  │ └─────────────┘ │  │               │
│               │  │                 │  │               │
└───────┬───────┘  └────────┬────────┘  └───────┬───────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼───────┐  ┌───────▼───────┐  ┌───────▼───────┐
│  PostgreSQL   │  │    Redis      │  │  向量数据库   │
│  + pgvector   │  │  (缓存/队列)  │  │  (ChromaDB/  │
│               │  │               │  │   Qdrant)    │
└───────────────┘  └───────────────┘  └───────────────┘

        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼───────┐  ┌───────▼───────┐  ┌───────▼───────┐
│  对象存储     │  │  消息队列     │  │  外部服务     │
│  (MinIO/OSS)  │  │  (RabbitMQ/  │  │  • 外卖API    │
│               │  │   Redis)     │  │  • 健康API    │
│               │  │              │  │  • 支付       │
└───────────────┘  └───────────────┘  └───────────────┘
```

### 3.2 AI 推荐引擎架构（核心）

这是 NutriAgent 最核心的子系统，展开设计：

```
用户请求
    │
    ▼
┌──────────────────────────────────────────────┐
│              意图识别层                        │
│  ┌─────────────────────────────────────────┐ │
│  │ LLM 分类：推荐/记录/查询/规划/闲聊       │ │
│  │ 意图 → 路由到对应 Agent                  │ │
│  └─────────────────────────────────────────┘ │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│              上下文组装层                      │
│  ┌─────────────────────────────────────────┐ │
│  │ • 用户画像（偏好/目标/禁忌）              │ │
│  │ • 时间上下文（早餐/午餐/晚餐/夜宵）       │ │
│  │ • 环境上下文（天气/季节/位置）            │ │
│  │ • 历史上下文（最近饮食记录，避免重复）     │ │
│  │ • 健康上下文（近期营养缺口）              │ │
│  └─────────────────────────────────────────┘ │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│              RAG 检索层                       │
│  ┌─────────────────────────────────────────┐ │
│  │ 向量检索：营养学知识库 + 食物数据库       │ │
│  │ → 召回 Top-K 相关知识片段                │ │
│  │ → 过滤：去除与用户禁忌冲突的选项          │ │
│  └─────────────────────────────────────────┘ │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│              推荐生成层                        │
│  ┌─────────────────────────────────────────┐ │
│  │ Prompt = 模板 + 上下文 + RAG 知识        │ │
│  │ LLM 推理 → 结构化推荐结果                │ │
│  │ Post-process：合理性校验 + 多样性检查     │ │
│  └─────────────────────────────────────────┘ │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│              结果渲染层                        │
│  ┌─────────────────────────────────────────┐ │
│  │ • 格式化输出（食谱/外卖选项/替代方案）    │ │
│  │ • 推荐理由可解释性                       │ │
│  │ • 用户反馈收集（👍👎 用于强化学习优化）  │ │
│  └─────────────────────────────────────────┘ │
```

### 3.3 数据流

```
[用户输入] → [前端 Vue] → [API Gateway] → [BFF/Router]
                                              │
                        ┌─────────────────────┤
                        ▼                     ▼
                  [同步处理]            [异步处理]
                   • 推荐请求            • 周报生成
                   • 饮食记录            • 数据同步
                   • 用户信息            • 推送通知
                        │                     │
                        ▼                     ▼
                  [PostgreSQL]          [Celery + Redis]
                        │                     │
                        ▼                     ▼
                  [返回结果]            [结果回调/通知]
```

### 3.4 核心 API 设计（逻辑分组）

```
用户与认证
  POST   /api/v1/auth/register
  POST   /api/v1/auth/login
  GET    /api/v1/users/me
  PATCH  /api/v1/users/me/profile
  GET    /api/v1/users/me/health-profile

推荐
  POST   /api/v1/recommendations/meal          # 单餐推荐
  POST   /api/v1/recommendations/daily         # 一日推荐
  POST   /api/v1/recommendations/weekly        # 周计划
  POST   /api/v1/recommendations/scenario      # 场景推荐
  POST   /api/v1/recommendations/:id/feedback  # 推荐反馈

饮食记录
  POST   /api/v1/food-logs                     # 记录饮食
  GET    /api/v1/food-logs                     # 查询记录
  POST   /api/v1/food-logs/photo               # 拍照识别
  GET    /api/v1/food-logs/stats               # 统计汇总

外卖对接
  GET    /api/v1/delivery/search               # 搜索附近健康外卖
  GET    /api/v1/delivery/merchants/:id/menu   # 商户菜单健康分析

营养分析
  GET    /api/v1/nutrition/dashboard           # 营养仪表盘
  GET    /api/v1/nutrition/report/weekly       # 周报
  GET    /api/v1/nutrition/report/monthly      # 月报
```

---

## 4. 项目目录设计

### 4.1 仓库策略

采用 **Monorepo** 结构，便于前后端协作和共享类型定义：

```
nutriagent/
├── .github/                        # CI/CD 配置
│   └── workflows/
│       ├── ci-frontend.yml
│       └── ci-backend.yml
│
├── apps/                           # 应用层
│   ├── web/                        # Vue 3 前端
│   │   ├── src/
│   │   │   ├── assets/             # 静态资源（图片/字体/图标）
│   │   │   ├── components/         # 通用组件
│   │   │   │   ├── ui/             #   shadcn-vue 基础组件
│   │   │   │   ├── common/         #   业务无关通用组件
│   │   │   │   └── nutrition/      #   营养相关业务组件
│   │   │   │       ├── MealCard.vue
│   │   │   │       ├── NutritionChart.vue
│   │   │   │       ├── FoodLogForm.vue
│   │   │   │       └── HealthDashboard.vue
│   │   │   ├── composables/        # 组合式函数
│   │   │   │   ├── useAuth.ts
│   │   │   │   ├── useRecommendation.ts
│   │   │   │   ├── useFoodLog.ts
│   │   │   │   └── useNutrition.ts
│   │   │   ├── layouts/            # 布局组件
│   │   │   │   ├── DefaultLayout.vue
│   │   │   │   └── AuthLayout.vue
│   │   │   ├── pages/              # 页面组件
│   │   │   │   ├── Home.vue
│   │   │   │   ├── Recommend.vue
│   │   │   │   ├── FoodLog.vue
│   │   │   │   ├── Dashboard.vue
│   │   │   │   ├── Profile.vue
│   │   │   │   ├── Settings.vue
│   │   │   │   └── Auth/
│   │   │   │       ├── Login.vue
│   │   │   │       └── Register.vue
│   │   │   ├── router/             # 路由配置
│   │   │   │   └── index.ts
│   │   │   ├── stores/             # Pinia 状态管理
│   │   │   │   ├── useAuthStore.ts
│   │   │   │   ├── useUserStore.ts
│   │   │   │   ├── useRecommendStore.ts
│   │   │   │   └── useNutritionStore.ts
│   │   │   ├── api/                # API 请求层
│   │   │   │   ├── client.ts       # axios/fetch 封装
│   │   │   │   ├── auth.ts
│   │   │   │   ├── recommendations.ts
│   │   │   │   ├── foodLogs.ts
│   │   │   │   └── nutrition.ts
│   │   │   ├── types/              # 前端类型定义
│   │   │   │   ├── user.ts
│   │   │   │   ├── recommendation.ts
│   │   │   │   └── nutrition.ts
│   │   │   ├── utils/              # 工具函数
│   │   │   │   ├── format.ts
│   │   │   │   └── validation.ts
│   │   │   ├── App.vue
│   │   │   └── main.ts
│   │   ├── public/
│   │   │   ├── favicon.svg
│   │   │   └── manifest.json       # PWA manifest
│   │   ├── index.html
│   │   ├── vite.config.ts
│   │   ├── tailwind.config.ts
│   │   ├── tsconfig.json
│   │   └── package.json
│   │
│   └── mobile/                     # 移动端（远期 Flutter/React Native）
│
├── services/                       # 后端微服务
│   ├── api-gateway/                # API 网关 / BFF
│   │   ├── src/
│   │   │   ├── routes/
│   │   │   ├── middleware/
│   │   │   │   ├── auth.py
│   │   │   │   ├── rate_limit.py
│   │   │   │   └── logging.py
│   │   │   ├── dependencies/
│   │   │   └── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── user-service/               # 用户服务
│   │   ├── src/
│   │   │   ├── models/
│   │   │   │   ├── user.py
│   │   │   │   └── health_profile.py
│   │   │   ├── schemas/
│   │   │   ├── repositories/
│   │   │   ├── services/
│   │   │   ├── api/
│   │   │   │   └── v1/
│   │   │   │       └── users.py
│   │   │   └── main.py
│   │   ├── tests/
│   │   ├── alembic/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── recommendation-service/     # 推荐服务（核心）
│   │   ├── src/
│   │   │   ├── engine/
│   │   │   │   ├── orchestrator.py     # 推荐编排器
│   │   │   │   ├── intent.py           # 意图识别
│   │   │   │   ├── context.py          # 上下文组装
│   │   │   │   ├── retriever.py        # RAG 检索
│   │   │   │   ├── generator.py        # 推荐生成
│   │   │   │   └── validator.py        # 合理性校验
│   │   │   ├── agents/
│   │   │   │   ├── base.py             # Agent 基类
│   │   │   │   ├── meal_agent.py       # 单餐推荐 Agent
│   │   │   │   ├── daily_agent.py      # 一日规划 Agent
│   │   │   │   ├── scenario_agent.py   # 场景推荐 Agent
│   │   │   │   └── analyst_agent.py    # 营养分析 Agent
│   │   │   ├── rag/
│   │   │   │   ├── embeddings.py       # 向量化
│   │   │   │   ├── vector_store.py     # 向量库操作
│   │   │   │   └── knowledge/
│   │   │   │       ├── nutrition.json  # 营养学知识
│   │   │   │       └── foods.json      # 食物数据库
│   │   │   ├── prompts/
│   │   │   │   ├── templates/          # Prompt 模板
│   │   │   │   │   ├── meal.yaml
│   │   │   │   │   ├── daily.yaml
│   │   │   │   │   └── scenario.yaml
│   │   │   │   └── loader.py           # Prompt 加载与管理
│   │   │   ├── models/
│   │   │   ├── schemas/
│   │   │   ├── api/
│   │   │   │   └── v1/
│   │   │   │       └── recommendations.py
│   │   │   └── main.py
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── food-log-service/           # 饮食记录服务
│   │   ├── src/
│   │   │   ├── models/
│   │   │   ├── services/
│   │   │   │   ├── food_recognition.py  # 拍照识别
│   │   │   │   └── nutrition_calc.py    # 营养计算
│   │   │   ├── api/
│   │   │   └── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── notification-service/       # 通知服务
│   │   ├── src/
│   │   │   ├── channels/
│   │   │   │   ├── push.py
│   │   │   │   ├── email.py
│   │   │   │   └── wechat.py
│   │   │   ├── scheduler.py
│   │   │   └── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── integration-service/        # 外部集成服务
│       ├── src/
│       │   ├── adapters/
│       │   │   ├── meituan.py      # 美团外卖
│       │   │   ├── eleme.py        # 饿了么
│       │   │   └── health_kit.py   # Apple Health
│       │   └── main.py
│       ├── Dockerfile
│       └── requirements.txt
│
├── packages/                       # 共享包
│   ├── shared-types/               # 共享 TypeScript 类型
│   │   ├── src/
│   │   │   ├── user.ts
│   │   │   ├── recommendation.ts
│   │   │   └── food.ts
│   │   └── package.json
│   │
│   ├── shared-constants/           # 共享常量
│   │   └── src/
│   │       ├── enums.ts
│   │       └── config.ts
│   │
│   └── eslint-config/              # 共享 ESLint 配置
│
├── data/                           # 数据相关
│   ├── seed/                       # 种子数据
│   │   ├── foods.csv               # 食物基础数据
│   │   └── nutrition_guidelines.json
│   └── migrations/                 # 全局迁移脚本
│
├── docs/                           # 项目文档
│   ├── architecture.md
│   ├── api-spec.md
│   ├── development.md
│   └── deployment.md
│
├── docker/                         # Docker 编排
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   └── docker-compose.prod.yml
│
├── scripts/                        # 工具脚本
│   ├── setup.sh
│   ├── seed_data.py
│   └── health_check.sh
│
├── .gitignore
├── .env.example
├── Makefile                        # 常用命令快捷方式
└── README.md
```

### 4.2 Makefile 命令规划

```makefile
# 开发
make dev           # 启动全部开发环境 (docker-compose)
make dev-web       # 仅启动前端
make dev-api       # 仅启动后端

# 数据库
make db-migrate    # 运行数据库迁移
make db-seed       # 导入种子数据
make db-reset      # 重置数据库

# 测试
make test          # 运行全部测试
make test-web      # 前端测试
make test-api      # 后端测试

# 构建
make build         # 构建生产镜像
make deploy        # 部署到生产环境
```

---

## 附录 A：MVP 范围建议（V1.0）

第一期聚焦以下功能，预计 **8–12 周** 由 3–5 人团队交付：

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P0 | 用户注册/登录 | 手机号 + 微信登录 |
| P0 | 健康画像采集 | 基础信息 + 饮食偏好问卷（5 步向导） |
| P0 | AI 单餐推荐 | "今天吃什么" → LLM 生成推荐 |
| P0 | 推荐反馈 | 👍👎 按钮 |
| P1 | 饮食记录（文字） | 手动输入吃了什么 |
| P1 | 简易营养仪表盘 | 今日热量/三大营养素环形图 |
| P1 | 场景推荐 | 预设几个场景模板 |

## 附录 B：技术风险与应对

| 风险 | 等级 | 应对策略 |
|------|------|----------|
| LLM 推荐不准/幻觉 | 🔴 高 | RAG 增强 + 结构化输出 + 人工审核机制 + 用户反馈闭环 |
| LLM 调用延迟高 | 🟡 中 | 结果缓存 + 相似用户群体复用 + 预生成 + 本地小模型降级 |
| 外卖 API 不稳定 | 🟡 中 | 多平台冗余 + 兜底通用建议 |
| 用户冷启动 | 🟡 中 | 引导式问卷 + 基于人群统计的默认推荐 |
| 健康数据合规 | 🔴 高 | 数据加密 + 最小化采集 + 合规审查 + 用户数据可删除 |
| LLM 调用成本 | 🟡 中 | 缓存策略 + 模型分层（高频用小模型，深度分析用大模型）|

---

> 🤖 文档生成日期：2026-07-30
>
> 📁 本文档为 NutriAgent 项目架构设计初稿，后续迭代请在此文档基础上更新。
