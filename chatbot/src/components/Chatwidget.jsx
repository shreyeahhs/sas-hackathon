import React, { useState, useRef, useEffect } from "react";
import MessageBubble from "./MessageBubble";
import QuickReplies from "./QuickReplies"
import ChatFloatingWindow from "./ChatFloatingWindow";
import { BsFillChatRightDotsFill } from "react-icons/bs";

export default function ChatWidget() {
  const [open, setOpen] = useState(false); //control the round button; True = Chat Window
  const [loading, setloading] = useState(false); //Loading State, to disable the button/dispaly when typing...
  const [messages, setMessages] = useState([
    //Example chat records, can set up the welcome and QuickReplies here.
    {
      id: 1,
      role: "bot",
      text: "Hi! Would you like some nice recommendations for restaturant?! I am here to help!",
    },
    { id: 2, role: "user", text: "Please recommend me a good restaurant." },
  ]);
  const [text, setText] = useState(""); //Users input questions
  const endRef = useRef(null); //For rolling to the bottom

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);
  //When state of messages or window-open change, roll to the bottom
  const toggleOpen = () => setOpen(!open);

  //sending messages
  function handleSend(e) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: "user", text: trimmed },
    ]);
    setText("");
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "bot",
          text: "Requests recevied. I will give you best options as soon as possible!",
        },
      ]);
    }, timeout);
  }
  return (
    <div
      style={{
        position: "fixed",
        right: "max(16px, env(safe-area-inset-right))",
        bottom: "max(16px, env(safe-area-inset-bottom))",
        zIndex: 1000,
      }}
    >
      {!open && (
        <button
          onClick={toggleOpen}
          style={floatBtnStyle}
          title="Chat"
          aria-label="Open chat"
          size="25"
        >
          {<BsFillChatRightDotsFill />}
        </button>
      )}
      {open && (
        <ChatFloatingWindow title="SAS Chatbot">
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              height: "60vh",
              borderTop: "1px solid #5A4066",
              backgroundColor: "#F1EDF5",
            }}
          >
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                padding: 0,
                background: "#",
              }}
            >
              {messages.map((m) => (
                <div
                  key={m.id}
                  style={{
                    display: "flex",
                    justifyContent:
                      m.role === "user" ? "flex-end" : "flex-start",
                    margin: "6px 0",
                  }}
                ></div>
              ))}
            </div>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                height: "100vh",
                justifyContent: "center",
                background: "9F63F8",
              }}
            >
              {messages.map((msg) => (
                <MessageBubble key={msg.id} role={msg.role} text={msg.text} />
              ))}
            </div>
            <form //onSubmit={handleSend}
              style={{
                margininTop: 10,
                display: "flex",
                gap: 8,
              }}
            >
              <input
                //value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Enter your words here..."
                style={{
                  padding: 8,
                  width: 350,
                  borderRadius: 5,
                }}
              />
              <button
                class="submit-button"
                type="submit"
                style={{
                  width: 80,
                  borderRadius: 5,
                  backgroundColor: "#BEB6D3",
                  color: "#42294C",
                }}
              >
                send
              </button>
            </form>
          </div>
        </ChatFloatingWindow>
      )}
    </div>
  );
}

const floatBtnStyle = {
  width: 56,
  height: 56,
  borderRadius: "50%",
  border: "none",
  background: "rgba(57, 32, 133, 1)",
  color: "#fff",
  fontSize: 25,
  boxShadow: "0 6px 18px rgba(0,0,0,.2)",
  cursor: "pointer",
  alignItems:"center",
};

const chatPanelStyle = {
  width: 360,
  maxHeight: "70vh",
  background: "#fff",
  borderRadius: 12,
  boxShadow: "0 10px 30px rgba(0,0,0,.25)",
  display: "flex",
  flexDirection: "column",
  animation: "fadeUp .18s ease-out",
};

const titleBarStyle = {
  background: "#604ca0ff",
  color: "#fff",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "8px 12px",
  fontSize: 14,
};

const titleBtnStyle = {
  background: "transparent",
  border: "none",
  color: "#fff",
  fontSize: 18,
  cursor: "pointer",
};

const inputBarStyle = {
  display: "flex",
  gap: 8,
  padding: 10,
  borderTop: "1px solid #eee",
};

const inputStyle = {
  flex: 1,
  padding: 10,
  border: "1px solid #e5e7eb",
  borderRadius: 8,
};

const sendBtnStyle = {
  padding: "0 14px",
  borderRadius: 8,
  border: "1px solid #e5e7eb",
  background: "#f8fafc",
  cursor: "pointer",
};
