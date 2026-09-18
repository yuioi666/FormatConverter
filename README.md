# FormatConverter

FormatConverter 是一个 Windows 桌面文档格式转换工具，提供 Office、PDF、图片和纯文本之间的常用转换能力。

## 功能

- Word、Excel、PowerPoint 转 PDF
- PDF 转 Word、TXT、图片
- PDF 合并与压缩
- 图片转 PDF、图片合并 PDF、图片格式转换
- TXT 转 PDF、Word 转 TXT、Excel 转 CSV
- 文件拖放、批量任务、暂停与停止

> Office 相关转换依赖本机安装的 Microsoft Office。

## 使用说明

1. 分别选择“转换前格式”和“转换后格式”，例如 Excel → PDF。
2. 将文件或文件夹拖入窗口；软件会递归扫描文件夹，只加入与当前模式兼容的文件。
3. 选择输出位置后开始转换。完成一批后，可以继续添加并执行下一批。

“画质引擎”只会在转换实现真正使用画质参数时启用，例如 Word/Excel 转 PDF、PDF 转图片、PDF 压缩和图片转 PDF；其他模式下会自动禁用。

## 下载

普通用户请前往仓库的 [Releases](https://github.com/yuioi666/FormatConverter/releases) 页面下载最新版 EXE，无需安装 Python。

## 从源码运行

要求：Windows 10/11、Python 3.10 或更高版本。

```powershell
git clone https://github.com/yuioi666/FormatConverter.git
cd FormatConverter
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

## 构建 EXE

项目使用 `FormatConverter.spec` 固定打包配置。该配置会同时设置 EXE 文件图标，并将窗口运行所需的 ICO 文件打包进去。

```powershell
python -m pip install pyinstaller
pyinstaller --clean --noconfirm FormatConverter.spec
```

构建结果位于：

```text
dist/FormatConverter.exe
```

## 测试

常规回归测试：

```powershell
python -m unittest discover -s tests -v
```

本机 Office 端到端测试：

```powershell
$env:FORMATCONVERTER_OFFICE_TESTS = "1"
python -m unittest tests.test_office_integration -v
```

## 版本

当前源码版本：`v1.0.3`

## 项目结构

```text
FormatConverter/
├─ assets/                  # 应用图标等资源
├─ core/                    # 格式转换实现
├─ gui/                     # 桌面界面
├─ utils/                   # 公共工具
├─ FormatConverter.spec     # PyInstaller 构建配置
├─ version_info.txt         # Windows 文件版本信息
├─ main.py                  # 程序入口
└─ requirements.txt         # 运行依赖
```
