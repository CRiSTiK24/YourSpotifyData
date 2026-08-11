(function () {
  // Defends against two Audio elements ever playing at once (heard as
  // "duplicated"/phased sound): this same script tag can only ever be
  // parsed once per document (it lives outside the htmx-boosted #content
  // swap, see page() in html.py), but the guard is cheap insurance against
  // that assumption ever breaking.
  if (window.__previewPlayerInitialized) return;
  window.__previewPlayerInitialized = true;

  var PLAY_ICON = "▶";
  var PAUSE_ICON = "⏸";
  var TOGGLE_PAUSE_ICON = "❚❚";
  var VOLUME_STORAGE_KEY = "previewVolume";
  var SESSION_KEY = "previewSession";

  var audio = new Audio();
  audio.volume = parseFloat(localStorage.getItem(VOLUME_STORAGE_KEY) || "1");
  var activeBtn = null;

  // The other, more likely, source of "duplicated" audio: two browser tabs
  // of this site each have their own independent Audio element, and if a
  // preview gets left running in a backgrounded tab, a second one started
  // elsewhere plays right on top of it. Reloading the tab you're looking
  // at kills that tab's own player and so *looks* like it fixed things,
  // even though the real fix is telling every other tab to stand down
  // whenever one of them starts playing.
  var channel = "BroadcastChannel" in window ? new BroadcastChannel("preview-audio") : null;
  if (channel) {
    channel.onmessage = function (e) {
      if (e.data === "stop") stop();
    };
  }

  var bar = document.getElementById("preview-bar");
  var barTrack = document.getElementById("preview-bar-track");
  var barArtist = document.getElementById("preview-bar-artist");
  var barFill = document.getElementById("preview-bar-fill");
  var barProgress = document.getElementById("preview-bar-progress");
  var barToggle = document.getElementById("preview-bar-toggle");
  var barToggleIcon = document.getElementById("preview-bar-toggle-icon");
  var barVolume = document.getElementById("preview-bar-volume");
  barVolume.value = audio.volume;

  function reset(btn) {
    btn.classList.remove("playing");
    var icon = btn.querySelector(".preview-icon");
    if (icon) icon.textContent = PLAY_ICON;
  }

  function showBar(track, artist) {
    barTrack.textContent = track;
    barArtist.textContent = artist;
    bar.hidden = false;
    document.body.classList.add("preview-bar-visible");
  }

  function hideBar() {
    bar.hidden = true;
    document.body.classList.remove("preview-bar-visible");
  }

  // Boosted navigation (hx-boost) never tears down this script or the
  // audio element - only the #content swap happens - so playback carries
  // on uninterrupted as you browse, same as a real media player. A real
  // navigation (typed URL, reload, a non-boosted redirect) does destroy
  // everything, which is what this persists against: the position gets
  // written to sessionStorage continuously, and restoreSession() below
  // reads it back on the next fresh page load so going back (or just
  // reloading) reopens the bar at the same track and moment, rather than
  // silently losing it.
  function saveSession() {
    if (!audio.src) return;
    var track = activeBtn ? activeBtn.dataset.previewTrack : barTrack.textContent;
    var artist = activeBtn ? activeBtn.dataset.previewArtist : barArtist.textContent;
    if (!track) return;
    sessionStorage.setItem(
      SESSION_KEY,
      JSON.stringify({ track: track, artist: artist, time: audio.currentTime || 0 })
    );
  }

  // Only called when the user explicitly stops a track (clicking its own
  // playing button) - navigating away must NOT clear the session, since
  // the whole point is picking it back up on the far side of that.
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

  // After a boosted swap or a history (back/forward) restore, the DOM
  // activeBtn pointed at may be gone (or, for a history-cache restore, a
  // stale snapshot of a button that's no longer actually playing) - relink
  // to a same-track/artist button if this page happens to render one, and
  // sweep away any other "playing" icon that doesn't match reality.
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
  }

  function play(track, artist) {
    var wasActive = activeBtn;
    if (wasActive) reset(wasActive);
    activeBtn = findMatchingButton(track, artist);
    showBar(track, artist);
    if (channel) channel.postMessage("stop");
    audio.src = "/preview?track=" + encodeURIComponent(track) + "&artist=" + encodeURIComponent(artist);
    audio.play().catch(function () {
      if (barTrack.textContent === track) stop();
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
      if (audio.duration) barFill.style.width = (resumeAt / audio.duration) * 100 + "%";
    });
    // Deliberately not auto-playing: browsers block autoplay-with-sound
    // without a fresh user gesture anyway, and resuming sound the instant
    // a page loads would be a jarring surprise even where it's allowed -
    // this just puts the player back where it was, one click from resuming.
    syncPlayingState();
  }

  function syncPlayingState() {
    var playing = !audio.paused && !audio.ended;
    if (activeBtn) {
      activeBtn.classList.toggle("playing", playing);
      var icon = activeBtn.querySelector(".preview-icon");
      if (icon) icon.textContent = playing ? PAUSE_ICON : PLAY_ICON;
    }
    barToggle.setAttribute("aria-label", playing ? "Pause" : "Resume");
    barToggleIcon.textContent = playing ? TOGGLE_PAUSE_ICON : PLAY_ICON;
  }

  document.addEventListener("click", function (e) {
    if (e.target.closest("#preview-bar-toggle")) {
      if (!audio.src) return;
      if (audio.paused) audio.play();
      else audio.pause();
      return;
    }

    var btn = e.target.closest(".preview-btn");
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();

    var track = btn.dataset.previewTrack || "";
    var artist = btn.dataset.previewArtist || "";

    if (btn === activeBtn) {
      // Ended (played through to the end) restarts from the top; merely
      // paused resumes where it left off; actively playing toggles off -
      // otherwise the only way to replay a finished preview was to click
      // a different track's button first, since audio.play() on an
      // already-ended element with currentTime still at the end is a
      // no-op.
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

  barProgress.addEventListener("click", function (e) {
    if (!audio.src || !audio.duration) return;
    var rect = barProgress.getBoundingClientRect();
    var fraction = (e.clientX - rect.left) / rect.width;
    audio.currentTime = Math.max(0, Math.min(1, fraction)) * audio.duration;
    // Seeking on an ended (or manually paused) track wouldn't otherwise
    // resume playback on its own - without this, clicking a point on the
    // bar after a preview finished would silently move the position with
    // no audible feedback.
    if (audio.paused) audio.play();
  });

  barVolume.addEventListener("input", function () {
    audio.volume = parseFloat(barVolume.value);
    localStorage.setItem(VOLUME_STORAGE_KEY, String(audio.volume));
  });

  audio.addEventListener("timeupdate", function () {
    saveSession();
    if (!audio.duration) return;
    barFill.style.width = (audio.currentTime / audio.duration) * 100 + "%";
  });
  audio.addEventListener("play", syncPlayingState);
  audio.addEventListener("pause", function () {
    syncPlayingState();
    saveSession();
  });
  // Not stop(): the "ended" transition already pauses (syncPlayingState
  // via the "pause" event handles the icon/aria-label), but the bar,
  // activeBtn, and audio.src all stay intact so the toggle button or
  // clicking the progress bar can still replay the same track - only
  // resetting currentTime so a subsequent play() doesn't just re-fire
  // "ended" immediately by starting already at the end.
  audio.addEventListener("ended", function () {
    audio.currentTime = 0;
    saveSession();
  });
  audio.addEventListener("error", function () {
    if (audio.src) stop();
  });

  document.addEventListener("htmx:afterSwap", relinkActiveBtn);
  window.addEventListener("popstate", relinkActiveBtn);
  window.addEventListener("pagehide", saveSession);

  restoreSession();
})();
