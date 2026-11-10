// Finish an update before starting Python, so the page and wheel agree.
async function boot() {
  if ("serviceWorker" in navigator) {
    const controller = navigator.serviceWorker.controller;
    try {
      const registration = await navigator.serviceWorker.register("./service-worker.js", {
        updateViaCache: "none",
      });
      await registration.update().catch(() => {}); // Offline: use the installed copy.
      const pending = registration.installing || registration.waiting;
      if (pending) await new Promise(resolve => {
        const changed = () => {
          if (["activated", "redundant"].includes(pending.state)) resolve();
        };
        pending.addEventListener("statechange", changed);
        changed();
      });
      if (navigator.serviceWorker.controller !== controller) {
        location.reload();
        return;
      }
    } catch (error) {
      // Private browsing or a full cache must not prevent online conversion.
      console.warn("Offline cache unavailable", error);
    }
  }
  await import("./app.js");
}
boot();
