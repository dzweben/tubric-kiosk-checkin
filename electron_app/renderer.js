const screens = Array.from(document.querySelectorAll(".card"));
const state = {
  consent_contact: null,
  is_guardian: null,
  first_name: "",
  last_name: "",
  dob: "",
  email: "",
  phone: "",
  tubric_study_code: "",
};

function showScreen(id) {
  screens.forEach((s) => s.classList.add("hidden"));
  document.getElementById(id).classList.remove("hidden");
}

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
  return (
    date.getFullYear() === yyyy &&
    date.getMonth() === mm - 1 &&
    date.getDate() === dd
  );
}

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function normalizePhoneDigits(phone) {
  return phone.replace(/\D/g, "");
}

function setInfoSubtitle() {
  const sub = document.getElementById("info-subtitle");
  if (state.is_guardian === "guardian") {
    sub.textContent =
      "You indicated you are a parent/guardian. Please enter the participant's information below.";
  } else {
    sub.textContent = "Please enter your information below.";
  }
}

document.querySelectorAll("[data-next]").forEach((btn) => {
  btn.addEventListener("click", () => showScreen(btn.dataset.next));
});

const contactModal = document.getElementById("contact-modal");
const contactModalOk = document.getElementById("contact-modal-ok");

document.querySelectorAll("[data-consent]").forEach((btn) => {
  btn.addEventListener("click", () => {
    state.consent_contact = btn.dataset.consent;
    if (state.consent_contact === "Yes") {
      contactModal.classList.remove("hidden");
    } else {
      showScreen("screen-role");
    }
  });
});

contactModalOk.addEventListener("click", () => {
  contactModal.classList.add("hidden");
  showScreen("screen-role");
});

document.querySelectorAll("[data-role]").forEach((btn) => {
  btn.addEventListener("click", () => {
    state.is_guardian = btn.dataset.role;
    setInfoSubtitle();
    showScreen("screen-info");
  });
});

document.querySelectorAll("[data-back]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const current = screens.find((s) => !s.classList.contains("hidden"));
    if (!current) return;
    if (current.id === "screen-privacy") return showScreen("screen-welcome");
    if (current.id === "screen-consent") return showScreen("screen-privacy");
    if (current.id === "screen-role") return showScreen("screen-consent");
    if (current.id === "screen-info") return showScreen("screen-role");
    if (current.id === "screen-study") return showScreen("screen-info");
  });
});

document.querySelectorAll("[data-privacy]").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.dataset.privacy === "yes") {
      showScreen("screen-consent");
    } else {
      showScreen("screen-no-checkin");
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

document.getElementById("info-continue").addEventListener("click", () => {
  const error = document.getElementById("info-error");
  error.textContent = "";

  const first = document.getElementById("firstName").value.trim();
  const last = document.getElementById("lastName").value.trim();
  const dob = document.getElementById("dob").value.trim();
  const email = document.getElementById("email").value.trim();
  const phone = document.getElementById("phone").value.trim();

  if (!first || !last) {
    error.textContent = "Please enter the participant's first and last name.";
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

  state.first_name = first;
  state.last_name = last;
  state.dob = normalizeDob(dob);
  state.email = email;
  state.phone = phone;

  showScreen("screen-study");
});

document.getElementById("finish").addEventListener("click", async () => {
  const error = document.getElementById("study-error");
  error.textContent = "";
  const code = document.getElementById("studyCode").value.trim();
  if (!code) {
    error.textContent = "Please enter the TUBRIC Study Code.";
    return;
  }

  state.tubric_study_code = code;

  try {
    await window.tubric.submitCheckin(state);
    showScreen("screen-done");
  } catch (err) {
    error.textContent = "Submission failed. Please try again or alert staff.";
  }
});

document.getElementById("done").addEventListener("click", () => {
  window.location.reload();
});

document.getElementById("no-checkin-done").addEventListener("click", () => {
  window.location.reload();
});
