import React, { useState, useRef, useEffect } from "react";
import { BsFillPersonCheckFill } from "react-icons/bs";

export default function ChatFloatingWindow({
  title = "SAS Travel Advisor",
  children,
}) {
  const [minimized, setMinimized] = useState(false);

  return (
    <div
      style={{
        position: "fixed",
        bottom: 20,
        right: 20,
        width: 360,
        boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
        borderRadius: 10,
        overflow: "hidden",
        background: "#fff",
        zIndex: 1000,
      }}
    >
      {/* Header bar */}
      <div
        style={{
          background: "linear-gradient(to bottom, #4F486B 0%, #A49DBE 100%)",
          color: "white",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "15px 12px",
          fontSize: 13,
          userSelect: "none",
        }}
      >
        <span>
          <BsFillPersonCheckFill fontSize="18" />
          You are speaking with <b>SAS Travel Advisor</b>
        </span>
        <button
          onClick={() => setMinimized((m) => !m)}
          title={minimized ? "Restore" : "Minimize"}
          style={{
            background: "transparent",
            border: "none",
            color: "white",
            fontSize: 16,
            cursor: "pointer",
            lineHeight: 1,
          }}
          onClick={(e) => {
            e.stopPropagation(); // prevent the click will affect the parent div
            setMinimized(!minimized);
          }}
        >
          {minimized ? "🗖" : "🗕"}
        </button>
      </div>

      {/* Chat body */}
      {!minimized && (
        <div style={{ maxHeight: "70vh", overflow: "hidden" }}>{children}</div>
      )}
    </div>
  );
}
