// This was vibecoded so you can alter some stuff here and also the css

import { DollarSign, Clock } from "lucide-react";
import "./Steps.css";

const budgets = [
  { id: "low",    label: "Budget-Friendly", range: "£-££",       icon: "💸" },
  { id: "medium", label: "Moderate",        range: "££-£££",     icon: "💰" },
  { id: "high",   label: "Premium",         range: "£££-££££",   icon: "💎" },
];

function BudgetTime({ preferences = {}, setPreferences }){
  return (
    <div className="step-container">
      <div className="header">
        <h2 className="title">Budget & Time</h2>
        <p className="subtitle">Let's make sure we find the perfect spots for you</p>
      </div>

      {/* Budget */}
      <div className="section">
        <div className="row">
          <DollarSign className="icon-prefix" />
          <label className="label">Budget</label>
        </div>

        <div className="budget-grid">
          {budgets.map((b) => {
            const isSelected = preferences.budget === b.id;
            return (
              <button
                key={b.id}
                type="button"
                aria-pressed={isSelected}
                onClick={() => setPreferences({ ...preferences, budget: b.id })}
                className={`card-btn card-btn--row ${isSelected ? "card-btn--active" : ""}`}
              >
                <span className="budget-emoji">{b.icon}</span>
                <div className="budget-text">
                  <div className="budget-label">{b.label}</div>
                  <div className="budget-range">{b.range}</div>
                </div>
                <div className={`badge ${isSelected ? "badge--on" : ""}`}>
                  <div className="dot" />
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Time */}
      <div className="section">
        <div className="row">
          <Clock className="icon-prefix icon-secondary" />
          <label className="label">Available Time</label>
        </div>

        <select
          className="select"
          value={preferences.availableTime || ""}
          onChange={(e) =>
            setPreferences({ ...preferences, availableTime: e.target.value })
          }
        >
          <option value="" disabled>Select duration</option>
          <option value="2-3">2-3 hours (Quick night)</option>
          <option value="4-5">4-5 hours (Full evening)</option>
          <option value="6+">6+ hours (All night long)</option>
        </select>
      </div>
    </div>
  );
};
export default BudgetTime;