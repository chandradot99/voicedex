// Voice samples: one shared <audio>, one playing at a time; the button shows the state.
(() => {
  const audio = new Audio();
  audio.preload = "none";
  let current = null;

  const reset = () => {
    if (current) current.setAttribute("aria-pressed", "false");
    current = null;
  };
  audio.addEventListener("ended", reset);
  audio.addEventListener("error", () => {
    if (current) current.setAttribute("aria-label", "Sample unavailable");
    reset();
  });

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("button.play");
    if (!btn) return;
    if (btn === current) {
      audio.pause();
      reset();
      return;
    }
    reset();
    current = btn;
    btn.setAttribute("aria-pressed", "true");
    audio.src = btn.dataset.src;
    audio.play().catch(reset);
  });

  document.querySelectorAll("button.play").forEach((b) => b.setAttribute("aria-pressed", "false"));
})();
