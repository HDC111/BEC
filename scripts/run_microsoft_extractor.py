import tkinter as tk
from tkinter import messagebox
from tkcalendar import DateEntry
import subprocess
import datetime
import yaml
import os
import threading

# === Load settings ===
with open("config/settings.yaml", "r") as f:
    settings = yaml.safe_load(f)

extractor_root = settings["extractors"]["microsoft"]["root_path"]
module_psd1_path = os.path.join(extractor_root, "Microsoft-Extractor-Suite.psd1")
module_psd1_path = os.path.abspath(module_psd1_path)

LOG_OPTIONS = {
    "Unified Audit Log (UAL)": "Get-UAL",
    "Sign-In Logs": "Get-GraphEntraSignInLogs",
    "Mail Flow Logs": "Get-MessageTraceLog",
    "Admin Audit Logs": "Get-AdminAuditLog",
    "Mailbox Audit Logs": "Get-MailboxAuditLog",
    "Mailbox Rules": "Get-MailboxRules",
    "Transport Rules": "Get-TransportRules",
    "OAuth Permissions": "Get-OAuthPermissions",
    "Risky Users": "Get-RiskyUsers",
    "Risky Detections": "Get-RiskyDetections",
    "Conditional Access Policies": "Get-ConditionalAccessPolicies",
    "MFA Status": "Get-MFA",
    "Mailbox Permissions": "Get-MailboxPermissions"
}


def run_extraction(selected_logs, start_date, end_date, added_users):
    start_utc = start_date.strftime("%Y-%m-%dT00:00:00Z")
    end_utc = end_date.strftime("%Y-%m-%dT23:59:59Z")

    powershell_commands = []

    for label in selected_logs:
        command = LOG_OPTIONS[label]

        # Determine if the command accepts -StartDate/-EndDate
        has_date = command in [
            "Get-UAL",
            "Get-GraphEntraSignInLogs",
            "Get-MessageTraceLog",
            "Get-AdminAuditLog",
            "Get-MailboxAuditLog"
        ]

        # Determine if the command supports -MergeOutput
        supports_merge = command in [
            "Get-UAL",
            "Get-GraphEntraSignInLogs",
            "Get-AdminAuditLog",
            "Get-MailboxAuditLog"
        ]

        # Handle user filtering
        param = ""
        if added_users:
            if command in ["Get-UAL", "Get-AdminAuditLog", "Get-MailboxAuditLog"]:
                param = "-UserIds " + ",".join([f'"{u}"' for u in added_users])
            elif command in ["Get-GraphEntraSignInLogs", "Get-MailboxRules", "Get-MailboxPermissions"]:
                param = "-UserPrincipalName " + ",".join([f'"{u}"' for u in added_users])
            elif command == "Get-MessageTraceLog":
                param = "-RecipientAddress " + ",".join([f'"{u}"' for u in added_users])

        # Assemble command
        cmd_parts = [command]
        if has_date:
            cmd_parts.append(f'-StartDate "{start_utc}"')
            cmd_parts.append(f'-EndDate "{end_utc}"')
        if param:
            cmd_parts.append(param)
        if supports_merge:
            cmd_parts.append("-MergeOutput")

        powershell_commands.append(" ".join(cmd_parts))

    full_script = (
        f"Import-Module '{module_psd1_path}'; "
        f"Connect-M365; "
        f"Connect-Azure; "
        + "; ".join(powershell_commands)
    )

    try:
        powershell_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        subprocess.run([powershell_path, "-Command", full_script], check=True)
        messagebox.showinfo("Success", "Log extraction completed.")
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"An error occurred:\n{e}")



def open_gui():
    root = tk.Tk()
    root.title("Microsoft Log Extractor")
    root.geometry("550x780")

    canvas = tk.Canvas(root)
    scrollbar = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
    scroll_frame = tk.Frame(canvas)

    scroll_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # === Log selection
    tk.Label(scroll_frame, text="Select logs to extract:", font=('Arial', 12, 'bold')).pack(pady=10)

    checkboxes = {}
    for option in LOG_OPTIONS:
        var = tk.BooleanVar()
        cb = tk.Checkbutton(scroll_frame, text=option, variable=var)
        cb.pack(anchor='w', padx=15)
        checkboxes[option] = var

    # === Date pickers
    tk.Label(scroll_frame, text="Start Date (UTC):", anchor="w").pack(pady=(20, 0), anchor="w", padx=15)
    start_entry = DateEntry(scroll_frame, width=16, background='darkblue', foreground='white', borderwidth=2)
    start_entry.pack(pady=5, anchor="w", padx=15)

    tk.Label(scroll_frame, text="End Date (UTC):", anchor="w").pack(pady=(10, 0), anchor="w", padx=15)
    end_entry = DateEntry(scroll_frame, width=16, background='darkblue', foreground='white', borderwidth=2)
    end_entry.pack(pady=5, anchor="w", padx=15)

    # === Filter by user
    tk.Label(scroll_frame, text="Filter by User (optional):", font=('Arial', 10), anchor="w").pack(pady=(20, 0), anchor="w", padx=15)

    user_input_container = tk.Frame(scroll_frame)
    user_input_container.pack(padx=15, pady=(5, 10), anchor="w")

    user_entry = tk.Entry(user_input_container, width=30)
    user_entry.pack(side="left")

    # Prepare user list structures and logic
    added_users = []
    user_rows = []

    user_list_container = tk.Frame(scroll_frame)
    user_list_container.pack(padx=20, anchor="w", pady=(0, 15))

    def refresh_user_list():
        for row in user_rows:
            row.destroy()
        user_rows.clear()
        for user in added_users:
            frame = tk.Frame(user_list_container)
            label = tk.Label(frame, text=user, fg="blue", anchor="w", width=30)
            delete_button = tk.Button(frame, text="❌", fg="red", command=lambda u=user: remove_user(u), bd=0)
            label.pack(side="left", padx=(0, 5))
            delete_button.pack(side="left")
            frame.pack(anchor="w", pady=2)
            user_rows.append(frame)

    def add_user():
        user = user_entry.get().strip()
        if user and user not in added_users:
            added_users.append(user)
            refresh_user_list()
        user_entry.delete(0, tk.END)

    def remove_user(user):
        if user in added_users:
            added_users.remove(user)
            refresh_user_list()

    add_btn = tk.Button(user_input_container, text="Add", command=add_user)
    add_btn.pack(side="left", padx=(5, 0))

    # === Submit Button
    def on_submit():
        selected = [key for key, var in checkboxes.items() if var.get()]
        if not selected:
            messagebox.showwarning("Warning", "Please select at least one log type.")
            return

        extract_button.config(state=tk.DISABLED)
        extract_button.config(text="Extracting...")

        def threaded_extraction():
            try:
                run_extraction(selected, start_entry.get_date(), end_entry.get_date(), added_users)
            finally:
                extract_button.config(state=tk.NORMAL)
                extract_button.config(text="Extract Logs")

        threading.Thread(target=threaded_extraction).start()

    extract_button = tk.Button(scroll_frame, text="Extract Logs", command=on_submit, bg="green", fg="white", font=('Arial', 11))
    extract_button.pack(pady=30)


    root.mainloop()


