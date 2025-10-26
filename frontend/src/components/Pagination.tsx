import React from 'react'

type Props = {
  page: number
  totalPages: number
  onPageChange: (p: number) => void
}

export const Pagination: React.FC<Props> = ({ page, totalPages, onPageChange }) => {
  if (totalPages <= 1) return null
  const pages = Array.from({ length: totalPages }, (_, i) => i + 1)
  return (
    <div className="pagination">
      <button disabled={page === 1} onClick={() => onPageChange(page - 1)}>Prev</button>
      {pages.map(p => (
        <button key={p} className={p === page ? 'active' : ''} onClick={() => onPageChange(p)}>{p}</button>
      ))}
      <button disabled={page === totalPages} onClick={() => onPageChange(page + 1)}>Next</button>
    </div>
  )
}
