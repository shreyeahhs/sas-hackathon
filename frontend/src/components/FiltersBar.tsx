import React from 'react'

type Props = {
  categories: string[]
  category: string
  onCategoryChange: (c: string) => void
  query: string
  onQueryChange: (q: string) => void
}

export const FiltersBar: React.FC<Props> = ({ categories, category, onCategoryChange, query, onQueryChange }) => {
  return (
    <div className="group" style={{ gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
      <button
        className="button secondary"
        type="button"
        title="Filters"
        onClick={() => { /* reserved for future filter panel */ }}
      >
        Filter
      </button>
      <input
        type="text"
        placeholder="Search events (name, venue)…"
        value={query}
        onChange={e => onQueryChange(e.target.value)}
        style={{ minWidth: 260, flex: '1 1 auto' }}
      />
      <select 
        value={category} 
        onChange={e => onCategoryChange(e.target.value)}
        style={{ minWidth: 160 }}
      >
        <option value="">All categories</option>
        {categories.map(c => <option key={c} value={c}>{c}</option>)}
      </select>
      {(query || category) && (
        <button
          className="button secondary"
          type="button"
          onClick={() => { onQueryChange(''); onCategoryChange(''); }}
        >
          Clear
        </button>
      )}
    </div>
  )
}
