---
name: weather
description: 获取当前天气和天气预报，无需 API 密钥。
homepage: https://wttr.in/:help
---

# 天气

查询天气时，先使用 `web_fetch`，不要使用 `exec` 运行联网命令。Shell 位于无网络沙箱中，不能可靠地获取天气数据。

## wttr.in

首选 `wttr.in`。将地点进行 URL 编码后，调用：

```text
https://wttr.in/<地点>?format=3
```

例如伦敦：

```text
https://wttr.in/London?format=3
```

如需温度、湿度和风速，使用：

```text
https://wttr.in/<地点>?format=%l:+%c+%t+%h+%w
```

如需完整预报，使用：

```text
https://wttr.in/<地点>?T
```

地点中的空格必须 URL 编码，例如 `New%20York`。`%c` 是天气状况，`%t` 是温度，`%h` 是湿度，`%w` 是风速，`%l` 是地点。

## Open-Meteo

当 wttr.in 不可用时，可使用 Open-Meteo 作为 JSON 备用服务：

```text
https://api.open-meteo.com/v1/forecast?latitude=<纬度>&longitude=<经度>&current_weather=true
```

先用公开搜索结果或用户提供的信息确定城市坐标，再查询预报。返回 JSON 中包含温度、风速和天气代码。
