export interface RunEvent {
  eventId: string;
  sequence: number;
  runId: string;
  eventType: string;
  timestamp: string; // ISO String
  summary: string;
  stateVersion: number | null;
  metadata: Record<string, any>;
}
