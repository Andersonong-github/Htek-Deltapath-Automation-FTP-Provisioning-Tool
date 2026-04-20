# Htek/Deltapath IP Phone Auto-Provisioning Tool

🚀 **专业版Htek/Deltapath通讯设备自动化部署工具 (Ultimate Edition)**
🚀 **Professional Auto-Provisioning Tool for Htek/Deltapath UC Devices (Ultimate Edition)**

---

## 📝 项目简介 (Introduction)

**中文**: 本工具由 Anderson Ong 开发，专为 Deltapath UC 和 Htek VOIP 工程师设计。它利用 Playwright 自动化技术，简化了 IP 电话的批量配置流程，实现自动登录、参数填充及远程重启。
**English**: Developed by Anderson Ong, this tool is designed for Deltapath UC and Htek VOIP engineers. It leverages Playwright automation to simplify mass configuration, enabling auto-login, parameter injection, and remote rebooting.

---

## ✨ 核心功能 (Key Features)

* **批量部署 (Batch Deployment)**: 
  * 支持多个 IP 地址排队处理，无需人工逐一操作。
  * Supports multiple IP addresses in a queue, eliminating manual one-by-one configuration.
* **Ping 预检 (Ping Pre-check)**: 
  * 自动跳过离线设备，节省脚本运行时间。
  * Automatically skips offline devices to save script execution time.
* **自动化填充 (Auto-Injection)**: 
  * 自动处理 HTTP 认证并下发 Provisioning Server 参数。
  * Handles HTTP authentication and pushes Provisioning Server parameters automatically.
* **全局快捷键 (Global Hotkeys)**: 
  * 内置 `Alt+1` 和 `Alt+2` 辅助在手动模式下快速填写凭据。
  * Built-in `Alt+1` and `Alt+2` to quickly fill credentials in manual mode.
* **结果导出 (Result Export)**: 
  * 一键将部署结果导出为 CSV 报告。
  * Export deployment results to a CSV report with one click.

---

## 📸 图形化操作指南 (Visual Guide)

### 第一步：处理安全拦截 (Step 1: Bypass Security Warning)
**中文**: 由于软件未签署证书，Windows 会弹出 SmartScreen 拦截。请点击 **"More info"** 然后选择 **"Run anyway"**。
**English**: As the software is not digitally signed, Windows SmartScreen will block it. Click **"More info"** and then select **"Run anyway"**.

<img width="512" height="478" alt="image" src="https://github.com/user-attachments/assets/656b457e-8205-4c9b-8352-42a78101b682" />

### 第二步：参数配置 (Step 2: Configuration)
**中文**: 在左侧面板填入设备 IP 列表、服务器地址以及 HTTP 账号密码，点击 **"START Task"**。
**English**: Enter the Device IP list, Server address, and HTTP credentials on the left panel, then click **"START Task"**.

<img width="1152" height="882" alt="image" src="https://github.com/user-attachments/assets/1239bc5e-c350-4d5c-9803-d157d12a321c" />

### 第三步：结果监控 (Step 3: Live Monitoring)
**中文**: 右侧表格会实时显示进度。双击某一行可在浏览器中直接打开该电话页面。
**English**: The right-side table shows live progress. Double-click any row to open the phone's web UI directly in your browser.

<img width="1279" height="882" alt="image" src="https://github.com/user-attachments/assets/6659c4a9-2163-4060-a42f-85f49ae78b6d" />

---

## 🛠️ 环境准备 (Setup for Developers)

### 1. 克隆与安装 (Clone & Install)
```bash
git clone [https://github.com/YourUsername/YourRepo.git](https://github.com/YourUsername/YourRepo.git)
pip install -r requirements.txt

### 2. 安装内核 (Install Browser Core)
```bash
playwright install chromium

### 3.📦 打包建议 (Packaging Tips)
中文: 建议使用 PyInstaller 将程序打包为文件夹模式，并包含 resources 文件夹。
English: It is recommended to use PyInstaller to package the app in "Directory" mode, ensuring the resources folder is included.
```bash
pyinstaller --noconfirm --onedir --windowed --icon "resources/app.ico" --add-data "resources;resources" main.py

👤 关于作者 (About Author)
Anderson Ong - UC & Voice Specialist | Maxis Broadband Sdn Bhd

