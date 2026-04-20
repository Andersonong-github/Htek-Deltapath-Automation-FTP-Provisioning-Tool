# -*- coding: utf-8 -*-
# Author: Anderson Ong (UC & Voice Delivery Team)
# Version: 8.2.0 (Public Edition)
# Purpose: Auto-Provisioning Tool for Htek/Deltapath IP Phones

import csv
import time
import os
import sys
import subprocess
import threading
import ctypes
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from playwright.sync_api import sync_playwright
import pyautogui
from pynput import keyboard

# --- Resource Path Handling ---
def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

CHROME_PATH = get_resource_path(os.path.join("resources", "chromium-1208", "chrome-win", "chrome.exe"))
APP_ICON = get_resource_path(os.path.join("resources", "app.ico"))

# --- Windows Taskbar Icon Fix ---
try:
    myappid = u'AnderOng.AutoProvision.Public.8.2'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except:
    pass

def check_ping(ip):
    try:
        output = subprocess.run(['ping', '-n', '1', '-w', '800', ip.strip()], capture_output=True, text=True)
        return output.returncode == 0
    except: return False

class UCApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Htek/Deltapath Auto-Provisioning Tool")
        self.root.geometry("1150x850") 
        
        try:
            if os.path.exists(APP_ICON): 
                self.root.iconbitmap(APP_ICON)
        except: pass

        self.is_running = False
        self.stop_requested = False
        self.provisioned_ips = set()
        self.hotkey_running = False
        self.listener = None
        self.results_data = {} 

        self.setup_ui()

    def setup_ui(self):
        main_container = tk.Frame(self.root)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Left Panel: Configuration ---
        left_panel = tk.Frame(main_container, width=420)
        left_panel.pack(side="left", fill="y", padx=(0, 10))

        frame_ip = ttk.LabelFrame(left_panel, text=" Device IP List (One per line) ")
        frame_ip.pack(fill="x", pady=5)
        self.ip_input = tk.Text(frame_ip, height=8, font=("Consolas", 10))
        self.ip_input.pack(padx=5, pady=5, fill="x")
        self.ip_input.insert("1.0", "# Example:\n192.168.1.100") # 已移除内部测试 IP

        frame_srv = ttk.LabelFrame(left_panel, text=" Provision Server Configuration ")
        frame_srv.pack(fill="x", pady=5)
        # 已将所有硬编码的敏感信息替换为通用占位符
        self.ent_srv = self.create_label_entry(frame_srv, "Config Server:", "your.provision.server", 0)
        self.ent_user = self.create_label_entry(frame_srv, "HTTP User:", "username", 1)
        self.ent_pass = self.create_label_entry(frame_srv, "HTTP Pass:", "", 2)
        frame_srv.columnconfigure(1, weight=1)

        btn_f = tk.Frame(left_panel)
        btn_f.pack(pady=10, fill="x")
        self.btn_start = tk.Button(btn_f, text="▶ START Task", bg="#007bff", fg="white", font=("Arial", 10, "bold"), height=2, command=self.start_task)
        self.btn_start.pack(side="left", expand=True, fill="x", padx=2)
        self.btn_stop = tk.Button(btn_f, text="■ STOP", bg="#6c757d", fg="white", font=("Arial", 10, "bold"), height=2, state="disabled", command=self.stop_task)
        self.btn_stop.pack(side="left", expand=True, fill="x", padx=2)

        self.log_text = tk.Text(left_panel, height=15, bg="#1e1e1e", fg="#ffffff", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

        # Shortcut Helper for Manual Login
        frame_hk = ttk.LabelFrame(left_panel, text=" Quick-Login Hotkeys ")
        frame_hk.pack(fill="x", pady=5)
        row1 = tk.Frame(frame_hk); row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="Alt+1 Creds:").pack(side="left", padx=5)
        self.hk1_u = ttk.Entry(row1, width=8); self.hk1_u.insert(0, "admin"); self.hk1_u.pack(side="left", padx=2)
        self.hk1_p = ttk.Entry(row1, width=12); self.hk1_p.insert(0, "admin"); self.hk1_p.pack(side="left", padx=2)
        
        row2 = tk.Frame(frame_hk); row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="Alt+2 Creds:").pack(side="left", padx=5)
        self.hk2_u = ttk.Entry(row2, width=8); self.hk2_u.insert(0, "admin"); self.hk2_u.pack(side="left", padx=2)
        self.hk2_p = ttk.Entry(row2, width=12); self.hk2_p.insert(0, ""); self.hk2_p.pack(side="left", padx=2)

        self.btn_hk_toggle = tk.Button(left_panel, text="Hotkey: DISABLED", bg="#6c757d", fg="white", font=("Arial", 10, "bold"), command=self.toggle_hotkeys)
        self.btn_hk_toggle.pack(fill="x", pady=5)

        # --- Right Panel: Monitoring ---
        right_panel = ttk.LabelFrame(main_container, text=" Live Monitoring ")
        right_panel.pack(side="right", fill="both", expand=True)

        columns = ("ip", "mac", "status", "detail")
        self.tree = ttk.Treeview(right_panel, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("ip", text="IP Address")
        self.tree.heading("mac", text="MAC Address")
        self.tree.heading("status", text="Status")
        self.tree.heading("detail", text="Detail")
        
        self.tree.column("ip", width=120, anchor="center")
        self.tree.column("mac", width=130, anchor="center")
        self.tree.column("status", width=90, anchor="center")
        self.tree.column("detail", width=350)

        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Button-3>", self.show_context_menu)

        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="📋 Copy IP", command=self.copy_ip)
        self.context_menu.add_command(label="📄 Copy Row", command=self.copy_row)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="❌ Delete Record", command=self.delete_selected, foreground="red")

        vsb = ttk.Scrollbar(right_panel, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="top", fill="both", expand=True, padx=5, pady=5)
        vsb.pack(side="right", fill="y")

        self.btn_export = tk.Button(right_panel, text="📥 Export Results to CSV", bg="#28a745", fg="white", command=self.export_csv)
        self.btn_export.pack(fill="x", padx=5, pady=5)
        
        footer_frame = tk.Frame(self.root)
        footer_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 2))
        author_label = tk.Label(footer_frame, text="Author: Anderson Ong | UC Specialist", font=("Arial", 7), fg="#a0a0a0")
        author_label.pack(side="right")

        self.setup_tags()

    def create_label_entry(self, parent, label, default, row): 
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ent = ttk.Entry(parent)
        ent.insert(0, default)
        ent.grid(row=row, column=1, sticky="ew", padx=5, pady=2)
        return ent

    def write_log(self, msg, level="info"):
        self.log_text.config(state="normal")
        tag = "white"
        if level == "blue": tag = "blue"
        elif any(x in msg for x in ["DONE", "Registered", "🎉"]): tag = "green"
        elif any(x in msg for x in ["☕", "Scanning"]): tag = "yellow"
        elif any(x in msg for x in ["OFFLINE", "Stopped"]): tag = "red"
        self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n", tag)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def toggle_hotkeys(self):
        if not self.hotkey_running:
            self.hotkey_running = True
            self.btn_hk_toggle.config(text="Hotkey: ENABLED", bg="#28a745")
            self.listener = keyboard.GlobalHotKeys({
                '<alt>+1': lambda: self.exec_sh(self.hk1_u.get(), self.hk1_p.get()),
                '<alt>+2': lambda: self.exec_sh(self.hk2_u.get(), self.hk2_p.get())
            })
            self.listener.start()
        else:
            self.hotkey_running = False
            self.btn_hk_toggle.config(text="Hotkey: DISABLED", bg="#6c757d")
            if self.listener: self.listener.stop()

    def exec_sh(self, u, p):
        time.sleep(0.5)
        pyautogui.write(u, interval=0.05); pyautogui.press('tab')
        time.sleep(0.1); pyautogui.write(p, interval=0.05); pyautogui.press('enter')

    def run_one_phone(self, ip, p, srv, user, pwd):
        if not check_ping(ip):
            if ip in self.provisioned_ips: return "RETRY", "Rebooting...", "N/A"
            return "DONE", "OFFLINE", "N/A"

        for u, p_wd in [(self.hk2_u.get(), self.hk2_p.get()), (self.hk1_u.get(), self.hk1_p.get())]:
            if self.stop_requested: return "STOP", "Aborted", "N/A"
            browser = None
            try:
                browser = p.chromium.launch(headless=True, executable_path=CHROME_PATH)
                context = browser.new_context(http_credentials={"username": u, "password": p_wd}, ignore_https_errors=True)
                page = context.new_page()
                res = page.goto(f"http://{ip}/auto_provision.htm", timeout=10000)
                
                if res.status == 401: browser.close(); continue
                
                # Configuration Injection
                page.fill('input[name="P237"]', srv)
                page.fill('input[name="P1360"]', user)
                page.evaluate('document.querySelector(\'input[name="P1361"]\').removeAttribute("readonly")')
                page.fill('input[name="P1361"]', pwd)
                page.click('input[value="SaveSet"]', force=True)
                time.sleep(0.5); page.click('input[value="Autoprovision Now"]', force=True)
                
                self.provisioned_ips.add(ip)
                browser.close()
                return "RETRY", "Task Sent", "N/A"
            except:
                if browser: browser.close()
                continue
        return "RETRY", "Login Fail", "N/A"

    def start_task(self):
        self.is_running = True
        self.stop_requested = False
        self.btn_start.config(text="● Running", bg="#6c757d", state="disabled")
        self.btn_stop.config(text="■ STOP", bg="#dc3545", state="normal")
        threading.Thread(target=self.main_loop, daemon=True).start()

    def stop_task(self):
        self.stop_requested = True
        self.write_log("Stopping...", "red")

    def main_loop(self):
        srv, u, p_wd = self.ent_srv.get(), self.ent_user.get(), self.ent_pass.get()
        raw_ips = self.ip_input.get("1.0", "end").strip().splitlines()
        all_ips = [line.strip() for line in raw_ips if line.strip() and not line.startswith("#")]
        pending = [ip for ip in all_ips if ip not in self.results_data]
        
        if pending:
            with sync_playwright() as p:
                while not self.stop_requested and pending:
                    for ip in list(pending):
                        if self.stop_requested: break
                        self.write_log(f"Processing: {ip}", "yellow")
                        status, detail, mac = self.run_one_phone(ip, p, srv, u, p_wd)
                        self.root.after(0, self.update_tree, ip, mac, status, detail)
                        if status == "DONE": pending.remove(ip)
                    if pending and not self.stop_requested: time.sleep(15)
        
        self.is_running = False
        self.root.after(0, self.reset_ui)

    def update_tree(self, ip, mac, status, detail):
        for item in self.tree.get_children():
            if str(self.tree.item(item)['values'][0]) == str(ip): self.tree.delete(item)
        tag = 'retry'
        if status == "DONE": tag = 'done'
        if "OFFLINE" in detail: tag = 'error'
        self.tree.insert("", "end", values=(ip, mac, status, detail), tags=(tag,))
        self.results_data[str(ip)] = [ip, mac, status, detail]

    def setup_tags(self):
        self.log_text.tag_config("green", foreground="#00ff00")
        self.log_text.tag_config("yellow", foreground="#ffff00")
        self.log_text.tag_config("red", foreground="#ff4444")
        self.log_text.tag_config("blue", foreground="#00ccff")
        self.tree.tag_configure('done', background='#e8f5e9')
        self.tree.tag_configure('retry', background='#fffde7')
        self.tree.tag_configure('error', background='#ffebee')

    def reset_ui(self):
        self.btn_start.config(text="▶ START Task", bg="#007bff", state="normal")
        self.btn_stop.config(text="■ STOP", bg="#6c757d", state="disabled")

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def copy_ip(self):
        selected = self.tree.selection()
        if selected:
            ip = self.tree.item(selected[0])['values'][0]
            self.root.clipboard_clear(); self.root.clipboard_append(ip)

    def copy_row(self):
        selected = self.tree.selection()
        if selected:
            values = self.tree.item(selected[0])['values']
            self.root.clipboard_clear(); self.root.clipboard_append("\t".join(map(str, values)))

    def delete_selected(self):
        selected = self.tree.selection()
        if selected:
            ip = str(self.tree.item(selected[0])['values'][0])
            if ip in self.results_data: del self.results_data[ip]
            self.tree.delete(selected[0])

    def on_tree_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            ip_to_open = self.tree.item(item_id, 'values')[0]
            webbrowser.open(f"http://{ip_to_open}")

    def export_csv(self):
        if not self.results_data: return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if path:
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['IP Address', 'MAC Address', 'Status', 'Detail'])
                writer.writerows(self.results_data.values())

if __name__ == "__main__":
    root = tk.Tk()
    app = UCApp(root)
    root.mainloop()
