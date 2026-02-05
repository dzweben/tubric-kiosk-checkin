import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import json
import os
import re
import uuid

APP_TITLE = "TUBRIC Check-In"
SITE_NAME = "TUBRIC"

# Professional Color Palette
COLORS = {
    'primary': '#2563eb',      # Blue
    'primary_dark': '#1e40af',
    'primary_light': '#dbeafe',
    'success': '#059669',
    'background': '#f8fafc',
    'card': '#ffffff',
    'text': '#1e293b',
    'text_light': '#64748b',
    'border': '#e2e8f0',
    'accent': '#0ea5e9',
}

DATA_FILE = os.path.join(os.path.dirname(__file__), "tubric_profiles.json")

## CODE COMPLETE!

# ----------------------------
# Helpers
# ----------------------------
def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def normalize_email(s: str) -> str:
    return (s or "").strip().lower()


def normalize_phone(s: str) -> str:
    """
    Accepts ONLY valid US phone numbers with exactly 10 digits
    (optionally entered with formatting characters).
    Returns 10-digit string or "" if invalid.
    """
    digits = re.sub(r"\D+", "", s or "")
    return digits if len(digits) == 10 else ""


def normalize_name(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_dob(s: str) -> str:
    """
    STRICT: Accepts ONLY MM-DD-YYYY entered by the user.
    Returns canonical YYYY-MM-DD for storage/matching, or "" if invalid.

    Example accepted: 03-14-2007
    """
    raw = (s or "").strip()
    if not raw:
        return ""

    try:
        dt = datetime.strptime(raw, "%m-%d-%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return ""


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"profiles": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Keep kiosk resilient
        return {"profiles": []}


def save_data(data):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, DATA_FILE)


def names_match(p, first_name: str, last_name: str) -> bool:
    return (
        normalize_name(p.get("first_name", "")) == normalize_name(first_name)
        and normalize_name(p.get("last_name", "")) == normalize_name(last_name)
    )


def find_profile(profiles, dob, first_name, last_name, email, phone):
    """
    DOB-first matching:
      - Step 1: candidates = exact DOB match (canonical YYYY-MM-DD)
      - Step 2: confirm identity using name/email/phone
      - Accept the best candidate only if confirmation score >= 2

    Scoring:
      +2 name match (first+last)
      +1 email match
      +1 phone match
    """
    email_n = normalize_email(email)
    phone_n = normalize_phone(phone)  # will be "" if invalid (we validate earlier)

    candidates = [p for p in profiles if p.get("dob") == dob]
    if not candidates:
        return None

    best = None
    best_score = -1

    for p in candidates:
        score = 0

        if names_match(p, first_name, last_name):
            score += 2

        pe = normalize_email(p.get("email", ""))
        if email_n and pe and email_n == pe:
            score += 1

        pp = normalize_phone(p.get("phone", ""))
        if phone_n and pp and phone_n == pp:
            score += 1

        if score > best_score:
            best_score = score
            best = p

    return best if best_score >= 2 else None


def new_guid():
    return str(uuid.uuid4())


# ----------------------------
# Custom Styled Widgets
# ----------------------------
class StyledButton(tk.Button):
    def __init__(self, parent, text, command, style="primary", **kwargs):
        if style == "primary":
            bg = COLORS['primary']
            fg = "black"
            active_bg = COLORS['primary_dark']
        elif style == "secondary":
            bg = COLORS['card']
            fg = COLORS['text']
            active_bg = COLORS['border']
        else:
            bg = COLORS['primary']
            fg = "black"
            active_bg = COLORS['primary_dark']
        
        super().__init__(
            parent,
            text=text,
            command=command,
            font=("Helvetica", 16, "bold"),
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=fg,
            relief="flat",
            padx=40,
            pady=16,
            cursor="hand2",
            borderwidth=2,
            highlightthickness=0,
            **kwargs
        )
        
        self.bind("<Enter>", lambda e: self.config(bg=active_bg))
        self.bind("<Leave>", lambda e: self.config(bg=bg))


class StyledEntry(tk.Entry):
    def __init__(self, parent, **kwargs):
        # Set defaults but allow them to be overridden
        defaults = {
            'font': ("Helvetica", 14),
            'bg': COLORS['card'],
            'fg': COLORS['text'],
            'insertbackground': COLORS['primary'],
            'relief': "solid",
            'borderwidth': 2,
            'highlightthickness': 1,
            'highlightcolor': COLORS['primary'],
            'highlightbackground': COLORS['border'],
        }
        # Merge defaults with kwargs (kwargs take precedence)
        defaults.update(kwargs)
        super().__init__(parent, **defaults)


# ----------------------------
# UI Frames
# ----------------------------
class BaseFrame(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLORS['background'])
        self.controller = controller
        
        # Create centered container with max width
        self.content = tk.Frame(self, bg=COLORS['background'])
        self.content.place(relx=0.5, rely=0.5, anchor="center")

    def on_show(self):
        pass


class WelcomeFrame(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        # Card container
        card = tk.Frame(self.content, bg=COLORS['card'], relief="flat", borderwidth=0)
        card.pack(padx=60, pady=40)
        
        # Add subtle shadow effect with border
        shadow = tk.Frame(card, bg=COLORS['border'], relief="flat")
        shadow.place(x=4, y=4, relwidth=1, relheight=1)
        card.lift()
        
        inner = tk.Frame(card, bg=COLORS['card'], padx=80, pady=60)
        inner.pack()

        # Header with icon
        header_frame = tk.Frame(inner, bg=COLORS['card'])
        header_frame.pack(pady=(0, 20))
        
        tk.Label(
            header_frame,
            text="👋",
            bg=COLORS['card'],
            font=("Helvetica", 48)
        ).pack()
        
        tk.Label(
            header_frame,
            text=f"Welcome to {SITE_NAME}",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=("Helvetica", 32, "bold"),
        ).pack(pady=(10, 0))

        # Subtitle
        tk.Label(
            inner,
            text="Please follow the prompts to check in for your visit today.",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=("Helvetica", 16),
            wraplength=600,
            justify="center"
        ).pack(pady=(0, 10))
        
        tk.Label(
            inner,
            text="If you are a parent/guardian completing this,\nplease enter the PARTICIPANT'S information.",
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            font=("Helvetica", 14),
            justify="center"
        ).pack(pady=(0, 30))

        StyledButton(inner, "Start Check-In", lambda: controller.show("ConsentFrame")).pack()


class ConsentFrame(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        card = tk.Frame(self.content, bg=COLORS['card'], padx=80, pady=60)
        card.pack(padx=60, pady=40)

        tk.Label(
            card,
            text="Contact Permission",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=("Helvetica", 28, "bold"),
        ).pack(pady=(0, 20))

        tk.Label(
            card,
            text="May we contact the participant/guardian in the future\nabout research opportunities?",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=("Helvetica", 16),
            justify="center"
        ).pack(pady=(0, 10))
        
        tk.Label(
            card,
            text='We will save your information regardless of your choice.',
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            font=("Helvetica", 14),
            justify="center"
        ).pack(pady=(0, 30))

        btn_row = tk.Frame(card, bg=COLORS['card'])
        btn_row.pack(pady=10)

        StyledButton(
            btn_row, 
            "Yes, you may contact me", 
            lambda: self._set_consent(True),
            width=22
        ).grid(row=0, column=0, padx=10)

        StyledButton(
            btn_row, 
            "No, do not contact me", 
            lambda: self._set_consent(False),
            style="secondary",
            width=22
        ).grid(row=0, column=1, padx=10)

        tk.Button(
            card, 
            text="← Back", 
            font=("Helvetica", 13),
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            relief="flat",
            cursor="hand2",
            command=lambda: controller.show("WelcomeFrame")
        ).pack(pady=(30, 0))

    def _set_consent(self, consent):
        self.controller.state["consent_contact"] = "Yes" if consent else "No"
        self.controller.show("RoleFrame")


class NoConsentFrame(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        card = tk.Frame(self.content, bg=COLORS['card'], padx=80, pady=60)
        card.pack(padx=60, pady=40)

        tk.Label(
            card,
            text="✓",
            bg=COLORS['card'],
            fg=COLORS['success'],
            font=("Helvetica", 56)
        ).pack(pady=(0, 20))

        tk.Label(
            card,
            text="All Set",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=("Helvetica", 28, "bold"),
        ).pack(pady=(0, 20))

        tk.Label(
            card,
            text="No problem — we won't save contact information.",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=("Helvetica", 16),
            justify="center"
        ).pack(pady=(0, 10))
        
        tk.Label(
            card,
            text="Please let the research assistant know\nyou have checked in.",
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            font=("Helvetica", 14),
            justify="center"
        ).pack(pady=(0, 30))

        StyledButton(card, "Finish", controller.reset).pack()


class RoleFrame(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        card = tk.Frame(self.content, bg=COLORS['card'], padx=80, pady=60)
        card.pack(padx=60, pady=40)

        tk.Label(
            card,
            text="Who is checking in?",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=("Helvetica", 28, "bold"),
        ).pack(pady=(0, 20))

        tk.Label(
            card,
            text="Please select who is filling out this form.",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=("Helvetica", 16),
            justify="center"
        ).pack(pady=(0, 10))
        
        tk.Label(
            card,
            text="If you are a parent/guardian, enter the\nPARTICIPANT'S information on the next screen.",
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            font=("Helvetica", 14),
            justify="center"
        ).pack(pady=(0, 30))

        StyledButton(card, "I am the participant", lambda: self._set_role("participant")).pack(pady=8)
        StyledButton(card, "I am a parent/guardian", lambda: self._set_role("guardian")).pack(pady=8)

        tk.Button(
            card, 
            text="← Back", 
            font=("Helvetica", 13),
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            relief="flat",
            cursor="hand2",
            command=lambda: controller.show("ConsentFrame")
        ).pack(pady=(30, 0))

    def _set_role(self, role):
        self.controller.state["is_guardian"] = role
        self.controller.show("ParticipantInfoFrame")


class ParticipantInfoFrame(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        card = tk.Frame(self.content, bg=COLORS['card'], padx=70, pady=50)
        card.pack(padx=60, pady=40)

        tk.Label(
            card,
            text="Participant Information",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=("Helvetica", 28, "bold"),
        ).pack(pady=(0, 15))

        self.sub = tk.Label(
            card,
            text="Please enter your information below.",
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            font=("Helvetica", 15),
            justify="center",
        )
        self.sub.pack(pady=(0, 25))

        # Form fields container
        form_frame = tk.Frame(card, bg=COLORS['card'])
        form_frame.pack(pady=10)

        def field(row, label_text, format_example=""):
            field_container = tk.Frame(form_frame, bg=COLORS['card'])
            field_container.grid(row=row, column=0, pady=10, sticky="ew")
            
            # Label with optional format example
            label_frame = tk.Frame(field_container, bg=COLORS['card'])
            label_frame.pack(anchor="w", pady=(0, 5))
            
            tk.Label(
                label_frame,
                text=label_text,
                bg=COLORS['card'],
                fg=COLORS['text'],
                font=("Helvetica", 14, "bold"),
                anchor="w"
            ).pack(side="left")
            
            if format_example:
                tk.Label(
                    label_frame,
                    text=f" ({format_example})",
                    bg=COLORS['card'],
                    fg=COLORS['text_light'],
                    font=("Helvetica", 13),
                    anchor="w"
                ).pack(side="left")

            ent = StyledEntry(field_container, width=45)
            ent.pack(fill="x", ipady=8)
            
            return ent

        self.first = field(0, "First Name")
        self.last  = field(1, "Last Name")
        self.dob   = field(2, "Date of Birth", "MM-DD-YYYY")
        self.email = field(3, "Email Address")
        self.phone = field(4, "Phone Number", "555-555-5555")
        
        # Auto-format DOB as user types
        def format_dob(event):
            content = self.dob.get().replace("-", "")  # Remove existing dashes
            # Only keep digits
            content = ''.join(c for c in content if c.isdigit())
            
            # Limit to 8 digits
            content = content[:8]
            
            # Add dashes at appropriate positions
            if len(content) >= 5:
                formatted = f"{content[:2]}-{content[2:4]}-{content[4:]}"
            elif len(content) >= 3:
                formatted = f"{content[:2]}-{content[2:]}"
            else:
                formatted = content
            
            # Update the field
            self.dob.delete(0, tk.END)
            self.dob.insert(0, formatted)
        
        self.dob.bind("<KeyRelease>", format_dob)
        
        # Auto-format phone as user types
        def format_phone(event):
            content = self.phone.get().replace("-", "")  # Remove existing dashes
            # Only keep digits
            content = ''.join(c for c in content if c.isdigit())
            
            # Limit to 10 digits
            content = content[:10]
            
            # Add dashes at appropriate positions (XXX-XXX-XXXX)
            if len(content) >= 7:
                formatted = f"{content[:3]}-{content[3:6]}-{content[6:]}"
            elif len(content) >= 4:
                formatted = f"{content[:3]}-{content[3:]}"
            else:
                formatted = content
            
            # Update the field
            self.phone.delete(0, tk.END)
            self.phone.insert(0, formatted)
        
        self.phone.bind("<KeyRelease>", format_phone)

        self.phone.bind("<Return>", lambda e: self._continue())

        # Note
        note_frame = tk.Frame(card, bg=COLORS['primary_light'], padx=15, pady=12)
        note_frame.pack(pady=(20, 20), fill="x")
        
        tk.Label(
            note_frame,
            text="📌 Please provide both email and phone number.",
            bg=COLORS['primary_light'],
            fg=COLORS['primary_dark'],
            font=("Helvetica", 12),
            justify="center"
        ).pack()

        # Buttons
        button_frame = tk.Frame(card, bg=COLORS['card'])
        button_frame.pack(pady=(10, 0))

        StyledButton(button_frame, "Continue", self._continue).pack(pady=5)

        tk.Button(
            button_frame,
            text="← Back",
            font=("Helvetica", 13),
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            relief="flat",
            cursor="hand2",
            command=lambda: controller.show("RoleFrame"),
        ).pack(pady=10)

    def on_show(self):
        role = self.controller.state.get("is_guardian")
        if role == "guardian":
            self.sub.config(
                text="You indicated you are a parent/guardian.\nPlease enter the PARTICIPANT'S information below."
            )
        else:
            self.sub.config(text="Please enter your information below.")

        for ent in (self.first, self.last, self.dob, self.email, self.phone):
            ent.delete(0, tk.END)
        self.first.focus_set()

    def _continue(self):
        first = self.first.get().strip()
        last = self.last.get().strip()
        dob_raw = self.dob.get().strip()
        email = self.email.get().strip()
        phone = self.phone.get().strip()

        if not first or not last:
            messagebox.showinfo("Missing Information", "Please enter the participant's first and last name.")
            return

        dob = normalize_dob(dob_raw)
        if not dob:
            messagebox.showinfo(
                "Date of Birth Required",
                "Please enter date of birth as MM-DD-YYYY\n(example: 03-14-2007)",
            )
            return

        if not email:
            messagebox.showinfo("Email Required", "Please enter an email address.")
            return
            
        if not phone:
            messagebox.showinfo("Phone Required", "Please enter a phone number.")
            return

        if not normalize_phone(phone):
            messagebox.showinfo(
                "Invalid Phone Number",
                "Please enter a valid 10-digit phone number\n(e.g., 215-555-1234)",
            )
            return

        self.controller.state.update(
            {
                "first_name": first,
                "last_name": last,
                "dob": dob,
                "email": email,
                "phone": phone,
            }
        )

        self.controller.show("StudyCodeFrame")


class StudyCodeFrame(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        card = tk.Frame(self.content, bg=COLORS['card'], padx=80, pady=60)
        card.pack(padx=60, pady=40)

        tk.Label(
            card,
            text="Today's Visit",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=("Helvetica", 28, "bold"),
        ).pack(pady=(0, 15))

        tk.Label(
            card,
            text="TUBRIC Study Code",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=("Helvetica", 16, "bold"),
        ).pack(pady=(0, 10))
        
        tk.Label(
            card,
            text="Please have the research assistant\nfill in this information.",
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            font=("Helvetica", 14),
            justify="center"
        ).pack(pady=(0, 25))

        self.code = StyledEntry(card, width=35, justify="center", font=("Helvetica", 18))
        self.code.pack(pady=15, ipady=10)
        self.code.bind("<Return>", lambda e: self._finish())

        StyledButton(card, "Finish Check-In", self._finish).pack(pady=(10, 0))

        tk.Button(
            card,
            text="← Back",
            font=("Helvetica", 13),
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            relief="flat",
            cursor="hand2",
            command=lambda: controller.show("ParticipantInfoFrame"),
        ).pack(pady=(25, 0))

    def on_show(self):
        self.code.delete(0, tk.END)
        self.code.focus_set()

    def _finish(self):
        code = self.code.get().strip()
        if not code:
            messagebox.showinfo(
                "Study Code Required",
                "Please enter the TUBRIC Study Code\n(ask the research assistant)",
            )
            return

        self.controller.state["tubric_study_code"] = code

        self.controller.submit_silently()
        self.controller.show("DoneFrame")


class DoneFrame(BaseFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        card = tk.Frame(self.content, bg=COLORS['card'], padx=80, pady=60)
        card.pack(padx=60, pady=40)

        tk.Label(
            card,
            text="✓",
            bg=COLORS['card'],
            fg=COLORS['success'],
            font=("Helvetica", 56)
        ).pack(pady=(0, 20))

        tk.Label(
            card,
            text="You're All Set!",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=("Helvetica", 28, "bold"),
        ).pack(pady=(0, 20))

        tk.Label(
            card,
            text="Thank you for checking in.",
            bg=COLORS['card'],
            fg=COLORS['text'],
            font=("Helvetica", 16),
            justify="center"
        ).pack(pady=(0, 10))
        
        tk.Label(
            card,
            text="Please let the research assistant know\nyou have completed the check-in process.",
            bg=COLORS['card'],
            fg=COLORS['text_light'],
            font=("Helvetica", 14),
            justify="center"
        ).pack(pady=(0, 30))

        StyledButton(card, "Done", controller.reset).pack()


# ----------------------------
# Main App
# ----------------------------
class KioskApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.configure(bg=COLORS['background'])

        self.attributes("-fullscreen", True)
        self.bind("<Escape>", lambda e: self._confirm_exit())

        self.data = load_data()

        self.state = {
            "date": today_str(),
            "is_guardian": None,
            "consent_contact": None,
            "first_name": "",
            "last_name": "",
            "dob": "",
            "email": "",
            "phone": "",
            "tubric_study_code": "",
        }

        self.container = tk.Frame(self, bg=COLORS['background'])
        self.container.pack(fill="both", expand=True)

        self.frames = {}
        for F in (
            WelcomeFrame,
            ConsentFrame,
            RoleFrame,
            ParticipantInfoFrame,
            StudyCodeFrame,
            DoneFrame,
            NoConsentFrame,
        ):
            frame = F(parent=self.container, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.show("WelcomeFrame")

    def show(self, frame_name: str):
        frame = self.frames[frame_name]
        frame.tkraise()
        frame.on_show()

    def _confirm_exit(self):
        if messagebox.askyesno("Exit Kiosk", "Are you sure you want to exit the kiosk?"):
            self.destroy()

    def reset(self):
        self.state.update(
            {
                "date": today_str(),
                "is_guardian": None,
                "consent_contact": None,
                "first_name": "",
                "last_name": "",
                "dob": "",
                "email": "",
                "phone": "",
                "tubric_study_code": "",
            }
        )
        self.show("WelcomeFrame")

    def submit_silently(self):
        """
        Silent save + DOB-first matching. Participant never sees matching details.
        """
        s = self.state

        dob = s["dob"]
        email = s["email"]
        phone = s["phone"]

        existing = find_profile(
            self.data["profiles"],
            dob=dob,
            first_name=s["first_name"],
            last_name=s["last_name"],
            email=email,
            phone=phone,
        )

        visit = {
            "visit_datetime": now_iso(),
            "tubric_study_code": s["tubric_study_code"],
            "consent_contact": s["consent_contact"],
            "entered_by": s["is_guardian"],
        }

        if existing:
            if email and not existing.get("email"):
                existing["email"] = normalize_email(email)
            if phone and not existing.get("phone"):
                existing["phone"] = normalize_phone(phone)

            existing.setdefault("visits", []).append(visit)
            guid = existing["guid"]
            action = "matched_existing"
        else:
            guid = new_guid()
            profile = {
                "guid": guid,
                "first_name": s["first_name"].strip(),
                "last_name": s["last_name"].strip(),
                "dob": dob,
                "email": normalize_email(email),
                "phone": normalize_phone(phone),
                "consent_contact": s["consent_contact"],
                "created_at": now_iso(),
                "visits": [visit],
            }
            self.data["profiles"].append(profile)
            action = "created_new"

        save_data(self.data)

        # DEV log (remove later)
        print("\n--- CHECK-IN SAVED ---")
        print("Action:", action)
        print("GUID:", guid)
        print("State:", dict(self.state))
        print("--- END ---\n")

        return guid, action


if __name__ == "__main__":
    app = KioskApp()
    app.mainloop()