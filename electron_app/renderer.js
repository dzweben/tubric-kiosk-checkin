const screens = Array.from(document.querySelectorAll(".card"));
const state = {
  consent_contact: null,
  is_guardian: "participant",
  first_name: "",
  last_name: "",
  dob: "",
  email: "",
  phone: "",
  tubric_study_code: "",
  newsletter_email: "",
  newsletter_phone: "",
  newsletter_pref: "",
  consent_name: "",
  consent_date: "",
  consent_signature: "",
};
let lookup = { matched: false, guid: "", consented: false };

function showScreen(id) {
  screens.forEach((s) => s.classList.add("hidden"));
  document.getElementById(id).classList.remove("hidden");
}

function currentScreen() {
  const current = screens.find((s) => !s.classList.contains("hidden"));
  return current ? current.id : "";
}

// ---------- formatting / validation ----------
function formatDOB(value) {
  const digits = value.replace(/\D/g, "").slice(0, 8);
  if (digits.length >= 5) return `${digits.slice(0, 2)}-${digits.slice(2, 4)}-${digits.slice(4)}`;
  if (digits.length >= 3) return `${digits.slice(0, 2)}-${digits.slice(2)}`;
  return digits;
}

function formatPhone(value) {
  const digits = value.replace(/\D/g, "").slice(0, 10);
  if (digits.length >= 7) return `${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6)}`;
  if (digits.length >= 4) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
  return digits;
}

function normalizeDob(dob) {
  const parts = dob.split("-");
  if (parts.length !== 3) return "";
  return `${parts[2]}-${parts[0]}-${parts[1]}`;
}

function isValidDob(dob) {
  if (!/^\d{2}-\d{2}-\d{4}$/.test(dob)) return false;
  const [mm, dd, yyyy] = dob.split("-").map((v) => parseInt(v, 10));
  if (mm < 1 || mm > 12) return false;
  if (dd < 1 || dd > 31) return false;
  if (yyyy < 1900 || yyyy > 2100) return false;
  const date = new Date(yyyy, mm - 1, dd);
  return date.getFullYear() === yyyy && date.getMonth() === mm - 1 && date.getDate() === dd;
}

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function normalizePhoneDigits(phone) {
  return phone.replace(/\D/g, "");
}

function todayParts() {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const yyyy = d.getFullYear();
  return { display: `${mm}-${dd}-${yyyy}`, iso: `${yyyy}-${mm}-${dd}` };
}

function ageOn(isoDob, on = new Date()) {
  const [y, m, d] = isoDob.split("-").map((v) => parseInt(v, 10));
  let age = on.getFullYear() - y;
  if (on.getMonth() + 1 < m || (on.getMonth() + 1 === m && on.getDate() < d)) age -= 1;
  return age;
}

// ---------- sign-in screen ----------
function setInfoSubtitle() {
  const sub = document.getElementById("info-subtitle");
  const guardian = state.is_guardian === "guardian";
  document.getElementById("guardian-banner").classList.toggle("hidden", !guardian);
  document.querySelectorAll("#info-form .lbl").forEach((el) => {
    el.textContent = guardian ? el.dataset.guardian : el.dataset.participant;
  });
  if (guardian) {
    sub.textContent =
      "You are signing in as the parent/guardian. Enter your own information exactly as on previous visits.";
  } else {
    sub.textContent =
      "Please enter your full legal name and date of birth exactly as you did on previous visits. Participants must be 18 or older to sign in themselves.";
  }
}

document.querySelectorAll("[data-next]").forEach((btn) => {
  btn.addEventListener("click", () => showScreen(btn.dataset.next));
});

document.querySelectorAll(".role-toggle [data-role]").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".role-toggle [data-role]").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.is_guardian = btn.dataset.role;
    setInfoSubtitle();
  });
});

document.querySelectorAll("[data-back]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const current = currentScreen();
    if (current === "screen-signin") return showScreen("screen-welcome");
    if (current === "screen-consent") return showScreen("screen-signin");
    if (current === "screen-study") {
      // Only revisit the consent form if it was actually shown this session.
      return showScreen(lookup.consented ? "screen-signin" : "screen-consent");
    }
  });
});

const dobInput = document.getElementById("dob");
dobInput.addEventListener("input", (e) => {
  e.target.value = formatDOB(e.target.value);
});

const phoneInput = document.getElementById("phone");
phoneInput.addEventListener("input", (e) => {
  e.target.value = formatPhone(e.target.value);
});

const infoContinue = document.getElementById("info-continue");
infoContinue.addEventListener("click", async () => {
  const error = document.getElementById("info-error");
  error.textContent = "";

  const first = document.getElementById("firstName").value.trim();
  const last = document.getElementById("lastName").value.trim();
  const dob = document.getElementById("dob").value.trim();
  const email = document.getElementById("email").value.trim();
  const phone = document.getElementById("phone").value.trim();

  if (!first || !last) {
    error.textContent = "Please enter the participant's full legal first and last name.";
    return;
  }
  if (!isValidDob(dob)) {
    error.textContent = "Please enter date of birth as MM-DD-YYYY.";
    return;
  }
  if (!email || !isValidEmail(email)) {
    error.textContent = "Please enter a valid email address.";
    return;
  }
  if (!phone) {
    error.textContent = "Please enter a phone number.";
    return;
  }
  if (normalizePhoneDigits(phone).length !== 10) {
    error.textContent = "Please enter a valid 10-digit phone number.";
    return;
  }

  const age = ageOn(normalizeDob(dob));
  if (state.is_guardian === "guardian" && age < 18) {
    error.textContent =
      "A parent/guardian must be 18 or older. Enter YOUR OWN date of birth, not the child's.";
    return;
  }
  if (state.is_guardian !== "guardian" && age < 18) {
    // Under-18 participants cannot sign in themselves. Nothing is saved.
    showScreen("screen-under18");
    return;
  }

  state.first_name = first;
  state.last_name = last;
  state.dob = normalizeDob(dob);
  state.email = email;
  state.phone = phone;

  // Ask the backend whether this person already exists and has signed consent.
  infoContinue.disabled = true;
  infoContinue.textContent = "Checking…";
  try {
    lookup = await window.tubric.lookup(state);
  } catch (err) {
    // If the lookup fails, fall back to showing the consent form: re-consenting
    // is harmless, skipping consent for a new person is not.
    lookup = { matched: false, guid: "", consented: false };
  } finally {
    infoContinue.disabled = false;
    infoContinue.textContent = "Continue";
  }

  if (lookup.matched && lookup.consented) {
    state.consent_contact = "Yes";
    showScreen("screen-study");
    return;
  }

  prepareConsentScreen();
  showScreen("screen-consent");
});

document.getElementById("under18-guardian").addEventListener("click", () => {
  // Switch to guardian mode and clear the child's details so the parent
  // enters their own.
  document.querySelectorAll(".role-toggle [data-role]").forEach((b) => {
    b.classList.toggle("active", b.dataset.role === "guardian");
  });
  state.is_guardian = "guardian";
  ["firstName", "lastName", "dob", "email", "phone"].forEach((id) => (document.getElementById(id).value = ""));
  document.getElementById("info-error").textContent = "";
  setInfoSubtitle();
  showScreen("screen-signin");
  document.getElementById("firstName").focus();
});

document.getElementById("under18-stop").addEventListener("click", () => {
  showScreen("screen-no-checkin");
});

// ---------- consent screen ----------
const consentName = document.getElementById("consentName");
const consentDate = document.getElementById("consentDate");
const consentNameLabel = document.getElementById("consent-name-label");
const consentError = document.getElementById("consent-error");

function prepareConsentScreen() {
  consentError.textContent = "";
  const today = todayParts();
  consentDate.value = today.display;
  state.consent_date = today.iso;
  consentNameLabel.textContent =
    state.is_guardian === "guardian" ? "Parent/guardian printed name" : "Printed name";
  consentName.value = `${state.first_name} ${state.last_name}`.trim();
  signature.clear();
  document.getElementById("consent-doc").scrollTop = 0;
}

// Simple signature pad on a canvas. Tracks whether any ink was laid down.
const signature = (() => {
  const canvas = document.getElementById("signature-pad");
  const ctx = canvas.getContext("2d");
  let drawing = false;
  let hasInk = false;
  let last = null;

  function resize() {
    const ratio = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(1, Math.floor(rect.width));
    const height = Math.max(100, Math.floor(rect.height) || 180);
    const snapshot = hasInk ? canvas.toDataURL("image/png") : null;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    canvas.style.height = `${height}px`;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = "#0b1220";
    if (snapshot) {
      const img = new Image();
      img.onload = () => ctx.drawImage(img, 0, 0, width, height);
      img.src = snapshot;
    }
  }

  function pos(evt) {
    const rect = canvas.getBoundingClientRect();
    return { x: evt.clientX - rect.left, y: evt.clientY - rect.top };
  }

  canvas.addEventListener("pointerdown", (evt) => {
    evt.preventDefault();
    canvas.setPointerCapture(evt.pointerId);
    drawing = true;
    last = pos(evt);
    ctx.beginPath();
    ctx.moveTo(last.x, last.y);
    ctx.lineTo(last.x + 0.1, last.y + 0.1);
    ctx.stroke();
    hasInk = true;
  });
  canvas.addEventListener("pointermove", (evt) => {
    if (!drawing) return;
    evt.preventDefault();
    const p = pos(evt);
    ctx.beginPath();
    ctx.moveTo(last.x, last.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    last = p;
  });
  const stop = () => {
    drawing = false;
    last = null;
  };
  canvas.addEventListener("pointerup", stop);
  canvas.addEventListener("pointercancel", stop);
  canvas.addEventListener("pointerleave", stop);

  window.addEventListener("resize", resize);
  // Size once the consent screen is visible (hidden canvases have no width).
  const observer = new MutationObserver(() => {
    if (!document.getElementById("screen-consent").classList.contains("hidden")) resize();
  });
  observer.observe(document.getElementById("screen-consent"), { attributes: true, attributeFilter: ["class"] });

  return {
    clear() {
      hasInk = false;
      resize();
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    },
    isEmpty() {
      return !hasInk;
    },
    toDataURL() {
      return canvas.toDataURL("image/png");
    },
  };
})();

document.getElementById("signature-clear").addEventListener("click", () => signature.clear());

document.getElementById("consent-accept").addEventListener("click", () => {
  consentError.textContent = "";
  const name = consentName.value.trim();
  if (!name) {
    consentError.textContent = "Please print your full name.";
    return;
  }
  if (signature.isEmpty()) {
    consentError.textContent = "Please sign in the box above.";
    return;
  }
  state.consent_name = name;
  state.consent_signature = signature.toDataURL();
  state.consent_contact = "Yes";
  showScreen("screen-study");
});

document.getElementById("consent-decline").addEventListener("click", () => {
  // Nothing is saved: the backend is never called on this path.
  showScreen("screen-no-checkin");
});

// ---------- study code / finish ----------
const finishBtn = document.getElementById("finish");
finishBtn.addEventListener("click", async () => {
  const error = document.getElementById("study-error");
  error.textContent = "";
  const code = document.getElementById("studyCode").value.trim();
  if (!code) {
    error.textContent = "Please enter the Study Code.";
    return;
  }

  state.tubric_study_code = code;
  finishBtn.disabled = true;
  finishBtn.textContent = "Saving…";
  try {
    await window.tubric.submitCheckin(state);
    showScreen("screen-done");
  } catch (err) {
    error.textContent = "Submission failed. Please try again or alert staff.";
  } finally {
    finishBtn.disabled = false;
    finishBtn.textContent = "Finish Check-In";
  }
});

document.getElementById("done").addEventListener("click", () => {
  window.location.reload();
});

document.getElementById("no-checkin-done").addEventListener("click", () => {
  window.location.reload();
});

setInfoSubtitle();
