import argparse
import os
import subprocess
import sys
from datetime import date, datetime, time, timedelta

FORMATS = [
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
    "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M",
    "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
    "%Y-%m-%d %I:%M %p", "%d-%m-%Y %I:%M %p",
    "%Y-%m-%d", "%d-%m-%Y",  # date only -> 12:00
]


def git(*args, check=True, env=None):
    res = subprocess.run(["git", *args], capture_output=True, text=True, env=env)
    if check and res.returncode != 0:
        print(f"git {' '.join(args)} failed:\n{res.stderr.strip() or res.stdout.strip()}")
        sys.exit(1)
    return res.stdout.strip()


def parse_date(s):
    s = s.strip()
    if s.lower() in ("", "now"):
        return datetime.now()
    for fmt in FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            if fmt in ("%Y-%m-%d", "%d-%m-%Y"):
                dt = dt.replace(hour=12)
            return dt
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------- GUI picker
def gui_available():
    try:
        import tkinter
        tkinter.Tk().destroy()
        return True
    except Exception:
        return False


def pick_gui(files, default_msg=""):
    """Calendar + time dialog. Returns (datetime, message) or (None, None) if cancelled."""
    import calendar
    import tkinter as tk
    from tkinter import ttk, messagebox

    root = tk.Tk()
    root.title("Backdate commit")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    today = date.today()
    st = {"sel": today, "year": today.year, "month": today.month}
    result = {}

    BLUE, GRAY = "#2563eb", "#9ca3af"

    frm = ttk.Frame(root, padding=14)
    frm.pack()

    ttk.Label(frm, text=f"{len(files)} file(s) staged",
              foreground=GRAY).grid(row=0, column=0, columnspan=7, pady=(0, 6))

    # --- month navigation
    title_var = tk.StringVar()

    def shift(months):
        m = st["month"] - 1 + months
        st["year"] += m // 12
        st["month"] = m % 12 + 1
        render()

    ttk.Button(frm, text="«", width=3, command=lambda: shift(-12)).grid(row=1, column=0)
    ttk.Button(frm, text="‹", width=3, command=lambda: shift(-1)).grid(row=1, column=1)
    ttk.Label(frm, textvariable=title_var, anchor="center",
              font=("TkDefaultFont", 11, "bold")).grid(row=1, column=2, columnspan=3, sticky="ew")
    ttk.Button(frm, text="›", width=3, command=lambda: shift(1)).grid(row=1, column=5)
    ttk.Button(frm, text="»", width=3, command=lambda: shift(12)).grid(row=1, column=6)

    # --- weekday header (Sunday first)
    for i, d in enumerate(["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]):
        ttk.Label(frm, text=d, anchor="center", foreground=GRAY, width=4).grid(row=2, column=i, pady=(8, 2))

    # --- 6x7 day grid
    cells = []
    for r in range(6):
        for c in range(7):
            lbl = tk.Label(frm, width=4, height=1, anchor="center", cursor="hand2",
                           bd=1, relief="flat", padx=2, pady=3)
            lbl.grid(row=3 + r, column=c, padx=1, pady=1)
            cells.append(lbl)

    def pick_day(d):
        st["sel"] = d
        st["year"], st["month"] = d.year, d.month
        render()

    def render():
        y, m = st["year"], st["month"]
        title_var.set(f"{calendar.month_name[m]} {y}")
        first = date(y, m, 1)
        start = first - timedelta(days=(first.weekday() + 1) % 7)
        default_bg = root.cget("bg")
        for i, lbl in enumerate(cells):
            d = start + timedelta(days=i)
            lbl.config(text=str(d.day), bg=default_bg,
                       fg=("black" if d.month == m else GRAY), relief="flat")
            if d == today:
                lbl.config(relief="ridge")
            if d == st["sel"]:
                lbl.config(bg=BLUE, fg="white")
            lbl.bind("<Button-1>", lambda e, d=d: pick_day(d))

    # --- time row
    trow = ttk.Frame(frm)
    trow.grid(row=9, column=0, columnspan=7, pady=(12, 4))
    now = datetime.now()
    hour_var = tk.StringVar(value=str(now.hour % 12 or 12))
    min_var = tk.StringVar(value=f"{now.minute:02d}")
    ampm_var = tk.StringVar(value="PM" if now.hour >= 12 else "AM")

    ttk.Label(trow, text="Time:").pack(side="left", padx=(0, 6))
    ttk.Spinbox(trow, from_=1, to=12, width=3, wrap=True, textvariable=hour_var,
                format="%.0f", justify="center").pack(side="left")
    ttk.Label(trow, text=":").pack(side="left")
    ttk.Spinbox(trow, from_=0, to=59, width=3, wrap=True, textvariable=min_var,
                format="%02.0f", justify="center").pack(side="left")
    ttk.Combobox(trow, values=["AM", "PM"], width=4, state="readonly",
                 textvariable=ampm_var).pack(side="left", padx=(6, 0))

    def set_now():
        n = datetime.now()
        hour_var.set(str(n.hour % 12 or 12))
        min_var.set(f"{n.minute:02d}")
        ampm_var.set("PM" if n.hour >= 12 else "AM")
        pick_day(date.today())

    ttk.Button(trow, text="Now", width=5, command=set_now).pack(side="left", padx=(10, 0))

    # --- message
    ttk.Label(frm, text="Commit message:").grid(row=10, column=0, columnspan=7, sticky="w", pady=(8, 2))
    msg_var = tk.StringVar(value=default_msg)
    entry = ttk.Entry(frm, textvariable=msg_var, width=42)
    entry.grid(row=11, column=0, columnspan=7, sticky="ew")

    # --- buttons
    def ok(event=None):
        try:
            h = int(float(hour_var.get()))
            mi = int(float(min_var.get()))
            if not (1 <= h <= 12 and 0 <= mi <= 59):
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid time", "Hour must be 1-12 and minute 0-59.", parent=root)
            return
        if not msg_var.get().strip():
            messagebox.showerror("Missing message", "Enter a commit message.", parent=root)
            return
        h24 = h % 12 + (12 if ampm_var.get() == "PM" else 0)
        result["dt"] = datetime.combine(st["sel"], time(h24, mi))
        result["msg"] = msg_var.get().strip()
        root.destroy()

    brow = ttk.Frame(frm)
    brow.grid(row=12, column=0, columnspan=7, pady=(12, 0), sticky="e")
    ttk.Button(brow, text="Cancel", command=root.destroy).pack(side="left", padx=4)
    ttk.Button(brow, text="Commit", command=ok).pack(side="left")

    root.bind("<Return>", ok)
    root.bind("<Escape>", lambda e: root.destroy())

    render()
    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 3
    root.geometry(f"+{x}+{y}")
    root.lift()
    root.focus_force()
    entry.focus_set()
    root.mainloop()

    return result.get("dt"), result.get("msg")


# -------------------------------------------------------------- CLI fallback
def pick_cli(default_msg=""):
    dt = None
    while dt is None:
        raw = input('Date & time (e.g. 2026-03-14 18:30, 14-03-2026 6:30 PM, or "now"): ')
        dt = parse_date(raw)
        if dt is None:
            print("Couldn't parse that, try again.")
    msg = default_msg or input("Commit message: ").strip()
    return dt, msg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-d", "--date", help='e.g. "2026-03-14 18:30"')
    ap.add_argument("-m", "--message", help="commit message")
    ap.add_argument("--cli", action="store_true", help="use terminal prompts instead of the GUI")
    args = ap.parse_args()

    if subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                      capture_output=True, text=True).returncode != 0:
        print("Not inside a git repository.")
        sys.exit(1)

    name = git("config", "user.name", check=False)
    email = git("config", "user.email", check=False)
    if not name or not email:
        print("Set your git identity first:\n"
              '  git config user.name "Your Name"\n'
              '  git config user.email "you@example.com"')
        sys.exit(1)

    staged = git("diff", "--cached", "--name-only")
    if not staged:
        if not git("status", "--porcelain"):
            print("Nothing to commit - working tree clean.")
            sys.exit(0)
        ans = input("Nothing staged. Run `git add -A` now? [Y/n]: ").strip().lower()
        if ans in ("", "y", "yes"):
            git("add", "-A")
            staged = git("diff", "--cached", "--name-only")
        else:
            print("Aborted. Stage files with `git add .` and re-run.")
            sys.exit(0)

    files = staged.splitlines()
    print("\nFiles to be committed:")
    for f in files:
        print(f"  {f}")
    print()

    dt = parse_date(args.date) if args.date else None
    msg = args.message

    if dt is None:
        if not args.cli and gui_available():
            dt, msg = pick_gui(files, msg or "")
            if dt is None:
                print("Cancelled.")
                sys.exit(0)
        else:
            if not args.cli:
                print("(GUI unavailable - on Linux: sudo apt install python3-tk. Using terminal.)")
            dt, msg = pick_cli(msg or "")

    if not msg:
        msg = input("Commit message: ").strip()
    if not msg:
        print("Commit message can't be empty.")
        sys.exit(1)

    iso = dt.astimezone().isoformat(timespec="seconds")
    print(f"Committing as: {iso}")

    env = os.environ.copy()
    env["GIT_AUTHOR_DATE"] = iso
    env["GIT_COMMITTER_DATE"] = iso

    print(git("commit", "-m", msg, env=env))
    print(git("log", "-1", "--format=Done: %h | author date: %ad | %s", "--date=iso"))
    print("\nPush manually when ready: git push")


if __name__ == "__main__":
    main()
