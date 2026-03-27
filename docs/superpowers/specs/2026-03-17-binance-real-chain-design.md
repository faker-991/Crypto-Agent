# Binance Real Chain Design

## Goal

把当前项目中与币价、K 线、基础技术分析、router 问答相关的占位链路，替换为真实的 Binance `spot + futures` 数据链路，并同步把首页升级为对话框形态，补齐 `/assets/[symbol]`、首页 router console、`/traces` 的可视化能力。

这一轮目标不是“做一个完整交易平台”，而是让项目先达到“真实可问、真实可答、真实可追踪”的可用状态。

## Scope

本次纳入范围：

- Binance `spot + futures` 真实数据接入
- 真实行情、真实 K 线、真实基础指标
- router 中相关问题必须走真实 Binance 数据
- 首页 command console 升级为对话框
- `/assets/[symbol]` 展示真实 K 线图与指标
- `/traces` 展示步骤、Binance 接口、输入参数摘要、输出摘要

本次不做：

- 下单交易
- 用户认证
- 多会话聊天系统
- CoinGecko / DefiLlama 主链路整合
- 真正的 MCP / Binance skill runtime 执行链

## Current Problems

当前系统已经有前后端壳和基础 agent 流程，但核心问题是：

1. `MarketDataService` 失败时直接回退 placeholder K 线，导致前端看到的是假数据。
2. Router 相关回答目前能执行，但并不保证所有币相关问题都严格依赖真实 Binance 数据。
3. 首页是命令面板，不是完整对话框，缺少持续上下文的聊天体验。
4. `/traces` 虽然有执行事件，但没有把 Binance 接口调用显式暴露出来。
5. `/assets/[symbol]` 的图表页虽然有 chart 组件，但真实数据链不稳定，且 UI 信息层还不完整。

## Recommended Approach

采用“真实 Binance 数据主链 + 显式降级标记 + 前端三页联动升级”的方案。

原则：

- 真实数据必须是默认路径
- fallback 只作为失败保护，不再伪装成正常结果
- 所有降级都要在 trace 里可见
- 前端页面不再只展示最终结果，还要展示链路来源

## Architecture

### 1. Real Binance Market Data Layer

新增或重构统一的 Binance 数据访问层，明确区分：

- `spot`
- `futures`

支持最少这些能力：

- 最新价格 / 24h ticker
- 指定 symbol 的多周期 K 线
- 可供分析层消费的标准 candle 数据结构

### 2. Analysis Layer

所有基础指标都建立在真实 K 线上，不再允许从 placeholder candle 推导：

- MA
- 支撑 / 阻力
- 趋势判断
- breakout signal
- drawdown state
- volume 摘要

`KlineAgent` 和与走势相关的 router 执行统一使用这套分析结果。

### 3. Router And Answer Generation

Router 在识别出以下类型问题时，必须走真实 Binance 数据：

- 现货价格 / 行情
- 合约价格 / 行情
- K 线分析
- 趋势判断
- 技术面观察是否支持继续跟踪

第一阶段不引入完整多 agent LLM 推理编排，但会把“真实数据驱动的回答生成”补齐：

- 真实数据先取回
- 结构化分析先完成
- 再生成用户可读答案

### 4. Trace Instrumentation

扩展 trace 事件结构，让 `/traces` 能显示：

- 执行步骤
- 调用了哪个 Binance endpoint
- 输入参数摘要
- 输出摘要
- 是否发生 fallback / degraded mode

trace 的目标不是只给开发者看 JSON，而是给产品层面验证“这次到底有没有走真实数据链”。

### 5. Frontend Surfaces

#### `/assets/[symbol]`

展示：

- 真实 K 线图
- `spot / futures` 切换
- 多周期分析摘要
- 关键支撑 / 阻力
- 基础指标卡片

#### 首页对话框

把 router console 升级为聊天界面：

- 多条消息列表
- 用户问题 / assistant 回答
- 回答中包含真实 Binance 数据摘要
- 每条回答可链接到对应 trace

#### `/traces`

从“原始事件列表”升级为可视化时间线：

- 步骤顺序
- Binance 接口调用节点
- 输入参数摘要
- 输出摘要
- fallback 显式标记

## Data Flow

### Asset Page

```text
Frontend /assets/[symbol]
  ↓
Backend research/market endpoint
  ↓
Binance adapter
  ↓
real spot/futures data
  ↓
analysis service
  ↓
frontend chart + indicator cards
```

### Router Chat

```text
Frontend chat input
  ↓
/api/router/execute
  ↓
RouterService
  ↓
intent classification
  ↓
real Binance data fetch
  ↓
analysis + answer generation
  ↓
trace write
  ↓
assistant reply + trace id
```

### Trace View

```text
Binance call / analysis / answer generation
  ↓
Execution events
  ↓
Trace log json
  ↓
/traces UI timeline
```

## API Direction

第一阶段后端接口需要具备这些方向：

- 面向资产页的真实市场数据接口
- 面向 router 的真实 Binance 查询执行链
- 面向 traces 的 richer event payload

不要求一次性重写所有接口，但必须保证：

- `/assets/[symbol]` 有真实数据来源
- 首页对话调用的 router 执行能返回真实回答
- `/traces` 能读到 Binance 调用细节

## Error Handling

关键规则：

1. Binance 请求失败时允许 fallback，但必须打标。
2. 前端不能把 degraded 数据伪装成正常数据。
3. trace 中必须明确写出：
   - 请求哪个 endpoint
   - 为什么失败
   - 是否回退
4. 用户回答里要尽量透明，例如：
   - “实时数据获取失败，以下为降级分析”

## Testing Strategy

至少覆盖：

1. `spot` 与 `futures` 的 Binance 请求构建
2. 真实数据解析和标准 candle 转换
3. 基础指标计算基于真实 candle
4. router 相关 query 走 Binance 数据链
5. trace 包含 endpoint / input / output / degraded 字段
6. 前端资产页、聊天页、traces 页在新响应结构下可编译运行

## Risks

1. Binance 接口不稳定或被限流。
   - 解决：保留降级路径，但必须显式标记。

2. Router 可能把并不属于行情类的问题错误地送到 Binance 数据链。
   - 解决：先聚焦明确的价格 / K 线 / 技术面问题集合。

3. 前端一次同时改三页，容易接口反复变动。
   - 解决：先稳定后端响应结构，再统一接前端。

4. 对话框引入后，如果仍沿用旧的一次性 payload，会导致 UI 很快变得别扭。
   - 解决：首页直接切成 message list 结构，而不是在旧 console 上硬补。

## Build Order

1. 重构 Binance `spot + futures` 真实数据访问层
2. 打通真实 K 线与基础指标链
3. 改 Router 相关执行链，使相关问题必须走真实 Binance 数据
4. 扩展 trace 事件结构
5. 升级 `/assets/[symbol]`
6. 升级首页为对话框
7. 升级 `/traces`

## Decision

采用“先真实 Binance 主链，后统一升级三处前端”的方案。

这样做的结果是：

- 用户能看到真实行情和真实 K 线
- Router 的相关提问能拿到真实 Binance 数据回答
- Trace 能明确说明本次执行到底调用了哪些 Binance 接口
- 首页从命令输入框升级为真正可用的对话界面
