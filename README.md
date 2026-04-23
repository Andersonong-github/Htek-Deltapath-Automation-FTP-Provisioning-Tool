Htek/Deltapath IP Phone Auto-Provisioning Tool

项目简介 (Introduction)

本工具由 Anderson Ong 开发，专为 Deltapath UC 和 Htek VOIP 工程师设计。它利用 Playwright 自动化技术，简化了 IP 电话的批量配置流程，实现自动登录、参数填充及远程重启。
Developed by Anderson Ong, this tool is designed for Deltapath UC and Htek VOIP engineers. It leverages Playwright automation to simplify mass configuration, enabling auto-login, parameter injection, and remote rebooting.



✨ 核心功能 (Key Features)

批量部署 (Batch Deployment): 
  * 支持多个 IP 地址排队处理，无需人工逐一操作。
  * Supports multiple IP addresses in a queue, eliminating manual one-by-one configuration.
Ping 预检 (Ping Pre-check): 
  * 自动跳过离线设备，节省脚本运行时间。
  * Automatically skips offline devices to save script execution time.
自动化填充 (Auto-Injection): 
  * 自动处理 HTTP 认证并下发 Provisioning Server 参数。
  * Handles HTTP authentication and pushes Provisioning Server parameters automatically.
全局快捷键 (Global Hotkeys): 
  * 内置 `Alt+1` 和 `Alt+2` 辅助在手动模式下快速填写凭据。
  * Built-in `Alt+1` and `Alt+2` to quickly fill credentials in manual mode.
结果导出 (Result Export): 
  * 一键将部署结果导出为 CSV 报告。
  * Export deployment results to a CSV report with one click.

---

📸 图形化操作指南 (Visual Guide)

第一步：处理安全拦截 (Step 1: Bypass Security Warning)
由于软件未签署证书，Windows 会弹出 SmartScreen 拦截。请点击 **"More info"** 然后选择 **"Run anyway"**。
As the software is not digitally signed, Windows SmartScreen will block it. Click **"More info"** and then select **"Run anyway"**.

<img width="512" height="478" alt="image" src="https://github.com/user-attachments/assets/656b457e-8205-4c9b-8352-42a78101b682" />

第二步：参数配置 (Step 2: Configuration)
在左侧面板填入设备 IP 列表、服务器地址以及 HTTP 账号密码，点击 **"START Task"**。
Enter the Device IP list, Server address, and HTTP credentials on the left panel, then click **"START Task"**.

<img width="1152" height="882" alt="image" src="https://github.com/user-attachments/assets/1239bc5e-c350-4d5c-9803-d157d12a321c" />

第三步：结果监控 (Step 3: Live Monitoring)
右侧表格会实时显示进度。双击某一行可在浏览器中直接打开该电话页面。
The right-side table shows live progress. Double-click any row to open the phone's web UI directly in your browser.

<img width="1279" height="882" alt="image" src="https://github.com/user-attachments/assets/6659c4a9-2163-4060-a42f-85f49ae78b6d" />

---

🛠️ 环境准备 (Setup for Developers)

1. 生成免安装exe (Generate Exe no Install version. Double click & Run)
如果你想在本地生成自己的 .exe 文件，请确保已安装 Python 3.10+。

在项目文件夹中按住 Shift 并右键点击空白处，选择 “在此处打开 PowerShell 窗口”。

复制并粘贴下方整段脚本并回车：

To generate your own .exe file locally, ensure Python 3.10+ is installed.

Hold Shift and Right-click in the project folder, then select "Open PowerShell window here".

Copy and paste the entire script below and press Enter:

Powershell：
# 1. 创建虚拟环境 (Create Virtual Environment)
python -m venv venv_pack;

# 2. 启动虚拟环境并安装核心依赖 (Activate & Install Dependencies)
.\venv_pack\Scripts\activate;
pip install playwright pyautogui pynput pyinstaller;

# 3. 执行打包命令 - 极致瘦身版 (Execute One-File Packaging)
pyinstaller --noconsole --onefile --add-data "resources;resources" --icon="resources/app.ico" --name "AnderOng_Htek_Provision_Tool" main.py


👤 关于作者 (About Author)
Anderson Ong - UC & Voice Specialist | Maxis Broadband Sdn Bhd

