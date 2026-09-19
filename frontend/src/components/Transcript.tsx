import type { ChatMsg } from "../types";

/** Shows ONLY the last exchange — the reference style, no scrolling history. */
export function LastExchange({ messages }: { messages: ChatMsg[] }) {
  const lastUser = [...messages].reverse().find((m) => m.role === "user");
  const lastAstra = [...messages].reverse().find((m) => m.role === "assistant" && m.text.trim());

  if (!lastUser && !lastAstra) {
    return (
      <div className="text-center">
        <h1 className="text-4xl md:text-5xl font-semibold leading-tight">
          Hey Boss <br />
        </h1>
        <p className="mt-2 text-lg md:text-xl font-normal text-slate-400">Ziva is waiting for you.</p>
      </div>
    );
  }
  return (
    <div className="text-center max-w-2xl">
      {lastAstra && (
        <h1 className="text-2xl md:text-[28px] font-medium leading-snug line-clamp-4">
          {lastAstra.text}
        </h1>
      )}
      {lastUser && (
        <p className="mt-3 text-sm text-slate-500">
          You said: <span className="text-slate-300">“{lastUser.text}”</span>
        </p>
      )}
    </div>
  );
}
