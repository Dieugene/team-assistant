/** Timeline view for displaying TraceEvents. */

import type { TraceEvent } from "../types";
import "./Timeline.css";

interface TimelineProps {
  events: TraceEvent[];
}

/**
 * Timeline component - displays trace events chronologically (newest on top).
 */
export function Timeline({ events }: TimelineProps) {
  /**
   * Format event for display.
   */
  const formatEvent = (event: TraceEvent): string => {
    const timestamp = new Date(event.timestamp).toLocaleTimeString();
    const dataPreview = JSON.stringify(event.data).slice(0, 100);
    return `[${timestamp}] ${event.actor}: ${event.event_type} — ${dataPreview}`;
  };

  return (
    <div className="timeline">
      <h2>Timeline</h2>
      <div className="timeline-events">
        {events.length === 0 ? (
          <p className="timeline-empty">No events yet...</p>
        ) : (
          events.map((event) => (
            <div key={event.id} className="timeline-event">
              <pre>{formatEvent(event)}</pre>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
