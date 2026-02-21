/** Type definitions for Team Assistant VS UI. */

export interface TraceEvent {
  id: string;
  event_type: string;
  actor: string;
  data: Record<string, unknown>;
  timestamp: string; // ISO 8601
}
