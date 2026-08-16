(function () {
  var DRAG_THRESHOLD_PX = 6;
  var dragState = null;
  var justDragged = false;

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
      if (Math.abs(dx) < DRAG_THRESHOLD_PX) return;
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
      justDragged = true;
    }
    dragState = null;
  }
  document.addEventListener("pointerup", endDrag);
  document.addEventListener("pointercancel", endDrag);

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
