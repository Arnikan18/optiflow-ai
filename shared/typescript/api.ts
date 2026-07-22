import { RunEvent } from './events';

export interface CreateRunForm {
  goal: string;
  scenarioId: string;
}

export interface CreateRunResponse {
  runId: string;
  status: string;
  eventsUrl: string;
}

export interface SystemHealthResponse {
  status: string;
  services: {
    core: string;
    postgres: string;
    crm: string;
    incident: string;
    workforce: string;
    communication: string;
  };
}
