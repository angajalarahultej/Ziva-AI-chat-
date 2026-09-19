/** Backend location. Local dev defaults to localhost; production (Vercel)
 *  injects these at build time:
 *  VITE_API_URL=https://your-backend.example.com
 *  VITE_WS_URL=wss://your-backend.example.com
 */
export const API =
  (import.meta.env.VITE_API_URL as string | undefined) || "http://localhost:8000";

const wsFromApi = API.replace(/^http/, "ws");
export const WS_URL =
  (import.meta.env.VITE_WS_URL as string | undefined) || `${wsFromApi}/ws/voice`;
