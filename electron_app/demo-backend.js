// Browser-only stand-in for the Python backend, used by the GitHub Pages demo.
// Nothing leaves the browser: people are kept in localStorage so a returning
// demo participant is recognized and skips the consent form.
(function () {
  const KEY = "tpp-demo-people";

  function load() {
    try {
      return JSON.parse(localStorage.getItem(KEY) || "[]");
    } catch (e) {
      return [];
    }
  }
  function save(people) {
    try {
      localStorage.setItem(KEY, JSON.stringify(people));
    } catch (e) {}
  }
  function norm(s) {
    return String(s || "")
      .normalize("NFKD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "");
  }
  function digits(s) {
    return String(s || "").replace(/\D/g, "");
  }
  // Same spirit as the real matcher: DOB 2, first 1, last 1, email 1, phone 1,
  // first-name mismatch -2, threshold 4.
  function score(p, s) {
    let n = 0;
    if (p.dob && p.dob === s.dob) n += 2;
    const f = norm(s.first_name), l = norm(s.last_name);
    if (f && p.first) n += p.first === f ? 1 : -2;
    if (l && p.last === l) n += 1;
    if (s.email && p.emails.includes(norm(s.email))) n += 1;
    if (s.phone && p.phones.includes(digits(s.phone))) n += 1;
    return n;
  }
  function find(s) {
    let best = null, bestScore = 3;
    for (const p of load()) {
      const sc = score(p, s);
      if (sc > bestScore) { bestScore = sc; best = p; }
    }
    return best;
  }
  function uuid() {
    return "demo-" + Math.random().toString(16).slice(2, 10);
  }

  window.tubric = {
    async lookup(s) {
      await new Promise((r) => setTimeout(r, 400));
      const p = find(s);
      return p ? { matched: true, guid: p.guid, consented: !!p.consented } : { matched: false, guid: "", consented: false };
    },
    async submitCheckin(s) {
      await new Promise((r) => setTimeout(r, 500));
      const people = load();
      let p = find(s);
      if (!p) {
        p = { guid: uuid(), first: norm(s.first_name), last: norm(s.last_name), dob: s.dob, emails: [], phones: [], consented: false, visits: [] };
        people.push(p);
      } else {
        p = people.find((x) => x.guid === p.guid);
      }
      if (s.email && !p.emails.includes(norm(s.email))) p.emails.push(norm(s.email));
      if (s.phone && !p.phones.includes(digits(s.phone))) p.phones.push(digits(s.phone));
      if (s.consent_name && s.consent_signature) p.consented = true;
      p.visits.push({ at: new Date().toISOString(), code: s.tubric_study_code, by: s.is_guardian });
      save(people);
      return { guid: p.guid, action: p.visits.length > 1 ? "matched_existing" : "created_new" };
    },
  };

  // Demo badge with a reset control.
  const badge = document.createElement("div");
  badge.id = "demo-badge";
  badge.innerHTML = 'DEMO &middot; nothing is sent anywhere <button type="button" id="demo-reset">Reset demo data</button>';
  document.body.appendChild(badge);
  document.getElementById("demo-reset").addEventListener("click", () => {
    localStorage.removeItem(KEY);
    window.location.reload();
  });
})();
