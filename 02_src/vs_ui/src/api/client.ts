/** Polling API client for TraceEvents. */

import type { TraceEvent } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface TraceEventsParams {
  after?: string;
  limit?: number;
  event_type?: string;
  actor?: string;
}

/**
 * Polling client for fetching trace events from the API.
 */
export class ApiClient {
  private polling: boolean = false;
  private pollingTimer: ReturnType<typeof setInterval> | null = null;
  private lastTimestamp: string | null = null;
  private isRequestInProgress: boolean = false;

  /**
   * Fetch trace events with optional filters.
   */
  async getTraceEvents(
    params: TraceEventsParams = {}
  ): Promise<TraceEvent[]> {
    const searchParams = new URLSearchParams();

    if (params.after) {
      searchParams.append("after", params.after);
    }
    if (params.limit) {
      searchParams.append("limit", params.limit.toString());
    }
    if (params.event_type) {
      searchParams.append("event_type", params.event_type);
    }
    if (params.actor) {
      searchParams.append("actor", params.actor);
    }

    const url = `${API_BASE_URL}/api/trace-events?${searchParams.toString()}`;

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return response.json();
  }

  /**
   * Start polling for trace events every 2-3 seconds.
   * Calls the callback with new events.
   */
  startPolling(
    onNewEvents: (events: TraceEvent[]) => void,
    interval: number = 3000
  ): void {
    if (this.polling) {
      return;
    }

    this.polling = true;

    const poll = async () => {
      if (!this.polling || this.isRequestInProgress) {
        return;
      }

      this.isRequestInProgress = true;

      try {
        const events = await this.getTraceEvents({
          after: this.lastTimestamp || undefined,
          limit: 50,
        });

        if (events.length > 0) {
          // Update last timestamp
          this.lastTimestamp = events[0].timestamp; // Events are newest first
          onNewEvents(events);
        }
      } catch (error) {
        console.error("Polling error:", error);
      } finally {
        this.isRequestInProgress = false;
      }

      if (this.polling) {
        this.pollingTimer = setTimeout(poll, interval);
      }
    };

    poll();
  }

  /**
   * Stop polling.
   */
  stopPolling(): void {
    this.polling = false;
    if (this.pollingTimer) {
      clearTimeout(this.pollingTimer);
      this.pollingTimer = null;
    }
  }

  /**
   * Reset the last timestamp to fetch all events.
   */
  reset(): void {
    this.lastTimestamp = null;
  }
}
