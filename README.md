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

## 版本

当前源码版本：`v1.0.2`

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
