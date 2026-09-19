export type AstraState = "OFFLINE" | "INITIALIZING" | "ONLINE" | "LISTENING" | "PROCESSING" | "SPEAKING" | "INTERRUPTED" | "ERROR";

export interface ChatMsg {
  role: "user" | "assistant";
  text: string;
}
