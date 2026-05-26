# 更适合BUPT数电实验的Quartus MCP
还在为数电实验不会做而发愁？还在为不会设置仿真波形而困惑？还在为设置引脚而烦躁？

### 不会写VHDL代码？
### 不会在波形里面引入VHDL的变量？
### 不会设置输入波形周期和形状？
### 不会设置仿真实验？
### 不会根据开发板设置引脚？
让Quartus接入codex/claude code可以解决所有麻烦！

所以我开发了一个MCP，让codex/claudecode直接接管你的Quartus软件进行实验！

**你可以用这个MCP完成VHDL代码生成、VWF仿真波形设置、仿真输出、自动引脚设置**


Quartus MCP 是一个本地运行的 Model Context Protocol server。它可以让 Codex、Claude Code 这类 AI 编程工具调用你电脑上的 Intel/Altera Quartus 命令行工具，自动创建工程、编译工程、运行简单仿真，并读取 Quartus 生成的报告。

这个项目目前主要面向 Quartus II 9.1 和 MAX II `EPM1270T144C5` 开发实验板
（也就是数电实验课的开发板）。

## 它能做什么

- 检查 Quartus 命令行工具是否能被找到。
- 创建一个 `counter_demo` 计数器示例工程。
- 生成 Quartus 工程文件：`QPF`、`QSF`。
- 生成 VHDL 顶层文件。
- 生成 VWF 波形仿真文件。
- 调用 `quartus_sh --flow compile` 编译工程。
- 调用 `quartus_sh --flow compile_and_simulate` 尝试运行 VWF 仿真。
- 汇总 `.rpt`、`.summary`、`.log`、`.sof`、`.pof`、`.cvwf` 等结果文件。

## 前置条件

你需要先准备好：

1. Windows。
2. Python 3.10 或更高版本。
3. 已安装 Quartus II 9.1，或兼容的 Quartus 版本。
4. 能在 Quartus 安装目录中找到 `quartus_sh.exe`。
5. codex或者claudecode
   
通常 `quartus.exe` 会在类似下面的位置：

```text
C:\altera\91\quartus\bin64\quartus.exe
```

也可能是：

```text
C:\intelFPGA_lite\<version>\quartus\bin64\quartus.exe
```

你真正需要配置的是 `bin64` 这个目录，不是 `quartus.exe` 文件本身。

例如，如果你的文件是：

```text
C:\altera\91\quartus\bin64\quartus.exe
```

那么 `QUARTUS_BIN` 应该填：

```text
C:\altera\91\quartus\bin64
```

## 安装

先下载或克隆本项目，然后进入项目目录。

```powershell
git clone https://github.com/<your-name>/quartus-mcp.git
cd quartus-mcp
```

安装为本地 Python 包：

```powershell
python -m pip install -e .
```

如果你不想安装，也可以在 MCP 配置里直接运行源码入口。不过对新手来说，推荐执行上面的安装命令。

## 先测试 Quartus 路径

把下面命令里的路径改成你自己的 Quartus `bin64` 目录：

```powershell
$env:QUARTUS_BIN="C:\altera\91\quartus\bin64"
python -c "from quartus_mcp.quartus_cli import detect_quartus_installation; print(detect_quartus_installation())"
```

如果输出里看到：

```text
'ok': True
```

说明 Quartus 命令行工具已经找到了。

如果是 `False`，请重点检查：

- 路径是否写到了 `bin64` 目录。
- 目录里面是否真的有 `quartus.exe`。
- 路径是否被中文引号、全角字符或多余空格影响。

## 部署到 Codex

把下面命令里的 `C:\altera\91\quartus\bin64` 改成你自己的 Quartus `bin64` 目录：

```powershell
codex mcp add quartus `
  --env QUARTUS_BIN="C:\altera\91\quartus\bin64" `
  -- python -m quartus_mcp.server
```

然后检查是否添加成功：

```powershell
codex mcp list
codex mcp get quartus --json
```

Quartus 编译可能比较慢，建议给这个 MCP 设置较长超时。打开 Codex 的 `config.toml`，找到 `[mcp_servers.quartus]`，加上：

```toml
tool_timeout_sec = 600
```

如果你不知道配置文件在哪里，可以先运行：

```powershell
codex mcp get quartus --json
```

根据输出找到当前 MCP 配置。

### Codex：手动编辑配置文件

如果你不想用 `codex mcp add` 命令，也可以手动修改 Codex 配置文件。

Codex 的配置文件通常在：

```text
%USERPROFILE%\.codex\config.toml
```

如果文件不存在，可以新建一个。然后加入下面这段配置：

```toml
[mcp_servers.quartus]
command = "python"
args = ["-m", "quartus_mcp.server"]
env = { QUARTUS_BIN = "C:\\altera\\91\\quartus\\bin64" }
tool_timeout_sec = 600
```

把 `C:\\altera\\91\\quartus\\bin64` 改成你自己的 Quartus `bin64` 目录。注意在 TOML 里，Windows 路径建议用两个反斜杠 `\\`。

保存文件后，重启 Codex，再检查：

```powershell
codex mcp list
```

## 部署到 Claude Code

把下面命令里的 `C:\altera\91\quartus\bin64` 改成你自己的 Quartus `bin64` 目录：

```powershell
claude mcp add --transport stdio `
  --env QUARTUS_BIN="C:\altera\91\quartus\bin64" `
  quartus `
  -- python -m quartus_mcp.server
```

检查是否添加成功：

```powershell
claude mcp list
claude mcp get quartus
```

进入 Claude Code 后，也可以输入：

```text
/mcp
```

如果看到 `quartus`，说明 MCP 已经被 Claude Code 识别。

### Claude Code：手动编辑配置文件

如果你不想用 `claude mcp add` 命令，也可以在项目根目录新建 `.mcp.json` 文件。

`.mcp.json` 适合和项目一起使用。Claude Code 在这个项目里启动时，会读取这个文件。

在你的项目根目录创建：

```text
.mcp.json
```

写入下面内容：

```json
{
  "mcpServers": {
    "quartus": {
      "command": "python",
      "args": ["-m", "quartus_mcp.server"],
      "env": {
        "QUARTUS_BIN": "C:\\altera\\91\\quartus\\bin64"
      },
      "timeout": 600000
    }
  }
}
```

把 `C:\\altera\\91\\quartus\\bin64` 改成你自己的 Quartus `bin64` 目录。JSON 里 Windows 路径也要写成两个反斜杠 `\\`。

保存后，在这个项目目录里重新启动 Claude Code，然后运行：

```powershell
claude mcp list
```

进入 Claude Code 后，也可以输入：

```text
/mcp
```

如果看到 `quartus`，说明手动配置已经生效。

## 更多配置样例

`examples` 目录里也提供了可复制的配置样例：

- `examples/codex.config.example.toml`
- `examples/claude_code.mcp.example.json`
- `examples/claude_desktop_config.example.json`

复制时只需要改一处：把 `QUARTUS_BIN` 改成你自己的 Quartus `bin64` 目录。

## 可用工具

连接成功后，AI 工具会看到这些 MCP tools：

| Tool | 用途 |
| --- | --- |
| `detect_quartus_installation` | 检查 Quartus 命令行工具是否存在 |
| `create_counter_project` | 创建 `counter_demo` 示例工程 |
| `compile_project` | 编译已有 Quartus 工程 |
| `run_vwf_simulation` | 运行 VWF 仿真流程并查找 `.cvwf` |
| `summarize_quartus_reports` | 汇总 Quartus 报告、日志和编程文件 |

## 使用示例

在 Codex 或 Claude Code 里可以直接说：

```text
用 quartus MCP 检查我的 Quartus 安装是否可用。
```

或者：

```text
用 quartus MCP 创建一个带异步复位的8421十进制计数器工程并编译。
```
然后你就会得到一个带VHDL、VMF仿真波形的完整工程，而且引脚会自动配置好，
你只需要下载到开发板即可。


如果你要编译自己的工程，需要告诉 AI 工程目录，例如：

```text
用 quartus MCP 编译 D:\fpga_projects\my_counter 里的工程。
```

## 常见问题

### 1. 提示找不到 Quartus

确认 `QUARTUS_BIN` 指向的是 Quartus 的 `bin64` 目录，并且里面有 `quartus_sh.exe`。

### 2. 编译超时

Quartus 编译可能需要几分钟。把 MCP tool timeout 设置到 `600` 秒或更高。

### 3. VWF 仿真没有生成 `.cvwf`或者没找到.cvwf文件
Quartus II 9.1 不会自动检测仿真完成的.cvwf文件，需要自行打开
解决方法：在quartus左上角选择打开文件，在项目根目录下找到.cvwf文件打开即可
Quartus II 9.1 的 VWF 格式比较旧。如果自动生成的 `.vwf` 被 Quartus 拒绝，可以用 Quartus GUI 打开 `.vwf` 文件，保存一次，再重新运行仿真。

### 4. 生成的编程文件在哪里

编译成功后，MCP 会在结果里返回 `.sof`、`.pof`、`.jic`、`.jam`、`.jbc` 等文件路径。MAX II 常见输出是 `.pof`。

## 开发

本项目是一个无第三方运行时依赖的 Python 包。

```powershell
python -m pip install -e .
python -m quartus_mcp.server
```

`python -m quartus_mcp.server` 会等待 MCP stdio 输入，正常情况下不需要手动操作，它应该由 Codex 或 Claude Code 启动。

## 许可证

MIT
