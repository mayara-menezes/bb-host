/* BB Host site behavior (replica). Plain JavaScript, no framework. */
(function () {
  "use strict";

  var WHATSAPP = "https://wa.me/5511916788282";
  var money = function (v) {
    return v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  /* ---------- Light/dark theme (Tailwind "dark" class on <html>) ---------- */
  var html = document.documentElement;
  var toggle = document.getElementById("theme_toggle");
  function paintToggle() {
    if (!toggle) { return; }
    toggle.querySelector("i").className = html.classList.contains("dark") ? "fa fa-sun-o" : "fa fa-moon-o";
  }
  if (toggle) {
    toggle.addEventListener("click", function () {
      var dark = html.classList.toggle("dark");
      try { localStorage.setItem("bb-theme", dark ? "dark" : "light"); } catch (e) { /* no storage */ }
      paintToggle();
    });
    paintToggle();
  }

  /* ---------- Copy the coupon from the promo banner ---------- */
  var promo = document.getElementById("promo_code");
  if (promo) {
    promo.addEventListener("click", function () {
      var ok = function () {
        promo.setAttribute("data-copied", "");
        setTimeout(function () { promo.removeAttribute("data-copied"); }, 1600);
      };
      if (navigator.clipboard) {
        navigator.clipboard.writeText(promo.getAttribute("data-code")).then(ok, function () {});
      }
    });
  }

  /* ---------- Chat links: open WhatsApp with a ready-made message ---------- */
  document.addEventListener("click", function (ev) {
    var a = ev.target.closest("[data-bb-chat]");
    if (!a) { return; }
    ev.preventDefault();
    window.open(WHATSAPP + "?text=" + encodeURIComponent(a.getAttribute("data-bb-chat")), "_blank", "noopener");
  });

  /* ---------- VPS builder ---------- */
  var vps = document.getElementById("vps_build");
  if (vps) {
    var unitPrice = {
      cpu: parseFloat(vps.dataset.pcpu) || 0,
      ram: parseFloat(vps.dataset.pram) || 0,
      disk: parseFloat(vps.dataset.pdisk) || 0
    };
    var resources = ["cpu", "ram", "disk"];
    var osSelect = document.getElementById("vps_os");
    var recalcVps = function () {
      var total = 0;
      resources.forEach(function (r) {
        var v = parseInt(document.getElementById(r).value, 10) || 0;
        document.getElementById(r + "_val").textContent = v;
        total += v * unitPrice[r];
      });
      if (osSelect && osSelect.selectedOptions[0]) {
        total += parseFloat(osSelect.selectedOptions[0].dataset.price) || 0;
      }
      document.getElementById("vps_price").textContent = money(total);
    };
    vps.addEventListener("input", recalcVps);
    vps.addEventListener("change", recalcVps);
    recalcVps();
  }

  /* ---------- Colocation estimate ---------- */
  var box = document.getElementById("colo_rows");
  var add = document.getElementById("colo_add");
  if (box && add) {
    var perUnit = parseFloat(box.dataset.ppu) || 0;
    var perWatt = parseFloat(box.dataset.ppw) || 0;
    var out = document.getElementById("colo_estimate");
    var recalcColo = function () {
      var total = 0;
      box.querySelectorAll(".colo-row").forEach(function (row) {
        var u = parseInt(row.querySelector(".colo-size").value, 10) || 0;
        var w = parseFloat(row.querySelector(".colo-watts").value) || 0;
        total += u * perUnit + w * perWatt;
      });
      out.textContent = money(total);
    };
    box.addEventListener("input", recalcColo);
    box.addEventListener("change", recalcColo);
    box.addEventListener("click", function (ev) {
      var rm = ev.target.closest(".colo-remove");
      if (rm && box.querySelectorAll(".colo-row").length > 1) {
        rm.closest(".colo-row").remove();
        recalcColo();
      }
    });
    add.addEventListener("click", function () {
      var clone = box.querySelector(".colo-row").cloneNode(true);
      clone.querySelectorAll("input").forEach(function (i) { i.value = ""; });
      clone.querySelector(".colo-watts").value = box.dataset.watts || "450";
      clone.querySelector("select").selectedIndex = 0;
      box.appendChild(clone);
      recalcColo();
    });
    recalcColo();
  }

  /* ---------- Mitigation: clean traffic + delivery mode ---------- */
  var range = document.getElementById("clean_range");
  if (range) {
    var tiers = (range.dataset.tiers || "").split("|");
    var mode = document.getElementById("mit_mode");
    var cta = document.getElementById("mit_cta");
    var updateMitigation = function () {
      var bandwidth = tiers[parseInt(range.value, 10)] || tiers[0];
      var label = bandwidth + " clean · " + mode.value;
      document.getElementById("clean_val").textContent = bandwidth;
      document.getElementById("mit_label").textContent = label;
      cta.href = cta.dataset.base + "?" + new URLSearchParams({ bandwidth: bandwidth, mode: mode.value }).toString();
      document.getElementById("mit_wa").href = WHATSAPP + "?text=" + encodeURIComponent(
        "Hi! I'd like to protect my business with BB Host Anti-DDoS: " + label + ".");
    };
    range.addEventListener("input", updateMitigation);
    mode.addEventListener("change", updateMitigation);
    updateMitigation();
  }

  /* ---------- Dedicated server: total with options + conditional OS fields ---------- */
  var ded = document.getElementById("ded_cfg");
  if (ded) {
    var base = parseFloat(ded.dataset.base) || 0;
    var pricedSelects = ded.querySelectorAll("select[data-priced]");
    var dedOs = ded.querySelector("select[name=operating_system]");
    var updateDedicated = function () {
      var total = base;
      pricedSelects.forEach(function (s) {
        var o = s.selectedOptions[0];
        if (o) { total += parseFloat(o.dataset.price) || 0; }
      });
      document.getElementById("ded_total").textContent = money(total);
      var needs = dedOs && dedOs.selectedOptions[0] ? dedOs.selectedOptions[0].dataset.needs : "";
      ded.querySelectorAll("[data-when-os]").forEach(function (el) {
        el.hidden = el.dataset.whenOs !== needs;
      });
    };
    ded.addEventListener("change", updateDedicated);
    updateDedicated();
  }

  /* ---------- Sign-up: company name only for CNPJ ---------- */
  var docType = document.querySelector("select[name=document_type]");
  var cnpjOnly = document.getElementById("company_field");
  if (docType && cnpjOnly) {
    var updateDocType = function () { cnpjOnly.hidden = docType.value !== "CNPJ"; };
    docType.addEventListener("change", updateDocType);
    updateDocType();
  }

  /* ---------- Dedicated catalog: re-sort when the select changes ---------- */
  var sortSelect = document.getElementById("sort_select");
  if (sortSelect) {
    sortSelect.addEventListener("change", function () { sortSelect.form.submit(); });
  }
})();
