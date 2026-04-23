# -*- coding: utf-8 -*-
import csv
import time
import os
import sys
import subprocess
import threading
import webbrowser
import re  # 增加正则表达式用于解析MAC
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from playwright.sync_api import sync_playwright
import pyautogui
from pynput import keyboard

# --- 资源路径处理 ---
def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

APP_ICON = get_resource_path(os.path.join("resources", "app.ico"))

# --- 自动寻找系统安装的 Chrome 或 Edge ---
def find_browser_path():
    paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\Application\msedge.exe")
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

SYSTEM_BROWSER = find_browser_path()

def check_ping(ip):
    try:
        # ping一下激活ARP缓存
        output = subprocess.run(['ping', '-n', '1', '-w', '800', ip.strip()], capture_output=True, text=True)
        return output.returncode == 0
    except:
        return False

# --- 新增功能：通过 ARP 获取 MAC 地址并校验 ---
def get_mac_address(ip):
    try:
        # 使用你提供的逻辑：ping 之后接 arp -a
        cmd = f"ping -n 1 -w 500 {ip} >nul && arp -a {ip}"
        output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT)
        
        # 使用正则提取 MAC 地址 (格式类似 00-1f-c1-22-ac-e9 或 00:1f:c1...)
        mac_pattern = r"([0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2})"
        match = re.search(mac_pattern, output)
        if match:
            # 统一转换成小写并去掉连字符，方便比对
            return match.group(1).replace("-", "").replace(":", "").lower()
    except:
        pass
    return None

# --- 解析 IP 段 10.10.7.1-254 ---
def parse_ip_range(ip_range):
    try:
        if '-' not in ip_range:
            return []
        base, end_part = ip_range.rsplit('-', 1)
        if '.' not in base:
            return []
        prefix = base.rsplit('.', 1)[0]
        start_num = int(base.rsplit('.', 1)[1])
        end_num = int(end_part)
        ips = []
        for num in range(start_num, end_num + 1):
            ips.append(f"{prefix}.{num}")
        return ips
    except:
        return []

class UCApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AnderOng Htek/Deltapath FTP AutoProvision Tool")
        self.root.geometry("1150x850") 
        
        try:
            if os.path.exists(APP_ICON): 
                self.root.iconbitmap(APP_ICON)
        except:
            pass

        self.is_running = False
        self.stop_requested = False
        self.provisioned_ips = set()
        self.hotkey_running = False
        self.listener = None
        self.results_data = {} 
        self.checked_items = set()
        # 新增：用于锁定 IP 与 MAC 的绑定关系
        self.locked_targets = {} 

        self.setup_ui()
        
        if not SYSTEM_BROWSER:
            messagebox.showwarning("Browser Warning", "Neither Chrome nor Edge was found.\nPlease install a Chromium-based browser.")

    def create_pw_entry_with_eye(self, parent, default_val, row=None, is_grid=True):
        container = tk.Frame(parent)
        ent = ttk.Entry(container, show="*")
        ent.insert(0, default_val)
        ent.pack(side="left", fill="x", expand=True)

        def toggle():
            if ent.cget('show') == '*':
                ent.config(show='')
                btn.config(text="👁️")
            else:
                ent.config(show='*')
                btn.config(text="🔒")

        btn = tk.Button(container, text="🔒", width=2, font=("Arial", 8), command=toggle, relief=tk.FLAT, bd=0)
        btn.pack(side="left")

        if is_grid:
            container.grid(row=row, column=1, sticky="ew", padx=5, pady=2)
        else:
            container.pack(side="left", padx=2)
        return ent

    def setup_ui(self):
        main_container = tk.Frame(self.root)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        left_panel = tk.Frame(main_container, width=420)
        left_panel.pack(side="left", fill="y", padx=(0, 10))

        # ========== Task Mode Selection (New Feature) ==========
        frame_mode = ttk.LabelFrame(left_panel, text="Execution Mode Selection")
        frame_mode.pack(fill="x", pady=5)
        self.task_mode = tk.StringVar(value="provision")
        tk.Radiobutton(frame_mode, text="Htek Full Provision (HTTP Auth + Auto Config)", variable=self.task_mode, value="provision").pack(anchor="w", padx=10)
        tk.Radiobutton(frame_mode, text="Scan IP, Mac Address & Htek Phone Status", variable=self.task_mode, value="scan_full").pack(anchor="w", padx=10)
        tk.Radiobutton(frame_mode, text="Scan IP & MAC Address Only (Rapid Scan)", variable=self.task_mode, value="scan").pack(anchor="w", padx=10)
        
        # ========== List IP 区域 ==========
        frame_ip = ttk.LabelFrame(left_panel, text="Please Provide Provision IP (Different Segments)")
        frame_ip.pack(fill="x", pady=5)
        self.ip_input = tk.Text(frame_ip, height=6, font=("Consolas", 10))
        self.ip_input.pack(padx=5, pady=5, fill="x")
        self.ip_input.insert("1.0", "10.10.7.81\n10.10.7.82\n10.10.7.83")

        def clear_list_ip():
            self.ip_input.config(state=tk.NORMAL)
            self.ip_input.delete("1.0", tk.END)

        btn_clear_list = tk.Button(frame_ip, text="Clear List IP", command=clear_list_ip, bg="#5a5a5a", fg="white", activebackground="#2a2a2a", activeforeground="white", relief=tk.RAISED, bd=2)
        btn_clear_list.pack(padx=5, pady=2, fill="x")

        # ========== Range IP 区域 ==========
        frame_range = ttk.LabelFrame(left_panel, text="IP Range (Example: 10.10.7.1-254)")
        frame_range.pack(fill="x", pady=5)
        self.ip_range_entry = ttk.Entry(frame_range, font=("Consolas", 10))
        self.ip_range_entry.pack(padx=5, pady=5, fill="x")

        def clear_range_ip():
            self.ip_range_entry.config(state=tk.NORMAL)
            self.ip_range_entry.delete(0, tk.END)

        btn_clear_range = tk.Button(frame_range, text="Clear Range IP", command=clear_range_ip, bg="#5a5a5a", fg="white", activebackground="#2a2a2a", activeforeground="white", relief=tk.RAISED, bd=2)
        btn_clear_range.pack(padx=5, pady=2, fill="x")

        # ========== 互斥逻辑 ==========
        def on_ip_type(event):
            self.ip_input.config(state=tk.NORMAL)
            self.ip_range_entry.config(state=tk.NORMAL)
            range_txt = self.ip_range_entry.get().strip()
            list_txt = self.ip_input.get("1.0", "end").strip()
            if range_txt: self.ip_input.config(state=tk.DISABLED)
            if list_txt: self.ip_range_entry.config(state=tk.DISABLED)

        self.ip_input.bind("<KeyRelease>", on_ip_type)
        self.ip_range_entry.bind("<KeyRelease>", on_ip_type)

        # ========== 服务器配置 + MAC 厂商前缀配置 ==========
        frame_srv = ttk.LabelFrame(left_panel, text="Configuration info")
        frame_srv.pack(fill="x", pady=5)
        self.ent_srv = self.create_label_entry(frame_srv, "Config Server:", "Please Provide URL", 0)
        self.ent_user = self.create_label_entry(frame_srv, "HTTP User:", "spipXXXX", 1)
        ttk.Label(frame_srv, text="HTTP Pass:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.ent_pass = self.create_pw_entry_with_eye(frame_srv, "XXXXXXXX", row=2, is_grid=True)
        
        # 新增：MAC 前缀过滤输入框
        self.ent_mac_prefix = self.create_label_entry(frame_srv, "MAC Vendor Prefix:", "001fc1", 3)
        
        frame_srv.columnconfigure(1, weight=1)

        # ========== 启动停止按钮 ==========
        btn_f = tk.Frame(left_panel)
        btn_f.pack(pady=10, fill="x")
        self.btn_start = tk.Button(btn_f, text="▶ START Task", bg="#007bff", fg="white", font=("Arial", 10, "bold"), height=2, command=self.start_task)
        self.btn_start.pack(side="left", expand=True, fill="x", padx=2)
        self.btn_stop = tk.Button(btn_f, text="■ STOP", bg="#6c757d", fg="white", font=("Arial", 10, "bold"), height=2, state="disabled", command=self.stop_task)
        self.btn_stop.pack(side="left", expand=True, fill="x", padx=2)

        # ========== 日志 ==========
        self.log_text = tk.Text(left_panel, height=15, bg="#1e1e1e", fg="#ffffff", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

        # ========== 快捷键 ==========
        frame_hk = ttk.LabelFrame(left_panel, text="HTTP Authentication Hotkeys Function")
        frame_hk.pack(fill="x", pady=5)
        row1 = tk.Frame(frame_hk); row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="Hotkeys:Alt+1 = Username & Password:").pack(side="left", padx=5)
        self.hk1_u = ttk.Entry(row1, width=8); self.hk1_u.insert(0, "admin"); self.hk1_u.pack(side="left", padx=2)
        self.hk1_p = self.create_pw_entry_with_eye(row1, "xxxxxx", is_grid=False)
        row2 = tk.Frame(frame_hk); row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="Hotkeys:Alt+2 = Username & Password:").pack(side="left", padx=5)
        self.hk2_u = ttk.Entry(row2, width=8); self.hk2_u.insert(0, "admin"); self.hk2_u.pack(side="left", padx=2)
        self.hk2_p = self.create_pw_entry_with_eye(row2, "xxxxxx", is_grid=False)
        self.btn_hk_toggle = tk.Button(left_panel, text="Shortcut: DISABLED", bg="#6c757d", fg="white", font=("Arial", 10, "bold"), command=self.toggle_hotkeys)
        self.btn_hk_toggle.pack(fill="x", pady=5)

        # ========== 右侧结果表格 ==========
        right_panel = ttk.LabelFrame(main_container, text="Provision Result & Live Monitoring (Double-Click Open Web & Right-Click More Option")
        right_panel.pack(side="right", fill="both", expand=True)
        columns = ("check", "ip", "mac", "status", "detail")
        self.tree = ttk.Treeview(right_panel, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("check", text="[X]"); self.tree.heading("ip", text="IP Address"); self.tree.heading("mac", text="MAC Address"); self.tree.heading("status", text="Status"); self.tree.heading("detail", text="Information/Result")
        self.tree.column("check", width=40, anchor="center"); self.tree.column("ip", width=120, anchor="center"); self.tree.column("mac", width=130, anchor="center"); self.tree.column("status", width=90, anchor="center"); self.tree.column("detail", width=350)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click); self.tree.bind("<Double-1>", self.on_tree_double_click); self.tree.bind("<Button-3>", self.show_context_menu)
        
        # --- 增强版右键菜单 ---
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="📋 Copy IP Address", command=self.copy_ip)
        self.context_menu.add_command(label="📋 Copy MAC Address", command=self.copy_mac)
        self.context_menu.add_command(label="📄 Copy Full Row", command=self.copy_row)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🔗 Copy Selected IPs (Checked)", command=self.copy_checked_ips)
        self.context_menu.add_command(label="🔗 Copy Selected MACs (Checked)", command=self.copy_checked_macs)
        self.context_menu.add_separator()
        # 新增：单独重新扫描
        self.context_menu.add_command(label="🔄 Rescan Selected IP", command=self.rescan_selected_row, foreground="blue")
        self.context_menu.add_command(label="🔄 Rescan Checked IPs", command=self.rescan_checked_ips, foreground="blue")
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🗑️ Delete Selected (Checked)", command=self.delete_checked, foreground="orange")
        self.context_menu.add_command(label="❌ Delete Current Record", command=self.delete_selected, foreground="red")
        
        vsb = ttk.Scrollbar(right_panel, orient="vertical", command=self.tree.yview); self.tree.configure(yscrollcommand=vsb.set); self.tree.pack(side="top", fill="both", expand=True, padx=5, pady=5); vsb.pack(side="right", fill="y")
        export_frame = tk.Frame(right_panel); export_frame.pack(fill="x", padx=5, pady=5); self.btn_export = tk.Button(export_frame, text="📥 Export Results to CSV", bg="#28a745", fg="white", command=self.export_csv); self.btn_export.pack(side="left", expand=True, fill="x", padx=(0, 2)); self.btn_clear = tk.Button(export_frame, text="🗑️ Clear All Results", bg="#6c757d", fg="white", command=self.clear_all_results); self.btn_clear.pack(side="left", expand=True, fill="x", padx=(2, 0))
        footer_frame = tk.Frame(self.root); footer_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 2))
        browser_name = "None"
        if SYSTEM_BROWSER: browser_name = "Edge" if "msedge" in SYSTEM_BROWSER.lower() else "Chrome"
        author_label = tk.Label(footer_frame, text=f"Author: Anderson OngCS | Email: anderson_ong84@hotmail.com | Browser: {browser_name}", font=("Arial", 7), fg="#a0a0a0")
        author_label.pack(side="right"); self.setup_tags()

    def create_label_entry(self, parent, label, default, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ent = ttk.Entry(parent); ent.insert(0, default)
        ent.grid(row=row, column=1, sticky="ew", padx=5, pady=2)
        return ent

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            if column == "#1":
                item = self.tree.identify_row(event.y)
                values = list(self.tree.item(item, 'values'))
                ip = values[1]
                if values[0] == "☐":
                    values[0] = "☑"
                    self.checked_items.add(ip)
                else:
                    values[0] = "☐"
                    self.checked_items.discard(ip)
                self.tree.item(item, values=values)

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item: self.tree.selection_set(item); self.context_menu.post(event.x_root, event.y_root)

    def copy_ip(self):
        selected = self.tree.selection()
        if selected:
            ip = self.tree.item(selected[0])['values'][1]
            self.root.clipboard_clear(); self.root.clipboard_append(ip); self.write_log(f"Copied IP: {ip}", "blue")

    def copy_mac(self):
        selected = self.tree.selection()
        if selected:
            mac = self.tree.item(selected[0])['values'][2]
            self.root.clipboard_clear(); self.root.clipboard_append(mac); self.write_log(f"Copied MAC: {mac}", "blue")

    def copy_row(self):
        selected = self.tree.selection()
        if selected:
            values = self.tree.item(selected[0])['values'][1:]
            self.root.clipboard_clear(); self.root.clipboard_append("\t".join(map(str, values)))

    def copy_checked_ips(self):
        if not self.checked_items: messagebox.showinfo("Info", "No items checked."); return
        text = "\n".join(sorted(list(self.checked_items)))
        self.root.clipboard_clear(); self.root.clipboard_append(text)
        self.write_log(f"Copied {len(self.checked_items)} checked IPs to clipboard.", "blue")

    def copy_checked_macs(self):
        checked_macs = []
        for item in self.tree.get_children():
            values = self.tree.item(item, 'values')
            if values[1] in self.checked_items:
                checked_macs.append(str(values[2]))
        
        if not checked_macs: messagebox.showinfo("Info", "No items checked."); return
        text = "\n".join(checked_macs)
        self.root.clipboard_clear(); self.root.clipboard_append(text)
        self.write_log(f"Copied {len(checked_macs)} checked MACs to clipboard.", "blue")

    # 新增：重新扫描功能 (单行)
    def rescan_selected_row(self):
        selected = self.tree.selection()
        if not selected: return
        ip = self.tree.item(selected[0])['values'][1]
        self.rescan_task([ip])

    # 新增：重新扫描功能 (批量勾选)
    def rescan_checked_ips(self):
        if not self.checked_items:
            messagebox.showinfo("Info", "No items checked to rescan.")
            return
        self.rescan_task(list(self.checked_items))

    # 新增：执行重扫的线程逻辑
    def rescan_task(self, ip_list):
        if self.is_running:
            messagebox.showwarning("Busy", "Task is already running. Please stop or wait.")
            return
        
        # 清理这些IP在内存中的状态，以便重新跑逻辑
        for ip in ip_list:
            if ip in self.results_data: del self.results_data[ip]
            if ip in self.locked_targets: del self.locked_targets[ip]
            if ip in self.provisioned_ips: self.provisioned_ips.discard(ip)
        
        self.is_running = True
        self.stop_requested = False
        self.write_log(f"🔄 Rescanning {len(ip_list)} IP(s)...", "blue")
        self.btn_start.config(text="● Running...", bg="#6c757d", state="disabled")
        self.btn_stop.config(text="■ STOP", bg="#dc3545", state="normal")
        
        # 借用 main_loop 的逻辑，但只跑选中的 IP
        def run():
            srv, u, p_wd = self.ent_srv.get(), self.ent_user.get(), self.ent_pass.get()
            pending = list(ip_list)
            with sync_playwright() as p:
                while not self.stop_requested and pending:
                    for ip in list(pending):
                        if self.stop_requested: break
                        self.write_log(f"👾Scanning & Working On: {ip}", "yellow")
                        status, detail, mac = self.run_one_phone(ip, p, srv, u, p_wd)
                        self.root.after(0, self.update_tree, ip, mac, status, detail)
                        if status == "DONE":
                            pending.remove(ip)
                    
                    if pending and not self.stop_requested:
                        if self.task_mode.get() in ["scan", "scan_full"]: break
                        self.write_log("☕ Cycle finished. Wait for 15s Next attempt...", "blue"); time.sleep(15)
            
            self.is_running = False
            self.root.after(0, self.reset_ui)
            if not self.stop_requested: self.write_log("🎉 RESCAN COMPLETED!", "green")

        threading.Thread(target=run, daemon=True).start()

    def delete_selected(self):
        selected = self.tree.selection()
        if selected:
            ip = str(self.tree.item(selected[0])['values'][1])
            if ip in self.results_data: del self.results_data[ip]
            if ip in self.locked_targets: del self.locked_targets[ip]
            self.checked_items.discard(ip); self.tree.delete(selected[0]); self.write_log(f"Record {ip} deleted.", "red")

    def delete_checked(self):
        if not self.checked_items: messagebox.showinfo("Info", "No items checked to delete."); return
        if messagebox.askyesno("Confirm", f"Delete {len(self.checked_items)} checked records?"):
            for item in self.tree.get_children():
                values = self.tree.item(item, 'values'); ip = values[1]
                if ip in self.checked_items:
                    if ip in self.results_data: del self.results_data[ip]
                    if ip in self.locked_targets: del self.locked_targets[ip]
                    self.tree.delete(item)
            self.write_log(f"Deleted {len(self.checked_items)} checked records.", "red"); self.checked_items.clear()

    def clear_all_results(self):
        if not self.results_data: return
        if messagebox.askyesno("Confirm", "Clear all data and reset process?"):
            self.results_data.clear(); self.provisioned_ips.clear(); self.checked_items.clear()
            self.locked_targets.clear()
            for item in self.tree.get_children(): self.tree.delete(item)
            self.write_log("All results cleared.", "red")

    def on_tree_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id: ip = self.tree.item(item_id, 'values')[1]; webbrowser.open(f"http://{ip}")

    def setup_tags(self):
        self.log_text.tag_config("green", foreground="#00ff00"); self.log_text.tag_config("yellow", foreground="#ffff00"); self.log_text.tag_config("red", foreground="#ff4444"); self.log_text.tag_config("blue", foreground="#00ccff")
        self.tree.tag_configure('done', background='#e8f5e9'); self.tree.tag_configure('retry', background='#fffde7'); self.tree.tag_configure('error', background='#ffebee')

    def update_tree(self, ip, mac, status, detail):
        for item in self.tree.get_children():
            if str(self.tree.item(item)['values'][1]) == str(ip): self.tree.delete(item)
        tag = 'retry'
        if status == "DONE": tag = 'done'
        if "OFFLINE" in detail or "MAC MISMATCH" in detail or "IP CONFLICT" in detail or "FAIL" in detail: tag = 'error'
        check_mark = "☑" if ip in self.checked_items else "☐"
        self.tree.insert("", "end", values=(check_mark, ip, mac, status, detail), tags=(tag,))
        self.results_data[str(ip)] = [ip, mac, status, detail]

    def export_csv(self):
        if not self.results_data: return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if path:
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f); writer.writerow(['IP Address', 'MAC Address', 'Status', 'Detail']); writer.writerows(self.results_data.values())
            messagebox.showinfo("Success", "Export Complete")

    def write_log(self, msg, level="info"):
        self.log_text.config(state="normal"); tag = "white"
        if level == "blue": tag = "blue"
        elif any(x in msg for x in ["DONE", "Registered", "🎉", "Total", "Found"]): tag = "green"
        elif any(x in msg for x in ["☕", "👾", "Scanning & Working On"]): tag = "yellow"
        elif any(x in msg for x in ["OFFLINE", "Stopped", "deleted", "Fail", "MAC MISMATCH", "IP CONFLICT"]): tag = "red"
        self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n", tag); self.log_text.see("end"); self.log_text.config(state="disabled")

    def toggle_hotkeys(self):
        if not self.hotkey_running:
            self.hotkey_running = True; self.btn_hk_toggle.config(text="Shortcut: ENABLED", bg="#28a745")
            self.listener = keyboard.GlobalHotKeys({'<alt>+1': lambda: self.exec_sh(self.hk1_u.get(), self.hk1_p.get()), '<alt>+2': lambda: self.exec_sh(self.hk2_u.get(), self.hk2_p.get())})
            self.listener.start()
        else:
            self.hotkey_running = False; self.btn_hk_toggle.config(text="Shortcut: DISABLED", bg="#6c757d")
            if self.listener: self.listener.stop()

    def exec_sh(self, u, p):
        time.sleep(0.5); pyautogui.write(u, interval=0.05); pyautogui.press('tab'); time.sleep(0.1); pyautogui.write(p, interval=0.05); pyautogui.press('enter')

    def get_status_info(self, page):
        reg_status = "Unknown"; mac_addr = "N/A"
        try:
            # 尝试跳转到 index 页面获取信息
            page.goto(f"http://{page.url.split('/')[2]}/index.htm", timeout=8000)
            page.wait_for_load_state("networkidle")
            for xpath in ["//td[contains(text(), 'Account 1')]/following-sibling::td[1]", "//td[text()='Account 1']/following-sibling::td[1]"]:
                try:
                    text = page.locator(f"xpath={xpath}").inner_text(timeout=2000).strip()
                    if text: reg_status = text.replace("\n", " "); break
                except: continue
            for xpath in ["//td[contains(text(), 'MAC Address')]/following-sibling::td[1]", "//td[@width='280' and contains(text(), ':')]", "//td[contains(text(), 'MAC')]/following-sibling::td"]:
                try:
                    text = page.locator(f"xpath={xpath}").inner_text(timeout=2000).strip()
                    if text and ":" in text: mac_addr = text.replace(":", ""); break
                except: continue
        except: pass
        return reg_status, mac_addr

    def run_one_phone(self, ip, p, srv, user, pwd):
        # 1. 检查物理连通性
        ping_ok = check_ping(ip)
        current_mac = get_mac_address(ip)
        allowed_prefix = self.ent_mac_prefix.get().strip().lower()

        # 如果是纯 ARP 扫描模式
        if self.task_mode.get() == "scan":
            if not ping_ok: return "DONE", "OFFLINE (No Device Found)", "N/A"
            if not current_mac: return "DONE", "FAIL (ARP MAC not found)", "N/A"
            if not current_mac.startswith(allowed_prefix):
                return "DONE", f"MAC MISMATCH (Prefix should be {allowed_prefix})", current_mac
            return "DONE", "Found (Scan Only)", current_mac

        # 如果是 Scan + Phone Status 模式 或者 Provision 模式
        # 初始检查
        if not ping_ok: return "DONE", "OFFLINE (No Device Found)", "N/A"
        if not current_mac: return "DONE", "FAIL (ARP MAC not found)", "N/A"
        if not current_mac.startswith(allowed_prefix):
            return "DONE", f"MAC MISMATCH (Prefix should be {allowed_prefix})", current_mac
        
        # 锁定当前 MAC
        self.locked_targets[ip] = current_mac

        # 尝试登录并获取信息
        for u, p_wd in [(self.hk2_u.get(), self.hk2_p.get()), (self.hk1_u.get(), self.hk1_p.get())]:
            if self.stop_requested: return "STOP", "Aborted", "N/A"
            browser = None
            try:
                browser = p.chromium.launch(headless=True, executable_path=SYSTEM_BROWSER)
                context = browser.new_context(http_credentials={"username": u, "password": p_wd}, ignore_https_errors=True)
                page = context.new_page()
                
                # 尝试进入一个页面以触发认证
                res = page.goto(f"http://{ip}/index.htm", timeout=10000)
                if res.status == 401: 
                    browser.close(); continue
                
                # 登录成功，获取状态
                info, mac = self.get_status_info(page)
                
                # 如果是 Scan Full 模式，拿到结果就走
                if self.task_mode.get() == "scan_full":
                    browser.close()
                    return "DONE", f"Status: {info} | MAC: {mac}", current_mac

                # 如果是 Provision 模式
                # 检查是否已经注册成功，如果已成功且不是由本次程序刚改的，可以跳过（或根据需要逻辑）
                if info != "Unknown" and "Registered" in info and ip in self.provisioned_ips:
                    browser.close(); return "DONE", info, mac

                # 执行 Provision 填单操作
                page.goto(f"http://{ip}/auto_provision.htm", timeout=10000)
                page.fill('input[name="P237"]', srv)
                page.fill('input[name="P1360"]', user)
                page.evaluate('document.querySelector(\'input[name="P1361"]\').removeAttribute("readonly")')
                page.fill('input[name="P1361"]', pwd)
                page.click('input[value="SaveSet"]', force=True)
                time.sleep(0.5)
                page.click('input[value="Autoprovision Now"]', force=True)
                self.provisioned_ips.add(ip); browser.close()
                return "RETRY", "Provision Sent -> Rebooting", current_mac
            except:
                if browser: browser.close()
                continue
        
        return "RETRY", "Waiting Login / Auth Fail", current_mac

    def start_task(self):
        if not SYSTEM_BROWSER: messagebox.showerror("Error", "No browser found!"); return
        self.is_running = True; self.stop_requested = False
        mode_map = {
            "provision": "Full Provision",
            "scan": "MAC Scanning",
            "scan_full": "IP, MAC & Phone Status Scan"
        }
        self.write_log(f"🚀 Starting Task Mode: {mode_map.get(self.task_mode.get())}", "blue")
        self.btn_start.config(text="● Running...", bg="#6c757d", state="disabled"); self.btn_stop.config(text="■ STOP", bg="#dc3545", state="normal")
        threading.Thread(target=self.main_loop, daemon=True).start()

    def stop_task(self):
        self.stop_requested = True; self.write_log("Stopping...", "red")

    def main_loop(self):
        srv, u, p_wd = self.ent_srv.get(), self.ent_user.get(), self.ent_pass.get()
        ip_range_str = self.ip_range_entry.get().strip()
        if ip_range_str: all_ips = parse_ip_range(ip_range_str); self.write_log(f"Using IP Range: {ip_range_str}", "blue")
        else:
            raw_ips = self.ip_input.get("1.0", "end").strip().splitlines()
            all_ips = [line.strip() for line in raw_ips if line.strip() and not line.startswith("#")]
        
        pending = [ip for ip in all_ips if ip not in self.results_data]
        if not pending: self.write_log("No new IP to process.", "yellow")
        else:
            self.write_log(f"Found {len(pending)} IP(s) to process. Working...", "blue")
            with sync_playwright() as p:
                while not self.stop_requested and pending:
                    for ip in list(pending):
                        if self.stop_requested: break
                        self.write_log(f"👾Scanning & Working On: {ip}", "yellow")
                        status, detail, mac = self.run_one_phone(ip, p, srv, u, p_wd)
                        self.root.after(0, self.update_tree, ip, mac, status, detail)
                        if status == "DONE": 
                            pending.remove(ip)
                        
                    if pending and not self.stop_requested:
                        # 扫描模式不需要循环重试
                        if self.task_mode.get() in ["scan", "scan_full"]: break
                        self.write_log("☕ Cycle finished. Wait for 15s Next attempt...", "blue"); time.sleep(15)
                
                if not self.stop_requested:
                    self.write_log("🎉 TASK COMPLETED!", "green")
                    total_success = 0; total_fail = 0
                    for item in self.tree.get_children():
                        values = self.tree.item(item)['values']
                        mac_addr = str(values[2])
                        status_str = str(values[3])
                        detail_str = str(values[4])
                        
                        if status_str == "DONE" and mac_addr != "N/A":
                            if not any(x in detail_str for x in ["OFFLINE", "MAC MISMATCH", "IP CONFLICT", "FAIL"]):
                                total_success += 1
                            else:
                                total_fail += 1
                        elif status_str == "DONE":
                            total_fail += 1
                    
                    self.write_log("-" * 30, "white")
                    self.write_log(f"📊 Summary Results:", "blue")
                    self.write_log(f"✅ Total Success/Found: {total_success}", "green")
                    self.write_log(f"❌ Total Fail (Offline/Mismatch/Conflict): {total_fail}", "red")
                    self.write_log("-" * 30, "white")
        
        self.is_running = False; self.root.after(0, self.reset_ui)

    def reset_ui(self):
        self.btn_start.config(text="▶ START Task", bg="#007bff", state="normal"); self.btn_stop.config(text="■ STOP", bg="#6c757d", state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = UCApp(root)
    root.mainloop)
