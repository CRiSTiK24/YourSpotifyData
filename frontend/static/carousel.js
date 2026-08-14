(function () {
  // Mouse drag-to-scroll for .carousel (see style.css - it's overflow-x:auto
  // with a hidden scrollbar). Touch/trackpad already get native scrolling
  // for free from overflow-x:auto, so this only handles pointerType
  // "mouse" - a touch drag here would fight the browser's own scroll
  // handling instead of complementing it. Delegated on document (like
  // tooltips.js) so it keeps working after htmx swaps #content, no
  // per-element init needed.

  var DRAG_THRESHOLD = 6; // px of movement before a mousedown counts as a drag, not a click
  var dragState = null;
  var justDragged = false;

  // Images and links are natively draggable (browser default), which
  // fights our own drag-to-scroll below with the native "drag this
  // image/link" ghost-preview gesture the moment the pointer moves - this
  // is what actually disables it; the -webkit-user-drag CSS on .carousel
  // img/a is only a same-effect hint WebKit honors earlier, before this
  // even runs.
  document.addEventListener("dragstart", function (e) {
    if (e.target.closest(".carousel")) e.preventDefault();
  });

  document.addEventListener("pointerdown", function (e) {
    if (e.pointerType !== "mouse" || e.button !== 0) return;
    var el = e.target.closest(".carousel");
    if (!el) return;
    dragState = {
      el: el,
      pointerId: e.pointerId,
      startX: e.clientX,
      startScrollLeft: el.scrollLeft,
      moved: false,
    };
  });

  document.addEventListener("pointermove", function (e) {
    if (!dragState || e.pointerId !== dragState.pointerId) return;
    var dx = e.clientX - dragState.startX;
    if (!dragState.moved) {
      if (Math.abs(dx) < DRAG_THRESHOLD) return;
      dragState.moved = true;
      dragState.el.setPointerCapture(e.pointerId);
      dragState.el.classList.add("carousel-dragging");
    }
    dragState.el.scrollLeft = dragState.startScrollLeft - dx;
  });

  function endDrag(e) {
    if (!dragState || e.pointerId !== dragState.pointerId) return;
    if (dragState.moved) {
      dragState.el.classList.remove("carousel-dragging");
      try {
        dragState.el.releasePointerCapture(e.pointerId);
      } catch (err) {}
      // consumed by the click handler below, which fires right after this
      justDragged = true;
    }
    dragState = null;
  }
  document.addEventListener("pointerup", endDrag);
  document.addEventListener("pointercancel", endDrag);

  // A drag ending on top of a card's link/play button would otherwise
  // still fire that element's click (mousedown+mouseup, wherever they
  // land, is exactly what a browser considers a click) - capture phase so
  // this runs, and can cancel it, before the link's own navigation does.
  document.addEventListener(
    "click",
    function (e) {
      if (!justDragged) return;
      justDragged = false;
      if (e.target.closest(".carousel")) {
        e.preventDefault();
        e.stopPropagation();
      }
    },
    true,
  );
})();
