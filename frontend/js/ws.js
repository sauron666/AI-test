/* ── SAURON WebSocket live telemetry ─────────────── */
const WS = (() => {
  const listeners = new Set();
  let socket = null;
  let retry = 0;

  function url() {
    const scheme = location.protocol === "https:" ? "wss:" : "ws:";
    return `${scheme}//${location.host}/ws`;
  }

  function connect() {
    const dot = document.getElementById("ws-dot");
    const label = document.getElementById("ws-label");
    socket = new WebSocket(url());

    socket.onopen = () => {
      retry = 0;
      dot.classList.remove("offline");
      dot.classList.add("online");
      label.textContent = "live — sauron is watching";
    };

    socket.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data);
        listeners.forEach((fn) => fn(evt));
      } catch (err) {
        console.warn("ws parse", err);
      }
    };

    socket.onclose = () => {
      dot.classList.remove("online");
      dot.classList.add("offline");
      label.textContent = "disconnected — retrying…";
      setTimeout(connect, Math.min(30000, 1000 * 2 ** retry++));
    };

    socket.onerror = () => socket.close();
  }

  return {
    connect,
    subscribe: (fn) => {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    send: (obj) => socket && socket.readyState === 1 && socket.send(JSON.stringify(obj)),
  };
})();
