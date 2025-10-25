import React from "react";
import { BsHeadset } from "react-icons/bs";
import { BsSunglasses } from "react-icons/bs";

export default function MessageBubble({ role, text }) {
  const isUser = role === "user";

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: isUser ? "flex-end" : "flex-start", // ✅ 控制整行对齐
          margin: "8px 0",
          width: "100%",
        }}
      >
        <div
          style={{
            display: "flex",
            order: isUser ? 2 : 1,
            alignItems: "flex-end",
            margin: "8px 0",
            maxWidth: "50%",
          }}
        >
          {isUser ? (
            <BsSunglasses size="30" color="4F486B" />
          ) : (
            <BsHeadset size="30" color="4F486B" />
          )}
        </div>
        <div
          style={{
            order: isUser ? 1 : 2, //user's message at right side, computer at left
            backgroundColor: isUser ? "#998DBA" : "#B79FC3",
            color: "#F8F7FA",
            padding: "8px 12px",
            borderRadius: "12px",
            margin: "6px 0",
            maxWidth: "50%",
            fontSize: 12,
            boxShadow: "0 1px 2px rgba(0, 0, 0, 0.1)",
          }}
        >
          {text}
        </div>
      </div>
    </div>
  );
}

}