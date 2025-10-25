import React from "react";

export default function QuickReplies({replies = [], onSelect }) {
    return(
        <div
          style={{
            display:"flex",
            flexWrap:"wrap",
            gap:6,
            margininTop:6,
          }}
        >
            {replies.map((label) => (
                <button
                  key={label}
                  onClick={() => onSelect(label)}
                  style={{
                    border:"1px solid #ccc",
                    borderRadius:16,
                    padding:"4px 10px",
                    backgroundColor:"#fff",
                    cursor:"pointer",
                    fontSize:11,
                  }}
                >
                    {label}
                </button>
            ))}

        </div>
    )
}