"use client";

import { MessageCircle, Scale } from "lucide-react";
import { useMode, AppMode } from "../contexts/ModeContext";
import { cn } from "@/lib/utils";

interface ModeToggleProps {
  className?: string;
}

export function ModeToggle({ className }: ModeToggleProps) {
  const { mode, setMode } = useMode();

  const handleToggle = (newMode: AppMode) => {
    if (newMode !== mode) {
      setMode(newMode);
    }
  };

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
        Mode
      </div>

      {/* Pill Toggle */}
      <div
        className={cn(
          "relative flex p-1.5 rounded-xl transition-all duration-300",
          mode === "chat"
            ? "bg-blue-50 border border-blue-100"
            : "bg-slate-100 border border-slate-200"
        )}
      >
        {/* Sliding background indicator */}
        <div
          className={cn(
            "absolute top-1.5 bottom-1.5 w-[calc(50%-6px)] rounded-lg transition-all duration-300 ease-out shadow-sm",
            mode === "chat"
              ? "left-1.5 bg-white border border-blue-200"
              : "left-[calc(50%+3px)] bg-white border border-slate-300"
          )}
        />

        {/* Chat Mode Button */}
        <button
          onClick={() => handleToggle("chat")}
          className={cn(
            "relative z-10 flex-1 flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer",
            mode === "chat"
              ? "text-blue-600"
              : "text-slate-400 hover:text-slate-600"
          )}
        >
          <MessageCircle
            className={cn(
              "h-4 w-4 transition-transform duration-200",
              mode === "chat" && "scale-110"
            )}
          />
          <span>Chat</span>
        </button>

        {/* Analysis Mode Button */}
        <button
          onClick={() => handleToggle("analysis")}
          className={cn(
            "relative z-10 flex-1 flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer",
            mode === "analysis"
              ? "text-slate-800"
              : "text-slate-400 hover:text-slate-600"
          )}
        >
          <Scale
            className={cn(
              "h-4 w-4 transition-transform duration-200",
              mode === "analysis" && "scale-110"
            )}
          />
          <span>Analysis</span>
        </button>
      </div>

      {/* Mode Description */}
      <p
        className={cn(
          "text-xs leading-relaxed transition-colors duration-200",
          mode === "chat" ? "text-blue-600/70" : "text-slate-500"
        )}
      >
        {mode === "chat"
          ? "General legal Q&A with AI"
          : "Guided intake for deep case analysis"}
      </p>
    </div>
  );
}
