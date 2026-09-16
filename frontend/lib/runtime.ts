import { api } from "@/lib/api";

export interface RuntimeConfiguration {
  ai_provider: string;
  ai_model: string;
  local_ai: boolean;
  discovery_provider: string;
}

export function getRuntimeConfiguration(): Promise<RuntimeConfiguration> {
  return api.get<RuntimeConfiguration>("/runtime/configuration");
}
