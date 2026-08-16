(function () {
  if (window.__previewPlayerInitialized) return;
  window.__previewPlayerInitialized = true;

  var PLAY_ICON = "▶";
  var PAUSE_ICON = "⏸";
  var TOGGLE_PAUSE_ICON = "❚❚";
  var VOLUME_STORAGE_KEY = "previewVolume";
  var SESSION_KEY = "previewSession";

  var audio = new Audio();
  audio.volume = parseFloat(localStorage.getItem(VOLUME_STORAGE_KEY) || "1");
  document.getElementById("preview-bar-volume").value = audio.volume;
  var activeBtn = null;

  var channel = "BroadcastChannel" in window ? new BroadcastChannel("preview-audio") : null;
  if (channel) {
    channel.onmessage = function (e) {
      if (e.data === "stop") stop();
    };
  }

  function el(id) {
    return document.getElementById(id);
  }

  function reset(btn) {
    btn.classList.remove("playing");
    var icon = btn.querySelector(".preview-icon");
    if (icon) icon.textContent = PLAY_ICON;
  }

  function showBar(track, artist) {
    el("preview-bar-track").textContent = track;
    el("preview-bar-artist").textContent = artist;
    el("preview-bar").hidden = false;
    document.body.classList.add("preview-bar-visible");
  }

  function hideBar() {
    el("preview-bar").hidden = true;
    document.body.classList.remove("preview-bar-visible");
  }

  function saveSession() {
    if (!audio.src) return;
    var track = activeBtn ? activeBtn.dataset.previewTrack : el("preview-bar-track").textContent;
    var artist = activeBtn
      ? activeBtn.dataset.previewArtist
      : el("preview-bar-artist").textContent;
    if (!track) return;
    sessionStorage.setItem(
      SESSION_KEY,
      JSON.stringify({ track: track, artist: artist, time: audio.currentTime || 0 })
    );
  }

  function stop() {
    audio.pause();
    audio.removeAttribute("src");
    document.querySelectorAll(".preview-btn.playing").forEach(reset);
    activeBtn = null;
    hideBar();
    sessionStorage.removeItem(SESSION_KEY);
  }

  function findMatchingButton(track, artist) {
    var btns = document.querySelectorAll(".preview-btn[data-preview-track]");
    for (var i = 0; i < btns.length; i++) {
      if (btns[i].dataset.previewTrack === track && btns[i].dataset.previewArtist === artist) {
        return btns[i];
      }
    }
    return null;
  }

  function relinkActiveBtn() {
    if (activeBtn && !activeBtn.isConnected) {
      var playing = !audio.paused && !audio.ended;
      var match = findMatchingButton(activeBtn.dataset.previewTrack, activeBtn.dataset.previewArtist);
      activeBtn = match;
      if (activeBtn) {
        activeBtn.classList.toggle("playing", playing);
        var icon = activeBtn.querySelector(".preview-icon");
        if (icon) icon.textContent = playing ? PAUSE_ICON : PLAY_ICON;
      }
    }
    document.querySelectorAll(".preview-btn.playing").forEach(function (btn) {
      if (btn !== activeBtn) reset(btn);
    });
    if (audio.src && activeBtn) {
      showBar(activeBtn.dataset.previewTrack, activeBtn.dataset.previewArtist);
    }
    el("preview-bar-volume").value = audio.volume;
  }

  function play(track, artist) {
    document.querySelectorAll(".preview-btn.playing").forEach(reset);
    activeBtn = findMatchingButton(track, artist);
    showBar(track, artist);
    if (channel) channel.postMessage("stop");
    audio.src = "/preview?track=" + encodeURIComponent(track) + "&artist=" + encodeURIComponent(artist);
    audio.play().catch(function () {
      if (el("preview-bar-track").textContent === track) stop();
    });
  }

  function restoreSession() {
    var raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return;
    var session;
    try {
      session = JSON.parse(raw);
    } catch (e) {
      return;
    }
    if (!session || !session.track || !session.artist) return;

    activeBtn = findMatchingButton(session.track, session.artist);
    showBar(session.track, session.artist);
    audio.src =
      "/preview?track=" + encodeURIComponent(session.track) + "&artist=" + encodeURIComponent(session.artist);
    var resumeAt = session.time || 0;
    audio.addEventListener("loadedmetadata", function onLoaded() {
      audio.removeEventListener("loadedmetadata", onLoaded);
      audio.currentTime = resumeAt;
      if (audio.duration) el("preview-bar-fill").style.width = (resumeAt / audio.duration) * 100 + "%";
    });
    syncPlayingState();
  }

  function syncPlayingState() {
    var playing = !audio.paused && !audio.ended;
    if (activeBtn) {
      activeBtn.classList.toggle("playing", playing);
      var icon = activeBtn.querySelector(".preview-icon");
      if (icon) icon.textContent = playing ? PAUSE_ICON : PLAY_ICON;
    }
    el("preview-bar-toggle").setAttribute("aria-label", playing ? "Pause" : "Resume");
    el("preview-bar-toggle-icon").textContent = playing ? TOGGLE_PAUSE_ICON : PLAY_ICON;
  }

  document.addEventListener("click", function (e) {
    if (e.target.closest("#preview-bar-toggle")) {
      if (!audio.src) return;
      if (audio.paused) audio.play();
      else audio.pause();
      return;
    }

    var progress = e.target.closest("#preview-bar-progress");
    if (progress) {
      if (!audio.src || !audio.duration) return;
      var rect = progress.getBoundingClientRect();
      var fraction = (e.clientX - rect.left) / rect.width;
      audio.currentTime = Math.max(0, Math.min(1, fraction)) * audio.duration;
      if (audio.paused) audio.play();
      return;
    }

    var btn = e.target.closest(".preview-btn");
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();

    var track = btn.dataset.previewTrack || "";
    var artist = btn.dataset.previewArtist || "";

    if (btn === activeBtn) {
      if (audio.ended) {
        audio.currentTime = 0;
        audio.play();
      } else if (audio.paused) {
        audio.play();
      } else {
        stop();
      }
      return;
    }

    play(track, artist);
  });

  document.addEventListener("input", function (e) {
    if (!e.target.closest("#preview-bar-volume")) return;
    audio.volume = parseFloat(e.target.value);
    localStorage.setItem(VOLUME_STORAGE_KEY, String(audio.volume));
  });

  audio.addEventListener("timeupdate", function () {
    saveSession();
    if (!audio.duration) return;
    el("preview-bar-fill").style.width = (audio.currentTime / audio.duration) * 100 + "%";
  });
  audio.addEventListener("play", syncPlayingState);
  audio.addEventListener("pause", function () {
    syncPlayingState();
    saveSession();
  });
  audio.addEventListener("ended", function () {
    audio.currentTime = 0;
    saveSession();
  });
  audio.addEventListener("error", function () {
    if (audio.src) stop();
  });

  document.addEventListener("htmx:afterSwap", relinkActiveBtn);
  window.addEventListener("popstate", function () {
    relinkActiveBtn();
    setTimeout(relinkActiveBtn, 0);
  });
  window.addEventListener("pagehide", saveSession);
  window.addEventListener("pageshow", function () {
    relinkActiveBtn();
    syncPlayingState();
  });

  restoreSession();
})();
