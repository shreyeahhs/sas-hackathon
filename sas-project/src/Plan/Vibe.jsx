// This was vibecoded so you can alter some stuff here and also the css

import { Smile, PartyPopper, Heart, Zap } from "lucide-react";
import "./Steps.css";

const moods = [
  { id: "chill",        label: "Chill",        emoji: "😌", icon: Smile,       desc: "Relaxed vibes" },
  { id: "party",        label: "Party",        emoji: "🎉", icon: PartyPopper, desc: "High energy" },
  { id: "romantic",     label: "Romantic",     emoji: "💕", icon: Heart,       desc: "Date night" },
  { id: "adventurous",  label: "Adventurous",  emoji: "⚡", icon: Zap,         desc: "Try something new" },
];


function Vibe({ preferences = {}, setPreferences }){

  const groupSize = preferences.groupSize ?? 2;

return (
    <div className="step-container">
      <div className="header">
        <h2 className="title">What's the vibe?</h2>
        <p className="subtitle">Tell us what kind of night you're looking for</p>
      </div>

      {/* Mood Selection */}
      <div className="mood-grid">
        {moods.map((mood) => {
          const Icon = mood.icon;
          const isSelected = preferences.mood === mood.id;

          return (
            <button
              key={mood.id}
              type="button"
              aria-pressed={isSelected}
              onClick={() => setPreferences({ ...preferences, mood: mood.id })}
              className={`card-btn ${isSelected ? "card-btn--active" : ""}`}
            >
              <div className="mood-card">
                <div className="mood-emoji">{mood.emoji}</div>
                <Icon className={`mood-icon ${isSelected ? "mood-icon--active" : ""}`} />
                <div className="mood-text">
                  <div className="mood-label">{mood.label}</div>
                  <div className="mood-desc">{mood.desc}</div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Group Size */}
      <div className="group">
        <div className="row">
          <label className="label">Group Size</label>
          <span className="pill">{groupSize}</span>
        </div>

        <input
          className="range"
          type="range"
          min="1"
          max="20"
          step="1"
          value={groupSize}
          onChange={(e) =>
            setPreferences({ ...preferences, groupSize: Number(e.target.value) })
          }
        />

        <div className="range-notes">
          <span>Solo</span>
          <span>Small group</span>
          <span>Large party</span>
        </div>
      </div>
    </div>
  );
}
export default Vibe;

