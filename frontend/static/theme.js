(function () {
  var STORAGE_KEY = "theme-overrides";

  function getOverrides() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    } catch (e) {
      return {};
    }
  }

  function setOverrides(overrides) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(overrides));
  }

  function isValidHex(value) {
    return /^#[0-9a-fA-F]{6}$/.test(value);
  }

  // Custom properties aren't resolved by getComputedStyle().getPropertyValue()
  // — it returns the raw "var(...)" token text. Route the value through a real
  // CSS property on a detached probe element to get the browser to resolve it.
  var probe = document.createElement("div");
  probe.style.cssText = "position:absolute;left:-9999px;top:-9999px;";
  document.body.appendChild(probe);

  function rgbToHex(rgb) {
    var m = rgb.match(/\d+/g);
    if (!m) return "#000000";
    return (
      "#" +
      m
        .slice(0, 3)
        .map(function (c) {
          return ("0" + parseInt(c, 10).toString(16)).slice(-2);
        })
        .join("")
    );
  }

  function resolvedHex(varName) {
    probe.style.setProperty("color", "var(" + varName + ")");
    return rgbToHex(getComputedStyle(probe).color);
  }

  document.querySelectorAll(".theme-row").forEach(function (row) {
    var varName = row.dataset.var;
    var swatch = row.querySelector(".theme-swatch");
    var hexInput = row.querySelector(".theme-hex");
    var clearBtn = row.querySelector(".theme-clear");

    function refresh() {
      var v = resolvedHex(varName);
      swatch.value = v;
      hexInput.value = v;
    }
    refresh();

    function apply(value) {
      document.documentElement.style.setProperty(varName, value);
      var overrides = getOverrides();
      overrides[varName] = value;
      setOverrides(overrides);
    }

    swatch.addEventListener("input", function () {
      hexInput.value = swatch.value;
      apply(swatch.value);
    });

    hexInput.addEventListener("change", function () {
      var v = hexInput.value.trim();
      if (v && v[0] !== "#") v = "#" + v;
      if (isValidHex(v)) {
        apply(v);
        swatch.value = v;
      } else {
        refresh();
      }
    });

    clearBtn.addEventListener("click", function () {
      document.documentElement.style.removeProperty(varName);
      var overrides = getOverrides();
      delete overrides[varName];
      setOverrides(overrides);
      refresh();
    });
  });

  var resetAll = document.getElementById("theme-reset-all");
  if (resetAll) {
    resetAll.addEventListener("click", function () {
      localStorage.removeItem(STORAGE_KEY);
      document.querySelectorAll(".theme-row").forEach(function (row) {
        document.documentElement.style.removeProperty(row.dataset.var);
        var v = resolvedHex(row.dataset.var);
        row.querySelector(".theme-swatch").value = v;
        row.querySelector(".theme-hex").value = v;
      });
    });
  }
})();
