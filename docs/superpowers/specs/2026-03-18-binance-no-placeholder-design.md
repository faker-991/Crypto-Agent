# Binance No-Placeholder Design

## Goal

把当前市场数据链里的 synthetic placeholder K 线彻底移出主流程，改成严格真实数据模式：

- `spot` 和 `futures` 都只接受真实 Binance 数据
- 请求失败时不再合成 candle
- 前端显示无数据或错误态，而不是假图
- trace 明确记录失败 endpoint 和原因
- router 回答明确说明“没有拿到实时市场数据”

这一步只解决“数据真实性”问题，不同时引入 MCP、Binance skill runtime 编排或完整 LLM 回答链。

## Scope

纳入范围：

- `MarketDataService` 不再返回 placeholder K 线
- `BinanceMarketAdapter` 的 placeholder helper 退出业务主链
- `/api/research/kline` 在真实请求失败时返回空 candles 和错误元数据
- `/assets/[symbol]` 对空 candles 显示明确错误态
- router 的币价 / K 线问题在无真实数据时返回透明失败说明
- `/traces` 显示失败 endpoint、输入摘要、错误原因

不纳入范围：

- 新缓存层
- MCP 工具接入
- Binance skills runtime 接入
- 多会话聊天持久化
- 完整 LLM answer generation

## Problem

当前问题不是页面没有图，而是页面可能在 Binance 请求失败时画出合成 K 线。这样会造成两个后果：

1. 用户误以为图表是真实行情。
2. 后续 LLM、MCP、skills 接进来之前，产品已经失去可信度。

对于交易和研究类应用，宁可显式失败，也不能默默造数。

## Recommended Approach

采用严格真实数据策略：

1. 真实 Binance 响应是唯一可接受的数据源。
2. 失败时返回结构化错误，不再返回 synthetic candles。
3. 前端所有图表页都必须识别“无真实数据”的状态。
4. trace 和回答层都必须透明说明失败。

这是最硬的一种策略，但它符合你当前的目标：先把“能信”做出来，再谈“体验平滑”。

## Architecture

### 1. Market Data Layer

`MarketDataService.get_klines()` 的行为改成：

- 成功：
  - 返回真实 candles
  - `source="binance"`
  - `endpoint_summary` 必填
  - `ticker_summary` 可选，若 ticker 请求成功则填充，失败则为 `null`
  - `degraded_reason=null`
- 失败：
  - 返回空 `candles`
  - `source="unavailable"`
  - `endpoint_summary`:
    - 请求已经构造成功并且目标 endpoint 已知时必填
    - 前置校验失败时可为 `null`
  - `ticker_summary=null`
  - `degraded_reason` 必填，写失败原因
  - 不生成 synthetic candle

如果 symbol 不存在、market type 不支持、Binance 直接报错，这些都应该原样进入 `degraded_reason` 或明确异常分支。

最小失败态 contract 统一定义为：

- `candles=[]`
- `source="unavailable"`
- `endpoint_summary={ integration, endpoint, market_type, url, method } | null`
- `ticker_summary=null`
- `degraded_reason=<non-empty string>`

跨层统一判定规则：

- 只要 `degraded_reason != null`，该 timeframe / execution 就视为 `degraded`
- `source="binance"` 等价于 `degraded_reason=null`
- `source="unavailable"` 等价于 `degraded_reason!=null`
- `endpoint_summary=null` 只允许出现在前置校验失败的场景，例如不支持的 `market_type`

### 2. Research API

`/api/research/kline` 保持响应结构稳定，但语义变化：

- `market_data[timeframe]` 是失败态和数据来源的 canonical source of truth
- `analyses[timeframe].candles` 直接镜像真实 candles，因此失败时为空
- `market_data[timeframe].degraded_reason` 是前端、router、trace 解释失败原因的统一字段

分析层要接受空 candle 输入，但不能再输出伪造结论。结论文案应该降级成：

- `Real-time Binance data unavailable for this timeframe.`

### 3. Router Execution

当 router 命中币价 / K 线 / futures 问题时：

- 若拿到真实数据：
  - 正常生成 market summary 和 answer
- 若没有拿到真实数据：
  - answer 必须明确失败，例如：
    - `Binance real-time market data was unavailable for BTC spot 1d.`
  - execution 中保留 provenance 和 degraded reason

这保证首页 chat 不会把失败包装成正常结论。

### 4. Frontend

#### `/assets/[symbol]`

- candles 为空时不画图
- 显示明确状态：
  - `Live Binance data unavailable`
  - `endpoint`
  - `reason`
- ticker snapshot 若为空，也显示 unavailable

#### 首页 chat

- 当 execution 是 degraded 且没有真实 candles 时：
  - assistant 回复显示失败说明
  - 仍保留 trace link

#### `/traces`

- degraded 节点继续高亮
- 如果 output 没有真实数据，显示：
  - `source=unavailable`
  - `error`
  - 对应 endpoint

## Error Handling

严格规则：

1. 禁止 synthetic candle fallback。
2. 允许结构化降级响应，但降级响应不能包含伪市场数据。
3. 前端不得把空 candles 渲染成图表。
4. 回答层不得基于空 candles 生成像真实分析一样的结论。
5. degraded 的唯一判定规则是 `degraded_reason != null`，不得由各层自行发明。

## Testing

至少覆盖：

1. `MarketDataService` 请求失败时返回空 candles，而不是 placeholder
2. `KlineAnalysisService` 对空 candles 不崩溃，并返回 degraded-safe summary
3. `/api/research/kline` 保持 schema 稳定
4. router 在 degraded 时返回透明失败 answer
5. 资产页在空 candles 时渲染无数据态
6. traces 继续显示 endpoint 和 error

## Decision

采用严格真实数据模式，不再允许假 K 线进入任何用户可见页面。
