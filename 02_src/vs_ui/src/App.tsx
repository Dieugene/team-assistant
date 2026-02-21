/** Main App component. */

import { useEffect, useState } from "react";
import { ApiClient } from "./api/client";
import type { TraceEvent } from "./types";
import { Timeline } from "./views/Timeline";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * Main application component.
 */
function App() {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [client] = useState(() => new ApiClient());

  useEffect(() => {
    // Start polling for events
    client.startPolling((newEvents) => {
      setEvents((prev) => {
        const seen = new Set(prev.map((event) => event.id));
        const deduped = newEvents.filter((event) => !seen.has(event.id));
        return [...deduped, ...prev];
      });
    });

    // Cleanup on unmount
    return () => {
      client.stopPolling();
    };
  }, [client]);

  const handleReset = async () => {
    try {
      await fetch(`${API_URL}/api/control/reset`, {
        method: "POST",
      });
      // Clear local events
      setEvents([]);
      client.reset();
    } catch (error) {
      console.error("Reset failed:", error);
    }
  };

  const handleStartSim = async () => {
    try {
      await fetch(`${API_URL}/api/control/sim/start`, {
        method: "POST",
      });
    } catch (error) {
      console.error("Start SIM failed:", error);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Team Assistant - VS UI</h1>
        <div className="controls">
          <button onClick={handleStartSim}>Start SIM</button>
          <button onClick={handleReset}>Reset</button>
        </div>
      </header>
      <main className="app-main">
        <Timeline events={events} />
      </main>
    </div>
  );
}

export default App;
